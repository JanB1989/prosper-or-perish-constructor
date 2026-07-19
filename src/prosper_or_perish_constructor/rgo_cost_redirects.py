"""Generate redirects from vanilla RGO expansion costs to PoP building costs."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

from eu5gameparser.clausewitz.parser import parse_file
from eu5gameparser.clausewitz.syntax import CEntry, CList, Value
from eu5gameparser.load_order import (
    DataProfile,
    MergedEntry,
    SourceRecord,
    load_merged_directory,
    load_profile,
)


RGO_METHODS = ("farming", "mining", "hunting", "gathering", "forestry")
RGO_COST_MODIFIERS = {
    method: f"expand_rgo_{method}_cost_modifier" for method in RGO_METHODS
}
RGO_BUILDING_COST_GROUPS = {
    method: f"pp_rgo_{method}_building_cost_group" for method in RGO_METHODS
}
RGO_REDIRECT_OBJECTIVE = (
    "redirect vanilla RGO expansion cost efficiency into Prosper or Perish "
    "raw-material building construction cost efficiency while neutralizing the "
    "original RGO expansion cost modifier"
)
RGO_COST_REDIRECT_FILE = "pp_rgo_building_cost_redirects.txt"
RGO_COST_REDIRECT_COLLECTIONS: tuple[tuple[str, str], ...] = (
    ("in_game", "advances"),
    ("in_game", "estate_privileges"),
    ("in_game", "gods"),
    ("in_game", "government_reforms"),
    ("in_game", "laws"),
    ("in_game", "parliament_issues"),
    ("in_game", "religions"),
    ("in_game", "religious_aspects"),
    ("in_game", "town_rights"),
    ("main_menu", "static_modifiers"),
)
# The RGO expansion-cost modifier is intentionally neutralized by the generated
# redirect.  These advances need a replacement effect so they do not become
# empty unlocks when no PoP building-cost target exists for the RGO method.
RGO_REDIRECT_COMPENSATIONS: dict[
    tuple[str, str, str, tuple[str, ...]], tuple[tuple[str, float], ...]
] = {
    ("in_game", "advances", "dal_dalmatian_olive_pacts", ()): (
        ("global_olives_output_modifier", 0.2),
    ),
    ("in_game", "advances", "mining_tradition", ()): (
        ("global_iron_output_modifier", 0.1),
    ),
    ("in_game", "advances", "romagnol_the_agricultural_academies", ()): (
        ("global_wheat_output_modifier", 0.1),
        ("global_wine_output_modifier", 0.1),
    ),
    ("in_game", "advances", "sao_the_parnassus_mines_advance", ()): (
        ("global_iron_output_modifier", 0.1),
    ),
    ("in_game", "advances", "sardinian_the_industrial_transition", ()): (
        ("global_lead_output_modifier", 0.15),
    ),
    ("in_game", "advances", "serbian_mining", ()): (
        ("global_silver_output_modifier", 0.1),
        ("global_goods_gold_output_modifier", 0.1),
    ),
    ("in_game", "advances", "svn_the_alluvial_grant_lands", ()): (
        ("global_wheat_output_modifier", 0.15),
    ),
    ("in_game", "advances", "tra_the_national_mining_academy", ()): (
        ("global_goods_gold_output_modifier", 0.1),
        ("global_silver_output_modifier", 0.1),
        ("global_salt_output_modifier", 0.1),
    ),
    ("in_game", "advances", "tro_the_aqueducts_of_popovo_polje", ()): (
        ("global_wheat_output_modifier", 0.15),
    ),
    ("in_game", "advances", "vid_the_mining_grants", ()): (
        ("global_silver_output_modifier", 0.1),
        ("global_lead_output_modifier", 0.1),
        ("global_copper_output_modifier", 0.1),
    ),
    ("in_game", "advances", "zmw_experienced_cattle_herder", ()): (
        ("global_livestock_output_modifier", 0.1),
    ),
}

@dataclass(frozen=True)
class RgoCostAssignment:
    scope: str
    collection: str
    path: tuple[str, ...]
    method: str
    modifier: str
    value: float
    source_file: str
    source_line: int


@dataclass(frozen=True)
class RgoBuildingCostTarget:
    building: str
    price_key: str
    modifier_key: str
    methods: tuple[str, ...]
    source_file: str
    source_line: int


@dataclass(frozen=True)
class RgoBuildingClassification:
    priced_targets: tuple[RgoBuildingCostTarget, ...]
    unpriced_buildings: Mapping[str, tuple[str, ...]]
    unclassified_price_buildings: Mapping[str, str]

    def modifiers_by_method(self) -> dict[str, tuple[str, ...]]:
        grouped: dict[str, list[str]] = {method: [] for method in RGO_METHODS}
        for target in self.priced_targets:
            for method in target.methods:
                grouped[method].append(target.modifier_key)
        return {
            method: tuple(sorted(set(modifiers)))
            for method, modifiers in grouped.items()
        }


@dataclass(frozen=True)
class RgoCostRedirectResult:
    assignments: tuple[RgoCostAssignment, ...]
    classification: RgoBuildingClassification
    generated_files: tuple[Path, ...]
    patch_count: int


def write_rgo_cost_redirects(
    *,
    repo: Path,
    mod_root: Path,
    load_order_path: Path,
    profile_name: str,
) -> RgoCostRedirectResult:
    """Write generated redirect files for active RGO cost modifiers."""

    profile = load_profile(profile_name, load_order_path)
    assignments = collect_active_rgo_cost_assignments(profile)
    classification = classify_pop_rgo_building_cost_targets(profile, mod_root)
    generated_files, patch_count = write_rgo_cost_redirect_files(
        mod_root=mod_root,
        assignments=assignments,
        classification=classification,
        profile=profile,
    )
    return RgoCostRedirectResult(
        assignments=tuple(assignments),
        classification=classification,
        generated_files=tuple(generated_files),
        patch_count=patch_count,
    )


def collect_active_rgo_cost_assignments(
    profile: DataProfile,
    *,
    collections: Iterable[tuple[str, str]] = RGO_COST_REDIRECT_COLLECTIONS,
) -> list[RgoCostAssignment]:
    """Find active expand_rgo_*_cost_modifier values in merged game data.

    Entries generated by this module are ignored so finalized mod files remain
    idempotent inputs to later finalize and audit runs.
    """

    assignments: list[RgoCostAssignment] = []
    for scope, collection in collections:
        merged = load_merged_directory(profile, collection, scope=scope)
        for entry in merged.entries:
            block = _assignment_source_block(entry)
            if block is None:
                continue
            assignments.extend(
                _walk_cost_assignments(
                    block,
                    scope=scope,
                    collection=collection,
                    path=(entry.key,),
                )
            )
    return assignments


def classify_pop_rgo_building_cost_targets(
    profile: DataProfile,
    mod_root: Path,
) -> RgoBuildingClassification:
    raw_material_methods = _raw_material_methods(profile)
    priced_keys = _pp_price_keys(mod_root)
    targets: list[RgoBuildingCostTarget] = []
    unpriced: dict[str, tuple[str, ...]] = {}
    unclassified_priced: dict[str, str] = {}

    for entry in load_merged_directory(profile, "building_types").entries:
        if not isinstance(entry.value, CList) or not _is_pop_owned_entry(entry):
            continue
        methods = _classify_building_methods(entry.key, entry.value, raw_material_methods)
        price_key = _scalar_string(_last_value(entry.value, "price"))
        if methods and price_key and price_key in priced_keys:
            targets.append(
                RgoBuildingCostTarget(
                    building=entry.key,
                    price_key=price_key,
                    modifier_key=f"{price_key}_cost_modifier",
                    methods=tuple(sorted(methods)),
                    source_file=entry.source_file,
                    source_line=entry.source_line,
                )
            )
        elif methods:
            unpriced[entry.key] = tuple(sorted(methods))
        elif price_key and price_key.startswith("pp_"):
            unclassified_priced[entry.key] = price_key

    return RgoBuildingClassification(
        priced_targets=tuple(sorted(targets, key=lambda target: target.modifier_key)),
        unpriced_buildings=dict(sorted(unpriced.items())),
        unclassified_price_buildings=dict(sorted(unclassified_priced.items())),
    )


def write_rgo_cost_redirect_files(
    *,
    mod_root: Path,
    assignments: Iterable[RgoCostAssignment],
    classification: RgoBuildingClassification,
    profile: DataProfile | None = None,
    collections: Iterable[tuple[str, str]] = RGO_COST_REDIRECT_COLLECTIONS,
) -> tuple[list[Path], int]:
    modifiers_by_method = classification.modifiers_by_method()
    grouped: dict[tuple[str, str, str], dict[tuple[str, ...], list[RgoCostAssignment]]] = (
        defaultdict(lambda: defaultdict(list))
    )
    for assignment in assignments:
        patch_key = (assignment.scope, assignment.collection, assignment.path[0])
        grouped[patch_key][assignment.path[1:-1]].append(assignment)

    collection_blocks: dict[tuple[str, str], list[str]] = defaultdict(list)
    patch_count = 0
    for (scope, collection, top_key), patches_by_path in sorted(grouped.items()):
        if collection == "laws":
            if profile is None:
                raise ValueError("profile is required to generate law cost redirects")
            collection_blocks[(scope, collection)].extend(
                _render_law_replacement_block(
                    profile=profile,
                    scope=scope,
                    collection=collection,
                    top_key=top_key,
                    patches_by_path=patches_by_path,
                    modifiers_by_method=modifiers_by_method,
                )
            )
            collection_blocks[(scope, collection)].append("")
            patch_count += len(patches_by_path)
            continue

        body: list[str] = []
        for path, patch_assignments in sorted(patches_by_path.items()):
            leaf_entries: list[tuple[str, float]] = []
            for assignment in patch_assignments:
                leaf_entries.append((RGO_COST_MODIFIERS[assignment.method], -assignment.value))
                for modifier_key in modifiers_by_method.get(assignment.method, ()):
                    leaf_entries.append((modifier_key, assignment.value))
            leaf_entries.extend(
                RGO_REDIRECT_COMPENSATIONS.get((scope, collection, top_key, path), ())
            )
            if leaf_entries:
                _append_nested_patch(body, path, leaf_entries, indent=1)
                patch_count += 1
        if not body:
            continue
        block = [f"TRY_INJECT:{top_key} = {{", *body, "}", ""]
        collection_blocks[(scope, collection)].extend(block)

    generated_files: list[Path] = []
    for scope, collection in collections:
        path = mod_root / scope / "common" / collection / RGO_COST_REDIRECT_FILE
        blocks = collection_blocks.get((scope, collection), [])
        if not blocks:
            if path.exists():
                path.unlink()
            continue
        lines = [
            "# Prosper or Perish - generated RGO building cost redirects.",
            f"# Objective: {RGO_REDIRECT_OBJECTIVE}.",
            "# Generated by ppc finalize from active expand_rgo_*_cost_modifier assignments.",
            "# Do not edit by hand.",
            "",
            *blocks,
        ]
        text = "\n".join(lines).rstrip() + "\n"
        path.parent.mkdir(parents=True, exist_ok=True)
        _write_text_if_changed(path, text)
        generated_files.append(path)

    return generated_files, patch_count


def _assignment_source_block(entry: MergedEntry) -> CList | None:
    if not isinstance(entry.value, CList):
        return None
    if not (
        entry.source_mode in {"REPLACE", "TRY_REPLACE"}
        and _is_generated_redirect_path(entry.source_file)
    ):
        return entry.value

    source = _replacement_source_record(entry)
    if source is None:
        return entry.value
    parsed = _entry_from_source_record(source, entry.key)
    if parsed is None or not isinstance(parsed.value, CList):
        return entry.value
    return parsed.value


def _render_law_replacement_block(
    *,
    profile: DataProfile,
    scope: str,
    collection: str,
    top_key: str,
    patches_by_path: Mapping[tuple[str, ...], list[RgoCostAssignment]],
    modifiers_by_method: Mapping[str, tuple[str, ...]],
) -> list[str]:
    merged_entry = _merged_entry_for_key(profile, scope, collection, top_key)
    source = _replacement_source_record(merged_entry)
    if source is None:
        raise ValueError(f"Cannot find source law group for {scope}/{collection}/{top_key}")

    source_path = Path(source.file)
    source_lines = source_path.read_text(encoding="utf-8-sig").splitlines()
    start_index = source.line - 1
    end_index = _find_block_end(source_lines, start_index)
    block_lines = list(source_lines[start_index : end_index + 1])
    block_lines[0] = _replace_top_level_key(block_lines[0], top_key)

    replacements: dict[int, list[str]] = {}
    for patch_assignments in patches_by_path.values():
        for assignment in patch_assignments:
            if Path(assignment.source_file) != source_path:
                raise ValueError(
                    "Cannot rewrite law redirect across source files: "
                    f"{top_key} is in {source_path}, assignment is in {assignment.source_file}"
                )
            line_index = assignment.source_line - source.line
            try:
                source_line = block_lines[line_index]
            except IndexError as error:
                raise ValueError(
                    f"Source line {assignment.source_line} for {assignment.modifier} "
                    f"is outside {source_path}:{source.line}"
                ) from error
            if assignment.modifier not in source_line:
                raise ValueError(
                    f"Expected {assignment.modifier} at {source_path}:{assignment.source_line}"
                )
            indent = re.match(r"\s*", source_line).group(0)
            replacements[line_index] = [
                f"{indent}{modifier_key} = {_format_number(assignment.value)}"
                for modifier_key in modifiers_by_method.get(assignment.method, ())
            ]

    rendered: list[str] = []
    for index, line in enumerate(block_lines):
        if index in replacements:
            rendered.extend(replacements[index])
        else:
            rendered.append(line)
    return rendered


def _merged_entry_for_key(
    profile: DataProfile,
    scope: str,
    collection: str,
    top_key: str,
) -> MergedEntry:
    for entry in load_merged_directory(profile, collection, scope=scope).entries:
        if entry.key == top_key:
            return entry
    raise ValueError(f"Missing merged entry for {scope}/{collection}/{top_key}")


def _replacement_source_record(entry: MergedEntry) -> SourceRecord | None:
    for source in reversed(entry.source_history):
        if _is_generated_redirect_path(source.file):
            continue
        if source.mode in {"CREATE", "REPLACE", "REPLACE_OR_CREATE", "TRY_REPLACE"}:
            return source
    return None


def _entry_from_source_record(source: SourceRecord, top_key: str) -> CEntry | None:
    for entry in parse_file(Path(source.file)).entries:
        if _entry_key(entry.key) == top_key and entry.location.line == source.line:
            return entry
    return None


def _entry_key(raw_key: str) -> str:
    if ":" not in raw_key:
        return raw_key
    return raw_key.split(":", 1)[1]


def _is_generated_redirect_path(path: str | Path) -> bool:
    return Path(path).name == RGO_COST_REDIRECT_FILE


def _find_block_end(lines: list[str], start_index: int) -> int:
    depth = 0
    seen_open = False
    for index in range(start_index, len(lines)):
        code = lines[index].split("#", 1)[0]
        depth += code.count("{") - code.count("}")
        if "{" in code:
            seen_open = True
        if seen_open and depth == 0:
            return index
    raise ValueError(f"Could not find block end after line {start_index + 1}")


def _replace_top_level_key(line: str, top_key: str) -> str:
    pattern = rf"^(\s*)(?:[A-Z_]+:)?{re.escape(top_key)}\s*=\s*\{{"
    replacement = rf"\1TRY_REPLACE:{top_key} = {{"
    replaced = re.sub(pattern, replacement, line, count=1)
    if replaced == line:
        return f"TRY_REPLACE:{top_key} = {{"
    return replaced


def _walk_cost_assignments(
    block: CList,
    *,
    scope: str,
    collection: str,
    path: tuple[str, ...],
) -> list[RgoCostAssignment]:
    assignments: list[RgoCostAssignment] = []
    for entry in block.entries:
        if _is_generated_entry(entry) and not isinstance(entry.value, CList):
            continue
        method = _method_for_modifier(entry.key)
        if method is not None:
            value = _scalar_float(entry.value)
            if value is not None:
                assignments.append(
                    RgoCostAssignment(
                        scope=scope,
                        collection=collection,
                        path=(*path, entry.key),
                        method=method,
                        modifier=entry.key,
                        value=value,
                        source_file=str(entry.location.path or ""),
                        source_line=entry.location.line,
                    )
                )
            continue
        if isinstance(entry.value, CList):
            assignments.extend(
                _walk_cost_assignments(
                    entry.value,
                    scope=scope,
                    collection=collection,
                    path=(*path, entry.key),
                )
            )
    return assignments


def _append_nested_patch(
    lines: list[str],
    path: tuple[str, ...],
    leaf_entries: list[tuple[str, float]],
    *,
    indent: int,
) -> None:
    if not path:
        prefix = "\t" * indent
        for key, value in leaf_entries:
            lines.append(f"{prefix}{key} = {_format_number(value)}")
        return

    key, *rest = path
    prefix = "\t" * indent
    lines.append(f"{prefix}{key} = {{")
    _append_nested_patch(lines, tuple(rest), leaf_entries, indent=indent + 1)
    lines.append(f"{prefix}}}")


def _classify_building_methods(
    building_key: str,
    block: CList,
    raw_material_methods: Mapping[str, str],
) -> set[str]:
    produced_methods = _methods_for_goods(_produced_goods(block), raw_material_methods)
    if produced_methods:
        return produced_methods

    gate_methods = _methods_for_goods(_raw_material_gate_goods(block), raw_material_methods)
    if gate_methods:
        return gate_methods

    return set()


def _raw_material_methods(profile: DataProfile) -> dict[str, str]:
    methods: dict[str, str] = {}
    for entry in load_merged_directory(profile, "goods").entries:
        if not isinstance(entry.value, CList):
            continue
        category = _scalar_string(_last_value(entry.value, "category"))
        method = _scalar_string(_last_value(entry.value, "method")) or "farming"
        if category == "raw_material" and method in RGO_METHODS:
            methods[entry.key] = method
    return methods


def _produced_goods(block: CList) -> set[str]:
    goods: set[str] = set()
    for entry in _walk_entries(block):
        if entry.key == "produced":
            good = _goods_key(entry.value)
            if good:
                goods.add(good)
    return goods


def _raw_material_gate_goods(block: CList) -> set[str]:
    goods: set[str] = set()
    for entry in _walk_entries(block):
        if entry.key == "raw_material":
            good = _goods_key(entry.value)
            if good:
                goods.add(good)
    return goods


def _walk_entries(block: CList) -> Iterable[CEntry]:
    for entry in block.entries:
        yield entry
        if isinstance(entry.value, CList):
            yield from _walk_entries(entry.value)
    for item in block.items:
        if isinstance(item, CList):
            yield from _walk_entries(item)


def _methods_for_goods(goods: Iterable[str], raw_material_methods: Mapping[str, str]) -> set[str]:
    return {
        raw_material_methods[good]
        for good in goods
        if raw_material_methods.get(good) in RGO_METHODS
    }


def _goods_key(value: Value | None) -> str | None:
    scalar = _scalar_string(value)
    if scalar is None:
        return None
    if scalar.startswith("goods:"):
        return scalar.split(":", 1)[1]
    return scalar


def _is_pop_owned_entry(entry: MergedEntry) -> bool:
    if entry.source_mod:
        return True
    return any(record.mod_name for record in entry.source_history)


def _is_generated_entry(entry: CEntry) -> bool:
    return Path(str(entry.location.path or "")).name == RGO_COST_REDIRECT_FILE


def _method_for_modifier(key: str) -> str | None:
    for method, modifier in RGO_COST_MODIFIERS.items():
        if key == modifier:
            return method
    return None


def _last_value(block: CList, key: str) -> Value | None:
    values = block.values(key)
    return values[-1] if values else None


def _scalar_string(value: Value | None) -> str | None:
    if isinstance(value, CList) or value is None:
        return None
    return str(value)


def _scalar_float(value: Value | None) -> float | None:
    if isinstance(value, bool) or isinstance(value, CList) or value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    return None


def _pp_price_keys(mod_root: Path) -> set[str]:
    prices_root = mod_root / "in_game" / "common" / "prices"
    if not prices_root.is_dir():
        return set()
    keys: set[str] = set()
    for path in sorted(prices_root.glob("pp_*.txt")):
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        for match in re.finditer(r"(?m)^\s*(pp_[A-Za-z0-9_]+_price)\s*=", text):
            keys.add(match.group(1))
    return keys


def _format_number(value: float) -> str:
    if abs(value) < 1e-12:
        return "0"
    return f"{value:.12g}"


def _write_text_if_changed(path: Path, text: str) -> None:
    if path.exists() and path.read_text(encoding="utf-8-sig") == text:
        return
    path.write_text(text, encoding="utf-8-sig")
