"""How much of the world's possible land improvement stands, per save (run report, 2026-10-28, Jan: to calibrate the
improvement costs).

The improvements are the World Builder capacity buildings (``arable_land_bar.model``: a ``pp_wb_cap_*`` max level and
land per level in ``raw_modifier local_population_capacity``), grouped by the cap they share (a unit: one building, or
the members of a shared cap, whose levels the cap holds together; a later tier upgrades the levels of the one it
replaces, so a unit's cap in levels does not depend on the tiers).

A unit's cap in a location, in levels, is the game's max-level script value (``pp_wb_building_caps.txt``, written by
``ppc worldbuilder apply`` from the handover's ``cap_equation_json``): base levels + the location's attribute class
terms (climate, vegetation, topography, fertility) + levels per development point x development, clamped at the level
limit, floored as the engine floors max_levels, never below 0, and 0 where no member's location gate passes. Base and
class terms are fixed per location (``RoomModel.locations``); development is the save's, so the cap is evaluated per
save in one vectorised step.

Per location and unit: built = the members' standing levels, possible = max(0, cap - built), total = built + possible
(where development fell below what stands, what stands counts). Land, in capacity units (1 = 1,000 people): total =
cap x the land per level of the best member "at full research" there: the best generally available member whose
location gate passes, or a member standing there; possible = max(0, total land - built land): new levels and the
upgrade of the standing ones. Only owned locations count.

Generally available (2026-10-28, Jan): a member without an unlocking advance or with one in a general advance file. A
regional member, whose every unlocking advance sits in a culture, country, region, religion, government or estate file
(the Andean incamisana, Vijayanagara's bunds, the Netherlandish polders), or a niche member locked to a culture (its
``lock`` or a culture condition in its gate: the Khmer baray, the Jiangnan works), counts only where it stands: a
member most owners can never research would value every irrigable location at its land. A location where only such
members may stand has no land to add until one stands there.

Gates are the buildings' ``location_potential`` as the World Builder stage writes them: the handover's gate rules per
class (OR of ANDs over attribute classes), with the sea coast where the mod's setup places ``pp_wb_coastal``; a niche
member (``[worldbuilder.buildings.niche]``) adds its structured gate to its family's. Culture conditions are left out:
no snapshot keeps a location's culture (only the Jiangnan works and the Khmer baray have them).
"""

from __future__ import annotations

import json
import re
import tomllib
from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import polars as pl
from eu5gameparser.clausewitz.parser import parse_file
from eu5gameparser.clausewitz.syntax import CList

from prosper_or_perish_constructor import arable_land_bar

SETUP_MODIFIERS = Path("main_menu/setup/1337/21_pp_wb_attribute_modifiers.txt")   # worldbuilder.modifiers writes it
SEA_COAST = "pp_wb_coastal"
# conditions no snapshot can check: a location's culture changes and the dataset does not keep it
UNCHECKED = frozenset({"culture"})
EPSILON = 1e-9   # the engine floors max_levels; a sum like 9.99999999 is 10 (buildings.cap_levels)
SUMS = ("built", "possible", "total", "over_cap", "built_land", "possible_land", "total_land")
ADVANCES = Path("in_game/common/advances")
# advance files only some countries can research (culture_andean.txt, country_vij.txt, region_iberia.txt, ...)
REGIONAL_ADVANCES = ("culture_", "country_", "region_", "religion_", "government_", "estate_")


@dataclass(frozen=True)
class Unit:
    equation: str               # the script value the members' max levels add (the arable land bar's unit)
    limit: int                  # level limit (the World Builder's, x the level scale)
    members: tuple[str, ...]


@dataclass
class RoomModel:
    units: list[Unit]
    members: pl.DataFrame       # building_type, unit, land (capacity units per level)
    member_gates: pl.DataFrame  # location_tag, building_type: where the member's location gate passes
    # location_tag, unit, base (levels at development 0: base + class terms), slope (levels per development point),
    # limit, best_land (the most land per level a generally available member may give there, 0 if none); only where a
    # member may stand
    locations: pl.DataFrame
    restricted: frozenset[str] = field(default_factory=frozenset)  # members that count only where they stand


def unlocking_files(roots: Iterable[Path], keys: Collection[str]) -> dict[str, set[str]]:
    """Building -> the advance files (stems) whose advances unlock it, as the game loads them from ``roots`` (vanilla's
    game folder, then the mod): a mod file of the same name replaces vanilla's, files load in one sorted order, the
    first definition of an advance wins, a REPLACE gives it new unlocks and an INJECT adds unlocks (the advance keeps
    the file it was defined in)."""
    files: dict[str, Path] = {}
    for root in roots:
        files.update({p.name: p for p in sorted((Path(root) / ADVANCES).glob("*.txt"))})
    advances: dict[str, tuple[str, set[str]]] = {}   # advance -> (its file, the buildings it unlocks)
    for name in sorted(files):
        for entry in parse_file(files[name]).entries:
            if not isinstance(entry.value, CList):
                continue
            prefix, _, key = str(entry.key).rpartition(":")
            unlocks = {str(v) for v in entry.value.values("unlock_building")}
            if key not in advances:
                if prefix in ("", "REPLACE_OR_CREATE", "INJECT_OR_CREATE"):
                    advances[key] = (Path(name).stem, unlocks)
            elif prefix.endswith("REPLACE") or prefix == "REPLACE_OR_CREATE":
                advances[key] = (advances[key][0], unlocks)
            elif prefix.endswith("INJECT") or prefix == "INJECT_OR_CREATE":
                advances[key][1].update(unlocks)
    found: dict[str, set[str]] = {}
    for stem, unlocks in advances.values():
        for building in unlocks & set(keys):
            found.setdefault(building, set()).add(stem)
    return found


def regional(unlocks: Mapping[str, set[str]]) -> set[str]:
    """The buildings whose every unlocking advance sits in a regional advance file (REGIONAL_ADVANCES)."""
    return {key for key, stems in unlocks.items() if stems and all(s.startswith(REGIONAL_ADVANCES) for s in stems)}


def culture_locked(niche: Mapping[str, Mapping[str, Any]]) -> set[str]:
    """Niche members locked to a culture: a ``lock`` or a culture condition in their structured gate."""
    return {key for key, spec in niche.items()
            if spec.get("lock") or any(UNCHECKED & set(rule) for rule in spec.get("gate") or [])}


def unit_label(unit: str) -> str:
    """Display name of a unit: pp_wb_cap_water_control_shared -> Water control."""
    name = unit.removeprefix("pp_wb_cap_").removesuffix("_shared").removesuffix("_terms")
    return name.replace("_", " ").capitalize()


def _text(column: str) -> pl.Expr:
    # CSV booleans and the coast override compare case-insensitively, as buildings.gate_matches does
    return pl.col(column).cast(pl.String).str.to_lowercase()


def gate_expr(rules: list[dict[str, list[str]]], columns: set[str]) -> pl.Expr:
    """A World Builder gate (OR of ANDs over attribute classes; none = everywhere) as a Polars expression over the
    attribute columns; culture conditions hold (UNCHECKED), an attribute the frame lacks fails like a missing key."""
    if not rules:
        return pl.lit(True)
    ors = []
    for rule in rules:
        ands = [(_text(attribute).is_in([str(v).lower() for v in allowed]).fill_null(False) if attribute in columns
                 else pl.lit(False))
                for attribute, allowed in rule.items() if attribute not in UNCHECKED]
        ors.append(pl.all_horizontal(ands) if ands else pl.lit(True))
    return pl.any_horizontal(ors)


def levels_expr(equation: Mapping[str, Any], scale: float, columns: set[str]) -> pl.Expr:
    """Base + the matching class terms (levels at development 0), rounded as the script writes them (two decimals)."""
    by_attribute: dict[str, dict[str, float]] = {}
    for term in equation["class_terms"]:
        levels = round(float(term["levels"]) * scale, 2)
        if levels:
            values = by_attribute.setdefault(str(term["attribute"]), {})
            values[str(term["value"]).lower()] = values.get(str(term["value"]).lower(), 0.0) + levels
    expr = pl.lit(round(float(equation["base_levels"]) * scale, 2))
    for attribute, values in by_attribute.items():
        if attribute not in columns:
            raise ValueError(f"cap equation tests {attribute!r}, which the location attributes lack")
        expr = expr + _text(attribute).replace_strict(values, default=0.0, return_dtype=pl.Float64).fill_null(0.0)
    return expr


def build_model(bar: arable_land_bar.Model, building_map: Mapping[str, str], niche: Mapping[str, Mapping[str, Any]],
                building_types: pl.DataFrame, attributes: pl.DataFrame, *, level_scale: Mapping[str, float] | None = None,
                level_limit: int = 15, restricted: Collection[str] = ()) -> RoomModel:
    """The caps per location: ``bar`` the improvement units, ``building_map`` World Builder class -> blueprint key,
    ``niche`` the niche members (family, structured gate), ``building_types`` the handover's (building, level_limit,
    gate_json, cap_equation_json), ``attributes`` one row per location (location_tag + attribute classes) and
    ``restricted`` the members that give their land only where they stand (regional unlocks, culture locks)."""
    scale_of = dict(level_scale or {})
    kind_of = {key: kind for kind, key in building_map.items()}
    rows = {str(r["building"]): r for r in building_types.iter_rows(named=True)}
    order = list(rows)
    gates = {kind: json.loads(str(row["gate_json"])) for kind, row in rows.items()}
    columns = set(attributes.columns)
    units, members, member_gates, locations = [], [], [], []
    for bar_unit in bar.units:
        keys = [b.key for b in bar_unit.members]
        kinds = sorted({kind_of[k] for k in keys if k in kind_of}, key=order.index)
        if not kinds:
            raise ValueError(f"{bar_unit.equation}: no World Builder class maps to {', '.join(keys)}")
        # a shared cap's equation is its first class's (buildings.write_caps writes the group's terms once)
        kind = kinds[0]
        scale = float(scale_of.get(building_map[kind], scale_of.get(kind, 1.0)))
        equation = json.loads(str(rows[kind]["cap_equation_json"]))
        limit = int(round(int(rows[kind].get("level_limit") or level_limit) * scale))
        unit = Unit(bar_unit.equation, limit, tuple(keys))
        units.append(unit)
        gate_columns = []
        for building in bar_unit.members:
            members.append({"building_type": building.key, "unit": unit.equation, "land": float(building.land)})
            if building.key in kind_of:
                gate = gate_expr(gates[kind_of[building.key]], columns)
            elif building.key in niche and str(niche[building.key]["family"]) in kind_of:
                spec = niche[building.key]
                gate = gate_expr(gates[kind_of[str(spec["family"])]], columns) & gate_expr(list(spec.get("gate") or []), columns)
            else:
                raise ValueError(f"{building.key}: neither a mapped World Builder class nor a niche member")
            gate_columns.append(gate.alias(building.key))
        frame = attributes.select(
            "location_tag",
            levels_expr(equation, scale, columns).alias("base"),
            pl.lit(round(float(equation["levels_per_development_point"]) * scale, 4)).alias("slope"),
            *gate_columns,
        )
        passing = (frame.unpivot(index="location_tag", on=list(keys), variable_name="building_type", value_name="gate")
                   .filter(pl.col("gate")).select("location_tag", "building_type"))
        member_gates.append(passing)
        # the cap stands where any member may stand; its land at full research comes from the generally available ones
        land = {b.key: float(b.land) for b in bar_unit.members}
        best = (passing.filter(~pl.col("building_type").is_in(sorted(restricted)))
                .with_columns(pl.col("building_type").replace_strict(land, return_dtype=pl.Float64).alias("land"))
                .group_by("location_tag").agg(pl.col("land").max().alias("best_land")))
        locations.append(frame.select("location_tag", "base", "slope")
                         .join(passing.select("location_tag").unique(), on="location_tag", how="semi")
                         .join(best, on="location_tag", how="left")
                         .with_columns(pl.col("best_land").fill_null(0.0), pl.lit(unit.equation).alias("unit"),
                                       pl.lit(float(limit)).alias("limit")))
    return RoomModel(
        units=units,
        members=pl.DataFrame(members, schema={"building_type": pl.String, "unit": pl.String, "land": pl.Float64}),
        member_gates=pl.concat(member_gates),
        locations=pl.concat(locations).select("location_tag", "unit", "base", "slope", "limit", "best_land"),
        restricted=frozenset(restricted),
    )


def setup_sea_coast(mod_root: Path) -> set[str] | None:
    """Locations the mod's setup gives the Sea Coast modifier (what the gates test), None without the setup file."""
    path = Path(mod_root) / SETUP_MODIFIERS
    if not path.is_file():
        return None
    return {m[1] for m in re.finditer(r"(?ms)^\t(\w+) = \{(.*?)^\t\}", path.read_text(encoding="utf-8-sig"))
            if f'"{SEA_COAST}"' in m[2]}


def load_model(repo: Path, project: Path) -> RoomModel:
    """The model of the built mod (its improvement buildings and setup) and the World Builder handover it was built from."""
    from prosper_or_perish_constructor.cap_tooltips import game_root
    from prosper_or_perish_constructor.worldbuilder.contract import load_config, load_contract
    from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

    configured = Path(str(tomllib.loads(project.read_text(encoding="utf-8"))["project"]["mod_root"]))
    mod_root = configured if configured.is_absolute() else repo / configured
    cfg = load_config(repo, project)
    contract = load_contract(cfg.handover)
    game = game_root(vanilla_root(repo, project))
    bar = arable_land_bar.model(mod_root, game)
    attributes = contract.location_attributes
    coast = setup_sea_coast(mod_root)
    if coast is not None and "is_coastal" in attributes.columns:
        attributes = attributes.with_columns(pl.col("location_tag").is_in(sorted(coast)).cast(pl.String).alias("is_coastal"))
    keys = {b.key for unit in bar.units for b in unit.members}
    restricted = regional(unlocking_files([game, mod_root], keys)) | culture_locked(cfg.niche)
    return build_model(bar, cfg.building_map, cfg.niche, contract.building_types, attributes,
                       level_scale=cfg.level_scale, level_limit=cfg.level_limit, restricted=restricted & keys)


def location_caps(model: RoomModel, locations: pl.DataFrame, unit: str | None = None) -> pl.DataFrame:
    """snapshot_id, slug, unit, cap (levels), best_land for ``locations`` (snapshot_id, slug, development), every unit
    or one; locations where no member may stand have no row (cap 0)."""
    static = model.locations if unit is None else model.locations.filter(pl.col("unit") == unit)
    return (
        locations.select("snapshot_id", "slug", "development")
        .join(static, left_on="slug", right_on="location_tag", how="inner")
        .with_columns(
            (pl.min_horizontal(pl.col("base") + pl.col("slope") * pl.col("development").fill_null(0.0), pl.col("limit"))
             + EPSILON).floor().clip(lower_bound=0.0).alias("cap"))
        .select("snapshot_id", "slug", "unit", "cap", "best_land")
    )


def room(model: RoomModel, locations: pl.DataFrame, buildings: pl.DataFrame) -> pl.DataFrame:
    """Per save and unit: built, possible, total and over-cap levels, and built, possible and total land.

    ``locations``: snapshot_id, slug, owner, development (one row per location and save); ``buildings``: snapshot_id,
    location_slug, building_type, level. Only owned locations count. One unit at a time (a whole run at once is millions
    of location rows)."""
    owned = locations.filter(pl.col("owner").is_not_null() & (pl.col("owner") > 0)).select("snapshot_id", "slug", "development")
    standing = (
        buildings.select("snapshot_id", pl.col("location_slug").alias("slug"), "building_type", "level")
        .join(model.members, on="building_type", how="inner")
        .join(owned.select("snapshot_id", "slug"), on=["snapshot_id", "slug"], how="semi")
        .group_by("snapshot_id", "slug", "unit")
        .agg(pl.col("level").sum().alias("built"), (pl.col("level") * pl.col("land")).sum().alias("built_land"),
             pl.col("land").max().alias("standing_land"))
    )
    keys = ["snapshot_id", "slug", "unit"]
    parts = []
    for unit in model.units:
        rows = (
            location_caps(model, owned, unit.equation)
            .join(standing.filter(pl.col("unit") == unit.equation), on=keys, how="full", coalesce=True)
            .with_columns(pl.col(c).fill_null(0.0) for c in ("cap", "best_land", "built", "built_land", "standing_land"))
            .with_columns(
                pl.max_horizontal("cap", "built").alias("total"),
                (pl.col("built") - pl.col("cap")).clip(lower_bound=0.0).alias("over_cap"),
                # a member standing there gives its land: a regional or culture-locked one too (and one the gates say
                # cannot stand there, a coast the setup moved)
                pl.max_horizontal(pl.col("cap") * pl.max_horizontal("best_land", "standing_land"), "built_land").alias("total_land"),
            )
            .with_columns((pl.col("total") - pl.col("built")).alias("possible"),
                          (pl.col("total_land") - pl.col("built_land")).alias("possible_land"))
            .group_by("snapshot_id", "unit").agg(pl.col(c).sum() for c in SUMS)
        )
        parts.append(rows)
    return pl.concat(parts).sort("snapshot_id", "unit") if parts else pl.DataFrame()


def world(frame: pl.DataFrame) -> pl.DataFrame:
    """The units summed per save (snapshot_id + SUMS)."""
    return frame.group_by("snapshot_id").agg(pl.col(c).sum() for c in SUMS)
