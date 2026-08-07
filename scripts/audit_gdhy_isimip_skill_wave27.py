"""Compare modern GDHY and ISIMIP rice anomalies without creating targets."""

from __future__ import annotations

from pathlib import Path
import hashlib
import json

import numpy as np
import polars as pl


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/data/population_capacity/physical_validation/interannual_sources/wave27"


def _corr(a: np.ndarray, b: np.ndarray) -> tuple[float, float]:
    if len(a) < 3 or np.std(a) == 0 or np.std(b) == 0:
        return float("nan"), float("nan")
    pearson = float(np.corrcoef(a, b)[0, 1])
    rank_a = np.argsort(np.argsort(a))
    rank_b = np.argsort(np.argsort(b))
    spearman = float(np.corrcoef(rank_a, rank_b)[0, 1])
    return pearson, spearman


def main() -> None:
    gdhy = pl.read_csv(OUT / "gdhy_superregion_annual_wave27.csv").filter(pl.col("crop") == "rice_major")
    isimip = pl.read_csv(OUT / "isimip_rice_superregion_annual_wave27.csv")
    rows: list[dict[str, object]] = []
    for mode in ("rainfed", "full_irrigation"):
        model = isimip.filter(pl.col("water_mode") == mode)
        for region in sorted(set(gdhy["super_region"].to_list())):
            observed = gdhy.filter(pl.col("super_region") == region).select(
                ["year", "yield_t_ha_area_weighted_mean", "valid_area_fraction"]
            )
            modeled = model.filter(pl.col("super_region") == region).select(
                ["year", "yield_t_ha_area_weighted_mean", "valid_area_fraction"]
            )
            joined = observed.join(modeled, on="year", suffix="_model").sort("year")
            # Keep the finite-paired rows as a frame.  Polars deliberately
            # does not support NumPy-style boolean Series indexing, and
            # retaining the frame also keeps coverage statistics aligned with
            # the exact rows used for the correlation.
            valid_joined = joined.filter(
                pl.col("yield_t_ha_area_weighted_mean").is_finite()
                & pl.col("yield_t_ha_area_weighted_mean_model").is_finite()
            )
            y = valid_joined["yield_t_ha_area_weighted_mean"].to_numpy()
            m = valid_joined["yield_t_ha_area_weighted_mean_model"].to_numpy()
            if len(y):
                y_anom = y - np.median(y)
                m_anom = m - np.median(m)
                pearson, spearman = _corr(y_anom, m_anom)
                gdhy_cov = float(valid_joined["valid_area_fraction"].min())
                model_cov = float(valid_joined["valid_area_fraction_model"].min())
                standardized_rmse = float(np.sqrt(np.mean((
                    (y_anom / (np.std(y_anom) or 1.0)) - (m_anom / (np.std(m_anom) or 1.0))
                ) ** 2)))
            else:
                pearson = spearman = standardized_rmse = float("nan")
                gdhy_cov = model_cov = 0.0
            rows.append(
                {
                    "source_a": "GDHYv1.2+v1.3",
                    "source_b": "ISIMIP2a_CLM-Crop_WATCH_WFDEI",
                    "crop": "rice",
                    "water_mode": mode,
                    "super_region": region,
                    "year_start": 1981,
                    "year_end": 2012,
                    "overlap_year_count": int(len(y)),
                    "min_gdhy_valid_area_fraction": gdhy_cov,
                    "min_isimip_valid_area_fraction": model_cov,
                    "pearson_anomaly_correlation": pearson,
                    "spearman_anomaly_correlation": spearman,
                    "standardized_anomaly_rmse": standardized_rmse,
                    "interpretation": "modern interannual timing diagnostic only; not a 1337 target or absolute-yield calibration",
                }
            )
    output = OUT / "gdhy_isimip_rice_skill_wave27.csv"
    pl.DataFrame(rows).write_csv(output)
    manifest = {
        "schema_version": "population_capacity_gdhy_isimip_skill_audit_v1",
        "path": str(output.relative_to(ROOT)),
        "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "size_bytes": output.stat().st_size,
        "rows": len(rows),
        "policy": "Correlations are standardized modern anomaly diagnostics. They never calibrate 1337 absolute yield or population capacity and never replace missing historical evidence.",
    }
    (OUT / "gdhy_isimip_skill_manifest_wave27.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
