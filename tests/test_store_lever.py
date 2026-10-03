"""The store lever (store_lever.py): where the Tavern, the Cookshop and the Grange stop, read from the mod's sources.

The province store moves the Province Food output (Low Stores / Full Stores, [stored_food] in constructor.toml), so
every maker of Province Food stops where its recipe stops paying, and the Grange earns Surplus Sales from a full
store only. These tests pin the properties the design rests on, not single numbers.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from prosper_or_perish_constructor import store_lever

ROOT = Path(__file__).resolve().parents[1]
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
DEFINES = MOD_ROOT / "loading_screen/common/defines/pp_defines_adjustments.txt"
VICTUALS = 2.7          # the mean victuals price the start model uses ([worldbuilder.start.food_sim])
PRICES = (1.5, 2.0, 2.7, 3.5, 4.5, 6.0)


@pytest.fixture(scope="module")
def design() -> store_lever.Design:
    return store_lever.load_design(ROOT)


def _margin_threshold() -> float:
    text = DEFINES.read_text(encoding="utf-8-sig")
    return float(re.search(r"^\s*AI_BUILDING_PROFIT_MARGIN_THRESHOLD\s*=\s*([\d.]+)", text, flags=re.M).group(1))


def test_design_is_read_from_the_blueprints_and_the_config(design: store_lever.Design) -> None:
    assert design.pivot == 12
    assert design.tavern_food == 25.5 and design.tavern_victuals == 0.8        # 1 victual = 32 food
    assert design.grange_food == 24.0 and design.grange_victuals == 0.6       # 1 victual = 40 food
    assert design.tavern_fixed > 0 and design.grange_fixed > design.grange_gate_cost > 0
    assert design.tavern_sales_cut < 0 and design.starving_victuals <= -2 and design.starving_food > 0


def test_province_food_is_worth_more_below_the_pivot_and_less_above(design: store_lever.Design) -> None:
    assert design.food_modifier(12) == 1.0
    values = [design.food_modifier(months) for months in range(25)]
    assert values == sorted(values, reverse=True) and values[0] > 1 > values[-1] > 0
    assert design.food_modifier(40) == design.food_modifier(24)                # the lever stops at 24 months
    # Jan's shares of an empty store's output (2026-10-03): 100 / 80 / 65 / 50 / 40 % at 0 / 6 / 12 / 18 / 24 months
    shares = [design.food_modifier(months) / design.food_modifier(0) for months in (0, 6, 12, 18, 24)]
    assert shares == pytest.approx([1.0, 0.8, 0.65, 0.5, 0.4])
    # staples move the other way (the farm trade-off): less crop for the market while the store is low, more while it is
    # full, by -0.40 x the Province Food line; the farms' ai_construct_weight takes the line out (pp_stored_food_staple_line)
    assert design.staple_modifier(0) < 1.0 == design.staple_modifier(12) < design.staple_modifier(24)
    for months in range(25):
        assert design.staple_line(months) == pytest.approx(-0.40 * design.food_line(months)), months


def test_tavern_fills_the_store_from_below_and_follows_the_victuals_price(design: store_lever.Design) -> None:
    fill = [design.tavern_fill(price) for price in PRICES]
    assert fill == sorted(fill, reverse=True)                                  # dearer victuals: fills less
    assert 5.0 <= design.tavern_fill(VICTUALS) <= 9.0                          # the fallback: well below the pivot
    assert design.tavern_fill(2.0) < design.pivot                              # never fills into the Full Stores range
    assert design.tavern_fill(4.5) == 0.0                                      # too dear for a merely empty store
    assert design.tavern_profit(0, 6.0, starving=True) > 0                     # but a starving province still buys


def test_grange_packs_a_full_store_and_never_a_lean_one(design: store_lever.Design) -> None:
    dig = [design.grange_dig(price) for price in PRICES]
    assert dig == sorted(dig, reverse=True)                                    # dearer victuals: packs deeper
    # 2026-10-03: only a really full store at base victuals (Full Stores stops growing at 24 months, so the break-even
    # sits just under it), about 14 months deeper per gold down to the pivot, never below victuals 2.86. Dear victuals
    # must reach the 14-19 month stores the farms leave alone (farm store bonus below 14; Mini World run 5).
    assert 21.5 <= design.grange_dig(3.0) <= 22.5
    assert 14.5 <= design.grange_dig(3.5) <= 15.5
    assert 11.0 <= design.grange_dig(4.0) <= 12.5
    assert design.grange_dig(2.8) == store_lever.CAP_MONTHS
    # its Surplus Sales are gone well above an empty store, and without them packing does not pay at any victuals
    # price the game shows (10 = more than three times the default)
    sales_end = design.pivot + 12 / design.sales_low
    assert sales_end >= 6 and design.sales_modifier(sales_end) == pytest.approx(0.0, abs=1e-9)
    assert design.grange_dig(10.0) >= sales_end - 0.01
    assert design.grange_profit(0, 10.0) < 0
    # a starving province packs nothing, whatever victuals cost and however efficient the country is
    assert design.grange_profit(0, 20.0, starving=True, efficiency=1.0) == -design.grange_fixed


def test_tavern_and_grange_never_pay_at_the_same_store(design: store_lever.Design) -> None:
    for price in PRICES:
        assert design.grange_dig(price) - design.tavern_fill(price) >= 4.0, price          # a quiet band between them
    # with high production efficiency both would pay at once; a staffed Tavern takes the Grange's Surplus Sales away
    assert design.tavern_fill(VICTUALS, efficiency=0.5) > design.grange_dig(VICTUALS, efficiency=0.5)
    for months in range(25):
        assert design.grange_profit(months, VICTUALS, staffed_taverns=1.0, efficiency=0.5) < 0, months


def test_ai_builds_a_new_grange_only_at_a_well_filled_store(design: store_lever.Design) -> None:
    # the gate opens just above the pivot; the weight's price line (next test) decides where above it
    threshold = _margin_threshold()
    opens = next(months for months in range(25) if design.grange_gate_margin(months) >= threshold)
    assert 12 < opens <= 14
    assert design.grange_gate_margin(12) < threshold


def test_grange_ai_weight_follows_its_break_even(design: store_lever.Design) -> None:
    """The Grange's ai_construct_weight vetoes a new Grange below its break-even store at today's victuals price plus
    a month (2026-10-03): the line it writes must be the design's grange_dig."""
    text = (ROOT / "blueprints/accepted/buildings/grange.yml").read_text(encoding="utf-8-sig")
    m = re.search(r'value = ([\d.]+) subtract = \{ value = "market\.market_price\(goods:victuals\)" multiply = ([\d.]+)'
                  r' max = ([\d.]+) \} subtract = pp_location_stored_months min = 0 max = 1 multiply = 10000', text)
    assert m, "the Grange weight's break-even veto"
    intercept, slope, cap = float(m.group(1)), float(m.group(2)), float(m.group(3))

    def line(price: float) -> float:
        return intercept - min(slope * price, cap) - 1.0

    for price in (3.0, 3.25, 3.5):
        assert abs(line(price) - design.grange_dig(price)) < 0.15, price
    # never below the pivot: at dear victuals the Grange stops just under 12 months, the veto at the pivot
    for price in (4.0, 4.5):
        assert line(price) == pytest.approx(design.pivot) and abs(line(price) - design.grange_dig(price)) < 1.0, price
    assert "pp_location_province_food_balance <= 0" in text
    # the build gate itself still opens below that line, so the weight decides where (gate = if, weight = where)
    threshold = _margin_threshold()
    opens = next(months for months in range(25) if design.grange_gate_margin(months) >= threshold)
    assert opens <= line(6.0) + 1.0
