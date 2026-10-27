"""The population and capacity bars of the location view (2026-10-27, Jan; view only).

Capacity model since 2026-10-27: total_population gives every person +1 capacity and unemployed_peasants takes it
back from the subsistence peasants, so the engine's capacity is everyone but the subsistence peasants (the townsfolk:
each brings their own room) plus the arable land left (the location's land and improvements, minus what the farms take).
The engine still compares the whole population with that capacity, so the panel shows exactly that, on one scale:

- Population: the townsfolk (neutral grey), then the subsistence peasants (yellow, one part with their whole number); the part
  of them beyond the capacity is marked over the yellow (a red tint with red edges), its number in the tooltip.
- Population capacity: the same townsfolk (grey: they cancel out), then the arable land left (green: the location's
  land and improvements after the farms), then past the end of the capacity the land the farms hold (a brownish
  green: the land is there, the farms take it; a gross bar with the capacity line as its net, 2026-10-27, Jan), then
  the land the improvements still buildable here could add (an empty slot: faint green in a green frame; striped like
  the farms it read alike, 2026-10-27).
- two thin lines across both bars at the engine's land state thresholds (2026-10-27, Jan): 10 % of the capacity (left
  of it abundant free land, which also needs fewer than 10,000 people) and the capacity (right of it overpopulation),
  labelled "10%" and "100%" above the bars.
- room for improvements: per improvement cap (one building, or the members of a shared cap) the cap clamped like the
  members' caps, minus the standing levels, times the land per level of the best member whose ``location_potential``
  the location passes (geography and culture gates; country gates and research are ignored: what the land allows).
- every part is as wide as its share of the common scale (data-bound pixel sizes on a fixed bar width) and carries
  its number; under the bars a legend of the
  colours and the land state the two bars make (the arable land chip with its strength: the engine's free land or
  overpopulation from population / capacity); the breakdown of the arable land and one line per land state (what it
  is, how it is defined) are in the tooltip.

Farm land and improvements are read from the building types the game loads (``raw_modifier``
``local_population_capacity`` per level, through the buildings' level counters, which the engine scales like the
capacity row). Every value includes the location's remaining capacity modifiers.
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
    units: list[CapUnit] = field(default_factory=list)


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
        blocks[match.group(1)] = text[match.end():_block_end(text, match.end() - 1)]
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


def model(mod_root: Path, vanilla_game: Path | None) -> Model:
    found = buildings(mod_root, vanilla_game)
    improvements = [b for b in found.values() if (b.max_levels or "").startswith("pp_wb_cap_") and b.land > 0]
    farms = [b for b in found.values() if b.land < 0 and any(c.startswith(FARM_COUNTER) for c in b.counters)]
    reserved = [b for b in found.values() if b.land < 0 and b not in farms]
    key = lambda b: b.key  # noqa: E731
    return Model(sorted(improvements, key=key), sorted(farms, key=key), sorted(reserved, key=key),
                 cap_units(mod_root, improvements))


def _num(value: float) -> str:
    return f"{value:.5f}".rstrip("0").rstrip(".")


def _level(key: str) -> str:
    return f'"location_building_level(building_type:{key})"'


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


_FIXED = """# Capacity multiplier as the engine applies it: (1 + local % + the owner's global %) x (1 + total %)
pp_land_bar_multiplier = {
	value = 1
	add = modifier:local_population_capacity_modifier
	# owner ?= (vanilla's form): `exists = owner` let a placeholder country through and logged a script error per view
	owner ?= { add = modifier:global_population_capacity_modifier }
	multiply = { value = 1 add = modifier:total_population_capacity_modifier }
	min = 0
}

# People, in thousands: the subsistence peasants live on the arable land, everyone else (the townsfolk) brings their
# own capacity (total_population +1 for every person, unemployed_peasants -1 for every subsistence peasant)
pp_land_bar_population = { value = population }
pp_land_bar_subsistence = { value = "unemployed_pops_of_pop_type_in_location(pop_type:peasants)" }
pp_land_bar_townsfolk = { value = pp_land_bar_population subtract = pp_land_bar_subsistence min = 0 }

# Flat capacity units: the arable land left is the capacity without the townsfolk's own; the farms (and reserved
# grounds) take land, the location's own land is what stays when the improvements and the farms are taken out again
pp_land_bar_left_flat = { value = modifier:local_population_capacity subtract = pp_land_bar_townsfolk }
pp_land_bar_taken_flat = { value = pp_land_bar_farms_flat add = pp_land_bar_reserved_flat }
pp_land_bar_natural_flat = {
	value = pp_land_bar_left_flat
	add = pp_land_bar_taken_flat
	subtract = pp_land_bar_improvements_flat
	min = 0
}

# In thousands of people (the capacity multiplier applied)
pp_land_bar_townsfolk_room = { value = pp_land_bar_townsfolk multiply = pp_land_bar_multiplier }
pp_land_bar_left = { value = pp_land_bar_left_flat multiply = pp_land_bar_multiplier }
pp_land_bar_left_shown = { value = pp_land_bar_left min = 0 }
pp_land_bar_farms = { value = pp_land_bar_taken_flat multiply = pp_land_bar_multiplier }
pp_land_bar_natural = { value = pp_land_bar_natural_flat multiply = pp_land_bar_multiplier }
pp_land_bar_improvements = { value = pp_land_bar_improvements_flat multiply = pp_land_bar_multiplier }
pp_land_bar_room = { value = pp_land_bar_room_flat multiply = pp_land_bar_multiplier }
# the land the farms hold, as far as there is land (farms beyond the location's land and improvements hold nothing more)
pp_land_bar_farms_shown = {
	value = pp_land_bar_left
	add = pp_land_bar_farms
	subtract = pp_land_bar_left_shown
	min = 0
}
pp_land_bar_capacity = { value = pp_land_bar_townsfolk_room add = pp_land_bar_left_shown }
pp_land_bar_percent = {
	value = 0
	if = { limit = { pp_land_bar_capacity > 0 } value = pp_land_bar_population divide = pp_land_bar_capacity multiply = 100 }
}

# Bar fractions (0..1) on one scale for both bars: the population, or the capacity with the farms' land and the room
# for improvements past its end
pp_land_bar_held = { value = pp_land_bar_capacity add = pp_land_bar_farms_shown }
pp_land_bar_scale_land = { value = pp_land_bar_held add = pp_land_bar_room }
pp_land_bar_scale = {
	value = pp_land_bar_scale_land
	if = { limit = { pp_land_bar_population > pp_land_bar_scale_land } value = pp_land_bar_population }
	min = 0.001
}
pp_land_bar_f_population = { value = pp_land_bar_population divide = pp_land_bar_scale }
pp_land_bar_f_within = { value = pp_land_bar_f_population max = pp_land_bar_f_capacity }
pp_land_bar_f_townsfolk = { value = pp_land_bar_townsfolk divide = pp_land_bar_scale }
pp_land_bar_f_townsfolk_room = { value = pp_land_bar_townsfolk_room divide = pp_land_bar_scale }
pp_land_bar_f_capacity = { value = pp_land_bar_capacity divide = pp_land_bar_scale }
pp_land_bar_f_held = { value = pp_land_bar_held divide = pp_land_bar_scale }
pp_land_bar_f_land = { value = pp_land_bar_scale_land divide = pp_land_bar_scale }
"""

HEADER = (
    "﻿# Generated by ppc finalize (arable_land_bar.py); do not edit by hand.\n"
    "# Location scope, read only by the population and capacity bars of the location view, in thousands of people:\n"
    "# capacity = the townsfolk's own room + the arable land left (land + improvements - farms).\n"
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
        "# Room for improvements: per cap, the land its improvements could still add\n"
        "pp_land_bar_room_flat = {\n\tvalue = 0\n"
        + "".join(f"\tadd = {_unit_name(unit)}\n" for unit in m.units) + "}",
        *(_room(unit) for unit in m.units),
    ]
    return "\n\n".join(part.strip("\n") if i else part.rstrip("\n") for i, part in enumerate(parts)) + "\n"


def _v(name: str, digits: int = 0) -> str:
    """A script value of the bars in text (thousands of people, shown like the game's 295K)."""
    return f"[LocationView.GetLocation.MakeScope.ScriptValue('{name}')|{digits}]K"


# The engine's land states in threshold order (location_status.land_chips draws the one that applies): key (its icon
# gfx/interface/icons/pp_arable_land/<key>.dds), concept, name, the chip's one-line definition
LAND_STATES = (
    ("abundant", "pp_abundant_free_land", "Abundant Arable Land", "PP_LAND_CHIP_ABUNDANT"),
    ("available", "pp_available_free_land", "Available Arable Land", "PP_LAND_CHIP_AVAILABLE"),
    ("overused", "pp_overused_arable_land", "Overused Arable Land", "PP_LAND_CHIP_OVERPOPULATION"),
)
STATE_ICONS = "gfx/interface/icons/pp_arable_land"
# Engine (EU5 1.4.4, location growth pass): abundant free land where the free share of the capacity is at least 0.9,
# i.e. the population at most this share of it (and fewer than 10,000 people); overpopulation beyond the capacity
ABUNDANT_SHARE = "0.1"

# The parts of the two bars as game concepts, each with a short Europedia entry (2026-10-27, Jan: every row label a
# link; texts short and technical, no values, no metaphors): key -> (texture under gfx/interface/icons, name, text)
CONCEPTS = Path("main_menu/common/game_concepts/pp_arable_land_bar.txt")
CONCEPT_TEXT = {
    "pp_townsfolk": ("location_icons/population", "Townsfolk",
                     "Everyone in a [location|e] except the [pp_subsistence_peasants|e]. Townsfolk do not use "
                     "[population_capacity|e]: in the calculation each townsperson adds 1 Arable Land and uses 1."),
    "pp_subsistence_peasants": ("location_icons/subsistence_agriculture", "Subsistence Peasants",
                                "[ShowPopTypeName('peasants')] without [employment|e]. Each uses 1 [population_capacity|e]."),
    "pp_location_land": ("location_icons/terrain", "Location's Land",
                         "[population_capacity|E] from a [location|e]'s [climate|e], [topography|e], [vegetation|e], "
                         "[ha1300_soil_type|e] and [ha1300_fertility|e], and from its [location_rank|e]."),
    "pp_land_improvements": ("modifier_types/total_population_capacity_modifier", "Land Improvements",
                             "[buildings|E] that add [population_capacity|e] to their [location|e]."),
    "pp_farm_land": ("trade_goods/icon_goods_wheat", "Farms",
                     "Each level of a farm [building|e] takes [population_capacity|e] from its [location|e]."),
}

LOC_TEXT = {
    "PP_LAND_BAR_POPULATION": "[population|E]",
    "PP_LAND_BAR_CAPACITY": "[population_capacity|E]",
    "PP_LAND_BAR_TOWNSFOLK": "[pp_townsfolk|e]",
    "PP_LAND_BAR_SUBSISTENCE": "[pp_subsistence_peasants|e]",
    "PP_LAND_BAR_LAND": "[Concept('population_capacity', 'Arable land left')|e]",
    "PP_LAND_BAR_FARMS": "[pp_farm_land|e]",
    "PP_LAND_BAR_ROOM": "[Concept('pp_land_improvements', 'Possible improvements')|e]",
    # the bars' tooltip (2026-10-27, Jan: lists, not prose; every row label a concept link)
    "PP_LAND_BAR_TT_TITLE": "Population and Arable Land",
    "PP_LAND_BAR_TT_TOTAL": "Total",
    "PP_LAND_BAR_TT_NATURAL": "[pp_location_land|e]",
    "PP_LAND_BAR_TT_IMPROVEMENTS": "[pp_land_improvements|e]",
    "PP_LAND_BAR_TT_OVER": "Over the [population_capacity|e]",
    # the land states, one line each (2026-10-27, Jan: what it is, how it is defined); the definitions are the chips'
    # own lines (pp_location_status_l_english.yml), so the chip beside the bars and this list say the same
    **{f"PP_LAND_BAR_TT_DEF_{key.upper()}": f"[Concept('{concept}', '{name}')|e]: ${chip}$"
       for key, concept, name, chip in LAND_STATES},
}


def render_localization() -> str:
    lines = ["﻿l_english:", "  # Generated by ppc finalize (arable_land_bar.py); the population and capacity bars of the location view"]
    lines += [f'  {key}: "{text}"' for key, text in LOC_TEXT.items()]
    lines.append("  # the bars' parts as game concepts (main_menu/common/game_concepts/pp_arable_land_bar.txt)")
    for key, (_, name, text) in CONCEPT_TEXT.items():
        lines += [f'  game_concept_{key}: "{name}"', f'  game_concept_{key}_desc: "{text}"']
    return "\n".join(lines) + "\n"


def render_concepts() -> str:
    lines = ["﻿# Generated by ppc finalize (arable_land_bar.py); do not edit by hand.",
             "# The parts of the location view's population and capacity bars, linked from their labels and tooltip rows."]
    for key, (texture, _, _) in CONCEPT_TEXT.items():
        lines += [f"{key} = {{", "\tfamily = food", f'\ttexture = "{texture}"', "}"]
    return "\n".join(lines) + "\n"


# --- GUI ---------------------------------------------------------------------------------------------------------

# min/max state the 0..1 range: without them a progressbar reads 0..100 (in game 2026-10-26, the bars stayed slivers)
_BAR = ('progressbar = {{ size = {{ 100% 100% }} progresstexture = "gfx/interface/progressbars/{texture}.dds" '
        'noprogresstexture = "{empty}" texture_density = 2 spriteType = Corneredstretched spriteborder = {{ 12 0 }} '
        'min = 0 max = 1 value = {value} direction = horizontal{extra} }}')
_EMPTY = "gfx/interface/icons/unit_view/moral_bar_transparent.dds"
_BACK = "gfx/interface/progressbars/progress_black.dds"
TEXTURES = {"townsfolk": "pp_land_bar_townsfolk", "subsistence": "progress_bar_yellow", "over": "progress_bar_red",
            "land": "progress_bar_green_alt", "farms": "pp_land_bar_farms", "room": "progress_bar_green_alt"}
# the two parts past the capacity, told apart at a glance (2026-10-27, Jan): the farms' land is used land, a plain
# brownish green; the room for improvements is land that can still be added, an empty slot (a faint green with a green
# frame). The townsfolk are a neutral grey. The two own shades are vanilla's bars recoloured by
# tools/build_land_bar_shades.py
SHADES = {part: Path(f"gfx/interface/progressbars/{TEXTURES[part]}.dds") for part in ("townsfolk", "farms")}
ALPHA = {"room": 0.2}
FRAMED = {"room"}
# the threshold lines: a light 1 px core in a dark 3 px line (reads on the dark panel and on every bar colour)
_LINE_LIGHT = "gfx/interface/progressbars/progress_bar_whiteish.dds"


def _sv(name: str) -> str:
    return f"{_LOC}.MakeScope.ScriptValue('{name}')"


def _fraction(name: str) -> str:
    return f"FixedPointToFloat({_sv(name)})"


def _bar(texture: str, value: str, bottom: bool = False, extra: str = "", edge: int = 1) -> str:
    """A bar layer; ``value`` is a data expression, or a plain number (a full swatch); a framed part's frame ``edge``
    px wide."""
    shown = value if value.replace(".", "").isdigit() else f'"[{value}]"'
    if texture in ALPHA:
        extra += f" alpha = {ALPHA[texture]}"
    bar = _BAR.format(texture=TEXTURES[texture], empty=_EMPTY if texture in ALPHA else (_BACK if bottom else _EMPTY),
                      value=shown, extra=extra)
    if texture in FRAMED:
        bar += f" widget = {{ size = {{ 100% 100% }} {_frame(TEXTURES[texture], edge)} }}"
    return bar


def _over_mark(edge: int) -> str:
    """The over-capacity mark laid over the yellow: a red frame ``edge`` px wide, nothing inside, so the yellow stays
    yellow (these are subsistence peasants, the ones beyond the capacity). A red tint over the yellow read orange in
    game, like the farms' brown (2026-10-27)."""
    return _frame(TEXTURES["over"], edge)


def _frame(texture_name: str, edge: int) -> str:
    """A frame ``edge`` px wide around the parent in a bar texture, nothing inside."""
    texture = f"gfx/interface/progressbars/{texture_name}.dds"
    sides = (f"100% {edge}", ""), (f"100% {edge}", " parentanchor = bottom"), (f"{edge} 100%", ""), \
            (f"{edge} 100%", " parentanchor = right")
    return " ".join(f'icon = {{ size = {{ {size} }}{anchor} texture = "{texture}" }}' for size, anchor in sides)


def _swatch(part: str | None) -> str:
    """A 14 x 10 colour swatch of a bar part (empty without one); ``over`` is the mark on the yellow."""
    if part is None:
        return "widget = { size = { 14 10 } }"
    if part == "over":
        return f'widget = {{ size = {{ 14 10 }} {_bar("subsistence", "1", bottom=True)} widget = {{ size = {{ 100% 100% }} {_over_mark(1)} }} }}'
    return f'widget = {{ size = {{ 14 10 }} {_bar(part, "1", bottom=True)} }}'


def _shading(shaded: bool) -> str:
    return ('blockoverride "field_background" { background = { using = tooltip_table_field_texture } }' if shaded
            else 'blockoverride "field_background" {}')


def _tt_row(key: str, value: str, part: str | None, shaded: bool, total: bool = False, visible: str = "") -> str:
    """One row of the bars' tooltip, as vanilla's tooltip tables: the bar's colour swatch, the name left, the value
    right; every second row shaded, a total in the title colour; ``visible`` a data test for a row shown only then."""
    test = f'blockoverride "visibility" {{ visible = "[{visible}]" }} ' if visible else ""
    style = ' default_format = "#yellow_titles"' if total else ""
    return (f'TooltipTableField = {{ {test}{_shading(shaded)} spacing = 6 blockoverride "field_content" {{ {_swatch(part)} '
            f'text_single = {{ layoutpolicy_horizontal = expanding align = left|nobaseline text = "{key}"{style} }} '
            f'text_single = {{ align = right|nobaseline raw_text = "{value}"{style} }} }} }}')


def _tt_list(title: str, rows: list[tuple[str, str, str | None]], total: tuple[str, str], after: str = "") -> str:
    fields = " ".join(_tt_row(key, value, part, index % 2 == 1) for index, (key, value, part) in enumerate(rows))
    fields += " " + _tt_row(total[0], total[1], None, len(rows) % 2 == 1, total=True)
    return f'TooltipListBase = {{ blockoverride "block_title" {{ text = "{title}" }} {fields}{after} }}'


def _state_list() -> str:
    """The land states, one row each: its icon, its name (a link) and how it is defined; rows grow to two lines."""
    rows = []
    for index, (key, *_rest) in enumerate(LAND_STATES):
        rows.append(f'TooltipTableField = {{ blockoverride "row_size" {{ minimumsize = {{ -1 30 }} }} {_shading(index % 2 == 1)} '
                    f'blockoverride "field_content" {{ spacing = 8 '
                    f'icon = {{ size = {{ 20 20 }} texture = "{STATE_ICONS}/{key}.dds" }} '
                    f'textbox = {{ using = tooltip_text_block_template minimumsize = {{ 330 -1 }} '
                    f'margin = {{ 0 4 }} text = "PP_LAND_BAR_TT_DEF_{key.upper()}" }} }} }}')
    return "TooltipListBase = { " + " ".join(rows) + " }"


def _over() -> str:
    """The subsistence peasants beyond the capacity, in thousands (GUI value)."""
    return _clamp0(f"Subtract_float({_f('pp_land_bar_population')}, {_f('pp_land_bar_capacity')})")


def tooltip_block() -> str:
    """The bars' tooltip: vanilla's contextual tooltip with the Arable Land icon, the population and the capacity as
    two lists (swatch, name, value; total last; the peasants over the capacity under the population's total, only
    when there are any) and the land states, one line each."""
    over = _tt_row("PP_LAND_BAR_TT_OVER", _k(_over()), "over", shaded=True,
                   visible=f"GreaterThan_float({_over()}, '(float)0')")
    population = _tt_list("PP_LAND_BAR_POPULATION", [
        ("PP_LAND_BAR_TOWNSFOLK", _v("pp_land_bar_townsfolk"), "townsfolk"),
        ("PP_LAND_BAR_SUBSISTENCE", _v("pp_land_bar_subsistence"), "subsistence"),
    ], ("PP_LAND_BAR_TT_TOTAL", _v("pp_land_bar_population")), after=" " + over)
    room = _tt_row("PP_LAND_BAR_ROOM", "+" + _v("pp_land_bar_room"), "room", shaded=True,
                   visible=f"GreaterThan_float({_f('pp_land_bar_room')}, '(float)0')")
    capacity = _tt_list("PP_LAND_BAR_CAPACITY", [
        ("PP_LAND_BAR_TOWNSFOLK", "+" + _v("pp_land_bar_townsfolk_room"), "townsfolk"),
        ("PP_LAND_BAR_TT_NATURAL", "+" + _v("pp_land_bar_natural"), "land"),
        ("PP_LAND_BAR_TT_IMPROVEMENTS", "+" + _v("pp_land_bar_improvements"), "land"),
        ("PP_LAND_BAR_FARMS", "-" + _v("pp_land_bar_farms"), "farms"),
    ], ("PP_LAND_BAR_TT_TOTAL", _v("pp_land_bar_capacity")), after=" " + room)
    icon = "gfx/interface/icons/modifier_types/total_population_capacity_modifier.dds"
    return f"""tooltipwidget = {{
	ContextualTooltipType = {{
		blockoverride "title_text" {{ text = "PP_LAND_BAR_TT_TITLE" }}
		blockoverride "concept_link" {{ visible = yes text = "[population_capacity|E]" }}
		blockoverride "title_icon" {{ icon = {{ using = tooltip_title_icon_size texture = "{icon}" }} }}
		blockoverride "tooltip_content" {{
			vbox = {{ layoutpolicy_horizontal = expanding spacing = 10 {population} {capacity} {_state_list()} }}
		}}
	}}
}}"""


def _term(part: str, key: str) -> str:
    """One legend entry under the bars: its colour swatch and its name (the numbers are in the bars)."""
    return (f'hbox = {{ spacing = 3 widget = {{ size = {{ 14 10 }} {_bar(part, "1", bottom=True)} }} '
            f'text_single = {{ text = "{key}" fontsize = 12 }} }}')


def _f(name: str) -> str:
    return f"FixedPointToFloat({_sv(name)})"


def _clamp0(expr: str) -> str:
    return f"Max_float({expr}, '(float)0')"


# Both bars are BAR_WIDTH pixels on one scale; each part is its share of the scale in pixels (a data-bound size, as
# vanilla's ToVector2f sizes; a data-bound stretch factor gave every part the same width in game, 2026-10-27)
BAR_WIDTH = 370
LABEL_WIDTH = 100
# a part's number shows where the part is wide enough for it (share of the bar)
_LABEL_SHARE = "0.06"


def _segment(share: str, texture: str) -> str:
    """A part of a bar: ``share`` (0..1 of the scale) x the bar width wide."""
    return f"""widget = {{
	size = "[ToVector2f(Multiply_float({share}, '(float){BAR_WIDTH}'), '(float)18')]"
	visible = "[GreaterThan_float({share}, '(float)0')]"
	{_bar(texture, "1", bottom=True, edge=2)}
}}"""


def _number(share: str, label: str) -> str:
    """A part's number, centred in a box as wide as the part (the numbers lie in a layer above the threshold lines,
    so a line never crosses one)."""
    return f"""widget = {{
	size = "[ToVector2f(Multiply_float({share}, '(float){BAR_WIDTH}'), '(float)18')]"
	visible = "[GreaterThan_float({share}, '(float)0')]"
	text_single = {{ parentanchor = center fontsize = 12 raw_text = "{label}" visible = "[GreaterThan_float({share}, '(float){_LABEL_SHARE}')]" }}
}}"""


def _label(key: str) -> str:
    return (f'widget = {{ size = {{ {LABEL_WIDTH} 18 }} text_single = {{ text = "{key}" parentanchor = vcenter fontsize = 14 '
            f'default_format = "#yellow_titles" }} }}')


def _px(share: str) -> str:
    return f"Multiply_float({share}, '(float){BAR_WIDTH}')"


def _spacer(width: str, height: int) -> str:
    """An empty widget ``width`` (a GUI pixel value, clamped at 0) wide: lays what follows it in an hbox at that x."""
    return f"widget = {{ size = \"[ToVector2f({_clamp0(width)}, '(float){height}')]\" }}"


def _layer(parts: list[str], attrs: str = "size = { 100% 100% }") -> str:
    """An hbox over the parent (whole by default), its parts laid from the left edge: a layer over the bars at the same
    x as their parts."""
    return f"""hbox = {{
{_indent(attrs, 1)}
{_indent(chr(10).join(parts), 1)}
	expand = {{}}
}}"""


Segment = tuple[str, str, str]   # (share 0..1 of the scale, texture part, its number)


def _bar_track(segments: list[Segment], overlay: list[str] | None = None) -> str:
    """One bar: a BAR_WIDTH x 18 track, its parts laid from the left edge; ``overlay`` a layer of parts over them."""
    layers = [_layer([_segment(share, part) for share, part, _ in segments])] + ([_layer(overlay)] if overlay else [])
    return f"""widget = {{
	size = {{ {BAR_WIDTH} 18 }}
	background = {{ texture = "{_BACK}" alpha = 0.6 }}
{_indent(chr(10).join(layers), 1)}
}}"""


def _number_track(segments: list[Segment]) -> str:
    """The numbers of one bar's parts, at the parts' x."""
    return f"""widget = {{
	size = {{ {BAR_WIDTH} 18 }}
{_indent(_layer([_number(share, label) for share, _, label in segments]), 1)}
}}"""


# the threshold lines: 3 px dark with a 1 px light core, from 2 px above the population bar to 2 px under the capacity
# bar; no tooltip of their own (a line's tooltip never showed over the bars' in game, 2026-10-27: the bars' tooltip
# defines the states)
LINE_WIDTH = 3
_BARS_HEIGHT = 18 + 4 + 18


def _line() -> str:
    return (f'widget = {{ size = {{ {LINE_WIDTH} {_BARS_HEIGHT + 4} }} background = {{ texture = "{_BACK}" alpha = 0.9 }} '
            f'icon = {{ size = {{ 1 100% }} parentanchor = hcenter texture = "{_LINE_LIGHT}" }} }}')


def _threshold_lines() -> str:
    """Two lines across both bars on their common scale: at ABUNDANT_SHARE of the capacity (left of it the land is
    abundant) and at the capacity (right of it overused). Laid by spacers of data-bound width, as the bars' parts."""
    capacity = _share("capacity")
    abundant = f"Multiply_float({capacity}, '(float){ABUNDANT_SHARE}')"
    half = LINE_WIDTH / 2
    parts = [
        _spacer(f"Subtract_float({_px(abundant)}, '(float){half}')", _BARS_HEIGHT + 4),
        _line(),
        _spacer(f"Subtract_float({_px(f'Subtract_float({capacity}, {abundant})')}, '(float){LINE_WIDTH}')", _BARS_HEIGHT + 4),
        _line(),
    ]
    return _layer(parts, f"position = {{ 0 -2 }}\nsize = {{ 100% {_BARS_HEIGHT + 4} }}\n"
                         f"visible = \"[GreaterThan_float({capacity}, '(float)0')]\"")


# the lines' labels: a row above the bars, each label LABEL_BOX px wide and centred on its line
LABEL_ROW = 12
LABEL_BOX = 34


def _line_label(text: str) -> str:
    return (f'widget = {{ size = {{ {LABEL_BOX} {LABEL_ROW} }} text_single = {{ parentanchor = center fontsize = 11 '
            f'raw_text = "{text}" }} }}')


def _threshold_labels() -> str:
    """"10%" and "100%" above the threshold lines (share of the capacity): what the lines mark. The 10 % label shows
    only where the two lines are far enough apart for both."""
    capacity = _share("capacity")
    abundant = f"Multiply_float({capacity}, '(float){ABUNDANT_SHARE}')"
    gap = _px(f"Subtract_float({capacity}, {abundant})")
    def placed(text: str, share: str, extra: str = "") -> str:
        # each label at its own data-bound x (its line's x minus half its box): chained spacers in an hbox clamped at
        # the left edge and pushed both labels off their lines (in game, 2026-10-27); a negative x may overhang left
        box = _line_label(text).replace("widget = {", f"widget = {{ position = \"[ToVector2f(Subtract_float("
                                         f"{_px(share)}, '(float){LABEL_BOX / 2}'), '(float)0')]\"", 1)
        return box.replace("text_single = {", f"text_single = {{{extra}", 1) if extra else box

    near = placed("10%", abundant, f" visible = \"[GreaterThan_float({gap}, '(float){LABEL_BOX}')]\"")
    # a fixed box at the top of the bars' column: an hbox alone stretched to the column's height and centred the labels
    # on the population bar (in game, 2026-10-27)
    return f"""widget = {{
	position = {{ 0 0 }}
	size = {{ {BAR_WIDTH} {LABEL_ROW} }}
	visible = "[GreaterThan_float({capacity}, '(float)0')]"
	{near}
	{placed("100%", capacity)}
}}"""


def _bars(rows: list[tuple[str, list[Segment], list[str] | None]]) -> str:
    """The labels in one column and the bars in another, each bar a track of the same width in the same column: both
    bars start at the same x whatever their labels (in rows of their own they did not, 2026-10-27). Over the bars'
    column, so they move nothing: the threshold lines, then the parts' numbers."""
    labels = "\n".join([f"widget = {{ size = {{ {LABEL_WIDTH} {LABEL_ROW} }} }}"] + [_label(key) for key, _, _ in rows])

    def column(tracks: list[str]) -> str:
        return f"""vbox = {{
	size = {{ 100% 100% }}
	spacing = 4
{_indent(chr(10).join(tracks), 1)}
}}"""

    bars = column([_bar_track(segments, overlay) for _, segments, overlay in rows])
    numbers = column([_number_track(segments) for _, segments, _ in rows])
    return f"""hbox = {{
	spacing = 8
	vbox = {{
		spacing = 4
{_indent(labels, 2)}
	}}
	widget = {{
		size = {{ {BAR_WIDTH} {LABEL_ROW + 4 + _BARS_HEIGHT} }}
{_indent(_threshold_labels(), 2)}
		widget = {{
			position = {{ 0 {LABEL_ROW + 4} }}
			size = {{ {BAR_WIDTH} {_BARS_HEIGHT} }}
{_indent(bars, 3)}
{_indent(_threshold_lines(), 3)}
{_indent(numbers, 3)}
		}}
	}}
}}"""


def _share(name: str) -> str:
    return _f(f"pp_land_bar_f_{name}")


def _part(upper: str, lower: str) -> str:
    """The share between two cumulative shares of a bar."""
    return _clamp0(f"Subtract_float({_share(upper)}, {_share(lower)})")


def _k(expr: str, sign: str = "") -> str:
    return f"{sign}[{expr}|0]K"


def gui_block(indent: str = "", land_state: str = "") -> str:
    """The panel under the location view's scene: the population on its capacity, as two bars on one scale.

    Population: townsfolk (grey) and subsistence peasants (yellow, one part), the ones beyond the capacity marked red
    over the yellow. Capacity: the same townsfolk (grey), the arable land left (green), then past the end of the
    capacity the land the farms hold (brownish green) and the room for improvements (faint green, green frame). Every part carries its number; two thin lines across both bars mark the
    land state thresholds, labelled 10% and 100% of the capacity above the bars. Right of the bars the land state they make (the arable land chip: overused / available / abundant,
    with its strength; its tooltip has the effects), under them a legend of the colours; the breakdown is in the
    bars' tooltip.
    """
    over_part = _part("population", "within")
    over_mark = f"""widget = {{
	size = "[ToVector2f({_px(over_part)}, '(float)18')]"
	visible = "[GreaterThan_float({over_part}, '(float)0')]"
	{_over_mark(2)}
}}"""
    population = ("PP_LAND_BAR_POPULATION", [
        (_share("townsfolk"), "townsfolk", _k(_sv("pp_land_bar_townsfolk"))),
        (_part("population", "townsfolk"), "subsistence", _k(_sv("pp_land_bar_subsistence"))),
    ], [_spacer(_px(_share("within")), 18), over_mark])
    capacity = ("PP_LAND_BAR_CAPACITY", [
        (_share("townsfolk_room"), "townsfolk", _k(_sv("pp_land_bar_townsfolk_room"))),
        (_part("capacity", "townsfolk_room"), "land", _k(_sv("pp_land_bar_left_shown"))),
        (_part("held", "capacity"), "farms", _k(_sv("pp_land_bar_farms_shown"))),
        (_part("land", "held"), "room", _k(_sv("pp_land_bar_room"))),
    ], None)
    legend = "\n".join([
        _term("townsfolk", "PP_LAND_BAR_TOWNSFOLK"),
        _term("subsistence", "PP_LAND_BAR_SUBSISTENCE"),
        _term("land", "PP_LAND_BAR_LAND"),
        _term("farms", "PP_LAND_BAR_FARMS"),
        _term("room", "PP_LAND_BAR_ROOM"),
        "expand = {}",
    ])
    block = f"""# PP: population and capacity bars (arable_land_bar.py): the population on its capacity, one scale, and right of
# them the land state the two make (the location view's only arable land chip)
vbox = {{
	name = "pp_arable_land_bar"
	layoutpolicy_horizontal = expanding
	margin = {{ 12 6 }}
	spacing = 4
	background = {{ using = color_dark_blue_texture alpha = 0.85 }}

	hbox = {{
		layoutpolicy_horizontal = expanding
		spacing = 8
		widget = {{
			size = {{ {LABEL_WIDTH + 8 + BAR_WIDTH} {LABEL_ROW + 4 + _BARS_HEIGHT} }}
{_indent(tooltip_block(), 3)}
{_indent(_bars([population, capacity]), 3)}
		}}
		expand = {{}}
{_indent(land_state, 2)}
	}}

	hbox = {{
		layoutpolicy_horizontal = expanding
		spacing = 6
{_indent(tooltip_block(), 2)}
{_indent(legend, 2)}
	}}
}}"""
    return _indent(block, 0, indent)


def _indent(text: str, tabs: int, prefix: str = "") -> str:
    pad = prefix + "\t" * tabs
    return "\n".join(pad + line if line else line for line in text.splitlines())


_SCENE = "# SCENE\n"


def add_to_window(text: str, land_state: str = "") -> str:
    """Insert the panel right under the location view's scene (once); ``land_state`` is the land chip line
    (location_status.land_state)."""
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
    return text[:end + 1] + "\n\n" + gui_block(indent, land_state) + text[end + 1:]


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
    """Write the bars' script values and localization (the window block is added by location_view.build_window)."""
    m = model(mod_root, vanilla_game)
    files = ((SCRIPT_VALUES, render_script_values(m)), (LOCALIZATION, render_localization()), (CONCEPTS, render_concepts()))
    changed = [str(rel) for rel, text in files if _write(mod_root / rel, text)]
    counts = {"improvements": len(m.improvements), "caps": len(m.units), "farms": len(m.farms),
              "reserved grounds": len(m.reserved)}
    return Result(counts, changed)
