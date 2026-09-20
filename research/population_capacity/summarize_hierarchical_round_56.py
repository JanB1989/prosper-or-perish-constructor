"""Top-down component attribution, coverage checks and comparable maps for round56."""
from pathlib import Path
import json
import hashlib
import numpy as np
import polars as pl
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm, TwoSlopeNorm

from run_historical_direct import ROOT, prepare
from prosper_or_perish_constructor.simulation.agricultural_employment import attach_slave_agriculture

ROUND=ROOT/'artifacts/data/population_simulation/repair_round_56'
BASE=ROOT/'artifacts/data/population_simulation/repair_round_55/grouped_world'


def main():
    out=ROUND/'handoff';out.mkdir(exist_ok=True)
    meta=json.loads((BASE/'manifest.json').read_text())
    profile,(baseline,context,_)=prepare(meta['overrides'])
    baseline=attach_slave_agriculture(baseline,subsistence_output=1.3,hiring_fraction=.75).sort('location_tag')
    old=pl.read_parquet(BASE/'starting_ledger.parquet').sort('location_tag')
    assert baseline.select(old.columns).equals(old)
    frames={'round55':baseline,
        'round56_basic':pl.read_parquet(ROUND/'world/starting_ledger.parquet').sort('location_tag'),
        'round56_historical':pl.read_parquet(ROUND/'archaeoglobe/world/starting_ledger.parquet').sort('location_tag')}
    statistics=[]; checks={}; attributions=[]
    for label,s in frames.items():
        assert s['location_tag'].to_list()==baseline['location_tag'].to_list()
        area=(s['crop_fallow_block_km2']+s['extensive_grazing_land_km2']+
              s['retained_wild_land_km2']+s['area_km2']*s['urban_fraction_1300'])
        assert np.allclose(area,s['area_km2'],rtol=0,atol=1e-7)
        assert (s['water_managed_fields_km2']<=s['crop_fallow_block_km2']+1e-8).all()
        assert np.allclose(s['capacity__water_control'],s['capacity__water_increment']+s['capacity__water_managed_baseline'])
        flat=s['base_population_capacity']+s['infrastructure_population_capacity']
        factor=1+profile.capacity_formula.global_relative+s['development']*profile.capacity_formula.development_relative
        assert np.allclose(flat*factor,s['local_population_capacity'])
        bflat=baseline['base_population_capacity']+baseline['infrastructure_population_capacity']
        # This is a sequential ACCOUNTING attribution, not a causal rerun:
        # attained-yield normalization can couple physical and management terms.
        delta_dev=bflat*factor-baseline['local_population_capacity']
        delta_physical=s['local_population_capacity']-bflat*factor
        assert np.allclose(delta_dev+delta_physical,s['local_population_capacity']-baseline['local_population_capacity'])
        current=s.with_columns(pl.lit(label).alias('candidate'),
            (s['capacity__water_increment']*factor).alias('irrigation_increment_effective'),
            (s['capacity__water_managed_baseline']*factor).alias('served_field_baseline_effective'),
            (s['remaining_clearing_capacity']*factor).alias('clearing_opportunity_effective'),
            (s['remaining_water_capacity']*factor).alias('water_opportunity_upper_effective'),
            (s['base_population_capacity']*factor).alias('natural_support_effective'),
            (s['capacity__cultivated_land']*factor).alias('maintained_dry_fields_effective'),
            (s['urban_population_allowance']*factor).alias('urban_allowance_effective'),
            (s['local_population_capacity']-pl.Series(profile.capacity_formula.evaluate(
                base_capacity=s['base_population_capacity'].to_numpy(),
                infrastructure_capacity=s['infrastructure_population_capacity'].to_numpy(),
                development=np.zeros(s.height)))).alias('development_full_increment'),
            (s['local_population_capacity']*1000/s['area_km2']).alias('capacity_density'),
            delta_dev.alias('development_accounting_effect'),delta_physical.alias('physical_accounting_effect'),
            (s['local_population_capacity']-baseline['local_population_capacity']).alias('capacity_change'))
        source_sum=current.select(pl.sum_horizontal('natural_support_effective','maintained_dry_fields_effective',
            'served_field_baseline_effective','irrigation_increment_effective','urban_allowance_effective')).to_series()
        assert np.allclose(source_sum,current['local_population_capacity'],rtol=1e-10,atol=1e-8)
        current.select('location_tag','candidate','macro_region','region','province','development',
            'management_rule_id','historical_system_id','local_population_capacity',
            'development_accounting_effect','physical_accounting_effect','capacity_change',
            'irrigation_increment_effective','served_field_baseline_effective',
            'clearing_opportunity_effective','water_opportunity_upper_effective').write_parquet(out/(label+'_location_attribution.parquet'))
        for scope in ['macro_region','region','province']:
            current.group_by(scope).agg(pl.col('capacity_change','development_accounting_effect',
                'physical_accounting_effect','irrigation_increment_effective','served_field_baseline_effective').sum()
                ).sort('capacity_change',descending=True).write_csv(out/f'{label}_{scope}_attribution.csv')
        stats=current.group_by('candidate','macro_region').agg(pl.len().alias('locations'),
            pl.col('total_population').sum().alias('population_total'),
            pl.col('local_population_capacity').sum().alias('capacity_total'),
            *[getattr(pl.col('local_population_capacity'),agg)().alias('capacity_'+agg) for agg in ['min','max','median','mean']],
            *[getattr(pl.col('development'),agg)().alias('development_'+agg) for agg in ['min','max','median','mean']],
            pl.col('capacity_density').median().alias('density_median_people_km2'),
            pl.col('crop_fallow_block_km2','water_managed_fields_km2','area_km2').sum(),
            pl.col('irrigation_increment_effective','clearing_opportunity_effective','water_opportunity_upper_effective',
                'natural_support_effective','maintained_dry_fields_effective','served_field_baseline_effective',
                'urban_allowance_effective','development_full_increment').sum())
        stats=stats.with_columns((pl.col('population_total')/pl.col('capacity_total')).alias('aggregate_fill'),
            (pl.col('irrigation_increment_effective')/pl.col('capacity_total')).alias('irrigation_increment_share'),
            (pl.col('development_full_increment')/pl.col('capacity_total')).alias('development_full_increment_share'),
            (pl.col('natural_support_effective')/pl.col('capacity_total')).alias('natural_support_share'),
            (pl.col('urban_allowance_effective')/pl.col('capacity_total')).alias('urban_allowance_share'),
            (pl.col('water_managed_fields_km2')/pl.col('crop_fallow_block_km2')).alias('served_field_area_share'),
            (pl.col('clearing_opportunity_effective')/(pl.col('capacity_total')+pl.col('clearing_opportunity_effective'))).alias('remaining_clearing_share'))
        statistics.append(stats)
        checks[label]=dict(locations=s.height,land_maximum_residual_km2=float((area-s['area_km2']).abs().max()),
            water_partition_maximum_residual=float((s['capacity__water_control']-s['capacity__water_increment']-s['capacity__water_managed_baseline']).abs().max()),
            capacity_total_million_people=float(s['local_population_capacity'].sum()/1000),
            management_mean=float(s['development'].mean()),area_conflicts=int((s['historical_area_conflict_km2']>1e-7).sum()))
    pl.concat(statistics).sort('macro_region','candidate').write_csv(out/'macro_starting_statistics.csv')
    source=pl.read_parquet(ROOT/'artifacts/data/population_capacity/location_land_potential.parquet')
    archaeo=[c for c in source.columns if c.startswith('archaeoglobe_land_use_intensity')]
    checks['previous_historical_practice_coverage']={c:source.height-source[c].null_count() for c in archaeo}
    history=pl.read_parquet(ROUND/'archaeoglobe/world/common_slower_quarter_monthly.parquet')
    history.filter(pl.col('province').is_in(['caozhou_province','hatunqulla_province','indrapura_khmer_province']) &
        pl.col('month').is_in([1,300,1200,2400])).group_by('province','month').agg(
        pl.col('total_population','food_production','food_consumption','food','food_balance').sum(),
        pl.col('food_growth_bonus','food_growth_ceiling','prosperity').mean(),
        ((pl.col('net_annualized_growth')*pl.col('total_population')).sum()/pl.col('total_population').sum()).alias('population_weighted_net_growth')
        ).sort('province','month').write_csv(out/'diagnostic_growth_budgets.csv')
    # Same colour limits across candidates; point positions come from canonical data.
    fig,axes=plt.subplots(3,3,figsize=(17,11),layout='constrained')
    for row,(label,s) in enumerate(frames.items()):
        vals=[s['local_population_capacity']*1000/s['area_km2'],s['development'],
              s['capacity__water_increment']/(s['base_population_capacity']+s['infrastructure_population_capacity'])]
        norms=[LogNorm(.1,1000),plt.Normalize(0,100),plt.Normalize(0,1)]
        for col,(v,norm) in enumerate(zip(vals,norms)):
            ax=axes[row,col];p=ax.scatter(s['calibrated_lon'],s['calibrated_lat'],c=np.maximum(v.to_numpy(),.001),s=1.2,cmap='viridis',norm=norm)
            ax.set(xlim=(-180,180),ylim=(-60,85),title=f'{label}: '+['capacity people/km²','development','incremental irrigation / current capacity'][col]);fig.colorbar(p,ax=ax,shrink=.75)
    fig.suptitle('Round56 research comparison — unaccepted; identical colour scales; canonical location points')
    fig.savefig(out/'starting_comparison.png',dpi=150);plt.close(fig)
    new=frames['round56_historical']
    coarse=new.filter(pl.col('management_rule_id').str.starts_with('archaeoglobe')).with_columns(
        (pl.col('crop_fallow_block_km2')/pl.col('area_km2')).alias('current_field_share'))
    sparse=coarse.filter(pl.col('current_field_share')<.01)
    sparse.select('location_tag','macro_region','region','province','current_field_share','development',
        'management_rule_id','local_population_capacity').write_csv(out/'coarse_practice_sparse_field_flags.csv')
    coarse.group_by('macro_region').agg(pl.len().alias('coarse_practice_locations'),
        (pl.col('current_field_share')<.01).sum().alias('below_one_percent_fields'),
        pl.col('current_field_share').median().alias('median_field_share')).sort('macro_region').write_csv(out/'coarse_practice_coverage.csv')
    (out/'coarse_practice_coverage_contract.json').write_text(json.dumps(dict(
        threshold_role='Diagnostic flag only; not used to assign, fit or clip development/capacity',
        threshold_current_cultivated_fraction=.01,population_used=False,
        historical_logic='Regional prevalence cannot establish local cultivation intensity',
        fields_include='Canonical crop/fallow block, not harvested hectares',
        flagged_locations=sparse.height,coarse_assigned_locations=coarse.height),indent=2)+'\n')
    b=pl.read_parquet(BASE/'common_slower_quarter_checkpoints.parquet').filter(pl.col('year')==200).sort('location_tag')
    a=pl.read_parquet(ROUND/'archaeoglobe/world/common_slower_quarter_checkpoints.parquet').filter(pl.col('year')==200).sort('location_tag')
    fig,axes=plt.subplots(1,3,figsize=(17,4.7),layout='constrained')
    vals=[np.log2(new['local_population_capacity']/baseline['local_population_capacity']),
          new['development']-baseline['development'],100*(a['total_population']/b['total_population']-1)]
    for ax,v,title,bound in zip(axes,vals,['Starting capacity: log2(new / baseline)','Starting development: point change','Year200 population: % difference'],[2,50,50]):
        p=ax.scatter(new['calibrated_lon'],new['calibrated_lat'],c=v,s=1.5,cmap='coolwarm',norm=TwoSlopeNorm(0,-bound,bound));ax.set(title=title,xlim=(-180,180),ylim=(-60,85));fig.colorbar(p,ax=ax,shrink=.75)
    fig.suptitle('Historical-practice variant versus round55 — changes, not acceptance')
    fig.savefig(out/'historical_variant_changes.png',dpi=150);plt.close(fig)
    checks['limitations']=['Capacity units in CSV are thousands of people; density is people/km².',
        'Means and medians describe locations; shares are ratios of regional sums.',
        'Irrigation share is incremental yield benefit, not the whole water-managed field system.',
        'Natural + maintained dry fields + served-field baseline + water increment + urban allowance reconcile current capacity; full development increment overlaps these sources and is not additive.',
        'Remaining clearing share excludes speculative water potential; water column remains an upper opportunity awaiting water-volume evidence.',
        'Sequential development/physical attribution is an identity, not independent causal scenarios.',
        'Maps clip colour ranges; underlying CSV/parquet values are not clipped.']
    checks['model_accepted']=False
    checks['hashes']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),
        BASE/'starting_ledger.parquet',ROUND/'world/starting_ledger.parquet',ROUND/'archaeoglobe/world/starting_ledger.parquet']}
    (out/'manifest.json').write_text(json.dumps(checks,indent=2)+'\n')
    print(json.dumps(checks,indent=2))


if __name__=='__main__':main()
