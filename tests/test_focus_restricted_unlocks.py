from __future__ import annotations

from collections import defaultdict, deque
from functools import lru_cache
import json
from pathlib import Path
import re

import yaml

from eu5gameparser.domain.eu5 import load_eu5_data


ROOT = Path(__file__).resolve().parents[1]
BLUEPRINT_ROOT = ROOT / "blueprints" / "accepted"
MANIFEST_PATH = ROOT / "blueprints" / "buildings.manifest.yml"
FOCUS_VALUES = {"adm", "dip", "mil"}
INTENTIONAL_ZERO_NET_ADVANCE_PATCH_FILES = {"pp_rgo_building_cost_redirects.txt"}


def test_constructor_owned_unlocks_do_not_depend_on_age_focus_advances() -> None:
    data = load_eu5_data(
        profile="constructor",
        load_order_path=ROOT / "constructor.load_order.toml",
    )
    advancement_rows = data.advancements.to_dicts()
    restricted_roots_by_advance = _focus_restricted_roots_by_advance(advancement_rows)
    constructor_buildings = _constructor_owned_names(data.building_data.buildings)
    constructor_methods = _constructor_owned_names(data.building_data.production_methods)

    offenders: list[str] = []
    for row in advancement_rows:
        restricted_roots = restricted_roots_by_advance.get(row["name"])
        if restricted_roots is None:
            continue

        offenders.extend(
            _restricted_unlock_offenders(
                row,
                unlock_column="unlock_building",
                item_kind="building",
                constructor_items=constructor_buildings,
                restricted_roots=restricted_roots,
            )
        )
        offenders.extend(
            _restricted_unlock_offenders(
                row,
                unlock_column="unlock_production_method",
                item_kind="production_method",
                constructor_items=constructor_methods,
                restricted_roots=restricted_roots,
            )
        )

    assert offenders == []


def test_constructor_owned_unlocks_after_age_one_have_institution_gated_ancestry() -> None:
    data = load_eu5_data(
        profile="constructor",
        load_order_path=ROOT / "constructor.load_order.toml",
    )
    advancement_rows = data.advancements.to_dicts()
    rows_by_advance = {row["name"]: row for row in advancement_rows}
    constructor_buildings, constructor_methods = _accepted_constructor_blueprint_unlocks()

    @lru_cache(maxsize=None)
    def has_institution_gated_ancestor(advance: str) -> bool:
        row = rows_by_advance.get(advance)
        if row is None:
            return False
        if "has_embraced_institution" in (row.get("data") or ""):
            return True
        return any(has_institution_gated_ancestor(requirement) for requirement in row.get("requires") or [])

    offenders: list[str] = []
    for row in advancement_rows:
        if _age_number(row.get("age")) <= 1 or has_institution_gated_ancestor(row["name"]):
            continue
        offenders.extend(
            _institution_free_unlock_offenders(
                row,
                unlock_column="unlock_building",
                item_kind="building",
                constructor_items=constructor_buildings,
            )
        )
        offenders.extend(
            _institution_free_unlock_offenders(
                row,
                unlock_column="unlock_production_method",
                item_kind="production_method",
                constructor_items=constructor_methods,
            )
        )

    assert offenders == []


def test_constructor_sourced_advances_are_not_empty_player_techs() -> None:
    data = load_eu5_data(
        profile="constructor",
        load_order_path=ROOT / "constructor.load_order.toml",
    )

    offenders = [
        f"{row['name']} at {_source_location(row)}"
        for row in data.advancements.to_dicts()
        if row.get("source_layer") == "constructor"
        and Path(row["source_file"]).name not in INTENTIONAL_ZERO_NET_ADVANCE_PATCH_FILES
        and not _advance_has_player_payload(row)
    ]

    assert offenders == []


def _focus_restricted_roots_by_advance(
    advancement_rows: list[dict],
) -> dict[str, set[str]]:
    children_by_requirement: dict[str, list[str]] = defaultdict(list)
    focus_roots: dict[str, str] = {}
    for row in advancement_rows:
        advance = row["name"]
        focus = row.get("focus")
        if focus in FOCUS_VALUES:
            focus_roots[advance] = focus
        for requirement in row.get("requires") or []:
            children_by_requirement[requirement].append(advance)

    restricted_roots_by_advance: dict[str, set[str]] = defaultdict(set)
    for root, focus in focus_roots.items():
        root_label = f"{root} ({focus})"
        queue: deque[str] = deque([root])
        visited: set[str] = set()
        while queue:
            advance = queue.popleft()
            if advance in visited:
                continue
            visited.add(advance)
            restricted_roots_by_advance[advance].add(root_label)
            queue.extend(children_by_requirement.get(advance, []))

    return dict(restricted_roots_by_advance)


def _constructor_owned_names(table) -> set[str]:
    return {
        row["name"]
        for row in table.select(["name", "source_layer"]).to_dicts()
        if row["source_layer"] == "constructor"
    }


def _restricted_unlock_offenders(
    row: dict,
    *,
    unlock_column: str,
    item_kind: str,
    constructor_items: set[str],
    restricted_roots: set[str],
) -> list[str]:
    source = _source_location(row)
    roots = ", ".join(sorted(restricted_roots))
    return [
        (
            f"{item_kind} {item} is unlocked by focus-restricted advance "
            f"{row['name']} under {roots} at {source}"
        )
        for item in row.get(unlock_column) or []
        if item in constructor_items
    ]


def _accepted_constructor_blueprint_unlocks() -> tuple[set[str], set[str]]:
    manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    buildings: set[str] = set()
    production_methods: set[str] = set()

    for entry in manifest["enabled"]:
        if not str(entry).startswith("buildings/"):
            continue
        raw = yaml.safe_load((BLUEPRINT_ROOT / entry).read_text(encoding="utf-8-sig"))
        building = raw.get("building") or {}
        building_key = building.get("key")
        if building.get("mode") == "CREATE" and isinstance(building_key, str):
            buildings.add(building_key)
        for method in _blueprint_production_methods(raw):
            if method.startswith("pp_"):
                production_methods.add(method)

    return buildings, production_methods


def _blueprint_production_methods(raw: dict) -> set[str]:
    methods: set[str] = set()
    building = raw.get("building") or {}
    body = building.get("body") or ""
    methods.update(re.findall(r"(?m)^\s*(pp_[A-Za-z0-9_]+)\s*=\s*\{", body))
    for production_method in raw.get("production_methods") or []:
        if isinstance(production_method, dict) and isinstance(production_method.get("key"), str):
            methods.add(production_method["key"])
    for slot in building.get("production_method_slots") or []:
        for method in slot.get("methods") or []:
            if isinstance(method, str):
                methods.add(method)
    return methods


def _institution_free_unlock_offenders(
    row: dict,
    *,
    unlock_column: str,
    item_kind: str,
    constructor_items: set[str],
) -> list[str]:
    source = _source_location(row)
    return [
        (
            f"{item_kind} {item} is unlocked by institution-free age {row.get('age')} "
            f"advance {row['name']} at {source}"
        )
        for item in row.get(unlock_column) or []
        if item in constructor_items
    ]


def _advance_has_player_payload(row: dict) -> bool:
    modifiers = _json_object(row.get("modifiers"))
    unlocks = _json_object(row.get("unlocks"))

    return _has_nonzero_modifier(modifiers) or any(unlocks.values())


def _has_nonzero_modifier(value: object) -> bool:
    if isinstance(value, dict):
        return any(_has_nonzero_modifier(item) for item in value.values())
    if isinstance(value, list):
        return any(_has_nonzero_modifier(item) for item in value)
    if isinstance(value, bool) or value is None:
        return False
    if isinstance(value, (int, float)):
        return abs(float(value)) > 1e-12
    return True


def _json_object(value: object) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value:
        parsed = json.loads(value)
        assert isinstance(parsed, dict)
        return parsed
    return {}


def _age_number(age: object) -> int:
    match = re.match(r"age_(\d+)_", str(age or ""))
    return int(match.group(1)) if match else 0


def _source_location(row: dict) -> str:
    source_file = Path(row["source_file"])
    try:
        source = source_file.relative_to(ROOT)
    except ValueError:
        source = source_file
    return f"{source}:{row['source_line']}"
