"""Game-start building placement from the capacity model.

Replaces the food startup compiler (savegame-driven planner + split_pop on_action) and the error-log driven
setup corrections with one offline pass that only reads files the game reads:

- capacity per location = attribute rows + placed improvement levels + rank flat (the same numbers the caps use);
- pops per location from the vanilla pops setup (type, size, culture, religion);
- owners from the countries setup, ranks from the cities setup, RGO and terrain from the location frame.

Per location: the raw-material building of its RGO (``[worldbuilder.start.processors]``: mines, quarries,
saltworks, lumber mills, fishing and forest villages), then a food farm where the farm gate passes (farming
village, orchard, sheep farm). Farm levels = min(spare land, available peasants, per-location cap) where spare
land = capacity - pops - reserve when ``keep_pops_within_capacity`` is on: a farm never pushes a location over
its cap and over-capacity locations get no farms. Per province, the urban food chain (cookery, victuals
market) is sized to the food the pops need beyond peasant subsistence.

Buildings that employ laborers get them converted from the largest local peasant pop in a regenerated copy of
the pops setup, keeping that pop's culture and religion (the old on_action split pops without culture or
religion, which produced foreign pops). Everything is written as setup data, never as runtime effects.
"""

from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import polars as pl
import yaml

from prosper_or_perish_constructor.worldbuilder.buildings import BLUEPRINTS, GENERATED, SETUP_PATH as IMPROVEMENT_SETUP_PATH, farm_constants
from prosper_or_perish_constructor.worldbuilder.contract import WorldBuilderConfig

START_SETUP_PATH = Path("main_menu/setup/start/14_pp_start_buildings.txt")
POPS_SETUP_PATH = Path("main_menu/setup/start/06_pops.txt")
REPORT_RELATIVE_PATH = Path("artifacts/data/worldbuilder/start_placement.json")
TABLE_RELATIVE_PATH = Path("artifacts/data/worldbuilder/start_placement.csv")
LEGACY_FILES = (
    "in_game/common/on_action/pp_food_building_startup_generated.txt",
    "in_game/common/town_setups/zz_pp_sanitized_start_town_setups.txt",
    "main_menu/setup/start/07_cities_and_buildings.txt",
)
RANK_ORDER = {"megalopolis": 0, "city": 1, "town": 2, "rural_settlement": 3}
FARMABLE_RGOS = {"livestock", "wheat", "legumes", "fruit", "millet", "wool", "rice", "beeswax", "maize", "olives", "potato"}
PASTURE_RGOS = {"livestock", "wool", "horses"}
FARMS = ("farming_village", "fruit_orchard", "sheep_farms")   # peasant farms that take farmland
_POP_RE = re.compile(r"define_pop\s*=\s*\{([^}]*)\}")
_FIELD_RE = re.compile(r"(\w+)\s*=\s*([A-Za-z0-9_.\-]+)")
DEFAULT_PROCESSORS: dict[str, dict[str, Any]] = {
    # raw material -> building placed at game start (levels as the old compiler placed them)
    "alum": {"building": "alum_quarry", "levels": 1},
    "clay": {"building": "clay_pit", "levels": 2},
    "coal": {"building": "coal_mine", "levels": 1},
    "copper": {"building": "copper_mine", "levels": 1},
    "fish": {"building": "fishing_village", "levels": 3},
    "fur": {"building": "forest_village", "levels": 2},
    "gems": {"building": "gem_gravel_pit", "levels": 1},
    "goods_gold": {"building": "gold_diggings", "levels": 1},
    "iron": {"building": "iron_mine", "levels": 2},
    "lead": {"building": "lead_mine", "levels": 1},
    "lumber": {"building": "lumber_mill", "levels": 2},
    "marble": {"building": "marble_quarry", "levels": 1},
    "mercury": {"building": "cinnabar_pit", "levels": 1},
    "salt": {"building": "inland_saltworks", "coastal_building": "salt_collector", "levels": 2},
    "saltpeter": {"building": "saltpeter_beds", "levels": 1},
    "sand": {"building": "sand_pit", "levels": 1},
    "silver": {"building": "silver_mine", "levels": 1},
    "stone": {"building": "stone_quarry", "levels": 1},
    "tin": {"building": "tin_streamworks", "levels": 1},
    "wild_game": {"building": "forest_village", "levels": 2},
}


@dataclass(frozen=True)
class StartConfig:
    """``[worldbuilder.start]`` of constructor.toml (all optional)."""

    keep_pops_within_capacity: bool = True
    fill_improvements_to_pops: bool = True   # raise starting improvement levels to their caps where the pops need the room
    peasant_work_share: float = 0.6
    max_farm_levels_per_location: int = 6
    food_target_ratio: float = 1.1
    subsistence_food_per_1000_peasants: float = 1.0
    max_cookery_levels_per_location: int = 6
    max_market_levels_per_location: int = 3
    laborer_conversion_share: float = 0.5   # share of a location's peasants that may become laborers
    rank_capacity_people: dict[str, float] = field(default_factory=lambda: {"town": 10000.0, "city": 25000.0, "megalopolis": 40000.0})
    processors: dict[str, dict[str, Any]] = field(default_factory=lambda: dict(DEFAULT_PROCESSORS))

    @classmethod
    def from_raw(cls, raw: Mapping[str, Any] | None) -> "StartConfig":
        raw = dict(raw or {})
        kwargs: dict[str, Any] = {}
        for name in ("keep_pops_within_capacity", "fill_improvements_to_pops", "peasant_work_share", "max_farm_levels_per_location", "food_target_ratio",
                     "subsistence_food_per_1000_peasants", "max_cookery_levels_per_location", "max_market_levels_per_location", "laborer_conversion_share"):
            if name in raw:
                kwargs[name] = type(getattr(cls, name))(raw[name])
        if isinstance(raw.get("rank_capacity_people"), dict):
            kwargs["rank_capacity_people"] = {str(k): float(v) for k, v in raw["rank_capacity_people"].items()}
        if isinstance(raw.get("processors"), dict):
            kwargs["processors"] = {str(k): dict(v) for k, v in raw["processors"].items() if isinstance(v, dict) and v.get("building")}
        return cls(**kwargs)


@dataclass
class Pop:
    type: str
    size_k: float
    culture: str
    religion: str


# ------------------------------------------------------------------ inputs

def setup_files(vanilla_root: Path, mod_root: Path, name: str) -> list[Path]:
    """The setup file the game loads for ``name``: the mod's copy if it has one, else vanilla's."""
    for root in (mod_root, Path(vanilla_root) / "game"):
        path = root / "main_menu/setup/start" / name
        if path.is_file():
            return [path]
    return []


def parse_pops(text: str) -> dict[str, list[Pop]]:
    pops: dict[str, list[Pop]] = defaultdict(list)
    current: str | None = None
    for line in text.splitlines():
        stripped = line.split("#", 1)[0].strip()
        if not stripped:
            continue
        head = re.match(r"^([A-Za-z0-9_]+)\s*=\s*\{", stripped)
        if head and head.group(1) not in ("locations", "define_pop"):
            current = head.group(1)
            continue
        if current and stripped.startswith("define_pop"):
            for match in _POP_RE.finditer(stripped):
                fields = dict(_FIELD_RE.findall(match.group(1)))
                try:
                    size = float(fields.get("size", "0"))
                except ValueError:
                    continue
                pops[current].append(Pop(fields.get("type", ""), size, fields.get("culture", ""), fields.get("religion", "")))
    return dict(pops)


def load_pops(vanilla_root: Path) -> dict[str, list[Pop]]:
    """Pops per location from vanilla's pops setup (sizes in thousands); the mod's copy is derived from it."""
    return parse_pops((Path(vanilla_root) / "game" / POPS_SETUP_PATH).read_text(encoding="utf-8-sig"))


def load_owners(vanilla_root: Path, mod_root: Path) -> dict[str, str]:
    """location tag -> owning country tag at game start: the countries setup's capital and own_* location lists.
    add_pops_from_locations is not ownership; buildings placed there are rejected by the game."""
    from eu5gameparser.clausewitz.parser import parse_file
    from eu5gameparser.clausewitz.syntax import CList

    owners: dict[str, str] = {}

    def entries(node):
        for entry in node.entries:
            if entry.key == "countries" and isinstance(entry.value, CList):
                yield from entries(entry.value)
            elif isinstance(entry.value, CList):
                yield entry

    for path in setup_files(vanilla_root, mod_root, "10_countries.txt"):
        document = parse_file(path)
        for countries in document.values("countries"):
            if not isinstance(countries, CList):
                continue
            for country in entries(countries):
                tag = str(country.key)
                for value in country.value.values("capital"):
                    if isinstance(value, str):
                        owners.setdefault(value, tag)
                for entry in country.value.entries:
                    # own_* lists are ownership; add_pops_from_locations only moves pops and must not count
                    if isinstance(entry.value, CList) and str(entry.key).startswith("own_"):
                        for item in entry.value.items:
                            if isinstance(item, str):
                                owners.setdefault(item, tag)
    return owners


_SETUP_ENTRY = re.compile(r"^\s*([A-Za-z0-9_]+)\s*=\s*\{([^{}]*)\}", re.MULTILINE)


def _top_level_block(text: str, name: str) -> str:
    """Body of the top-level ``name = { ... }`` block (brace-matched), or an empty string."""
    m = re.search(rf"^\s*{name}\s*=\s*\{{", text, re.MULTILINE)
    if not m:
        return ""
    depth, start = 1, m.end()
    for i in range(start, len(text)):
        depth += (text[i] == "{") - (text[i] == "}")
        if depth == 0:
            return text[start:i]
    return text[start:]


def _cities_text(vanilla_root: Path, mod_root: Path) -> str:
    return "\n".join(re.sub(r"#.*", "", path.read_text(encoding="utf-8-sig")) for path in setup_files(vanilla_root, mod_root, "07_cities_and_buildings.txt"))


def load_ranks(vanilla_root: Path, mod_root: Path) -> dict[str, str]:
    """``locations = { tag = { rank = town town_setup = ... } }`` (one entry per line in vanilla)."""
    ranks: dict[str, str] = {}
    for tag, body in _SETUP_ENTRY.findall(_top_level_block(_cities_text(vanilla_root, mod_root), "locations")):
        m = re.search(r"\brank\s*=\s*([a-z_]+)", body)
        if m:
            ranks[tag] = m.group(1)
    return ranks


def load_existing_buildings(vanilla_root: Path, mod_root: Path) -> set[tuple[str, str]]:
    """(location, building) pairs the cities setup already places (``building_manager``; no double placement)."""
    found: set[tuple[str, str]] = set()
    for building, body in _SETUP_ENTRY.findall(_top_level_block(_cities_text(vanilla_root, mod_root), "building_manager")):
        m = re.search(r"\blocation\s*=\s*([A-Za-z0-9_]+)", body)
        if m:
            found.add((m.group(1), building))
    return found


def load_pop_food_consumption(vanilla_root: Path, mod_root: Path) -> dict[str, float]:
    """pop type -> monthly food per 1,000 pops: vanilla pop_types plus the mod's TRY_INJECT overrides."""
    values: dict[str, float] = {}
    for folder in (Path(vanilla_root) / "game/in_game/common/pop_types", mod_root / "in_game/common/pop_types"):
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.txt")):
            current: str | None = None
            for raw in path.read_text(encoding="utf-8-sig").splitlines():
                line = raw.split("#", 1)[0].strip()
                head = re.match(r"^(?:TRY_INJECT:|TRY_REPLACE:|REPLACE:|INJECT:)?([a-z_]+)\s*=\s*\{", line)
                if head:
                    current = head.group(1)
                    continue
                m = re.match(r"^pop_food_consumption\s*=\s*(-?\d+(?:\.\d+)?)", line)
                if m and current:
                    values[current] = float(m.group(1))
    return values


def blueprint_numbers(repo: Path, key: str) -> dict[str, Any]:
    """employment_size, local_monthly_food and pop_type of a blueprint (vanilla-only buildings: laborers, 1.0)."""
    out: dict[str, Any] = {"employment_size": 1.0, "local_monthly_food": 0.0, "pop_type": "laborers"}
    path = repo / BLUEPRINTS / f"{key}.yml"
    if not path.is_file():
        return out
    body = str(yaml.safe_load(path.read_text(encoding="utf-8-sig"))["building"]["body"])
    m = re.search(r"^\s*employment_size\s*=\s*([0-9.]+)", body, re.M)
    if m:
        out["employment_size"] = float(m.group(1))
    m = re.search(r"^\s*local_monthly_food\s*=\s*(-?[0-9.]+)", body, re.M)
    if m:
        out["local_monthly_food"] = float(m.group(1))
    m = re.search(r"^\s*pop_type\s*=\s*([a-z_]+)", body, re.M)
    if m:
        out["pop_type"] = m.group(1)
    return out


def improvement_demand(contract, start: StartConfig, vanilla_root: Path, mod_root: Path) -> dict[str, float]:
    """People per location the improvement buildings must house for the pops at game start to fit: pops minus the
    attribute rows, the rank housing and the development term (only positive values)."""
    ranks = load_ranks(vanilla_root, mod_root)
    pops = {tag: sum(p.size_k for p in ps) * 1000.0 for tag, ps in load_pops(vanilla_root).items()}
    k = contract.people_per_development_point
    demand: dict[str, float] = {}
    for tag, flat, dev in contract.location_targets.select("location_tag", "attribute_flat_people", "development").iter_rows():
        base = float(flat or 0.0) + float(start.rank_capacity_people.get(ranks.get(str(tag), ""), 0.0)) + k * float(dev or 0.0)
        need = pops.get(str(tag), 0.0) - base
        if need > 0:
            demand[str(tag)] = need
    return demand


def improvement_people_by_location(mod_root: Path, caps: Mapping[str, Mapping[str, float]]) -> dict[str, float]:
    """People of capacity from the placed improvement levels (the World Builder setup file)."""
    people: dict[str, float] = defaultdict(float)
    path = mod_root / IMPROVEMENT_SETUP_PATH
    if not path.is_file():
        return {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        m = re.match(r"\s*(\w+) = \{ tag = \w+ level = (\d+) location = (\w+) \}", line)
        if m and m.group(1) in caps:
            people[m.group(3)] += int(m.group(2)) * float(caps[m.group(1)]["unit_units"]) * 1000.0
    return dict(people)


# ------------------------------------------------------------------ gates (mirror the blueprints' location_potential)

def farm_for(loc: Mapping[str, Any]) -> str | None:
    """The peasant farm the location's RGO and vegetation call for (the farming village gate, orchards, pastures)."""
    rgo = str(loc.get("raw_material") or "")
    if rgo == "fruit":
        return "fruit_orchard"
    if rgo == "wool":
        return "sheep_farms"
    if rgo in FARMABLE_RGOS or str(loc.get("vegetation")) == "farmland":
        return "farming_village"
    return None


def processor_for(loc: Mapping[str, Any], processors: Mapping[str, Mapping[str, Any]]) -> tuple[str, int] | None:
    spec = processors.get(str(loc.get("raw_material") or ""))
    if not spec:
        return None
    building = str(spec.get("coastal_building") or spec["building"]) if bool(loc.get("is_coastal")) and spec.get("coastal_building") else str(spec["building"])
    return building, int(spec.get("levels", 1))


# ------------------------------------------------------------------ the plan

@dataclass
class Placement:
    location: str
    owner: str
    building: str
    level: int


@dataclass
class PopConversion:
    location: str
    from_type: str
    to_type: str
    size_k: float
    culture: str
    religion: str


class _Workers:
    """Peasant pool of one location: farms employ peasants, laborer buildings convert them."""

    def __init__(self, pops: list[Pop], start: StartConfig) -> None:
        self.peasant_pops = sorted((p for p in pops if p.type == "peasants"), key=lambda p: -p.size_k)
        peasants = sum(p.size_k for p in self.peasant_pops)
        self.work_k = peasants * start.peasant_work_share
        self.convert_k = peasants * start.laborer_conversion_share
        self.existing = defaultdict(float)
        for p in pops:
            self.existing[p.type] += p.size_k

    def levels(self, wanted: int, employment: float, pop_type: str) -> int:
        if pop_type == "peasants":
            return max(min(wanted, int(math.floor(self.work_k / employment + 1e-9))), 0)
        available = self.existing.get(pop_type, 0.0) + self.convert_k
        return max(min(wanted, int(math.floor(available / employment + 1e-9))), 0)

    def take(self, levels: int, employment: float, pop_type: str, location: str, conversions: list[PopConversion]) -> None:
        needed = levels * employment
        if pop_type == "peasants":
            self.work_k -= needed
            return
        from_existing = min(self.existing.get(pop_type, 0.0), needed)
        self.existing[pop_type] -= from_existing
        needed -= from_existing
        if needed > 1e-9 and self.peasant_pops:
            biggest = self.peasant_pops[0]
            take = round(min(needed, self.convert_k, biggest.size_k * 0.9), 3)
            if take > 0:
                conversions.append(PopConversion(location, "peasants", pop_type, take, biggest.culture, biggest.religion))
                self.convert_k -= take
                self.work_k -= take
                biggest.size_k -= take


def plan(*, cfg: WorldBuilderConfig, start: StartConfig, locations: pl.DataFrame, capacity_people: Mapping[str, float], pops: Mapping[str, list[Pop]],
         owners: Mapping[str, str], ranks: Mapping[str, str], existing: set[tuple[str, str]], food_consumption: Mapping[str, float],
         numbers: Mapping[str, Mapping[str, Any]]) -> tuple[list[Placement], list[PopConversion], pl.DataFrame, dict[str, Any]]:
    placements: list[Placement] = []
    conversions: list[PopConversion] = []
    rows: list[dict[str, Any]] = []
    by_province: dict[str, list[str]] = defaultdict(list)
    pools: dict[str, _Workers] = {}
    for loc in locations.iter_rows(named=True):
        tag = str(loc["location_tag"])
        owner = owners.get(tag)
        if not owner:
            continue
        province = str(loc.get("province") or "")
        by_province[province].append(tag)
        local = [Pop(p.type, p.size_k, p.culture, p.religion) for p in pops.get(tag, [])]
        pool = _Workers(local, start)
        pools[tag] = pool
        pops_k = sum(p.size_k for p in local)
        cap = float(capacity_people.get(tag, 0.0))
        occupied = pops_k * 1000.0 if start.keep_pops_within_capacity else 0.0
        row: dict[str, Any] = {"location_tag": tag, "province": province, "owner": owner, "rank": ranks.get(tag, "rural_settlement"), "rgo": str(loc.get("raw_material") or ""),
                               "capacity_people": cap, "pops_people": pops_k * 1000.0, "over_capacity": pops_k * 1000.0 > cap, "processor": "", "processor_levels": 0,
                               "farm": "", "farm_levels": 0, "land_levels_available": 0, "farm_land_people": 0.0, "farm_limit": ""}
        # 1. the raw-material building
        proc = processor_for(loc, start.processors)
        if proc and (tag, proc[0]) not in existing:
            building, wanted = proc
            num = numbers.get(building) or {"employment_size": 1.0, "pop_type": "laborers"}
            emp, pop_type = float(num["employment_size"]) or 1.0, str(num["pop_type"])
            levels = pool.levels(wanted, emp, pop_type)
            row["processor"], row["processor_levels"] = building, levels
            if levels > 0:
                placements.append(Placement(tag, owner, building, levels))
                pool.take(levels, emp, pop_type, tag, conversions)
        # 2. the farm (takes farmland)
        farm = farm_for(loc)
        if farm and (tag, farm) not in existing:
            num = numbers[farm]
            emp = float(num["employment_size"]) or 1.0
            land, reserve = farm_constants(cfg, farm)
            land_levels = int(math.floor(((cap - occupied) / 1000.0 - reserve) / land + 1e-9))
            worker_levels = pool.levels(start.max_farm_levels_per_location, emp, "peasants")
            levels = max(min(land_levels, worker_levels), 0)
            row["farm"], row["farm_levels"], row["land_levels_available"] = farm, levels, max(land_levels, 0)
            row["farm_limit"] = "land" if land_levels <= worker_levels else ("workers" if worker_levels < start.max_farm_levels_per_location else "cap")
            if levels > 0:
                placements.append(Placement(tag, owner, farm, levels))
                pool.take(levels, emp, "peasants", tag, conversions)
                row["farm_land_people"] = levels * land * 1000.0
        rows.append(row)
    table = pl.DataFrame(rows)

    # 3. the urban food chain per province
    cookery, market = numbers["cookery"], numbers["victuals_market_import"]
    cookery_food, market_food = float(cookery["local_monthly_food"]), float(market["local_monthly_food"])
    cookery_emp, cookery_pop = float(cookery["employment_size"]) or 1.0, str(cookery["pop_type"])
    market_emp, market_pop = float(market["employment_size"]) or 0.001, str(market["pop_type"])
    province_rows: list[dict[str, Any]] = []
    for province, tags in by_province.items():
        demand = sum(p.size_k * float(food_consumption.get(p.type, 0.0)) for t in tags for p in pops.get(t, []))
        subsistence = sum(p.size_k for t in tags for p in pops.get(t, []) if p.type == "peasants") * start.subsistence_food_per_1000_peasants
        need = demand * start.food_target_ratio - subsistence
        cookery_levels = market_levels = 0
        if need > 0 and cookery_food > 0:
            candidates = sorted(tags, key=lambda t: (RANK_ORDER.get(ranks.get(t, "rural_settlement"), 3), -sum(p.size_k for p in pops.get(t, []))))
            remaining = need
            for tag in candidates:
                if remaining <= 0:
                    break
                levels = pools[tag].levels(min(start.max_cookery_levels_per_location, int(math.ceil(remaining / cookery_food))), cookery_emp, cookery_pop)
                if levels <= 0:
                    continue
                placements.append(Placement(tag, owners[tag], "cookery", levels))
                pools[tag].take(levels, cookery_emp, cookery_pop, tag, conversions)
                remaining -= levels * cookery_food
                cookery_levels += levels
            if remaining > 0 and market_food > 0:
                capital = candidates[0]
                levels = min(start.max_market_levels_per_location, int(math.ceil(remaining / market_food)))
                if levels > 0:
                    placements.append(Placement(capital, owners[capital], "victuals_market_import", levels))
                    pools[capital].take(levels, market_emp, market_pop, capital, conversions)
                    market_levels = levels
        supply = subsistence + cookery_levels * cookery_food + market_levels * market_food
        province_rows.append({"province": province, "demand": demand, "subsistence": subsistence, "cookery_levels": cookery_levels, "market_levels": market_levels, "coverage": (supply / demand) if demand else 1.0})
    provinces = pl.DataFrame(province_rows) if province_rows else pl.DataFrame({"province": [], "coverage": []})
    by_building: dict[str, int] = defaultdict(int)
    for p in placements:
        by_building[p.building] += p.level
    summary = {
        "locations_planned": int(table.height),
        "over_capacity_locations": int(table["over_capacity"].sum()) if table.height else 0,
        "rows": len(placements),
        "levels_by_building": dict(sorted(by_building.items(), key=lambda kv: -kv[1])),
        "farm_land_people": float(table["farm_land_people"].sum()) if table.height else 0.0,
        "farm_limited_by": dict(table.filter(pl.col("farm") != "").group_by("farm_limit").agg(pl.len()).iter_rows()) if table.height else {},
        "converted_people": round(sum(c.size_k for c in conversions) * 1000.0),
        "conversions": len(conversions),
        "provinces": int(provinces.height),
        "provinces_below_food_target": int((provinces["coverage"] < 1.0).sum()) if provinces.height else 0,
        "province_food_coverage_median": float(provinces["coverage"].median()) if provinces.height else None,
    }
    return placements, conversions, table, summary


# ------------------------------------------------------------------ outputs

def write_start_setup(placements: list[Placement], mod_root: Path) -> int:
    rows = [f"\t{p.building} = {{ tag = {p.owner} level = {p.level} location = {p.location} }}" for p in sorted(placements, key=lambda p: (p.building, p.location))]
    text = "\n".join([GENERATED, "# Game-start raw-material buildings, farms and the urban food chain, placed from the capacity model.", "building_manager = {", *rows, "}", ""])
    path = mod_root / START_SETUP_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("﻿" + text, encoding="utf-8", newline="\n")
    return len(rows)


def apply_conversions(text: str, conversions: list[PopConversion]) -> str:
    """Vanilla pops text with the conversions applied: the source pop shrinks, a pop of the target type is added
    with the same culture and religion; byte-identical everywhere else. Several conversions of one pop merge."""
    by_location: dict[str, list[PopConversion]] = defaultdict(list)
    for c in conversions:
        by_location[c.location].append(c)
    out: list[str] = []
    current: str | None = None
    pending: list[PopConversion] = []
    for line in text.splitlines(keepends=True):
        stripped = line.split("#", 1)[0].strip()
        head = re.match(r"^([A-Za-z0-9_]+)\s*=\s*\{", stripped)
        if head and head.group(1) not in ("locations", "define_pop"):
            current = head.group(1)
            pending = list(by_location.get(current, []))
            out.append(line)
            continue
        if current and pending and stripped.startswith("define_pop"):
            match = _POP_RE.search(stripped)
            fields = dict(_FIELD_RE.findall(match.group(1))) if match else {}
            size = float(fields.get("size", "0") or 0)
            added: dict[str, float] = defaultdict(float)
            done: list[PopConversion] = []
            for c in pending:
                if fields.get("type") == c.from_type and fields.get("culture") == c.culture and fields.get("religion") == c.religion:
                    take = min(c.size_k, size)
                    if take <= 0:
                        continue
                    size -= take
                    added[c.to_type] += take
                    done.append(c)
            if done:
                line = re.sub(r"size\s*=\s*[0-9.]+", f"size = {size:.3f}", line, count=1)
                indent = re.match(r"[ \t]*", line).group(0)
                for to_type, take in added.items():
                    line += f"{indent}define_pop = {{\ttype = {to_type}\tsize = {take:.3f}\tculture = {fields.get('culture')}\treligion = {fields.get('religion')} }}\t# pp start: converted from {fields.get('type')}\n"
                for c in done:
                    pending.remove(c)
        if stripped == "}" and current:
            current = None
            pending = []
        out.append(line)
    return "".join(out)


def write_pops(vanilla_root: Path, mod_root: Path, conversions: list[PopConversion]) -> dict[str, Any]:
    source = Path(vanilla_root) / "game" / POPS_SETUP_PATH
    target = mod_root / POPS_SETUP_PATH
    if not conversions:
        if target.is_file():
            target.unlink()
        return {"written": False, "conversions": 0}
    header = f"{GENERATED}\n# Vanilla pops with peasants converted to the workers the game-start buildings employ (same culture and religion).\n"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("﻿" + header + apply_conversions(source.read_text(encoding="utf-8-sig"), conversions), encoding="utf-8", newline="\n")
    return {"written": True, "conversions": len(conversions)}


def apply(*, repo: Path, project: Path, mod_root: Path, vanilla_root: Path, cfg: WorldBuilderConfig, contract, caps: Mapping[str, Mapping[str, float]], locations: pl.DataFrame) -> dict[str, Any]:
    start = StartConfig.from_raw(cfg.raw.get("start") if isinstance(cfg.raw.get("start"), dict) else None)
    owners = load_owners(vanilla_root, mod_root)
    ranks = load_ranks(vanilla_root, mod_root)
    pops = load_pops(vanilla_root)
    existing = load_existing_buildings(vanilla_root, mod_root)
    food = load_pop_food_consumption(vanilla_root, mod_root)
    keys = {*FARMS, "cookery", "victuals_market_import", *(str(s.get("building")) for s in start.processors.values()), *(str(s["coastal_building"]) for s in start.processors.values() if s.get("coastal_building"))}
    numbers = {key: blueprint_numbers(repo, key) for key in keys}
    improvements = improvement_people_by_location(mod_root, caps)
    flat = {str(t): float(v) for t, v in contract.location_targets.select("location_tag", "attribute_flat_people").iter_rows()}
    k = contract.people_per_development_point
    dev = {str(t): float(v or 0.0) for t, v in contract.location_targets.select("location_tag", "development").iter_rows()} if k else {}
    capacity = {tag: flat.get(tag, 0.0) + improvements.get(tag, 0.0) + float(start.rank_capacity_people.get(ranks.get(tag, ""), 0.0)) + k * dev.get(tag, 0.0) for tag in flat}
    placements, conversions, table, summary = plan(cfg=cfg, start=start, locations=locations, capacity_people=capacity, pops=pops, owners=owners, ranks=ranks, existing=existing, food_consumption=food, numbers=numbers)
    summary["setup_rows"] = write_start_setup(placements, mod_root)
    summary["pops"] = write_pops(vanilla_root, mod_root, conversions)
    for rel in LEGACY_FILES:
        path = mod_root / rel
        if path.is_file():
            path.unlink()
            summary.setdefault("legacy_removed", []).append(rel)
    (repo / TABLE_RELATIVE_PATH).parent.mkdir(parents=True, exist_ok=True)
    table.write_csv(repo / TABLE_RELATIVE_PATH)
    (repo / REPORT_RELATIVE_PATH).write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary
