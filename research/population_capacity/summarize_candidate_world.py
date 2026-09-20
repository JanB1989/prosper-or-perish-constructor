"""Global outcome and collateral tables; no automatic demographic acceptance."""
import argparse
import json
import numpy as np
import polars as pl
from run_historical_direct import ROOT
from prosper_or_perish_constructor.simulation.cache import fingerprint


def run(output, report=None, selected_scenario="equal_rank_quarter_offset"):
    report = report or output / "world_findings.md"
    manifest=json.loads((output/'manifest.json').read_text())
    start=pl.read_parquet(output/'starting_ledger.parquet').select('location_tag','province','region','macro_region','area_km2',
        pl.col('total_population').alias('initial_population'),pl.col('development').alias('initial_development'))
    baseline=pl.read_parquet(output/'native_rank_no_offset_checkpoints.parquet')
    rows=[]; effects=[]; distributions=[]; outliers=[]
    for case in manifest['cases']:
        name=case['name']; frame=pl.read_parquet(output/f'{name}_checkpoints.parquet')
        for year in (100,200):
            current=frame.filter(pl.col('year')==year).join(start.select('location_tag','initial_population','initial_development'),on='location_tag',validate='1:1')
            previous=baseline.filter(pl.col('year')==year).select('location_tag',
                pl.col('unmet_food_months').alias('baseline_unmet_food_months'),
                pl.col('total_population').alias('baseline_population'))
            current=current.join(previous,on='location_tag',validate='1:1').with_columns(
                pl.when(pl.col('initial_population')>0).then(pl.col('total_population')/pl.col('initial_population')).otherwise(None).alias('population_retention'),
                (pl.col('food_growth_cap_months')/(year*12)).alias('fraction_months_at_growth_cap'),
                (pl.col('total_population')/pl.col('local_population_capacity').clip(lower_bound=1e-12)).alias('fill'),
                pl.when(pl.col('initial_population')>0).then((pl.col('total_population')/pl.col('initial_population'))**(1/year)-1).otherwise(None).alias('annualized_population_change'),
                (pl.col('total_population')-pl.col('baseline_population')).alias('population_delta_thousands'),
                (pl.col('unmet_food_months')-pl.col('baseline_unmet_food_months')).alias('additional_unmet_food_months'))
            values=current['annualized_population_change'].drop_nulls().to_numpy()
            assert np.isfinite(values).all()
            assert current.filter(pl.col('initial_population')<=0)['total_population'].sum()==0
            rows.append(dict(candidate=name,year=year,population_people=current['total_population'].sum()*1000,
                capacity_people=current['local_population_capacity'].sum()*1000,
                locations_more_unmet_food=current.filter(pl.col('additional_unmet_food_months')>1e-9).height,
                additional_unmet_location_months=current['additional_unmet_food_months'].sum(),
                locations_population_below_90pct=current.filter(pl.col('population_retention')<.9).height,
                locations_at_food_growth_cap_90pct_of_months=current.filter(pl.col('fraction_months_at_growth_cap')>=.9).height,
                minimum_population_retention=current['population_retention'].min(),
                maximum_population_multiplier=current['population_retention'].max(),
                initially_empty_locations=current.filter(pl.col('initial_population')<=0).height,
                maximum_annualized_population_change=float(values.max())))
            effects.append(current.select('location_tag','province','region','macro_region','population_retention',
                'population_delta_thousands','additional_unmet_food_months','unmet_food_months',
                'fraction_months_at_growth_cap','annualized_population_change','fill',
                'population_maximum_drawdown','development_maximum_drawdown',
                'maximum_consecutive_starvation_months').with_columns(pl.lit(name).alias('candidate'),pl.lit(year).alias('year')))
            for scope in ('province','region','macro_region'):
                for metric in ('population_retention','fill','annualized_population_change','fraction_months_at_growth_cap'):
                    distributions.append(current.group_by(scope).agg(
                        pl.col(metric).min().alias('minimum'),pl.col(metric).quantile(.1).alias('p10'),
                        pl.col(metric).median().alias('median'),pl.col(metric).quantile(.9).alias('p90'),
                        pl.col(metric).max().alias('maximum')).rename({scope:'scope_key'}).with_columns(
                            pl.lit(scope).alias('scope'),pl.lit(metric).alias('metric'),pl.lit(name).alias('candidate'),pl.lit(year).alias('year')))
            if name == selected_scenario:
                outliers.append(current.sort('local_population_capacity',descending=True).head(30).select(
                    'location_tag','province','area_km2','total_population','local_population_capacity','fill',
                    'population_retention','annualized_population_change','fraction_months_at_growth_cap').with_columns(pl.lit(year).alias('year')))
    pl.DataFrame(rows).write_csv(output/'world_comparison.csv')
    pl.concat(effects).write_parquet(output/'all_location_collateral.parquet')
    pl.concat(distributions).write_csv(output/'horizon_scope_distributions.csv')
    pl.concat(outliers).write_csv(output/'largest_capacity_outcomes.csv')
    replay=[r['maximum_absolute_residual'] for c in manifest['cases'] for r in c['monthly_replay']]
    lines=['# Global collateral comparison','',
        '**Diagnostic results, not overall acceptance.** Every location is simulated with identical geographical inputs, starting composition, food supply, employment and consumption. These comparisons use the growth and development settings recorded in each manifest scenario. Subsistence output and other shared inputs are recorded in the preparation manifest. No new cookery or victuals-market food is assumed.','',
        '| Scenario | Year | World population (millions) | World capacity (millions) | Locations with more unmet food than native-rank control | Locations below 90% starting population | Locations at stock-growth ceiling ≥90% of months |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for row in rows:
        lines.append(f"| {row['candidate']} | {row['year']} | {row['population_people']/1e6:.3f} | {row['capacity_people']/1e6:.3f} | {row['locations_more_unmet_food']} | {row['locations_population_below_90pct']} | {row['locations_at_food_growth_cap_90pct_of_months']} |")
    lines+=['',f"World checkpoints reproduce the independently saved monthly provincial comparison within {max(replay):.3g} absolute units across population, capacity, development, food stocks, production and consumption. Replay is checked at years 0, 25, 100 and 200.",'',
        'Growth-ceiling duration measures the provincial food-stock bonus, not net growth of every population type. Tribesmen retain the authorized cancellation. Sparse settlements are not rejected solely for reaching the ceiling. Historical demographic applicability, initial denominators, annualized growth, local drawdowns and physically defensible accessible capacity must be evaluated together. The 36 initially empty locations remain empty; proportional retention and annualized growth are undefined there and excluded from those distributions, while their capacity and food remain in world accounts.','',
        'Additional unmet food identifies collateral risk requiring diagnosis; it is not hidden by a higher world total. Global population declines are likewise not all classified as failed healthy controls: this world includes genuine starting scarcity and unmodeled external supply. The complete per-location effects and scoped quantiles are saved alongside this report.','',
        'Artifacts: `world_comparison.csv`, `all_location_collateral.parquet`, `horizon_scope_distributions.csv`, `largest_capacity_outcomes.csv`, annual province/scope histories, all-location checkpoints and the fingerprinted manifest.','']
    report.write_text('\n'.join(lines)+'\n')
    (output/'summary_identity.json').write_text(json.dumps(dict(model_accepted=False,monthly_replay_max_absolute_residual=max(replay),
        fingerprint=fingerprint([__file__,output/'manifest.json',*[output/f"{c['name']}_checkpoints.parquet" for c in manifest['cases']]],{})),indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);p.add_argument('--report');p.add_argument('--selected-scenario',default='equal_rank_quarter_offset');a=p.parse_args()
    run(ROOT/a.output, ROOT/a.report if a.report else None, a.selected_scenario)
