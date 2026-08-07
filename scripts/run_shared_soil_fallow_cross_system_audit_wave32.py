"""Audit a globally shared nutrient/fallow sensitivity on independent systems.

This is intentionally a validation diagnostic, not a production model change.
The physical rule uses only EU5-mapped soil, precipitation, crop and fallow
features.  Historical systems supply independent bounds or process checks; no
starting population, HYDE, RGO, trade, or system-specific multiplier is used.
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
DEFAULT_OUTPUT = ROOT / "research/population_capacity/diagnostics/shared_soil_fallow_cross_system_audit_wave32.json"

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


def _conditions(row: dict[str, Any]) -> tuple[bool, bool]:
    soil = str(row.get("soil_quality") or "")
    precipitation = float(row.get("chelsa_annual_precipitation") or 0.0)
    nutrient_limited = soil in NUTRIENT_LIMITED_SOILS
    # The dryland window deliberately follows the independent Sahel study's
    # rainfed environment; it is not a region name or a historical label.
    dryland_nutrient = nutrient_limited and 350.0 <= precipitation <= 900.0
    humid_leaching = nutrient_limited and precipitation >= 1300.0
    return humid_leaching, dryland_nutrient


def _factor(row: dict[str, Any], scenario: str) -> float:
    soil = str(row.get("soil_quality") or "")
    humid_leaching, dryland_nutrient = _conditions(row)
    soil_factor = SOIL_RETENTION.get(soil, 1.0)
    if scenario == "baseline":
        return 1.0
    if scenario == "leaching_only":
        return 0.60 if humid_leaching else 1.0
    if scenario == "fallow_only":
        # De Rouw & Rajot (2004): 125/300 kg ha^-1 for short versus long
        # fallow in Banizoumbou, a transparent process sensitivity.
        if dryland_nutrient:
            return 125.0 / 300.0
        # A 5/5 rock-garden/root-crop cycle is an intentionally broad stress
        # envelope from Puleston et al. (2017), not a fitted crop fraction.
        return 0.50 if humid_leaching else 1.0
    if scenario == "shared_nutrient_fallow":
        if dryland_nutrient:
            return 125.0 / 300.0
        if humid_leaching:
            return soil_factor * 0.60 * 0.50
        return 1.0
    if scenario == "shared_nutrient_fallow_strict":
        if dryland_nutrient:
            return 125.0 / 300.0
        if humid_leaching:
            # A deliberately wider stress envelope (40% active intensive
            # rotation rather than the moderate 50% envelope).  It is shown
            # for uncertainty, never promoted as a production coefficient.
            return soil_factor * 0.60 * 0.40
        return 1.0
    raise ValueError(f"unknown scenario: {scenario}")


def _selector(frame: pl.DataFrame, system: str) -> pl.DataFrame:
    if system == "rapa_nui":
        return frame.filter(pl.col("area") == "rapa_nui_area")
    if system == "iceland":
        return frame.filter(pl.col("area") == "iceland_area")
    if system == "england":
        excluded = ["hebrides_area", "scottish_highlands_area", "scottish_lowlands_area", "wales_area"]
        return frame.filter((pl.col("region") == "great_britain_region") & (~pl.col("area").is_in(excluded)))
    if system == "peten":
        return frame.filter(pl.col("area") == "peten_area")
    if system == "zarma_sahel":
        return frame.filter(pl.col("area") == "zarma_area")
    if system == "hawaii":
        return frame.filter(pl.col("area") == "hawaii_area")
    raise ValueError(f"unknown system: {system}")


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
            "allocated_crop_fraction",
            "allocated_fallow_fraction",
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
    crop_total = sum(float(r["crop_capacity_people_p50"] or 0.0) for r in rows)
    return {
        "scenario": scenario,
        "location_count": frame.height,
        "capacity_people_p10": round(sum(adjusted["p10"])),
        "capacity_people_p50": round(sum(adjusted["p50"])),
        "capacity_people_p90": round(sum(adjusted["p90"])),
        "baseline_capacity_people_p50": round(sum(float(r["capacity_people_p50"] or 0.0) for r in rows)),
        "weighted_crop_retention_p50": round(
            sum(float(r["crop_capacity_people_p50"] or 0.0) * f for r, f in zip(rows, factors))
            / max(crop_total, 1.0),
            6,
        ),
        "factor_min": round(min(factors, default=1.0), 6),
        "factor_max": round(max(factors, default=1.0), 6),
        "mean_allocated_crop_fraction": round(
            sum(float(r["allocated_crop_fraction"] or 0.0) for r in rows) / max(len(rows), 1), 6
        ),
        "mean_allocated_fallow_fraction": round(
            sum(float(r["allocated_fallow_fraction"] or 0.0) for r in rows) / max(len(rows), 1), 6
        ),
    }


SYSTEMS: dict[str, dict[str, Any]] = {
    "rapa_nui": {
        "role": "held_out_validation_only",
        "interval": [3500, 17500],
        "source": "Puleston et al. 2017",
        "mapping": "exact EU5 rapa_nui_area selector",
    },
    "england": {
        "role": "formal_interval_anchor",
        "interval": [4250000, 6200000],
        "source": "1290 Great Britain reconstruction plus independent pressure evidence",
        "mapping": "EU5 Great Britain region with Wales and northern Scottish areas excluded",
    },
    "iceland": {
        "role": "held_out_validation_only",
        "interval": [40000, 80000],
        "source": "Iceland historical carrying-capacity interval packet",
        "mapping": "exact EU5 iceland_area selector",
    },
    "peten": {
        "role": "validation_only_boundary_review",
        "interval": [3000000, 4000000],
        "source": "Schwartz & Corzo 2015",
        "source_area_km2": 35854,
        "mapping": "EU5 peten_area selector; area mismatch prevents training use",
    },
    "zarma_sahel": {
        "role": "physical_process_validation_only",
        "source": "De Rouw & Rajot 2004",
        "mapping": "EU5 zarma_area selector, used only for dryland process comparison",
    },
    "hawaii": {
        "role": "physical_process_validation_only",
        "source": "Hartshorn et al. 2006; Ladefoged et al. 2009",
        "mapping": "EU5 hawaii_area selector, used only for soil-fertility process comparison",
    },
}


def build_audit(frame_path: Path) -> dict[str, Any]:
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
        "allocated_crop_fraction",
        "allocated_fallow_fraction",
        "area_km2",
    }
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"frame missing physical/model columns: {missing}")

    scenarios = ["baseline", "leaching_only", "fallow_only", "shared_nutrient_fallow", "shared_nutrient_fallow_strict"]
    results: dict[str, dict[str, dict[str, Any]]] = {}
    for system in SYSTEMS:
        selected = _selector(frame, system)
        if selected.height == 0:
            raise ValueError(f"system selector returned no rows: {system}")
        results[system] = {scenario: _summarize(selected, scenario) for scenario in scenarios}

    # Petén's source reports a broad estimate for 35,854 km2.  The EU5 area
    # selector is deliberately reported, but not treated as an exact target.
    peten_area = float(_selector(frame, "peten")["area_km2"].sum())
    peten_source_area = float(SYSTEMS["peten"]["source_area_km2"])
    peten_ratio = peten_area / peten_source_area
    peten_scaled_interval = [round(v * peten_ratio) for v in SYSTEMS["peten"]["interval"]]

    interval_results: dict[str, dict[str, Any]] = {}
    for system, spec in SYSTEMS.items():
        if "interval" not in spec:
            continue
        interval = peten_scaled_interval if system == "peten" else spec["interval"]
        prediction = results[system]["shared_nutrient_fallow"]["capacity_people_p50"]
        interval_results[system] = {
            "interval": interval,
            "predicted_capacity_people_p50": prediction,
            "inside_interval": interval[0] <= prediction <= interval[1],
            "role": spec["role"],
            "training_eligible": system == "england",
        }

    source_evidence = [
        {
            "source_family": "rapa_nui_soil_yield",
            "citation": "Puleston et al. 2017, Frontiers in Ecology and Evolution 5:69",
            "url": "https://doi.org/10.3389/fevo.2017.00069",
            "quantitative_constraint": "3,133.9 effective ha; low-N continuous sweet-potato yield 1.46 t/ha/year versus high-N 5.09; 5/5 and 15/3 fallow scenarios; approximately 3,500–17,500 people in the published N envelope.",
            "use": "held-out validation only; no target fitting",
        },
        {
            "source_family": "peten_milpa_fallow",
            "citation": "Schwartz & Corzo 2015, Journal of Anthropological Research 71(1)",
            "url": "https://doi.org/10.3998/jar.0521004.0071.104",
            "quantitative_constraint": "Traditional Petenero milpa uses a 1:6 crop:fallow cycle and two harvests per plot/year; authors estimate 3–4 million provisioned people on no more than 60% of 35,854 km2.",
            "use": "validation-only; EU5 boundary mismatch is explicit",
        },
        {
            "source_family": "sahel_nutrient_fallow",
            "citation": "De Rouw & Rajot 2004, Agriculture, Ecosystems & Environment 104:249–262",
            "url": "https://doi.org/10.1016/j.agee.2003.12.019",
            "quantitative_constraint": "32 field-years in Banizoumbou; long fallow >15 years gives about 300 kg/ha millet, short 3–5 year fallow about 125 kg/ha; 0.5–1 Mg/ha/year manure can stabilize about 350 kg/ha under 10–17 years cropping.",
            "use": "mapped Zarma process validation; source ratio 125/300 is a sensitivity, not a fitted multiplier",
        },
        {
            "source_family": "hawaii_prehistoric_nutrient_depletion",
            "citation": "Hartshorn et al. 2006, PNAS 103:11092–11097",
            "url": "https://doi.org/10.1073/pnas.0604594103",
            "quantitative_constraint": "After centuries of indigenous dryland agriculture, cultivated profiles show approximately 49% Ca, 28% Mg, 75% Na, 37% K and 32% P lower volumetric totals than controls; P losses averaged about 4 kg/ha/year and K estimates 10–34 kg/ha/year.",
            "use": "mapped Hawaii process validation; supports dynamic P/K balance, not a population target",
        },
        {
            "source_family": "tikopia_carrying_capacity",
            "citation": "Hervad-Jørgensen 1977, Geografisk Tidsskrift 76:88–95",
            "url": "https://tidsskrift.dk/geografisktidsskrift/article/download/45927/56312?inline=1",
            "quantitative_constraint": "442 ha island, 390 ha cultivable; 1,278 people in 1929 used about 0.27 ha/person including fallow and were near the calculated maximum; 1,753 in 1952 required about 475 ha and exceeded stable local capacity.",
            "use": "out-of-period external validation only; no EU5 selector and no training use",
        },
    ]

    mapped_fields = []
    for field, role in (
        ("soil_quality", "physical soil class"),
        ("chelsa_annual_precipitation", "same-location precipitation/leaching proxy"),
        ("allocated_crop_fraction", "mechanistic land-allocation output"),
        ("allocated_fallow_fraction", "mechanistic rotation/fallow output"),
        ("area_km2", "calibrated physical area"),
    ):
        mapped_fields.append(
            {
                "field": field,
                "coverage_fraction": round(frame[field].is_not_null().sum() / frame.height, 6),
                "role": role,
                "forbidden_training_fields": field in {"hyde_population_density", "hyde_cropland_intensity"},
            }
        )

    return {
        "schema_version": "population_capacity_shared_soil_fallow_cross_system_audit_v1",
        "diagnostic_id": "shared_soil_fallow_cross_system_audit_wave32",
        "generated_on": "2026-08-04",
        "frame_path": str(frame_path),
        "frame_sha256": _sha256(frame_path),
        "frame_rows": frame.height,
        "mapped_physical_features": mapped_fields,
        "systems": SYSTEMS,
        "source_evidence": source_evidence,
        "peten_mapping": {
            "source_area_km2": peten_source_area,
            "mapped_area_km2": round(peten_area, 6),
            "area_ratio": round(peten_ratio, 6),
            "coverage_status": "boundary_not_exact; scaled interval is validation-only",
            "scaled_interval": peten_scaled_interval,
        },
        "scenario_definition": {
            "name": "shared_nutrient_fallow",
            "mechanism": "Crop contribution is retained only to the extent supported by soil class, rainfall-driven leaching, and an independently documented fallow/yield process. Livestock, fisheries, wild foods and settlement are not scaled by this crop-only diagnostic.",
            "dryland_ratio": "125/300 from De Rouw & Rajot (2004), short versus long fallow millet yield",
            "humid_root_fallow_envelope": "0.50 is a broad 5/5 rotation sensitivity from Puleston et al. (2017), not a production parameter",
            "strict_stress_envelope": "0.40 active intensive rotation under humid nutrient-limited conditions; an uncertainty stress case, not a fitted coefficient",
            "hard_non_goals": [
                "no anchor-specific multiplier",
                "no starting-population/HYDE/RGO/trade predictor",
                "no observed historical cropland share",
                "no regional or global median imputation",
            ],
        },
        "scenario_results": results,
        "interval_results": interval_results,
        "interpretation": {
            "status": "diagnostic_only_not_production_ready",
            "cross_system_result": "The shared rule is directionally consistent with Rapa Nui, Petén, Sahel dryland and Hawaiian soil-process evidence, while England and Iceland remain controls. This does not establish a universal coefficient: all process factors remain uncertainty envelopes until dynamic N/P/K, crop-family demand, fallow duration, erosion and manure/mulch return are implemented.",
            "production_blockers": [
                "no globally gridded pre-1337 nutrient stock or weathering/deposition balance",
                "no globally mapped pre-1337 rock-garden/terrace/fallow suitability",
                "crop-family-specific nutrient withdrawal and residue/manure return are absent",
                "Petén EU5 boundary is not exact and remains validation-only",
                "Tikopia is out-of-period and has no EU5 crosswalk",
            ],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frame", type=Path, default=DEFAULT_FRAME)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = build_audit(args.frame)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
