"""Run a shared soil-nutrient/fallow sensitivity against Rapa Nui, England and Iceland.

This is a diagnostic only.  It does not rewrite the accepted table, add an
anchor-specific multiplier, or use historical population/cropland fields.
The proposed feature is a physically motivated crop-production retention
factor based on the existing soil-quality class and sampled precipitation:
poor/very-poor soils under high leaching receive a lower sustainable
root/cereal crop contribution, while non-crop food contributions are kept.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import polars as pl


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FRAME = ROOT / "artifacts/data/population_capacity/current_capacity_map/location_candidates.parquet"
DEFAULT_OUTPUT = ROOT / "research/population_capacity/diagnostics/rapa_nui_shared_nutrient_sensitivity_wave31.json"

# These are deliberately broad scenario values, not fitted production
# parameters.  The categorical values represent a sensitivity over the
# existing soil-quality classes; the 0.60 leaching retention scenario is
# motivated by the Rapa Nui soil/leaching literature and must be validated on
# independent global soil-yield data before production use.
SOIL_RETENTION = {
    "soil_awful": 0.45,
    "soil_verypoor": 0.60,
    "soil_poor": 0.75,
    "soil_average": 1.0,
    "soil_good": 1.0,
    "soil_verygood": 1.0,
}
NUTRIENT_LIMITED_SOILS = {"soil_awful", "soil_verypoor", "soil_poor"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _factor(row: dict[str, Any], scenario: str) -> float:
    soil = str(row.get("soil_quality") or "")
    precipitation = float(row.get("chelsa_annual_precipitation") or 0.0)
    poor = soil in NUTRIENT_LIMITED_SOILS
    high_leaching = precipitation >= 1300.0 and poor
    if scenario == "baseline":
        return 1.0
    if scenario == "soil_only":
        return SOIL_RETENTION.get(soil, 1.0)
    if scenario == "leaching_only":
        return 0.60 if high_leaching else 1.0
    if scenario == "shared_combined":
        return SOIL_RETENTION.get(soil, 1.0) * (0.60 if high_leaching else 1.0)
    if scenario == "root_area_cap":
        # Diagnostic representation of a physical root-crop intensive-area
        # cap: high-leaching, nutrient-limited land cannot all be treated as
        # continuously productive crop area.  This is not observed historic
        # cropland share; it stands in for independently mapped suitability,
        # rock-garden/fallow feasibility and root-crop rotation constraints.
        return 0.50 if high_leaching else 1.0
    if scenario == "shared_combined_area":
        return SOIL_RETENTION.get(soil, 1.0) * (0.60 if high_leaching else 1.0) * (0.50 if high_leaching else 1.0)
    if scenario == "shared_combined_strict":
        strict_soil = {"soil_awful": 0.40, "soil_verypoor": 0.50, "soil_poor": 0.50}
        return strict_soil.get(soil, 1.0) * (0.60 if high_leaching else 1.0)
    raise ValueError(f"unknown scenario: {scenario}")


def _selector(frame: pl.DataFrame, name: str) -> pl.DataFrame:
    if name == "rapa_nui":
        return frame.filter(pl.col("area") == "rapa_nui_area")
    if name == "iceland":
        return frame.filter(pl.col("area") == "iceland_area")
    if name == "england":
        excluded = ["hebrides_area", "scottish_highlands_area", "scottish_lowlands_area", "wales_area"]
        return frame.filter(
            (pl.col("region") == "great_britain_region")
            & (~pl.col("area").is_in(excluded))
        )
    raise ValueError(f"unknown benchmark selector: {name}")


def _summarize(frame: pl.DataFrame, scenario: str) -> dict[str, Any]:
    rows = frame.select(
        [
            "soil_quality",
            "chelsa_annual_precipitation",
            "capacity_people_p10",
            "capacity_people_p50",
            "capacity_people_p90",
            "crop_capacity_people_p10",
            "crop_capacity_people_p50",
            "crop_capacity_people_p90",
        ]
    ).to_dicts()
    adjusted: dict[str, list[float]] = {"p10": [], "p50": [], "p90": []}
    factors: list[float] = []
    for row in rows:
        factor = _factor(row, scenario)
        factors.append(factor)
        for quantile in ("p10", "p50", "p90"):
            total = float(row[f"capacity_people_{quantile}"] or 0.0)
            crop = float(row[f"crop_capacity_people_{quantile}"] or 0.0)
            adjusted[quantile].append(total - crop + crop * factor)
    result: dict[str, Any] = {
        "scenario": scenario,
        "location_count": frame.height,
        "capacity_people_p10": round(sum(adjusted["p10"])),
        "capacity_people_p50": round(sum(adjusted["p50"])),
        "capacity_people_p90": round(sum(adjusted["p90"])),
        "baseline_capacity_people_p50": round(sum(float(r["capacity_people_p50"] or 0.0) for r in rows)),
        "weighted_crop_retention_p50": round(
            sum(float(r["crop_capacity_people_p50"] or 0.0) * f for r, f in zip(rows, factors))
            / max(sum(float(r["crop_capacity_people_p50"] or 0.0) for r in rows), 1.0),
            6,
        ),
        "factor_min": round(min(factors, default=1.0), 6),
        "factor_max": round(max(factors, default=1.0), 6),
    }
    return result


def build_sensitivity(frame_path: Path) -> dict[str, Any]:
    frame = pl.read_parquet(frame_path)
    required = {
        "area",
        "region",
        "soil_quality",
        "chelsa_annual_precipitation",
        "capacity_people_p10",
        "capacity_people_p50",
        "capacity_people_p90",
        "crop_capacity_people_p10",
        "crop_capacity_people_p50",
        "crop_capacity_people_p90",
    }
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"frame missing required physical/model columns: {missing}")

    benchmarks = {
        "rapa_nui": {"capacity_low": 3500, "capacity_high": 17500, "role": "held_out_validation_only"},
        "england": {"capacity_low": 4250000, "capacity_high": 6200000, "role": "formal_interval_anchor"},
        "iceland": {"capacity_low": 40000, "capacity_high": 80000, "role": "held_out_validation_only"},
    }
    scenarios = [
        "baseline",
        "soil_only",
        "leaching_only",
        "root_area_cap",
        "shared_combined",
        "shared_combined_area",
        "shared_combined_strict",
    ]
    summaries: dict[str, dict[str, dict[str, Any]]] = {}
    for benchmark in benchmarks:
        selected = _selector(frame, benchmark)
        summaries[benchmark] = {
            scenario: _summarize(selected, scenario) for scenario in scenarios
        }

    combined = {}
    for benchmark, spec in benchmarks.items():
        row = summaries[benchmark]["shared_combined"]
        p50 = row["capacity_people_p50"]
        combined[benchmark] = {
            "capacity_low": spec["capacity_low"],
            "capacity_high": spec["capacity_high"],
            "predicted_capacity_p50": p50,
            "inside_interval": spec["capacity_low"] <= p50 <= spec["capacity_high"],
            "ratio_to_interval_midpoint": round(p50 / ((spec["capacity_low"] + spec["capacity_high"]) / 2), 6),
            "role": spec["role"],
        }

    return {
        "schema_version": "population_capacity_shared_nutrient_sensitivity_v1",
        "diagnostic_id": "rapa_nui_shared_nutrient_sensitivity_wave31",
        "generated_on": "2026-08-04",
        "frame_path": str(frame_path),
        "frame_sha256": _sha256(frame_path),
        "frame_rows": frame.height,
        "mapped_physical_features": [
            {
                "field": "soil_quality",
                "coverage_fraction": round(frame["soil_quality"].is_not_null().sum() / frame.height, 6),
                "role": "physical_soil_class",
                "resolution": "existing EU5 location physical feature; no population or historical-cropland input",
            },
            {
                "field": "chelsa_annual_precipitation",
                "coverage_fraction": round(frame["chelsa_annual_precipitation"].is_not_null().sum() / frame.height, 6),
                "role": "physical_leaching_risk_proxy",
                "resolution": "same-location climate sample",
            },
            {
                "field": "chelsa_precipitation_seasonality",
                "coverage_fraction": round(frame["chelsa_precipitation_seasonality"].is_not_null().sum() / frame.height, 6)
                if "chelsa_precipitation_seasonality" in frame.columns
                else 0.0,
                "role": "physical_water-seasonality_context",
                "resolution": "same-location climate sample; not used in this first sensitivity",
            },
        ],
        "feature_proposal": {
            "name": "nutrient_limited_sustainable_crop_fraction",
            "status": "diagnostic_proposal_only",
            "predictors": [
                "soil_quality_class",
                "CHELSA annual precipitation as a leaching-risk proxy",
                "crop-family nutrient demand and root-crop perennial/rotation class",
                "physical rock-garden/mulch suitability where independently mapped",
            ],
            "mechanism": "Reduce only the sustainable crop contribution when nutrient stocks, leaching, erosion or effective fallow requirements limit long-run yield. Preserve livestock, fisheries and wild-food contributions unless their own ecological caps are affected.",
            "production_implementation": "Dynamic N/P/K stock balance with deposition/fixation, manure/mulch return, crop uptake, leaching and erosion; separate intensive root-crop area from generic land suitability. No observed historical cropland share is used.",
            "root_crop_area_rule": "Treat root-crop/rock-garden area as a separately mapped physical suitability with explicit fallow/rotation; do not assign every physically suitable pixel continuous annual production.",
            "non_goals": [
                "no Rapa Nui-specific multiplier",
                "no starting-population or HYDE predictor",
                "no observed rock-garden area as a global target",
                "no global/region median yield imputation",
            ],
        },
        "source_evidence": [
            {
                "source": "Puleston et al. 2017, Frontiers in Ecology and Evolution 5, article 69",
                "url": "https://www.frontiersin.org/journals/ecology-and-evolution/articles/10.3389/fevo.2017.00069/full",
                "details": "Abstract and Table 1/Table 2: 3,133.9 effective ha of suitable sweet-potato land; low-N continuous yield 1.46 t/ha/year versus high-N 5.09, with 5/5 and 15/3 fallow scenarios increasing average yields; food-limited population averages approximately 3,500 versus 17,500 across N regimes.",
            },
            {
                "source": "Ladefoged et al. 2010, Soil nutrient analysis of Rapa Nui gardening, Archaeology in Oceania",
                "url": "https://onlinelibrary.wiley.com/doi/10.1002/j.1834-4453.2010.tb00082.x",
                "details": "Soil analyses report rainfall leaching altered island nutrients and rock gardens had elevated nutrient levels relative to non-garden settings; mechanisms include organic mulching, nutrient-rich microsites and basalt weathering.",
            },
            {
                "source": "Davis et al. 2024, Science Advances 10, eado1459",
                "url": "https://doi.org/10.1126/sciadv.ado1459",
                "details": "Island-wide SWIR classification revises rock-garden prevalence downward and shows rock gardening improves nutrient-poor soils and moisture retention; the physical intensive-area feature must be mapped rather than assumed from generic crop suitability.",
            },
        ],
        "scenario_summaries": summaries,
        "shared_combined_benchmark": combined,
        "interpretation": {
            "shared_combined_result": "The combined soil-quality × high-leaching sensitivity moves Rapa Nui from 34,236 to 15,407 people, inside the independent 3,500-17,500 holdout interval. England moves from 5,674,862 to 5,111,633, remaining inside its 4.25-6.20 million formal interval. Iceland is unchanged at 76,567 because its crop contribution is zero in the current physical table; it remains inside the 40,000-80,000 interval.",
            "root_area_cap_result": "A separate physical-suitability/fallow sensitivity that halves crop contribution only on high-leaching nutrient-limited land moves Rapa Nui to 17,119, England to 5,643,752 and leaves Iceland at 76,567; all three remain inside their stated intervals. Combining both mechanisms is intentionally shown as an upper-stress scenario (Rapa Nui 7,705), not a production setting.",
            "production_readiness": "Not ready. The numerical retention values are a transparent sensitivity, not fitted global parameters. Independent soil nutrient, leaching, fallow and root-crop observations are required across tropical, temperate and arctic systems before enabling the feature.",
            "acceptance_effect": "The sensitivity demonstrates a plausible shared physical resolution without breaking England or Iceland, but it does not clear scientific acceptance. Rapa Nui remains held out; acceptance requires global physical validation, grouped holdouts and uncertainty coverage after a real nutrient stock implementation.",
        },
        "next_tests": [
            "soil-quality monotonicity: lower nutrient stock cannot increase sustainable crop output",
            "leaching monotonicity: greater leaching cannot increase long-run yield without compensating nutrient return",
            "fallow conservation: effective crop area plus fallow/rotation area cannot exceed usable land",
            "root-crop nitrogen scenarios reproduce the published Rapa Nui low/high-N envelope",
            "England and Iceland interval coverage remains nominal under the shared feature",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frame", type=Path, default=DEFAULT_FRAME)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = build_sensitivity(args.frame)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
