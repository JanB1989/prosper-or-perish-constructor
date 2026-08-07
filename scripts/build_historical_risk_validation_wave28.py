"""Summarize in-period harvest/price/famine evidence as one-sided risk tests.

This artifact deliberately keeps historical observations separate from the
capacity target.  Medieval yields and prices can test whether a simulated
low-tail is implausibly narrow; they cannot label every EU5 location or set
the global population-capacity scale.
"""

from __future__ import annotations

from pathlib import Path
import hashlib
import json

import polars as pl


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/data/population_capacity/physical_validation/interannual_sources/wave28"
BAHS = ROOT / "artifacts/data/population_capacity/historical_yields/bahs_medieval_yield_observations.parquet"
BAHS_VALIDATION = ROOT / "artifacts/data/population_capacity/historical_yields/bahs_yield_validation_1270_1349.parquet"
CLARK_PDF = OUT / "clark_market99_medieval_grain_market.pdf"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def summarize_bahs() -> tuple[pl.DataFrame, pl.DataFrame]:
    frame = pl.read_parquet(BAHS).filter(
        (pl.col("harvest_year") >= 1100)
        & (pl.col("harvest_year") <= 1500)
        & pl.col("gross_yield_per_seed_ratio").is_not_null()
        & (pl.col("gross_yield_per_seed_ratio") > 0)
    ).with_columns(
        pl.col("model_crop").fill_null("unmapped_historical_crop").alias("model_crop")
    )
    summary = (
        frame.group_by("model_crop")
        .agg(
            pl.len().alias("observation_count"),
            pl.col("harvest_year").n_unique().alias("year_count"),
            pl.col("harvest_year").min().alias("year_start"),
            pl.col("harvest_year").max().alias("year_end"),
            pl.col("gross_yield_per_seed_ratio").mean().alias("mean_yield_per_seed"),
            pl.col("gross_yield_per_seed_ratio").std().alias("std_yield_per_seed"),
            pl.col("gross_yield_per_seed_ratio").quantile(0.10).alias("p10_yield_per_seed"),
            pl.col("gross_yield_per_seed_ratio").quantile(0.50).alias("p50_yield_per_seed"),
            pl.col("gross_yield_per_seed_ratio").quantile(0.90).alias("p90_yield_per_seed"),
            pl.col("eu5_location_tag").drop_nulls().n_unique().alias("mapped_location_count"),
            pl.col("location_mapping_method")
            .filter(pl.col("eu5_location_tag").is_not_null())
            .first()
            .alias("mapped_location_method_example"),
        )
        .with_columns(
            (pl.col("std_yield_per_seed") / pl.col("mean_yield_per_seed")).alias(
                "coefficient_of_variation"
            ),
            (pl.col("p10_yield_per_seed") / pl.col("p50_yield_per_seed")).alias(
                "lower_tail_ratio_p10_p50"
            ),
            pl.when(pl.col("model_crop") == "unmapped_historical_crop")
            .then(pl.lit("unresolved_crop_family"))
            .otherwise(pl.lit("one_sided_historical_harvest_risk_validation"))
            .alias("label_state"),
        )
        .sort("model_crop")
    )
    mapped = frame.filter(pl.col("eu5_location_tag").is_not_null())
    location = (
        mapped.group_by(["eu5_location_tag", "model_crop"])
        .agg(
            pl.len().alias("observation_count"),
            pl.col("harvest_year").n_unique().alias("year_count"),
            pl.col("harvest_year").min().alias("year_start"),
            pl.col("harvest_year").max().alias("year_end"),
            pl.col("gross_yield_per_seed_ratio").quantile(0.10).alias("p10_yield_per_seed"),
            pl.col("gross_yield_per_seed_ratio").quantile(0.50).alias("p50_yield_per_seed"),
            pl.col("gross_yield_per_seed_ratio").quantile(0.90).alias("p90_yield_per_seed"),
        )
        .with_columns(
            (pl.col("p10_yield_per_seed") / pl.col("p50_yield_per_seed")).alias(
                "lower_tail_ratio_p10_p50"
            ),
            pl.when(pl.col("model_crop") == "unmapped_historical_crop")
            .then(pl.lit("unresolved_crop_family"))
            .otherwise(pl.lit("one_sided_historical_harvest_risk_validation"))
            .alias("label_state"),
        )
        .sort(["eu5_location_tag", "model_crop"])
    )
    return summary, location


def main() -> None:
    summary, location = summarize_bahs()
    summary_path = OUT / "bahs_historical_risk_summary_wave28.csv"
    location_path = OUT / "bahs_historical_location_risk_wave28.csv"
    summary.write_csv(summary_path)
    location.write_csv(location_path)
    validation = pl.read_parquet(BAHS_VALIDATION)
    manifest = {
        "schema_version": "population_capacity_historical_risk_validation_wave28",
        "target_window": [1100, 1500],
        "target_year": 1337,
        "purpose": "One-sided validation of interannual low-tail and harvest-risk width, never a population-capacity target.",
        "sources": [
            {
                "source_id": "bahs_medieval_crop_yields_1211_1491",
                "title": "Three centuries of English crop yields, 1211-1491 / Medieval Crop Yields Database",
                "source_url": "https://www.cropyields.ac.uk/",
                "documentation_url": "https://www.bahs.org.uk/crop-yields-database/chronologies/",
                "local_artifact": str(BAHS.relative_to(ROOT)),
                "local_artifact_sha256": sha256(BAHS),
                "validation_artifact": str(BAHS_VALIDATION.relative_to(ROOT)),
                "validation_artifact_sha256": sha256(BAHS_VALIDATION),
                "semantics": {
                    "period": [1211, 1491],
                    "target_overlap": [1211, 1491],
                    "observation": "manorial gross yield per seed ratio; source-specific units, not uniform kg/ha",
                    "mapped_eu5_locations_in_raw_rows": int(location.select("eu5_location_tag").n_unique()),
                    "training_population_target": False,
                    "one_sided_use": "An observed p10/p50 lower-tail ratio can reject a mechanistic risk interval that is narrower than the historical series, after boundary and crop-system compatibility review.",
                },
            },
            {
                "source_id": "clark_medieval_english_grain_market_1208_1453",
                "title": "Markets and Economic Growth: The Grain Market of Medieval England",
                "author_url": "https://faculty.econ.ucdavis.edu/faculty/gclark/data.html",
                "paper_url": "https://www.econ.ucdavis.edu/faculty/gclark/210a/readings/market99.pdf",
                "local_artifact": str(CLARK_PDF.relative_to(ROOT)),
                "local_artifact_sha256": sha256(CLARK_PDF),
                "semantics": {
                    "period": [1208, 1453],
                    "target_overlap": [1208, 1453],
                    "coverage": "227 English manors; annual wheat-yield and price indices",
                    "reported_risk_statistics": {
                        "yield_autocorrelation_1208_1349": 0.19,
                        "price_autocorrelation_1208_1349": 0.51,
                        "yield_autocorrelation_1350_1499": 0.12,
                        "price_autocorrelation_1350_1499": 0.38,
                        "low_previous_price_implied_inventory_fraction": 0.40,
                        "low_price_cases_n": 9,
                    },
                    "interpretation": "Price persistence exceeds yield persistence, consistent with storage and market smoothing; risk validation must not equate price spikes with local yield loss.",
                    "training_population_target": False,
                    "one_sided_use": "Use published yield autocorrelation and low-price/storage cases to test whether the model's temporal persistence and reserve assumptions are physically plausible; no absolute capacity label is created.",
                },
            },
            {
                "source_id": "hao_eastern_china_harvest_grades_801_1910",
                "title": "Patterns in extreme droughts/floods and harvest grades in eastern China",
                "paper_url": "https://doi.org/10.5194/cp-16-101-2020",
                "raw_series_status": "not_open_machine_readable; authors state data available on request",
                "semantics": {
                    "period": [801, 1910],
                    "target_overlap": [1100, 1500],
                    "observation": "ordinal harvest grades relative to local normal, broad regional stations",
                    "one_sided_use": "After raw annual series acquisition, severe-grade frequencies can reject a risk model that is too narrow; ordinal grades cannot calibrate kg/ha or capacity.",
                    "training_population_target": False,
                },
            },
            {
                "source_id": "european_famine_database_screen",
                "title": "European famine database, 1000-1850 screening source",
                "url": "https://www.openicpsr.org/openicpsr/project/120551/version/V1/view",
                "raw_series_status": "screening/validation only; event list does not establish local yield magnitude or saturation",
                "semantics": {
                    "target_overlap": [1100, 1500],
                    "one_sided_use": "A mapped famine event may be used as a one-sided stress-test: the model must permit a low-output shock in the affected food system. Event presence cannot set a capacity target or loss magnitude.",
                    "training_population_target": False,
                },
            },
        ],
        "outputs": {
            "crop_summary": str(summary_path.relative_to(ROOT)),
            "crop_summary_sha256": sha256(summary_path),
            "location_summary": str(location_path.relative_to(ROOT)),
            "location_summary_sha256": sha256(location_path),
            "summary_rows": summary.height,
            "location_rows": location.height,
            "bahs_validation_rows": validation.height,
        },
        "coverage": {
            "bahs_observation_rows_1100_1500": int(summary["observation_count"].sum()),
            "bahs_crop_summary_rows": summary.height,
            "bahs_mapped_location_crop_rows": location.height,
            "bahs_mapped_location_count": int(location.select("eu5_location_tag").n_unique()),
            "bahs_unresolved_crop_family_rows": int(
                summary.filter(pl.col("model_crop") == "unmapped_historical_crop")["observation_count"].sum()
            ),
            "bahs_p10_p50_available": bool(summary.height > 0),
        },
        "acceptance": {
            "one_sided_historical_risk_validation_available": True,
            "absolute_1100_1500_yield_target_available": False,
            "global_historical_risk_closed": False,
            "famine_price_evidence_can_set_capacity": False,
            "mechanistic_p10_p90_gate_unblocked": False,
            "training_target_allowed": False,
            "validation_allowed": True,
            "blocking_gaps": [
                "BAHS is geographically concentrated in England and its yield-per-seed unit is not a uniform edible-calorie yield.",
                "Clark's price series is highly valuable for reserve/storage stress tests but prices reflect market integration and cannot be treated as local harvest labels.",
                "Hao's eastern-China annual grade series and the European famine database are not open, exact local continuous yield panels; they remain one-sided/validation evidence.",
                "No global annual absolute harvest-yield panel for 1100-1500 with EU5-mappable boundaries was identified.",
            ],
        },
    }
    manifest_path = OUT / "historical_risk_validation_manifest_wave28.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
