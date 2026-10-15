"""AI road weights: every road type carries its veto value, and each veto gap = the type's own step + 2."""
from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
COMMON = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)" / "in_game" / "common"
ROAD_PROXIMITY = {"gravel": 0, "paved": 5, "modern": 10, "railroad": 15}  # vanilla road_types proximity


def test_every_road_type_has_its_weight() -> None:
    injects = (COMMON / "road_types" / "pp_road_ai_weights.txt").read_text(encoding="utf-8-sig")
    values = (COMMON / "script_values" / "pp_road_ai_values.txt").read_text(encoding="utf-8-sig")
    for kind in ROAD_PROXIMITY:
        key = kind if kind == "railroad" else f"{kind}_road"
        assert f"INJECT:{key} = {{ ai_construct_weight = pp_road_ai_weight_{kind} }}" in injects
        assert re.search(rf"^pp_road_ai_weight_{kind} = \{{", values, re.M)


def test_veto_gap_is_road_step_plus_two() -> None:
    values = (COMMON / "script_values" / "pp_road_ai_values.txt").read_text(encoding="utf-8-sig")
    for kind, prox in ROAD_PROXIMITY.items():
        block = values.split(f"pp_road_ai_weight_{kind} = {{", 1)[1].split("\n}", 1)[0]
        gap = float(re.search(r"pp_road_proximity_gap < ([\d.]+)", block).group(1))
        assert abs(gap - ((20 - prox) / 1.15 + 2)) < 0.06, (kind, gap)
