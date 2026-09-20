"""Render the current candidate and diagnostic outcomes without implying acceptance."""
from pathlib import Path
import argparse
import json
from prosper_or_perish_constructor.simulation.cache import fingerprint

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
import numpy as np
import polars as pl

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'artifacts/data/population_simulation/repair_round_25/reconciled_opportunities'


def run(output=OUT, title='Candidate — model acceptance incomplete', scenario=None):
    state = pl.read_parquet(output / 'starting_ledger.parquet')
    fig, axes = plt.subplots(2, 2, figsize=(16, 9), layout='constrained')
    panels = [('Starting capacity density (people/km²)', state['local_population_capacity'].to_numpy() * 1000 / state['area_km2'].to_numpy(), True),
              ('Starting development', state['development'].to_numpy(), False),
              ('Active infrastructure (flat game units)', state['infrastructure_population_capacity'].to_numpy(), True),
              ('Remaining clearing support (flat game units)', state['remaining_clearing_capacity'].to_numpy(), True)]
    for ax, (label, values, log) in zip(axes.flat, panels):
        finite = np.isfinite(values)
        points = ax.scatter(state['calibrated_lon'].to_numpy()[finite], state['calibrated_lat'].to_numpy()[finite],
            c=np.maximum(values[finite], .001) if log else values[finite], s=2, cmap='viridis',
            norm=LogNorm(vmin=.001, vmax=max(1., float(np.quantile(values[finite], .995)))) if log else None)
        ax.set(title=label, xlim=(-180, 180), ylim=(-60, 85), xlabel='Longitude', ylabel='Latitude')
        fig.colorbar(points, ax=ax, shrink=.8)
    fig.suptitle(title + '; point maps use canonical location coordinates')
    fig.savefig(output / 'candidate_maps.png', dpi=160)
    plt.close(fig)

    outcomes_path = output / 'province_horizon_results.csv'
    if outcomes_path.exists():
        outcomes = pl.read_csv(outcomes_path)
    else:
        outcomes_path = output / 'viability_criteria.csv'
        outcomes = pl.read_csv(outcomes_path).rename({'candidate': 'scenario'})
    choices = outcomes['scenario'].unique().to_list()
    if scenario is None:
        scenario = 'stock_12_shock_False' if 'stock_12_shock_False' in choices else (
            choices[0] if len(choices) == 1 else None)
    if scenario not in choices:
        raise ValueError('Select one available outcome scenario: ' + ', '.join(choices))
    outcomes = outcomes.filter(pl.col('scenario') == scenario)
    provinces = outcomes['province'].unique().sort().to_list()
    fig, ax = plt.subplots(figsize=(14, 7), layout='constrained')
    x = np.arange(len(provinces))
    for offset, year in ((-.18, 100), (.18, 200)):
        values = outcomes.filter(pl.col('year') == year).sort('province')['population_retention'].to_numpy()
        ax.bar(x + offset, values, width=.36, label=f'Year {year}')
    ax.axhline(.9, color='firebrick', linestyle='--', label='Peaceful-control 90% guardrail')
    ax.set_xticks(x, [p.removesuffix('_province').replace('_', ' ') for p in provinces], rotation=60, ha='right')
    ax.set(ylabel='Population / starting population', title='Complete-province outcomes — diagnostic screens are not historical fitting targets')
    ax.legend()
    fig.savefig(output / 'province_retention.png', dpi=160)
    plt.close(fig)
    (output/'render_manifest.json').write_text(json.dumps(dict(model_accepted=False,
        title=title,scenario=scenario,canonical_starting_ledger=True,
        limitations=['Point maps, not surveyed field polygons',
                     'Logarithmic panels clamp zero to0.001; these images do not certify source completeness',
                     'Provincial totals do not replace per-location acceptance checks'],
        fingerprint=fingerprint([Path(__file__),output/'starting_ledger.parquet',
            outcomes_path],{'scenario':scenario})),indent=2)+'\n')


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=OUT)
    parser.add_argument('--title',default='Candidate — model acceptance incomplete')
    parser.add_argument('--scenario')
    args=parser.parse_args()
    run(args.output,args.title,args.scenario)
