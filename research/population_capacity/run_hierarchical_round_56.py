"""One candidate world run, plus unchanged monthly controls for the expanded scope."""
import json
from run_historical_direct import ROOT
from run_candidate_world_comparison import run


def main():
    output=ROOT/'artifacts/data/population_simulation/repair_round_56'
    tags=json.loads((output/'preflight/additional_tags.json').read_text())
    kwargs=dict(scenario_file=ROOT/'research/population_capacity/round_37_source_replay_scenario.json',
        extra_overrides=('capacity.gaez_zero_development_fraction=4.5','mechanics.subsistence_output=1.3',
            'paths.annual_crop_evidence="artifacts/data/population_capacity/repair_round_45/crop_risk_scenarios/crop_system_scenarios.parquet"'),
        additional_tags=tags)
    run('research/population_capacity/historical_assignments_round_56.json',output/'world',**kwargs)
    run('artifacts/data/population_simulation/repair_round_55/grouped_hyde/input/assignments.json',
        output/'baseline_expanded_controls',regional_only=True,**kwargs)


if __name__=='__main__':
    main()
