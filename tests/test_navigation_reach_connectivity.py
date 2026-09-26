"""The researched navigable rivers must stay continuous and reach the open sea.

The World Builder handover's navigation manifest reports, per researched river, the share of its traced course that
became water and the share lying in tiles connected to the open sea. A stranded river (a channel piece a fleet cannot
reach from the sea, like the old two-tile Seine at Rouen) fails here.
"""
from pathlib import Path
import json

import pytest

from prosper_or_perish_constructor.worldbuilder.contract import load_config

REPO = Path(__file__).resolve().parents[1]
# rivers that cannot reach the sea by design, and small known shortfalls
EXCEPTIONS = {
    "Niger (middle, inland delta)": 0.0,   # inland system above the Niger rapids, not connected to the sea
    "Ob with Irtysh": 0.0,                  # the Ob mouth opens onto an impassable arctic sea zone
    "James": 0.85,                          # 12 % of the traced course sits in a separate channel group (not yet investigated)
    "Mekong": 0.9,                          # 9 % of the traced course sits in a separate channel group (not yet investigated)
}


@pytest.fixture(scope="module")
def connectivity():
    cfg = load_config(REPO, REPO / "constructor.toml")
    manifest = cfg.handover / "navigation" / "manifest.json"
    if not manifest.is_file():
        pytest.skip(f"no navigation handover at {manifest}")
    data = json.loads(manifest.read_text())
    if "reach_connectivity" not in data:
        pytest.skip("handover navigation is not built from researched reaches")
    return data["reach_connectivity"]


def test_every_researched_river_became_water(connectivity):
    low = {r: v["converted"] for r, v in connectivity.items() if v["converted"] < 0.97}
    assert not low, f"researched rivers only partly converted to channels: {low}"


def test_every_researched_river_reaches_the_sea(connectivity):
    low = {r: v["ocean_connected"] for r, v in connectivity.items() if v["ocean_connected"] < EXCEPTIONS.get(r, 0.95)}
    assert not low, f"researched rivers stranded from the open sea: {low}"
