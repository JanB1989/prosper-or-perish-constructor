"""Generate flat rural-capacity scripted values.

The generated files intentionally duplicate formula rows for each building's
max-level path. EU5 exposes the scripted-value rows directly in the building
max-level tooltip: every step of a described row is drawn as a sub-row, so the
farm rows read their helpers through ``this.`` (one number each, cap_tooltips.py).
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from prosper_or_perish_constructor.rural_capacity import (
    FISH_CAP_BUILDINGS,
    FOREST_CAP_BUILDINGS,
    LAND_FARM_BUILDINGS,
    capacity_max_omitted_buildings_by_building,
    farm_level_counter_for_building,
)


ROOT = Path(__file__).resolve().parents[1]
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_VALUES_ROOT = MOD_ROOT / "in_game" / "common" / "script_values"
CULLING_EFFECTS_PATH = MOD_ROOT / "in_game" / "common" / "scripted_effects" / "pp_capacity_culling_effects.txt"
# error_log fields after "PPBLD;capacity_cull;", written in the culled building's scope: date;building owner tag;
# location id;building;level before the cull. Verified in game 2026-09-30: the log text reaches the building through
# THIS; ROOT and saved scopes (SCOPE.sCountry/sLocation/...) resolve to nothing there.
# Debug instrumentation of the capacity cull (per-location counter pp_dbg_script_cull + PPBLD error_log line per cull).
# Off in the shipped mod since 2026-10-03 (Jan: no test hooks in normal play); set True for a measuring run.
CULL_DEBUG = False
CULL_LOG_FIELDS = (
    "[GetDateString];[THIS.GetBuilding.GetOwner.GetTag];[THIS.GetBuilding.GetLocation.GetKey];"
    "[THIS.GetBuilding.GetType.GetNameWithNoTooltip];[THIS.GetBuilding.GetLevel]"
)
BUILDING_BLUEPRINT_ROOT = ROOT / "blueprints" / "accepted" / "buildings"


def _line(text: str, depth: int = 0) -> str:
    return "\t" * depth + text


def _if_has_building_block(
    building: str,
    inner: Iterable[str | tuple[int, str]],
    depth: int = 1,
) -> list[str]:
    rows = [
        _line("if = {", depth),
        _line(f"limit = {{ has_building = building_type:{building} }}", depth + 1),
    ]
    for item in inner:
        if isinstance(item, tuple):
            relative_depth, line = item
        else:
            relative_depth, line = 0, item
        rows.append(_line(line, depth + 1 + relative_depth))
    rows.append(_line("}", depth))
    return rows


def _capacity_building_subtract_rows(
    *,
    prefix: str,
    buildings: Iterable[str],
    omit_building: str | None = None,
    omit_buildings: Iterable[str] = (),
) -> list[str]:
    rows: list[str] = []
    omitted = set(omit_buildings)
    if omit_building is not None:
        omitted.add(omit_building)
    for building in buildings:
        if building in omitted:
            continue
        rows.extend(
            _if_has_building_block(
                building,
                (
                    "subtract = {",
                    (1, f'desc = "BUILDING_LEVEL_{prefix}_{building.upper()}"'),
                    (1, f'value = "location_building_level(building_type:{building})"'),
                    "}",
                ),
            )
        )
    return rows


def _building_level_pressure_rows(*, prefix: str) -> list[str]:
    return [
        _line("subtract = {", 1),
        _line(f'desc = "BUILDING_LEVEL_{prefix}_URBANIZATION"', 2),
        _line("value = total_building_levels", 2),
        _line("multiply = 0.05", 2),
        _line("}", 1),
    ]


def _script_value(name: str, rows: Iterable[str], comments: Iterable[str] = ()) -> str:
    lines = [f"{name} = {{"]
    lines.extend(_line(f"# {comment}", 1) for comment in comments)
    lines.extend(rows)
    lines.append("}")
    return "\n".join(lines)


def _farm_land_constants() -> tuple[dict[str, tuple[float, float]], tuple[float, float]]:
    """Per-building (land, reserve) in capacity units from constructor.toml [worldbuilder.farm_land]."""
    import tomllib

    raw = tomllib.loads((REPO_ROOT / "constructor.toml").read_text(encoding="utf-8"))
    section = raw.get("worldbuilder", {}).get("farm_land", {})
    classes = section.get("classes", {})
    per_building: dict[str, tuple[float, float]] = {}
    for cls, members in classes.items():
        values = section[cls]
        for building in members:
            per_building[str(building)] = (float(values["land"]), float(values["reserve"]))
    default = (float(section["arable"]["land"]), float(section["arable"]["reserve"]))
    return per_building, default


# The arable land left in the flat capacity: total_population gives every person +1 and pp_subsistence_land takes -1
# from every subsistence peasant (2026-10-27, Jan), so the capacity of everyone else is taken back out here. The farm
# cap counts land only; without this a town's people would count as farmland. The start simulation models the flat as
# land only and reads this value as 0 (start_rules.py).
TOWNSFOLK_CAPACITY = "pp_townsfolk_capacity"
# pp_subsistence_land's size as the engine applies it (marker modifier type, 1 per unit of size). The modifier is
# refreshed once a year, so between refreshes it differs from today's subsistence peasants: a new farm level hires
# subsistence peasants at once, and reading them today took their land a second time until the refresh (2026-10-28).
SUBSISTENCE_SIZE = "modifier:pp_subsistence_land_size"


def _arable_rows(land: float, reserve: float, depth: int) -> list[str]:
    FARM_HELPERS[TOWNSFOLK_CAPACITY] = _script_value(
        TOWNSFOLK_CAPACITY,
        [_line("value = population", 1), _line(f"subtract = {SUBSISTENCE_SIZE}", 1)],
        ["The capacity total_population (+1 per person) and pp_subsistence_land (-1 per subsistence peasant, at the",
         "size it was last given) add to the flat"],
    )
    rows = [_line("value = modifier:local_population_capacity", depth), _line(f"subtract = {TOWNSFOLK_CAPACITY}", depth)]
    if reserve:
        rows.append(_line(f"subtract = {reserve:g}", depth))
    return rows + [_line(f"divide = {land:g}", depth), _line("floor = yes", depth)]


def _free_land_rows(land: float, reserve: float, desc: str) -> list[str]:
    return [_line("add = {", 1), _line(f'desc = "{desc}"', 2), *_arable_rows(land, reserve, 2), _line("}", 1)]


def _farm_source_rows(
    omit_building: str | None = None,
    omit_buildings: Iterable[str] = (),
) -> list[str]:
    """Farm capacity = remaining farmland: (arable land left - reserve) / land per level.

    The arable land left is the flat capacity without the capacity everyone but the subsistence peasants brings. It
    already contains -land per built farm level (raw_modifier on each farm building), so the
    public value is the land still free for farms, in farm levels. Per-building max values add the building's
    own levels back (its level counter pp_levels_<farm> is +1 per level) so the max is the same number no matter
    how many of it exist; replaceable lower tiers are added back too.
    """
    per_building, default = _farm_land_constants()
    # ordered: the building whose max this is comes first (its own land constants apply), then replaceable tiers
    omitted = list(dict.fromkeys([*([omit_building] if omit_building is not None else []), *omit_buildings]))
    if not omitted:
        land, reserve = default
        return _free_land_rows(land, reserve, "BUILDING_LEVEL_WB_FREE_FARMLAND") + [_line('min = { desc = "BUILDING_LEVEL_WB_MINIMUM" value = 0 }', 1)]
    # Max-level tooltip, in levels of this farm (2026-10-23, Jan: one name for the land on a farm, so no second land
    # record): "Free Arable Land" floor((flat - reserve) / land) plus "This farm" (its own levels and those of its
    # replaceable lower tiers, from their level counters; the counters are scaled like the land they take, so the cap is
    # exact). Each row reads its helper through this., so the game shows it as one number (cap_tooltips.py).
    target = omitted[0]
    land, reserve = per_building.get(target, default)
    free = _free_farmland_helper(land, reserve)
    queued = _queued_levels_helper(target, land, reserve, free)
    own = f"farm_capacity_max_{target}_own_levels"
    FARM_HELPERS[own] = _script_value(
        own,
        [_line("value = 0", 1), *(_line(f"add = modifier:{farm_level_counter_for_building(b)}", 1) for b in omitted)],
    )
    return [
        _line(f'add = {{ desc = "BUILDING_LEVEL_WB_FREE_FARMLAND" value = this.{free} }}', 1),
        _line(f'if = {{ limit = {{ {queued} < 0 }} add = {{ desc = "PP_BUILDING_LEVEL_FARM_UNDER_CONSTRUCTION" '
              f'value = this.{queued} }} }}', 1),
        _line(f'add = {{ desc = "PP_BUILDING_LEVEL_FARM_OWN_LEVELS" value = this.{own} }}', 1),
        _line('min = { desc = "BUILDING_LEVEL_WB_MINIMUM" value = 0 }', 1),
    ]


FARM_HELPERS: dict[str, str] = {}   # tooltip helpers of the farm max levels, written after them
# Every land farm's upgrade line (its tiers, lowest first) and the farms of each land per level; set by main()
FARM_FAMILIES: dict[str, tuple[str, ...]] = {}
FARM_LAND_CLASSES: dict[float, tuple[str, ...]] = {}
# Levels under construction per building counted (building_levels_under_construction is a trigger, so the count is
# stepped; a farm rarely has more than one level under construction, 2026-10-28 save of 1554: 715 farm constructions)
QUEUE_STEPS = 5
FARM_LAND_TRIGGERS_PATH = MOD_ROOT / "in_game" / "common" / "scripted_triggers" / "pp_farm_land_classes.txt"


def _land_class_trigger(land: float) -> str:
    return f"pp_farm_land_class_{land:g}".replace(".", "_")


def _queued_outside_helper(target: str) -> str:
    """Land (capacity units) that the farm levels under construction in the location will take, other than the levels
    of this farm's own upgrade line: the engine counts a building's own levels under construction against its max
    level, but not another farm's, so two farms could start levels on the same free land (2026-10-28, Jan)."""
    family = FARM_FAMILIES.get(target, (target,))
    name = f"pp_farm_land_queued_outside_{family[0]}"
    if name in FARM_HELPERS:
        return name
    own_line = " ".join(f"building_type = building_type:{b}" for b in family)
    rows = [
        _line("value = 0", 1),
        _line("every_buildings_in_location = {", 1),
        _line(f"limit = {{ building_levels_under_construction >= 1 NOT = {{ OR = {{ {own_line} }} }} }}", 2),
    ]
    for index, land in enumerate(sorted(FARM_LAND_CLASSES)):
        steps = " ".join(f"if = {{ limit = {{ building_levels_under_construction >= {n} }} add = {land:g} }}"
                         for n in range(2, QUEUE_STEPS + 1))
        branch = "if" if index == 0 else "else_if"
        rows.append(_line(f"{branch} = {{ limit = {{ {_land_class_trigger(land)} = yes }} add = {land:g} {steps} }}", 2))
    rows.append(_line("}", 1))
    FARM_HELPERS[name] = _script_value(name, rows, [
        "Land the farm levels under construction here will take (capacity units), this farm's upgrade line left out:",
        "the engine counts a building's own levels under construction against its max level, not another farm's"])
    return name


def _queued_levels_helper(target: str, land: float, reserve: float, free: str) -> str:
    """Levels of this farm that the other farms' levels under construction take from its free arable land (0 or less).
    Only where land is free: on overused land the cap stays as it was, so a construction never lowers a farm's max
    below the levels it stands at (the capacity cull removes levels above the max)."""
    family = FARM_FAMILIES.get(target, (target,))
    outside = _queued_outside_helper(target)
    name = f"pp_farm_queued_levels_{family[0]}"
    if name not in FARM_HELPERS:
        rows = [
            _line("value = 0", 1),
            _line("if = {", 1),
            _line(f"limit = {{ {free} > 0 }}", 2),
            *_arable_rows(land, reserve, 2)[:2],
            _line(f"subtract = {outside}", 2),
            *_arable_rows(land, reserve, 2)[2:],
            _line("min = 0", 2),
            _line(f"subtract = {free}", 2),
            _line("}", 1),
        ]
        FARM_HELPERS[name] = _script_value(name, rows)
    return name


def _farm_land_triggers_file() -> str:
    lines = ["# Generated by scripts/generate_rural_capacity_values.py; do not edit by hand.",
             "# Building scope: the land farms by their land per level (capacity units, [worldbuilder.farm_land] in",
             "# constructor.toml), read by the farm max levels for the farm levels under construction in a location.", ""]
    for land, members in sorted(FARM_LAND_CLASSES.items()):
        lines.append(f"{_land_class_trigger(land)} = {{")
        lines.append(_line("OR = {", 1))
        lines.extend(_line(f"building_type = building_type:{b}", 2) for b in members)
        lines.append(_line("}", 1))
        lines.append("}")
    return "\n".join(lines) + "\n"


def _set_farm_families(omissions: dict[str, tuple[str, ...]]) -> None:
    """Upgrade lines from the max-level omissions (each farm omits itself and the lower tiers it replaces) and the
    land classes; every farm of one line must take the same land per level."""
    per_building, default = _farm_land_constants()
    parent = {b: b for b in LAND_FARM_BUILDINGS}

    def root(b: str) -> str:
        while parent[b] != b:
            b = parent[b]
        return b

    for building, omitted in omissions.items():
        for other in omitted:
            parent[root(other)] = root(building)
    lines: dict[str, list[str]] = {}
    for building in LAND_FARM_BUILDINGS:
        lines.setdefault(root(building), []).append(building)
    FARM_FAMILIES.clear()
    for members in lines.values():
        family = tuple(sorted(members, key=lambda b: len(omissions.get(b, (b,)))))
        constants = {per_building.get(b, default) for b in family}
        if len(constants) != 1:
            raise ValueError(f"farm upgrade line {family} takes different land per level: {sorted(constants)}")
        FARM_FAMILIES.update({b: family for b in family})
    classes: dict[float, list[str]] = {}
    for building in LAND_FARM_BUILDINGS:
        classes.setdefault(per_building.get(building, default)[0], []).append(building)
    FARM_LAND_CLASSES.clear()
    FARM_LAND_CLASSES.update({land: tuple(members) for land, members in classes.items()})


def _free_farmland_helper(land: float, reserve: float) -> str:
    """Free arable land for a farm with this land per level and reserve, in its levels (floored, as the cap always
    had it)."""
    name = f"pp_free_farmland_levels_land_{land:g}_reserve_{reserve:g}".replace(".", "_")
    FARM_HELPERS[name] = _script_value(name, _arable_rows(land, reserve, 1))
    return name


def _fish_source_rows(
    omit_building: str | None = None,
    omit_buildings: Iterable[str] = (),
) -> list[str]:
    rows = [
        _line("add = {", 1),
        _line('desc = "BUILDING_LEVEL_BASE_FISHING"', 2),
        _line("if = {", 2),
        _line("limit = { has_variable = pp_fish_base_capacity }", 3),
        _line("value = var:pp_fish_base_capacity", 3),
        _line("}", 2),
        _line("else = { value = pp_fish_base_capacity_value }", 2),
        _line("}", 1),
        _line("add = {", 1),
        _line('desc = "BUILDING_LEVEL_RGO_SIZE_FISHING"', 2),
        _line("if = {", 2),
        _line("limit = { has_variable = pp_fish_base_capacity }", 3),
        _line("value = var:pp_fish_base_capacity", 3),
        _line("}", 2),
        _line("else = { value = pp_fish_base_capacity_value }", 2),
        _line("multiply = max_rgo_workers", 2),
        _line("multiply = 0.030", 2),
        _line("}", 1),
        _line("add = {", 1),
        _line("# River size is bridged through a source-specific modifier so it remains a", 2),
        _line("# visible row for locations whose river size is stored on static modifiers.", 2),
        _line('desc = "BUILDING_LEVEL_FISH_RIVER"', 2),
        _line("value = modifier:fish_capacity_from_river_size", 2),
        _line("}", 1),
        _line("if = {", 1),
        _line("limit = { has_town_rights = town_rights_type:manorial_customals }", 2),
        _line("add = {", 2),
        _line('desc = "BUILDING_LEVEL_FISH_MANORIAL_CUSTOMALS"', 3),
        _line("value = 2", 3),
        _line("}", 2),
        _line("}", 1),
    ]
    rows.extend(
        _capacity_building_subtract_rows(
            prefix="FISH",
            buildings=FISH_CAP_BUILDINGS,
            omit_building=omit_building,
            omit_buildings=omit_buildings,
        )
    )
    return rows


def _forest_source_rows(
    omit_building: str | None = None,
    omit_buildings: Iterable[str] = (),
) -> list[str]:
    rows = [
        _line("add = {", 1),
        _line('desc = "BUILDING_LEVEL_BASE_FOREST"', 2),
        _line("if = {", 2),
        _line("limit = { has_variable = pp_forest_base_capacity }", 3),
        _line("value = var:pp_forest_base_capacity", 3),
        _line("}", 2),
        _line("else = { value = pp_forest_base_capacity_value }", 2),
        _line("}", 1),
        _line("if = {", 1),
        _line("limit = { has_variable = pp_forest_base_capacity }", 2),
        _line("add = {", 2),
        _line('desc = "BUILDING_LEVEL_RGO_SIZE_FOREST"', 3),
        _line("value = var:pp_forest_base_capacity", 3),
        _line("multiply = max_rgo_workers", 3),
        _line("multiply = 0.040", 3),
        _line("}", 2),
        _line("}", 1),
        _line("if = {", 1),
        _line("limit = { has_town_rights = town_rights_type:manorial_customals }", 2),
        _line("add = {", 2),
        _line('desc = "BUILDING_LEVEL_FOREST_MANORIAL_CUSTOMALS"', 3),
        _line("value = 1", 3),
        _line("}", 2),
        _line("}", 1),
    ]
    for rank, value in (("megalopolis", "-20"), ("city", "-5"), ("town", "-1")):
        rows.extend(
            [
                _line("if = {", 1),
                _line(f"limit = {{ location_rank = location_rank:{rank} }}", 2),
                _line("add = {", 2),
                _line('desc = "BUILDING_LEVEL_FOREST_LOCATION_RANK"', 3),
                _line(f"value = {value}", 3),
                _line("}", 2),
                _line("}", 1),
            ]
        )
    rows.extend(
        _capacity_building_subtract_rows(
            prefix="FOREST",
            buildings=FOREST_CAP_BUILDINGS,
            omit_building=omit_building,
            omit_buildings=omit_buildings,
        )
    )
    rows.extend(_building_level_pressure_rows(prefix="FOREST"))
    return rows


def _generated_header(scope: str) -> str:
    return "\n".join(
        (
            f"# Generated by scripts/generate_rural_capacity_values.py for {scope}.",
            "# Keep these values flat: EU5 displays scripted-value rows in building",
            "# max-level tooltips, and nested helpers create confusing extra rows.",
            "",
        )
    )


def _capacity_file(
    *,
    value_name: str,
    max_prefix: str,
    buildings: Iterable[str],
    source_rows,
    scope: str,
    max_omitted_buildings=None,
) -> str:
    parts = [
        _generated_header(scope),
        _script_value(
            value_name,
            source_rows(),
            (
                "Public remaining-capacity path for map modes and new-building gates.",
                "Capacity buildings subtract their levels directly from this sum.",
            ),
        ),
        "",
        "# Per-building max-level paths. Each one is the same flat capacity sum",
        "# but omits that building's own capacity-consumption row.",
    ]
    if max_omitted_buildings is not None:
        parts.append("# Selected upgrade targets also omit replaceable lower-tier rows.")
    for building in buildings:
        omitted_buildings = (
            max_omitted_buildings(building)
            if max_omitted_buildings is not None
            else (building,)
        )
        parts.extend(
            (
                "",
                _script_value(
                    f"{max_prefix}_{building}",
                    source_rows(omit_building=building, omit_buildings=omitted_buildings),
                ),
            )
        )
    return "\n".join(parts).rstrip() + "\n"


def _culling_effects_file() -> str:
    """One culling call per land, fish and forest capacity building (the order of the capacity tuples), plus the
    helper that removes a level while a building stands above its maximum."""
    lines = [
        "# Prosper or Perish - shared building capacity culling helpers",
        "",
        "pp_cull_capacity_buildings_over_max_v2_effect = {",
        _line("every_owned_location = {", 1),
    ]
    groups = (
        ("Land farm capacity", "farm_capacity_max", LAND_FARM_BUILDINGS),
        ("Fish capacity", "fish_capacity_max", FISH_CAP_BUILDINGS),
        ("Forest capacity", "forest_capacity_max", FOREST_CAP_BUILDINGS),
    )
    for index, (title, prefix, buildings) in enumerate(groups):
        if index:
            lines.append("")
        lines.append(_line(f"# {title}", 2))
        lines.extend(
            _line(f"pp_cull_capacity_building_above_max = {{ building = {building} max_level = {prefix}_{building} }}", 2)
            for building in buildings
        )
    # Victuals packing and serving (caps from worldbuilder/market_capacity.py): the Victualling Yard's cap is 0 off
    # harbour sites, the Grange's off province capitals and the Tavern's off town-or-larger province capitals
    # (2026-10-01), so these also clear buildings in the wrong kind of location.
    lines.append("")
    lines.append(_line("# Victuals packing and serving", 2))
    lines.extend(
        _line(f"pp_cull_capacity_building_above_max = {{ building = {building} max_level = {building}_max_level }}", 2)
        for building in ("victualling_yard", "grange", "tavern")
    )
    lines.extend(
        [
            _line("}", 1),
            "}",
            "",
            "pp_cull_capacity_building_above_max = {",
            _line("if = {", 1),
            _line("limit = {", 2),
            _line("has_building = building_type:$building$", 3),
            _line("location_building_level = {", 3),
            _line("building_type = building_type:$building$", 4),
            _line("value > $max_level$", 4),
            _line("}", 3),
            _line("}", 2),
            *(
                [
                    _line("# Debug flag: scripted cull, counted per location (save) and logged from the building's scope before the", 2),
                    _line("# level change (the log text reaches the building through THIS). Log fields: kind;date;owner tag;", 2),
                    _line("# location id;building;level before the cull.", 2),
                    _line("if = { limit = { has_variable = pp_dbg_script_cull } change_variable = { name = pp_dbg_script_cull add = 1 } } else = { set_variable = { name = pp_dbg_script_cull value = 1 } }", 2),
                    _line("random_buildings_in_location = {", 2),
                    _line("limit = { building_type = building_type:$building$ }", 3),
                    _line(f'error_log = "PPBLD;capacity_cull;{CULL_LOG_FIELDS}"', 3),
                    _line("}", 2),
                ]
                if CULL_DEBUG
                else []
            ),
            _line("change_building_level_in_location = {", 2),
            _line("building = building_type:$building$", 3),
            _line("value = -1", 3),
            _line("}", 2),
            _line("}", 1),
            "}",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    farm_max_omissions = capacity_max_omitted_buildings_by_building(
        blueprint_root=BUILDING_BLUEPRINT_ROOT,
        capacity_buildings=LAND_FARM_BUILDINGS,
    )
    fish_max_omissions = capacity_max_omitted_buildings_by_building(
        blueprint_root=BUILDING_BLUEPRINT_ROOT,
        capacity_buildings=FISH_CAP_BUILDINGS,
    )
    forest_max_omissions = capacity_max_omitted_buildings_by_building(
        blueprint_root=BUILDING_BLUEPRINT_ROOT,
        capacity_buildings=FOREST_CAP_BUILDINGS,
    )
    _set_farm_families(farm_max_omissions)
    outputs = {
        "pp_farming_capacity.txt": _capacity_file(
            value_name="farm_capacity",
            max_prefix="farm_capacity_max",
            buildings=LAND_FARM_BUILDINGS,
            source_rows=_farm_source_rows,
            scope="farming",
            max_omitted_buildings=farm_max_omissions.__getitem__,
        ),
        "pp_fishing_capacity.txt": _capacity_file(
            value_name="fish_capacity",
            max_prefix="fish_capacity_max",
            buildings=FISH_CAP_BUILDINGS,
            source_rows=_fish_source_rows,
            scope="fishing",
            max_omitted_buildings=fish_max_omissions.__getitem__,
        ),
        "pp_forest_capacity.txt": _capacity_file(
            value_name="forest_capacity",
            max_prefix="forest_capacity_max",
            buildings=FOREST_CAP_BUILDINGS,
            source_rows=_forest_source_rows,
            scope="forest",
            max_omitted_buildings=forest_max_omissions.__getitem__,
        ),
    }
    outputs["pp_farming_capacity.txt"] += (
        "\n# Tooltip helpers of the farm max levels: each is one row, read through this. (one number in the tooltip).\n\n"
        + "\n\n".join(FARM_HELPERS[name] for name in sorted(FARM_HELPERS)) + "\n"
    )
    for filename, text in outputs.items():
        (SCRIPT_VALUES_ROOT / filename).write_text(text, encoding="utf-8-sig")
    CULLING_EFFECTS_PATH.write_text(_culling_effects_file(), encoding="utf-8-sig", newline="\n")
    FARM_LAND_TRIGGERS_PATH.parent.mkdir(parents=True, exist_ok=True)
    FARM_LAND_TRIGGERS_PATH.write_text(_farm_land_triggers_file(), encoding="utf-8-sig", newline="\n")


if __name__ == "__main__":
    main()
