"""Verify this bounded research round, without certifying model acceptance."""
from pathlib import Path
import hashlib
import json
import re
import polars as pl

from run_historical_direct import ROOT
from prosper_or_perish_constructor.simulation.historical_model import load_assignments

ROUND=ROOT/'artifacts/data/population_simulation/repair_round_56'


def hashes(mapping):
    for path,expected in mapping.items():
        actual=hashlib.sha256((ROOT/path).read_bytes()).hexdigest()
        if actual!=expected:
            raise ValueError('Stale evidence: '+path)


def main():
    handoff=ROUND/'handoff'
    tested=json.loads((handoff/'test_manifest.json').read_text())
    assert tested['exit_code']==0 and tested['tested_sources_unchanged']
    hashes(tested['hashes'])
    log=(handoff/'full_tests.log').read_text()
    result=re.search(r'(\d+) passed, (\d+) skipped',log)
    assert result and int(result[1])>=892 and int(result[2])==1
    assert 'local error.log has no setup building errors' in log
    replay=json.loads((handoff/'final_replay_manifest.json').read_text())
    assert replay['world_checkpoints_byte_identical']
    hashes(replay['after'])
    ledger_checks=json.loads((handoff/'manifest.json').read_text())
    hashes(ledger_checks['hashes'])
    records=[]
    for variant,directory,assignment in [
        ('basic',ROUND,'historical_assignments_round_56.json'),
        ('historical',ROUND/'archaeoglobe','historical_assignments_round_56_archaeoglobe.json')]:
        load_assignments(ROOT/'research/population_capacity'/assignment)
        compared=json.loads((directory/'comparison/manifest.json').read_text())
        hashes(compared['hashes'])
        assert compared['baseline_expanded_monthly_replays_world']
        assert compared['unchanged_food_growth_and_physical_scale_parameters']
        assert not compared['model_accepted']
        criteria=pl.read_csv(directory/'comparison/evaluated_criteria.csv')
        assert criteria.select('province','year').unique().height==96
        assert criteria.filter(pl.col('year')==100).height==48
        assert criteria.filter(pl.col('year')==200).height==48
        world=json.loads((directory/'world/manifest.json').read_text())
        assert len(world['regional_provinces'])==48 and not world['regional_only']
        audit=json.loads((directory/'world/world_food_audit/manifest.json').read_text())
        assert audit['starting_state_reproduced'] and audit['provincial_budgets_reproduced']
        assert len(audit['complete_provinces'])==3819
        attribution=world['preparation']['capacity_attribution']
        assert attribution['irrigation_attribution_available']
        assert attribution['irrigation_total']<attribution['infrastructure_total']
        records.append(dict(variant=variant,checks=criteria.height,
            passed=criteria.filter(pl.col('viability')=='passed').height,
            failed=criteria.filter(pl.col('viability')=='failed').height,
            model_accepted=False,irrigation_share=attribution['irrigation_share']))
    stats=pl.read_csv(handoff/'macro_starting_statistics.csv')
    assert stats.select('candidate','macro_region').unique().height==57==stats.height
    for f in ['starting_comparison.png','historical_variant_changes.png','diagnostic_growth_budgets.csv',
              'coarse_practice_coverage.csv','coarse_practice_sparse_field_flags.csv']:
        assert (handoff/f).stat().st_size>0
    paths=[ROOT/'research/population_capacity/round_56_findings.md',
        ROOT/'research/population_capacity/population_capacity_food_design.md',
        ROOT/'research/population_capacity/repair_progress.md',Path(__file__)]
    paths+=list(handoff.glob('*.csv'))+list(handoff.glob('*.png'))
    report=dict(bounded_research_round_verified=True,model_accepted=False,
        scope='Historical management, geographical accounting and top-down 100/200-year comparisons; no building balance or deployment',
        tests_passed=int(result[1]),tests_skipped=int(result[2]),
        skip_reason='Existing environment-dependent setup-building error-log fixture has no errors',
        variants=records,macro_table_rows=stats.height,
        remaining_model_failures='Broad local management applicability, Khmer food behavior, Caozhou growth equilibrium, global collateral scarcity and wider acceptance gates remain unresolved',
        hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
    (handoff/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='hashes'},indent=2))


if __name__=='__main__':main()
