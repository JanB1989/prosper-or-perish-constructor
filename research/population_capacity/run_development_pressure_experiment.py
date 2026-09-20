"""Unaccepted world counterfactuals for starting development and land pressure.

Run with uv run python research/population_capacity/run_development_pressure_experiment.py.
No game data are changed. All interventions are explicit diagnostic assumptions.
"""
from dataclasses import fields
from pathlib import Path
import json
import numpy as np
import polars as pl
from prosper_or_perish_constructor.simulation.numpy_engine import NumPyLocationState
from prosper_or_perish_constructor.simulation.capacity_pressure import capacity_pressure_strength_arrays
from prosper_or_perish_constructor.simulation.prosperity import LOCAL_MONTHLY_DEVELOPMENT_KEY, LOCAL_MONTHLY_DEVELOPMENT_MODIFIER_KEY, DEVELOPMENT_MAX
from prosper_or_perish_constructor.simulation.profile import load_population_simulation_profile, prepare_population_simulation_state
from prosper_or_perish_constructor.simulation.land_experiments import _totals
from prosper_or_perish_constructor.simulation.run import Simulation
from prosper_or_perish_constructor.simulation.cache import fingerprint

ROOT = Path(__file__).resolve().parents[2]
YEARS = (0, 25, 100, 200, 300, 400, 500)
OVERRIDES = ("capacity.gaez_zero_development_fraction=1.5", "capacity.location_area_exponent=0.5",
    "capacity.baseline_open_land_access_fraction=0.005", "mechanics.subsistence_output=1.25",
    "mechanics.development_monthly_per_point=-0.000025", "simulation.initial_food_months=12")


def pressure_incentive(population, capacity):
    """Constant positive effect offset by native free-land strength.

    Overpopulation does not give an unbounded bonus. The no-band gap follows
    current simulator semantics and therefore gets the full constant effect.
    """
    abundant, available, _, strength = capacity_pressure_strength_arrays(population, capacity)
    return 1. - np.where(abundant | available, strength, 0.)


class PressureExperimentEngine(NumPyLocationState):
    absolute_bonus = 0.
    relative_bonus = 0.

    def _apply_prosperity_development(self, prosperity_scale):
        b = self.prosperity_baselines
        if b is None or self.development.shape[0] != self.n:
            return
        incentive = pressure_incentive(self.total_population, self.population_capacity)
        monthly = (prosperity_scale * b.get_effect(LOCAL_MONTHLY_DEVELOPMENT_KEY)
            + self.development * b.development_monthly_per_point + self.absolute_bonus * incentive)
        modifier = prosperity_scale * b.get_effect(LOCAL_MONTHLY_DEVELOPMENT_MODIFIER_KEY) + self.relative_bonus * incentive
        self.development = np.clip(self.development + monthly * (1. + modifier), 0., DEVELOPMENT_MAX)
        self.extras_float['development'] = self.development


def run(*, strong_development=False):
    overrides = (*OVERRIDES, *(['capacity.development_relative=0.01'] if strong_development else []))
    profile = load_population_simulation_profile(ROOT / 'population_capacity_simulation.toml', repo=ROOT, overrides=overrides)
    state, context, prep = prepare_population_simulation_state(ROOT, ROOT / 'constructor.toml', profile)
    output = ROOT / 'artifacts/data/population_simulation' / ('repair_round_19_strong' if strong_development else 'repair_round_19')
    output.mkdir(parents=True, exist_ok=True)
    # Deliberately broad starting-development probes, never inferred history.
    plans = {'baseline': (0, 0., 0.), 'asia_start_dev_plus20': (20, 0., 0.),
             'asia_start_dev_plus50': (50, 0., 0.), 'pressure_absolute_0005': (0, .005, 0.),
             'pressure_relative_100pct': (0, 0., 1.), 'asia20_and_pressure_absolute': (20, .005, 0.)}
    if strong_development:
        plans = {key: plans[key] for key in ('baseline', 'asia_start_dev_plus20', 'pressure_absolute_0005', 'asia20_and_pressure_absolute')}
    histories, snapshots = [], []
    for name, (start_add, absolute, relative) in plans.items():
        initial = state.with_columns(pl.lit(True).alias('capacity_experiment_only'))
        if start_add:
            initial = initial.with_columns(pl.when(pl.col('macro_region').is_in(['east_asia', 'south_east_asia']))
                .then((pl.col('development') + start_add).clip(0, DEVELOPMENT_MAX)).otherwise(pl.col('development')).alias('development'))
        sim = Simulation(initial, context)
        old = sim._engine
        sim._engine = PressureExperimentEngine(**{f.name: getattr(old, f.name) for f in fields(NumPyLocationState)})
        sim._engine.absolute_bonus = absolute
        sim._engine.relative_bonus = relative
        annual = []
        for year in range(501):
            if year:
                sim.run(12, progress=False, materialize=False)
            sim.evaluate_food_budget()
            d = sim.diagnostic_state()
            annual.append(_totals(d, year).with_columns(pl.lit(name).alias('scenario')))
            if year in YEARS:
                snapshots.append(d.with_columns(pl.lit(year).alias('year'), pl.lit(name).alias('scenario')))
        histories.extend(annual)
        print('Completed ' + name, flush=True)
    history = pl.concat(histories, how='diagonal_relaxed')
    history.write_parquet(output / 'annual_history.parquet')
    pl.concat(snapshots, how='diagonal_relaxed').write_parquet(output / 'checkpoints.parquet')
    history.filter(pl.col('year').is_in(YEARS)).write_csv(output / 'comparison.csv')
    manifest = {'accepted': False, 'overrides': overrides, 'plans': plans, 'preparation': prep,
        'formula': '(prosperity development + D decay + absolute*(1-free_land_strength)) * (1+prosperity modifier+relative*(1-free_land_strength))',
        'limitations': ['Starting Asian development additions are broad counterfactuals, not historical estimates.',
            'No new hectares or infrastructure in these scenarios; existing infrastructure retained.',
            'No-band gap below 10% fill and above 10000 people receives full bonus under current unverified engine semantics.',
            'No food gate: scarcity can stimulate development while starving, intentionally tested for failure.',
            'Constant effect plus opposite abundant/available effects requires native game implementation and engine verification before acceptance.',
            'No autonomous investment, trade, migration or promotion; P50 only.'],
        'fingerprint': fingerprint([Path(__file__), ROOT/'src/prosper_or_perish_constructor/simulation/numpy_engine.py'], {'preparation':prep, 'plans':plans, 'overrides':OVERRIDES})}
    (output/'manifest.json').write_text(json.dumps(manifest, indent=2, default=str))
    rows = history.filter((pl.col('year')==500) & pl.col('scope_key').is_in(['world','east_asia','south_east_asia','western_europe','south_america']))
    lines = ['# Development and land-pressure counterfactuals', '', 'Unaccepted diagnostic scenarios; no historical development assignments or game export.', '',
        '| Scenario | Scope | P500 million | K500 million | Mean development | Starved location-months |', '|---|---|---:|---:|---:|---:|']
    for r in rows.iter_rows(named=True):
        lines.append(f"| {r['scenario']} | {r['scope_key']} | {r['total_population']*profile.people_per_game_unit/1e6:.2f} | {r['local_population_capacity']*profile.people_per_game_unit/1e6:.2f} | {r['mean_development']:.2f} | {r['starvation_months']:.0f} |")
    lines += ['', *manifest['limitations']]
    (output/'report.md').write_text('\n'.join(lines)+'\n')

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--strong-development', action='store_true')
    run(strong_development=parser.parse_args().strong_development)
