"""The store lever's numbers, read from the mod's sources (2026-10-02).

The province store moves three goods outputs through the Low Stores / Full Stores modifiers (``stored_food.py``,
``[stored_food.low]`` / ``[stored_food.full]`` in constructor.toml): Province Food (worth more while the store is low,
less while it is full), the staples (more for the market above the pivot) and the Grange's Surplus Sales. Every maker
of Province Food stops where its own recipe stops paying, so the store rests there:

* the Tavern (``pp_tavern_serve_victuals``): 24 Province Food from 0.8 victuals; it fills the store up to the months
  where 24 x 0.10 x (1 + Province Food output) = victuals + labour + offset;
* the Cookshop: the same, with its staples as the cost;
* the farms' Provisioning: always on, the modifier scales what it yields;
* the Grange (``pp_grange_surplus_sales`` + Haulage): takes 24 food per staffed level and packs victuals; its Surplus
  Sales grow above the pivot and are gone well above an empty store, and a staffed Tavern in the same location takes
  them away, so the two never pass the same food round in a circle;
* a starving province (``province_starving``) makes no victuals and pays double for Province Food.

``load_design`` reads all of it from constructor.toml, the accepted Tavern and Grange blueprints and the mod's
``province_starving`` modifier, so the simulator (tools/province_store_sim.py), the start-food validator
(worldbuilder/food_sim.py) and the tests follow the mod. Prices are the floors: Province Food 0.10, dummy goods and
labour 1 gold.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FOOD_PRICE = 0.10          # Province Food at its floor (20 % of 0.5)
CAP_MONTHS = 24.0          # NEconomy.GROWTH_FROM_FOOD_MULTIPLIER_MAX years

FOOD_KEY = "local_local_food_output_modifier"
SALES_KEY = "local_province_food_sales_output_modifier"
VICTUALS_KEY = "local_victuals_output_modifier"
STAPLE_KEY = "staple_output"

TAVERN_BLUEPRINT = Path("blueprints/accepted/buildings/tavern.yml")
GRANGE_BLUEPRINT = Path("blueprints/accepted/buildings/grange.yml")
STARVING_FILE = Path("main_menu/common/static_modifiers/pp_location_modifier_adjustments.txt")
MOD_GLOB = "Prosper or Perish (Population*"


@dataclass(frozen=True)
class Design:
    pivot: float             # stored months where neither Low Stores nor Full Stores is applied
    food_low: float          # Province Food output per year below the pivot (+)
    food_full: float         # ... per year above (-)
    staple_low: float
    staple_full: float
    sales_low: float         # Surplus Sales output per year below the pivot (-)
    sales_full: float
    tavern_victuals: float
    tavern_food: float
    tavern_fixed: float      # labour + offset per level
    tavern_sales_cut: float  # Surplus Sales output per staffed Tavern level in the location (-)
    grange_victuals: float
    grange_food: float       # food a staffed level takes
    grange_sales: float
    grange_fixed: float      # labour + offset per level (Haulage + Surplus Sales)
    grange_gate_cost: float  # the Surplus Sales method's own offset: the AI gate margin is sales x modifier / this
    starving_victuals: float # victuals output modifier of a starving province (-)
    starving_food: float     # Province Food output modifier of a starving province (+)

    # ---- modifiers at a store
    def sizes(self, months: float) -> tuple[float, float]:
        """(Low Stores size, Full Stores size) at ``months`` stored (capped at 24)."""
        months = min(CAP_MONTHS, max(0.0, months))
        return max(0.0, self.pivot - months) / 12.0, max(0.0, months - self.pivot) / 12.0

    def food_modifier(self, months: float, starving: bool = False, efficiency: float = 0.0) -> float:
        """Province Food output multiplier (1 at the pivot)."""
        low, full = self.sizes(months)
        return max(0.0, 1.0 + efficiency + self.food_low * low + self.food_full * full
                   + (self.starving_food if starving else 0.0))

    def staple_modifier(self, months: float, land: float = 0.0, efficiency: float = 0.0) -> float:
        low, full = self.sizes(months)
        return max(0.0, 1.0 + land + efficiency + self.staple_low * low + self.staple_full * full)

    def sales_modifier(self, months: float, staffed_taverns: float = 0.0, efficiency: float = 0.0) -> float:
        low, full = self.sizes(months)
        return max(0.0, 1.0 + efficiency + self.sales_low * low + self.sales_full * full
                   + self.tavern_sales_cut * staffed_taverns)

    # ---- profit per level at floor prices
    def tavern_profit(self, months: float, victuals: float, starving: bool = False, efficiency: float = 0.0) -> float:
        return (self.tavern_food * FOOD_PRICE * self.food_modifier(months, starving, efficiency)
                - self.tavern_victuals * victuals - self.tavern_fixed)

    def grange_profit(self, months: float, victuals: float, starving: bool = False, staffed_taverns: float = 0.0,
                      efficiency: float = 0.0) -> float:
        packed = max(0.0, 1.0 + efficiency + (self.starving_victuals if starving else 0.0))
        return (self.grange_victuals * victuals * packed
                + self.grange_sales * self.sales_modifier(months, staffed_taverns, efficiency) - self.grange_fixed)

    def grange_gate_margin(self, months: float, efficiency: float = 0.0) -> float:
        """Revenue / cost of the Surplus Sales method, the margin the AI checks before it builds a new Grange."""
        return self.grange_sales * self.sales_modifier(months, 0.0, efficiency) / self.grange_gate_cost

    # ---- where the buildings stop (stored months)
    def tavern_fill(self, victuals: float, efficiency: float = 0.0) -> float:
        """The store a Tavern fills up to: it pays below this many months (0 = never, 24 = at every store)."""
        return _threshold(lambda m: self.tavern_profit(m, victuals, efficiency=efficiency), rising=False)

    def grange_dig(self, victuals: float, efficiency: float = 0.0) -> float:
        """The store a Grange packs down to: it pays above this many months (24 = never, 0 = at every store)."""
        return _threshold(lambda m: self.grange_profit(m, victuals, efficiency=efficiency), rising=True)

    def cookshop_fill(self, cost_share: float, efficiency: float = 0.0) -> float:
        """The store a Cookshop fills up to when its inputs cost ``cost_share`` of its revenue at the pivot."""
        return _threshold(lambda m: self.food_modifier(m, efficiency=efficiency) - cost_share, rising=False)


def _threshold(profit, *, rising: bool) -> float:
    """The stored months where ``profit`` crosses zero (it is monotone in the store); the range end when it never does."""
    lo, hi = 0.0, CAP_MONTHS
    at_lo, at_hi = profit(lo) > 0, profit(hi) > 0
    if at_lo == at_hi:
        if rising:
            return 0.0 if at_lo else CAP_MONTHS
        return CAP_MONTHS if at_lo else 0.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if (profit(mid) > 0) == at_lo:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _method(body: str, name: str) -> dict[str, float]:
    match = re.search(rf"\b{re.escape(name)}\s*=\s*\{{(.*?)\}}", body, re.S)
    if not match:
        raise ValueError(f"production method {name} not found")
    return {key: float(value) for key, value in re.findall(r"(\w+)\s*=\s*(-?[\d.]+)", match.group(1))}


def _modifier(body: str, key: str) -> float:
    match = re.search(rf"^\s*{re.escape(key)}\s*=\s*(-?[\d.]+)", body, re.M)
    return float(match.group(1)) if match else 0.0


def _starving(root: Path, key: str) -> float:
    mod = next((root / "mod").glob(MOD_GLOB))
    text = (mod / STARVING_FILE).read_text(encoding="utf-8-sig")
    block = text[text.index("province_starving"):]
    return _modifier(block[: block.index("\n}")], key)


def load_design(root: Path = ROOT) -> Design:
    raw = tomllib.loads((root / "constructor.toml").read_text(encoding="utf-8-sig"))["stored_food"]
    low, full = raw["low"], raw["full"]
    tavern = (root / TAVERN_BLUEPRINT).read_text(encoding="utf-8-sig")
    grange = (root / GRANGE_BLUEPRINT).read_text(encoding="utf-8-sig")
    serve = _method(tavern, "pp_tavern_serve_victuals")
    porters = _method(grange, "pp_grange_porters")
    sales = _method(grange, "pp_grange_surplus_sales")
    return Design(
        pivot=float(raw.get("pivot_months", 12)),
        food_low=float(low[FOOD_KEY]), food_full=float(full[FOOD_KEY]),
        staple_low=float(low.get(STAPLE_KEY, 0.0)), staple_full=float(full.get(STAPLE_KEY, 0.0)),
        sales_low=float(low[SALES_KEY]), sales_full=float(full[SALES_KEY]),
        tavern_victuals=serve["victuals"], tavern_food=serve["output"],
        tavern_fixed=serve.get("manual_labor", 0.0) + serve.get("offset", 0.0),
        tavern_sales_cut=_modifier(tavern, SALES_KEY),
        grange_victuals=porters["output"], grange_food=-_modifier(grange, "local_monthly_food"),
        grange_sales=sales["output"],
        grange_fixed=porters.get("manual_labor", 0.0) + porters.get("offset", 0.0) + sales.get("offset", 0.0),
        grange_gate_cost=sales.get("offset", 0.0),
        starving_victuals=_starving(root, VICTUALS_KEY),
        starving_food=_starving(root, FOOD_KEY),
    )
