"""Screen every province, with reconciled budgets and an explicit failure register."""
from pathlib import Path
import json
import polars as pl
from run_historical_direct import ROOT,prepare
from prosper_or_perish_constructor.simulation.food_diagnosis import diagnose_provincial_food

def run():
    out=ROOT/'artifacts/data/population_simulation/repair_round_23'
    _,(state,context,prep)=prepare(('capacity.development_relative=0.05',
        'paths.active_modifier_ledger="artifacts/data/population_simulation/repair_round_23/active_modifiers/active_modifier_ledger.parquet"'))
    locations,totals,diagnosis=diagnose_provincial_food(state,context)
    locations.write_parquet(out/'starting_food_locations.parquet')
    totals.write_csv(out/'starting_food_provinces.csv')
    diagnosis.write_csv(out/'pressure_food_diagnosis.csv')
    history=pl.read_parquet(out/'historical_extent_correction/checkpoints.parquet')
    initial=history.filter(pl.col('year')==0).group_by('province').agg(
        pl.col('total_population').sum().alias('initial_population'),
        pl.col('development').mean().alias('initial_development'))
    screen=history.filter(pl.col('year').is_in([100,200])).group_by('province','year').agg(
        pl.col('total_population').sum(),pl.col('development').mean()).join(initial,on='province').with_columns(
        (pl.col('total_population')/pl.col('initial_population')).alias('population_retention'),
        pl.when(pl.col('initial_development')>0).then(pl.col('development')/pl.col('initial_development')).otherwise(None).alias('development_retention'))
    screen=screen.with_columns(((pl.col('population_retention')<.9)|(pl.col('development_retention')<.9)).alias('needs_diagnosis'))
    screen.join(diagnosis,on='province',suffix='_starting').write_csv(out/'province_failure_screen.csv')
    register={'model_accepted':False,'screening_not_historical_fitting':True,
      'required_horizons':[100,200],'input_fingerprint':prep['model_input_fingerprint'],
      'historical_run_manifest':json.loads((out/'historical_extent_correction/manifest.json').read_text()),
      'binding_note':'Fixed-state diagnosis and historical trajectories retain separate fingerprints; this screen does not certify either as accepted.',
      'failures':[
        {'id':'land-mixture-ceiling','status':'accounting corrected','diagnosis':'Crop-mixture-weighted suitability was used as a physical historical-area ceiling.',
         'expected_effect':'Restore only assigned fields by displacing known livelihoods, conserve area.', 'regression':'tests/test_historical_model.py'},
        {'id':'regional-demographic-loss','status':'open','diagnosis':'Large losses persist in East/Southeast Asia; inspect province_failure_screen.csv and residual deficits.',
         'next':'Complete dated regional management and cultivated-land assessments before changing shared food coefficients.'},
        {'id':'active-effects-coverage','status':'partial','diagnosis':prep['active_country_modifiers'],
         'next':'Reconcile output effects with observed food accounts; preserve unknown activation and unmodeled scopes.'},
        {'id':'historical-validation','status':'open','diagnosis':'Broader regional evidence, independent holdouts, demographic ranges and physically bounded water scenarios remain unvalidated.'}
      ]}
    (out/'failure_register.json').write_text(json.dumps(register,indent=2,default=str))
    print(screen.group_by('year').agg(pl.col('needs_diagnosis').sum()))
    print(diagnosis.filter(pl.col('province').is_in(['suzhou_province','jiaxing_province','songjiang_province','angkor_province','cairo_province','alexandria_province'])).select('province','food_balance','pressure_recoverable_consumption','residual_deficit_at_low_pressure'))
if __name__=='__main__':run()
