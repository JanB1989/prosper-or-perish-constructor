"""Crop farm chains: eight crops x four tiers of farm buildings, generated from ``config/crop_farms.toml``.

The single farming-village chain (farming_village -> husbandry_farmstead -> farming_village_rotations -> model_farm,
the crop chosen as a production method) is split into one chain per crop::

    <stem>_farm -> <stem>_farmstead -> <stem>_rotations -> <stem>_model_farm

``ppc crop-farms --write`` renders the 32 accepted blueprints (``blueprints/accepted/buildings/<building>.yml``), the
scripted triggers they gate on (``pp_crop_farm_triggers.txt`` in the mod), enables them in the building manifest,
deletes the retired tier blueprints and turns ``farming_village`` (a vanilla building other vanilla content names) into
a tombstone that can never be built. ``--check`` compares the loaded YAML with what would be written (a semantic
comparison, so a re-dump of the same data is not stale) and ``ppc build`` fails on any difference.

Per blueprint:

- slot 0: the passive base method ``pp_<b>_base`` (labour class ``base``);
- slot 1: ``pp_<b>_no_cultivation`` and the tier's cultivation methods of the crop (labour class of the tier, or
  ``hand_work``); a method that names an advance is unlocked by it (``pp_heavy_plough``, ``pp_improved_rotations``,
  ``pp_water_lifting``, rendered once in ``wheat_farm.yml``);
- slot 2 (legumes and olives, tiers 0-2): ``pp_<b>_no_beekeeping`` and the tier's hive method;
- last slot: Provisioning (``provisioning.py``), Provision listed first, then Sell the Surplus.

Every producing method goes through the production-labour pass (``production_labour.plan_method``) before it is
written, so ``ppc labour check`` finds nothing to change. Gated crops (rice, maize, potato, olives) carry
``country_potential = { OR = { pp_<stem>_native_country = yes has_advance = <general advance> } }`` on all four tiers;
the native trigger lists the sub-continents and regions where the good is an established RGO (``[unlocks]``), and the
general advance is rendered in the crop's tier-0 blueprint. ``country_potential`` is not evaluated by the offline start
placement (``worldbuilder/start_rules.py`` tests ``location_potential`` and ``allow`` only), so a gated crop's
location gate alone decides where it may be placed at game start.
"""

from __future__ import annotations

import difflib
import re
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

import polars as pl
import yaml

from prosper_or_perish_constructor import yaml_io

TABLE_RELATIVE_PATH = Path("config/crop_farms.toml")
BLUEPRINT_ROOT_RELATIVE = Path("blueprints/accepted/buildings")
ICON_ROOT_RELATIVE = Path("blueprints/accepted/assets/icons")
MANIFEST_RELATIVE_PATH = Path("blueprints/buildings.manifest.yml")
TRIGGERS_RELATIVE_PATH = Path("in_game/common/scripted_triggers/pp_crop_farm_triggers.txt")
GOODS_CATEGORIES_RELATIVE = Path("config/goods_categories.csv")
GOODS_CATEGORY_SCALING_RELATIVE = Path("config/goods_category_scaling.toml")
TIERS = (0, 1, 2, 3)
TOMBSTONE = "farming_village"
RETIRED_BLUEPRINTS = ("husbandry_farmstead", "farming_village_rotations", "model_farm")
TOMBSTONE_METHOD = "pp_farming_village_retired"
LABOUR_GOOD = "manual_labor"
CULTIVATION_ADVANCE_HOST = ("wheat", 0)   # the new cultivation advances are rendered once, in wheat_farm.yml
TIER_ADVANCE_HOST_STEM = "wheat"          # each tier advance is rendered once, in the wheat blueprint of its tier


# ---------------------------------------------------------------------------------------------------------- table


@dataclass(frozen=True)
class CropMethod:
    tier: int
    key: str
    name: str
    desc: str
    inputs: dict[str, float]
    output: float
    labour_class: str
    advance: str


@dataclass(frozen=True)
class Crop:
    stem: str
    good: str
    gated: bool
    land_class: str
    names: dict[int, str]
    descs: dict[int, str]
    slot0_name: str
    provision_name: str
    beekeeping: bool
    side_modifiers: dict[str, float]
    location_rule: str
    location_rule_standalone: bool
    base_labour: dict[int, float] | None
    methods: tuple[CropMethod, ...]

    def tier_methods(self, tier: int) -> tuple[CropMethod, ...]:
        return tuple(method for method in self.methods if method.tier == tier)


@dataclass(frozen=True)
class CropTable:
    raw: dict[str, Any]
    crops: tuple[Crop, ...]

    @property
    def general(self) -> dict[str, Any]:
        return self.raw["general"]

    def tier_value(self, name: str, tier: int) -> Any:
        return _tiered(self.general[name], f"general.{name}")[tier]

    def building(self, crop: Crop, tier: int) -> str:
        return f"{crop.stem}_{self.tier_value('tier_suffix', tier)}"

    def tier_advance(self, tier: int) -> str | None:
        return None if tier == 0 else _tiered(self.general["tier_advances"], "general.tier_advances")[tier]

    @property
    def unlocks(self) -> dict[str, Any]:
        return self.raw.get("unlocks", {})

    @property
    def gated_goods(self) -> tuple[str, ...]:
        return tuple(str(good) for good in self.unlocks.get("goods", ()))

    @property
    def threshold(self) -> float:
        return float(self.unlocks.get("subcontinent_region_threshold", 0.60))

    def general_advance(self, crop: Crop) -> str:
        pattern = str(self.unlocks.get("advance_key_pattern", "pp_{good}_farm_advance_{kind}"))
        return pattern.format(good=crop.good, stem=crop.stem, kind="general")

    def crop(self, stem: str) -> Crop:
        return next(crop for crop in self.crops if crop.stem == stem)


def load_crop_table(repo: Path) -> CropTable:
    raw = tomllib.loads((repo / TABLE_RELATIVE_PATH).read_text(encoding="utf-8-sig"))
    crops: list[Crop] = []
    for index, item in enumerate(raw.get("crops", [])):
        name = f"crops[{index}]"
        methods = tuple(
            CropMethod(
                tier=int(method["tier"]),
                key=str(method["key"]),
                name=str(method["name"]),
                desc=str(method.get("desc", "")),
                inputs={str(k): float(v) for k, v in dict(method.get("inputs", {})).items()},
                output=float(method["output"]),
                labour_class=str(method.get("labour_class", "")),
                advance=str(method.get("advance", "")),
            )
            for method in item.get("methods", [])
        )
        base_labour = item.get("base_labour")
        crops.append(
            Crop(
                stem=str(item["stem"]),
                good=str(item["good"]),
                gated=bool(item.get("gated", False)),
                land_class=str(item.get("land_class", "arable")),
                names=_tiered(item["names"], f"{name}.names"),
                descs=_tiered(item["descs"], f"{name}.descs"),
                slot0_name=str(item["slot0_name"]),
                provision_name=str(item["provision_name"]),
                beekeeping=bool(item.get("beekeeping", False)),
                side_modifiers={str(k): float(v) for k, v in dict(item.get("side_modifiers", {})).items()},
                location_rule=str(item["location_rule"]).strip("\n"),
                location_rule_standalone=bool(item.get("location_rule_standalone", False)),
                base_labour=None
                if base_labour is None
                else {k: float(v) for k, v in _tiered(base_labour, f"{name}.base_labour").items()},
                methods=methods,
            )
        )
    table = CropTable(raw=raw, crops=tuple(crops))
    _validate_table(table)
    return table


def crop_buildings(table: CropTable) -> tuple[str, ...]:
    """The 32 building keys in chain order: stem-major, tier 0..3 within a chain (the crop table's crop order)."""
    return tuple(table.building(crop, tier) for crop in table.crops for tier in TIERS)


def crop_building_goods(table: CropTable) -> dict[str, str]:
    """Building -> the crop good it grows (and provisions with)."""
    return {table.building(crop, tier): crop.good for crop in table.crops for tier in TIERS}


def _validate_table(table: CropTable) -> None:
    stems = [crop.stem for crop in table.crops]
    if len(set(stems)) != len(stems):
        raise ValueError(f"{TABLE_RELATIVE_PATH}: duplicate crop stems")
    advances = set(table.raw.get("advances", {}))
    for crop in table.crops:
        for tier in TIERS:
            if not crop.tier_methods(tier):
                raise ValueError(f"{TABLE_RELATIVE_PATH}: crop {crop.stem} has no tier {tier} cultivation method")
        keys = [(method.tier, method.key) for method in crop.methods]
        if len(set(keys)) != len(keys):
            raise ValueError(f"{TABLE_RELATIVE_PATH}: crop {crop.stem} repeats a method key within a tier")
        for method in crop.methods:
            if method.advance and method.advance not in advances:
                raise ValueError(f"{TABLE_RELATIVE_PATH}: {crop.stem}.{method.key} names unknown advance {method.advance}")
        if crop.gated and crop.good not in table.gated_goods:
            raise ValueError(f"{TABLE_RELATIVE_PATH}: gated crop {crop.stem} is missing from [unlocks].goods")
    for good in table.gated_goods:
        if not any(crop.good == good and crop.gated for crop in table.crops):
            raise ValueError(f"{TABLE_RELATIVE_PATH}: [unlocks].goods names {good}, which is not a gated crop")


def _tiered(value: Any, name: str) -> dict[int, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{TABLE_RELATIVE_PATH}: {name} must be a table keyed by tier")
    return {int(key): item for key, item in value.items()}


# ---------------------------------------------------------------------------------------------------------- gates


@dataclass(frozen=True)
class RgoUnlockGate:
    good: str
    subcontinents: tuple[str, ...]
    regions: tuple[str, ...]

    @property
    def empty(self) -> bool:
        return not self.subcontinents and not self.regions


def derive_rgo_unlock_gates(
    locations: pl.DataFrame,
    goods: Sequence[str],
    threshold: float,
) -> tuple[RgoUnlockGate, ...]:
    """Per good, the sub-continents where the good is the RGO in at least ``threshold`` of the regions (that carry
    any RGO), and outside them the single regions where it is an RGO at all."""
    _require_columns(locations, ("raw_material", "region", "macro_region"))
    rgo_regions = _rgo_region_frame(locations)
    totals = {
        str(row["macro_region"]): int(row["total_regions"])
        for row in rgo_regions.select("macro_region", "region")
        .unique()
        .group_by("macro_region")
        .len()
        .rename({"len": "total_regions"})
        .to_dicts()
    }

    gates: list[RgoUnlockGate] = []
    for good in goods:
        good_regions = rgo_regions.filter(pl.col("raw_material") == good).select("macro_region", "region").unique()
        subcontinents: list[str] = []
        regions: list[str] = []
        for macro_region in sorted(str(value) for value in good_regions["macro_region"].unique().to_list()):
            macro_regions = sorted(
                str(value)
                for value in good_regions.filter(pl.col("macro_region") == macro_region)["region"].unique().to_list()
            )
            total = totals.get(macro_region, 0)
            if total > 0 and len(macro_regions) / total >= threshold:
                subcontinents.append(macro_region)
            else:
                regions.extend(macro_regions)
        gates.append(RgoUnlockGate(good=good, subcontinents=tuple(sorted(subcontinents)), regions=tuple(sorted(regions))))
    return tuple(gates)


def current_gates(repo: Path, project: Path, table: CropTable) -> dict[str, RgoUnlockGate]:
    """The gates of the crop table's gated goods from the current (vanilla + mod) location data."""
    from prosper_or_perish_constructor.location_baseline import load_current_location_frame

    locations = load_current_location_frame(repo, project)
    return {gate.good: gate for gate in derive_rgo_unlock_gates(locations, table.gated_goods, table.threshold)}


def _rgo_region_frame(locations: pl.DataFrame) -> pl.DataFrame:
    return (
        locations.with_columns(
            pl.col("raw_material").cast(pl.String).str.strip_chars().alias("raw_material"),
            pl.col("region").cast(pl.String).str.strip_chars().alias("region"),
            pl.col("macro_region").cast(pl.String).str.strip_chars().alias("macro_region"),
        )
        .filter(
            pl.col("raw_material").is_not_null()
            & (pl.col("raw_material") != "")
            & pl.col("region").is_not_null()
            & (pl.col("region") != "")
            & pl.col("macro_region").is_not_null()
            & (pl.col("macro_region") != "")
        )
        .select("raw_material", "macro_region", "region")
        .unique()
    )


def _require_columns(frame: pl.DataFrame, columns: Sequence[str]) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"Location data is missing required columns: {', '.join(missing)}")


def _gate_lines(gate: RgoUnlockGate, *, indent: str) -> list[str]:
    return [
        *[f"{indent}sub_continent = sub_continent:{subcontinent}" for subcontinent in gate.subcontinents],
        *[f"{indent}region = region:{region}" for region in gate.regions],
    ]


def native_trigger(crop: Crop) -> str:
    return f"pp_{crop.stem}_native_country"


def location_trigger(crop: Crop) -> str:
    return f"pp_{crop.stem}_farm_location_potential"


# ---------------------------------------------------------------------------------------------------------- context


@dataclass
class RenderContext:
    prices: dict[str, float]
    labour: Any  # production_labour.LabourConfig
    provisioning: Any  # provisioning.ProvisioningConfig
    category_costs: dict[str, str]  # good -> scaled increase_per_level_cost text
    farm_land: dict[str, dict[str, float]]  # class -> {land, reserve}
    farm_classes: dict[str, tuple[str, ...]]  # class -> member buildings
    gates: dict[str, RgoUnlockGate] = field(default_factory=dict)

    def land_class(self, building: str) -> str:
        """The [worldbuilder.farm_land] class of a farm building, as ``worldbuilder.buildings.farm_constants`` finds it."""
        return next((cls for cls, members in self.farm_classes.items() if building in members), "arable")

    def land(self, building: str) -> float:
        return float(self.farm_land[self.land_class(building)]["land"])


def load_context(repo: Path, project: Path, table: CropTable, *, gates: bool = True) -> RenderContext:
    from prosper_or_perish_constructor import production_labour, provisioning
    from prosper_or_perish_constructor.goods_categories import load_good_category_costs, load_increase_per_level_cost_band

    raw = tomllib.loads(project.read_text(encoding="utf-8-sig"))
    farm_land_section = dict(raw.get("worldbuilder", {}).get("farm_land", {}))
    classes = {str(k): tuple(str(b) for b in v) for k, v in dict(farm_land_section.pop("classes", {})).items()}
    band = load_increase_per_level_cost_band(repo / GOODS_CATEGORY_SCALING_RELATIVE)
    costs = load_good_category_costs(repo / GOODS_CATEGORIES_RELATIVE, band)
    context = RenderContext(
        prices=production_labour.load_prices(repo, project),
        labour=production_labour.load_config(project),
        provisioning=provisioning.load_provisioning_config(project),
        category_costs={good: cost.scaled_cost_text for good, cost in costs.items()},
        farm_land={str(k): {"land": float(v["land"]), "reserve": float(v["reserve"])} for k, v in farm_land_section.items()},
        farm_classes=classes,
    )
    for crop in table.crops:
        for tier in TIERS:
            building = table.building(crop, tier)
            if context.land_class(building) != crop.land_class:
                raise ValueError(
                    f"{building}: crop table land_class {crop.land_class!r}, but [worldbuilder.farm_land.classes] puts it in "
                    f"{context.land_class(building)!r}"
                )
    if gates:
        context.gates = current_gates(repo, project, table)
    return context


# ---------------------------------------------------------------------------------------------------------- methods


@dataclass
class RenderedMethod:
    name: str
    inputs: dict[str, float]  # goods (table order) then labour; zero-amount goods kept
    produced: str | None
    output: float | None
    labour_class: str | None  # None: a selector without output (no labour pass)
    kind: str  # base | none | cultivation | beekeeping
    worked: bool = True  # carries debug_max_profit = 0

    def lines(self) -> list[str]:
        lines = [f"{self.name} = {{"]
        lines.extend(f"    {good} = {_num(amount)}" for good, amount in self.inputs.items())
        if self.produced is not None:
            lines.append(f"    produced = {self.produced}")
            lines.append(f"    output = {_num(self.output or 0.0)}")
            if self.worked:
                lines.append("    debug_max_profit = 0")
        lines.append("    category = building_maintenance")
        lines.append("}")
        return lines


def _labour_pass(method: RenderedMethod, building: str, context: RenderContext) -> RenderedMethod:
    """Apply the production-labour pass until it has nothing left to change (the fixed point ``ppc labour`` keeps)."""
    from prosper_or_perish_constructor import production_labour

    if method.labour_class is None or method.produced is None:
        return method
    labour_class = context.labour.classes.get(method.labour_class)
    if labour_class is None:
        raise ValueError(f"{method.name}: labour class {method.labour_class!r} is not in [production_labour.classes]")
    good = context.labour.good
    current = dict(method.inputs)
    for _ in range(8):
        plan = production_labour.plan_method(
            production_labour.Method(
                blueprint=Path(f"{building}.yml"),
                building=building,
                name=method.name,
                inputs=current,
                produced=method.produced,
                output=method.output,
            ),
            labour_class,
            context.labour,
            context.prices,
        )
        if plan.problem:
            raise ValueError(f"{building}: {method.name}: {plan.problem}")
        if not plan.changed:
            method.inputs = current
            return method
        updated: dict[str, float] = {}
        for item, amount in current.items():
            if item == good:
                continue
            if amount == 0:
                updated[item] = amount  # zero-amount goods lines stay
            elif item in plan.amounts:
                updated[item] = plan.amounts[item]
        if plan.amounts.get(good):
            updated[good] = plan.amounts[good]
        current = updated
    raise ValueError(f"{building}: {method.name}: the labour pass does not settle")


def _base_method(table: CropTable, crop: Crop, tier: int, building: str) -> RenderedMethod:
    labour = crop.base_labour[tier] if crop.base_labour else float(table.tier_value("tier_base_labour", tier))
    return RenderedMethod(
        name=f"pp_{building}_base",
        inputs={LABOUR_GOOD: labour},
        produced=crop.good,
        output=float(table.tier_value("tier_base_output", tier)),
        labour_class=str(table.general.get("base_labour_class", "base")),
        kind="base",
        worked=False,
    )


def _selector(name: str) -> RenderedMethod:
    return RenderedMethod(name=name, inputs={}, produced=None, output=None, labour_class=None, kind="none", worked=False)


def _cultivation_method(table: CropTable, crop: Crop, method: CropMethod, building: str) -> RenderedMethod:
    return RenderedMethod(
        name=f"pp_{building}_{method.key}",
        inputs=dict(method.inputs),
        produced=crop.good,
        output=method.output,
        labour_class=method.labour_class or str(table.tier_value("tier_labour_class", method.tier)),
        kind="cultivation",
    )


def _hive_method(table: CropTable, tier: int, building: str) -> RenderedMethod:
    hive = table.raw["beekeeping"][str(tier)]
    inputs = {str(k): float(v) for k, v in dict(hive.get("inputs", {})).items()}
    if float(hive.get("manual_labor", 0) or 0):
        inputs[LABOUR_GOOD] = float(hive["manual_labor"])
    return RenderedMethod(
        name=f"pp_{building}_{hive['key']}",
        inputs=inputs,
        produced="beeswax",
        output=float(hive["output"]),
        labour_class=str(hive.get("labour_class") or table.tier_value("tier_labour_class", tier)),
        kind="beekeeping",
    )


def has_beekeeping(table: CropTable, crop: Crop, tier: int) -> bool:
    return crop.beekeeping and str(tier) in table.raw.get("beekeeping", {})


# ---------------------------------------------------------------------------------------------------------- render


def render_blueprint(table: CropTable, crop: Crop, tier: int, context: RenderContext) -> dict[str, Any]:
    """The accepted blueprint of one crop farm tier, as a mapping in file order."""
    from prosper_or_perish_constructor import provisioning

    general = table.general
    building = table.building(crop, tier)
    previous = table.building(crop, tier - 1) if tier > 0 else None
    following = table.building(crop, tier + 1) if tier + 1 in TIERS else None
    loc = table.raw.get("loc", {})

    # ---- slots (the provisioning slot is rendered by provisioning.py and comes last)
    slots: list[tuple[str, list[RenderedMethod]]] = []
    slots.append(("base", [_labour_pass(_base_method(table, crop, tier, building), building, context)]))
    cultivation = [_selector(f"pp_{building}_no_cultivation")]
    cultivation += [
        _labour_pass(_cultivation_method(table, crop, method, building), building, context) for method in crop.tier_methods(tier)
    ]
    slots.append(("cultivation", cultivation))
    if has_beekeeping(table, crop, tier):
        hives = _labour_pass(_hive_method(table, tier, building), building, context)
        slots.append(("beekeeping", [_selector(f"pp_{building}_no_beekeeping"), hives]))
    base_output = Decimal(str(table.tier_value("tier_base_output", tier)))
    price = Decimal(str(context.prices.get(crop.good, 1.0)))
    amounts = provisioning.provisioning_amounts(base_output, good_price=price, config=context.provisioning)

    # ---- body
    shared = dict(general.get("body", {}))
    body: list[str] = []
    if tier == 0:
        body.extend(f"{key} = {_value(value)}" for key, value in dict(general.get("body_tier0", {})).items())
    body.append(f"is_foreign = {_value(shared.get('is_foreign', 'no'))}")
    body.append(f"increase_per_level_cost = {_increase_cost(crop, slots, context)}")
    body.append(f"max_levels = {str(general.get('max_levels_pattern', 'farm_capacity_max_{building}')).format(building=building)}")
    body.append(f"pop_type = {table.tier_value('tier_pop_type', tier)}")
    body.append(f"employment_size = {_value(shared.get('employment_size', 1))}")
    body.append(f"category = {_value(shared.get('category', 'village_category'))}")
    body.append("custom_tags = { " + " ".join(str(tag) for tag in shared.get("custom_tags", ())) + " }")
    body.append(f"icon = {building}")
    for rank in ("rural_settlement", "town", "city", "megalopolis"):
        if rank in shared:
            body.append(f"{rank} = {_value(shared[rank])}")
    if previous is not None and bool(table.tier_value("tier_obsoletes_previous", tier)):
        body.append(f"obsolete = {previous}")
    body.append(f"forbidden_for_estates = {_value(shared.get('forbidden_for_estates', 'yes'))}")
    body.append(f"ai_forbid_shutdown = {_value(shared.get('ai_forbid_shutdown', 'no'))}")
    if bool(table.tier_value("tier_can_close", tier)):
        body.append("can_close = yes")  # tier 0 keeps the engine default, as farming_village did
    body.append(f"build_time = {table.tier_value('tier_build_time', tier)}")
    body.append(f"construction_demand = {table.tier_value('tier_construction_demand', tier)}")
    body.append("")
    body.extend(["location_potential = {", f"    {location_trigger(crop)} = yes", "}"])
    if crop.gated:
        body.extend(
            [
                "country_potential = {",
                "    OR = {",
                f"        {native_trigger(crop)} = yes",
                f"        has_advance = {table.general_advance(crop)}",
                "    }",
                "}",
            ]
        )
    body.append("")
    for _, methods in slots:
        body.append("unique_production_methods = {")
        for method in methods:
            body.extend(f"    {line}" for line in method.lines())
        body.append("}")
    body.append(provisioning.render_slot(building, crop.good, amounts))
    body.append("")
    body.extend(
        [
            "raw_modifier = {",
            f"  {str(general.get('farm_capacity_line_pattern', 'farm_capacity_from_{building} = -1')).format(building=building)}",
            f"  local_population_capacity = {_land_text(-context.land(building))}",
            "}",
            "",
            "modifier = {",
        ]
    )
    modifier = dict(general.get("tier_modifier", {}).get(str(tier), {}))
    modifier.update(crop.side_modifiers)
    body.extend(f"    {key} = {_num(value)}" for key, value in modifier.items())
    body.append("}")

    # ---- slot metadata
    provision, sell = provisioning.slot_methods(building)
    slot_methods = [[method.name for method in methods] for _, methods in slots]
    slot_methods.append([provision, sell])
    production_method_slots = [{"name": f"slot_{index}", "methods": methods} for index, methods in enumerate(slot_methods)]

    # ---- labour tag: the tier class by default, per-method overrides (base, hand_work, household hives)
    tier_class = str(table.tier_value("tier_labour_class", tier))
    labour_methods: dict[str, str] = {}
    for _, methods in slots:
        for method in methods:
            if method.labour_class is not None and method.labour_class != tier_class:
                labour_methods[method.name] = method.labour_class
    labour_methods[provision] = "keep"
    labour_methods[sell] = "keep"

    # ---- localization
    entries: dict[str, str] = {building: crop.names[tier], f"{building}_desc": crop.descs[tier]}
    slot_labels = {
        "base": crop.slot0_name,
        "cultivation": str(loc.get("slot_cultivation", "Cultivation")),
        "beekeeping": str(loc.get("slot_beekeeping", "Beekeeping")),
    }
    for index, (kind, _) in enumerate(slots):
        entries[f"{building}_slot_{index}"] = slot_labels[kind]
    entries[f"{building}_slot_{len(slots)}"] = str(loc.get("slot_provisioning", provisioning.SLOT_LABEL))
    entries[f"pp_{building}_base"] = crop.slot0_name
    entries[f"pp_{building}_no_cultivation"] = str(loc.get("no_cultivation", "No Cultivation"))
    for method in crop.tier_methods(tier):
        entries[f"pp_{building}_{method.key}"] = method.name
        if method.desc:
            entries[f"pp_{building}_{method.key}_desc"] = method.desc
    if has_beekeeping(table, crop, tier):
        hive = table.raw["beekeeping"][str(tier)]
        entries[f"pp_{building}_no_beekeeping"] = str(loc.get("no_beekeeping", "No Beekeeping"))
        entries[f"pp_{building}_{hive['key']}"] = str(hive["name"])
        if hive.get("desc"):
            entries[f"pp_{building}_{hive['key']}_desc"] = str(hive["desc"])
    entries[provision] = crop.provision_name
    entries[f"{provision}_desc"] = str(loc.get("provision_desc", ""))
    entries[sell] = str(loc.get("sell_surplus", provisioning.SELL_LABEL))
    entries[f"{sell}_desc"] = str(loc.get("sell_surplus_desc", provisioning.SELL_DESC))

    # ---- advancements
    advancements: list[dict[str, str]] = []
    if crop.stem == TIER_ADVANCE_HOST_STEM and tier > 0:
        key = str(table.tier_advance(tier))
        spec = table.raw["tier_advance"][key]
        advancements.append({"key": key, "body": _tier_advance_body(table, key, tier)})
        entries[key] = str(spec["name"])
        entries[f"{key}_desc"] = str(spec["desc"])
    if crop.gated and tier == 0:
        key = table.general_advance(crop)
        spec = table.unlocks["general"][crop.good]
        advancements.append({"key": key, "body": _general_advance_body(table, crop, context.gates.get(crop.good))})
        entries[key] = str(spec["name"])
        entries[f"{key}_desc"] = str(spec["desc"])
    if (crop.stem, tier) == CULTIVATION_ADVANCE_HOST:
        for key, spec in table.raw.get("advances", {}).items():
            advancements.append({"key": key, "body": _cultivation_advance_body(table, key, spec)})
            entries[key] = str(spec["name"])
            entries[f"{key}_desc"] = str(spec["desc"])

    # ---- evaluation
    evaluation = dict(table.raw.get("evaluation", {}).get(str(tier), {}))
    efficiency = dict(evaluation.get("production_efficiency", {}))
    per_method: dict[str, dict[str, Any]] = {}
    for _, methods in slots:
        for method in methods:
            entry: dict[str, Any] = {"production_efficiency": float(efficiency.get(method.kind, 1.0))}
            rules: dict[str, str] = {}
            if method.kind == "base":
                rules = dict(evaluation.get("herd_base_allow_rules" if crop.land_class == "herd" else "base_allow_rules", {}))
            elif method.kind == "beekeeping":
                rules = dict(evaluation.get("beekeeping_allow_rules", {}))
            if rules:
                entry["allow_rules"] = rules
            per_method[method.name] = entry
    per_method.update(provisioning.evaluation_rules(building))

    blueprint: dict[str, Any] = {
        "version": 2,
        "tag": building,
        "output_tag": f"{crop.stem}_farm_tier{tier}",
        "footprint": str(general.get("footprint", "farm_land")),
        "labour": {"class": tier_class, "methods": labour_methods},
        "upgrade_chain": {
            "family": f"{crop.stem}_farm",
            "tier": tier,
            "previous": previous,
            "next": following,
            "unlock_advance": table.tier_advance(tier),
        },
        "building": {
            "key": building,
            "mode": "CREATE",
            "source": "pp_new_buildings.txt",
            "production_method_slots": production_method_slots,
            "possible_production_methods": [],
            "body": "\n".join(body),
        },
    }
    if advancements:
        blueprint["advancements"] = advancements
    blueprint["localization"] = {"entries": entries}
    blueprint["icon"] = {"source_png": f"../assets/icons/{building}.png", "output_dds": f"{building}.dds", "size": 512}
    blueprint["evaluation"] = {"allow_rules": dict(evaluation.get("allow_rules", {})), "production_methods": per_method}
    return blueprint


def _increase_cost(crop: Crop, slots: Sequence[tuple[str, Sequence[RenderedMethod]]], context: RenderContext) -> str:
    """The goods-category cost of the building's main good: the producing method with the highest output value, as
    ``goods_categories.building_increase_cost_assignments`` picks it (so the cost test holds by construction)."""
    candidates = []
    for _, methods in slots:
        for method in methods:
            if method.produced is None or method.produced not in context.category_costs or not method.output:
                continue
            value = float(method.output) * float(context.prices.get(method.produced, 0.0))
            candidates.append((value, float(method.output), method.produced, method.name))
    good = max(candidates)[2] if candidates else crop.good
    return context.category_costs[good]


def _tier_advance_body(table: CropTable, key: str, tier: int) -> str:
    spec = table.raw["tier_advance"][key]
    lines = []
    if spec.get("icon"):
        lines.append(f"icon = {spec['icon']}")
    lines.append(f"age = {spec['age']}")
    lines.append(f"requires = {spec['requires']}")
    lines.extend(f"unlock_building = {table.building(crop, tier)}" for crop in table.crops)
    lines.append(f"ai_weight = {{ add = {int(spec.get('ai_weight', 125))} }}")
    return "\n".join(lines)


def _general_advance_body(table: CropTable, crop: Crop, gate: RgoUnlockGate | None) -> str:
    spec = table.unlocks["general"][crop.good]
    lines = [
        f"age = {spec['age']}",
        f"requires = {spec['requires']}",
        f"ai_weight = {{ add = {int(table.unlocks.get('ai_weight', 50))} }}",
        "potential = {",
        "    exists = capital",
    ]
    if gate is not None and not gate.empty:
        lines.extend(
            [
                "    NOT = {",
                "        original_capital ?= {",
                "            OR = {",
                *_gate_lines(gate, indent="                "),
                "            }",
                "        }",
                "    }",
            ]
        )
    lines.append("}")
    return "\n".join(lines)


def cultivation_advance_methods(table: CropTable) -> dict[str, list[str]]:
    """Advance -> every cultivation method (across all chains) that names it, in chain order."""
    methods: dict[str, list[str]] = {key: [] for key in table.raw.get("advances", {})}
    for crop in table.crops:
        for tier in TIERS:
            building = table.building(crop, tier)
            for method in crop.tier_methods(tier):
                if method.advance:
                    methods[method.advance].append(f"pp_{building}_{method.key}")
    return methods


def _cultivation_advance_body(table: CropTable, key: str, spec: Mapping[str, Any]) -> str:
    lines = [f"age = {spec['age']}", f"requires = {spec['requires']}"]
    lines.extend(f"unlock_production_method = {method}" for method in cultivation_advance_methods(table)[key])
    lines.append(f"ai_weight = {{ add = {int(spec.get('ai_weight', table.unlocks.get('ai_weight', 50)))} }}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------------------------------------- tombstone


def render_tombstone() -> dict[str, Any]:
    """``farming_village`` stays defined (vanilla content names it) but can never be built or placed."""
    body = "\n".join(
        [
            "audio_tier = 1",
            "startup_ramp_target = rural_startup_ramp_target",
            "is_foreign = no",
            "max_levels = 0",
            "pop_type = peasants",
            "employment_size = 1",
            "category = village_category",
            "build_time = village_build_time",
            "construction_demand = village_construction",
            "",
            "location_potential = {",
            "    always = no",
            "}",
            "",
            "unique_production_methods = {",
            f"    {TOMBSTONE_METHOD} = {{",
            "        category = building_maintenance",
            "    }",
            "}",
        ]
    )
    return {
        "version": 2,
        "tag": TOMBSTONE,
        "footprint": "technical",
        "building": {
            "key": TOMBSTONE,
            "mode": "REPLACE",
            "source": "pp_food_buildings.txt",
            "production_method_slots": [{"name": "slot_0", "methods": [TOMBSTONE_METHOD]}],
            "possible_production_methods": [],
            "body": body,
        },
        "localization": {
            "entries": {
                TOMBSTONE: "Farming Village (retired)",
                f"{TOMBSTONE}_desc": "Farming villages have given way to farms that each grow one crop.",
                f"{TOMBSTONE}_slot_0": "Retired",
                TOMBSTONE_METHOD: "Retired",
            }
        },
    }


# ---------------------------------------------------------------------------------------------------------- triggers


def render_triggers(table: CropTable, gates: Mapping[str, RgoUnlockGate]) -> str:
    base = str(table.general.get("location_potential_base", "pp_general_farmable_food_location_potential"))
    lines = [
        "# Prosper or Perish - crop farm location and country gates.",
        "# Generated by `ppc crop-farms --write` from config/crop_farms.toml; do not edit by hand.",
        "",
    ]
    for crop in table.crops:
        lines.append(f"{location_trigger(crop)} = {{")
        lines.append("\tis_ownable = yes")
        if not crop.location_rule_standalone:
            lines.append(f"\t{base} = yes")
        lines.extend(f"\t{line}" if line.strip() else "" for line in crop.location_rule.splitlines())
        lines.append("}")
        lines.append("")
    for crop in table.crops:
        if not crop.gated:
            continue
        gate = gates.get(crop.good)
        lines.append(f"{native_trigger(crop)} = {{")
        if gate is None or gate.empty:
            lines.append("\talways = no")
        else:
            lines.append("\toriginal_capital ?= {")
            lines.append("\t\tOR = {")
            lines.extend(_gate_lines(gate, indent="\t\t\t"))
            lines.append("\t\t}")
            lines.append("\t}")
        lines.append("}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


# ---------------------------------------------------------------------------------------------------------- write / check


def expected_outputs(repo: Path, project: Path) -> tuple[CropTable, dict[str, dict[str, Any]], str]:
    table = load_crop_table(repo)
    context = load_context(repo, project, table)
    blueprints = {
        table.building(crop, tier): render_blueprint(table, crop, tier, context) for crop in table.crops for tier in TIERS
    }
    blueprints[TOMBSTONE] = render_tombstone()
    return table, blueprints, render_triggers(table, context.gates)


def write(repo: Path, project: Path) -> list[str]:
    """Write the 32 blueprints, the tombstone, the triggers and the manifest; delete the retired blueprints.
    Returns what changed (paths relative to the repo)."""
    table, blueprints, triggers = expected_outputs(repo, project)
    missing = [
        str(ICON_ROOT_RELATIVE / f"{building}.png")
        for building in crop_buildings(table)
        if not (repo / ICON_ROOT_RELATIVE / f"{building}.png").is_file()
    ]
    if missing:
        raise FileNotFoundError("crop farm icons missing (run tools/build_crop_farm_icons.py): " + ", ".join(missing))
    changed: list[str] = []
    for building, data in blueprints.items():
        path = repo / BLUEPRINT_ROOT_RELATIVE / f"{building}.yml"
        text = dump_blueprint(data)
        if not path.is_file() or path.read_bytes() != text.encode("utf-8"):
            path.write_text(text, encoding="utf-8", newline="\n")
            changed.append(str(path.relative_to(repo)))
    for building in RETIRED_BLUEPRINTS:
        path = repo / BLUEPRINT_ROOT_RELATIVE / f"{building}.yml"
        if path.exists():
            path.unlink()
            changed.append(f"{path.relative_to(repo)} (deleted)")
    manifest = repo / MANIFEST_RELATIVE_PATH
    manifest_text = manifest.read_text(encoding="utf-8")
    new_manifest = _updated_manifest(manifest_text, crop_buildings(table))
    if new_manifest != manifest_text:
        manifest.write_text(new_manifest, encoding="utf-8", newline="\n")
        changed.append(str(MANIFEST_RELATIVE_PATH))
    trigger_path = _mod_root(repo, project) / TRIGGERS_RELATIVE_PATH
    trigger_bytes = ("﻿" + triggers).encode("utf-8")
    if not trigger_path.is_file() or trigger_path.read_bytes() != trigger_bytes:
        trigger_path.parent.mkdir(parents=True, exist_ok=True)
        trigger_path.write_bytes(trigger_bytes)
        changed.append(str(trigger_path.relative_to(repo)))
    return changed


def check(repo: Path, project: Path) -> list[str]:
    """Differences between the repo and what ``write`` would produce (empty = current)."""
    table, blueprints, triggers = expected_outputs(repo, project)
    problems: list[str] = []
    for building, data in blueprints.items():
        path = repo / BLUEPRINT_ROOT_RELATIVE / f"{building}.yml"
        if not path.is_file():
            problems.append(f"{path.relative_to(repo)}: missing")
            continue
        current = yaml_io.safe_load(path.read_text(encoding="utf-8-sig"))
        expected = yaml_io.safe_load(dump_blueprint(data))
        if current != expected:
            problems.append(f"{path.relative_to(repo)}: stale\n" + _mapping_diff(current, expected))
    for building in RETIRED_BLUEPRINTS:
        path = repo / BLUEPRINT_ROOT_RELATIVE / f"{building}.yml"
        if path.exists():
            problems.append(f"{path.relative_to(repo)}: retired blueprint still present")
    manifest_text = (repo / MANIFEST_RELATIVE_PATH).read_text(encoding="utf-8")
    if _updated_manifest(manifest_text, crop_buildings(table)) != manifest_text:
        problems.append(f"{MANIFEST_RELATIVE_PATH}: crop farm entries missing or retired entries present")
    trigger_path = _mod_root(repo, project) / TRIGGERS_RELATIVE_PATH
    current_triggers = trigger_path.read_text(encoding="utf-8-sig") if trigger_path.is_file() else ""
    if current_triggers.replace("\r\n", "\n") != triggers:
        diff = difflib.unified_diff(current_triggers.splitlines(True), triggers.splitlines(True), "current", "expected")
        problems.append(f"{trigger_path.relative_to(repo)}: stale\n" + "".join(list(diff)[:60]))
    return problems


def dump_blueprint(data: Mapping[str, Any]) -> str:
    return yaml.dump(dict(data), Dumper=_Dumper, sort_keys=False, allow_unicode=True, width=10_000)


class _Dumper(yaml.SafeDumper):
    def ignore_aliases(self, data: Any) -> bool:  # noqa: ARG002 - never write anchors
        return True


def _str_presenter(dumper: yaml.SafeDumper, data: str):
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


_Dumper.add_representer(str, _str_presenter)


_MANIFEST_ENTRY_RE = re.compile(r"^  (?P<entry>buildings/[^:]+\.yml):\s*(?P<value>\S+)\s*$")


def _updated_manifest(text: str, buildings: Sequence[str]) -> str:
    """The manifest with the retired tiers removed and every crop farm enabled (inserted after farming_village)."""
    retired = {f"buildings/{key}.yml" for key in RETIRED_BLUEPRINTS}
    wanted = [f"buildings/{key}.yml" for key in buildings]
    present: dict[str, str] = {}
    kept: list[str] = []
    for line in text.splitlines(keepends=True):
        match = _MANIFEST_ENTRY_RE.match(line.rstrip("\r\n"))
        if match and match.group("entry") in retired:
            continue
        if match:
            present[match.group("entry")] = match.group("value")
        kept.append(line)
    if all(present.get(entry) == "true" for entry in wanted):
        return "".join(kept)
    kept = [
        line
        for line in kept
        if not ((match := _MANIFEST_ENTRY_RE.match(line.rstrip("\r\n"))) and match.group("entry") in wanted)
    ]
    insert = [f"  {entry}: true\n" for entry in wanted]
    anchor = next((i for i, line in enumerate(kept) if line.startswith(f"  buildings/{TOMBSTONE}.yml:")), None)
    if anchor is None:
        anchor = max((i for i, line in enumerate(kept) if _MANIFEST_ENTRY_RE.match(line.rstrip("\r\n"))), default=len(kept) - 1)
    return "".join(kept[: anchor + 1] + insert + kept[anchor + 1 :])


def _mapping_diff(current: Any, expected: Any) -> str:
    lines: list[str] = []

    def walk(a: Any, b: Any, where: str) -> None:
        if len(lines) > 60:
            return
        if isinstance(a, Mapping) and isinstance(b, Mapping):
            for key in dict.fromkeys([*a.keys(), *b.keys()]):
                if key not in a:
                    lines.append(f"  {where}.{key}: missing")
                elif key not in b:
                    lines.append(f"  {where}.{key}: unexpected")
                else:
                    walk(a[key], b[key], f"{where}.{key}")
        elif isinstance(a, str) and isinstance(b, str) and "\n" in a + b and a != b:
            diff = difflib.unified_diff(a.splitlines(), b.splitlines(), "current", "expected", lineterm="", n=1)
            lines.append(f"  {where}:")
            lines.extend(f"    {line}" for line in list(diff)[:40])
        elif a != b:
            lines.append(f"  {where}: {a!r} -> {b!r}")

    walk(current, expected, "")
    return "\n".join(lines)


def _mod_root(repo: Path, project: Path) -> Path:
    raw = tomllib.loads(project.read_text(encoding="utf-8-sig"))
    return repo / str(raw.get("project", {}).get("mod_root", "mod"))


# ---------------------------------------------------------------------------------------------------------- formatting


def _num(value: float | int | str) -> str:
    text = format(Decimal(str(value)).normalize(), "f")
    return "0" if text in {"-0", "0"} else text


def _land_text(value: float) -> str:
    """As ``worldbuilder.buildings._fmt`` writes the land line, so the farm-land patch finds nothing to change."""
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return text if text not in ("", "-0") else "0"


def _value(value: Any) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (int, float)):
        return _num(value)
    return str(value)
