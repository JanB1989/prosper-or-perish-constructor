"""Bind evaluated recovery histories to the matching acceptance candidate."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import numpy as np
import polars as pl
from run_historical_direct import ROOT
from prosper_or_perish_constructor.simulation.cache import fingerprint
from prosper_or_perish_constructor.simulation.behavior_acceptance import compare_recovery,write_evaluated_evidence
from prosper_or_perish_constructor.simulation.historical_scenarios import HistoricalScenario
from prosper_or_perish_constructor.simulation.model_acceptance import evaluate_model_acceptance,REQUIRED_EVIDENCE
from summarize_acceptance_evidence import run as summarize


def attach(output,recovery):
    acceptance=json.loads((output/'acceptance.json').read_text())
    reference=json.loads((output/'manifest.json').read_text())
    report_path=recovery/'report.json';report=json.loads(report_path.read_text())
    source_record=json.loads((ROOT/'research/population_capacity/population_convergence_extraction.json').read_text())
    identity=acceptance['input_fingerprint']
    if report['input_fingerprint']!=identity or not report['candidate_preparation_matches']:
        raise ValueError('Recovery belongs to a different acceptance candidate')
    recipe_path=Path(report['recipe_path']);recipe=json.loads(recipe_path.read_text())
    if (ROOT/recipe['reference_manifest']).resolve()!=(output/'manifest.json').resolve():
        raise ValueError('Recovery reference path differs')
    perturbations=[(c['perturbation'],c['population_factor'],c['food_factor']) for c in report['cases'] if c['development']==0]
    expected=fingerprint([ROOT/'research/population_capacity/run_equilibrium_recovery.py',recipe_path,output/'manifest.json',
        ROOT/'src/prosper_or_perish_constructor/simulation',ROOT/'research/population_capacity/population_convergence_extraction.json'],
        dict(model_input_fingerprint=reference['preparation']['model_input_fingerprint'],
             scenario=asdict(HistoricalScenario(**recipe['scenario'])),perturbations=perturbations))
    if report['fingerprint']!=expected:
        raise ValueError('Recovery code, source interpretation or recipe is stale')
    history=pl.read_parquet(recovery/'monthly.parquet')
    cases=[]
    for case in report['cases']:
        actual=history.filter(pl.col('location_tag')==case['name'])
        control=history.filter(pl.col('location_tag')==f"D{case['development']:g}_control")
        ordinary=compare_recovery(actual,control,end_month=0)
        logged=compare_recovery(actual.with_columns(pl.col('total_population').log()),
            control.with_columns(pl.col('total_population').log()),end_month=0)['total_population']
        if ordinary!=case['recovery'] or logged!=case['log_population_deviation_recovery']:
            raise ValueError('Saved recovery history disagrees with reported measurements')
        stationary=bool(np.max(np.abs(control['total_population'].to_numpy()/control['total_population'][0]-1.))<1e-5)
        if stationary!=case['stationary_control']:
            raise ValueError('Stationary-control claim disagrees with history')
        checks=[{'name':'stationary_unshocked_population','passed':stationary},
            {'name':'complete_required_horizons','passed':all(y*12 in actual['month'] for y in (100,200))},
            {'name':'finite_positive_population','passed':bool(np.isfinite(actual['total_population'].to_numpy()).all() and actual['total_population'].min()>0)}]
        horizons=[]
        for year in (100,200):
            a=actual.filter(pl.col('month')==year*12).row(0,named=True)
            b=control.filter(pl.col('month')==year*12).row(0,named=True)
            horizons.append(dict(year=year,population=a['total_population'],control_population=b['total_population'],
                population_log_deviation=float(np.log(a['total_population']/b['total_population'])),
                food=a['food'],control_food=b['food']))
        if case['perturbation'].startswith('population_'):
            checks.append({'name':'perturbation_halves_within_observed_200_years','horizon':200,'passed':logged['sustained_half_recovery_months'] is not None})
        cases.append(dict(name='fixed_system_recovery_'+case['name'],status='passed' if all(c['passed'] for c in checks) else 'failed',
            checks=checks,horizons=horizons,measurements=case,evidence=str(report_path)))
    results={}
    for group in REQUIRED_EVIDENCE:
        path=output/'evidence'/f'{group}.json';data=json.loads(path.read_text())
        if data['input_fingerprint']!=identity:
            raise ValueError('Stale original acceptance evidence')
        if group=='food_and_growth_equilibria':
            data['cases']=[x for x in data['cases'] if not x['name'].startswith('fixed_system_recovery_')]+cases
            data['missing_cases']=['actual-composition equilibria and stability; pure-peasant fixed-system stability is evaluated']
        if group=='historical_adjustment_comparisons':
            data['cases']=[{'name':'population_convergence_metric_comparison','status':'unresolved',
                'source':'research/population_capacity/population_convergence_extraction.json',
                'source_population_log_deviation_half_life_years':source_record['implied_monotone_half_life_years'],
                'measured_fixed_system_recovery':str(report_path),
                'limitation':'Recovery measurements are evaluated separately from wages, but historical applicability and frozen acceptance ranges remain unresolved.'}]
            data['missing_cases']=['applicable frozen demographic rate/recovery ranges and geographical coverage; do not turn convergence estimates into intrinsic growth rates']
        results[group]=write_evaluated_evidence(path,requirement=group,input_fingerprint=identity,
            cases=data['cases'],missing_cases=data['missing_cases'])
    reference_history=pl.read_parquet(output/'stock_12_shock_False.parquet')
    snapshots={y:reference_history.filter(pl.col('month')==y*12) for y in (0,25,100,200)}
    initial=pl.read_parquet(output/'starting_ledger.parquet').select('location_tag','historical_area_conflict_km2')
    snapshots[0]=snapshots[0].join(initial,on='location_tag',validate='1:1')
    evaluated=evaluate_model_acceptance(snapshots,results,input_fingerprint=identity)
    evaluated['coverage']=acceptance['coverage']
    evaluated['recovery_evidence_fingerprint']=fingerprint([Path(__file__),report_path,recovery/'monthly.parquet'],{})
    (output/'acceptance.json').write_text(json.dumps(evaluated,indent=2)+'\n')
    summarize(output)
    (output/'criteria_register.md').write_text((output/'evaluated_criteria_register.md').read_text())

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--recovery',type=Path,required=True)
    args=parser.parse_args();attach(args.output.resolve(),args.recovery.resolve())
