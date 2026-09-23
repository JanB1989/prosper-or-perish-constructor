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

from . import start_placement as sp
from .market_capacity import write as write_market_caps
from .start_rules import Rules, first


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


def seed_vanilla(vanilla_root, rules, owners):
    path = vanilla_root / "game/main_menu/setup/start/07_cities_and_buildings.txt"
    doc = parse_file(path)
    counts = setup_counts(path)
    for block in doc.values("locations"):
        for entry in block.entries:
            if entry.key not in owners:
                continue
            town = first(entry.value, "town_setup")
            if town in rules.towns:
                for building in rules.towns[town].entries:
                    if isinstance(building.value, (int, float)):
                        counts[entry.key][building.key] += int(building.value)
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
        mod_root / "main_menu/setup/start/07_cities_and_buildings.txt",
        expand_presets=True,
    )


def additional_setups(vanilla_root, mod_root):
    """Find building managers outside the town and generated placement files."""
    base = vanilla_root / "game/main_menu/setup/start"
    target = mod_root / "main_menu/setup/start"
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


def plan_food_chain(deficit, victuals_surplus, food_per_import, food_per_cookery, victuals_per_cookery, victuals_per_import, absorb):
    """Cookery and import-market levels that cover a catchment's food deficit while the imports buy ``absorb`` of
    the victuals the catchment makes (existing surplus plus the new cookeries'). Returns (cookery, import) levels.

    Food: cookery x food_per_cookery + imports x food_per_import >= deficit.
    Victuals: imports x victuals_per_import = absorb x (victuals_surplus + cookery x victuals_per_cookery).
    """
    if deficit <= 0 or food_per_import <= 0 or victuals_per_import <= 0:
        return 0, 0
    food_per_import_victual = food_per_import * absorb / victuals_per_import
    from_surplus = food_per_import_victual * max(0.0, victuals_surplus)
    if from_surplus >= deficit:
        return 0, math.ceil(deficit / food_per_import)
    per_cookery = food_per_cookery + food_per_import_victual * victuals_per_cookery
    if per_cookery <= 0:
        return 0, 0
    cookery = math.ceil((deficit - from_surplus) / per_cookery)
    imports = math.ceil(absorb * (max(0.0, victuals_surplus) + cookery * victuals_per_cookery) / victuals_per_import)
    return cookery, imports


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


class Simulation:
    # Engine start state per location (filled in __init__; empty means "as the pops file says").
    est_pops: dict = {}
    food_mult: dict = {}
    rgo_k: dict = {}
    victuals_pop_factors: dict = {}
    victuals: dict = {}

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
    ):
        self.rules, self.cfg, self.start = rules, cfg, start
        self.pops, self.owners, self.ranks, self.food = pops, owners, ranks, food
        self.counts = initial
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
        self.markets = market_centres
        self.raw = {
            key: rules.modifiers(key, "raw_modifier") for key in rules.buildings
        }
        self.numbers = {key: rules.numbers(key) for key in rules.buildings}
        self.base = {}
        self.neighbors = defaultdict(list)
        self.navigation = cfg.raw.get("_navigation", {})
        self.refresh_navigation()
        # Engine start state the pops file does not show: setup promotion out of the peasants, the RGO's own
        # workers, and the local food modifier of rank and classes (scales subsistence and building food alike).
        self.est_pops = {}
        self.food_mult = {}
        self.rgo_k = {}
        self.victuals_pop_factors = rules.victuals_pop_factors()
        for tag, loc in self.locations.items():
            a = self.attrs.get(tag, {})
            target = self.targets.get(tag, {})
            rank = ranks.get(tag, "rural_settlement")
            self.est_pops[tag] = sp.estimate_start_pops(pops.get(tag, []), rank, start)
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
            ctx = {
                **loc,
                "location_tag": tag,
                "location_rank": rank,
                "population": sum(p.size_k for p in pops.get(tag, [])),
                "development": float(target.get("development") or 0),
                "owner": owners[tag],
                "is_ownable": True,
                "has_river": bool(level),
                "is_coastal": bool(loc.get("is_coastal")) or bool(self.neighbors[tag]),
                "is_adjacent_to_lake": str(a.get("is_adjacent_to_lake", "")).lower()
                == "true",
                "market_access": 0.0,
                "max_rgo_workers": 0.0,
                "is_market_center": tag in market_centres,
                "initializing": True,
                "variables": {},
                "static_modifiers": static,
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
            self.base[tag] = ctx
        self.groups = defaultdict(list)
        for tag, loc in self.locations.items():
            self.groups[(owners[tag], str(loc.get("province") or tag))].append(tag)
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

    def ctx(self, tag):
        base = self.base[tag]
        mods = defaultdict(float, base["modifiers"])
        for key, n in self.counts[tag].items():
            for k, v in self.raw.get(key, {}).items():
                mods[k] += v * n
        return {**base, "buildings": self.counts[tag], "modifiers": dict(mods)}

    def cap(self, tag, key, gates=True):
        """``Rules.cap`` on the location's current state. Between navigation refreshes the context depends only
        on the location's building levels, so results are memoised per level state."""
        state = (tag, key, gates, tuple(sorted((k, n) for k, n in self.counts[tag].items() if n)))
        cache = self.__dict__.setdefault("_caps", {})
        cached = cache.get(state)
        if cached is None:
            cached = cache[state] = self.rules.cap(key, self.ctx(tag), gates=gates)
        return cached

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
                    -self.numbers.get(kv[0], {}).get("local_monthly_food", 0),
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
            if any(
                n > self.cap(tag, k, gates=False)
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

    def budgets(self, subsistence=None, groups=None):
        value = self.rules.subsistence if subsistence is None else subsistence
        converted = defaultdict(Counter)
        for c in self.conversions:
            converted[c.location][c.to_type] += c.size_k
        subsistence_types = self.cfg.raw.get("start", {}).get(
            "subsistence_pop_types", ["peasants", "laborers", "slaves"]
        )
        result = {}
        for group, tags in (
            (g, self.groups[g]) for g in (groups if groups is not None else self.groups)
        ):
            demand = unemployed = supply = 0.0
            for tag in tags:
                types = self.location_pops(tag, converted[tag])
                demand += sum(n * self.food.get(kind, 0) for kind, n in types.items())
                mult = self.food_mult.get(tag, 1.0)
                for kind in subsistence_types:
                    employed = sum(
                        n * self.numbers[k]["employment_size"]
                        for k, n in self.staffed[tag].items()
                        if self.numbers[k]["pop_type"] == kind
                    )
                    if kind == "peasants":
                        employed += self.rgo_k.get(tag, 0.0)
                    # Workers weighted by the local food modifier so subsistence = workers x define.
                    unemployed += max(0, types[kind] - employed) * mult
                supply += mult * sum(
                    n * self.numbers[k]["local_monthly_food"]
                    for k, n in self.staffed[tag].items()
                )
            subs = unemployed * value
            supply += subs
            result[group] = {
                "owner": group[0],
                "province": group[1],
                "catchment": self.catchments[group],
                "region": self.locations[tags[0]].get("region", ""),
                "longitude": sum(
                    float(self.attrs.get(t, {}).get("calibrated_lon") or 0)
                    for t in tags
                )
                / len(tags),
                "latitude": sum(
                    float(self.attrs.get(t, {}).get("calibrated_lat") or 0)
                    for t in tags
                )
                / len(tags),
                "demand": demand,
                "subsistence": subs,
                "subsistence_workers_k": unemployed,
                "supply": supply,
                "balance": supply - demand,
                "coverage": supply / demand if demand else 1.0,
                "shortfall": max(0, demand - supply),
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
            # the peasant work share only; the cookeries' conversion share stays available.
            farm = sp.farm_for(loc)
            if farm:
                self.add(tag, farm, self.start.max_farm_levels_per_location)
            for key in ("fishing_village", "forest_village"):
                self.add(tag, key, max(0, 2 - self.counts[tag][key]))
        self.place_trade_and_cookeries()

    def cookery_net_food(self, tag):
        """Food one cookery level adds to its province: its output minus the subsistence and extra consumption of the
        peasants it turns into laborers; local food is scaled by the location's modifier."""
        num = self.numbers["cookery"]
        return self.food_mult.get(tag, 1.0) * (
            num["local_monthly_food"] - num["employment_size"] * self.rules.subsistence
        ) - num["employment_size"] * max(
            0, self.food.get(num["pop_type"], 0) - self.food.get("peasants", 0)
        )

    def victuals_balance(self, catchment):
        """Victuals the catchment's buildings make and take each month, and what its pops buy (game demand
        scaled by the observed share), before any import markets are placed."""
        v = self.start.victuals
        supply = demand = 0.0
        converted = sim_converted(self)
        for group, tags in self.groups.items():
            if self.catchments[group] != catchment:
                continue
            for tag in tags:
                for key, n in self.counts[tag].items():
                    supply += n * float(v["producers"].get(key, 0.0))
                    if key != "victuals_market_import":
                        demand += n * float(v["consumers"].get(key, 0.0))
                pops = self.location_pops(tag, converted[tag])
                demand += float(v["pop_demand_scale"]) * sum(
                    n * self.victuals_pop_factors.get(kind, 0.0) for kind, n in pops.items()
                )
        return supply, demand

    def place_trade_and_cookeries(self):
        before = self.budgets()
        export = -self.numbers["victuals_market"]["local_monthly_food"]
        imports = self.numbers["victuals_market_import"]["local_monthly_food"]
        if export <= 0 or imports <= 0:
            raise ValueError("Start trade requires positive food transfer units")
        v = self.start.victuals
        per_import = float(v["consumers"].get("victuals_market_import", 0.0))
        per_cookery = float(v["producers"].get("cookery", 0.0))
        absorb = float(v["absorb_share"])
        target = self.start.food_target_ratio
        units = defaultdict(int)
        # Export only food beyond the local reserve target, up to what the catchment's deficits could use.
        requested = defaultdict(int)
        for group, b in before.items():
            requested[self.catchments[group]] += max(0, math.ceil((b["demand"] * target - b["supply"]) / imports))
        for group, tags in sorted(self.groups.items(), key=lambda kv: -before[kv[0]]["balance"]):
            b = before[group]
            market = self.catchments[group]
            spare = min(
                max(0, math.floor((b["supply"] - b["demand"] * target) / export)),
                max(0, requested[market] - units[market]),
            )
            for tag in self.order(tags, "victuals_market"):
                if not spare:
                    break
                n = self.add(tag, "victuals_market", spare)
                spare -= n
                units[market] += n
        # Per catchment: cover the deficit with cookeries (food plus victuals) and import markets (victuals into
        # food) so that the imports buy the configured share of the victuals the catchment makes.
        by_catchment = defaultdict(list)
        for group in self.groups:
            by_catchment[self.catchments[group]].append(group)
        self.victuals = {}
        urban_ranks = ("town", "city", "megalopolis")

        def is_urban(group):
            return any(self.base[t]["location_rank"] in urban_ranks for t in self.groups[group])

        for catchment, members in sorted(by_catchment.items()):
            budgets = self.budgets(groups=members)
            need = {g: max(0.0, budgets[g]["demand"] * target - budgets[g]["supply"]) for g in members}
            deficit = sum(need.values())
            supply0, demand0 = self.victuals_balance(catchment)
            plan = plan_food_chain(deficit, supply0 - demand0, imports, self.numbers["cookery"]["local_monthly_food"] - self.numbers["cookery"]["employment_size"] * (self.rules.subsistence + max(0, self.food.get("laborers", 0) - self.food.get("peasants", 0))), per_cookery, per_import, absorb)
            cookery_budget = plan[0]
            placed_cookeries = 0
            # Cookeries: rural deficits first (their peasants convert; towns keep their nobles for imports).
            for group in sorted(members, key=lambda g: (is_urban(g), -need[g])):
                if cookery_budget <= 0 or need[group] <= 0:
                    continue
                for tag in self.order(self.groups[group], "cookery"):
                    net = self.cookery_net_food(tag)
                    if net <= 0 or cookery_budget <= 0 or need[group] <= 0:
                        break
                    n = self.add(tag, "cookery", min(self.start.max_cookery_levels_per_location, math.ceil(need[group] / net), cookery_budget))
                    need[group] -= n * net
                    cookery_budget -= n
                    placed_cookeries += n
            # Imports buy the configured share of the victuals actually made: the existing surplus plus the
            # cookeries that were really placed. Urban deficits first, then the rest, then extra urban levels.
            import_budget = max(0, math.floor(absorb * (max(0.0, supply0 - demand0) + placed_cookeries * per_cookery) / per_import)) if per_import > 0 else 0
            placed_imports = 0

            def place_imports(group, levels):
                n_total = 0
                for tag in self.order(self.groups[group], "victuals_market_import"):
                    if levels <= 0:
                        break
                    if any(self.counts[t]["victuals_market"] for t in self.groups[group]):
                        break   # never opposite transfers in one province
                    n = self.add(tag, "victuals_market_import", levels)
                    levels -= n
                    n_total += n
                return n_total

            import_budget_total = import_budget
            for group in sorted(members, key=lambda g: (not is_urban(g), -need[g])):
                if import_budget <= 0 or need[group] <= 0:
                    continue
                n = place_imports(group, min(import_budget, math.ceil(need[group] / imports)))
                need[group] -= n * imports
                import_budget -= n
                placed_imports += n
            imports_for_need = placed_imports
            urban = sorted((g for g in members if is_urban(g)), key=lambda g: -budgets[g]["demand"])

            def spread(budget):
                """Leftover budget: the towns and cities become importers beyond their deficit (round-robin,
                one level per pass, so the victuals find buyers without piling up in one place)."""
                nonlocal placed_imports
                while budget > 0 and urban:
                    progressed = False
                    for group in urban:
                        if budget <= 0:
                            break
                        n = place_imports(group, 1)
                        if n:
                            budget -= n
                            placed_imports += n
                            progressed = True
                    if not progressed:
                        break
                return budget

            import_budget = spread(import_budget)
            # Deficits the imports could not reach (rural caps, no nobles, budget spent) fall back to cookeries;
            # the victuals those make are bought by further urban import levels.
            fallback = 0
            for group in sorted(members, key=lambda g: -need[g]):
                if need[group] <= 0:
                    continue
                for tag in self.order(self.groups[group], "cookery"):
                    net = self.cookery_net_food(tag)
                    if net <= 0 or need[group] <= 0:
                        break
                    n = self.add(tag, "cookery", min(self.start.max_cookery_levels_per_location, math.ceil(need[group] / net)))
                    need[group] -= n * net
                    fallback += n
            if fallback and per_import > 0:
                extra = math.floor(absorb * fallback * per_cookery / per_import) + import_budget
                import_budget_total += extra - import_budget
                import_budget = spread(extra)
            supply, demand = self.victuals_balance(catchment)
            demand += placed_imports * per_import
            self.victuals[catchment] = {
                "deficit": round(deficit, 1),
                "planned_cookery_levels": plan[0],
                "placed_cookery_levels": placed_cookeries,
                "fallback_cookery_levels": fallback,
                "planned_import_levels": plan[1],
                "import_budget": import_budget_total,
                "placed_import_levels": placed_imports,
                "imports_for_deficits": imports_for_need,
                "unmet_food": round(sum(max(0.0, n) for n in need.values()), 1),
                "victuals_supply": round(supply, 1),
                "victuals_demand": round(demand, 1),
                "absorbed": round(demand / supply, 3) if supply else None,
            }
        self.ensure_city_imports(units)
        self.before_trade = before
        self.unallocated_exports = dict(units)

    def ensure_city_imports(self, units):
        """Every city gets import infrastructure, even if it initially lies idle.

        This minimum is independent of deficit and the ordinary one-direction
        trade policy. Do not count extra food without both workers and exports.
        """
        self.city_import_minimum = {"cities": 0, "added": 0, "idle": []}
        key = "victuals_market_import"
        group_for = {tag: group for group, tags in self.groups.items() for tag in tags}
        for tag in sorted(self.locations):
            if self.base[tag].get("location_rank") not in ("city", "megalopolis"):
                continue
            self.city_import_minimum["cities"] += 1
            if self.counts[tag][key] >= 1:
                continue
            if self.cap(tag, key) < 1:
                raise ValueError(f"City import minimum exceeds allowed cap: {tag}")
            self.counts[tag][key] = 1
            self.placements.append(sp.Placement(tag, self.owners[tag], key, 1))
            self.city_import_minimum["added"] += 1
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
                self.city_import_minimum["idle"].append(tag)

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


def run(*, repo, project, mod_root, vanilla_root, cfg, contract, caps, locations, development=None):
    write_market_caps(repo, mod_root)
    rules = Rules(repo, project)
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
        from .development import compute_vanilla_development

        development = compute_vanilla_development(repo, project)
    targets = (
        contract.location_targets.drop("development")
        .join(development, on="location_tag", how="left")
        .with_columns(pl.col("development").fill_null(0))
    )
    contract = replace(contract, location_targets=targets)
    sim = Simulation(
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
    for name, (extra_doc, counts) in extra.items():
        kept = defaultdict(Counter)
        for tag, local in counts.items():
            for key, n in local.items():
                kept[tag][key] = min(n, kept_vanilla[tag][key])
                kept_vanilla[tag][key] -= kept[tag][key]
        write_setup(extra_doc, kept, owners, mod_root / "main_menu/setup/start" / name)
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
    # Merge repeated incremental placements into a single setup row.
    counts = defaultdict(Counter)
    for p in sim.placements:
        counts[p.location][p.building] += p.level
    placements = [
        sp.Placement(tag, owners[tag], key, n)
        for tag, local in sorted(counts.items())
        for key, n in sorted(local.items())
        if n
    ]
    sp.write_start_setup(placements, mod_root)
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
                "import_cap": rules.cap(
                    "victuals_market_import", {**current, "initializing": False}
                ),
                "export_cap": rules.cap(
                    "victuals_market", {**current, "initializing": False}
                ),
                "setup_import_cap": rules.cap("victuals_market_import", current),
                "setup_export_cap": rules.cap("victuals_market", current),
                "import_levels": sim.counts[tag]["victuals_market_import"],
                "export_levels": sim.counts[tag]["victuals_market"],
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
    demand_by_type = Counter()
    converted = sim_converted(sim)
    for tag in sim.locations:
        for kind, n in sim.location_pops(tag, converted[tag]).items():
            demand_by_type[kind] += n * food.get(kind, 0)
    summary = {
        "locations_planned": len(sim.locations),
        "rows": len(placements),
        "levels_by_building": dict(sum(counts.values(), Counter())),
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
            "planned_cookery_levels": sum(c["planned_cookery_levels"] for c in sim.victuals.values()),
            "placed_cookery_levels": sum(c["placed_cookery_levels"] for c in sim.victuals.values()),
            "fallback_cookery_levels": sum(c["fallback_cookery_levels"] for c in sim.victuals.values()),
            "planned_import_levels": sum(c["planned_import_levels"] for c in sim.victuals.values()),
            "import_budget": sum(c["import_budget"] for c in sim.victuals.values()),
            "placed_import_levels": sum(c["placed_import_levels"] for c in sim.victuals.values()),
            "imports_for_deficits": sum(c["imports_for_deficits"] for c in sim.victuals.values()),
            "unmet_food": round(sum(c["unmet_food"] for c in sim.victuals.values()), 1),
            "catchments": sim.victuals,
        },
        "market_import_food": sim.numbers["victuals_market_import"][
            "local_monthly_food"
        ],
        "market_export_food": sim.numbers["victuals_market"]["local_monthly_food"],
        "building_rows_audited": audited,
        "over_cap_rows": 0,
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
        "unallocated_export_levels": sim.unallocated_exports,
        "city_import_minimum": sim.city_import_minimum,
        "unresolved_rules": dict(rules.unsupported),
        "placement_rejections": dict(sim.rejections),
        "pops": pop_report,
        "assumptions": [
            "Full staffing of ordinary placed food buildings; mandatory city imports count food only with workers and export backing.",
            "Nearest starting market centre within the same game region is an offline catchment proxy, not engine market access.",
            "RGO size and market access use zero lower bounds for cap safety; unsupported rules fail closed.",
            "Budget excludes seasonal harvests, prices, trade competition, armies and engine-only country modifiers.",
            "Subsistence includes unemployed peasants, laborers and slaves; engine RGO employment and RGO food are not simulated.",
        ],
    }
    (repo / sp.REPORT_RELATIVE_PATH).write_text(json.dumps(summary, indent=2) + "\n")
    (folder / "report.json").write_text(json.dumps(summary, indent=2) + "\n")
    from .food_report import write as write_report

    write_report(folder, summary, list(budgets.values()), diagnostics)
    return summary
