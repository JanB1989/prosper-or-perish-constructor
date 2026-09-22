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


def summed(block):
    result = defaultdict(float)
    if isinstance(block, CList):
        for e in block.entries:
            if isinstance(e.value, (int, float)):
                result[e.key] += float(e.value)
    return result


class Simulation:
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
        for tag, loc in self.locations.items():
            a = self.attrs.get(tag, {})
            target = self.targets.get(tag, {})
            rank = ranks.get(tag, "rural_settlement")
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

    def clamp(self):
        # Caps can share pools or shrink with urbanisation: iterate to a stable
        # state, always removing levels and never silently raising the cap.
        for _ in range(20):
            changed = False
            for tag in sorted(self.locations):
                for key, n in sorted(self.counts[tag].items()):
                    if not n:
                        continue
                    cap = self.rules.cap(key, self.ctx(tag), gates=False)
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
            pool = sp._Workers(local, self.start)
            self.pools[tag] = pool
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
            ctx = self.ctx(tag)
            if self.counts[tag][key] >= self.rules.cap(key, ctx):
                self.rejections[key + ": cap or gate"] += 1
                break
            if pool.levels(1, num["employment_size"], num["pop_type"]) < 1:
                self.rejections[key + ": workers"] += 1
                break
            self.counts[tag][key] += 1
            ctx = self.ctx(tag)
            # Forest pressure and all other shared caps must remain valid after
            # every placement, including the building's own level.
            if any(
                n > self.rules.cap(k, ctx, gates=False)
                for k, n in self.counts[tag].items()
                if n
            ):
                self.counts[tag][key] -= 1
                self.rejections[key + ": shared cap or land"] += 1
                break
            raw = self.raw.get(key, {})
            if (
                raw.get("local_population_capacity", 0) < 0
                and self.start.keep_pops_within_capacity
                and ctx["modifiers"]["local_population_capacity"] < ctx["population"]
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

    def budgets(self, subsistence=None, groups=None):
        value = self.rules.subsistence if subsistence is None else subsistence
        converted = defaultdict(Counter)
        for c in self.conversions:
            converted[c.location][c.from_type] -= c.size_k
            converted[c.location][c.to_type] += c.size_k
        result = {}
        for group, tags in (
            (g, self.groups[g]) for g in (groups if groups is not None else self.groups)
        ):
            demand = unemployed = supply = 0.0
            for tag in tags:
                types = Counter()
                for p in self.pops.get(tag, []):
                    types[p.type] += p.size_k
                types.update(converted[tag])
                demand += sum(n * self.food.get(kind, 0) for kind, n in types.items())
                subsistence_types = self.cfg.raw.get("start", {}).get(
                    "subsistence_pop_types", ["peasants", "laborers", "slaves"]
                )
                for kind in subsistence_types:
                    employed = sum(
                        n * self.numbers[k]["employment_size"]
                        for k, n in self.staffed[tag].items()
                        if self.numbers[k]["pop_type"] == kind
                    )
                    unemployed += max(0, types[kind] - employed)
                supply += sum(
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
                -self.rules.cap(key, self.ctx(t)),
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
            # A small starting rural economy, plus food production wherever the
            # actual gates permit it (not only on matching resource deposits).
            farm = sp.farm_for(loc)
            if farm:
                self.add(tag, farm, self.start.max_farm_levels_per_location)
            for key in ("fishing_village", "forest_village"):
                self.add(tag, key, max(0, 2 - self.counts[tag][key]))
        before = self.budgets()
        export = -self.numbers["victuals_market"]["local_monthly_food"]
        imports = self.numbers["victuals_market_import"]["local_monthly_food"]
        if not math.isclose(export, imports) or imports <= 0:
            raise ValueError("Start trade requires equal positive food transfer units")
        units = defaultdict(int)
        requested = defaultdict(int)
        for group, b in before.items():
            requested[self.catchments[group]] += max(
                0,
                math.ceil(
                    (b["demand"] * self.start.food_target_ratio - b["supply"]) / imports
                ),
            )
        # Export only food beyond the local reserve target.
        for group, tags in sorted(
            self.groups.items(), key=lambda kv: -before[kv[0]]["balance"]
        ):
            b = before[group]
            market = self.catchments[group]
            spare = min(
                max(
                    0,
                    math.floor(
                        (b["supply"] - b["demand"] * self.start.food_target_ratio)
                        / export
                    ),
                ),
                max(0, requested[market] - units[market]),
            )
            for tag in self.order(tags, "victuals_market"):
                if not spare:
                    break
                n = self.add(tag, "victuals_market", spare)
                spare -= n
                units[self.catchments[group]] += n
        # Matched imports use only funded exports in the same catchment. Rural
        # donors retain their reserve; cities get priority among deficits.
        for group, tags in sorted(
            self.groups.items(),
            key=lambda kv: (before[kv[0]]["coverage"], -before[kv[0]]["demand"]),
        ):
            b = before[group]
            needed = max(
                0,
                math.ceil(
                    (b["demand"] * self.start.food_target_ratio - b["supply"]) / imports
                ),
            )
            if not needed:
                continue
            market = self.catchments[group]
            for tag in self.order(tags, "victuals_market_import"):
                if not needed or not units[market]:
                    break
                # Never place opposite food transfers in the same province.
                if any(self.counts[t]["victuals_market"] for t in tags):
                    break
                n = self.add(tag, "victuals_market_import", min(needed, units[market]))
                needed -= n
                units[market] -= n
        # Local preparation fills remaining deficits after supported imports. Groups never pool food
        # across a political border merely because they share a province name.
        for group, tags in sorted(self.groups.items()):
            budget = self.budgets(groups=[group])[group]
            need = budget["demand"] * self.start.food_target_ratio - budget["supply"]
            if need <= 0:
                continue
            for tag in self.order(tags, "cookery"):
                num = self.numbers["cookery"]
                # Include lost subsistence and changed worker consumption.
                net = num["local_monthly_food"] - num["employment_size"] * (
                    self.rules.subsistence
                    + max(
                        0,
                        self.food.get(num["pop_type"], 0)
                        - self.food.get("peasants", 0),
                    )
                )
                if net <= 0:
                    break
                n = self.add(
                    tag,
                    "cookery",
                    min(
                        self.start.max_cookery_levels_per_location,
                        math.ceil(need / net),
                    ),
                )
                need -= n * net
                if need <= 0:
                    break
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
            if self.rules.cap(key, self.ctx(tag)) < 1:
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


def run(*, repo, project, mod_root, vanilla_root, cfg, contract, caps, locations):
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
            }
        )
    pl.DataFrame(diagnostics).write_csv(repo / sp.TABLE_RELATIVE_PATH)
    summary = {
        "locations_planned": len(sim.locations),
        "rows": len(placements),
        "levels_by_building": dict(sum(counts.values(), Counter())),
        "subsistence_define": rules.subsistence,
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
