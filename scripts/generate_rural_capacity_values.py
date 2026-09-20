"""Generate flat rural-capacity scripted values.

The generated files intentionally duplicate formula rows for each building's
max-level path. EU5 exposes the scripted-value rows directly in the building
max-level tooltip, so nested helper values make the UI misleading.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from prosper_or_perish_constructor.rural_capacity import (
    FARM_WATER_CONTROL_BUILDINGS,
    FISH_CAP_BUILDINGS,
    FOREST_CAP_BUILDINGS,
    LAND_FARM_BUILDINGS,
    capacity_max_omitted_buildings_by_building,
    farm_capacity_modifier_for_building,
)


ROOT = Path(__file__).resolve().parents[1]
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_VALUES_ROOT = MOD_ROOT / "in_game" / "common" / "script_values"
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


def _farm_modifier_rows(
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
            [
                _line("add = {", 1),
                _line(f'desc = "BUILDING_LEVEL_{prefix}_{building.upper()}"', 2),
                _line(f"value = modifier:{farm_capacity_modifier_for_building(building)}", 2),
                _line("}", 1),
            ]
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


def _free_land_rows(land: float, reserve: float, desc: str) -> list[str]:
    return [
        _line("add = {", 1),
        _line(f'desc = "{desc}"', 2),
        _line("value = modifier:local_population_capacity", 2),
        _line(f"subtract = {reserve:g}", 2),
        _line(f"divide = {land:g}", 2),
        _line("floor = yes", 2),
        _line("}", 1),
    ]


def _farm_source_rows(
    omit_building: str | None = None,
    omit_buildings: Iterable[str] = (),
) -> list[str]:
    """Farm capacity = remaining farmland: (flat population capacity - reserve) / land per level.

    The flat already contains -land per built farm level (raw_modifier on each farm building), so the
    public value is the land still held by subsistence farmers in farming-village levels. Per-building
    max values add the building's own levels back (its level counter modifier is -1 per level) so the
    max is the same number no matter how many of it exist; replaceable lower tiers are added back too.
    """
    per_building, default = _farm_land_constants()
    # ordered: the building whose max this is comes first (its own land constants apply), then replaceable tiers
    omitted = list(dict.fromkeys([*([omit_building] if omit_building is not None else []), *omit_buildings]))
    if not omitted:
        land, reserve = default
        return _free_land_rows(land, reserve, "BUILDING_LEVEL_WB_FREE_FARMLAND") + [_line("min = 0", 1)]
    target = omitted[0]
    land, reserve = per_building.get(target, default)
    rows = _free_land_rows(land, reserve, "BUILDING_LEVEL_WB_FREE_FARMLAND")
    for building in omitted:
        rows.extend(
            [
                _line("subtract = {", 1),
                _line(f'desc = "BUILDING_LEVEL_FARM_{building.upper()}"', 2),
                _line(f"value = modifier:{farm_capacity_modifier_for_building(building)}", 2),
                _line("}", 1),
            ]
        )
    rows.append(_line("min = 0", 1))
    return rows


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
        _line("else = { value = 0 }", 2),
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
    for filename, text in outputs.items():
        (SCRIPT_VALUES_ROOT / filename).write_text(text, encoding="utf-8-sig")


if __name__ == "__main__":
    main()
