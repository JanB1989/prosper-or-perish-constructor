"""Compare rebuilt crop scenarios against identical-code baseline and old cache."""
import argparse
import json
from pathlib import Path
import polars as pl
from prosper_or_perish_constructor.simulation.cache import fingerprint
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts/data/population_capacity/repair_round_37"
COLS = ["rainfed_energy_kcal_ha_year", "irrigated_energy_kcal_ha_year", "rainfed_protein_kg_ha_year", "irrigated_protein_kg_ha_year", "rainfed_suitable_fraction", "irrigated_suitable_fraction"]
KEYS = ["location_tag", "model_year_id"]


def compare(before_path, after_path, name, restricted, *, output=OUT):
    output.mkdir(parents=True, exist_ok=True)
    before, after = [pl.read_parquet(p).select(*KEYS, *COLS) for p in (before_path, after_path)]
    frame = before.join(after, on=KEYS, suffix="_after", validate="1:1")
    if frame.height != before.height or frame.height != after.height:
        raise ValueError("Scenario universe changed")
    changed = frame.filter(pl.any_horizontal(*[(pl.col(c) - pl.col(c + "_after")).abs() > 1e-8 for c in COLS]))
    tags = pl.read_csv(output / "crop_history/availability_changes.csv")["location_tag"].unique().to_list()
    outside = changed.filter(~pl.col("location_tag").is_in(tags))
    summary = changed.group_by("location_tag").agg(
        *[pl.col(c).mean().alias(c + "_before") for c in COLS],
        *[pl.col(c + "_after").mean() for c in COLS])
    summary.write_csv(output / f"{name}_location_changes.csv")
    report = dict(name=name, rows=frame.height, changed_rows=changed.height,
        changed_locations=changed["location_tag"].n_unique(), outside_exclusion_changed_rows=outside.height,
        outside_exclusion_changed_locations=outside["location_tag"].n_unique(),
        outside_named_scope_changed_rows=outside.height,
        model_accepted=False, capacity_recomputed=False,
        fingerprint=fingerprint([__file__, before_path, after_path, output / "crop_history/availability_changes.csv"], {}))
    (output / f"{name}.json").write_text(json.dumps(report, indent=2) + "\n")
    if restricted and outside.height:
        raise ValueError("Paired historical correction changed support outside its named scope")
    print(report)


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before',type=Path)
    parser.add_argument('--after',type=Path)
    parser.add_argument('--output',type=Path,default=OUT)
    parser.add_argument('--name',default='paired_crop_history')
    args=parser.parse_args()
    if args.before is not None or args.after is not None:
        if args.before is None or args.after is None:
            parser.error('--before and --after must be provided together')
        compare(args.before,args.after,args.name,True,output=args.output)
    else:
        baseline = OUT / 'baseline_crop_risk_scenarios/crop_system_scenarios.parquet'
        compare(ROOT / 'artifacts/data/population_capacity/pyaez_1337/crop_risk_scenarios/crop_system_scenarios.parquet', baseline, 'cached_annual_replay', False)
        compare(baseline, OUT / 'crop_risk_scenarios/crop_system_scenarios.parquet', 'paired_historical_exclusion', True)
