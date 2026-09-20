"""Summarize the corrected Taihu stock/progression experiments.

uv run python research/population_capacity/summarize_taihu_experiments.py
"""
from pathlib import Path
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import polars as pl

from prosper_or_perish_constructor.simulation.cache import fingerprint


ROOT = Path(__file__).resolve().parents[2]
DIRECTORY = ROOT / "artifacts/data/population_simulation/repair_round_18"
LABELS = {
    "baseline__dry_0.86": ("Current model", "#64748b"),
    "song_all_fields__dry_0.86": ("Higher yield on current fields", "#0284c7"),
    "half_land_plus_song_all_fields__dry_0.86": ("More fields + historical yield", "#d97706"),
    "half_land_song_then_ming__dry_0.86": ("Same start + later intensification", "#7c3aed"),
}


def run():
    histories, stock_results, manifests, paths = [], [], [], []
    for months in (0, 3, 12, 24):
        folder = DIRECTORY / f"taihu_stocks_{months}"
        path = folder / "monthly_locations.parquet"
        manifest_path = folder / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifests.append({"initial_food_months": months, "run_fingerprint": manifest["fingerprint"]})
        paths.extend([path, manifest_path])
        locations = pl.read_parquet(path).sort("scenario", "location_tag", "month").with_columns(
            pl.col("starvation_months").diff().over("scenario", "location_tag").fill_null(0.).alias("new_starvation"))
        totals = locations.group_by("scenario", "month").agg(
            pl.col("total_population", "local_population_capacity").sum(),
            pl.col("development").mean().alias("mean_development"))
        histories.append(totals.with_columns(pl.lit(months).alias("initial_food_months")))
        for scenario, (label, _) in LABELS.items():
            series = totals.filter(pl.col("scenario") == scenario).sort("month")
            initial, final = series.row(0, named=True), series.row(-1, named=True)
            episodes = locations.filter((pl.col("scenario") == scenario) & (pl.col("new_starvation") > 0))
            stock_results.append({"scenario": scenario, "label": label, "initial_food_months": months,
                "starting_population_people": initial["total_population"] * 1000,
                "minimum_population_people": series["total_population"].min() * 1000,
                "final_population_people": final["total_population"] * 1000,
                "starting_capacity_people": initial["local_population_capacity"] * 1000,
                "final_capacity_people": final["local_population_capacity"] * 1000,
                "starting_mean_development": initial["mean_development"],
                "minimum_mean_development": series["mean_development"].min(),
                "final_mean_development": final["mean_development"],
                "starved_province_months": episodes.select("province", "month").n_unique(),
                "starved_location_months": episodes.height})
    history = pl.concat(histories).sort("initial_food_months", "scenario", "month")
    history.write_parquet(DIRECTORY / "aggregate_monthly_history.parquet")
    results = pl.DataFrame(stock_results)
    results.write_csv(DIRECTORY / "stock_and_progression_comparison.csv")

    figure, axes = plt.subplots(1, 2, figsize=(12, 5), layout="constrained")
    for scenario, (label, colour) in LABELS.items():
        traces = history.filter(pl.col("scenario") == scenario).group_by("month").agg(
            *(pl.col(metric).min().alias(metric + "_min") for metric in ("total_population", "local_population_capacity")),
            *(pl.col(metric).max().alias(metric + "_max") for metric in ("total_population", "local_population_capacity")),
        ).sort("month")
        central = history.filter((pl.col("scenario") == scenario) & (pl.col("initial_food_months") == 12)).sort("month")
        for axis, metric, title in zip(axes, ("total_population", "local_population_capacity"), ("Population", "Capacity"), strict=True):
            axis.plot(central["month"].to_numpy() / 12, central[metric].to_numpy() / 1000, label=label, color=colour, linewidth=2)
            axis.fill_between(traces["month"].to_numpy() / 12,
                traces[metric + "_min"].to_numpy() / 1000, traces[metric + "_max"].to_numpy() / 1000,
                color=colour, alpha=.12)
            axis.set(title=title, xlabel="Years from starting conditions", ylabel="Million people", xlim=(0, 500), ylim=(0, 10.5))
            axis.grid(alpha=.15)
            axis.spines[["top", "right"]].set_visible(False)
    axes[0].axhline(results["starting_population_people"][0] / 1e6, color="#94a3b8", linestyle="--", linewidth=.8)
    axes[1].legend(loc="lower right", frameon=False, fontsize=9)
    figure.suptitle("Taihu mechanism experiments\nDated field yields; assumed cultivated areas; trial food coefficients", fontsize=14)
    figure.savefig(DIRECTORY / "taihu_mechanisms.png", dpi=160)
    plt.close(figure)

    lines = ["# Taihu mechanism and progression experiments", "",
        "**Status: diagnostic; geographical acceptance incomplete.**", "",
        "Twelve locations in three complete food-sharing provinces start at 6.204 million people. The source supplies field yields; the adoption hectares remain assumptions. The same food coefficients and current employment/building contributions are used throughout.", "",
        "![Taihu population and capacity trajectories](taihu_mechanisms.png)", "",
        "Lines use 12 months of starting food. Shading spans runs with 0, 3, 12 and 24 months.", "",
        "| Case | Population after 500 years, million | Capacity after 500 years, million | Starved province-months across starting-stock cases |",
        "|---|---:|---:|---|"]
    for scenario, (label, _) in LABELS.items():
        cases = results.filter(pl.col("scenario") == scenario).sort("initial_food_months")
        middle = cases.filter(pl.col("initial_food_months") == 12).row(0, named=True)
        lines.append(f"| {label} | {middle['final_population_people']/1e6:.3f} | {middle['final_capacity_people']/1e6:.3f} | "
                     + ", ".join(str(v) for v in cases["starved_province_months"]) + " |")
    lines.extend(["", "The starved province-month column lists the 0-, 3-, 12- and 24-month-stock runs in that order.", "",
        "The land-plus-yield case uses 6,307.79 km² of intensive fields versus 3,373.15 km² in the current crop block. It realizes half the remaining known suitable land, including the loss of displaced wild/grazing support. That fraction is an intervention probe, not a researched adoption estimate.", "",
        "Managed yield targets are divided by the existing relative capacity factor before calculating incremental flat improvements. Already counted crop support and agricultural allowances are subtracted. Crop losses and the area transform remain shared with the pipeline.", "",
        "The progression case switches to the dated Ming yield benchmark at year 200 (1537), without adding more hectares. The date and attainment are explicit scenario assumptions; native costs and legal building levels are still unimplemented.", "",
        "In the 24-month-stock combined case, Suzhou experiences one starvation month at month 255 after early growth. The other three stock cases experience none. The zero-stock combined case briefly falls about 0.68% below starting population before recovering. These are controlled mechanisms, not proof of a repaired world map.", "",
        "The source study's moisture content and 1337 field adoption remain uncertain. This round uses dry matter 0.86; the wider moisture sensitivity in rounds 14–15 predates the development reconciliation. Independent spatial evidence, nutrient mixing, native construction and engine verification remain outstanding.", ""])
    (DIRECTORY / "report.md").write_text("\n".join(lines))
    (DIRECTORY / "comparison_manifest.json").write_text(json.dumps({"accepted": False, "runs": manifests,
        "fingerprint": fingerprint([Path(__file__), *paths]),
        "people_per_game_unit": 1000, "initial_food_months": [0, 3, 12, 24]}, indent=2) + "\n")
    return str(DIRECTORY / "report.md")


if __name__ == "__main__":
    print(run())
