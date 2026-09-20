"""Summarize round 19 without hiding local failures in world totals."""
from pathlib import Path
import json
import polars as pl
ROOT = Path(__file__).resolve().parents[2]
import argparse
parser = argparse.ArgumentParser()
parser.add_argument('--strong-development', action='store_true')
args = parser.parse_args()
output = ROOT / 'artifacts/data/population_simulation' / ('repair_round_19_strong' if args.strong_development else 'repair_round_19')
frame = pl.read_parquet(output/'checkpoints.parquet')
start = frame.filter(pl.col('year') == 0).select('scenario', 'location_tag',
    pl.col('total_population').alias('initial_population'), pl.col('development').alias('initial_development'))
comparison = frame.filter(pl.col('year') == 500).join(start, on=['scenario', 'location_tag'], validate='1:1').with_columns(
    (pl.col('total_population') / pl.col('initial_population')).alias('population_retention'),
    (pl.col('development') - pl.col('initial_development')).alias('development_change'))
comparison.write_parquet(output/'location_outcomes.parquet')
summary = comparison.group_by('scenario').agg(
    ((pl.col('population_retention') < .8) & (pl.col('initial_population') > 0)).sum().alias('locations_losing_over_20pct'),
    (pl.col('development_change') < -1).sum().alias('locations_losing_over_1_development'),
    (pl.col('development') >= 99.99).sum().alias('locations_at_development_ceiling'),
    (pl.col('starvation_months') > 120).sum().alias('locations_over_10_years_starvation'),
    pl.col('development').min().alias('development_min'), pl.col('development').max().alias('development_max'))
summary.write_csv(output/'failure_counts.csv')
for c in ['total_population', 'local_population_capacity', 'development', 'food']:
    assert frame[c].is_finite().all(), c
    assert frame[c].min() >= 0, c
notes = ['','## Local failure counts','', 'Starvation counts cover cumulative location-months, not necessarily consecutive famine. These are diagnostics, not historical acceptance thresholds.', '', summary.sort('scenario').write_csv()]
report = output/'report.md'
text = report.read_text().split('\n## Local failure counts')[0]
report.write_text(text.rstrip() + '\n' + '\n'.join(notes))
print(summary.sort('scenario'))

initial = frame.filter((pl.col('year') == 0) & (pl.col('scenario') == 'baseline'))
initial.group_by('macro_region').agg(pl.col('development').mean().alias('mean_development'),
    pl.col('development').quantile(.9).alias('development_p90')).write_csv(output/'starting_development_by_macro_region.csv')
initial.filter((pl.col('total_population') >= 10.) &
    (pl.col('total_population') < .1 * pl.col('local_population_capacity'))).write_csv(output/'no_band_starting_locations.csv')
