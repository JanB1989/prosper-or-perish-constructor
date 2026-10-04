"""The AI builds up food in its capital province (2026-10-04, Jan).

Every building that makes Province Food in the province (a Provisioning slot, the Tavern, the Cookshop, the Public
Kitchen) adds the location-scope script value ``pp_capital_food_weight`` to its ``ai_construct_weight`` after the income
divide, so the term is flat: the engine values a capital's food and profit far less in rich empires, and the capitals
belong to the richest. Buildings that move food out of the province (Grange, Victualling Yard) do not get it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
BLUEPRINTS = ROOT / "blueprints/accepted/buildings"
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
VALUES = MOD_ROOT / "in_game/common/script_values/pp_food_building_values.txt"
TERM = "add = pp_capital_food_weight"


def _blueprints() -> dict[str, dict]:
    out = {}
    for path in sorted(BLUEPRINTS.glob("*.yml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
        if isinstance(raw, dict) and raw.get("tag"):
            out[raw["tag"]] = raw
    return out


def _methods(raw: dict) -> list[str]:
    building = raw.get("building") or {}
    return [m for slot in building.get("production_method_slots") or [] for m in slot.get("methods") or []]


def _weight(body: str) -> str:
    match = re.search(r"ai_construct_weight = \{", body)
    if not match:
        return ""
    i, depth = match.end(), 1
    while depth:
        depth += (body[i] == "{") - (body[i] == "}")
        i += 1
    return body[match.end(): i - 1]


def _food_makers() -> dict[str, dict]:
    makers = {}
    for tag, raw in _blueprints().items():
        if not (raw.get("building") or {}).get("body"):
            continue
        if tag in {"tavern", "cookshop", "public_kitchen"} or any(m.endswith("_provision") for m in _methods(raw)):
            makers[tag] = raw
    return makers


def test_capital_food_weight_value() -> None:
    text = VALUES.read_text(encoding="utf-8-sig")
    block = text[text.index("pp_capital_food_weight = {"):]
    assert "province_definition = owner.capital.province_definition" in block
    assert re.search(r"add = \{ value = 14 subtract = pp_location_stored_months divide = 8 min = 0 max = 1 "
                     r"multiply = 100 \}", block)


def test_every_food_maker_wants_the_capital() -> None:
    makers = _food_makers()
    assert {"tavern", "cookshop", "public_kitchen", "wheat_farm", "fishing_village", "fruit_orchard"} <= set(makers)
    missing = [tag for tag, raw in makers.items() if TERM not in _weight(raw["building"]["body"])]
    assert not missing


@pytest.mark.parametrize("tag", sorted(_food_makers()))
def test_capital_term_is_flat(tag: str) -> None:
    weight = _weight(_food_makers()[tag]["building"]["body"])
    divide = weight.rfind("divide = { value = scope:owner.monthly_income_total")
    assert weight.index(TERM) > divide


def test_food_movers_do_not_get_it() -> None:
    blueprints = _blueprints()
    for tag in ("grange", "victualling_yard"):
        assert TERM not in blueprints[tag]["building"]["body"]


def test_rendered_weights_carry_it() -> None:
    for name in ("zz_pp_tavern.txt", "zz_pp_wheat_farm_tier0.txt"):
        text = (MOD_ROOT / "in_game/common/building_types" / name).read_text(encoding="utf-8-sig")
        assert TERM in text
