"""Stockpile prices (branch stockpile-prices): in_game/common/goods/zz_pp_goods_stockpile_prices.txt from [stockpile_prices].

One line per good: its default market price x base_price_mult x its price_factor (the floor-pinned dummy goods in
keep_base_price stay out) and, for the goods in [stockpile_prices.pop_demand], a demand_multiply on every pop type.

The engine's price target is default price x a ratio of the market's demand, supply and stock, so the raise moves the
price level and every nominal income with it, never price / default: a good reaches its default price only with an
empty stock and supply = demand. The engine's brake on pop demand reads that same price / default and has no setting
per good or pop type, so a good's pop demand is tuned here, as a fixed factor.

An injected demand_multiply runs after the good's demand_add (the goods loader multiplies what is already there), and
this file loads last. `ppc stockpile apply` writes the file, `check` reports it off; ppc build prints it and a test
enforces it.
"""

from __future__ import annotations

from pathlib import Path
import tomllib
from typing import Any, Mapping

from eu5gameparser.clausewitz.parser import parse_file
from eu5gameparser.clausewitz.syntax import CList

from prosper_or_perish_constructor.production_labour import stockpile_price_raise
from prosper_or_perish_constructor.ship_upkeep import MOD_FOLDER, _number, _strip

OUTPUT = Path("in_game/common/goods/zz_pp_goods_stockpile_prices.txt")
GOODS_FOLDER = Path("in_game/common/goods")


def base_prices(repo: Path, project: Path) -> dict[str, float]:
    """default_market_price per good from the vanilla goods and the mod's, this file left out; later files win."""
    from prosper_or_perish_constructor.building_footprint import vanilla_files
    from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

    paths = [p for p in vanilla_files(Path(vanilla_root(repo, project)), GOODS_FOLDER) if p.name != "readme.txt"]
    folder = Path(repo) / "mod" / MOD_FOLDER / GOODS_FOLDER
    paths += [p for p in sorted(folder.glob("*.txt")) if p.name != OUTPUT.name]
    prices: dict[str, float] = {}
    for path in paths:
        for entry in parse_file(path).entries:
            value = entry.value.first("default_market_price") if isinstance(entry.value, CList) else None
            if value is not None:
                prices[_strip(entry.key)] = _number(value)
    return prices


def render(raw: Mapping[str, Any], prices: Mapping[str, float]) -> str:
    section = raw["stockpile_prices"]
    keep = {str(g) for g in section.get("keep_base_price", [])}
    factors = {str(g): float(v) for g, v in dict(section.get("price_factor") or {}).items()}
    pop_demand = {str(g): float(v) for g, v in dict(section.get("pop_demand") or {}).items()}
    raised = sorted(g for g in prices if g not in keep)
    for name, goods in (("price_factor", factors), ("pop_demand", pop_demand)):
        unknown = sorted(set(goods) - set(raised))
        if unknown:
            raise ValueError(f"[stockpile_prices.{name}] names goods without a raised price: {', '.join(unknown)}")
    lines = [
        "# Prosper or Perish - stockpile prices (branch stockpile-prices). Written by ppc stockpile apply from [stockpile_prices]",
        "# in constructor.toml; do not edit by hand.",
        f"# Every default_market_price x{float(section['base_price_mult']):g} (base_price_mult), the floor-pinned dummy goods "
        f"({', '.join(sorted(keep))}) excepted.",
        "# A market with supply = demand sits at the default price with an empty stock and lower the more months of stock it holds.",
        "# Loads last (zz_), so it wins over the full copies and pp_goods_adjustments.txt. The comment is the value before the raise",
        "# and the [stockpile_prices.price_factor] on top (oversupplied goods a little cheaper, undersupplied dearer).",
        "# demand_multiply: [stockpile_prices.pop_demand], the good's pop demand on every pop type.",
    ]
    for good in raised:
        base = prices[good]
        value = round(base * stockpile_price_raise(raw, good), 5)
        note = f"{base:g}" if good not in factors else f"{base:g} x {factors[good]:g}"
        demand = f" demand_multiply = {{ all = {pop_demand[good]:g} }}" if good in pop_demand else ""
        lines.append(f"TRY_INJECT:{good} = {{ default_market_price = {value:g}{demand} }} # {note}")
    return "\n".join(lines) + "\n"


def apply(repo: Path, project: Path, *, write: bool = True) -> tuple[int, bool]:
    """(goods in the file, whether it was or would be changed)."""
    raw = tomllib.loads(Path(project).read_text(encoding="utf-8-sig"))
    text = render(raw, base_prices(repo, project))
    path = Path(repo) / "mod" / MOD_FOLDER / OUTPUT
    changed = (path.read_text(encoding="utf-8-sig") if path.exists() else None) != text
    if changed and write:
        path.write_text(text, encoding="utf-8-sig")
    return sum(line.startswith("TRY_INJECT:") for line in text.splitlines()), changed
