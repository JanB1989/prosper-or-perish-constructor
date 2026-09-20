"""Reproduce candidate maps, distributions and snapshot-integrity checks."""
from pathlib import Path
import json
import hashlib
import numpy as np
import polars as pl
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm, TwoSlopeNorm

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "artifacts/data/population_simulation/repair_round_20"


def run():
    start = pl.read_parquet(OUTPUT / "starting_ledger.parquet")
    snapshots = pl.read_parquet(OUTPUT / "checkpoints.parquet")
    history = pl.read_parquet(OUTPUT / "annual_history.parquet")
    populations = [c for c in snapshots.columns if c.startswith("population_")]
    total = snapshots.select(pl.sum_horizontal(populations)).to_series().to_numpy()
    if not np.allclose(total, snapshots["total_population"].to_numpy(), rtol=1e-10, atol=1e-8):
        raise ValueError("snapshot population components disagree with totals; regenerate histories")
    if snapshots.select("scenario", "year", "location_tag").unique().height != snapshots.height:
        raise ValueError("duplicate checkpoint location")
    snapshots = snapshots.with_columns(
        (pl.col("total_population") * 1000 / pl.col("area_km2")).alias("population_density_people_km2"),
        (pl.col("local_population_capacity") * 1000 / pl.col("area_km2")).alias("capacity_density_people_km2"),
        pl.when(pl.col("local_population_capacity") > 0)
        .then(pl.col("total_population") / pl.col("local_population_capacity")).alias("capacity_fill"),
    )
    metrics = [c for c in ("total_population", "local_population_capacity", "food", "food_production",
        "last_food_consumption", "food_balance", "subsistence_surplus", "employed_peasants",
        "unemployed_peasants", "starvation_months", "development", "prosperity",
        "capacity_pressure_strength", "population_density_people_km2", "capacity_density_people_km2",
        "capacity_fill") if c in snapshots.columns]
    additive = set(metrics[:10])
    # Location-level checkpoints are already retained. Add distributions within
    # every province, region, macro-region and world, without hiding small failures.
    parts = []
    for scope in ("province", "region", "macro_region", "world"):
        frame = snapshots.with_columns(pl.lit("world").alias("world")) if scope == "world" else snapshots
        for metric in metrics:
            valid = pl.col(metric).filter(pl.col(metric).is_finite())
            part = frame.group_by("scenario", "year", scope).agg(
                pl.len().alias("location_count"), valid.count().alias("finite_count"),
                valid.min().alias("min"), valid.quantile(.1, interpolation="linear").alias("p10"),
                valid.median().alias("median"), valid.quantile(.9, interpolation="linear").alias("p90"),
                valid.max().alias("max"), valid.mean().alias("mean"),
                (valid.sum() if metric in additive else pl.lit(None, dtype=pl.Float64)).alias("total"),
            ).rename({scope: "scope_key"}).with_columns(pl.lit(scope).alias("scope"), pl.lit(metric).alias("metric"))
            parts.append(part)
    statistics = pl.concat(parts, how="diagonal_relaxed")
    statistics.write_parquet(OUTPUT / "checkpoint_statistics.parquet")
    statistics.filter(pl.col("scope") == "world").write_csv(OUTPUT / "world_statistics.csv")
    baseline = snapshots.filter((pl.col("scenario") == "decay_compensation_0") & (pl.col("year") == 500))
    map_data = start.select("location_tag", "calibrated_lon", "calibrated_lat", "area_km2",
        pl.col("total_population").alias("start_population"),
        pl.col("local_population_capacity").alias("start_capacity")).join(
            baseline.select("location_tag", pl.col("total_population").alias("final_population")),
            on="location_tag", validate="1:1")
    x, y = map_data["calibrated_lon"].to_numpy(), map_data["calibrated_lat"].to_numpy()
    density = map_data["start_capacity"].to_numpy() * 1000 / map_data["area_km2"].to_numpy()
    initial = map_data["start_population"].to_numpy()
    retention = np.divide(map_data["final_population"].to_numpy(), initial,
                          out=np.full(len(initial), np.nan), where=initial > 0)
    fig, axes = plt.subplots(2, 1, figsize=(13, 8), constrained_layout=True)
    for ax in axes:
        ax.set(xlim=(-180, 180), ylim=(-60, 80), xlabel="Longitude", ylabel="Latitude")
        ax.set_facecolor("#edf0f2")
        ax.grid(alpha=.15)
    a = axes[0].scatter(x, y, c=np.maximum(density, .01), s=3, cmap="viridis", norm=LogNorm(.01, 1000), rasterized=True)
    fig.colorbar(a, ax=axes[0], label="Starting capacity density (people/km²)")
    axes[0].set_title("Candidate starting capacity density — location centroids, not an accepted map")
    b = axes[1].scatter(x, y, c=retention, s=3, cmap="RdBu", norm=TwoSlopeNorm(vmin=0, vcenter=1, vmax=2), rasterized=True)
    fig.colorbar(b, ax=axes[1], label="Population at year 500 / start")
    axes[1].set_title("Frozen infrastructure, coupled development: baseline retention")
    fig.suptitle("Diagnostic only · colour bounds: capacity 0.01–1,000 people/km²; retention 0–2", fontsize=10)
    fig.savefig(OUTPUT / "candidate_geography.png", dpi=160)
    plt.close(fig)
    rows = history.filter((pl.col("year") == 500) & (pl.col("scope") == "world")).sort("scenario")
    lines = ["# Round 20 candidate comparison", "", "**Not accepted.** No trade, migration, promotion or autonomous construction.", "",
        "![Candidate geography](candidate_geography.png)", "",
        "| D50 decay offset | World population, million | World capacity, million | Mean development |",
        "|---|---:|---:|---:|"]
    for r in rows.to_dicts():
        lines.append(f"| {r['scenario']} | {r['total_population']/1000:.3f} | {r['local_population_capacity']/1000:.3f} | {r['mean_development']:.3f} |")
    lines += ["", "The conservative offset has little demographic effect. Regional failures remain; aggregate capacity is not acceptance.", "",
        "`checkpoint_statistics.parquet` contains within-scope minima, maxima, quantiles, means and valid counts for provinces, regions, macro-regions and world. Location checkpoints remain available separately. Non-additive metrics have no reported sum. Density and fill distributions are location-weighted, not averages weighted by population or hectares.", "",
        "`starting_ledger.parquet` and `checkpoints.parquet` supply component inputs and outcomes. Saved population components were verified against totals at every checkpoint. A historical field/infrastructure assignment and native engine comparison are still required.", ""]
    (OUTPUT / "report.md").write_text("\n".join(lines))
    hashes = {}
    for name in ("manifest.json", "starting_ledger.parquet", "checkpoints.parquet", "annual_history.parquet"):
        with (OUTPUT / name).open("rb") as stream:
            hashes[name] = hashlib.file_digest(stream, "sha256").hexdigest()
    (OUTPUT / "diagnostic_validation.json").write_text(json.dumps({"accepted": False, "input_sha256": hashes,
        "snapshot_components_match_totals": True, "unique_checkpoint_keys": True,
        "checkpoint_rows": snapshots.height, "statistics_rows": statistics.height,
        "geography": "canonical calibrated centroids; marker size does not encode land area",
        "snapshot_manifest": "manifest.json"}, indent=2) + "\n")
    print(OUTPUT / "report.md")


if __name__ == "__main__":
    run()
