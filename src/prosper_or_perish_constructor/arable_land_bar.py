"""The population and capacity bars of the location view (2026-10-27, Jan; view only).

Capacity model since 2026-10-27: total_population gives every person +1 capacity and unemployed_peasants takes it
back from the subsistence peasants, so the engine's capacity is everyone but the subsistence peasants (the townsfolk:
each brings their own room) plus the arable land left (the location's land and improvements, minus what the farms take).
The engine still compares the whole population with that capacity, so the panel shows exactly that, on one scale:

- Population: the townsfolk (grey), then the subsistence peasants (yellow); beyond the capacity red.
- Population capacity: the same townsfolk (grey: they cancel out), then the arable land left (green), then the land the
  farms take (brown, past the end of the capacity). The subsistence peasants live on the green; farms grow into it.
- every part is as wide as its number (data-bound stretch factors) and carries it; under the bars a legend of the
  colours and the land state the two bars make (the arable land chip with its strength: the engine's free land or
  overpopulation from population / capacity); the breakdown of the arable land is in the tooltip.

Farm land and improvements are read from the building types the game loads (``raw_modifier``
``local_population_capacity`` per level, through the buildings' level counters, which the engine scales like the
capacity row). Every value includes the location's remaining capacity modifiers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from eu5gameparser.clausewitz.parser import parse_file
from eu5gameparser.clausewitz.syntax import CList

SCRIPT_VALUES = Path("in_game/common/script_values/pp_arable_land_bar.txt")
LOCALIZATION = Path("main_menu/localization/english/pp_arable_land_bar_l_english.yml")
BUILDING_TYPES = Path("in_game/common/building_types")
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

    @property
    def counter(self) -> str | None:
        """The building's own level counter, if it carries exactly one of the farm or improvement kind."""
        own = sorted(c for c in self.counters if c.startswith((FARM_COUNTER, IMPROVEMENT_COUNTER)))
        return own[0] if len(own) == 1 else None


@dataclass
class Model:
    improvements: list[Building]
    farms: list[Building]
    reserved: list[Building]


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


def _read_buildings(paths: list[Path], buildings: dict[str, Building]) -> None:
    for path in paths:
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


def buildings(mod_root: Path, vanilla_game: Path | None) -> dict[str, Building]:
    """Every building type the game loads, vanilla first, then the mod's files in load order."""
    found: dict[str, Building] = {}
    if vanilla_game is not None:
        _read_buildings(sorted((vanilla_game / "in_game/common/building_types").glob("*.txt")), found)
    _read_buildings(sorted((mod_root / BUILDING_TYPES).glob("*.txt")), found)
    return found


def model(mod_root: Path, vanilla_game: Path | None) -> Model:
    found = buildings(mod_root, vanilla_game)
    improvements = [b for b in found.values() if (b.max_levels or "").startswith("pp_wb_cap_") and b.land > 0]
    farms = [b for b in found.values() if b.land < 0 and any(c.startswith(FARM_COUNTER) for c in b.counters)]
    reserved = [b for b in found.values() if b.land < 0 and b not in farms]
    key = lambda b: b.key  # noqa: E731
    return Model(sorted(improvements, key=key), sorted(farms, key=key), sorted(reserved, key=key))


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


_FIXED = """# Capacity multiplier as the engine applies it: (1 + local % + the owner's global %) x (1 + total %)
pp_land_bar_multiplier = {
	value = 1
	add = modifier:local_population_capacity_modifier
	if = { limit = { exists = owner } add = owner.modifier:global_population_capacity_modifier }
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
pp_land_bar_capacity = { value = pp_land_bar_townsfolk_room add = pp_land_bar_left_shown }
pp_land_bar_percent = {
	value = 0
	if = { limit = { pp_land_bar_capacity > 0 } value = pp_land_bar_population divide = pp_land_bar_capacity multiply = 100 }
}

# Bar fractions (0..1) on one scale for both bars: the population, or the capacity with the farms' land past its end
pp_land_bar_scale_land = { value = pp_land_bar_capacity add = pp_land_bar_farms }
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
    ]
    return "\n\n".join(part.strip("\n") if i else part.rstrip("\n") for i, part in enumerate(parts)) + "\n"


def _v(name: str, digits: int = 0) -> str:
    """A script value of the bars in text (thousands of people, shown like the game's 295K)."""
    return f"[LocationView.GetLocation.MakeScope.ScriptValue('{name}')|{digits}]K"


LOC_TEXT = {
    "PP_LAND_BAR_POPULATION": "Population",
    "PP_LAND_BAR_CAPACITY": "[population_capacity|E]",
    "PP_LAND_BAR_TOWNSFOLK": "Townsfolk",
    "PP_LAND_BAR_SUBSISTENCE": "Subsistence peasants",
    "PP_LAND_BAR_LAND": "Arable land left",
    "PP_LAND_BAR_FARMS": "Farms",
    "PP_LAND_BAR_TT": (
        f"Population: {_v('pp_land_bar_townsfolk')} townsfolk (everyone who is not a subsistence peasant) "
        f"and {_v('pp_land_bar_subsistence')} subsistence peasants.\\n"
        f"[population_capacity|E]: {_v('pp_land_bar_townsfolk_room')} for the townsfolk, who each bring their own, "
        f"and {_v('pp_land_bar_left')} arable land left.\\n\\n"
        f"Arable land left: the location's land {_v('pp_land_bar_natural')} and its improvements "
        f"{_v('pp_land_bar_improvements')}, minus {_v('pp_land_bar_farms')} the farms take.\\n\\n"
        "The subsistence peasants live on the arable land left. Farms can take all of it: a new farm pushes them out, "
        "and they leave until the location fits its capacity again."
    ),
}


def render_localization() -> str:
    lines = ["﻿l_english:", "  # Generated by ppc finalize (arable_land_bar.py); the population and capacity bars of the location view"]
    lines += [f'  {key}: "{text}"' for key, text in LOC_TEXT.items()]
    return "\n".join(lines) + "\n"


# --- GUI ---------------------------------------------------------------------------------------------------------

# min/max state the 0..1 range: without them a progressbar reads 0..100 (in game 2026-10-26, the bars stayed slivers)
_BAR = ('progressbar = {{ size = {{ 100% 100% }} progresstexture = "gfx/interface/progressbars/{texture}.dds" '
        'noprogresstexture = "{empty}" texture_density = 2 spriteType = Corneredstretched spriteborder = {{ 12 0 }} '
        'min = 0 max = 1 value = {value} direction = horizontal{extra} }}')
_EMPTY = "gfx/interface/icons/unit_view/moral_bar_transparent.dds"
_BACK = "gfx/interface/progressbars/progress_black.dds"
TEXTURES = {"townsfolk": "progress_bar_grey_alt", "subsistence": "progress_bar_yellow", "over": "progress_bar_red_alt",
            "land": "progress_bar_green_alt", "farms": "progress_bar_brown_alt"}


def _sv(name: str) -> str:
    return f"{_LOC}.MakeScope.ScriptValue('{name}')"


def _fraction(name: str) -> str:
    return f"FixedPointToFloat({_sv(name)})"


def _bar(texture: str, value: str, bottom: bool = False, extra: str = "") -> str:
    """A bar layer; ``value`` is a data expression, or a plain number (a full swatch)."""
    shown = value if value.replace(".", "").isdigit() else f'"[{value}]"'
    return _BAR.format(texture=TEXTURES[texture], empty=_BACK if bottom else _EMPTY, value=shown, extra=extra)


def _term(part: str, key: str) -> str:
    """One legend entry under the bars: its colour swatch and its name (the numbers are in the bars)."""
    return (f'hbox = {{ spacing = 3 widget = {{ size = {{ 14 10 }} {_bar(part, "1", bottom=True)} }} '
            f'text_single = {{ text = "{key}" fontsize = 12 }} }}')


def _f(name: str) -> str:
    return f"FixedPointToFloat({_sv(name)})"


def _clamp0(expr: str) -> str:
    return f"Max_float({expr}, '(float)0')"


_SCALE = _f("pp_land_bar_scale")
# a segment's number shows where the segment is wide enough for it (a share of the bar)
_LABEL_SHARE = "0.06"


def _segment(weight: str, texture: str | None, label: str = "") -> str:
    """A part of a bar, as wide as its weight in the bar's row (data-bound stretch factor, as vanilla's societal values
    do), with its number in it. An empty texture is the unfilled rest of the bar."""
    fill = _bar(texture, "1", bottom=True) if texture else ""
    text = ""
    if label:
        text = (f'\n\ttext_single = {{ parentanchor = center fontsize = 12 raw_text = "{label}" '
                f"visible = \"[GreaterThan_float({weight}, Multiply_float({_SCALE}, '(float){_LABEL_SHARE}'))]\" }}")
    return f"""widget = {{
	size = {{ 0 16 }}
	layoutpolicy_horizontal = expanding
	layoutstretchfactor_horizontal = "[{weight}]"
	visible = "[GreaterThan_float({weight}, '(float)0')]"
	{fill}{text}
}}"""


def _row(label: str, segments: list[str]) -> str:
    """A labelled bar: the label in a fixed column, so both bars start at the same x and share one scale."""
    parts = "\n".join(segments)
    return f"""hbox = {{
	layoutpolicy_horizontal = expanding
	spacing = 8
	widget = {{
		size = {{ 150 18 }}
		text_single = {{ text = "{label}" parentanchor = vcenter fontsize = 14 default_format = "#yellow_titles" }}
	}}
	hbox = {{
		layoutpolicy_horizontal = expanding
		size = {{ -1 16 }}
		background = {{ texture = "{_BACK}" alpha = 0.6 }}
{_indent(parts, 2)}
	}}
}}"""


def _k(expr: str, sign: str = "") -> str:
    return f"{sign}[{expr}|0]K"


def gui_block(indent: str = "", land_state: str = "") -> str:
    """The panel under the location view's scene: the population on its capacity, as two bars on one scale.

    Population: townsfolk (grey) and subsistence peasants (yellow), red beyond the capacity. Capacity: the same
    townsfolk (grey), the arable land left (green), then the farms' land (brown) past the end of the capacity. Every
    part carries its number; under the bars a legend of the colours and the land state the two bars make (the arable
    land chip: overused / available / abundant, with its strength); the breakdown is in the tooltip.
    """
    townsfolk, subsistence = _f("pp_land_bar_townsfolk"), _f("pp_land_bar_subsistence")
    within = f"Min_float({subsistence}, {_f('pp_land_bar_left_shown')})"
    over = _clamp0(f"Subtract_float({_f('pp_land_bar_population')}, {_f('pp_land_bar_capacity')})")
    population = _row("PP_LAND_BAR_POPULATION", [
        _segment(townsfolk, "townsfolk", _k(_sv("pp_land_bar_townsfolk"))),
        _segment(within, "subsistence", _k(_sv("pp_land_bar_subsistence"))),
        _segment(over, "over", _k(over, "+")),
        _segment(_clamp0(f"Subtract_float({_SCALE}, {_f('pp_land_bar_population')})"), None),
    ])
    capacity = _row("PP_LAND_BAR_CAPACITY", [
        _segment(_f("pp_land_bar_townsfolk_room"), "townsfolk", _k(_sv("pp_land_bar_townsfolk_room"))),
        _segment(_f("pp_land_bar_left_shown"), "land", _k(_sv("pp_land_bar_left_shown"))),
        _segment(_f("pp_land_bar_farms"), "farms", _k(_sv("pp_land_bar_farms"))),
        _segment(_clamp0(f"Subtract_float({_SCALE}, {_f('pp_land_bar_scale_land')})"), None),
    ])
    legend = "\n".join([
        _term("townsfolk", "PP_LAND_BAR_TOWNSFOLK"),
        _term("subsistence", "PP_LAND_BAR_SUBSISTENCE"),
        _term("land", "PP_LAND_BAR_LAND"),
        _term("farms", "PP_LAND_BAR_FARMS"),
        "expand = {}",
        land_state,
    ])
    block = f"""# PP: population and capacity bars (arable_land_bar.py): the population on its capacity, one scale
vbox = {{
	name = "pp_arable_land_bar"
	layoutpolicy_horizontal = expanding
	margin = {{ 12 6 }}
	spacing = 4
	background = {{ using = color_dark_blue_texture alpha = 0.85 }}
	tooltip = "PP_LAND_BAR_TT"

{_indent(population, 1)}
{_indent(capacity, 1)}

	hbox = {{
		layoutpolicy_horizontal = expanding
		spacing = 6
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
    changed = [str(rel) for rel, text in ((SCRIPT_VALUES, render_script_values(m)), (LOCALIZATION, render_localization()))
               if _write(mod_root / rel, text)]
    counts = {"improvements": len(m.improvements), "farms": len(m.farms), "reserved grounds": len(m.reserved)}
    return Result(counts, changed)
