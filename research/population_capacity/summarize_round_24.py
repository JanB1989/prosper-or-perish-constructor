"""Reproducible employment targets and regional comparison figures."""
from pathlib import Path
import json
import polars as pl
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[2]

def run():
 out=ROOT/'artifacts/data/population_simulation/repair_round_24'
 state=pl.read_parquet(out/'employment_075/starting_jobs_0.75.parquet')
 state.select('location_tag','province','candidate_agriculture_jobs__slaves','candidate_agriculture_food_per_worker__slaves',
   'candidate_agriculture_land_job_budget','candidate_agriculture_reserved_peasant_jobs','candidate_agriculture_reserved_existing_jobs',
   (pl.col('candidate_agriculture_jobs__slaves')*pl.col('candidate_agriculture_food_per_worker__slaves')).alias('fully_staffed_monthly_food'),
   'candidate_agriculture_contract').write_csv(out/'proposed_agricultural_employment_targets.csv')
 base=pl.read_parquet(out/'employment_reserved/checkpoints.parquet').filter(pl.col('hiring_fraction')==0)
 proposed=pl.read_parquet(out/'employment_075/checkpoints.parquet')
 baseline=base.select('location_tag','year',pl.col('total_population').alias('baseline_population'))
 comparison=proposed.join(baseline,on=['location_tag','year']).join(state.select('location_tag','candidate_agriculture_jobs__slaves'),on='location_tag')
 comparison.group_by('province','year').agg(pl.col('total_population').sum(),pl.col('baseline_population').sum(),
    pl.col('agriculture_food__slaves').sum(),pl.col('candidate_agriculture_jobs__slaves').sum(),pl.col('development').mean()).with_columns(
    (pl.col('total_population')-pl.col('baseline_population')).alias('population_change')).write_csv(out/'all_province_075_comparison.csv')
 h=pl.read_parquet(out/'employment_controls_0.75/monthly_history.parquet').group_by('scenario','month').agg(pl.col('total_population').sum())
 bali=pl.read_parquet(out/'bali/monthly_history.parquet').group_by('scenario','month').agg(pl.col('total_population').sum())
 fig,axes=plt.subplots(1,2,figsize=(12,4),constrained_layout=True)
 for scenario in ['stock_0_shock_False','stock_24_shock_False','stock_12_shock_True']:
    d=h.filter(pl.col('scenario')==scenario).sort('month');axes[0].plot(d['month']/12,d['total_population']/1000,label=scenario.replace('_',' '))
 axes[0].axhline(1.47008444,color='grey',linestyle=':',label='starting population')
 axes[0].set(title='Patna: proposed productive employment',xlabel='Years',ylabel='Population (millions)');axes[0].legend(fontsize=8)
 for scenario in ['unchanged','evidence_0.5']:
    d=bali.filter(pl.col('scenario')==scenario).sort('month');axes[1].plot(d['month']/12,d['total_population']/1000,label=scenario)
 axes[1].axhline(.26634357,color='grey',linestyle=':',label='starting population')
 axes[1].set(title='Bali province: management correction alone',xlabel='Years',ylabel='Population (millions)');axes[1].legend(fontsize=8)
 fig.suptitle('Round 24 experiments — capacity model not yet accepted')
 fig.savefig(out/'behavior_comparison.png',dpi=160);plt.close(fig)
 print(out/'behavior_comparison.png')
 print(pl.read_parquet(out/'employment_075/annual_history.parquet').filter(pl.col('scope_key').is_in(['world','south_asia'])&pl.col('year').is_in([0,100,200])).select('scope_key','year','total_population'))
if __name__=='__main__':run()
