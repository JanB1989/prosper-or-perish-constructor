"""Ship upkeep = the value of the goods the ship consumes (2026-10-11, Jan).

The engine prices a ship's monthly upkeep as the category's gold price (prices/02_units.txt: heavy 1, light, galley and
transport 0.5) x 2^(age index of the ship type) (NUnit.BASE_SCALE_SHIP_DOUBLE_PER_AGE, an integer: 0 makes ships free,
no other growth rate is possible), then x the goods cost at the home market (its maintenance_demand basket's prices
against their defaults) and x maintenance efficiency (private notes military_transport_140.md). The basket is only
market demand: an age-6 three-decker charged 32 for goods worth ~11.5, an age-1 heavy ship 1 for ~2.5.

A unit-specific price `<unit_type>_maintenance` adds to its category's price before the age doubling (vanilla
prices/02_units.txt: "Base 0.5 - 0.3 = 0.2"). This pass writes one per navy unit type so that
(category gold + add) x 2^age index = its basket at default market prices; the define stays 1. Sailors are untouched.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from eu5gameparser.clausewitz.parser import parse_file
from eu5gameparser.clausewitz.syntax import CList

MOD_FOLDER = "Prosper or Perish (Population Growth & Food Rework)"
OUTPUT = Path("in_game/common/prices/pp_ship_upkeep.txt")
DECIMALS = 5
_PREFIXES = ("TRY_REPLACE:", "REPLACE:", "INJECT:", "TRY_INJECT:", "REPLACE_OR_CREATE:")


@dataclass(frozen=True)
class Ship:
    unit: str
    category: str
    age: str
    age_index: int
    basket_key: str
    basket_value: float  # gold at default market prices
    category_gold: float
    add: float
    vanilla_entry: CList | None  # vanilla already prices this unit (replace it, keep its sailors)

    @property
    def scale(self) -> int:
        return 1 << self.age_index

    @property
    def old_base(self) -> float:
        own = _number(self.vanilla_entry.first("gold")) if self.vanilla_entry is not None else 0.0
        return (self.category_gold + own) * self.scale

    @property
    def new_base(self) -> float:
        return (self.category_gold + self.add) * self.scale


def _number(value: object) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0


def _strip(key: str) -> str:
    for prefix in _PREFIXES:
        if key.startswith(prefix):
            return key[len(prefix) :]
    return key


def _blocks(folder: Path) -> dict[str, CList]:
    out: dict[str, CList] = {}
    for path in sorted(folder.glob("*.txt")) if folder.is_dir() else []:
        for entry in parse_file(path).entries:
            if isinstance(entry.value, CList):
                out[_strip(entry.key)] = entry.value
    return out


def _vanilla_common(repo: Path, project: Path) -> Path:
    from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

    return Path(vanilla_root(repo, project)) / "game" / "in_game" / "common"


def plan(repo: Path, project: Path, prices: dict[str, float] | None = None) -> list[Ship]:
    """One entry per navy unit type, from vanilla unit types, ages, goods demands and unit prices."""
    from prosper_or_perish_constructor import production_labour

    common = _vanilla_common(repo, project)
    mod_common = Path(repo) / "mod" / MOD_FOLDER / "in_game" / "common"
    prices = prices if prices is not None else production_labour.load_prices(repo, project)
    units = _blocks(common / "unit_types")
    categories = _blocks(common / "unit_categories")
    demands = {**_blocks(common / "goods_demand"), **_blocks(mod_common / "goods_demand")}
    vanilla_prices = _blocks(common / "prices")
    ages = sorted(_blocks(common / "age").items(), key=lambda item: _number(item[1].first("year")))
    age_index = {name: i for i, (name, _) in enumerate(ages)}

    def field(unit: str, key: str, seen: tuple[str, ...] = ()) -> object:
        body = units[unit]
        value = body.first(key)
        parent = body.first("copy_from")
        if value is None and parent is not None and str(parent) in units and str(parent) not in seen:
            return field(str(parent), key, (*seen, unit))
        return value

    ships: list[Ship] = []
    for unit in units:
        category = str(field(unit, "category") or "")
        if not category.startswith("navy_"):
            continue
        basket_key = str(field(unit, "maintenance_demand") or categories[category].first("maintenance_demand"))
        age = str(field(unit, "age") or "")
        if basket_key not in demands or age not in age_index:
            raise ValueError(f"{unit}: basket {basket_key!r} or age {age!r} not found")
        basket = demands[basket_key]
        missing = [e.key for e in basket.entries if e.key != "category" and e.key not in prices]
        if missing:
            raise ValueError(f"{unit}: no default price for {missing}")
        value = sum(_number(e.value) * prices[e.key] for e in basket.entries if e.key != "category")
        category_gold = _number(vanilla_prices[f"{category}_maintenance"].first("gold"))
        scale = 1 << age_index[age]
        add = round(value / scale - category_gold, DECIMALS)
        ships.append(
            Ship(
                unit=unit,
                category=category,
                age=age,
                age_index=age_index[age],
                basket_key=basket_key,
                basket_value=value,
                category_gold=category_gold,
                add=add,
                vanilla_entry=vanilla_prices.get(f"{unit}_maintenance"),
            )
        )
    return ships


def render(ships: list[Ship]) -> str:
    lines = [
        "# GENERATED by `uv run ppc ship-upkeep apply` (src/prosper_or_perish_constructor/ship_upkeep.py); do not edit.",
        "# Ship upkeep = the value of its maintenance goods at default market prices: each add makes",
        "# (category gold + add) x 2^(age index) equal that value (NUnit.BASE_SCALE_SHIP_DOUBLE_PER_AGE stays 1).",
        "",
    ]
    for ship in sorted(ships, key=lambda s: (s.category, s.age_index, s.unit)):
        prefix = "TRY_REPLACE:" if ship.vanilla_entry is not None else ""
        sailors = _number(ship.vanilla_entry.first("sailors")) if ship.vanilla_entry is not None else 0.0
        lines += [
            f"# {ship.category} {ship.age}: {ship.basket_key} {ship.basket_value:.2f} gold (was {ship.old_base:g})",
            f"{prefix}{ship.unit}_maintenance = {{",
            f"\tgold = {ship.add:.{DECIMALS}f}".rstrip("0").rstrip("."),
            f"\tsailors = {sailors:g}",
            "}",
        ]
    return "\n".join(lines) + "\n"


def apply(repo: Path, project: Path, *, write: bool = True) -> tuple[list[Ship], bool]:
    """Returns the plan and whether the file was (or would be) changed."""
    ships = plan(repo, project)
    path = Path(repo) / "mod" / MOD_FOLDER / OUTPUT
    text = render(ships)
    current = path.read_text(encoding="utf-8-sig") if path.exists() else None
    changed = current != text
    if write and changed:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8-sig")
    return ships, changed
