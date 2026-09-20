"""Prepare direct historical capacity without building-level calibration."""
from pathlib import Path
import json
import polars as pl
from prosper_or_perish_constructor.simulation.profile import load_population_simulation_profile, prepare_population_simulation_state
ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "artifacts/data/population_simulation/historical_direct_round_22"
OVERRIDES = ('paths.historical_assignments="research/population_capacity/historical_capacity_assignments.json"',
 'capacity.gaez_zero_development_fraction=1.5','capacity.location_area_exponent=0.5',
 'capacity.baseline_open_land_access_fraction=0.005','mechanics.subsistence_output=1.25',
 'mechanics.development_monthly_per_point=-0.000025','simulation.initial_food_months=12')
def prepare(extra=()):
 p=load_population_simulation_profile(ROOT/'population_capacity_simulation.toml',repo=ROOT,overrides=(*OVERRIDES,*extra))
 return p, prepare_population_simulation_state(ROOT,ROOT/'constructor.toml',p)
if __name__=='__main__':
 p,(state,context,metadata)=prepare()
 out=OUTPUT;out.mkdir(parents=True,exist_ok=True)
 state.write_parquet(out/'starting_ledger.parquet')
 (out/'preparation.json').write_text(json.dumps(metadata,indent=2,default=str))
 print(metadata['historical_model'])
 print(state.filter(pl.col('location_tag').is_in(['wuxian','angkor','cairo'])).select('location_tag','development','base_population_capacity','infrastructure_population_capacity','local_population_capacity','historical_area_conflict_km2'))
