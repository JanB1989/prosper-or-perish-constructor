"""Evaluate the frozen regional-practice variant with unchanged mechanics."""
import json
from run_historical_direct import ROOT
from run_candidate_world_comparison import run

if __name__ == '__main__':
    root=ROOT/'artifacts/data/population_simulation/repair_round_56'
    run('research/population_capacity/historical_assignments_round_56_archaeoglobe.json',
        root/'archaeoglobe/world',
        scenario_file=ROOT/'research/population_capacity/round_37_source_replay_scenario.json',
        additional_tags=json.loads((root/'preflight/additional_tags.json').read_text()),
        extra_overrides=('capacity.gaez_zero_development_fraction=4.5',
            'mechanics.subsistence_output=1.3',
            'paths.annual_crop_evidence="artifacts/data/population_capacity/repair_round_45/crop_risk_scenarios/crop_system_scenarios.parquet"'))
