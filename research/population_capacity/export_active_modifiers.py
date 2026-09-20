"""Recover actual starting advances/policies from the simulation-aligned save."""
from pathlib import Path
import json
from prosper_or_perish_constructor.simulation.active_modifiers import export_activation_ledger
ROOT=Path(__file__).resolve().parents[2]
if __name__=='__main__':
    preparation=json.loads((ROOT/'artifacts/data/population_simulation/prepared_sources.manifest.json').read_text())
    print(export_activation_ledger(save=Path(preparation['population_snapshot']['source_save']),
        output=ROOT/'artifacts/data/population_simulation/repair_round_23/active_modifiers',
        profile='constructor',load_order=ROOT/'constructor.load_order.toml'))
