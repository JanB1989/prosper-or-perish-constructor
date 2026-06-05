"""Audit Prosper or Perish references against two vanilla EU5 revisions."""

from __future__ import annotations

import csv
import difflib
import hashlib
import html
import io
import json
import re
import subprocess
import tarfile
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from eu5gameparser.clausewitz.parser import parse_file, parse_text
from eu5gameparser.clausewitz.serializer import normalized_value
from eu5gameparser.clausewitz.syntax import CEntry, CList, Value
from eu5gameparser.load_order import LoadOrderConfig


COMMON_SCOPES = ("in_game", "main_menu")
PATCH_TARGET_MODES = {
    "REPLACE",
    "TRY_REPLACE",
    "INJECT",
    "TRY_INJECT",
}
CONDITIONAL_PATCH_TARGET_MODES = {
    "CREATE",
    "REPLACE_OR_CREATE",
    "INJECT_OR_CREATE",
}
IMPACT_STATUSES = {"changed", "added", "removed"}
LARGE_MOD_FILE_BYTES = 1_000_000
IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
REFERENCE_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
REFERENCE_PREFIXES = {
    "building",
    "building_type",
    "concept",
    "country",
    "culture",
    "define",
    "flag",
    "global_var",
    "goods",
    "modifier",
    "scope",
    "script_value",
    "static_modifier",
    "trigger",
    "var",
}
TEXT_LIKE_ENTRY_KEYS = {
    "desc",
    "description",
    "display_name",
    "loc",
    "localization",
    "raw_text",
    "text",
    "title",
}


@dataclass(frozen=True, order=True)
class SymbolId:
    scope: str
    collection: str
    key: str

    @property
    def qualified(self) -> str:
        return f"{self.scope}/{self.collection}/{self.key}"


@dataclass(frozen=True)
class SymbolDefinition:
    symbol: SymbolId
    definition: dict[str, Any]
    source_path: str
    source_line: int
    duplicate_count: int = 0

    @property
    def source(self) -> str:
        return f"{self.source_path}:{self.source_line}"


@dataclass(frozen=True)
class ModReference:
    symbol_text: str
    source_path: str
    source_line: int
    kind: str
    context: str

    @property
    def source(self) -> str:
        return f"{self.source_path}:{self.source_line}"


@dataclass(frozen=True)
class DependencyRecord:
    symbol: SymbolId
    references: tuple[ModReference, ...]
    old: SymbolDefinition | None
    new: SymbolDefinition | None
    status: str
    diff: str


@dataclass(frozen=True)
class AuditSummary:
    old_ref: str
    new_ref: str
    output_dir: Path
    index_html: Path
    changed_csv: Path
    all_csv: Path
    changed_json: Path
    dependency_count: int
    changed_count: int
    added_count: int
    removed_count: int
    unchanged_count: int
    missing_both_count: int
    warning_count: int


@dataclass
class _Catalog:
    definitions: dict[SymbolId, SymbolDefinition] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


@dataclass
class _ModDependencyScan:
    references: dict[SymbolId, list[ModReference]] = field(default_factory=dict)
    unresolved_references: dict[str, list[ModReference]] = field(default_factory=dict)
    conditional_targets: list[tuple[SymbolId, ModReference]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def run_update_audit(
    *,
    repo: Path,
    project: Path,
    load_order_path: Path,
    old_ref: str,
    new_ref: str,
    output_dir: Path | None = None,
) -> AuditSummary:
    """Run the EU5 update audit and write HTML, CSV, and JSON outputs."""

    load_order = LoadOrderConfig.load(load_order_path)
    vanilla_root = load_order.vanilla_root
    mod_root = _project_mod_root(repo, project)
    _require_git_ref(vanilla_root, old_ref)
    _require_git_ref(vanilla_root, new_ref)

    old_catalog = _load_vanilla_catalog(vanilla_root, old_ref)
    new_catalog = _load_vanilla_catalog(vanilla_root, new_ref)
    all_symbols = set(old_catalog.definitions) | set(new_catalog.definitions)
    symbols_by_key = _symbols_by_key(all_symbols)

    scan = _scan_mod_dependencies(
        repo=repo,
        mod_root=mod_root,
        old_catalog=old_catalog.definitions,
        new_catalog=new_catalog.definitions,
        symbols_by_key=symbols_by_key,
    )
    dependencies = _build_dependency_records(
        references=scan.references,
        old_catalog=old_catalog.definitions,
        new_catalog=new_catalog.definitions,
    )

    if output_dir is None:
        output_dir = repo / "reports" / "eu5_update_audit" / f"{_safe_ref(old_ref)}..{_safe_ref(new_ref)}"
    output_dir.mkdir(parents=True, exist_ok=True)

    warnings = [*old_catalog.warnings, *new_catalog.warnings, *scan.warnings]
    all_rows = [_dependency_row(record, repo=repo) for record in dependencies]
    changed_rows = [row for row in all_rows if row["status"] in IMPACT_STATUSES]

    all_csv = output_dir / "all_dependencies.csv"
    changed_csv = output_dir / "changed_dependencies.csv"
    changed_json = output_dir / "changed_dependencies.json"
    index_html = output_dir / "index.html"

    _write_csv(all_csv, all_rows)
    _write_csv(changed_csv, changed_rows)
    _write_json(changed_json, changed_rows, warnings=warnings, old_ref=old_ref, new_ref=new_ref)
    _write_html(index_html, all_rows, warnings=warnings, old_ref=old_ref, new_ref=new_ref)

    counts = _status_counts(dependencies)
    return AuditSummary(
        old_ref=old_ref,
        new_ref=new_ref,
        output_dir=output_dir,
        index_html=index_html,
        changed_csv=changed_csv,
        all_csv=all_csv,
        changed_json=changed_json,
        dependency_count=len(dependencies),
        changed_count=counts.get("changed", 0),
        added_count=counts.get("added", 0),
        removed_count=counts.get("removed", 0),
        unchanged_count=counts.get("unchanged", 0),
        missing_both_count=counts.get("missing_both", 0),
        warning_count=len(warnings),
    )


def _project_mod_root(repo: Path, project: Path) -> Path:
    with project.open("rb") as handle:
        config = tomllib.load(handle)
    configured = config.get("project", {}).get("mod_root")
    if not isinstance(configured, str):
        raise SystemExit(f"Missing [project].mod_root in {project}")
    mod_root = Path(configured)
    return mod_root if mod_root.is_absolute() else repo / mod_root


def _require_git_ref(vanilla_root: Path, ref: str) -> None:
    result = subprocess.run(
        ["git", "-C", str(vanilla_root), "rev-parse", "--verify", f"{ref}^{{commit}}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(f"Vanilla EU5 Git ref not found: {ref}")


def _load_vanilla_catalog(vanilla_root: Path, ref: str) -> _Catalog:
    catalog = _Catalog()
    for path, text in _git_common_text_blobs(vanilla_root, ref):
        scope, collection = _common_scope_and_collection(path)
        if scope is None or collection is None:
            continue
        try:
            document = parse_text(text, Path(path))
        except ValueError as error:
            catalog.warnings.append(f"{ref}: skipped unparsable {path}: {error}")
            continue
        for entry in document.entries:
            mode, key = _entry_mode(entry.key)
            symbol = SymbolId(scope=scope, collection=collection, key=key)
            duplicate_count = 0
            existing = catalog.definitions.get(symbol)
            if existing is not None:
                duplicate_count = existing.duplicate_count + 1
            catalog.definitions[symbol] = SymbolDefinition(
                symbol=symbol,
                definition=_normalized_entry(entry, mode=mode),
                source_path=path,
                source_line=entry.location.line,
                duplicate_count=duplicate_count,
            )
    return catalog


def _git_common_text_blobs(vanilla_root: Path, ref: str) -> list[tuple[str, str]]:
    result = subprocess.run(
        [
            "git",
            "-C",
            str(vanilla_root),
            "archive",
            "--format=tar",
            ref,
            "game/in_game/common",
            "game/main_menu/common",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    blobs: list[tuple[str, str]] = []
    with tarfile.open(fileobj=io.BytesIO(result.stdout), mode="r:") as archive:
        for member in archive.getmembers():
            if not member.isfile():
                continue
            path = member.name
            if not path.endswith(".txt"):
                continue
            if Path(path).name.lower() == "readme.txt":
                continue
            extracted = archive.extractfile(member)
            if extracted is None:
                continue
            text = extracted.read().decode("utf-8-sig", errors="surrogateescape")
            blobs.append((path, text))
    return blobs


def _common_scope_and_collection(path: str) -> tuple[str | None, str | None]:
    parts = Path(path).parts
    if len(parts) < 5 or parts[0] != "game" or parts[2] != "common":
        return None, None
    scope = parts[1]
    if scope not in COMMON_SCOPES:
        return None, None
    return scope, parts[3]


def _normalized_entry(entry: CEntry, *, mode: str) -> dict[str, Any]:
    return {
        "mode": mode,
        "op": entry.op,
        "value": normalized_value(entry.value),
    }


def _entry_mode(raw_key: str) -> tuple[str, str]:
    if ":" not in raw_key:
        return "CREATE", raw_key
    mode, key = raw_key.split(":", 1)
    return mode.strip().upper(), key


def _symbols_by_key(symbols: Iterable[SymbolId]) -> dict[str, set[SymbolId]]:
    by_key: dict[str, set[SymbolId]] = {}
    for symbol in symbols:
        by_key.setdefault(symbol.key, set()).add(symbol)
    return by_key


def _scan_mod_dependencies(
    *,
    repo: Path,
    mod_root: Path,
    old_catalog: dict[SymbolId, SymbolDefinition],
    new_catalog: dict[SymbolId, SymbolDefinition],
    symbols_by_key: dict[str, set[SymbolId]],
) -> _ModDependencyScan:
    scan = _ModDependencyScan()
    for scope in COMMON_SCOPES:
        root = mod_root / scope / "common"
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.txt")):
            if path.name.lower() == "readme.txt":
                continue
            try:
                collection = path.relative_to(root).parts[0]
            except IndexError:
                continue
            if path.stat().st_size > LARGE_MOD_FILE_BYTES:
                _scan_large_mod_file(
                    scan=scan,
                    path=path,
                    repo=repo,
                    scope=scope,
                    collection=collection,
                    old_catalog=old_catalog,
                    new_catalog=new_catalog,
                    symbols_by_key=symbols_by_key,
                )
                continue
            try:
                document = parse_file(path)
            except ValueError as error:
                scan.warnings.append(f"mod: skipped unparsable {path}: {error}")
                continue
            relative_path = _display_path(path, repo)
            for entry in document.entries:
                _scan_top_level_entry(
                    scan=scan,
                    scope=scope,
                    collection=collection,
                    entry=entry,
                    relative_path=relative_path,
                    old_catalog=old_catalog,
                    new_catalog=new_catalog,
                    symbols_by_key=symbols_by_key,
                )
    return scan


def _scan_top_level_entry(
    *,
    scan: _ModDependencyScan,
    scope: str,
    collection: str,
    entry: CEntry,
    relative_path: str,
    old_catalog: dict[SymbolId, SymbolDefinition],
    new_catalog: dict[SymbolId, SymbolDefinition],
    symbols_by_key: dict[str, set[SymbolId]],
) -> None:
    mode, key = _entry_mode(entry.key)
    symbol = SymbolId(scope=scope, collection=collection, key=key)
    reference = ModReference(
        symbol_text=key,
        source_path=relative_path,
        source_line=entry.location.line,
        kind="patch_target" if mode in PATCH_TARGET_MODES else "create_target",
        context=mode,
    )
    if mode in PATCH_TARGET_MODES:
        for target_symbol in _target_symbols_for_entry(
            scope=scope,
            collection=collection,
            key=key,
            old_catalog=old_catalog,
            new_catalog=new_catalog,
            symbols_by_key=symbols_by_key,
            fallback_to_declared=True,
        ):
            _add_reference(scan.references, target_symbol, reference)
    elif mode in CONDITIONAL_PATCH_TARGET_MODES:
        target_symbols = _target_symbols_for_entry(
            scope=scope,
            collection=collection,
            key=key,
            old_catalog=old_catalog,
            new_catalog=new_catalog,
            symbols_by_key=symbols_by_key,
            fallback_to_declared=False,
        )
        if target_symbols:
            for target_symbol in target_symbols:
                _add_reference(scan.references, target_symbol, reference)
        else:
            scan.conditional_targets.append((symbol, reference))

    _collect_value_references(
        scan=scan,
        value=entry.value,
        relative_path=relative_path,
        source_line=entry.location.line,
        parent_key=key,
        symbols_by_key=symbols_by_key,
    )


def _scan_large_mod_file(
    *,
    scan: _ModDependencyScan,
    path: Path,
    repo: Path,
    scope: str,
    collection: str,
    old_catalog: dict[SymbolId, SymbolDefinition],
    new_catalog: dict[SymbolId, SymbolDefinition],
    symbols_by_key: dict[str, set[SymbolId]],
) -> None:
    relative_path = _display_path(path, repo)
    depth = 0
    top_level_entry = re.compile(
        r"^\s*(?P<raw>(?:(?P<mode>[A-Z_]+):)?[A-Za-z_][A-Za-z0-9_]*)\s*[<>=!]*="
    )
    try:
        lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    except OSError as error:
        scan.warnings.append(f"mod: skipped unreadable {path}: {error}")
        return

    for line_number, line in enumerate(lines, start=1):
        content = line.split("#", 1)[0]
        match = top_level_entry.match(content) if depth == 0 else None
        if match:
            mode, key = _entry_mode(match.group("raw"))
            symbol = SymbolId(scope=scope, collection=collection, key=key)
            reference = ModReference(
                symbol_text=key,
                source_path=relative_path,
                source_line=line_number,
                kind="patch_target" if mode in PATCH_TARGET_MODES else "create_target",
                context=mode,
            )
            if mode in PATCH_TARGET_MODES:
                for target_symbol in _target_symbols_for_entry(
                    scope=scope,
                    collection=collection,
                    key=key,
                    old_catalog=old_catalog,
                    new_catalog=new_catalog,
                    symbols_by_key=symbols_by_key,
                    fallback_to_declared=True,
                ):
                    _add_reference(scan.references, target_symbol, reference)
            elif mode in CONDITIONAL_PATCH_TARGET_MODES:
                for target_symbol in _target_symbols_for_entry(
                    scope=scope,
                    collection=collection,
                    key=key,
                    old_catalog=old_catalog,
                    new_catalog=new_catalog,
                    symbols_by_key=symbols_by_key,
                    fallback_to_declared=False,
                ):
                    _add_reference(scan.references, target_symbol, reference)

        for token in REFERENCE_TOKEN_RE.findall(content):
            _resolve_symbol_text(
                scan=scan,
                symbol_text=token,
                reference=ModReference(
                    symbol_text=token,
                    source_path=relative_path,
                    source_line=line_number,
                    kind="lexical",
                    context=collection,
                ),
                symbols_by_key=symbols_by_key,
            )
        depth += content.count("{") - content.count("}")
        if depth < 0:
            depth = 0


def _target_symbols_for_entry(
    *,
    scope: str,
    collection: str,
    key: str,
    old_catalog: dict[SymbolId, SymbolDefinition],
    new_catalog: dict[SymbolId, SymbolDefinition],
    symbols_by_key: dict[str, set[SymbolId]],
    fallback_to_declared: bool,
) -> list[SymbolId]:
    declared = SymbolId(scope=scope, collection=collection, key=key)
    if declared in old_catalog or declared in new_catalog:
        return [declared]

    cross_scope_matches = sorted(
        symbol for symbol in symbols_by_key.get(key, set()) if symbol.collection == collection
    )
    if cross_scope_matches:
        return cross_scope_matches
    if fallback_to_declared:
        return [declared]
    return []


def _collect_entry_references(
    *,
    scan: _ModDependencyScan,
    entry: CEntry,
    relative_path: str,
    symbols_by_key: dict[str, set[SymbolId]],
) -> None:
    mode, key = _entry_mode(entry.key)
    _resolve_symbol_text(
        scan=scan,
        symbol_text=key,
        reference=ModReference(
            symbol_text=key,
            source_path=relative_path,
            source_line=entry.location.line,
            kind="entry_key",
            context=mode,
        ),
        symbols_by_key=symbols_by_key,
    )
    _collect_value_references(
        scan=scan,
        value=entry.value,
        relative_path=relative_path,
        source_line=entry.location.line,
        parent_key=key,
        symbols_by_key=symbols_by_key,
    )


def _collect_value_references(
    *,
    scan: _ModDependencyScan,
    value: Value,
    relative_path: str,
    source_line: int,
    parent_key: str,
    symbols_by_key: dict[str, set[SymbolId]],
) -> None:
    if isinstance(value, CList):
        for item in value.items:
            _collect_value_references(
                scan=scan,
                value=item,
                relative_path=relative_path,
                source_line=source_line,
                parent_key=parent_key,
                symbols_by_key=symbols_by_key,
            )
        for entry in value.entries:
            _collect_entry_references(
                scan=scan,
                entry=entry,
                relative_path=relative_path,
                symbols_by_key=symbols_by_key,
            )
        return
    if isinstance(value, str):
        for token in _reference_tokens(value, parent_key=parent_key):
            _resolve_symbol_text(
                scan=scan,
                symbol_text=token,
                reference=ModReference(
                    symbol_text=token,
                    source_path=relative_path,
                    source_line=source_line,
                    kind="scalar",
                    context=parent_key,
                ),
                symbols_by_key=symbols_by_key,
            )


def _reference_tokens(value: str, *, parent_key: str) -> set[str]:
    if parent_key in TEXT_LIKE_ENTRY_KEYS:
        return set()
    if not value or value.startswith("$") or value.startswith("["):
        return set()
    if any(separator in value for separator in ("/", "\\", " ")):
        return set()
    if IDENTIFIER_RE.match(value):
        return {value}
    if ":" in value:
        prefix, _, tail = value.partition(":")
        tokens = {token for token in REFERENCE_TOKEN_RE.findall(tail) if IDENTIFIER_RE.match(token)}
        if prefix in REFERENCE_PREFIXES:
            return tokens
        return tokens
    if "|" in value:
        return {token for token in REFERENCE_TOKEN_RE.findall(value) if IDENTIFIER_RE.match(token)}
    return set()


def _resolve_symbol_text(
    *,
    scan: _ModDependencyScan,
    symbol_text: str,
    reference: ModReference,
    symbols_by_key: dict[str, set[SymbolId]],
) -> None:
    symbols = symbols_by_key.get(symbol_text)
    if not symbols:
        return
    for symbol in symbols:
        _add_reference(scan.references, symbol, reference)


def _add_reference(
    references: dict[SymbolId, list[ModReference]],
    symbol: SymbolId,
    reference: ModReference,
) -> None:
    references.setdefault(symbol, []).append(reference)


def _build_dependency_records(
    *,
    references: dict[SymbolId, list[ModReference]],
    old_catalog: dict[SymbolId, SymbolDefinition],
    new_catalog: dict[SymbolId, SymbolDefinition],
) -> list[DependencyRecord]:
    records: list[DependencyRecord] = []
    symbols = set(references)
    symbols.update(symbol for symbol in new_catalog if symbol not in old_catalog)
    symbols.update(symbol for symbol in old_catalog if symbol not in new_catalog)
    for symbol in sorted(symbols):
        old = old_catalog.get(symbol)
        new = new_catalog.get(symbol)
        status = _dependency_status(old, new)
        records.append(
            DependencyRecord(
                symbol=symbol,
                references=tuple(sorted(references.get(symbol, ()), key=_reference_sort_key)),
                old=old,
                new=new,
                status=status,
                diff=_definition_diff(old, new),
            )
        )
    return records


def _reference_sort_key(reference: ModReference) -> tuple[str, int, str, str]:
    return (reference.source_path, reference.source_line, reference.kind, reference.context)


def _dependency_status(old: SymbolDefinition | None, new: SymbolDefinition | None) -> str:
    if old is None and new is None:
        return "missing_both"
    if old is None:
        return "added"
    if new is None:
        return "removed"
    if old.definition != new.definition:
        return "changed"
    return "unchanged"


def _definition_diff(old: SymbolDefinition | None, new: SymbolDefinition | None) -> str:
    old_text = _definition_text(old)
    new_text = _definition_text(new)
    if old_text == new_text:
        return ""
    return "\n".join(
        difflib.unified_diff(
            old_text.splitlines(),
            new_text.splitlines(),
            fromfile="old",
            tofile="new",
            lineterm="",
        )
    )


def _definition_text(definition: SymbolDefinition | None) -> str:
    if definition is None:
        return ""
    mode = str(definition.definition.get("mode", "CREATE"))
    key = definition.symbol.key if mode == "CREATE" else f"{mode}:{definition.symbol.key}"
    op = str(definition.definition.get("op", "="))
    value = definition.definition.get("value")
    return f"{key} {op} {_render_normalized_value(value, indent=0)}"


def _render_normalized_value(value: Any, *, indent: int) -> str:
    if isinstance(value, dict) and "entries" in value and "items" in value:
        return _render_normalized_list(value, indent=indent)
    return _render_normalized_scalar(value)


def _render_normalized_list(value: dict[str, Any], *, indent: int) -> str:
    items = value.get("items", [])
    entries = value.get("entries", [])
    if not items and not entries:
        return "{}"

    lines = ["{"]
    base_indent = "\t" * indent
    child_indent = "\t" * (indent + 1)
    for item in items:
        rendered = _render_normalized_value(item, indent=indent + 1)
        lines.extend(f"{child_indent}{line}" for line in rendered.splitlines())
    for entry in entries:
        key = str(entry.get("key", ""))
        op = str(entry.get("op", "="))
        rendered = _render_normalized_value(entry.get("value"), indent=indent + 1)
        rendered_lines = rendered.splitlines()
        if len(rendered_lines) == 1:
            lines.append(f"{child_indent}{key} {op} {rendered_lines[0]}")
        else:
            lines.append(f"{child_indent}{key} {op} {rendered_lines[0]}")
            lines.extend(f"{child_indent}{line}" for line in rendered_lines[1:])
    lines.append(f"{base_indent}}}")
    return "\n".join(lines)


def _render_normalized_scalar(value: Any) -> str:
    if value is True:
        return "yes"
    if value is False:
        return "no"
    if isinstance(value, str):
        if value and re.match(r"^[A-Za-z0-9_./:+|'-]+$", value):
            return value
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _dependency_row(record: DependencyRecord, *, repo: Path) -> dict[str, str]:
    reference_kinds = sorted({reference.kind for reference in record.references})
    return {
        "status": record.status,
        "scope": record.symbol.scope,
        "collection": record.symbol.collection,
        "key": record.symbol.key,
        "qualified": record.symbol.qualified,
        "reference_kinds": ", ".join(reference_kinds),
        "mod_sources": _format_references(record.references),
        "old_source": "" if record.old is None else record.old.source,
        "new_source": "" if record.new is None else record.new.source,
        "old_hash": "" if record.old is None else _definition_hash(record.old.definition),
        "new_hash": "" if record.new is None else _definition_hash(record.new.definition),
        "old_duplicate_count": "" if record.old is None else str(record.old.duplicate_count),
        "new_duplicate_count": "" if record.new is None else str(record.new.duplicate_count),
        "diff": record.diff,
        "old_definition": _definition_text(record.old),
        "new_definition": _definition_text(record.new),
    }


def _format_references(references: tuple[ModReference, ...]) -> str:
    grouped: dict[tuple[str, str, str], list[int]] = {}
    for reference in references:
        grouped.setdefault(
            (reference.source_path, reference.kind, reference.context),
            [],
        ).append(reference.source_line)

    lines: list[str] = []
    for (source_path, kind, context), source_lines in sorted(grouped.items()):
        count = len(source_lines)
        first_line = min(source_lines)
        if count == 1:
            lines.append(f"{source_path}:{first_line} [{kind}; {context}]")
        else:
            lines.append(f"{source_path}:{first_line} [{kind}; {context}; count={count}]")
    return "\n".join(lines)


def _definition_hash(definition: dict[str, Any]) -> str:
    payload = json.dumps(definition, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]


def _status_counts(records: Iterable[DependencyRecord]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        counts[record.status] = counts.get(record.status, 0) + 1
    return counts


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = [
        "status",
        "scope",
        "collection",
        "key",
        "qualified",
        "reference_kinds",
        "mod_sources",
        "old_source",
        "new_source",
        "old_hash",
        "new_hash",
        "old_duplicate_count",
        "new_duplicate_count",
        "diff_line_count",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            csv_row = {field: row.get(field, "") for field in fieldnames}
            diff = row.get("diff", "")
            csv_row["diff_line_count"] = str(len(diff.splitlines()) if diff else 0)
            writer.writerow(csv_row)


def _write_json(
    path: Path,
    rows: list[dict[str, str]],
    *,
    warnings: list[str],
    old_ref: str,
    new_ref: str,
) -> None:
    payload = {
        "old_ref": old_ref,
        "new_ref": new_ref,
        "warnings": warnings,
        "dependencies": rows,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_html(
    path: Path,
    rows: list[dict[str, str]],
    *,
    warnings: list[str],
    old_ref: str,
    new_ref: str,
) -> None:
    collections = sorted({row["collection"] for row in rows})
    statuses = ["changed", "added", "removed", "unchanged", "missing_both"]
    kinds = sorted({kind.strip() for row in rows for kind in row["reference_kinds"].split(", ") if kind.strip()})
    summary = {
        "total": len(rows),
        "changed": sum(1 for row in rows if row["status"] == "changed"),
        "added": sum(1 for row in rows if row["status"] == "added"),
        "removed": sum(1 for row in rows if row["status"] == "removed"),
        "unchanged": sum(1 for row in rows if row["status"] == "unchanged"),
        "missing_both": sum(1 for row in rows if row["status"] == "missing_both"),
    }
    table_rows = "\n".join(_html_record(row) for row in rows)
    html_text = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>EU5 Update Audit {html.escape(old_ref)}..{html.escape(new_ref)}</title>
<style>
:root {{
  color-scheme: light;
  --border: #d9dee7;
  --border-strong: #b7c0ce;
  --muted: #667085;
  --panel: #f7f8fb;
  --panel-strong: #eef2f7;
  --text: #111827;
  --changed: #9a3412;
  --added: #166534;
  --removed: #991b1b;
}}
body {{
  margin: 0;
  font: 13px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  color: var(--text);
  background: #fff;
  overflow-x: hidden;
}}
header {{
  padding: 22px 28px 16px;
  border-bottom: 1px solid var(--border);
}}
h1 {{
  margin: 0 0 8px;
  font-size: 22px;
  font-weight: 700;
}}
.subtitle {{
  color: var(--muted);
}}
.summary {{
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 16px;
}}
.pill {{
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 5px 9px;
  background: var(--panel);
}}
.controls {{
  display: grid;
  grid-template-columns: minmax(280px, 1fr) repeat(3, minmax(150px, 210px));
  gap: 10px;
  padding: 14px 28px;
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 0;
  background: #fff;
  z-index: 3;
}}
input, select {{
  width: 100%;
  box-sizing: border-box;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 7px 9px;
  background: #fff;
  color: var(--text);
}}
main {{
  padding: 0 28px 32px;
}}
.visible-count {{
  color: var(--muted);
  margin: 12px 0;
}}
.table-wrap {{
  overflow-x: auto;
  border: 1px solid var(--border);
  border-radius: 8px;
}}
table {{
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
}}
th, td {{
  border-bottom: 1px solid var(--border);
  padding: 8px 10px;
  text-align: left;
  vertical-align: top;
  overflow-wrap: anywhere;
}}
th {{
  background: var(--panel-strong);
  cursor: pointer;
  user-select: none;
}}
.summary-row:hover {{
  background: #fbfcfe;
}}
.status-badge, .kind-badge {{
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 2px 7px;
  font-weight: 700;
  font-size: 12px;
  border: 1px solid var(--border);
  background: #fff;
}}
.status-badge {{
  font-weight: 700;
}}
.status-badge.changed {{ color: var(--changed); background: #fff7ed; border-color: #fed7aa; }}
.status-badge.added {{ color: var(--added); background: #f0fdf4; border-color: #bbf7d0; }}
.status-badge.removed {{ color: var(--removed); background: #fef2f2; border-color: #fecaca; }}
.status-badge.unchanged {{ color: #374151; }}
.status-badge.missing_both {{ color: #6b21a8; background: #faf5ff; border-color: #e9d5ff; }}
.kind-list {{
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}}
.kind-badge {{
  color: #344054;
  font-weight: 600;
  background: var(--panel);
}}
.key-cell strong {{
  display: block;
  margin-bottom: 2px;
}}
.qualified {{
  color: var(--muted);
  font-size: 12px;
}}
.review-toggle {{
  margin-top: 6px;
  border: 1px solid var(--border);
  border-radius: 5px;
  background: #fff;
  color: #344054;
  cursor: pointer;
  font: inherit;
  font-size: 12px;
  font-weight: 700;
  padding: 3px 7px;
}}
.review-toggle:hover {{
  border-color: var(--border-strong);
  background: var(--panel);
}}
.source-summary, .source-list {{
  color: var(--muted);
}}
.source-summary {{
  max-height: 58px;
  overflow: hidden;
}}
.source-list {{
  white-space: pre-wrap;
  max-height: 220px;
  overflow: auto;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 8px;
  background: #fff;
}}
.detail-row > td {{
  padding: 0;
  background: #fbfcfe;
}}
.detail-row[hidden] {{
  display: none;
}}
.detail-content {{
  display: grid;
  grid-template-columns: minmax(260px, 360px) minmax(0, 1fr);
  gap: 14px;
  padding: 14px;
}}
.detail-card {{
  min-width: 0;
}}
.detail-card h3 {{
  margin: 0 0 8px;
  font-size: 13px;
}}
.source-path {{
  color: var(--muted);
}}
.diff-shell {{
  border: 1px solid var(--border);
  border-radius: 6px;
  overflow: hidden;
  background: #fff;
}}
.diff-header {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  background: var(--panel-strong);
  border-bottom: 1px solid var(--border);
}}
.diff-header div {{
  padding: 7px 10px;
  font-weight: 700;
}}
.diff-header div + div {{
  border-left: 1px solid var(--border);
}}
.diff-scroll {{
  max-height: 70vh;
  overflow: auto;
}}
.diff-table {{
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace;
  font-size: 12px;
}}
.diff-table td {{
  padding: 0 8px;
  border-bottom: none;
  vertical-align: top;
}}
.diff-line-no {{
  width: 46px;
  color: #98a2b3;
  text-align: right;
  user-select: none;
  border-right: 1px solid var(--border);
}}
.diff-code {{
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}}
.diff-row.equal .diff-code {{ color: #344054; }}
.diff-row.delete td:nth-child(1), .diff-row.delete td:nth-child(2) {{ background: #fff1f2; }}
.diff-row.insert td:nth-child(3), .diff-row.insert td:nth-child(4) {{ background: #ecfdf3; }}
.diff-row.replace td:nth-child(1), .diff-row.replace td:nth-child(2) {{ background: #fff7ed; }}
.diff-row.replace td:nth-child(3), .diff-row.replace td:nth-child(4) {{ background: #f0fdf4; }}
.diff-skip td {{
  text-align: center;
  color: var(--muted);
  background: var(--panel);
  font-family: inherit;
  padding: 5px;
}}
.no-diff {{
  color: var(--muted);
  padding: 12px;
}}
.warnings {{
  margin: 16px 28px;
  padding: 12px 14px;
  border: 1px solid #facc15;
  border-radius: 6px;
  background: #fefce8;
}}
.warnings summary {{
  cursor: pointer;
  font-weight: 700;
}}
@media (max-width: 900px) {{
  .controls {{ grid-template-columns: 1fr; }}
  .detail-content {{ grid-template-columns: 1fr; }}
}}
</style>
</head>
<body>
<header>
  <h1>EU5 Update Audit</h1>
  <div class="subtitle">{html.escape(old_ref)} to {html.escape(new_ref)}</div>
  <div class="summary">
    <span class="pill">Total: {summary["total"]}</span>
    <span class="pill">Changed: {summary["changed"]}</span>
    <span class="pill">Added: {summary["added"]}</span>
    <span class="pill">Removed: {summary["removed"]}</span>
    <span class="pill">Unchanged: {summary["unchanged"]}</span>
    <span class="pill">Missing both: {summary["missing_both"]}</span>
  </div>
</header>
{_warnings_html(warnings)}
<section class="controls">
  <input id="search" type="search" placeholder="Search key, source, collection">
  <select id="status"><option value="__impacted" selected>Impacted only</option><option value="">All statuses</option>{_options(statuses)}</select>
  <select id="collection"><option value="">All collections</option>{_options(collections)}</select>
  <select id="kind"><option value="">All reference types</option>{_options(kinds)}</select>
</section>
<main>
  <p id="visible-count" class="visible-count"></p>
  <div class="table-wrap">
  <table id="audit-table">
    <colgroup>
      <col style="width: 110px">
      <col style="width: 160px">
      <col style="width: 250px">
      <col style="width: 180px">
      <col>
      <col style="width: 210px">
      <col style="width: 210px">
    </colgroup>
    <thead>
      <tr>
        <th data-sort="status">Status</th>
        <th data-sort="collection">Collection</th>
        <th data-sort="key">Key</th>
        <th data-sort="referenceKinds">Type</th>
        <th data-sort="modSources">Mod sources</th>
        <th data-sort="oldSource">Old vanilla</th>
        <th data-sort="newSource">New vanilla</th>
      </tr>
    </thead>
{table_rows}
  </table>
  </div>
</main>
<script>
const table = document.getElementById("audit-table");
const records = Array.from(document.querySelectorAll("#audit-table tbody.record"));
const search = document.getElementById("search");
const statusFilter = document.getElementById("status");
const collectionFilter = document.getElementById("collection");
const kindFilter = document.getElementById("kind");
const visibleCount = document.getElementById("visible-count");
const impactedStatuses = new Set(["changed", "added", "removed"]);

function applyFilters() {{
  const query = search.value.trim().toLowerCase();
  let visible = 0;
  for (const record of records) {{
    const okQuery = !query || record.dataset.search.includes(query);
    const statusValue = statusFilter.value;
    const okStatus = !statusValue ||
      (statusValue === "__impacted" ? impactedStatuses.has(record.dataset.status) : record.dataset.status === statusValue);
    const okCollection = !collectionFilter.value || record.dataset.collection === collectionFilter.value;
    const okKind = !kindFilter.value || record.dataset.kinds.split(",").includes(kindFilter.value);
    const show = okQuery && okStatus && okCollection && okKind;
    record.hidden = !show;
    if (show) visible += 1;
  }}
  visibleCount.textContent = `${{visible}} visible dependencies`;
}}

for (const control of [search, statusFilter, collectionFilter, kindFilter]) {{
  control.addEventListener("input", applyFilters);
}}

document.querySelectorAll(".review-toggle").forEach((button) => {{
  button.addEventListener("click", () => {{
    const record = button.closest("tbody.record");
    const detailRow = record.querySelector(".detail-row");
    const opening = detailRow.hidden;
    detailRow.hidden = !opening;
    record.classList.toggle("open", opening);
    button.setAttribute("aria-expanded", String(opening));
    button.textContent = opening ? "Hide diff" : "Diff & sources";
  }});
}});

document.querySelectorAll("th[data-sort]").forEach((header) => {{
  header.addEventListener("click", () => {{
    const key = header.dataset.sort;
    const sortKey = `sort${{key.charAt(0).toUpperCase()}}${{key.slice(1)}}`;
    const sorted = records.sort((a, b) => (a.dataset[sortKey] || "").localeCompare(b.dataset[sortKey] || ""));
    for (const record of sorted) table.appendChild(record);
    applyFilters();
  }});
}});

applyFilters();
</script>
</body>
</html>
"""
    path.write_text(html_text, encoding="utf-8")


def _html_record(row: dict[str, str]) -> str:
    kinds = ",".join(kind.strip() for kind in row["reference_kinds"].split(", ") if kind.strip())
    search_text = " ".join(
        (
            row["status"],
            row["scope"],
            row["collection"],
            row["key"],
            row["qualified"],
            row["reference_kinds"],
            row["mod_sources"],
            row["old_source"],
            row["new_source"],
        )
    ).lower()
    return f"""    <tbody class="record" data-status="{_html_attr(row["status"])}" data-collection="{_html_attr(row["collection"])}" data-kinds="{_html_attr(kinds)}" data-search="{_html_attr(search_text)}" data-sort-status="{_html_attr(row["status"])}" data-sort-key="{_html_attr(row["key"])}" data-sort-collection="{_html_attr(row["collection"])}" data-sort-reference-kinds="{_html_attr(row["reference_kinds"])}" data-sort-mod-sources="{_html_attr(_source_summary(row["mod_sources"], max_lines=1))}" data-sort-old-source="{_html_attr(row["old_source"])}" data-sort-new-source="{_html_attr(row["new_source"])}">
      <tr class="summary-row">
        <td>{_status_badge(row["status"])}</td>
        <td>{html.escape(row["scope"])}/{html.escape(row["collection"])}</td>
        <td class="key-cell"><strong>{html.escape(row["key"])}</strong><span class="qualified">{html.escape(row["qualified"])}</span><button class="review-toggle" type="button" aria-expanded="false">Diff & sources</button></td>
        <td>{_kind_badges(row["reference_kinds"])}</td>
        <td><div class="source-summary">{html.escape(_source_summary(row["mod_sources"]))}</div></td>
        <td><span class="source-path">{html.escape(row["old_source"] or "not present")}</span></td>
        <td><span class="source-path">{html.escape(row["new_source"] or "not present")}</span></td>
      </tr>
      <tr class="detail-row" hidden>
        <td colspan="7">
          <div class="detail-content">
            <section class="detail-card">
              <h3>Prosper or Perish references</h3>
              <div class="source-list">{html.escape(row["mod_sources"])}</div>
            </section>
            <section class="detail-card">
              <h3>Vanilla definition diff</h3>
              {_side_by_side_diff_html(row)}
            </section>
          </div>
        </td>
      </tr>
    </tbody>"""


def _html_attr(value: str) -> str:
    return html.escape(" ".join(value.split()), quote=True)


def _status_badge(status: str) -> str:
    return f'<span class="status-badge {html.escape(status)}">{html.escape(status)}</span>'


def _kind_badges(reference_kinds: str) -> str:
    kinds = [kind.strip() for kind in reference_kinds.split(",") if kind.strip()]
    badges = "".join(f'<span class="kind-badge">{html.escape(kind)}</span>' for kind in kinds)
    return f'<div class="kind-list">{badges}</div>'


def _source_summary(sources: str, *, max_lines: int = 2) -> str:
    lines = [line for line in sources.splitlines() if line]
    if not lines:
        return ""
    shown = lines[:max_lines]
    remaining = len(lines) - len(shown)
    if remaining > 0:
        shown.append(f"... {remaining} more source groups")
    return "\n".join(shown)


def _side_by_side_diff_html(row: dict[str, str]) -> str:
    old_text = row.get("old_definition", "")
    new_text = row.get("new_definition", "")
    if not old_text and not new_text:
        return '<div class="diff-shell"><div class="no-diff">No vanilla definition was found in either ref.</div></div>'

    old_source = row["old_source"] or "not present"
    new_source = row["new_source"] or "not present"
    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()
    body_rows = "\n".join(_diff_rows(old_lines, new_lines))
    return f"""<div class="diff-shell">
  <div class="diff-header"><div>{html.escape(old_source)}</div><div>{html.escape(new_source)}</div></div>
  <div class="diff-scroll">
    <table class="diff-table">
      <tbody>
{body_rows}
      </tbody>
    </table>
  </div>
</div>"""


def _diff_rows(old_lines: list[str], new_lines: list[str]) -> list[str]:
    matcher = difflib.SequenceMatcher(a=old_lines, b=new_lines)
    rows: list[str] = []
    for tag, old_start, old_end, new_start, new_end in matcher.get_opcodes():
        if tag == "equal":
            rows.extend(_equal_diff_rows(old_lines, new_lines, old_start, old_end, new_start, new_end))
        elif tag == "delete":
            for offset, line in enumerate(old_lines[old_start:old_end]):
                rows.append(_diff_row("delete", old_start + offset + 1, line, None, ""))
        elif tag == "insert":
            for offset, line in enumerate(new_lines[new_start:new_end]):
                rows.append(_diff_row("insert", None, "", new_start + offset + 1, line))
        elif tag == "replace":
            old_chunk = old_lines[old_start:old_end]
            new_chunk = new_lines[new_start:new_end]
            max_len = max(len(old_chunk), len(new_chunk))
            for offset in range(max_len):
                old_line = old_chunk[offset] if offset < len(old_chunk) else ""
                new_line = new_chunk[offset] if offset < len(new_chunk) else ""
                old_no = old_start + offset + 1 if offset < len(old_chunk) else None
                new_no = new_start + offset + 1 if offset < len(new_chunk) else None
                rows.append(_diff_row("replace", old_no, old_line, new_no, new_line))
    return rows or [_diff_skip_row("definitions are identical")]


def _equal_diff_rows(
    old_lines: list[str],
    new_lines: list[str],
    old_start: int,
    old_end: int,
    new_start: int,
    new_end: int,
    *,
    context: int = 3,
) -> list[str]:
    length = old_end - old_start
    if length <= context * 2 + 2:
        indexes = list(range(length))
        skipped = False
    else:
        indexes = [*range(context), *range(length - context, length)]
        skipped = True

    rows: list[str] = []
    for position, offset in enumerate(indexes):
        if skipped and position == context:
            rows.append(_diff_skip_row(f"{length - context * 2} unchanged lines"))
        rows.append(
            _diff_row(
                "equal",
                old_start + offset + 1,
                old_lines[old_start + offset],
                new_start + offset + 1,
                new_lines[new_start + offset],
            )
        )
    return rows


def _diff_row(
    row_class: str,
    old_line_no: int | None,
    old_line: str,
    new_line_no: int | None,
    new_line: str,
) -> str:
    old_no = "" if old_line_no is None else str(old_line_no)
    new_no = "" if new_line_no is None else str(new_line_no)
    return (
        f'        <tr class="diff-row {row_class}">'
        f'<td class="diff-line-no">{html.escape(old_no)}</td>'
        f'<td class="diff-code">{html.escape(old_line)}</td>'
        f'<td class="diff-line-no">{html.escape(new_no)}</td>'
        f'<td class="diff-code">{html.escape(new_line)}</td>'
        "</tr>"
    )


def _diff_skip_row(label: str) -> str:
    return f'        <tr class="diff-skip"><td colspan="4">{html.escape(label)}</td></tr>'


def _warnings_html(warnings: list[str]) -> str:
    if not warnings:
        return ""
    items = "".join(f"<li>{html.escape(warning)}</li>" for warning in warnings[:80])
    more = "" if len(warnings) <= 80 else f"<p>{len(warnings) - 80} more warnings omitted.</p>"
    return f'<details class="warnings"><summary>Parser warnings ({len(warnings)})</summary><ul>{items}</ul>{more}</details>'


def _options(values: Iterable[str]) -> str:
    return "".join(f'<option value="{html.escape(value)}">{html.escape(value)}</option>' for value in values)


def _safe_ref(ref: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", ref).strip("_") or "ref"


def _display_path(path: Path, repo: Path) -> str:
    try:
        return str(path.relative_to(repo))
    except ValueError:
        return str(path)
