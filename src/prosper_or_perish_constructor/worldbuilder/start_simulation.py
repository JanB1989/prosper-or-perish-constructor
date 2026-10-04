"""Start-state food budget and cap-constrained placement from parsed game data.

This is an offline, steady-state budget, not the engine's market-price simulator.
Trade catchments are nearest starting market centres within each game region.
"""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from dataclasses import replace
from pathlib import Path

import polars as pl
from eu5gameparser.clausewitz.parser import parse_file
from eu5gameparser.clausewitz.serializer import render_entry
from eu5gameparser.clausewitz.syntax import CList

from . import crop_allocation as ca
from . import start_food_model_v2 as fm
from . import start_placement as sp
from .market_capacity import write as write_market_caps
from .modifiers import setup_modifier_keys
from .start_rules import Rules, Unresolved, entries, first
from ..setup_layout import SETUP_DIR

# Bumped on every change of a location's building levels in the plan (_TrackedCounter): the province farm and Yard
# level sums are cached until the next change instead of being re-added on every cap check (2026-10-04: 1.6 million
# re-sums, about 80 s of the two-minute World Builder stage).
_LEVELS_VERSION = [0]


class _TrackedCounter(Counter):
    """A location's building levels; any change invalidates the cached province sums."""

    def __setitem__(self, key, value):
        _LEVELS_VERSION[0] += 1
        super().__setitem__(key, value)

    def __delitem__(self, key):
        _LEVELS_VERSION[0] += 1
        super().__delitem__(key)

    def pop(self, *args):
        _LEVELS_VERSION[0] += 1
        return super().pop(*args)

    def popitem(self):
        _LEVELS_VERSION[0] += 1
        return super().popitem()

    def clear(self):
        _LEVELS_VERSION[0] += 1
        super().clear()

    def setdefault(self, key, default=None):
        _LEVELS_VERSION[0] += 1
        return super().setdefault(key, default)

    def update(self, *args, **kwargs):
        _LEVELS_VERSION[0] += 1
        super().update(*args, **kwargs)

    def subtract(self, *args, **kwargs):
        _LEVELS_VERSION[0] += 1
        super().subtract(*args, **kwargs)


def _tracked_counts(initial):
    tracked = {tag: _TrackedCounter(levels) for tag, levels in initial.items()}
    if isinstance(initial, defaultdict):
        return defaultdict(_TrackedCounter, tracked)
    return tracked


VANILLA_CLIMATES = {"arctic", "arid", "cold_arid", "cold_semi_arid", "continental", "hot_semi_arid", "mediterranean", "oceanic",
                    "subpolar", "subtropical", "tropical"}   # EU5 1.4 keys; the World Builder uses them for its own semi-arid and subpolar


def climate_key(name):
    """The game's climate key for a World Builder class (the handover writes 'savanna' for ha1300_climate_savanna)."""
    if not name:
        return None
    name = str(name)
    return name if name in VANILLA_CLIMATES or name.startswith("ha1300_climate_") else "ha1300_climate_" + name


def setup_counts(path):
    result = defaultdict(Counter)
    if not path.exists():
        return result
    for manager in parse_file(path).values("building_manager"):
        for entry in manager.entries:
            tag = first(entry.value, "location")
            level = first(entry.value, "level", 0)
            if tag and level:
                result[tag][entry.key] += int(level)
    return result


def town_levels(towns, name, stack=()):
    """Building levels of a town preset: its ``copy_from`` base first, then its own levels added on top (vanilla's
    40 named-city presets such as florence_city are a base preset plus a few extra guilds)."""
    levels = Counter()
    block = towns.get(name)
    if block is None or name in stack:
        return levels
    base = first(block, "copy_from")
    if base:
        levels.update(town_levels(towns, str(base), (*stack, name)))
    for building in block.entries:
        if isinstance(building.value, (int, float)) and not isinstance(building.value, bool):
            levels[building.key] += int(building.value)
    return levels


def seed_vanilla(vanilla_root, rules, owners):
    path = vanilla_root / "game" / SETUP_DIR / "07_cities_and_buildings.txt"
    doc = parse_file(path)
    counts = setup_counts(path)
    for block in doc.values("locations"):
        for entry in block.entries:
            if entry.key not in owners:
                continue
            town = first(entry.value, "town_setup")
            if town in rules.towns:
                counts[entry.key].update(town_levels(rules.towns, town))
    return doc, counts


SETUP_MARKER = "# Generated: cap-checked starting buildings."


def write_setup(doc, counts, owners, path, *, expand_presets=False):
    # Keep unrelated setup sections and foreign building ownership intact.
    lines = [SETUP_MARKER]
    for entry in doc.entries:
        if entry.key == "building_manager":
            continue
        if entry.key == "locations" and expand_presets:
            cleaned = []
            for loc in entry.value.entries:
                value = replace(
                    loc.value,
                    entries=[e for e in loc.value.entries if e.key != "town_setup"],
                )
                cleaned.append(replace(loc, value=value))
            entry = replace(entry, value=replace(entry.value, entries=cleaned))
        lines.append(render_entry(entry))
    lines.append("building_manager = {")
    remaining = {tag: Counter(local) for tag, local in counts.items()}
    # Keep the owning tags and other metadata of explicit foreign buildings.
    # Only implicit town-preset rows acquire the location owner's tag.
    for manager in doc.values("building_manager"):
        for entry in manager.entries:
            tag = first(entry.value, "location")
            wanted = int(first(entry.value, "level", 0))
            n = min(wanted, remaining.get(tag, {}).get(entry.key, 0))
            if n <= 0:
                continue
            fields = [
                replace(field, value=n) if field.key == "level" else field
                for field in entry.value.entries
            ]
            lines.append(
                render_entry(
                    replace(entry, value=replace(entry.value, entries=fields)), indent=1
                )
            )
            remaining[tag][entry.key] -= n
    for tag, buildings in sorted(remaining.items()):
        for key, n in sorted(buildings.items()):
            if n > 0 and tag in owners:
                lines.append(
                    f" {key} = {{ tag = {owners[tag]} level = {n} location = {tag} }}"
                )
    lines.append("}")
    path.write_text("\ufeff" + "\n".join(lines) + "\n", encoding="utf-8")


def write_vanilla(doc, counts, owners, mod_root):
    write_setup(
        doc,
        counts,
        owners,
        mod_root / SETUP_DIR / "07_cities_and_buildings.txt",
        expand_presets=True,
    )


def additional_setups(vanilla_root, mod_root):
    """Find building managers outside the town and generated placement files."""
    base = vanilla_root / "game" / SETUP_DIR
    target = mod_root / SETUP_DIR
    paths = {p.name: p for root in (base, target) for p in root.glob("*.txt")}
    excluded = {
        "07_cities_and_buildings.txt",
        sp.START_SETUP_PATH.name,
        sp.IMPROVEMENT_SETUP_PATH.name,
    }
    result = {}
    for name, path in sorted(paths.items()):
        if name in excluded:
            continue
        text = path.read_text(encoding="utf-8-sig")
        if text.startswith(SETUP_MARKER) and (base / name).exists():
            path = base / name
            text = path.read_text(encoding="utf-8-sig")
        if "building_manager" in text:
            result[name] = (parse_file(path), setup_counts(path))
    return result


TOPUP_PATH = Path("in_game/common/scripted_effects/pp_start_river_topup.txt")
CROP_REPORT_RELATIVE_PATH = Path("artifacts/data/worldbuilder/crop_allocation.csv")


def without_river(ctx, rules):
    """The location context as if the engine had traced no river through it."""
    mods = dict(ctx["modifiers"])
    statics = {s for s in ctx["static_modifiers"] if s.startswith("river_flowing_through_")}
    for key in statics:
        for k, v in summed(rules.statics.get(key)).items():
            if k != "local_population_capacity":
                mods[k] = mods.get(k, 0.0) - v
    return {**ctx, "modifiers": mods, "static_modifiers": set(ctx["static_modifiers"]) - statics, "has_river": False}


TOPUP_POTENTIALS_PATH = Path("in_game/common/scripted_triggers/pp_start_river_topup_potentials.txt")


def topup_potential_trigger(key):
    """The scripted trigger holding a copy of ``key``'s location_potential (the topup's validity guard)."""
    return f"pp_start_topup_{key}_potential"


def _render_scalar(value):
    if value is True:
        return "yes"
    if value is False:
        return "no"
    text = str(value)
    return f'"{text}"' if not text or any(c in text for c in ' \t"{}=<>#') else text


def render_trigger(node, depth=1):
    """A parsed trigger block back as script text, one entry per line (the parser keeps ``a ?= b`` as an anonymous
    entry whose left side sits in the block's items; quoted strings come back quoted)."""
    pad = "\t" * depth
    items = list(node.items)
    lines = []
    for entry in node.entries:
        if entry.key == "?":
            key, op = items.pop(0), "?="
        else:
            key, op = entry.key, entry.op
        value = entry.value
        if isinstance(value, CList):
            lines.append(f"{pad}{key} {op} {{\n{render_trigger(value, depth + 1)}\n{pad}}}")
        else:
            lines.append(f"{pad}{key} {op} {_render_scalar(value)}")
    lines[:0] = [f"{pad}{_render_scalar(item)}" for item in items]
    return "\n".join(lines)


def write_topup(topup, owners, mod_root, *, base=None, potentials=None, first_keys=frozenset()):
    """``pp_start_river_topup``: the river share of the starting buildings (called by pp_navigation_start).

    Whether the engine traces a location's river, and at which size, cannot be told offline: it keeps stray river
    pixels as ``has_river`` without a size, and some World Builder rivers are none to it (EU5 1.4 start: nine inland
    fishing villages invalid, irrigated fields and Taverns above max where this effect added levels unconditionally).
    So every level is added only where the engine allows it at game start, which is also when it validates the
    start buildings: the building's own location_potential (``pp_start_topup_<key>_potential``, a copy of it) and its
    live max level (``building_type_max_level`` at least the level the step reaches). ``base``: (location, building)
    -> levels the setup already places; ``potentials``: building -> its location_potential block (None: no gate);
    ``first_keys``: buildings whose levels raise other caps (farms, fisheries, Victualling Yards: the Cookshop cap),
    written before the rest so the live max-level checks after them see their levels."""
    from eu5gameparser.clausewitz.parser import parse_text
    from eu5gameparser.clausewitz.serializer import normalized_value

    base = base or {}
    potentials = potentials or {}
    lines = [SETUP_MARKER.replace("cap-checked starting buildings", "river share of the starting buildings (start_simulation.river_topup)"),
             "# Each level only where the engine allows it: the building's location_potential and its live max level.",
             "pp_start_river_topup = {"]
    guarded = set()
    for (tag, key), n in sorted(topup.items(), key=lambda kv: (kv[0][1] not in first_keys, kv[0])):
        if n <= 0 or tag not in owners:
            continue
        have = int(base.get((tag, key), 0))
        steps = " ".join(
            f"if = {{ limit = {{ building_type_max_level = {{ building_type = building_type:{key} value >= {have + k} }} }} "
            f"change_building_level_in_location = {{ building = building_type:{key} value = 1 }} }}"
            for k in range(1, n + 1)
        )
        guarded.add(key)
        lines.append(f" location:{tag} = {{ if = {{ limit = {{ {topup_potential_trigger(key)} = yes }} {steps} }} }}")
    lines.append("}")
    path = mod_root / TOPUP_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("﻿" + "\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    triggers = [SETUP_MARKER.replace("cap-checked starting buildings", "copies of the location_potential the river topup tests (start_simulation.write_topup)")]
    for key in sorted(guarded):
        potential = potentials.get(key)
        if not isinstance(potential, CList):
            triggers.append(f"{topup_potential_trigger(key)} = {{\n\talways = yes\n}}")   # the building has no potential
            continue
        body = render_trigger(potential)
        # the copy must be the potential the engine reads: a rendering the parser does not read back identically fails
        again = parse_text(f"t = {{\n{body}\n}}").entries[0].value
        if normalized_value(again) != normalized_value(potential):
            raise ValueError(f"location_potential of {key} does not render back identically for the river topup guard")
        triggers.append(f"{topup_potential_trigger(key)} = {{\n{body}\n}}")
    target = mod_root / TOPUP_POTENTIALS_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("﻿" + "\n\n".join(triggers) + "\n", encoding="utf-8", newline="\n")


def sim_converted(sim):
    """Planner conversions per location and target type (thousands)."""
    converted = defaultdict(Counter)
    for c in sim.conversions:
        converted[c.location][c.to_type] += c.size_k
    return converted


def summed(block):
    result = defaultdict(float)
    if isinstance(block, CList):
        for e in block.entries:
            if isinstance(e.value, (int, float)):
                result[e.key] += float(e.value)
    return result


PROVINCE_FOOD_GOOD = "local_food"


def has_method(body, method):
    """Whether the building defines the unique production method ``method``."""
    return any(
        isinstance(first(block, method), CList)
        for block in (body.values("unique_production_methods") if isinstance(body, CList) else [])
    )


def method_output(body, method, good=PROVINCE_FOOD_GOOD):
    """Output of the building's unique production method ``method`` when it produces ``good`` (else 0)."""
    for block in body.values("unique_production_methods") if isinstance(body, CList) else []:
        node = first(block, method)
        if isinstance(node, CList) and str(first(node, "produced", "")) == good:
            return float(first(node, "output", 0) or 0)
    return 0.0


def province_food_per_level(rules, spec):
    """building -> Province Food (``local_food``, 1 food per unit) one staffed level makes on top of its
    ``local_monthly_food``: the Provisioning method's output (``spec["method_pattern"]``, e.g. crop farms 0.96 x M,
    fishing villages 0.8), for the buildings in ``spec["serve"]`` the named Serve method and for those in
    ``spec["unpack"]`` the named method that turns victuals into Province Food (the Tavern); ``spec["per_level"]``
    overrides. A configured method that the building does not have is an error, not a silent zero."""
    pattern = str(spec.get("method_pattern") or "pp_{building}_provision")
    serve = {**dict(spec.get("serve") or {}), **dict(spec.get("unpack") or {})}
    out = {}
    for key, body in rules.buildings.items():
        if key in serve:
            continue
        value = method_output(body, pattern.format(building=key))
        if value:
            out[key] = value
    for key, method in serve.items():
        body = rules.buildings.get(key)
        if not has_method(body, str(method)):
            raise ValueError(f"[worldbuilder.start.province_food] serve: {key} has no method {method}")
        # 0 when the method sells something else: the Cookshop's dishes sell for offset since 2026-10-03 and its food
        # is its flat local_monthly_food (the method still names the recipe whose staples the start budget counts)
        out[key] = method_output(body, str(method))
    for key, value in (spec.get("per_level") or {}).items():
        out[str(key)] = float(value)
    return dict(sorted(out.items()))


# Farm counters (2026-10-03): the modifier every farm and orchard level carries, the one every fishery and sheep level
# carries, and the location-scope script value the Cookshop cap reads (in_game/common/script_values/
# pp_food_building_values.txt: both counters). The farms' own spread term reads only the farm counter.
FARM_LEVELS_MODIFIER = "local_pp_farm_levels"
STAPLE_LEVELS_MODIFIER = "local_pp_staple_levels"
PROVINCE_FARM_LEVELS_VALUE = "pp_location_province_farm_levels"
# Victualling Yard levels (2026-10-04): every standing level adds half a Cookshop level to its province
# (raw_modifier local_pp_victualling_yard_levels, script value pp_location_province_victualling_yard_levels).
YARD_LEVELS_MODIFIER = "local_pp_victualling_yard_levels"
PROVINCE_YARD_LEVELS_VALUE = "pp_location_province_victualling_yard_levels"

class Simulation:
    # Engine start state per location (filled in __init__; empty means "as the pops file says").
    est_pops: dict = {}
    food_mult: dict = {}
    rgo_k: dict = {}
    victuals_pop_factors: dict = {}
    victuals: dict = {}
    province_food: dict = {}   # building -> Province Food per staffed level (province_food_per_level)
    crop_cfg = None            # crop_allocation.CropConfig; None skips the crop farms
    food_model = fm.FoodModelConfig()
    yield_k: dict = {}         # location -> food per 1,000 jobless peasants/slaves (start_food_model_v2)

    def __init__(
        self,
        *,
        rules,
        cfg,
        start,
        contract,
        locations,
        pops,
        owners,
        ranks,
        food,
        initial,
        improvement_keys,
        market_centres,
        repo=None,
        crop_threshold=0.60,
        province_food=None,
    ):
        self.rules, self.cfg, self.start = rules, cfg, start
        self.province_food = dict(province_food or {})
        self.pops, self.owners, self.ranks, self.food = pops, owners, ranks, food
        self.counts = _tracked_counts(initial)
        self.improvement_keys = improvement_keys
        self.original = {tag: dict(buildings) for tag, buildings in initial.items()}
        self.conversions = []
        self.placements = []
        self.trimmed = []
        self.audit = []
        self.rejections = Counter()
        self.attrs = {
            r["location_tag"]: r
            for r in contract.location_attributes.iter_rows(named=True)
        }
        self.targets = {
            r["location_tag"]: r
            for r in contract.location_targets.iter_rows(named=True)
        }
        self.locations = {
            r["location_tag"]: r
            for r in locations.iter_rows(named=True)
            if r["location_tag"] in owners
        }
        # unowned land (tribal mostly): only the validator's tribesmen pools read it (food_sim.unowned_pools)
        self.unowned_locations = {
            r["location_tag"]: r
            for r in locations.iter_rows(named=True)
            if r["location_tag"] not in owners and pops.get(r["location_tag"])
        }
        self.markets = market_centres
        self.raw = {
            key: rules.modifiers(key, "raw_modifier") for key in rules.buildings
        }
        self.numbers = {key: rules.numbers(key) for key in rules.buildings}
        # farm and orchard levels carry local_pp_farm_levels: Cookshop caps read the province's sum (script value
        # pp_location_province_farm_levels). Since 2026-10-03 the counter sits in raw_modifier (every standing level,
        # staffing ignored); both blocks are read. Rules.numbers carries only employment, pop type and local food.
        def counter(key: str, name: str) -> float:
            return float(rules.modifiers(key).get(name, 0)) + float(self.raw[key].get(name, 0))

        self.farm_counters = {k: v for k in rules.buildings if (v := counter(k, FARM_LEVELS_MODIFIER))}
        # the Cookshop cap also counts fishery and sheep levels (local_pp_staple_levels)
        self.kitchen_counters = {k: v for k in rules.buildings
                                 if (v := counter(k, FARM_LEVELS_MODIFIER) + counter(k, STAPLE_LEVELS_MODIFIER))}
        # and the Victualling Yard levels (half a Cookshop level each)
        self.yard_counters = {k: v for k in rules.buildings if (v := counter(k, YARD_LEVELS_MODIFIER))}
        self.base = {}
        self.neighbors = defaultdict(list)
        self.navigation = cfg.raw.get("_navigation", {})
        self.water = cfg.raw.get("_water_access")
        self.refresh_navigation()
        # Engine start state the pops file does not show: setup promotion out of the peasants, the RGO's own
        # workers, and the local food modifier of rank and classes (scales subsistence and building food alike).
        self.est_pops = {}
        self.food_mult = {}
        self.rgo_k = {}
        self.yield_k = {}
        self.food_model = fm.FoodModelConfig.from_raw((cfg.raw.get("start") or {}).get("food_model"))
        self.victuals_pop_factors = rules.victuals_pop_factors()
        setup_keys = setup_modifier_keys(contract, self.navigation)
        # The engine's province capitals at game start (config/start_province_capitals.txt, read from a start save):
        # the setup files do not name them and no rule reproduces the engine's pick.
        capitals_file = Path(repo or ".") / "config/start_province_capitals.txt"
        self.province_capitals = (
            {line.strip() for line in capitals_file.read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")}
            if capitals_file.exists()
            else None
        )
        for tag, loc in self.locations.items():
            a = self.attrs.get(tag, {})
            target = self.targets.get(tag, {})
            rank = ranks.get(tag, "rural_settlement")
            self.est_pops[tag] = sp.estimate_start_pops(pops.get(tag, []), rank, start, float(target.get("development") or 0))
            self.food_mult[tag] = max(
                0.0,
                1.0
                + rules.food_modifier(
                    rank,
                    {kind: a.get(kind) or loc.get(kind) for kind in ("climate", "vegetation", "topography")},
                ),
            )
            self.rgo_k[tag] = max(
                0.0,
                min(float(start.rgo_workers_k.get(rank, 0.0)), self.est_pops[tag].get("peasants", 0.0)),
            )
            mods = defaultdict(float)
            for block in rules.ranks.get(rank, CList([], [])).values("rank_modifier"):
                for k, v in summed(block).items():
                    mods[k] += v
            # Contract attributes include the class capacity; rank housing and
            # the development term are read from their live source definitions.
            rank_capacity = mods.get("local_population_capacity", 0)
            mods["local_population_capacity"] = (
                float(target.get("attribute_flat_people") or 0) / 1000
                + rank_capacity
                + contract.people_per_development_point
                * float(target.get("development") or 0)
                / 1000
            )
            mods["natural_harbor_suitability"] = float(
                loc.get("natural_harbor_suitability") or 0
            )
            static = set()
            level = int(a.get("river_level") or 0)
            if level:
                key = f"river_flowing_through_{level}"
                static.add(key)
                for k, v in summed(rules.statics.get(key)).items():
                    if k != "local_population_capacity":
                        mods[k] += v
            # engine is_coastal: any passable sea zone next to it, river channels included (coast.py, read from the map)
            coastal = (tag in self.water) if self.water is not None else (bool(loc.get("is_coastal")) or bool(self.neighbors[tag]))
            if level and coastal:
                # The engine adds river_flowing_through_coast_N (natural harbour +0.05 per river size) to every coastal
                # location with a river; river ports count as coastal (checked in game on Samara: 0 + 0.25).
                key = f"river_flowing_through_coast_{level}"
                static.add(key)
                for k, v in summed(rules.statics.get(key)).items():
                    mods[k] += v
            # Harbour capacity (harbor_suitability, the Victualling Yard cap): the engine derives it from the natural
            # harbour value (location_template_natural_harbor_suitability; Samara in game: 0.25 = its natural 0.25).
            # Setup docks and shipyards are not modelled: a lower bound, like the roads.
            mods["harbor_suitability"] += mods["natural_harbor_suitability"]
            # Fertility, soil, sea coast and lake shore modifiers from the setup: the caps test for them
            # (fertility alone moves field management by 3 levels). Their capacity rows are in the attribute flat.
            for key in setup_keys.get(tag, ()):
                static.add(key)
                for k, v in summed(rules.statics.get(key)).items():
                    if not k.startswith("local_population_capacity"):
                        mods[k] += v
            ctx = {
                **loc,
                "location_tag": tag,
                "location_rank": rank,
                "sub_continent": loc.get("sub_continent") or loc.get("macro_region"),
                "population": sum(p.size_k for p in pops.get(tag, [])),
                "development": float(target.get("development") or 0),
                "owner": owners[tag],
                "is_ownable": True,
                "has_river": bool(level),
                "is_coastal": coastal,
                # the engine's port rule is not in the map files (ports.csv lists every coastal location, 5,701, the
                # game reports 3,567 ports): the start model lets every coastal location count as a port
                "is_port": coastal,
                "trigger_values": {
                    "pp_is_sea_coast": (self.water or {}).get(tag) == "sea_coast" if self.water is not None
                    else str(a.get("is_coastal", "")).lower() == "true",
                    "pp_is_waterway": (self.water or {}).get(tag) == "waterway",
                },
                "is_province_capital": tag in self.province_capitals if self.province_capitals is not None else False,
                "num_roads": 0,   # setup roads are not modelled: a lower bound for road-scaled caps
                "climate": climate_key(a.get("climate") or loc.get("climate")),
                "is_adjacent_to_lake": str(a.get("is_adjacent_to_lake", "")).lower()
                == "true",
                "market_access": 0.0,
                "max_rgo_workers": 0.0,
                "is_market_center": tag in market_centres,
                "initializing": True,
                "variables": {},
                "static_modifiers": static,
                # the engine applies the river statics itself: has_location_modifier does not see them (only their
                # values count), unlike the setup-placed attribute modifiers
                "engine_modifiers": frozenset(k for k in static if k.startswith("river_flowing_through_")),
                "neighbors": self.neighbors[tag],
                "modifiers": dict(mods),
                "buildings": {},
            }
            ctx["variables"]["pp_forest_base_capacity"] = rules.value(
                "pp_forest_base_capacity_value", ctx
            )
            ctx["variables"]["pp_fish_base_capacity"] = rules.value(
                "pp_fish_base_capacity_value", ctx
            )
            # the setup's static modifiers (fertility, soil, coast, lake, river) join the rank and class food stack
            self.food_mult[tag] = max(0.0, self.food_mult[tag] + fm.statics_food_modifier(rules.statics, static))
            self.yield_k[tag] = fm.location_yield(
                rules.subsistence, self.food_mult[tag] - 1.0, rank, a.get("climate") or loc.get("climate"), self.food_model
            )
            self.base[tag] = ctx
        self.groups = defaultdict(list)
        for tag, loc in self.locations.items():
            self.groups[(owners[tag], str(loc.get("province") or tag))].append(tag)
        self.group_of = {t: g for g, ts in self.groups.items() for t in ts}
        # Historical countries can share markets. Region masks prevent a global
        # pool from teleporting food between unconnected continents.
        centres = defaultdict(list)
        for tag in market_centres:
            if tag in self.locations:
                centres[self.locations[tag].get("region")].append(tag)
        self.catchments = {}
        for group, tags in self.groups.items():
            anchor = max(tags, key=lambda t: self.base[t]["population"])
            region = self.locations[anchor].get("region", "unknown")
            choices = centres.get(region, [])

            def distance(t, anchor=anchor):
                a, b = self.attrs.get(anchor, {}), self.attrs.get(t, {})
                lat = float(a.get("calibrated_lat") or 0)
                return (
                    (
                        float(a.get("calibrated_lon") or 0)
                        - float(b.get("calibrated_lon") or 0)
                    )
                    * math.cos(math.radians(lat))
                ) ** 2 + (lat - float(b.get("calibrated_lat") or 0)) ** 2

            self.catchments[group] = (
                min(sorted(choices), key=distance) if choices else str(region)
            )
        # Crop farms: a crop location's farm levels are spread over the tier-0 crop farms (crop_allocation). The plan
        # here filters on the buildings' gates; place() re-allocates each location on its live caps.
        self.crop_cfg = ca.load_crop_config({"worldbuilder": cfg.raw}, repo=repo)
        gates = ca.crop_gates(locations, self.crop_cfg, crop_threshold)
        self.crop_weights = ca.crop_weights(contract, locations, self.crop_cfg)
        self.crop_available = ca.available_by_location(locations, gates, self.crop_cfg)
        self.crop_placed = defaultdict(Counter)
        budget = {
            tag: start.max_farm_levels_per_location
            for tag, loc in self.locations.items()
            if sp.crop_location(loc)
        }
        self.crop_plan = ca.plan_all(
            contract,
            locations,
            gates,
            self.crop_cfg,
            budget,
            weights=self.crop_weights,
            candidate_filter=self.crop_gate,
        )


    def refresh_navigation(self):
        navigation = self.navigation
        self._caps = {}  # neighbour states feed the caps
        self.neighbors = defaultdict(list)
        for edge in navigation.get("edges", []):
            if not edge["shore"]:
                continue
            tile = navigation["tiles"][edge["from"]]
            status = {"barrier": 3, "navigable": 1, "improvable": 2}[tile["state"]]
            if edge.get("cost_profile") == "difficult":
                status = 5
            host = edge.get("host")
            site = navigation.get("sites", {}).get(host, {})
            if status != 3 and any(
                self.counts.get(host, {}).get(k, 0) > 0
                for k in site.get("supporting_buildings", [])
            ):
                status = 4
            self.neighbors[edge["to"]].append(
                {"variables": {"pp_navigation_map_state": status}}
            )
        for tag, ctx in self.base.items():
            ctx["neighbors"] = self.neighbors[tag]

    def ctx(self, tag, counts=None, others=None):
        """The location's rule context with its building levels (``counts``: other levels than the plan's, e.g. the
        ones the setup files place; ``others``: location -> levels for the rest of the province, default the plan)."""
        base = self.base[tag]
        levels = self.counts[tag] if counts is None else counts
        mods = defaultdict(float, base["modifiers"])
        for key, n in levels.items():
            for k, v in self.raw.get(key, {}).items():
                mods[k] += v * n
        counters = getattr(self, "farm_counters", {})   # absent on the bare test doubles
        mods[FARM_LEVELS_MODIFIER] += sum(levels.get(k, 0) * v for k, v in counters.items())
        # ``counts``, not ``levels``: None takes the cached province sums (the plan's own levels)
        province_farms = self.province_farm_levels(tag, counts, others)
        province_yards = self.province_yard_levels(tag, counts, others)
        return {**base, "buildings": levels, "modifiers": dict(mods), PROVINCE_FARM_LEVELS_VALUE: province_farms,
                PROVINCE_YARD_LEVELS_VALUE: province_yards}

    def province_farm_levels(self, tag, levels=None, others=None):
        """Farm, orchard, fishery and sheep levels placed in the location's province pool (``levels``: this location's
        own, if not the plan's; ``others``: location -> levels for the other locations, default the plan). The Cookshop
        cap reads it, so it depends on the other locations of the province too."""
        counters = getattr(self, "kitchen_counters", getattr(self, "farm_counters", {}))
        return self._province_levels(tag, counters, levels, others)

    def province_yard_levels(self, tag, levels=None, others=None):
        """Victualling Yard levels placed in the location's province pool (the Cookshop cap adds half a level each)."""
        return self._province_levels(tag, getattr(self, "yard_counters", {}), levels, others)

    def _province_levels(self, tag, counters, levels=None, others=None):
        if levels is None and others is None:
            cache = self.__dict__.setdefault("_province_levels_cache", {})
            if cache.get("version") != _LEVELS_VERSION[0]:
                cache.clear()
                cache["version"] = _LEVELS_VERSION[0]
            key = (id(counters), getattr(self, "group_of", {}).get(tag, ("location", tag)))
            cached = cache.get(key)
            if cached is None:
                cached = cache[key] = self._sum_province_levels(tag, counters, None, None)
            return cached
        return self._sum_province_levels(tag, counters, levels, others)

    def _sum_province_levels(self, tag, counters, levels=None, others=None):
        levels = self.counts[tag] if levels is None else levels
        others = self.counts if others is None else others
        group = getattr(self, "group_of", {}).get(tag)
        return sum(
            (levels if t == tag else others.get(t, {})).get(k, 0) * v
            for t in (self.groups.get(group, (tag,)) if group is not None else (tag,))
            for k, v in counters.items()
        )

    def food_per_level(self, key, mult=1.0):
        """Province food one staffed level makes: ``local_monthly_food`` scaled by the local food modifier ``mult``,
        plus the Province Food good its Provisioning or Serve method makes (a good: not scaled)."""
        return mult * self.numbers.get(key, {}).get("local_monthly_food", 0) + float(self.province_food.get(key, 0.0))

    def crop_gate(self, tag, good):
        """Whether ``good``'s crop farm may stand in the location: rank, ``location_potential`` and ``allow`` as
        ``Rules.cap`` evaluates them (no level room check). Unresolved syntax fails closed and is reported."""
        key = self.crop_cfg.buildings.get(good)
        body = self.rules.buildings.get(key)
        if body is None or tag not in self.base:
            return False
        ctx = self.ctx(tag)
        try:
            return (
                first(body, ctx.get("location_rank", "rural_settlement"), False) is True
                and self.rules.test(first(body, "location_potential"), ctx)
                and self.rules.test(first(body, "allow"), ctx)
            )
        except Unresolved as exc:
            self.rules.unsupported[f"{key}: {exc}"] += 1
            return False

    def crop_candidates(self, tag):
        """Crop goods whose tier-0 farm has room for a level in the location now (``Rules.cap``: gates and cap)."""
        return frozenset(
            good
            for good, key in self.crop_cfg.buildings.items()
            if key in self.numbers and self.cap(tag, key) > self.counts[tag][key]
        )

    def _staffable(self, tag, key):
        num = self.numbers.get(key)
        return bool(num) and self.pools[tag].levels(1, num["employment_size"], num["pop_type"]) >= 1

    def place_crops(self, tag):
        """Spread the location's farm levels (``max_farm_levels_per_location``) over the crop farms.

        The plan is ``crop_allocation.allocate`` over the goods that are available here (native gates) and whose farm
        passes its live cap; it replaces the location's entry in ``crop_plan``. Levels are placed farm by farm, most
        planned levels first, each through ``add`` (caps, workers, shared land, pops within capacity). Levels a farm
        refuses go to the RGO crop's farm, else the heaviest other candidate, livestock last and never beyond one level
        over its planned share (a herd level takes little land and would otherwise absorb every refused level); what
        no farm takes is not placed (rejection ``crop farms: no room``). Placing stops as soon as no peasant is left
        to staff a level. Returns the levels placed."""
        cfg = self.crop_cfg
        budget = self.start.max_farm_levels_per_location
        rgo = str(self.locations[tag].get("raw_material") or "") or None
        weights = self.crop_weights.get(tag, {})
        candidates = self.crop_candidates(tag)
        available = self.crop_available.get(tag, frozenset())
        allowed = candidates & available
        split = ca.allocate(budget, weights, available, rgo, cfg, candidate_filter=candidates.__contains__)
        plan = {cfg.buildings[g]: n for g, n in split.items()}
        self.crop_plan[tag] = plan
        if not plan:
            return 0
        rank = {key: i for i, key in enumerate(cfg.buildings.values())}
        placed_here = self.__dict__.setdefault("crop_placed", defaultdict(Counter))[tag]
        placed = 0
        refused = set()
        for key, wanted in sorted(plan.items(), key=lambda kv: (-kv[1], rank[kv[0]])):
            n = self.add(tag, key, min(wanted, budget - placed))
            placed_here[key] += n
            placed += n
            if n < wanted:
                refused.add(key)
                if not self._staffable(tag, key):
                    return placed
        crops = sorted(
            (g for g in allowed if g != ca.LIVESTOCK),
            key=lambda g: (-float(weights.get(g, 0.0)), rank[cfg.buildings[g]]),
        )
        fallback = ([rgo] if rgo in allowed else []) + crops + ([ca.LIVESTOCK] if ca.LIVESTOCK in allowed else [])
        cattle = cfg.buildings[ca.LIVESTOCK]
        for good in dict.fromkeys(fallback):
            leftover = min(sum(plan.values()), budget) - placed
            key = cfg.buildings[good]
            if leftover <= 0:
                break
            if key in refused:
                continue
            wanted = leftover
            if key == cattle:
                # a herd level takes far less land than an arable one: without this bound cattle would absorb every
                # level the crops refuse. It gets at most one level beyond its planned share.
                wanted = min(leftover, plan.get(cattle, 0) + 1 - placed_here[cattle])
                if wanted <= 0:
                    continue
            n = self.add(tag, key, wanted)
            placed_here[key] += n
            placed += n
            if n < wanted:
                refused.add(key)
                if not self._staffable(tag, key):
                    return placed
        leftover = min(sum(plan.values()), budget) - placed
        if leftover > 0:
            self.rejections["crop farms: no room"] += leftover   # no crop farm could take them: not placed
        return placed

    def _cap_state(self, tag):
        """The part of the cap memo key that belongs to the location: its levels and its province's farm and Yard
        levels. One placement re-checks every building of the location against the same state."""
        return (tuple(sorted((k, n) for k, n in self.counts[tag].items() if n)),
                self.province_farm_levels(tag), self.province_yard_levels(tag))

    def cap(self, tag, key, gates=True, loc_state=None):
        """``Rules.cap`` on the location's current state. Between navigation refreshes the context depends on the
        location's building levels and its province's farm and Yard levels (the Cookshop cap), so results are memoised on
        them."""
        state = (tag, key, gates, *(self._cap_state(tag) if loc_state is None else loc_state))
        cache = self.__dict__.setdefault("_caps", {})
        cached = cache.get(state)
        if cached is None:
            cached = cache[state] = self.rules.cap(key, self.ctx(tag), gates=gates)
        return cached

    def drop_invalid(self):
        """Remove setup rows the engine reports as invalid: a location rank the building may not stand in, or a
        failing location_potential (vanilla tar kilns on land the World Builder made unwooded). The engine keeps
        such buildings anyway; this keeps error.log clean. Gates the evaluator cannot resolve are kept."""
        for tag in sorted(self.locations):
            ctx = self.ctx(tag)
            rank = ctx.get("location_rank", "rural_settlement")
            for key, n in sorted(self.counts[tag].items()):
                body = self.rules.buildings.get(key)
                if not n or body is None:
                    continue
                try:
                    valid = first(body, rank, False) in (True, "setup_only") and self.rules.test(
                        first(body, "location_potential"), ctx
                    )
                except Unresolved:
                    continue
                if not valid:
                    self.trimmed.append({"location": tag, "building": key, "before": n, "after": 0})
                    self.counts[tag][key] = 0

    def river_topup(self):
        """(location, building) -> starting levels that need the location's river; added at game start.

        The engine validates setup buildings against the river sizes it traces from rivers.png, and drops some
        bank remnants of the navigable rivers the World Builder still counts (Mechelen, Hanyang). Which ones
        cannot be told offline, so the setup carries only the levels that hold without any river (gate and cap);
        pp_start_river_topup adds the rest at game start, after pp_navigation_preserve_rivers, each level only where
        the engine's own potential and max level allow it (write_topup)."""
        topup = {}

        def check(tag, dry, keys):
            for key, n in keys:
                body = self.rules.buildings.get(key)
                if not n or body is None:
                    continue
                before = Counter(self.rules.unsupported)
                try:
                    valid = self.rules.test(first(body, "location_potential"), dry)
                except Unresolved:
                    valid = True
                keep = min(n, self.rules.cap(key, dry, gates=False)) if valid else 0
                if self.rules.unsupported != before:   # an unresolved rule on the dry path: keep the setup as is
                    self.rules.unsupported = before
                    keep = n
                if keep < n:
                    topup[(tag, key)] = max(topup.get((tag, key), 0), n - keep)

        for tag in sorted(self.locations):
            ctx = self.ctx(tag)
            if not ctx["has_river"]:
                continue
            check(tag, without_river(ctx, self.rules), sorted(self.counts[tag].items()))
        # Farm (and fishery, sheep) levels and Victualling Yard levels moved to the topup are not there when the engine
        # validates the setup, and the Cookshop cap counts them in the province: re-check the other buildings of those
        # provinces against the setup's.
        counters = {**getattr(self, "kitchen_counters", getattr(self, "farm_counters", {})),
                    **getattr(self, "yard_counters", {})}
        moved = {(t, k): n for (t, k), n in topup.items() if k in counters}
        if moved:
            setup = {t: Counter({k: n - moved.get((t, k), 0) for k, n in c.items()}) for t, c in self.counts.items()}
            groups = {self.group_of.get(t) for t, _ in moved}
            for tag in sorted(t for g in groups for t in self.groups.get(g, ())):
                ctx = self.ctx(tag, setup[tag], setup)
                dry = without_river(ctx, self.rules) if ctx["has_river"] else ctx
                check(tag, dry, sorted((k, setup[tag][k]) for k in setup[tag] if k not in counters))
        return topup

    def clamp(self):
        # Caps can share pools or shrink with urbanisation: iterate to a stable
        # state, always removing levels and never silently raising the cap.
        for _ in range(20):
            changed = False
            for tag in sorted(self.locations):
                for key, n in sorted(self.counts[tag].items()):
                    if not n:
                        continue
                    cap = self.cap(tag, key, gates=False)
                    if n > cap:
                        self.trimmed.append(
                            {
                                "location": tag,
                                "building": key,
                                "before": n,
                                "after": cap,
                            }
                        )
                        self.counts[tag][key] = cap
                        changed = True
            if not changed:
                return
        raise ValueError("Starting building caps failed to converge")

    def workers(self):
        self.pools = {}
        self.staffed = defaultdict(Counter)
        for tag in sorted(self.locations):
            local = [replace(p) for p in self.pops.get(tag, [])]
            # Only peasants left after the engine's promotion and the RGO's hiring can staff or convert.
            pool = sp._Workers(
                local,
                self.start,
                peasants_k=(
                    self.est_pops[tag].get("peasants", 0.0) - self.rgo_k.get(tag, 0.0)
                    if tag in self.est_pops
                    else None
                ),
            )
            self.pools[tag] = pool
            # The engine's setup promotion supplies the nobles and burghers the markets and guilds employ.
            for kind, n in self.est_pops.get(tag, {}).items():
                if kind != "peasants":
                    pool.existing[kind] = max(pool.existing.get(kind, 0.0), n)
            for key, n in sorted(
                self.counts[tag].items(),
                key=lambda kv: (
                    -self.food_per_level(kv[0]),
                    kv[0],
                ),
            ):
                num = self.numbers.get(key)
                if not num:
                    continue
                levels = pool.levels(n, num["employment_size"], num["pop_type"])
                pool.take(
                    levels,
                    num["employment_size"],
                    num["pop_type"],
                    tag,
                    self.conversions,
                )
                self.staffed[tag][key] = levels

    def add(self, tag, key, wanted=1):
        num = self.numbers.get(key)
        if not num:
            return 0
        pool = self.pools[tag]
        count = 0
        for _ in range(max(wanted, 0)):
            if self.counts[tag][key] >= self.cap(tag, key):
                self.rejections[key + ": cap or gate"] += 1
                break
            if pool.levels(1, num["employment_size"], num["pop_type"]) < 1:
                self.rejections[key + ": workers"] += 1
                break
            self.counts[tag][key] += 1
            # Forest pressure and all other shared caps must remain valid after
            # every placement, including the building's own level.
            loc_state = self._cap_state(tag)
            if any(
                n > self.cap(tag, k, gates=False, loc_state=loc_state)
                for k, n in list(self.counts[tag].items())
                if n
            ):
                self.counts[tag][key] -= 1
                self.rejections[key + ": shared cap or land"] += 1
                break
            raw = self.raw.get(key, {})
            if (
                raw.get("local_population_capacity", 0) < 0
                and self.start.keep_pops_within_capacity
                and (ctx := self.ctx(tag))["modifiers"]["local_population_capacity"] < ctx["population"]
            ):
                self.counts[tag][key] -= 1
                self.rejections[key + ": shared cap or land"] += 1
                break
            pool.take(1, num["employment_size"], num["pop_type"], tag, self.conversions)
            self.staffed[tag][key] += 1
            count += 1
        if count:
            self.placements.append(sp.Placement(tag, self.owners[tag], key, count))
        return count

    def location_pops(self, tag, converted=None):
        """Pops by type at tick 0: the file's pops, the engine's setup promotion, and the planner's own worker
        conversions where they exceed what the engine promotes anyway (the engine tops up to its share)."""
        types = Counter()
        for p in self.pops.get(tag, []):
            types[p.type] += p.size_k
        estimated = self.est_pops.get(tag, {})
        for kind, n in estimated.items():
            if kind == "peasants":
                continue
            promoted = max(0.0, n - types.get(kind, 0.0))
            added = max(promoted, (converted or {}).get(kind, 0.0))
            if added > 0:
                types[kind] += added
                types["peasants"] -= added
        return types

    def capacity_k(self, tag):
        """Population capacity (thousands) of the location with its current building levels."""
        base = self.base.get(tag, {}).get("modifiers", {}).get("local_population_capacity", 0.0)
        return base + sum(
            self.raw.get(k, {}).get("local_population_capacity", 0.0) * n for k, n in self.counts[tag].items() if n
        )

    def location_yield(self, tag):
        """Food per 1,000 jobless peasants/slaves (start_food_model_v2); define x local food modifier without one."""
        y = self.yield_k.get(tag)
        return y if y is not None else self.rules.subsistence * self.food_mult.get(tag, 1.0)

    def food_capacity_per_level(self):
        """building -> province food capacity (``local_food_capacity``) one staffed level adds (Granary: 500; its 10 % capacity modifier is not modelled)."""
        cached = self.__dict__.get("_food_capacity_per_level")
        if cached is None:
            modifiers = getattr(self.rules, "modifiers", None)
            cached = {}
            if callable(modifiers) and getattr(self.rules, "buildings", None):
                for key in self.numbers:
                    try:
                        value = modifiers(key).get("local_food_capacity", 0)
                    except Exception:  # noqa: BLE001 - a building without a readable modifier block adds nothing
                        value = 0
                    if value:
                        cached[key] = float(value)
            self._food_capacity_per_level = cached
        return cached

    def serve_keys(self):
        return set((self.start.province_food.get("serve") or {}))

    def budgets(self, subsistence=None, groups=None):
        """Food budget per province/owner pool (start_food_model_v2).

        demand = the pops' food plus the overpopulation consumption; subsistence = jobless peasants and slaves x the
        location's yield (pops in jobs and the RGO's workers do not farm; laborers never do); building food = staffed
        levels' local food (scaled) plus the Province Food of their Provisioning method; Cookshops count their Serve
        food on ``cookshop_serve_share`` of the levels (1: they have no victuals recipes); Taverns add and Victualling
        Yards take their ``local_monthly_food`` (60) per staffed level. ``day0_production`` is what the engine shows on the first day (no
        Provisioning or Serve yet, overpopulation netted out as the save's production does)."""
        model = self.food_model
        share = float(model.cookshop_serve_share)
        scale = 1.0 if subsistence is None else float(subsistence) / float(self.rules.subsistence)
        converted = sim_converted(self)
        serve_keys = self.serve_keys()
        result = {}
        for group, tags in (
            (g, self.groups[g]) for g in (groups if groups is not None else self.groups)
        ):
            demand = overpop = jobless = workers = subs = own_food = day0_flat = serve_food = market_food = pop = store = 0.0
            cookshop = taverns = yards = 0
            packers = Counter()
            cap_rows = []
            for tag in tags:
                types = self.location_pops(tag, converted[tag])
                demand += sum(n * self.food.get(kind, 0) for kind, n in types.items())
                here = sum(max(0.0, n) for n in types.values())
                pop += here
                if here > 0:                              # the tribal share's flat food (tribesmen pop_percentage_impact)
                    tribal = float(model.tribal_share_food) * max(0.0, types.get("tribesmen", 0.0)) / here
                    own_food += tribal
                    day0_flat += tribal
                overpop += fm.overpopulation_food(
                    sum(types.get(t, 0.0) for t in model.overpopulation_pop_types), here, self.capacity_k(tag), model
                )
                employed = Counter()
                for k, n in self.staffed[tag].items():
                    num = self.numbers.get(k)
                    if num and n:
                        employed[num["pop_type"]] += n * num["employment_size"]
                employed["peasants"] += self.rgo_k.get(tag, 0.0)
                y = self.location_yield(tag) * scale
                for kind in model.subsistence_pop_types:
                    have = max(0.0, types.get(kind, 0.0))
                    idle = max(0.0, have - employed.get(kind, 0.0))
                    jobless += idle
                    workers += have
                    subs += idle * y
                mult = self.food_mult.get(tag, 1.0)
                for k, n in self.staffed[tag].items():
                    if not n:
                        continue
                    flat = n * mult * self.numbers.get(k, {}).get("local_monthly_food", 0)
                    if k == self.TAVERN:
                        taverns += n
                        market_food += flat + n * float(self.province_food.get(k, 0.0))
                    elif k in self.YARDS:
                        yards += n
                        packers[k] += n
                        market_food += flat
                    elif k in serve_keys:
                        cookshop += n
                        serve_food += n * (share * float(self.province_food.get(k, 0.0)) + float(model.cookshop_drink_food))
                        own_food += flat
                        day0_flat += flat
                    else:
                        own_food += flat + n * float(self.province_food.get(k, 0.0))
                        day0_flat += flat
                base = self.base.get(tag, {})
                cap_rows.append((base.get("development", 0.0), here, base.get("location_rank", "rural_settlement")))
                per_level = self.food_capacity_per_level()
                store += sum(n * per_level.get(k, 0.0) for k, n in self.staffed[tag].items() if n)
            eats = demand + overpop
            fed = subs + own_food + serve_food
            supply = fed + market_food
            capacity = fm.food_capacity(cap_rows, model) + store
            result[group] = {
                "owner": group[0],
                "province": group[1],
                "catchment": self.catchments[group],
                "region": self.locations[tags[0]].get("region", ""),
                "longitude": sum(float(self.attrs.get(t, {}).get("calibrated_lon") or 0) for t in tags) / len(tags),
                "latitude": sum(float(self.attrs.get(t, {}).get("calibrated_lat") or 0) for t in tags) / len(tags),
                "pop_k": pop,
                "demand": eats,
                "demand_base": demand,
                "overpopulation": overpop,
                "subsistence": subs,
                "subsistence_workers_k": jobless,
                "workers_k": workers,
                "jobs_k": workers - jobless,
                "building_food": own_food,
                "cookshop_levels": cookshop,
                "serve_food": serve_food,
                "tavern_levels": taverns,
                "yard_levels": yards,
                "harbor_yard_levels": packers[self.YARD],
                "grange_levels": packers[self.GRANGE],
                "market_food": market_food,
                "supply": supply,
                "balance": supply - eats,
                "coverage": supply / eats if eats else 1.0,
                "shortfall": max(0, eats - supply),
                "structural_balance": fed - eats,
                "R": fed / eats if eats else None,
                "day0_production": subs + day0_flat + market_food - overpop,
                "food_capacity": capacity,
                "capacity_months": capacity / eats if eats else None,
            }
        return result

    def order(self, tags, key):
        return sorted(
            tags,
            key=lambda t: (
                -self.cap(t, key),
                -self.base[t]["population"],
                t,
            ),
        )

    def place(self):
        for tag in sorted(self.locations):
            loc = self.locations[tag]
            proc = sp.processor_for(loc, self.start.processors)
            if proc:
                self.add(tag, proc[0], max(0, proc[1] - self.counts[tag][proc[0]]))
            # A small starting rural economy wherever the actual gates permit it (not only on matching resource
            # deposits). Food-neutral (a farm level yields what its peasants gave in subsistence) but the villages'
            # worker provisions are the baseline victuals supply, so they come before the food chain. They draw on
            # the peasant work share only; the Cookshops' conversion share stays available.
            farm = sp.farm_for(loc)
            if farm:
                self.add(tag, farm, self.start.max_farm_levels_per_location)
            elif self.crop_cfg is not None and sp.crop_location(loc):
                self.place_crops(tag)
            for key in ("fishing_village", "forest_village"):
                self.add(tag, key, max(0, 2 - self.counts[tag][key]))
        self.place_food_chain()
        self.place_construction_materials()

    def cookshop_net_food(self, tag):
        """Food one Cookshop level adds to its province: its local food plus the Serve method's Province Food on the
        share of levels that run Serve and the drink slot's expected Province Food, minus the subsistence of the peasant it turns into a laborer (the location's
        yield) and the laborer's extra consumption."""
        num = self.numbers[self.COOKSHOP]
        mult = self.food_mult.get(tag, 1.0)
        return (
            mult * num.get("local_monthly_food", 0)
            + float(self.food_model.cookshop_serve_share) * float(self.province_food.get(self.COOKSHOP, 0.0))
            + float(self.food_model.cookshop_drink_food)
            - num["employment_size"] * self.location_yield(tag)
            - num["employment_size"] * max(0, self.food.get(num["pop_type"], 0) - self.food.get("peasants", 0))
        )

    # ------------------------------------------------------------------ food chain v2 (deficit and surplus pools)
    COOKSHOP = "cookshop"
    TAVERN = "tavern"
    YARD = "victualling_yard"
    GRANGE = "grange"
    # One producer role, two buildings: the harbour Victualling Yard (20 food + shipped grain -> 3 victuals, store band
    # from about 12 months) on harbour sites, the Grange (60 food -> 1.5 victuals, band from 20 months) at the other
    # province capitals. Harbour Yard sites are filled first.
    YARDS = (YARD, GRANGE)

    def yard_levels(self, tags):
        return sum(self.counts[t][k] for t in tags for k in self.YARDS)

    def packer_levels(self, b):
        """Packer levels of a pool budget by building (budgets without the split fields count as harbour Yards)."""
        if "harbor_yard_levels" in b or "grange_levels" in b:
            return {self.YARD: b.get("harbor_yard_levels", 0), self.GRANGE: b.get("grange_levels", 0)}
        return {self.YARD: b.get("yard_levels", 0)}

    def packer(self, key):
        """(food per level, victuals per level, minimum store months) of a packing building: food from its blueprint
        modifier (none for the harbour Yard since 2026-10-03), victuals and store band from the food model config."""
        model = self.food_model
        if key not in self.numbers:
            return 0.0, 0.0, math.inf   # a building the rules do not define (test fixtures): never placed
        food = -self.numbers[key].get("local_monthly_food", 0.0)
        if key == self.YARD:
            return food, model.harbor_yard_victuals_per_level, model.harbor_yard_min_capacity_months
        return food, model.yard_victuals_per_level, model.yard_min_capacity_months

    def province_capital(self, group):
        """The pool's province capital: the engine's province capital is not in the setup files, so the highest
        ranked location stands in for it (a market centre first, then the most populous)."""
        return min(
            self.groups[group],
            key=lambda t: (
                fm.RANK_ORDER.get(self.base[t].get("location_rank"), 4),
                not self.base[t].get("is_market_center", False),
                -float(self.base[t].get("population", 0.0)),
                t,
            ),
        )

    def serve_inputs(self):
        """(raw goods any cookshop Serve method uses, raw goods one level of the configured Serve method uses)."""
        cached = self.__dict__.get("_serve_inputs")
        if cached is None:
            goods, per_level = set(), 0.0
            body = self.rules.buildings.get(self.COOKSHOP)
            serve = str((self.start.province_food.get("serve") or {}).get(self.COOKSHOP, ""))
            known = set(getattr(self.rules, "goods", {}) or {})
            for block in body.values("unique_production_methods") if isinstance(body, CList) else []:
                for method in block.entries:
                    if not (isinstance(method.value, CList) and method.key.endswith("_serve")):
                        continue
                    inputs = {
                        e.key: float(e.value) for e in method.value.entries
                        if isinstance(e.value, (int, float)) and (e.key in known or not known)
                        and e.key not in ("output", "manual_labor", "debug_max_profit")
                    }
                    goods.update(inputs)
                    if method.key == serve:
                        per_level = sum(inputs.values())
            cached = self._serve_inputs = (frozenset(goods), per_level or 2.0)
        return cached

    def market_raw_goods(self, members):
        """Raw food goods the market makes each month (the Serve Cookshops' inputs): its RGO workers on those goods
        x ``raw_goods_per_rgo_k`` (nb.eu5: 1.50 per 1,000 RGO workers)."""
        goods, _ = self.serve_inputs()
        return sum(
            self.rgo_k.get(t, 0.0) * self.food_model.raw_goods_per_rgo_k
            for g in members
            for t in self.groups[g]
            if str(self.locations[t].get("raw_material") or "") in goods
        )

    def victuals_v2(self, members, budgets):
        """(supply, demand without the Taverns, Tavern levels) of the market's victuals per month: configured producers
        (the Victualling Yards' victuals follow their pool's surplus: market_victuals_use; Cookshops make none); the
        pops' demand (game demand x ``pop_demand_scale``) and other configured consumers."""
        v = self.start.victuals
        model = self.food_model
        serve_keys = self.serve_keys()
        converted = sim_converted(self)
        supply = demand = 0.0
        imports = 0
        for group in members:
            for tag in self.groups[group]:
                for key, n in self.staffed[tag].items():
                    if not n:
                        continue
                    if key == self.TAVERN:
                        imports += n
                    elif key in self.YARDS:
                        pass   # the Yards' victuals follow their pool's surplus (market_victuals_use)
                    elif key in serve_keys:
                        pass   # Cookshops serve every dish as Province Food
                    else:
                        supply += n * float(v["producers"].get(key, 0.0))
                        demand += n * float(v["consumers"].get(key, 0.0))
                pops = self.location_pops(tag, converted[tag])
                demand += float(v["pop_demand_scale"]) * sum(n * self.victuals_pop_factors.get(kind, 0.0) for kind, n in pops.items())
        return supply, demand, imports

    def market_victuals_use(self, b):
        """Expected victuals per month the pool's Taverns buy (+) or its packers make (-): a staffed Tavern only keeps
        running while the pool is short, so it buys what the pool's gap needs (gap / 30 food per victual) up to 2 per
        level; a packer runs on what the pool's surplus gives, its own food per level at a time (harbour Yard: 20 food,
        with shipped grain, for 3 victuals; Grange: 60 food for 1.5), harbour Yards first."""
        model = self.food_model
        tavern_rate = self.food_per_level(self.TAVERN) / model.tavern_victuals_per_level
        fed = b["supply"] - b["market_food"]
        gap = b["demand"] - fed
        use = 0.0
        if b["tavern_levels"]:
            use += min(b["tavern_levels"] * model.tavern_victuals_per_level, max(0.0, gap) / tavern_rate)
        surplus = max(0.0, -gap)
        levels = self.packer_levels(b)
        for key in self.YARDS:
            n = levels.get(key, 0)
            if not n:
                continue
            food, victuals, _ = self.packer(key)
            running = min(float(n), surplus / food) if food > 0 else float(n)
            surplus -= running * food
            use -= running * victuals
        return use

    def farm_net_food(self, tag, key):
        """Food one more staffed level of the farm ``key`` adds to its province: its local food (scaled) and its
        Provisioning food, minus the subsistence its peasants gave up."""
        num = self.numbers[key]
        return (self.food_per_level(key, self.food_mult.get(tag, 1.0))
                - num["employment_size"] * self.location_yield(tag))

    def deficit_farm(self, tag):
        """The tier-0 crop farm a short pool gets its next level from at ``tag``: allowed here (native gates), room
        under its live cap, best by the location's crop weight, livestock last; None when none adds enough food."""
        cfg = self.crop_cfg
        if cfg is None:
            return None
        weights = self.crop_weights.get(tag, {})
        rank = {key: i for i, key in enumerate(cfg.buildings.values())}
        goods = self.crop_candidates(tag) & self.crop_available.get(tag, frozenset())
        floor = float(self.food_model.deficit_farm_min_net_food)
        for good in sorted(goods, key=lambda g: (g == ca.LIVESTOCK, -float(weights.get(g, 0.0)), rank[cfg.buildings[g]])):
            key = cfg.buildings[good]
            if self.farm_net_food(tag, key) >= floor:
                return key
        return None

    def _feed_with_farms(self, members, need):
        """Crop farm levels in the pools with a need, one level at a time round the pool's locations (most people
        first), each where a level adds at least ``deficit_farm_min_net_food`` (caps, workers and land through
        ``add``), until the need is met or no location takes another level. Returns the levels placed."""
        placed = 0
        for group in sorted((g for g in members if need.get(g, 0.0) > 0), key=lambda g: (-need[g], g)):
            remaining = need[group]
            tags = sorted(self.groups[group], key=lambda t: (-self.base[t]["population"], t))
            open_ = list(tags)
            while remaining > 1e-6 and open_:
                for tag in list(open_):
                    key = self.deficit_farm(tag)
                    if key is None or not self.add(tag, key, 1):
                        open_.remove(tag)
                        continue
                    self.__dict__.setdefault("crop_placed", defaultdict(Counter))[tag][key] += 1
                    remaining -= self.farm_net_food(tag, key)
                    placed += 1
                    if remaining <= 1e-6:
                        break
        return placed

    def _serve_cookshops(self, members, need, room, budgets):
        """Cookshops in the pools with a remaining need, at most ``room`` levels, one level at a time to the pool whose
        need is the largest share of its demand. A Cookshop feeds only its own province (it serves, it does not sell
        victuals), so the market's raw goods are spread over its short provinces instead of filling the largest one."""
        placed = 0
        demand = {g: max(1e-9, float(budgets[g]["demand"])) for g in members}
        blocked = set()
        cap = self.start.max_cookshop_levels_per_location
        while room > 0:
            open_ = [g for g in members if need.get(g, 0.0) > 0 and g not in blocked]
            if not open_:
                break
            group = max(open_, key=lambda g: (need[g] / demand[g], g))
            for tag in self.order(self.groups[group], self.COOKSHOP):
                net = self.cookshop_net_food(tag)
                if net <= 0:
                    break
                if self.counts[tag][self.COOKSHOP] >= cap:
                    continue
                if self.add(tag, self.COOKSHOP, 1):
                    need[group] -= net
                    room -= 1
                    placed += 1
                    break
            else:
                blocked.add(group)
                continue
            if net <= 0:
                blocked.add(group)
        return placed

    def _yard_pools(self, members, budgets, target):
        """Pools that may pack victuals: spare food beyond the target and no Tavern in the province. Well-connected
        pools first (surplus x the pool's best packer cap, which rewards harbours, market centres, roads and
        development), pools with a free harbour Yard site before all others: (group, spare food after the packers
        already there, store months, whether the pool feeds itself by the Grange's surplus share)."""
        model = self.food_model
        out = []
        for group in members:
            b = budgets[group]
            eats = b["demand"]
            fed = b["supply"] - b["market_food"]
            if eats <= 0:
                continue
            if any(self.counts[t][self.TAVERN] for t in self.groups[group]):
                continue
            levels = self.packer_levels(b)
            spare = fed - eats * target - sum(n * self.packer(k)[0] for k, n in levels.items())
            if spare > 0:
                reach = max(self.cap(t, k) for t in self.groups[group] for k in self.YARDS)
                # a free harbour Yard site first: it packs twice the victuals for a third of the food
                harbour = any(self.cap(t, self.YARD) > self.counts[t][self.YARD] for t in self.groups[group])
                surplus_ok = fed >= eats * (1.0 + model.yard_surplus_share)
                out.append((group, spare, b["capacity_months"] or 0.0, surplus_ok, harbour, (fed - eats) * reach))
        return [(g, s, m, ok) for g, s, m, ok, _, _ in sorted(out, key=lambda x: (not x[4], -x[5], x[0]))]

    def _place_yards(self, members, budgets, target, victuals):
        """Packer levels until ``victuals`` per month are covered: harbour Victualling Yards on the pool's harbour sites
        first (their store band starts lower and they ship in their grain, so any spare food will do), then the
        province capital's Grange (only where the pool feeds itself by ``yard_surplus_share``: it packs the surplus).
        A level is placed once the pool's spare food fills ``yard_min_level_share`` of that building's food per level.
        Returns the levels placed."""
        model = self.food_model
        placed = 0
        for group, spare, months, surplus_ok in self._yard_pools(members, budgets, target):
            if victuals <= 1e-6:
                break
            for key in self.YARDS:
                food, per_level, min_months = self.packer(key)
                if per_level <= 0 or key not in self.numbers:
                    continue
                if key == self.GRANGE and (not surplus_ok or not model.grange_at_start):
                    continue
                if food > 0:
                    if months < min_months:
                        continue
                    room = math.floor(spare / food + 1.0 - model.yard_min_level_share)
                else:
                    # ships its own grain (the harbour Yard since 2026-10-03): only the need and its sites limit it
                    room = math.ceil(victuals / per_level)
                want = min(room, math.ceil(victuals / per_level))
                for tag in self.order(self.groups[group], key):
                    if want <= 0 or victuals <= 1e-6:
                        break
                    n = self.add(tag, key, want)
                    want -= n
                    spare -= n * food
                    victuals -= n * per_level
                    placed += n
        return placed

    def _place_taverns(self, group, levels):
        """Tavern levels at the province capital first, then at the pool's other locations (never next to a
        Victualling Yard in the same province)."""
        if levels <= 0 or self.yard_levels(self.groups[group]):
            return 0
        capital = self.province_capital(group)
        placed = 0
        for tag in [capital] + [t for t in self.order(self.groups[group], self.TAVERN) if t != capital]:
            if levels <= 0:
                break
            n = self.add(tag, self.TAVERN, levels)
            levels -= n
            placed += n
        return placed

    def place_food_chain(self):
        """Placement v2 per market (catchment): Serve Cookshops where the market's raw goods allow, Taverns sized to
        the remaining need at the province capital, Victualling Yards in surplus pools (well-connected first) until the
        market's victuals cover the Taverns x ``victuals_target``; Taverns the market cannot supply become Cookshops."""
        model = self.food_model
        target = self.start.food_target_ratio
        per_tavern = self.food_per_level(self.TAVERN)
        # every packer must make victuals; the harbour Yard takes no store food since 2026-10-03 (it ships grain)
        if per_tavern <= 0 or any(self.packer(k)[1] <= 0 for k in self.YARDS if k in self.numbers):
            raise ValueError("Start trade requires positive food transfer units")
        vict = model.tavern_victuals_per_level
        _, raw_per_level = self.serve_inputs()
        self.before_trade = self.budgets()
        by_catchment = defaultdict(list)
        for group in self.groups:
            by_catchment[self.catchments[group]].append(group)
        self.victuals = {}
        self.market_slack = {}

        def needs(b):
            return {g: max(0.0, b[g]["demand"] * target - b[g]["supply"]) for g in b}

        for catchment, members in sorted(by_catchment.items()):
            b = self.budgets(groups=members)
            need0 = needs(b)
            raw = self.market_raw_goods(members)

            def room(share, members=members, raw=raw):
                current = self.budgets(groups=members)
                used = sum(current[g]["cookshop_levels"] for g in members) * raw_per_level
                return max(0, math.floor((share * raw - used) / raw_per_level))

            # 0. Farms first (2026-10-03, Jan): crop farm levels wherever they add food, before any kitchen or Tavern
            farms = self._feed_with_farms(members, need0)
            self.deficit_farm_levels = getattr(self, "deficit_farm_levels", 0) + farms
            if farms:
                b = self.budgets(groups=members)
                need0 = needs(b)
            # 1. Cookshops where the market's raw goods allow (all Serve: Province Food, no victuals)
            serve = self._serve_cookshops(members, dict(need0), room(model.serve_raw_goods_share), b)
            wanted = None
            placed_taverns = yards = fallback = 0
            # 2. Taverns sized to the remaining need, as far as the market's victuals reach (Victualling Yards in
            # surplus pools first); what the Taverns cannot cover goes to further Cookshops. A Tavern buys only what
            # its pool's gap needs (market_victuals_use), so a small town's level costs the market a victual, not two.
            per_victual = per_tavern / vict
            for _ in range(8):
                b = self.budgets(groups=members)
                want = {g: math.ceil(n / per_tavern) for g, n in needs(b).items() if n > 1e-6}
                if wanted is None:
                    wanted = sum(want.values())
                if not want:
                    break
                supply, other, _ = self.victuals_v2(members, b)

                def flows(b):
                    uses = [self.market_victuals_use(b[g]) for g in members]
                    return sum(u for u in uses if u > 0), -sum(u for u in uses if u < 0)

                bought, sold = flows(b)
                cost = {g: min(want[g] * vict, max(0.0, b[g]["demand"] - (b[g]["supply"] - b[g]["market_food"])) / per_victual
                               - max(0.0, self.market_victuals_use(b[g]))) for g in want}
                missing = max(0.0, (other + bought + sum(max(0.0, c) for c in cost.values())) * model.victuals_target - supply - sold)
                if missing > 1e-6:
                    placed = self._place_yards(members, b, target, missing)
                    yards += placed
                    if placed:
                        b = self.budgets(groups=members)
                        bought, sold = flows(b)
                left = (supply + sold) / model.victuals_target - other - bought
                progress = 0
                # pools that would collapse without food from outside first, cheapest (smallest gap) first: when the
                # market's victuals run out they save the most pools; then the rest from the poorest-fed up
                risk = model.import_priority_coverage
                for g in sorted(want, key=lambda g: (b[g]["coverage"] >= risk, cost[g] if b[g]["coverage"] < risk else b[g]["coverage"], g)):
                    c = max(0.0, cost[g])
                    if c > left + 1e-9:
                        continue
                    n = self._place_taverns(g, want[g])
                    if n:
                        left -= min(c, n * vict)
                        progress += n
                placed_taverns += progress
                b = self.budgets(groups=members)
                rest = needs(b)
                if any(n > 1e-6 for n in rest.values()):
                    c = self._serve_cookshops(members, rest, room(model.serve_fallback_raw_goods_share), b)
                    fallback += c
                    progress += c
                if not progress:
                    break
            after = self.budgets(groups=members)
            supply_after, other_after, imports_after = self.victuals_v2(members, after)
            flows = [self.market_victuals_use(after[g]) for g in members]
            supply_after -= sum(f for f in flows if f < 0)            # the Yards' expected victuals
            demand_after = other_after + sum(f for f in flows if f > 0)
            self.market_slack[catchment] = max(0, math.floor((supply_after / model.victuals_target - demand_after) / vict))
            self.victuals[catchment] = {
                "deficit": round(sum(need0.values()), 1),
                "raw_goods": round(raw, 1),
                "deficit_farm_levels": farms,
                "serve_cookshop_levels": serve,
                "fallback_cookshop_levels": fallback,
                "wanted_tavern_levels": wanted or 0,
                "placed_tavern_levels": placed_taverns,
                "placed_yard_levels": yards,
                "tavern_levels": imports_after,
                "unmet_food": round(sum(needs(after).values()), 1),
                "victuals_supply": round(supply_after, 1),
                "victuals_demand": round(demand_after, 1),
                "covered": round(supply_after / demand_after, 3) if demand_after else None,
            }
        self.ensure_city_taverns(self.market_slack)
        self.unallocated_yards = dict(self.market_slack)

    # ------------------------------------------------------------------ construction materials
    def construction_config(self):
        """``[worldbuilder.start.construction_materials]``: per good the producers (building -> output per level as the
        market sees it), the buildings to place (in order), their inputs, the expected construction demand per
        million pops and per queued Tavern level."""
        return dict((self.cfg.raw.get("start") or {}).get("construction_materials") or {})

    def material_balance(self, members, good, spec, pending_taverns=0):
        """(supply, expected construction demand) of ``good`` in the market per month."""
        producers = {str(k): float(v) for k, v in (spec.get("producers") or {}).items()}
        supply = sum(
            n * producers.get(key, 0.0)
            for g in members for t in self.groups[g] for key, n in self.counts[t].items() if n
        )
        # a raw material's RGOs supply it too (lumber: 1.16 per lumber RGO on day 0)
        rgo = float(spec.get("rgo_output_per_location", 0.0))
        if rgo:
            supply += rgo * sum(1 for g in members for t in self.groups[g] if str(self.locations[t].get("raw_material") or "") == good)
        pop_m = sum(self.base[t].get("population", 0.0) for g in members for t in self.groups[g]) / 1000.0
        cfg = self.construction_config()
        demand = float(cfg.get("margin", 2.0)) * float(spec.get("construction_per_million_pops", 0.0)) * pop_m
        demand += float(spec.get("per_tavern", 0.0)) * pending_taverns
        return supply, demand

    def material_inputs(self, members, spec):
        """Whether the market makes one of the good's inputs (an RGO or a placed producer of it)."""
        inputs = set(spec.get("inputs") or ())
        if not inputs:
            return True
        makers = {str(k) for k in (spec.get("input_buildings") or ())}
        for g in members:
            for t in self.groups[g]:
                if str(self.locations[t].get("raw_material") or "") in inputs:
                    return True
                if any(self.counts[t][k] for k in makers):
                    return True
        return False

    def place_construction_materials(self):
        """Every market gets a minimum monthly supply of the base construction materials (lumber, masonry, tools):
        the expected construction demand of its first years (``margin`` x the 1341 demand per million pops, plus the
        Taverns it still wants) against what its placed buildings make; missing producer levels go to the
        market's locations through the ordinary checks (caps, gates, workers, land), markets without any supply
        first. A market that makes none of a good's inputs gets no producer (reported as ``no_inputs``)."""
        cfg = self.construction_config()
        goods = {str(k): dict(v) for k, v in (cfg.get("goods") or {}).items()}
        self.construction = {}
        if not goods:
            return
        by_catchment = defaultdict(list)
        for group in self.groups:
            by_catchment[self.catchments[group]].append(group)
        pending = {c: max(0, int(v.get("wanted_tavern_levels", 0)) - int(v.get("placed_tavern_levels", 0)))
                   for c, v in getattr(self, "victuals", {}).items()}
        for good, spec in goods.items():
            report = {"markets": len(by_catchment), "short_before": 0, "zero_before": 0, "short_after": 0, "zero_after": 0,
                      "no_inputs": 0, "levels_added": Counter(), "supply_before": 0.0, "supply_after": 0.0, "demand": 0.0}
            rows = []
            for catchment, members in by_catchment.items():
                supply, demand = self.material_balance(members, good, spec, pending.get(catchment, 0))
                rows.append((supply, catchment, members, demand))
            for supply, catchment, members, demand in sorted(rows, key=lambda r: (r[0] > 1e-9, r[0] - r[3], r[1])):
                report["supply_before"] += supply
                report["demand"] += demand
                report["short_before"] += supply + 1e-9 < demand
                report["zero_before"] += supply <= 1e-9
                if supply + 1e-9 < demand:
                    if not self.material_inputs(members, spec):
                        report["no_inputs"] += 1
                    else:
                        for key in spec.get("place") or ():
                            per_level = float((spec.get("producers") or {}).get(key, 0.0))
                            if per_level <= 0 or key not in self.numbers:
                                continue
                            tags = sorted({t for g in members for t in self.groups[g]}, key=lambda t: (-self.cap(t, key), -self.base[t]["population"], t))
                            for tag in tags:
                                if supply + 1e-9 >= demand:
                                    break
                                n = self.add(tag, key, min(int(spec.get("max_levels_per_location", 2)), math.ceil((demand - supply) / per_level)))
                                supply += n * per_level
                                report["levels_added"][key] += n
                            if supply + 1e-9 >= demand:
                                break
                report["supply_after"] += supply
                report["short_after"] += supply + 1e-9 < demand
                report["zero_after"] += supply <= 1e-9
            report["levels_added"] = dict(report["levels_added"])
            for k in ("supply_before", "supply_after", "demand"):
                report[k] = round(report[k], 1)
            self.construction[good] = report

    def ensure_city_taverns(self, units):
        """Every city that is a province capital gets a Tavern, even if it initially lies idle (Taverns stand only in
        towns and larger that are province capitals since 2026-10-01; other cities are listed under not_capital).

        This minimum is independent of deficit and the ordinary one-direction
        trade policy. Do not count extra food without both workers and Victualling Yards.
        """
        self.city_tavern_minimum = {"cities": 0, "added": 0, "idle": [], "packing": [], "not_capital": []}
        key = self.TAVERN
        group_for = {tag: group for group, tags in self.groups.items() for tag in tags}
        for tag in sorted(self.locations):
            if self.base[tag].get("location_rank") not in ("city", "megalopolis"):
                continue
            self.city_tavern_minimum["cities"] += 1
            if not self.base[tag].get("is_province_capital"):
                self.city_tavern_minimum["not_capital"].append(tag)
                continue
            if self.counts[tag][key] >= 1:
                continue
            if self.yard_levels(self.groups[group_for[tag]]):
                self.city_tavern_minimum["packing"].append(tag)   # never both directions in one province
                continue
            if self.cap(tag, key) < 1:
                raise ValueError(f"City Tavern minimum exceeds allowed cap: {tag}")
            self.counts[tag][key] = 1
            self.placements.append(sp.Placement(tag, self.owners[tag], key, 1))
            self.city_tavern_minimum["added"] += 1
            num = self.numbers[key]
            pool = self.pools[tag]
            market = self.catchments[group_for[tag]]
            if units.get(market, 0) and pool.levels(
                1, num["employment_size"], num["pop_type"]
            ):
                pool.take(
                    1, num["employment_size"], num["pop_type"], tag, self.conversions
                )
                self.staffed[tag][key] += 1
                units[market] -= 1
            else:
                self.city_tavern_minimum["idle"].append(tag)

    def verify(self):
        failures = []
        for tag in sorted(self.locations):
            ctx = self.ctx(tag)
            for key, n in sorted(self.counts[tag].items()):
                if not n:
                    continue
                cap = self.rules.cap(key, ctx, gates=False)
                self.audit.append(
                    {"location": tag, "building": key, "levels": n, "cap": cap}
                )
                if n > cap:
                    failures.append(self.audit[-1])
        if failures:
            raise ValueError(f"Buildings above cap: {failures[:10]}")
        return len(self.audit)


SETUP_AUDIT_RELATIVE_PATH = Path("artifacts/data/worldbuilder/setup_validation.csv")


def setup_levels(vanilla_root, mod_root, towns=None):
    """location -> building -> levels the game places from the active setup folder: every file in it (a mod file
    replaces the vanilla file of the same name), all ``building_manager`` rows summed, plus the preset buildings of
    any ``town_setup`` a location still names (``towns``: the town setup definitions)."""
    roots = (Path(vanilla_root) / "game" / SETUP_DIR, Path(mod_root) / SETUP_DIR)
    names = sorted({p.name for root in roots if root.is_dir() for p in root.glob("*.txt")})
    levels = defaultdict(Counter)
    for name in names:
        path = roots[1] / name if (roots[1] / name).is_file() else roots[0] / name
        text = path.read_text(encoding="utf-8-sig")
        if "building_manager" not in text and "town_setup" not in text:
            continue
        for tag, local in setup_counts(path).items():
            levels[tag].update(local)
        if towns and "town_setup" in text:
            for block in parse_file(path).values("locations"):
                for entry in block.entries:
                    town = first(entry.value, "town_setup")
                    if town:
                        levels[entry.key].update(town_levels(towns, str(town)))
    return levels


def audit_setup(sim, levels, cultures=None):
    """Every setup building against the start placement's model of the engine when it validates the start (after
    on_game_start): the location must be owned, the building allowed at the location's rank, its location_potential
    must hold and its level must not exceed its max level. Whether the engine traces a World Builder river cannot be
    told offline, so river locations are checked as if it traced none (``without_river``: the setup carries only what
    holds without the river; pp_start_river_topup adds the rest under the engine's own checks). Returns one row per
    (location, building) with ``problem`` empty, ``unresolved`` (a rule the evaluator cannot read: the engine decides)
    or the error the engine would log. ``cultures``: location -> dominant culture of its setup pops (the culture-locked
    potentials of niche buildings test it)."""
    rows = []
    cultures = cultures or {}
    for tag, local in sorted(levels.items()):
        local = Counter({k: n for k, n in local.items() if n > 0})
        for key, n in sorted(local.items()):
            body = sim.rules.buildings.get(key)
            problem, cap, detail = "", None, ""
            if tag not in sim.locations:
                problem = "unowned location"
            elif body is None:
                problem = "unknown building"
            else:
                ctx = sim.ctx(tag, local, levels)   # the province's farms as the setup files place them
                if ctx.get("has_river"):
                    ctx = without_river(ctx, sim.rules)
                if cultures.get(tag):
                    ctx = {**ctx, "dominant_culture": cultures[tag]}
                rank = ctx.get("location_rank", "rural_settlement")
                # rank, potential and max level are checked independently: a rule the evaluator cannot read in one
                # (a culture-locked potential) leaves the others checked
                unresolved = []
                if first(body, rank, False) not in (True, "setup_only"):
                    problem = "invalid building (rank)"
                try:
                    if not problem and not sim.rules.test(first(body, "location_potential"), ctx):
                        problem = "invalid building (location_potential)"
                except Unresolved as exc:
                    unresolved.append(f"location_potential: {exc}")
                before = Counter(sim.rules.unsupported)
                value = sim.rules.cap(key, ctx, gates=False)
                if sim.rules.unsupported != before:
                    unresolved.extend(k for k in sim.rules.unsupported if sim.rules.unsupported[k] != before.get(k))
                else:
                    cap = value
                    if not problem and n > cap:
                        problem = "above max level"
                sim.rules.unsupported = before
                if not problem and unresolved:
                    problem, detail = "unresolved", "; ".join(unresolved)
            rows.append({"location": tag, "building": key, "levels": int(n), "cap": cap, "problem": problem, "detail": detail})
    return rows


def unguarded_topup_rows(path):
    """(location, building) of every level ``pp_start_river_topup`` adds without both engine checks around it: the
    building's potential copy (``pp_start_topup_<key>_potential``) and its live max level (``building_type_max_level``)."""
    bad = []

    def walk(node, tag, potential, maxed):
        for entry in node.entries:
            value = entry.value
            if entry.key == "change_building_level_in_location":
                key = str(first(value, "building", "")).split(":")[-1]
                if key not in potential or key not in maxed:
                    bad.append((tag, key))
            elif not isinstance(value, CList):
                continue
            elif entry.key == "if":
                limit = first(value, "limit")
                here_potential, here_max = set(potential), set(maxed)
                for k, _, v in entries(limit) if isinstance(limit, CList) else ():
                    if k == "building_type_max_level" and isinstance(v, CList):
                        here_max.add(str(first(v, "building_type", "")).split(":")[-1])
                    elif k.startswith("pp_start_topup_") and k.endswith("_potential") and v is True:
                        here_potential.add(k.removeprefix("pp_start_topup_").removesuffix("_potential"))
                walk(value, tag, here_potential, here_max)
            else:
                walk(value, entry.key.split(":")[-1] if entry.key.startswith("location:") else tag, potential, maxed)

    for block in parse_file(path).values("pp_start_river_topup"):
        walk(block, None, set(), set())
    return bad


def validate_setup(sim, repo, vanilla_root, mod_root):
    """Audit the setup files as written (``audit_setup``) and the topup's guards; any error the engine would log at
    the start fails the build. Writes every audited row to ``SETUP_AUDIT_RELATIVE_PATH``."""
    rows = audit_setup(sim, setup_levels(vanilla_root, mod_root, sim.rules.towns), sp.dominant_cultures(sim.pops))
    unguarded = unguarded_topup_rows(Path(mod_root) / TOPUP_PATH)
    path = Path(repo) / SETUP_AUDIT_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    schema = {"location": pl.String, "building": pl.String, "levels": pl.Int64, "cap": pl.Int64, "problem": pl.String, "detail": pl.String}
    pl.DataFrame(rows, schema=schema).write_csv(path)
    problems = Counter(r["problem"] for r in rows if r["problem"])
    errors = [r for r in rows if r["problem"] not in ("", "unresolved")]
    if errors or unguarded:
        raise ValueError(
            f"Setup buildings the engine would reject at game start: {dict(problems)}; first rows {errors[:10]}; "
            f"topup levels without the engine checks: {unguarded[:10]}"
        )
    return {"rows": len(rows), "levels": sum(r["levels"] for r in rows), "problems": dict(problems),
            "unguarded_topup_rows": len(unguarded), "table": str(SETUP_AUDIT_RELATIVE_PATH)}


def check_river_size_modifier(rules):
    """The caps read the river size as ``modifier:irrigant_cap_modifier`` (buildings.river_size_trigger): each
    river_flowing_through_N must carry exactly N and no other static modifier any."""
    from .buildings import RIVER_SIZE_MODIFIER

    wrong = {}
    for key, block in rules.statics.items():
        level = key.removeprefix("river_flowing_through_")
        want = float(level) if level.isdigit() else 0.0
        got = summed(block).get(RIVER_SIZE_MODIFIER, 0.0)
        if got != want:
            wrong[key] = got
    if wrong:
        raise ValueError(f"{RIVER_SIZE_MODIFIER} must equal the river size on river_flowing_through_N only: {wrong}")


SETUP_BUILDING_TRIGGERS_PATH = Path("in_game/common/scripted_triggers/pp_wb_setup_buildings.txt")
SETUP_BUILDING_HEADER = ("# Generated by ppc worldbuilder: game-start buildings of the vanilla setup kept where the World Builder "
                         "geography fails their location_potential; do not edit by hand.")


def setup_building_trigger(key):
    return f"pp_wb_setup_{key}_location"


def _mentions(node, key):
    if not isinstance(node, CList):
        return False
    return any(k == key or _mentions(v, key) for k, _, v in entries(node))


def keep_setup_buildings(sim, keys, mod_root):
    """Keep the game's setup buildings of ``keys`` ([worldbuilder.start] keep_setup_buildings) where the World Builder
    geography fails their location_potential, as the World Builder test mod does (terraces, fruit orchards, tar kilns,
    lumber mills on land it made unwooded or flat).

    The engine keeps a setup building that fails its location_potential at game start, but deletes it when the
    location changes owner, government or rank, and ``drop_invalid`` drops it from the setup. For every key,
    ``pp_wb_setup_<key>_location`` lists the locations whose setup row fails the potential without it; each key's
    location_potential (its blueprint) tests that trigger in its top-level OR, so these buildings stay valid for good.
    Evaluated before ``drop_invalid`` on the setup rows (vanilla setup plus the mod's extra setup files); the trigger
    is always written (``always = no`` when nothing fails), so the potentials never name an unknown trigger.
    Returns key -> kept locations and the keys whose potential does not test the trigger yet."""
    from eu5gameparser.clausewitz.parser import parse_text

    kept, unreferenced = {}, []
    lines = [SETUP_BUILDING_HEADER]
    for key in keys:
        body = sim.rules.buildings.get(key)
        if body is None:
            raise ValueError(f"[worldbuilder.start] keep_setup_buildings: unknown building {key!r}")
        trigger = setup_building_trigger(key)
        potential = first(body, "location_potential")
        if not _mentions(potential, trigger):
            unreferenced.append(key)
        tags = []
        for tag in sorted(sim.locations):
            if not sim.counts[tag].get(key):
                continue
            ctx = sim.ctx(tag)
            ctx = {**ctx, "trigger_values": {**ctx.get("trigger_values", {}), trigger: False}}
            try:
                valid = sim.rules.test(potential, ctx)
            except Unresolved:
                continue
            if not valid:
                tags.append(tag)
        kept[key] = tags
        condition = ("OR = { " + " ".join(f"this = location:{t}" for t in tags) + " }") if tags else "always = no"
        lines.append(f"{trigger} = {{\n\t{condition}\n}}")
        sim.rules.triggers[trigger] = parse_text("trigger = {" + condition + "}").entries[0].value
    path = Path(mod_root) / SETUP_BUILDING_TRIGGERS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\ufeff" + "\n\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    sim.__dict__.pop("_caps", None)   # memoised caps were evaluated with the previous trigger
    return kept, unreferenced


def run(*, repo, project, mod_root, vanilla_root, cfg, contract, caps, locations, development=None):
    write_market_caps(repo, mod_root)
    rules = Rules(repo, project)
    check_river_size_modifier(rules)
    start = sp.StartConfig.from_raw(cfg.raw.get("start"))
    owners = sp.load_owners(vanilla_root, mod_root)
    # Always derive ranks/presets from vanilla, not last build's sanitized copy.
    ranks = sp.load_ranks(vanilla_root, Path("/nonexistent-start-source"))
    pops = sp.load_pops(vanilla_root)
    food = sp.load_pop_food_consumption(vanilla_root, mod_root)
    doc, vanilla = seed_vanilla(vanilla_root, rules, owners)
    extra = additional_setups(vanilla_root, mod_root)
    improvements = setup_counts(mod_root / sp.IMPROVEMENT_SETUP_PATH)
    initial = defaultdict(Counter)
    for tag, counts in vanilla.items():
        if tag in owners:
            initial[tag].update({k: n for k, n in counts.items() if k not in caps})
    for _, counts in extra.values():
        for tag, local in counts.items():
            if tag in owners:
                initial[tag].update(local)
    for tag, counts in improvements.items():
        initial[tag].update(counts)
    centres = set()
    for path in sp.setup_files(vanilla_root, mod_root, "03_markets.txt"):
        for manager in parse_file(path).values("market_manager"):
            centres.update(str(v) for v in manager.values("add_market"))
    if development is None:
        from .development import compute_start_development

        development = compute_start_development(repo, project)
    targets = (
        contract.location_targets.drop("development")
        .join(development, on="location_tag", how="left")
        .with_columns(pl.col("development").fill_null(0))
    )
    contract = replace(contract, location_targets=targets)
    from prosper_or_perish_constructor.crop_farms import load_crop_table

    province_food = province_food_per_level(rules, start.province_food)
    sim = Simulation(
        repo=repo,
        crop_threshold=load_crop_table(repo).threshold,
        province_food=province_food,
        rules=rules,
        cfg=cfg,
        start=start,
        contract=contract,
        locations=locations,
        pops=pops,
        owners=owners,
        ranks=ranks,
        food=food,
        initial=initial,
        improvement_keys=set(caps),
        market_centres=centres,
    )
    keep_keys = [str(k) for k in ((cfg.raw.get("start") or {}).get("keep_setup_buildings") or [])]
    setup_buildings_kept, setup_keepers_unreferenced = keep_setup_buildings(sim, keep_keys, mod_root)
    sim.drop_invalid()
    sim.clamp()
    sim.refresh_navigation()
    # Keep source rows split: improvements, expanded vanilla presets, new plan.
    kept_improvements = defaultdict(Counter)
    kept_vanilla = defaultdict(Counter)
    for tag, counts in sim.counts.items():
        for key, n in counts.items():
            if key in caps:
                kept_improvements[tag][key] = n
            else:
                kept_vanilla[tag][key] = n
    sim.workers()
    sim.place()
    audited = sim.verify()
    if rules.unsupported:
        raise ValueError(
            "Unresolved starting rules: " + json.dumps(dict(rules.unsupported))
        )
    # Merge repeated incremental placements into a single setup row.
    counts = defaultdict(Counter)
    for p in sim.placements:
        counts[p.location][p.building] += p.level
    # The river share of each starting building is added at game start, not in the setup (river_topup).
    topup = sim.river_topup()
    for (tag, key), n in topup.items():
        for source in (counts, kept_vanilla, kept_improvements):
            take = min(n, source[tag][key])
            source[tag][key] -= take
            n -= take
    # each topup level is added under the engine's own potential and max-level checks, from the level the setup places
    write_topup(
        topup,
        owners,
        mod_root,
        base={(tag, key): counts[tag][key] + kept_vanilla[tag][key] + kept_improvements[tag][key] for tag, key in topup},
        potentials={key: first(rules.buildings.get(key), "location_potential") for _, key in topup},
        first_keys=frozenset({*getattr(sim, "kitchen_counters", {}), *getattr(sim, "yard_counters", {})}),
    )
    for name, (extra_doc, counts_extra) in extra.items():
        kept = defaultdict(Counter)
        for tag, local in counts_extra.items():
            for key, n in local.items():
                kept[tag][key] = min(n, kept_vanilla[tag][key])
                kept_vanilla[tag][key] -= kept[tag][key]
        write_setup(extra_doc, kept, owners, mod_root / SETUP_DIR / name)
    write_vanilla(doc, kept_vanilla, owners, mod_root)
    rows = [
        f" {key} = {{ tag = {owners[tag]} level = {n} location = {tag} }}"
        for tag, counts in sorted(kept_improvements.items())
        for key, n in sorted(counts.items())
        if n > 0
    ]
    (mod_root / sp.IMPROVEMENT_SETUP_PATH).write_text(
        "\ufeff"
        + sp.GENERATED
        + "\nbuilding_manager = {\n"
        + "\n".join(rows)
        + "\n}\n",
        encoding="utf-8",
    )
    placements = [
        sp.Placement(tag, owners[tag], key, n)
        for tag, local in sorted(counts.items())
        for key, n in sorted(local.items())
        if n
    ]
    sp.write_start_setup(placements, mod_root)
    setup_validation = validate_setup(sim, repo, vanilla_root, mod_root)
    pop_report = sp.write_pops(vanilla_root, mod_root, sim.conversions)
    for rel in sp.LEGACY_FILES:
        if rel.endswith("07_cities_and_buildings.txt"):
            continue
        path = mod_root / rel
        if path.is_file():
            path.unlink()
    folder = repo / "artifacts/data/worldbuilder/food_simulation"
    folder.mkdir(parents=True, exist_ok=True)
    budgets = sim.budgets()
    pl.DataFrame(list(budgets.values())).sort("shortfall", descending=True).write_csv(
        folder / "provinces.csv"
    )
    pl.DataFrame(sim.audit).write_csv(folder / "building_caps.csv")
    pl.DataFrame(
        sim.trimmed,
        schema={
            "location": pl.String,
            "building": pl.String,
            "before": pl.Int64,
            "after": pl.Int64,
        },
    ).write_csv(folder / "clamped_buildings.csv")
    sensitivity = []
    for factor in sorted({1.0, 1.25, float(rules.subsistence), 1.75, 2.0}):
        b = list(sim.budgets(factor).values())
        sensitivity.append(
            {
                "subsistence": factor,
                "deficit_provinces": sum(r["shortfall"] > 1e-6 for r in b),
                "missing_food": sum(r["shortfall"] for r in b),
                "supply": sum(r["supply"] for r in b),
                "demand": sum(r["demand"] for r in b),
            }
        )
    pl.DataFrame(sensitivity).write_csv(folder / "subsistence_sensitivity.csv")
    diagnostics = []
    for tag, ctx in sorted(sim.base.items()):
        current = sim.ctx(tag)
        diagnostics.append(
            {
                "location_tag": tag,
                "region": ctx.get("region"),
                "province": ctx.get("province"),
                "owner": owners[tag],
                "rank": ranks.get(tag, "rural_settlement"),
                "population_k": ctx["population"],
                "development": ctx["development"],
                "capacity_people": current["modifiers"]["local_population_capacity"]
                * 1000,
                "tavern_cap": rules.cap(sim.TAVERN, {**current, "initializing": False}
                ),
                "yard_cap": rules.cap(sim.YARD, {**current, "initializing": False}
                ),
                "setup_tavern_cap": rules.cap(sim.TAVERN, current),
                "setup_yard_cap": rules.cap(sim.YARD, current),
                "tavern_levels": sim.counts[tag][sim.TAVERN],
                "yard_levels": sim.counts[tag][sim.YARD],
                "grange_cap": rules.cap(sim.GRANGE, {**current, "initializing": False}),
                "grange_levels": sim.counts[tag][sim.GRANGE],
                "crop_location": sp.crop_location(sim.locations[tag]),
                "crop_planned_levels": sum(sim.crop_plan.get(tag, {}).values()),
                "crop_placed_levels": sum(sim.crop_placed.get(tag, {}).values()),
                **{f"{key}_levels": sim.counts[tag][key] for key in sp.FARMS},
                "food_modifier": round(sim.food_mult[tag] - 1.0, 4),
                "rgo_workers_k": round(sim.rgo_k[tag], 3),
                "engine_promoted_k": round(
                    sum(n for k, n in sim.est_pops[tag].items() if k != "peasants")
                    - sum(p.size_k for p in pops.get(tag, []) if p.type != "peasants"),
                    3,
                ),
            }
        )
    pl.DataFrame(diagnostics).write_csv(repo / sp.TABLE_RELATIVE_PATH)
    crop_tags = sorted(t for t, loc in sim.locations.items() if sp.crop_location(loc))
    ca.write_report(
        sim.crop_plan,
        sim.crop_weights,
        repo / CROP_REPORT_RELATIVE_PATH,
        cfg=sim.crop_cfg,
        available=sim.crop_available,
        tags=crop_tags,
        placed=sim.crop_placed,
    )
    crop_by_building = Counter()
    for local in sim.crop_placed.values():
        crop_by_building.update({k: n for k, n in local.items() if n})
    good_of = {b: g for g, b in sim.crop_cfg.buildings.items()}
    crop_total = sum(crop_by_building.values())
    crops = {
        "locations": len(crop_tags),
        "locations_with_crop_farms": sum(1 for t in crop_tags if sum(sim.crop_placed.get(t, {}).values())),
        "planned_levels": sum(sum(p.values()) for p in sim.crop_plan.values()),
        "placed_levels": crop_total,
        "levels_by_building": dict(sorted(crop_by_building.items(), key=lambda kv: -kv[1])),
        "livestock_share": round(crop_by_building.get(sim.crop_cfg.buildings[ca.LIVESTOCK], 0) / crop_total, 4) if crop_total else None,
        "report": str(CROP_REPORT_RELATIVE_PATH),
    }
    demand_by_type = Counter()
    converted = sim_converted(sim)
    for tag in sim.locations:
        for kind, n in sim.location_pops(tag, converted[tag]).items():
            demand_by_type[kind] += n * food.get(kind, 0)
    summary = {
        "locations_planned": len(sim.locations),
        "rows": len(placements),
        "levels_by_building": dict(sum(counts.values(), Counter())),
        "crop_levels_total": crop_total,
        "crop_levels_by_good": {good_of[k]: n for k, n in sorted(crop_by_building.items(), key=lambda kv: -kv[1])},
        "crops": crops,
        "province_food_per_level": {k: v for k, v in province_food.items() if k in sim.numbers and any(sim.counts[t][k] for t in sim.locations)},
        "river_topup_levels": dict(sum((Counter({key: n}) for (_, key), n in topup.items()), Counter())),
        "subsistence_define": rules.subsistence,
        "demand_by_pop_type": {k: round(v, 1) for k, v in sorted(demand_by_type.items(), key=lambda kv: -kv[1])},
        "engine_promotion_people": round(
            1000
            * sum(
                sum(n for k, n in sim.est_pops[t].items() if k != "peasants")
                - sum(p.size_k for p in pops.get(t, []) if p.type != "peasants")
                for t in sim.locations
            )
        ),
        "rgo_workers_people": round(1000 * sum(sim.rgo_k.values())),
        "victuals": {
            "supply": round(sum(c["victuals_supply"] for c in sim.victuals.values()), 1),
            "demand": round(sum(c["victuals_demand"] for c in sim.victuals.values()), 1),
            "deficit_farm_levels": sum(c.get("deficit_farm_levels", 0) for c in sim.victuals.values()),
            "serve_cookshop_levels": sum(c["serve_cookshop_levels"] for c in sim.victuals.values()),
            "fallback_cookshop_levels": sum(c["fallback_cookshop_levels"] for c in sim.victuals.values()),
            "wanted_tavern_levels": sum(c["wanted_tavern_levels"] for c in sim.victuals.values()),
            "placed_tavern_levels": sum(c["placed_tavern_levels"] for c in sim.victuals.values()),
            "placed_yard_levels": sum(c["placed_yard_levels"] for c in sim.victuals.values()),
            "unmet_food": round(sum(c["unmet_food"] for c in sim.victuals.values()), 1),
            "markets": len(sim.victuals),
            "markets_covered": sum(1 for c in sim.victuals.values() if c["covered"] is None or c["covered"] >= sim.food_model.victuals_target - 1e-9),
            "catchments": sim.victuals,
        },
        "construction_materials": getattr(sim, "construction", {}),
        "food_model": {
            "structural_short_pools": sum(1 for b in sim.before_trade.values() if b["structural_balance"] < 0),
            "pools_R_below_1": sum(1 for b in budgets.values() if b["R"] is not None and b["R"] < 1.0),
            "demand_base": round(sum(b["demand_base"] for b in budgets.values())),
            "overpopulation": round(sum(b["overpopulation"] for b in budgets.values())),
            "subsistence": round(sum(b["subsistence"] for b in budgets.values())),
            "building_food": round(sum(b["building_food"] for b in budgets.values())),
            "serve_food": round(sum(b["serve_food"] for b in budgets.values())),
            "market_food": round(sum(b["market_food"] for b in budgets.values())),
            "day0_production": round(sum(b["day0_production"] for b in budgets.values())),
        },
        "tavern_food": sim.food_per_level(sim.TAVERN),
        "yard_food": sim.numbers[sim.YARD].get("local_monthly_food", 0.0),
        "building_rows_audited": audited,
        "over_cap_rows": 0,
        "setup_validation": setup_validation,
        "setup_buildings_kept": {k: len(v) for k, v in setup_buildings_kept.items()},
        "setup_building_keepers_unreferenced": setup_keepers_unreferenced,
        "clamped_rows": len(sim.trimmed),
        "clamped_levels": sum(r["before"] - r["after"] for r in sim.trimmed),
        "provinces": len(budgets),
        "provinces_short_of_food": sum(b["shortfall"] > 1e-6 for b in budgets.values()),
        "food_target_ratio": start.food_target_ratio,
        "provinces_below_food_target": sum(
            b["supply"] + 1e-6 < b["demand"] * start.food_target_ratio
            for b in budgets.values()
        ),
        "food_shortfall": sum(b["shortfall"] for b in budgets.values()),
        "food_demand": sum(b["demand"] for b in budgets.values()),
        "subsistence_sensitivity": sensitivity,
        "unallocated_yard_levels": sim.unallocated_yards,
        "city_tavern_minimum": sim.city_tavern_minimum,
        "unresolved_rules": dict(rules.unsupported),
        "placement_rejections": dict(sim.rejections),
        "pops": pop_report,
        "assumptions": [
            "Full staffing of ordinary placed food buildings; mandatory city Taverns count food only with workers and Victualling Yard backing.",
            "Nearest starting market centre within the same game region is an offline catchment proxy, not engine market access.",
            "RGO size and market access use zero lower bounds for cap safety; unsupported rules fail closed.",
            "Budget excludes seasonal harvests, prices, trade competition, armies and engine-only country modifiers.",
            "Subsistence (start_food_model_v2): jobless peasants and slaves x the location's fitted yield; the RGO's workers and pops in jobs do not farm, laborers never do.",
            "Overpopulation adds +0.5 peasant consumption per unit of pop / capacity - 1 (the mod's overpopulation modifier).",
            "Province Food (local_food) of the Provisioning methods counts per staffed level, unscaled; the Cookshops' Serve food counts on every staffed level (they have no victuals recipes).",
        ],
    }
    from . import food_sim

    summary["validator"] = food_sim.write_inputs_and_run(repo, sim, budgets, cfg)
    (repo / sp.REPORT_RELATIVE_PATH).write_text(json.dumps(summary, indent=2) + "\n")
    (folder / "report.json").write_text(json.dumps(summary, indent=2) + "\n")
    from .food_report import write as write_report

    write_report(folder, summary, list(budgets.values()), diagnostics)
    return summary
