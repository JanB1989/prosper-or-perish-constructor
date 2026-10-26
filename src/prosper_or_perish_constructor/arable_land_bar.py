"""The Arable Land bar of the location view (2026-10-26, Jan; view only).

The engine compares every person of a location with its population capacity (Arable Land), so the vanilla gauge mixes
land with housing: buildings and town ranks add capacity for the people they employ or house. This bar shows the land
model's capacity side (2026-10-26, Jan: first nail the capacity, the population comes later; the land-vs-use versions
before were too busy):

- the bar's length is everything that adds capacity: natural land (green; every capacity row that is neither an
  improvement, a building's land or housing), improvements (blue) and housing from buildings and the town rank
  (purple); the land farms and reserved grounds take is laid over it from the right (brown). What stays clear is the
  location's Arable Land, the engine's capacity.
- under it the same as an equation of colour swatches and numbers; the words and the room for improvements are in the
  tooltip. The land-use values (subsistence peasants, used, scale) stay in the script values for the next step.

Everything is read from the files the game loads, in finalize (after the footprint and the World Builder caps):

- building land and housing: each building type's ``raw_modifier`` ``local_population_capacity`` (vanilla blocks plus
  the mod's injects; a REPLACE starts over). Farms (land takers with a ``pp_levels_<farm>`` counter) and improvements
  (``pp_wb_levels_<key>``) are read through their counters, which the engine scales by input fulfilment as it scales
  the capacity row; buildings without a counter by whole levels.
- room for improvements: per cap (one building, or the members of a shared cap) the cap's equation clamped like the
  members' caps, minus the standing levels, times the land per level of the best member whose ``location_potential``
  the location passes (geography and culture gates; country gates and research are ignored: the theoretical maximum).
- town rank housing: the ranks' ``rank_modifier`` capacity (vanilla plus the mod's injects).
- the capacity multiplier: (1 + local % + the owner's global %) x (1 + total %), as the engine computes it.

The natural land is the remainder: flat capacity - improvements - housing + the land farms and reserved grounds take.
It also holds small rows the bar does not split off (vanilla buildings' staffing-scaled capacity, events).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from eu5gameparser.clausewitz.parser import parse_file
from eu5gameparser.clausewitz.syntax import CList

SCRIPT_VALUES = Path("in_game/common/script_values/pp_arable_land_bar.txt")
LOCALIZATION = Path("main_menu/localization/english/pp_arable_land_bar_l_english.yml")
BUILDING_TYPES = Path("in_game/common/building_types")
CAPS = Path("in_game/common/script_values/pp_wb_building_caps.txt")
RANKS = Path("in_game/common/location_ranks")
CAPACITY = "local_population_capacity"
FARM_COUNTER = "pp_levels_"
IMPROVEMENT_COUNTER = "pp_wb_levels_"
_REPLACE = ("REPLACE_OR_CREATE:", "TRY_REPLACE:", "REPLACE:")
_INJECT = ("INJECT_OR_CREATE:", "TRY_INJECT:", "INJECT:")
_LOC = "LocationView.GetLocation"


@dataclass
class Building:
    key: str
    land: float = 0.0                       # raw_modifier local_population_capacity per level
    counters: set[str] = field(default_factory=set)
    max_levels: str | None = None
    potential: str | None = None            # location_potential, rendered as trigger text

    @property
    def counter(self) -> str | None:
        """The building's own level counter, if it carries exactly one of the farm or improvement kind."""
        own = sorted(c for c in self.counters if c.startswith((FARM_COUNTER, IMPROVEMENT_COUNTER)))
        return own[0] if len(own) == 1 else None


@dataclass
class CapUnit:
    equation: str                           # the script value the members' caps add
    limit: float | None                     # the members' level clamp (the World Builder level limit)
    members: list[Building]


@dataclass
class Model:
    improvements: list[Building]
    farms: list[Building]
    reserved: list[Building]
    housing: list[Building]
    units: list[CapUnit]
    rank_housing: dict[str, float]


def _bare(key: str) -> tuple[str, str]:
    for prefix in _REPLACE:
        if key.startswith(prefix):
            return "replace", key[len(prefix):]
    for prefix in _INJECT:
        if key.startswith(prefix):
            return "inject", key[len(prefix):]
    return "define", key


def _block_end(text: str, open_brace: int) -> int:
    """Index of the brace closing ``text[open_brace]``; braces in comments and strings are ignored."""
    depth, quoted, comment = 0, False, False
    for i in range(open_brace, len(text)):
        c = text[i]
        if comment:
            comment = c != "\n"
        elif quoted:
            quoted = c != '"'
        elif c == "#":
            comment = True
        elif c == '"':
            quoted = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i
    raise ValueError("unbalanced block")


_TOP_BLOCK = re.compile(r"(?m)^([\w:]+)[ \t]*=[ \t]*\{")
_POTENTIAL = re.compile(r"(?m)^[ \t]*location_potential[ \t]*=[ \t]*\{")


def potentials(text: str) -> dict[str, str]:
    """building key -> its location_potential as one line of trigger text (the file text itself: the game-data
    parser does not keep ``?=``)."""
    found: dict[str, str] = {}
    for match in _TOP_BLOCK.finditer(text):
        end = _block_end(text, match.end() - 1)
        inner = _POTENTIAL.search(text, match.end(), end)
        if inner:
            body = text[inner.end():_block_end(text, inner.end() - 1)]
            body = re.sub(r"#[^\n]*", "", body)
            found[_bare(match.group(1))[1]] = " ".join(body.split())
    return found


def _read_buildings(paths: list[Path], buildings: dict[str, Building]) -> None:
    for path in paths:
        gates = potentials(path.read_text(encoding="utf-8-sig"))
        for entry in parse_file(path).entries:
            if not isinstance(entry.value, CList):
                continue
            kind, key = _bare(str(entry.key))
            if kind != "inject" or key not in buildings:
                buildings[key] = Building(key)
            building = buildings[key]
            for block in entry.value.values("raw_modifier"):
                if not isinstance(block, CList):
                    continue
                for item in block.entries:
                    name = str(item.key)
                    if name == CAPACITY and isinstance(item.value, (int, float)):
                        building.land += float(item.value)
                    elif name.startswith((FARM_COUNTER, IMPROVEMENT_COUNTER)) and item.value == 1:
                        building.counters.add(name)
            levels = entry.value.first("max_levels")
            if isinstance(levels, str):
                building.max_levels = levels
            if key in gates:
                building.potential = gates[key]


def buildings(mod_root: Path, vanilla_game: Path | None) -> dict[str, Building]:
    """Every building type the game loads, vanilla first, then the mod's files in load order."""
    found: dict[str, Building] = {}
    if vanilla_game is not None:
        _read_buildings(sorted((vanilla_game / "in_game/common/building_types").glob("*.txt")), found)
    _read_buildings(sorted((mod_root / BUILDING_TYPES).glob("*.txt")), found)
    return found


_CAP_EQUATION = re.compile(r"^\s*(?:add|value)\s*=\s*(pp_wb_cap_\w+)\s*$", re.M)
_CAP_LIMIT = re.compile(r'max\s*=\s*\{\s*desc\s*=\s*"BUILDING_LEVEL_WB_MAXIMUM"\s*value\s*=\s*([\d.]+)')


def _cap_blocks(text: str) -> dict[str, str]:
    blocks: dict[str, str] = {}
    for match in re.finditer(r"(?m)^(pp_wb_cap_\w+)\s*=\s*\{", text):
        depth, i = 0, match.end() - 1
        for i in range(match.end() - 1, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    break
        blocks[match.group(1)] = text[match.end():i]
    return blocks


def cap_units(mod_root: Path, improvements: list[Building]) -> list[CapUnit]:
    """Group the improvement buildings by the equation their caps add (one building, or a shared cap's members)."""
    path = mod_root / CAPS
    blocks = _cap_blocks(path.read_text(encoding="utf-8-sig")) if path.is_file() else {}
    units: dict[str, CapUnit] = {}
    for building in improvements:
        body = blocks.get(building.max_levels or "", "")
        equation = _CAP_EQUATION.search(body)
        name = equation.group(1) if equation else building.max_levels
        limit = _CAP_LIMIT.search(body)
        unit = units.setdefault(name, CapUnit(name, None, []))
        if limit:
            unit.limit = max(unit.limit or 0.0, float(limit.group(1)))
        unit.members.append(building)
    return sorted(units.values(), key=lambda unit: unit.equation)


def rank_housing(mod_root: Path, vanilla_game: Path | None) -> dict[str, float]:
    """Capacity of each location rank's rank_modifier (vanilla plus the mod's injects)."""
    ranks: dict[str, float] = {}
    paths = sorted((vanilla_game / "in_game/common/location_ranks").glob("*.txt")) if vanilla_game is not None else []
    for path in paths + sorted((mod_root / RANKS).glob("*.txt")):
        for entry in parse_file(path).entries:
            if not isinstance(entry.value, CList):
                continue
            kind, key = _bare(str(entry.key))
            if kind != "inject":
                ranks[key] = 0.0
            for block in entry.value.values("rank_modifier"):
                if isinstance(block, CList):
                    for item in block.entries:
                        if str(item.key) == CAPACITY and isinstance(item.value, (int, float)):
                            ranks[key] = ranks.get(key, 0.0) + float(item.value)
    return {rank: value for rank, value in sorted(ranks.items()) if value}


def model(mod_root: Path, vanilla_game: Path | None) -> Model:
    found = buildings(mod_root, vanilla_game)
    improvements = [b for b in found.values() if (b.max_levels or "").startswith("pp_wb_cap_") and b.land > 0]
    names = {b.key for b in improvements}
    farms = [b for b in found.values() if b.land < 0 and any(c.startswith(FARM_COUNTER) for c in b.counters)]
    reserved = [b for b in found.values() if b.land < 0 and b not in farms]
    housing = [b for b in found.values() if b.land > 0 and b.key not in names]
    key = lambda b: b.key  # noqa: E731
    return Model(sorted(improvements, key=key), sorted(farms, key=key), sorted(reserved, key=key),
                 sorted(housing, key=key), cap_units(mod_root, improvements), rank_housing(mod_root, vanilla_game))


def _num(value: float) -> str:
    return f"{value:.5f}".rstrip("0").rstrip(".")


def _level(key: str) -> str:
    return f'"location_building_level(building_type:{key})"'


def _land_sum(name: str, members: list[Building], comment: str, counters: bool) -> str:
    """Sum of land per level x levels; a counter (scaled by input fulfilment like the capacity row) where it has one."""
    lines = [f"# {comment}", f"{name} = {{", "\tvalue = 0"]
    for b in members:
        land = _num(abs(b.land))
        if counters and b.counter:
            lines.append(f"\tadd = {{ value = modifier:{b.counter} multiply = {land} }}")
        else:
            lines.append(f"\tif = {{ limit = {{ has_building = building_type:{b.key} }} add = {{ value = {_level(b.key)} multiply = {land} }} }}")
    lines.append("}")
    return "\n".join(lines)


def _unit_name(unit: CapUnit) -> str:
    return "pp_land_bar_room_" + unit.equation.removeprefix("pp_wb_cap_")


def _room(unit: CapUnit) -> str:
    """Land the unit's improvements could still add: (clamped cap - standing levels) x the best member's land."""
    name = _unit_name(unit)
    lines = [f"{name} = {{", f"\tvalue = {unit.equation}"]
    if unit.limit is not None:
        lines.append(f"\tmax = {_num(unit.limit)}")
    for b in unit.members:
        lines.append(f"\tif = {{ limit = {{ has_building = building_type:{b.key} }} subtract = {_level(b.key)} }}")
    lines.append("\tmin = 0")
    lines.append(f"\tmultiply = {name}_land")
    lines.append("}")
    land = [f"{name}_land = {{", "\tvalue = 0"]
    first = True
    for b in sorted(unit.members, key=lambda b: (-b.land, b.key)):   # the best member the location allows
        if b.potential:
            land.append(f"\t{'if' if first else 'else_if'} = {{ limit = {{ {b.potential} }} value = {_num(b.land)} }}")
            first = False
        else:
            land.append(f"\tvalue = {_num(b.land)}" if first else f"\telse = {{ value = {_num(b.land)} }}")
            break
    land.append("}")
    return "\n".join(lines) + "\n" + "\n".join(land)


def _rank_lines(ranks: dict[str, float]) -> str:
    lines = ["# Housing of the town ranks (rank_modifier capacity, vanilla plus the mod's injects)",
             "pp_land_bar_rank_housing_flat = {", "\tvalue = 0"]
    branch = "if"
    for rank, value in ranks.items():
        lines.append(f"\t{branch} = {{ limit = {{ location_rank = location_rank:{rank} }} value = {_num(value)} }}")
        branch = "else_if"
    lines.append("}")
    return "\n".join(lines)


_FIXED = """# Capacity multiplier as the engine applies it: (1 + local % + the owner's global %) x (1 + total %)
pp_land_bar_multiplier = {
	value = 1
	add = modifier:local_population_capacity_modifier
	if = { limit = { exists = owner } add = owner.modifier:global_population_capacity_modifier }
	multiply = { value = 1 add = modifier:total_population_capacity_modifier }
	min = 0
}

# Natural land: flat capacity without the improvements and the housing, with the land the farms and reserved grounds take
pp_land_bar_natural_flat = {
	value = modifier:local_population_capacity
	subtract = pp_land_bar_improvements_flat
	subtract = pp_land_bar_housing_flat
	subtract = pp_land_bar_rank_housing_flat
	add = pp_land_bar_farms_flat
	add = pp_land_bar_reserved_flat
	min = 0
}

# In thousands of people (the capacity multiplier applied; subsistence peasants are people already)
pp_land_bar_natural = { value = pp_land_bar_natural_flat multiply = pp_land_bar_multiplier }
pp_land_bar_improvements = { value = pp_land_bar_improvements_flat multiply = pp_land_bar_multiplier }
pp_land_bar_room = { value = pp_land_bar_room_flat multiply = pp_land_bar_multiplier }
pp_land_bar_farms = { value = pp_land_bar_farms_flat multiply = pp_land_bar_multiplier }
pp_land_bar_reserved = { value = pp_land_bar_reserved_flat multiply = pp_land_bar_multiplier }
pp_land_bar_housing = {
	value = pp_land_bar_housing_flat
	add = pp_land_bar_rank_housing_flat
	multiply = pp_land_bar_multiplier
}
pp_land_bar_subsistence = { value = "unemployed_pops_of_pop_type_in_location(pop_type:peasants)" }

pp_land_bar_land = { value = pp_land_bar_natural add = pp_land_bar_improvements }
pp_land_bar_max = { value = pp_land_bar_land add = pp_land_bar_room }
pp_land_bar_taken = { value = pp_land_bar_farms add = pp_land_bar_reserved }
pp_land_bar_used = { value = pp_land_bar_taken add = pp_land_bar_subsistence }
pp_land_bar_unused = { value = pp_land_bar_land subtract = pp_land_bar_used min = 0 }
pp_land_bar_overused = { value = pp_land_bar_used subtract = pp_land_bar_land min = 0 }
pp_land_bar_used_percent = {
	value = 0
	if = { limit = { pp_land_bar_land > 0 } value = pp_land_bar_used divide = pp_land_bar_land multiply = 100 }
}

# Bar fractions (0..1) on one scale for both rows: the larger of the maximum land and the land in use
pp_land_bar_scale = {
	value = pp_land_bar_max
	if = { limit = { pp_land_bar_used > pp_land_bar_max } value = pp_land_bar_used }
	min = 0.001
}
pp_land_bar_f_land = { value = pp_land_bar_land divide = pp_land_bar_scale }
pp_land_bar_f_max = { value = pp_land_bar_max divide = pp_land_bar_scale }
pp_land_bar_f_used = { value = pp_land_bar_used divide = pp_land_bar_scale }
pp_land_bar_f_used_within = { value = pp_land_bar_f_used max = pp_land_bar_f_land }

# The capacity bar: what adds capacity (natural, improvements, housing) and the farms' land laid over it from the right
pp_land_bar_positive = { value = pp_land_bar_land add = pp_land_bar_housing }
pp_land_bar_capacity = { value = pp_land_bar_positive subtract = pp_land_bar_taken }
pp_land_bar_multiplier_percent = { value = pp_land_bar_multiplier subtract = 1 multiply = 100 }
pp_land_bar_capacity_scale = {
	value = pp_land_bar_positive
	if = { limit = { pp_land_bar_taken > pp_land_bar_positive } value = pp_land_bar_taken }
	min = 0.001
}
pp_land_bar_f_natural = { value = pp_land_bar_natural divide = pp_land_bar_capacity_scale }
pp_land_bar_f_natural_improvements = { value = pp_land_bar_land divide = pp_land_bar_capacity_scale }
pp_land_bar_f_positive = { value = pp_land_bar_positive divide = pp_land_bar_capacity_scale }
pp_land_bar_f_taken = { value = pp_land_bar_taken divide = pp_land_bar_capacity_scale }
"""

HEADER = (
    "﻿# Generated by ppc finalize (arable_land_bar.py); do not edit by hand.\n"
    "# Location scope, read only by the Arable Land bar of the location view: the land model in thousands of people\n"
    "# (land = natural + improvements; use = farms + reserved grounds + subsistence peasants).\n"
)


def render_script_values(m: Model) -> str:
    parts = [
        HEADER,
        _FIXED,
        _land_sum("pp_land_bar_improvements_flat", m.improvements,
                  "Land the standing improvements add (raw_modifier capacity per level)", counters=True),
        _land_sum("pp_land_bar_farms_flat", m.farms, "Land the farms take (raw_modifier capacity per level)", counters=True),
        _land_sum("pp_land_bar_reserved_flat", m.reserved,
                  "Land the reserved grounds take (buildings with negative capacity and no farm counter)", counters=False),
        _land_sum("pp_land_bar_housing_flat", m.housing,
                  "Housing the other buildings add (building footprint and other raw_modifier capacity)", counters=False),
        _rank_lines(m.rank_housing),
        "# Room for improvements: per cap, the land its improvements could still add\n"
        "pp_land_bar_room_flat = {\n\tvalue = 0\n"
        + "".join(f"\tadd = {_unit_name(unit)}\n" for unit in m.units) + "}",
        *(_room(unit) for unit in m.units),
    ]
    return "\n\n".join(part.strip("\n") if i else part.rstrip("\n") for i, part in enumerate(parts)) + "\n"


def _v(name: str, digits: int = 0) -> str:
    """A script value of the bar in text (thousands of people, shown like the game's 295K)."""
    return f"[LocationView.GetLocation.MakeScope.ScriptValue('{name}')|{digits}]K"


LOC_TEXT = {
    "PP_LAND_BAR_TITLE": "[population_capacity|E]",
    "PP_LAND_BAR_TT": (
        "How this location's [population_capacity|E] is made up:\\n"
        f"Natural land (green): {_v('pp_land_bar_natural')}\\n"
        f"Improvements (blue): {_v('pp_land_bar_improvements')}\\n"
        f"Housing from buildings and the town rank (purple): {_v('pp_land_bar_housing')}\\n"
        f"Taken by farms (brown strip; the bar is dimmed above it): -{_v('pp_land_bar_taken')}\\n"
        f"= {_v('pp_land_bar_capacity')}, the bright part of the bar\\n\\n"
        "Every value includes this location's capacity modifiers "
        "([LocationView.GetLocation.MakeScope.ScriptValue('pp_land_bar_multiplier_percent')|+=0]%). "
        f"Improvements could still add {_v('pp_land_bar_room')}."
    ),
}


def render_localization() -> str:
    lines = ["﻿l_english:", "  # Generated by ppc finalize (arable_land_bar.py); the Arable Land bar of the location view"]
    lines += [f'  {key}: "{text}"' for key, text in LOC_TEXT.items()]
    return "\n".join(lines) + "\n"


# --- GUI ---------------------------------------------------------------------------------------------------------

# min/max state the 0..1 range: without them a progressbar reads 0..100 (in game 2026-10-26, the bars stayed slivers)
_BAR = ('progressbar = {{ size = {{ 100% 100% }} progresstexture = "gfx/interface/progressbars/{texture}.dds" '
        'noprogresstexture = "{empty}" texture_density = 2 spriteType = Corneredstretched spriteborder = {{ 12 0 }} '
        'min = 0 max = 1 value = {value} direction = horizontal{extra} }}')
_EMPTY = "gfx/interface/icons/unit_view/moral_bar_transparent.dds"
_BACK = "gfx/interface/progressbars/progress_black.dds"
TEXTURES = {"natural": "progress_bar_green_alt", "improvements": "progress_bar_blue_alt",
            "housing": "progress_bar_purple", "taken": "progress_bar_brown_alt", "dim": "progress_black"}


def _sv(name: str) -> str:
    return f"{_LOC}.MakeScope.ScriptValue('{name}')"


def _fraction(name: str) -> str:
    return f"FixedPointToFloat({_sv(name)})"


def _bar(texture: str, value: str, bottom: bool = False, extra: str = "") -> str:
    """A bar layer; ``value`` is a data expression, or a plain number (a full swatch)."""
    shown = value if value.replace(".", "").isdigit() else f'"[{value}]"'
    return _BAR.format(texture=TEXTURES[texture], empty=_BACK if bottom else _EMPTY, value=shown, extra=extra)


def _term(part: str, value: str, sign: str = "") -> str:
    """One term of the equation under the bar: its colour swatch and its value (raw text: numbers only)."""
    return (f'hbox = {{ spacing = 4 widget = {{ size = {{ 16 10 }} {_bar(part, "1", bottom=True)} }} '
            f'text_single = {{ raw_text = "{sign}{_v(value)}" fontsize = 14 }} }}')


def _op(symbol: str) -> str:
    return f'text_single = {{ raw_text = "{symbol}" fontsize = 14 alpha = 0.7 }}'


def gui_block(indent: str = "") -> str:
    """The Arable Land panel under the location view's scene: what the capacity is made of, as one bar.

    The bar's length is everything that adds capacity: natural land (green), improvements (blue) and housing from
    buildings and the town rank (purple). The farms' land is laid over it from the right (brown); what stays clear is
    the location's Arable Land. Under it the same as an equation of swatches and numbers; the words are in the tooltip.
    """
    stack = "\n".join([
        _bar("housing", _fraction("pp_land_bar_f_positive"), bottom=True),
        _bar("improvements", _fraction("pp_land_bar_f_natural_improvements")),
        _bar("natural", _fraction("pp_land_bar_f_natural")),
        # the farms' share dims the stack from the right, so every part stays visible under it
        _bar("dim", _fraction("pp_land_bar_f_taken"), extra=" invertprogress = yes alpha = 0.65"),
    ])
    strip = _bar("taken", _fraction("pp_land_bar_f_taken"), extra=" invertprogress = yes")
    bar = f"""widget = {{
	size = {{ 100% 15 }}
{_indent(stack, 1)}
}}
widget = {{
	size = {{ 100% 5 }}
	parentanchor = bottom
{_indent(strip, 1)}
}}"""
    equation = "\n".join([
        _term("natural", "pp_land_bar_natural"), _op("+"),
        _term("improvements", "pp_land_bar_improvements"), _op("+"),
        _term("housing", "pp_land_bar_housing"), _op("-"),
        _term("taken", "pp_land_bar_taken"), _op("="),
        f'text_single = {{ raw_text = "{_v("pp_land_bar_capacity")}" fontsize = 15 default_format = "#yellow_titles" }}',
    ])
    block = f"""# PP: the Arable Land bar (arable_land_bar.py): what adds capacity, the farms' land laid over it from the right
vbox = {{
	name = "pp_arable_land_bar"
	layoutpolicy_horizontal = expanding
	margin = {{ 12 6 }}
	spacing = 5
	background = {{ using = color_dark_blue_texture alpha = 0.85 }}
	tooltip = "PP_LAND_BAR_TT"

	hbox = {{
		layoutpolicy_horizontal = expanding
		spacing = 10
		text_single = {{ text = "PP_LAND_BAR_TITLE" default_format = "#yellow_titles" fontsize = 15 }}
		widget = {{
			layoutpolicy_horizontal = expanding
			size = {{ -1 21 }}
{_indent(bar, 3)}
		}}
	}}

	hbox = {{
		layoutpolicy_horizontal = expanding
		spacing = 8
		expand = {{}}
{_indent(equation, 2)}
	}}
}}"""
    return _indent(block, 0, indent)


def _indent(text: str, tabs: int, prefix: str = "") -> str:
    pad = prefix + "\t" * tabs
    return "\n".join(pad + line if line else line for line in text.splitlines())


_SCENE = "# SCENE\n"


def add_to_window(text: str) -> str:
    """Insert the panel right under the location view's scene (once)."""
    found = text.count(_SCENE)
    if found != 1:
        raise ValueError(f"location_window.gui: expected 1 scene anchor for the Arable Land bar, found {found}")
    anchor = text.index(_SCENE)
    start = text.index("widget = {", anchor)
    if text[anchor + len(_SCENE):start].strip():
        raise ValueError("location_window.gui: expected the scene widget right after the scene anchor")
    depth = 0
    for end in range(start, len(text)):
        if text[end] == "{":
            depth += 1
        elif text[end] == "}":
            depth -= 1
            if depth == 0:
                break
    indent = text[text.rfind("\n", 0, anchor) + 1:anchor]
    return text[:end + 1] + "\n\n" + gui_block(indent) + text[end + 1:]


@dataclass
class Result:
    counts: dict[str, int]
    changed: list[str]


def _write(path: Path, text: str) -> bool:
    if path.is_file() and path.read_text(encoding="utf-8") == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return True


def write(mod_root: Path, vanilla_game: Path | None) -> Result:
    """Write the bar's script values and localization (the window block is added by location_view.build_window)."""
    m = model(mod_root, vanilla_game)
    changed = [str(rel) for rel, text in ((SCRIPT_VALUES, render_script_values(m)), (LOCALIZATION, render_localization()))
               if _write(mod_root / rel, text)]
    counts = {"improvements": len(m.improvements), "caps": len(m.units), "farms": len(m.farms),
              "reserved grounds": len(m.reserved), "housing buildings": len(m.housing), "ranks": len(m.rank_housing)}
    return Result(counts, changed)
