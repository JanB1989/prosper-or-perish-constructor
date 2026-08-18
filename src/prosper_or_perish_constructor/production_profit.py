from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
import math
from pathlib import Path
import re
from statistics import median
from typing import Any, Iterable, Mapping, Sequence

import yaml

from eu5_building_pipeline.template import load_template
from eu5_mod_orchestrator.blueprints import enabled_manifest_entries
from eu5gameparser.clausewitz.serializer import render_list
from eu5gameparser.clausewitz.syntax import CEntry, CList, SourceLocation, Value
from eu5gameparser.domain.availability import AGE_INDEX, AGE_ORDER, annotate_building_data_availability
from eu5gameparser.domain.eu5 import load_eu5_data
from eu5gameparser.load_order import LoadOrderConfig, load_merged_directory, load_profile
from eu5gameparser.savegame.notebook_labels import NotebookLabelResolver

from prosper_or_perish_constructor.rural_capacity import LAND_FARM_BUILDINGS


BUILDING_BLUEPRINT_MANIFEST_RELATIVE = Path("blueprints/buildings.manifest.yml")
BUILDING_BLUEPRINT_ROOT_RELATIVE = Path("blueprints/accepted")
BUILDING_BLUEPRINT_BUILDINGS_RELATIVE = BUILDING_BLUEPRINT_ROOT_RELATIVE / "buildings"
POSITIVE_OUTPUT_EPSILON = 0.0
EMPLOYMENT_STEP = Decimal("0.05")
BALANCE_UPPER_RATIO = 1.5
BALANCE_WRITE_TARGET_RATIO = 1.2
BASE_WORKER_FOOD_SCENARIO = "base_100"
METHOD_METADATA_KEYS = {
    "allow",
    "category",
    "debug_max_profit",
    "no_upkeep",
    "output",
    "potential",
    "produced",
}
DISABLED_PRODUCTION_EXPERIMENTS = frozenset(
    {
        "dummy_victuals_producer",
        "mining_village",
        "mining_village_blast_furnace",
        "mining_village_coke_blast_furnace",
        "mining_village_hot_blast_furnace",
        "mining_village_slitting_mills",
        "victuals_market_export",
    }
)
FAITHFUL_IMPORT_ALLOW_RULES = {
    "profit_percent": "Faithful production import pending building-specific rebalance.",
    "base_output_per_1k": "Faithful production import pending building-specific rebalance.",
    "input_throughput": "Faithful production import pending building-specific rebalance.",
    "output_throughput": "Faithful production import pending building-specific rebalance.",
    "amortization_months": "Faithful production import pending building-specific rebalance.",
}
VANILLA_BUILDING_ICON_RELATIVE = Path("game") / "main_menu" / "gfx" / "interface" / "icons" / "buildings"


@dataclass(frozen=True)
class ProductionBuildingCoverage:
    vanilla_buildings: set[str]
    vanilla_goods_by_building: dict[str, set[str]]
    constructor_buildings: set[str]
    constructor_goods_by_building: dict[str, set[str]]
    constructor_source_by_building: dict[str, tuple[str, str]]
    accepted_blueprints_by_building: dict[str, Path]
    cost_only_stub_buildings: set[str]
    production_blueprint_buildings: set[str]

    @property
    def missing_buildings(self) -> set[str]:
        return self.vanilla_buildings - set(self.accepted_blueprints_by_building)

    @property
    def constructor_only_buildings(self) -> set[str]:
        return self.constructor_buildings - self.vanilla_buildings - DISABLED_PRODUCTION_EXPERIMENTS

    @property
    def missing_constructor_buildings(self) -> set[str]:
        return (
            self.constructor_buildings - DISABLED_PRODUCTION_EXPERIMENTS
        ) - set(self.accepted_blueprints_by_building)

    @property
    def missing_import_targets(self) -> set[str]:
        return self.missing_buildings | self.missing_constructor_buildings

    @property
    def stub_only_buildings(self) -> set[str]:
        return self.vanilla_buildings & self.cost_only_stub_buildings

    @property
    def unowned_constructor_buildings(self) -> set[str]:
        unowned: set[str] = set()
        for building in self.constructor_buildings - DISABLED_PRODUCTION_EXPERIMENTS:
            mode, layer = self.constructor_source_by_building.get(building, ("", ""))
            expected_mode = "REPLACE" if building in self.vanilla_buildings else "CREATE"
            if layer != "constructor" or mode != expected_mode:
                unowned.add(building)
        return unowned


@dataclass(frozen=True)
class BuildingProfitRow:
    building: str
    age: str
    profit: float
    worker_food_gold: float
    benchmark_profit: float | None
    benchmark_ratio: float | None
    method_names: tuple[str, ...]


@dataclass(frozen=True)
class BlueprintConversionResult:
    building: str
    path: Path
    method_count: int
    slot_count: int
    changed: bool


class LiteralString(str):
    pass


class BlueprintDumper(yaml.SafeDumper):
    pass


def _literal_string_representer(dumper: yaml.Dumper, data: LiteralString) -> yaml.ScalarNode:
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")


BlueprintDumper.add_representer(LiteralString, _literal_string_representer)


def production_building_coverage(
    repo: Path,
    *,
    load_order_path: Path,
    vanilla_profile: str = "vanilla",
    constructor_profile: str = "constructor",
) -> ProductionBuildingCoverage:
    vanilla_data = load_eu5_data(profile=vanilla_profile, load_order_path=load_order_path)
    constructor_data = load_eu5_data(profile=constructor_profile, load_order_path=load_order_path)
    vanilla_buildings, goods_by_building = positive_output_buildings(vanilla_data.building_data)
    constructor_buildings, constructor_goods = positive_output_buildings(constructor_data.building_data)
    accepted = accepted_blueprint_paths_by_building(repo)
    stub_only = accepted_cost_only_stub_buildings(repo)
    production = accepted_production_blueprint_buildings(repo)
    return ProductionBuildingCoverage(
        vanilla_buildings=vanilla_buildings,
        vanilla_goods_by_building=goods_by_building,
        constructor_buildings=constructor_buildings,
        constructor_goods_by_building=constructor_goods,
        constructor_source_by_building=_constructor_source_by_building(constructor_data.buildings),
        accepted_blueprints_by_building=accepted,
        cost_only_stub_buildings=stub_only,
        production_blueprint_buildings=production,
    )


def positive_output_buildings(building_data: Any) -> tuple[set[str], dict[str, set[str]]]:
    buildings: set[str] = set()
    goods_by_building: dict[str, set[str]] = {}
    global_output_goods = {
        str(row["name"]): str(row["produced"])
        for row in building_data.production_methods.filter(
            (building_data.production_methods["source_kind"] == "global")
            & building_data.production_methods["produced"].is_not_null()
            & (building_data.production_methods["output"].fill_null(0.0) > POSITIVE_OUTPUT_EPSILON)
        )
        .select(["name", "produced"])
        .to_dicts()
    }

    for row in (
        building_data.production_methods.filter(
            building_data.production_methods["building"].is_not_null()
            & (building_data.production_methods["source_kind"].fill_null("") != "generated_rgo")
            & building_data.production_methods["produced"].is_not_null()
            & (building_data.production_methods["output"].fill_null(0.0) > POSITIVE_OUTPUT_EPSILON)
        )
        .select(["building", "produced"])
        .to_dicts()
    ):
        building = str(row["building"])
        buildings.add(building)
        goods_by_building.setdefault(building, set()).add(str(row["produced"]))

    for row in building_data.buildings.select(["name", "possible_production_methods"]).to_dicts():
        building = str(row["name"])
        for method in row["possible_production_methods"] or []:
            good = global_output_goods.get(str(method))
            if good is None:
                continue
            buildings.add(building)
            goods_by_building.setdefault(building, set()).add(good)

    return buildings, goods_by_building


def accepted_blueprint_paths_by_building(repo: Path) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    for path in _manifest_blueprint_paths(repo):
        template = load_template(path)
        paths[template.key] = path
    return paths


def accepted_cost_only_stub_buildings(repo: Path) -> set[str]:
    result: set[str] = set()
    for path in _manifest_blueprint_paths(repo):
        raw = _load_yaml(path)
        building = raw.get("building") or {}
        body = str(building.get("body") or "")
        slots = building.get("production_method_slots") or []
        methods = raw.get("production_methods") or []
        mode = str(building.get("mode") or "").upper()
        if (
            mode in {"TRY_INJECT", "INJECT"}
            and not slots
            and not methods
            and "unique_production_methods" not in body
            and "possible_production_methods" not in body
        ):
            result.add(str(building.get("key")))
    return result


def accepted_production_blueprint_buildings(repo: Path) -> set[str]:
    result: set[str] = set()
    for path in _manifest_blueprint_paths(repo):
        raw = _load_yaml(path)
        building = raw.get("building") or {}
        body = str(building.get("body") or "")
        slots = building.get("production_method_slots") or []
        methods = raw.get("production_methods") or []
        if slots or methods or "unique_production_methods" in body or "possible_production_methods" in body:
            result.add(str(building.get("key")))
    return result


def production_profit_rows(
    *,
    profile: str,
    load_order_path: Path,
    include_specific: bool = False,
) -> tuple[list[BuildingProfitRow], dict[str, float]]:
    data = load_eu5_data(profile=profile, load_order_path=load_order_path)
    annotated = annotate_building_data_availability(
        data.building_data,
        data.advancements,
        include_specific_unlocks=include_specific,
    )
    method_rows = _attached_production_methods(
        annotated.buildings.to_dicts(),
        annotated.production_methods.to_dicts(),
    )
    worker_food = _base_worker_food_by_building(data.building_worker_food_costs.to_dicts())
    rows, benchmark_by_age = _rows_and_benchmarks_by_age(
        method_rows,
        worker_food,
        include_specific=include_specific,
    )

    with_benchmarks = [
        BuildingProfitRow(
            building=row.building,
            age=row.age,
            profit=row.profit,
            worker_food_gold=row.worker_food_gold,
            benchmark_profit=benchmark_by_age.get(row.age),
            benchmark_ratio=_safe_ratio(row.profit, benchmark_by_age.get(row.age)),
            method_names=row.method_names,
        )
        for row in rows
    ]
    return with_benchmarks, benchmark_by_age


def production_profit_report(
    repo: Path,
    *,
    profile: str,
    vanilla_profile: str,
    load_order_path: Path,
    include_specific: bool = False,
) -> str:
    coverage = production_building_coverage(
        repo,
        load_order_path=load_order_path,
        vanilla_profile=vanilla_profile,
    )
    rows, benchmarks = production_profit_rows(
        profile=profile,
        load_order_path=load_order_path,
        include_specific=include_specific,
    )
    latest_by_building = _latest_rows_by_building(rows)
    flagged = [
        row
        for building, row in sorted(latest_by_building.items())
        if building in coverage.vanilla_buildings
        and (building in coverage.stub_only_buildings or (row.benchmark_ratio or 0.0) > BALANCE_UPPER_RATIO)
    ]
    lines = [
        "production-profit report",
        f"vanilla_positive_output_buildings={len(coverage.vanilla_buildings)}",
        f"accepted_blueprint_targets={len(coverage.accepted_blueprints_by_building)}",
        f"missing_blueprint_targets={len(coverage.missing_buildings)}",
        f"cost_only_stub_targets={len(coverage.stub_only_buildings)}",
        "benchmarks:",
    ]
    lines.extend(f"  {age}: {_fmt_float(value)}" for age, value in benchmarks.items())
    lines.append("flagged:")
    if not flagged:
        lines.append("  none")
    else:
        for row in sorted(flagged, key=lambda item: (-_ratio_sort_value(item), item.building)):
            flags = []
            if row.building in coverage.stub_only_buildings:
                flags.append("stub")
            if row.benchmark_ratio is not None and row.benchmark_ratio > BALANCE_UPPER_RATIO:
                flags.append("profit")
            lines.append(
                "  "
                f"{row.building} {row.age} profit={_fmt_float(row.profit)} "
                f"benchmark={_fmt_float(row.benchmark_profit)} "
                f"ratio={_fmt_float(row.benchmark_ratio)} "
                f"flags={','.join(flags)}"
            )
    return "\n".join(lines)


def convert_vanilla_production_stubs(
    repo: Path,
    *,
    profile: str,
    vanilla_profile: str,
    load_order_path: Path,
    dry_run: bool = False,
    target_buildings: Sequence[str] | None = None,
    burgher_employment_size: float | None = None,
) -> list[BlueprintConversionResult]:
    coverage = production_building_coverage(
        repo,
        load_order_path=load_order_path,
        vanilla_profile=vanilla_profile,
    )
    targets = sorted(set(target_buildings) if target_buildings is not None else coverage.stub_only_buildings)
    unknown_targets = set(targets) - coverage.vanilla_buildings
    if unknown_targets:
        raise ValueError(f"Targets are not vanilla positive-output buildings: {sorted(unknown_targets)}")
    missing_targets = set(targets) - set(coverage.accepted_blueprints_by_building)
    if missing_targets:
        raise ValueError(f"Targets do not have accepted blueprints: {sorted(missing_targets)}")
    if not targets:
        return []

    data = load_eu5_data(profile=profile, load_order_path=load_order_path)
    annotated = annotate_building_data_availability(
        data.building_data,
        data.advancements,
        include_specific_unlocks=True,
    )
    rows_by_method = {str(row["name"]): row for row in annotated.production_methods.to_dicts()}
    rows_by_building_method = {
        (str(row.get("building")), str(row["name"])): row
        for row in annotated.production_methods.to_dicts()
        if row.get("building") is not None
    }
    buildings = {str(row["name"]): row for row in annotated.buildings.to_dicts()}
    current_entries = {
        entry.key: entry
        for entry in load_merged_directory(
            load_profile(profile, load_order_path),
            "building_types",
        ).entries
    }
    global_methods = {
        entry.key: entry.value
        for entry in load_merged_directory(
            load_profile(profile, load_order_path),
            "production_methods",
        ).entries
    }
    _rows, benchmarks = production_profit_rows(
        profile=profile,
        load_order_path=load_order_path,
        include_specific=True,
    )

    results: list[BlueprintConversionResult] = []
    for building in targets:
        path = coverage.accepted_blueprints_by_building[building]
        raw = _load_yaml(path)
        current = current_entries.get(building)
        if current is None or not isinstance(current.value, CList):
            continue
        converted_block, slots, method_count, _mapping = _converted_building_block(
            building,
            current.value,
            building_row=buildings.get(building, {}),
            production_methods=rows_by_method,
            production_methods_by_building=rows_by_building_method,
            global_method_blocks=global_methods,
            benchmarks=benchmarks,
            burgher_employment_size=burgher_employment_size,
        )
        raw["building"]["mode"] = "REPLACE"
        raw["building"]["source"] = "pp_building_adjustments.txt"
        raw["building"]["production_method_slots"] = slots
        raw["building"]["possible_production_methods"] = []
        raw["building"]["body"] = LiteralString(_body_from_block(converted_block))
        raw["localization"] = {"entries": _localization_entries(building, slots)}

        text = _dump_blueprint(raw)
        old_text = path.read_text(encoding="utf-8-sig")
        changed = text != old_text
        if changed and not dry_run:
            path.write_text(text, encoding="utf-8")
        results.append(
            BlueprintConversionResult(
                building=building,
                path=path,
                method_count=method_count,
                slot_count=len(slots),
                changed=changed,
            )
        )
    return results


def import_missing_production_buildings(
    repo: Path,
    *,
    profile: str,
    vanilla_profile: str,
    load_order_path: Path,
    dry_run: bool = False,
    burgher_employment_size: float | None = None,
) -> list[BlueprintConversionResult]:
    coverage = production_building_coverage(
        repo,
        load_order_path=load_order_path,
        vanilla_profile=vanilla_profile,
        constructor_profile=profile,
    )
    targets = sorted(coverage.missing_import_targets)
    if not targets:
        return []

    vanilla_profile_config = load_profile(vanilla_profile, load_order_path)
    constructor_profile_config = load_profile(profile, load_order_path)
    vanilla_entries = {
        entry.key: entry
        for entry in load_merged_directory(vanilla_profile_config, "building_types").entries
    }
    constructor_entries = {
        entry.key: entry
        for entry in load_merged_directory(constructor_profile_config, "building_types").entries
    }
    vanilla_globals = {
        entry.key: entry.value
        for entry in load_merged_directory(vanilla_profile_config, "production_methods").entries
    }
    constructor_globals = {
        entry.key: entry.value
        for entry in load_merged_directory(constructor_profile_config, "production_methods").entries
    }
    vanilla_data = load_eu5_data(profile=vanilla_profile, load_order_path=load_order_path)
    constructor_data = load_eu5_data(profile=profile, load_order_path=load_order_path)
    vanilla_buildings = {str(row["name"]): row for row in vanilla_data.buildings.to_dicts()}
    constructor_buildings = {str(row["name"]): row for row in constructor_data.buildings.to_dicts()}
    vanilla_methods = {str(row["name"]): row for row in vanilla_data.production_methods.to_dicts()}
    constructor_methods = {str(row["name"]): row for row in constructor_data.production_methods.to_dicts()}
    vanilla_methods_by_building = {
        (str(row.get("building")), str(row["name"])): row
        for row in vanilla_data.production_methods.to_dicts()
        if row.get("building") is not None
    }
    constructor_methods_by_building = {
        (str(row.get("building")), str(row["name"])): row
        for row in constructor_data.production_methods.to_dicts()
        if row.get("building") is not None
    }
    vanilla_root = LoadOrderConfig.load(load_order_path).vanilla_root
    vanilla_loc = _english_localization(vanilla_profile, load_order_path)
    constructor_loc = _english_localization(profile, load_order_path)
    manifest_path = repo / BUILDING_BLUEPRINT_MANIFEST_RELATIVE
    buildings_dir = repo / BUILDING_BLUEPRINT_BUILDINGS_RELATIVE
    results: list[BlueprintConversionResult] = []
    manifest_entries: list[str] = []

    for building in targets:
        is_vanilla = building in coverage.vanilla_buildings
        current = vanilla_entries.get(building) if is_vanilla else constructor_entries.get(building)
        if current is None or not isinstance(current.value, CList):
            continue
        building_row = vanilla_buildings.get(building, {}) if is_vanilla else constructor_buildings.get(building, {})
        converted_block, slots, method_count, mapping = _converted_building_block(
            building,
            current.value,
            building_row=building_row,
            production_methods=vanilla_methods if is_vanilla else constructor_methods,
            production_methods_by_building=(
                vanilla_methods_by_building if is_vanilla else constructor_methods_by_building
            ),
            global_method_blocks=vanilla_globals if is_vanilla else constructor_globals,
            benchmarks={},
            burgher_employment_size=burgher_employment_size,
        )
        raw = _faithful_production_blueprint(
            building,
            mode="REPLACE" if is_vanilla else "CREATE",
            block=converted_block,
            slots=slots,
            building_row=building_row,
            vanilla_root=vanilla_root,
            method_names=mapping,
            loc=vanilla_loc if is_vanilla else constructor_loc,
        )
        relative = Path("buildings") / f"{building}.yml"
        path = buildings_dir / f"{building}.yml"
        text = _dump_blueprint(raw)
        existed = path.exists()
        already_enabled = building in coverage.accepted_blueprints_by_building
        if existed:
            if not already_enabled:
                manifest_entries.append(relative.as_posix())
            results.append(
                BlueprintConversionResult(
                    building=building,
                    path=path,
                    method_count=method_count,
                    slot_count=len(slots),
                    changed=not already_enabled,
                )
            )
            continue
        if not dry_run:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        manifest_entries.append(relative.as_posix())
        results.append(
            BlueprintConversionResult(
                building=building,
                path=path,
                method_count=method_count,
                slot_count=len(slots),
                changed=True,
            )
        )

    if manifest_entries and not dry_run:
        _enable_manifest_entries(manifest_path, manifest_entries)
    return results


def validate_employment_size_step(value: float | int | str | None) -> bool:
    if value is None or isinstance(value, bool):
        return False
    try:
        decimal = Decimal(str(value))
    except Exception:
        return False
    if decimal <= 0:
        return False
    ratio = decimal / EMPLOYMENT_STEP
    return ratio == ratio.to_integral_value()


def _constructor_source_by_building(buildings: Any) -> dict[str, tuple[str, str]]:
    return {
        str(row["name"]): (str(row.get("source_mode") or ""), str(row.get("source_layer") or ""))
        for row in buildings.select(["name", "source_mode", "source_layer"]).to_dicts()
    }


def _faithful_production_blueprint(
    building: str,
    *,
    mode: str,
    block: CList,
    slots: list[dict[str, Any]],
    building_row: Mapping[str, Any],
    vanilla_root: Path,
    method_names: Mapping[str, str] | None = None,
    loc: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    raw: dict[str, Any] = {
        "version": 2,
        "tag": _safe_key(building),
        "building": {
            "key": building,
            "mode": mode,
            "source": "pp_building_adjustments.txt" if mode == "REPLACE" else "pp_new_buildings.txt",
            "production_method_slots": slots,
            "possible_production_methods": [],
            "body": LiteralString(_body_from_block(block)),
        },
        "localization": {
            "entries": _localization_entries(
                building,
                slots,
                method_names=method_names,
                loc=loc,
                include_building=mode == "CREATE",
            )
        },
        "evaluation": {"allow_rules": dict(FAITHFUL_IMPORT_ALLOW_RULES)},
    }
    icon = _optional_icon_spec(building_row, vanilla_root)
    if icon is not None:
        raw["icon"] = icon
    return raw


def _optional_icon_spec(building_row: Mapping[str, Any], vanilla_root: Path) -> dict[str, Any] | None:
    icon_name = building_row.get("icon")
    if not isinstance(icon_name, str) or not icon_name.strip():
        return None
    filename = f"{icon_name}.dds"
    source = vanilla_root / VANILLA_BUILDING_ICON_RELATIVE / filename
    if not source.is_file():
        return None
    return {
        "source_dds": source.as_posix(),
        "output_dds": filename,
        "size": 512,
    }


def _enable_manifest_entries(manifest_path: Path, entries: Sequence[str]) -> None:
    existing = manifest_path.read_text(encoding="utf-8")
    raw = yaml.safe_load(existing) if existing.strip() else {}
    if not isinstance(raw, dict):
        raise ValueError(f"{manifest_path}: expected mapping")
    enabled = raw.get("enabled") or {}
    if isinstance(enabled, dict):
        known = {str(path) for path in enabled}
        missing = [entry for entry in entries if entry not in known]
        if not missing:
            return
        if not enabled:
            raw["enabled"] = {entry: True for entry in missing}
            manifest_path.write_text(_dump_blueprint(raw), encoding="utf-8")
            return
        suffix = "" if existing.endswith("\n") else "\n"
        addition = "".join(f"  {entry}: true\n" for entry in missing)
        manifest_path.write_text(existing + suffix + addition, encoding="utf-8")
        return
    raise ValueError(f"{manifest_path}: enabled must be a mapping of path -> true/false")


def _manifest_blueprint_paths(repo: Path) -> list[Path]:
    manifest_path = repo / BUILDING_BLUEPRINT_MANIFEST_RELATIVE
    manifest = _load_yaml(manifest_path)
    return [
        repo / BUILDING_BLUEPRINT_ROOT_RELATIVE / entry
        for entry in enabled_manifest_entries(manifest.get("enabled", []), source=manifest_path)
    ]


def _load_yaml(path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: expected mapping")
    return raw


def _attached_production_methods(
    buildings: Sequence[dict[str, Any]],
    production_methods: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    global_methods = {
        str(row["name"]): row
        for row in production_methods
        if row.get("source_kind") == "global"
    }
    for row in production_methods:
        if row.get("building") is not None:
            rows.append(dict(row))
    for building in buildings:
        building_name = str(building["name"])
        for method_name in building.get("possible_production_methods") or []:
            method = global_methods.get(str(method_name))
            if method is None:
                continue
            row = dict(method)
            row["building"] = building_name
            row["production_method_group"] = "possible_production_methods"
            row["production_method_group_index"] = None
            rows.append(row)
    return rows


def _base_worker_food_by_building(rows: Sequence[dict[str, Any]]) -> dict[str, float]:
    result: dict[str, float] = {}
    for row in rows:
        if row.get("scenario") != BASE_WORKER_FOOD_SCENARIO:
            continue
        value = _optional_float(row.get("worker_food_gold"))
        if value is not None:
            result[str(row["building"])] = value
    return result


def _rows_and_benchmarks_by_age(
    methods: Sequence[dict[str, Any]],
    worker_food: Mapping[str, float],
    *,
    include_specific: bool,
) -> tuple[list[BuildingProfitRow], dict[str, float]]:
    rows: list[BuildingProfitRow] = []
    benchmark_by_age: dict[str, float] = {}

    for age in AGE_ORDER:
        rows_for_age = _profit_rows_for_age(
            methods,
            worker_food,
            age,
            include_specific=include_specific,
        )
        farm_profits = [
            row.profit
            for row in rows_for_age
            if row.building in LAND_FARM_BUILDINGS and row.profit > 0
        ]
        if farm_profits:
            benchmark_by_age[age] = median(farm_profits)
        else:
            prior = [known for known in AGE_ORDER if known in benchmark_by_age]
            benchmark_by_age[age] = benchmark_by_age[prior[-1]] if prior else 0.0
        rows.extend(rows_for_age)

    return rows, benchmark_by_age


def _profit_rows_for_age(
    methods: Sequence[dict[str, Any]],
    worker_food: Mapping[str, float],
    age: str,
    *,
    include_specific: bool,
) -> list[BuildingProfitRow]:
    slots_by_building: dict[str, dict[object, tuple[float, str]]] = {}
    for method in methods:
        building = str(method.get("building") or "")
        if not building or not method.get("produced"):
            continue
        if not _method_available_by_age(method, age, include_specific=include_specific):
            continue
        output = _optional_float(method.get("output_value"))
        if output is None or output <= 0:
            continue
        input_cost = _optional_float(method.get("input_cost")) or 0.0
        profit = output - input_cost
        slot = _method_slot(method)
        name = str(method.get("name") or "")
        slots = slots_by_building.setdefault(building, {})
        existing = slots.get(slot)
        if existing is None or profit > existing[0] or (profit == existing[0] and name < existing[1]):
            slots[slot] = (profit, name)

    rows: list[BuildingProfitRow] = []
    for building, slots in slots_by_building.items():
        method_profit = sum(profit for profit, _name in slots.values())
        food = worker_food.get(building, 0.0)
        rows.append(
            BuildingProfitRow(
                building=building,
                age=age,
                profit=method_profit - food,
                worker_food_gold=food,
                benchmark_profit=None,
                benchmark_ratio=None,
                method_names=tuple(name for _profit, name in slots.values()),
            )
        )
    return rows


def _method_available_by_age(
    method: Mapping[str, Any],
    age: str,
    *,
    include_specific: bool,
) -> bool:
    kind = str(method.get("effective_availability_kind") or method.get("availability_kind") or "")
    if kind == "available_by_default":
        return True
    if kind == "specific_only" and not include_specific:
        return False
    unlock_age = method.get("effective_unlock_age") or method.get("unlock_age")
    if unlock_age not in AGE_INDEX:
        return False
    return AGE_INDEX[str(unlock_age)] <= AGE_INDEX[age]


def _method_slot(method: Mapping[str, Any]) -> object:
    slot = method.get("production_method_group_index")
    if slot is not None:
        return slot
    return method.get("production_method_group") or "__slotless__"


def _latest_rows_by_building(rows: Iterable[BuildingProfitRow]) -> dict[str, BuildingProfitRow]:
    latest: dict[str, BuildingProfitRow] = {}
    for row in rows:
        existing = latest.get(row.building)
        if existing is None or AGE_INDEX[row.age] > AGE_INDEX[existing.age]:
            latest[row.building] = row
    return latest


def _converted_building_block(
    building: str,
    block: CList,
    *,
    building_row: Mapping[str, Any],
    production_methods: Mapping[str, Mapping[str, Any]],
    production_methods_by_building: Mapping[tuple[str, str], Mapping[str, Any]],
    global_method_blocks: Mapping[str, Value],
    benchmarks: Mapping[str, float],
    burgher_employment_size: float | None,
) -> tuple[CList, list[dict[str, Any]], int, dict[str, str]]:
    location = _location()
    mapping: dict[str, str] = {}
    slot_methods: list[list[str]] = []
    group_count = sum(
        1
        for entry in block.entries
        if entry.key == "unique_production_methods" and isinstance(entry.value, CList)
    )
    possible_methods = _possible_methods(block)
    if possible_methods:
        group_count += 1
    group_count = max(group_count, 1)
    benchmark = _building_benchmark(building_row, benchmarks)
    slot_target = benchmark * BALANCE_WRITE_TARGET_RATIO / group_count if benchmark > 0 else None

    entries: list[CEntry] = []
    saw_employment = False
    saw_increase_cost = False
    for entry in block.entries:
        if entry.key == "possible_production_methods":
            continue
        if entry.key == "employment_size":
            saw_employment = True
            entries.append(
                CEntry(
                    entry.key,
                    entry.op,
                    _clean_employment_size(
                        building_row.get("employment_size"),
                        pop_type=building_row.get("pop_type"),
                        burgher_employment_size=burgher_employment_size,
                    ),
                    entry.location,
                )
            )
            continue
        if entry.key == "increase_per_level_cost":
            saw_increase_cost = True
            entries.append(entry)
            continue
        if entry.key == "unique_production_methods" and isinstance(entry.value, CList):
            converted_group, methods = _converted_method_group(
                building,
                entry.value,
                mapping,
                production_methods_by_building=production_methods_by_building,
                slot_target=slot_target,
            )
            slot_methods.append(methods)
            entries.append(CEntry(entry.key, entry.op, converted_group, entry.location))
            continue
        entries.append(entry)

    if possible_methods:
        converted_entries: list[CEntry] = []
        methods: list[str] = []
        for method in possible_methods:
            value = global_method_blocks.get(method)
            if not isinstance(value, CList):
                continue
            original = CEntry(method, "=", value, location)
            new_name = mapping.setdefault(method, _pp_method_name(building, method))
            converted = _converted_method_entry(
                building,
                original,
                new_name,
                production_methods.get(method),
                slot_target=slot_target,
            )
            converted_entries.append(converted)
            methods.append(new_name)
        if converted_entries:
            entries.append(
                CEntry(
                    "unique_production_methods",
                    "=",
                    CList(entries=converted_entries),
                    location,
                )
            )
            slot_methods.append(methods)

    if not saw_employment:
        entries.append(
            CEntry(
                "employment_size",
                "=",
                _clean_employment_size(
                    building_row.get("employment_size"),
                    pop_type=building_row.get("pop_type"),
                    burgher_employment_size=burgher_employment_size,
                ),
                location,
            )
        )
    if not saw_increase_cost:
        cost = building_row.get("increase_per_level_cost")
        if cost is not None:
            entries.append(CEntry("increase_per_level_cost", "=", cost, location))

    slots = [
        {"name": f"slot_{index}", "methods": methods}
        for index, methods in enumerate(slot_methods)
        if methods
    ]
    return (
        CList(entries=entries, items=list(block.items)),
        slots,
        sum(len(slot["methods"]) for slot in slots),
        mapping,
    )


def _converted_method_group(
    building: str,
    group: CList,
    mapping: dict[str, str],
    *,
    production_methods_by_building: Mapping[tuple[str, str], Mapping[str, Any]],
    slot_target: float | None,
) -> tuple[CList, list[str]]:
    entries: list[CEntry] = []
    methods: list[str] = []
    for entry in group.entries:
        if not isinstance(entry.value, CList):
            entries.append(entry)
            continue
        new_name = mapping.setdefault(entry.key, _pp_method_name(building, entry.key))
        converted = _converted_method_entry(
            building,
            entry,
            new_name,
            production_methods_by_building.get((building, entry.key)),
            slot_target=slot_target,
        )
        entries.append(converted)
        methods.append(new_name)
    return CList(entries=entries, items=list(group.items)), methods


def _converted_method_entry(
    building: str,
    entry: CEntry,
    new_name: str,
    method_row: Mapping[str, Any] | None,
    *,
    slot_target: float | None,
) -> CEntry:
    block = entry.value
    if not isinstance(block, CList):
        return CEntry(new_name, entry.op, entry.value, entry.location)
    scale = _input_scale_for_target(method_row, slot_target)
    return CEntry(
        new_name,
        entry.op,
        CList(
            entries=[
                _converted_method_child(child, scale=scale)
                for child in block.entries
            ],
            items=list(block.items),
        ),
        entry.location,
    )


def _converted_method_child(entry: CEntry, *, scale: float) -> CEntry:
    if entry.key == "output":
        value = _rounded_float(entry.value)
    elif entry.key not in METHOD_METADATA_KEYS:
        value = _scaled_numeric_value(entry.value, scale=scale)
    else:
        value = entry.value
    return CEntry(entry.key, entry.op, value, entry.location)


def _input_scale_for_target(
    method_row: Mapping[str, Any] | None,
    slot_target: float | None,
) -> float:
    if method_row is None or slot_target is None:
        return 1.0
    output = _optional_float(method_row.get("output_value"))
    input_cost = _optional_float(method_row.get("input_cost"))
    if output is None or input_cost is None or input_cost <= 0:
        return 1.0
    profit = output - input_cost
    if profit <= slot_target:
        return 1.0
    desired_input = max(output - slot_target, input_cost)
    return max(1.0, desired_input / input_cost)


def _scaled_numeric_value(value: Value, *, scale: float) -> Value:
    number = _optional_float(value)
    if number is None:
        return value
    return _rounded_float(number * scale)


def _rounded_float(value: Any) -> float:
    number = _optional_float(value)
    if number is None:
        return value
    return float(Decimal(str(number)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP))


def _possible_methods(block: CList) -> list[str]:
    methods: list[str] = []
    for entry in block.entries:
        if entry.key != "possible_production_methods" or not isinstance(entry.value, CList):
            continue
        for item in entry.value.items:
            if isinstance(item, str):
                methods.append(item)
    return methods


def _building_benchmark(building_row: Mapping[str, Any], benchmarks: Mapping[str, float]) -> float:
    age = str(
        building_row.get("effective_unlock_age")
        or building_row.get("unlock_age")
        or building_row.get("general_unlock_age")
        or AGE_ORDER[0]
    )
    if age in benchmarks and benchmarks[age] > 0:
        return benchmarks[age]
    known = [item for item in AGE_ORDER if item in benchmarks and benchmarks[item] > 0]
    if not known:
        return 0.0
    age_index = AGE_INDEX.get(age, 0)
    prior = [item for item in known if AGE_INDEX[item] <= age_index]
    return benchmarks[(prior or known)[-1]]


def _clean_employment_size(
    value: Any,
    *,
    pop_type: Any = None,
    burgher_employment_size: float | None = None,
) -> float:
    number = (
        _optional_float(burgher_employment_size)
        if str(pop_type) == "burghers" and burgher_employment_size is not None
        else _optional_float(value)
    )
    if number is None or number <= 0:
        number = 1.0
    decimal = Decimal(str(number))
    steps = (decimal / EMPLOYMENT_STEP).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return float((steps * EMPLOYMENT_STEP).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _body_from_block(block: CList) -> str:
    rendered = render_list(block, indent=0).splitlines()
    inner = rendered[1:-1]
    stripped = [line[1:] if line.startswith("\t") else line for line in inner]
    return "\n".join(line.replace("\t", "    ") for line in stripped).rstrip() + "\n"


def _english_localization(profile: str, load_order_path: Path) -> dict[str, str]:
    return dict(
        NotebookLabelResolver.from_profile(
            profile=profile,
            load_order_path=load_order_path,
        ).localization
    )


def _localization_entries(
    building: str,
    slots: Sequence[Mapping[str, Any]],
    *,
    method_names: Mapping[str, str] | None = None,
    loc: Mapping[str, str] | None = None,
    include_building: bool = False,
) -> dict[str, str]:
    reverse = {new: old for old, new in (method_names or {}).items()}
    loc = loc or {}
    entries: dict[str, str] = {}
    if include_building:
        if loc.get(building):
            entries[building] = str(loc[building])
        desc_key = f"{building}_desc"
        if loc.get(desc_key):
            entries[desc_key] = str(loc[desc_key])
    for index, slot in enumerate(slots):
        slot_key = f"{building}_slot_{index}"
        entries[slot_key] = str(loc.get(slot_key) or f"{_title_from_key(building)} Work")
        for method in slot.get("methods") or []:
            original = reverse.get(str(method), str(method))
            entries[str(method)] = str(
                loc.get(original)
                or loc.get(str(method))
                or _title_from_key(str(method).removeprefix("pp_"))
            )
    return entries


def _dump_blueprint(raw: Mapping[str, Any]) -> str:
    return yaml.dump(
        raw,
        Dumper=BlueprintDumper,
        allow_unicode=False,
        default_flow_style=False,
        sort_keys=False,
        width=1000,
    )


def _pp_method_name(building: str, method: str) -> str:
    method_key = re.sub(r"(^|_)base(_|$)", r"\1standard\2", _safe_key(method))
    return f"pp_{_safe_key(building)}_{method_key}"


def _safe_key(value: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", value.lower()).strip("_")


def _title_from_key(value: str) -> str:
    return " ".join(part.capitalize() for part in value.split("_") if part)


def _optional_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _safe_ratio(value: float, divisor: float | None) -> float | None:
    if divisor is None or divisor <= 0:
        return None
    return value / divisor


def _ratio_sort_value(row: BuildingProfitRow) -> float:
    return -1.0 if row.benchmark_ratio is None else row.benchmark_ratio


def _fmt_float(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.2f}"


def _location() -> SourceLocation:
    return SourceLocation(path=None, line=1, column=1)
