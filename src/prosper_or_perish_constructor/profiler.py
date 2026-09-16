"""Read EU5 script-profiler CSVs and export an offline, source-aware explorer.

CSV rows are measurements, not stacks. Edges are explicitly static source
relationships; inclusive times are never added to estimate elapsed time.
"""

from __future__ import annotations

import argparse
import base64
import csv
import gzip
import hashlib
import io
import json
import math
import os
import re
import tomllib
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath


METRICS = {
    "Bottleneck Time": "bottleneck",
    "Call Count": "calls",
    "Max Time": "max",
    "Min Time": "min",
    "Self Time": "self",
    "Total Time": "total",
}
NODE_COLUMNS = [
    "label", "file", "line", "kind", "calls", "self", "total", "bottleneck",
    "max", "min", "rows", "origin", "symbol", "source", "measured", "operation",
]
LOCATION = re.compile(r"^(.*?)\s+@\s+(.+):(\d+)$")
SCRIPT_DIRS = {"scripted_triggers", "scripted_effects", "script_values"}


def host_path(value: str | Path, base: Path) -> Path:
    """Accept native paths and Windows drive paths from a WSL command line."""
    text = str(value)
    if os.name != "nt" and re.match(r"^[A-Za-z]:[\\/]", text):
        text = f"/mnt/{text[0].lower()}/{text[3:].replace(chr(92), '/')}"
    path = Path(text).expanduser()
    return path if path.is_absolute() else base / path


def add_profiler_command(subcommands) -> None:
    parser = subcommands.add_parser(
        "profiler", help="Visualize EU5 profiler hotspots and inferred source call graphs."
    )
    parser.add_argument("input", nargs="?", help="Dump directory or profiler CSV; defaults to the live EU5 logs folder.")
    parser.add_argument("--output", default="graphs/profiler", help="Parent directory for unique timestamped reports (default: graphs/profiler).")
    parser.add_argument("--label", help="Capture name; defaults to the input directory name.")
    parser.add_argument("--baseline", help="Optional earlier report, dump directory or CSV for comparison.")
    parser.add_argument("--load-order", help="Load-order TOML for source lookup; requires --profile.")
    parser.add_argument("--profile", help="Explicit source profile, e.g. vanilla or constructor.")
    parser.add_argument("--source", action="append", default=[], metavar="NAME=PATH",
                        help="Additional source root; repeat in load order, last wins per file.")
    parser.add_argument("--time-unit", choices=["raw", "seconds", "milliseconds", "microseconds"],
                        default="raw", help="Unit of dump values; CSV headers do not specify one.")
    parser.set_defaults(handler=run_profiler)


def read_capture(path: Path) -> dict:
    label = path.name if path.is_dir() else path.parent.name
    if path.is_dir() and (path / "profile.json").is_file() and (path / "inputs").is_dir():
        path = path / "inputs"
    if path.is_dir():
        paths = [(name, path / filename) for name, filename in (
            ("summary", "profiling.csv"), ("detail", "profiling_roots.csv")
        ) if (path / filename).is_file()]
    else:
        paths = [("detail" if path.name == "profiling_roots.csv" else "summary", path)]
    if not paths:
        raise ValueError(f"No profiling.csv or profiling_roots.csv in {path}")
    result = {"label": label, "datasets": {}}
    for scope, filename in paths:
        result["datasets"][scope] = read_csv(filename)
    performance = (path if path.is_dir() else path.parent) / "performance_degradation.log"
    result["performance"] = read_performance(performance) if performance.is_file() else None
    return result


def default_logs(repo: Path) -> Path:
    local = repo / "constructor.local.toml"
    if local.is_file():
        config = tomllib.loads(local.read_text(encoding="utf-8-sig"))
        configured = config.get("profiler", {}).get("logs_dir")
        if configured:
            return host_path(configured, repo)
    from prosper_or_perish_constructor.cli import _default_eu5_user_data_root

    return _default_eu5_user_data_root() / "logs"


def read_performance(path: Path) -> dict:
    """Keep the engine's explicit seconds/MB series separate from script timings."""
    rows, warnings = [], []
    raw = snapshot_bytes(path)
    with io.StringIO(raw.decode("utf-8-sig"), newline="") as stream:
        reader = csv.DictReader(stream, skipinitialspace=True)
        # Engine headers use tabs before quoted fields; csv.skipinitialspace
        # removes spaces only, leaving those header quotes literal.
        reader.fieldnames = [key.strip().strip('"').strip() for key in (reader.fieldnames or [])]
        for row in reader:
            try:
                point = {"elapsed_seconds": float(row["Total Time"]),
                         "average_frame_seconds": float(row["Average Delta"]),
                         "max_frame_seconds": float(row["MaxDelta"]),
                         "memory_mb": float(row["Memory Usage (MB)"]),
                         "date": row.get("Game Data", "")}
                if not all(math.isfinite(value) and value >= 0 for value in point.values() if isinstance(value, float)):
                    raise ValueError("invalid number")
                rows.append(point)
            except (KeyError, ValueError, TypeError):
                warnings.append(f"Skipped malformed performance row {reader.line_num}")
    if not rows:
        warnings.append("performance_degradation.log contains no usable samples (the live game may have reset it).")
    return {"input": str(path), "sha256": hashlib.sha256(raw).hexdigest(),
            "rows": rows, "warnings": warnings, "_raw_bytes": raw}


def snapshot_bytes(path: Path) -> bytes:
    before = path.stat()
    raw = path.read_bytes()
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError(f"{path} changed while reading; wait for the dump to finish and rerun")
    return raw


def read_csv(path: Path) -> dict:
    nodes: dict[str, dict] = {}
    raw_rows = 0
    raw = snapshot_bytes(path)
    with io.StringIO(raw.decode("utf-8-sig"), newline="") as stream:
        first = stream.readline()
        stream.seek(0)
        delimiter = ";" if ";" in first else "\t" if "\t" in first else ","
        reader = csv.DictReader(stream, delimiter=delimiter)
        reader.fieldnames = [name.strip() for name in (reader.fieldnames or [])]
        missing = {"File Location", *METRICS} - set(reader.fieldnames)
        if missing:
            raise ValueError(f"{path}: missing columns: {', '.join(sorted(missing))}")
        for row in reader:
            raw_rows += 1
            try:
                if None in row or any(value is None for value in row.values()):
                    raise ValueError("wrong number of columns")
                label = row["File Location"].strip()
                if not label:
                    raise ValueError("empty File Location")
                values = {key: float(row[column].strip()) for column, key in METRICS.items()}
                if any(not math.isfinite(v) or v < 0 for v in values.values()):
                    raise ValueError("metrics must be finite and non-negative")
                # Parse as an integer, without rounding large counts through a float.
                values["calls"] = int(row["Call Count"].strip())
            except (ValueError, AttributeError) as exc:
                raise ValueError(f"{path}:{reader.line_num}: {exc}") from exc
            match = LOCATION.match(label)
            kind, file, line = match.groups() if match else (label, "<unknown>", "0")
            file = file.replace("\\", "/")
            identity = f"{kind} @ {file}:{line}"
            if identity not in nodes:
                nodes[identity] = dict(label=identity, file=file, line=int(line), kind=kind,
                                       rows=0, origin="unresolved", symbol="", source="",
                                       measured=True, operation="", **values)
            else:
                node = nodes[identity]
                for key in ("self", "total", "bottleneck", "calls"):
                    node[key] += values[key]
                node["max"] = max(node["max"], values["max"])
                node["min"] = min(node["min"], values["min"])
            nodes[identity]["rows"] += 1
    if not nodes:
        raise ValueError(f"{path}: no measurement rows")
    return {"nodes": list(nodes.values()), "edges": [], "input": str(path),
            "sha256": hashlib.sha256(raw).hexdigest(), "_raw_bytes": raw, "raw_rows": raw_rows,
            "duplicates": raw_rows - len(nodes), "self_sum": sum(n["self"] for n in nodes.values())}


def source_roots(args, repo: Path) -> list[tuple[str, Path]]:
    roots = []
    if args.load_order and not args.profile:
        raise ValueError("--load-order requires an explicit --profile matching the capture")
    if args.profile:
        from eu5gameparser.load_order import LoadOrderConfig

        config = host_path(args.load_order or "constructor.load_order.toml", repo)
        roots.extend((layer.id, layer.root) for layer in LoadOrderConfig.load(config).profile(args.profile).layers)
    for source in args.source:
        name, sep, value = source.partition("=")
        if not sep or not name.strip() or not value.strip():
            raise ValueError("--source must be NAME=PATH")
        roots.append((name, host_path(value, repo)))
    for name, root in roots:
        if not root.is_dir():
            raise ValueError(f"Source root {name!r} is not a directory: {root}")
    return roots


def resolve_source(file: str, roots: list[tuple[str, Path]]) -> tuple[str, Path] | None:
    relative = PurePosixPath(file)
    # Profiler paths are data, never permission to read arbitrary local files.
    if relative.is_absolute() or ".." in relative.parts or ":" in file or file.startswith("<"):
        return None
    for name, root in reversed(roots):
        for prefix in ("", "in_game", "main_menu", "game/in_game", "game/main_menu", "game"):
            candidate = root / prefix / file
            if candidate.is_file() and candidate.resolve().is_relative_to(root.resolve()):
                return name, candidate
    return None


def build_source_index(files: set[str], roots: list[tuple[str, Path]]) -> tuple[dict, list[str]]:
    """Use the shared Clausewitz parser, preserving real entry ancestry and lines."""
    from eu5gameparser.clausewitz.parser import parse_text
    from eu5gameparser.clausewitz.syntax import CList

    sources = {}
    warnings = []
    for file in sorted(files):
        resolved = resolve_source(file, roots)
        if not resolved:
            continue
        origin, path = resolved
        raw = path.read_bytes()
        text = raw.decode("utf-8-sig", errors="replace")
        source = {"origin": origin, "path": str(path), "sha256": hashlib.sha256(raw).hexdigest(),
                  "lines": text.splitlines(), "entries": []}
        sources[file] = source
        try:
            parse_source, declarations = prepare_source(text)
            source["declarations"] = declarations
            document = parse_text(parse_source, path)
            def visit(entries, parent, symbol):
                for entry in entries:
                    index = len(source["entries"])
                    current_symbol = symbol or entry.key
                    scalar = entry.value if isinstance(entry.value, str) else ""
                    source["entries"].append({"line": entry.location.line, "key": entry.key,
                                              "value": scalar, "parent": parent, "symbol": current_symbol})
                    if isinstance(entry.value, CList):
                        visit(entry.value.entries, index, current_symbol)
            visit(document.entries, None, "")
        except (ValueError, RecursionError) as exc:
            warnings.append(f"Cannot infer edges for {file}: {exc}")
            source["entries"] = []
    return sources, warnings


def prepare_source(text: str) -> tuple[str, list[int]]:
    """Mask syntax unsupported by the shared parser for structural indexing only.

    Preserve every character position/newline; never evaluate inline arithmetic.
    Quoted strings and comments are consumed first and left untouched.
    """
    declarations = []
    pattern = re.compile(r'"(?:\\.|[^"\\])*"|#[^\n]*|@\[[^\]]*\]|\bscripted_(?:effect|trigger|value)\s+(?=[\w.:]+\s*=\s*\{)')

    def replace(match):
        value = match.group()
        if value.startswith(('"', '#')):
            return value
        if value.startswith("scripted_"):
            declarations.append(text.count("\n", 0, match.end()) + 1)
            return "".join("\n" if char == "\n" else " " for char in value)
        return "0" + "".join("\n" if char == "\n" else " " for char in value[1:])

    return pattern.sub(replace, text), declarations


def enrich_dataset(dataset: dict, sources: dict) -> None:
    nodes = dataset["nodes"]
    by_file = defaultdict(list)
    for i, node in enumerate(nodes):
        by_file[node["file"]].append(i)
    # A file:line may represent several profiler kinds. Keep their measurements
    # separate and omit ambiguous edge endpoints instead of inventing a caller.
    entry_nodes = {}
    definitions = defaultdict(list)
    local_definitions = defaultdict(list)
    edges = set()
    ambiguous = 0
    for file, source in sources.items():
        entries = source["entries"]
        by_line = defaultdict(list)
        for j, entry in enumerate(entries):
            by_line[entry["line"]].append(j)
        matching = defaultdict(list)
        for i in by_file[file]:
            node = nodes[i]
            node.update(origin=source["origin"], source=file)
            matches = by_line[node["line"]]
            if matches:
                node["symbol"] = entries[matches[0]]["symbol"]
                if len(matches) == 1:
                    matching[matches[0]].append(i)
                    node["operation"] = entries[matches[0]]["key"]
                else:
                    ambiguous += 1
        for j, ids in matching.items():
            if len(ids) == 1:
                entry_nodes[(file, j)] = ids[0]
            else:
                ambiguous += len(ids)
        global_script = bool(set(PurePosixPath(file).parts) & SCRIPT_DIRS)
        definition_ids = {j for j, e in enumerate(entries) if e["parent"] is None and
                          (global_script or e["line"] in source.get("declarations", []))}
        needed = set(matching) | definition_ids
        for j in list(needed):
            parent = entries[j]["parent"]
            while parent is not None:
                needed.add(parent)
                parent = entries[parent]["parent"]
        for j in sorted(needed):
            entry = entries[j]
            if (file, j) not in entry_nodes:
                entry_nodes[file, j] = len(nodes)
                kind = "definition" if j in definition_ids else "source block"
                nodes.append(dict(label=f"{kind} @ {file}:{entry['line']} ({j})", file=file,
                                  line=entry["line"], kind=kind, calls=0, self=0, total=0,
                                  bottleneck=0, max=0, min=0, rows=0, origin=source["origin"],
                                  symbol=entry["symbol"], operation=entry["key"], source=file, measured=False))
                for measurement in matching.get(j, []):
                    edges.add((entry_nodes[file, j], measurement, "measurement"))
            if j in definition_ids:
                if global_script:
                    definitions[entry["key"]].append(entry_nodes[file, j])
                else:
                    local_definitions[file, entry["key"]].append(entry_nodes[file, j])
    for file, source in sources.items():
        entries = source["entries"]
        owners = {}
        for j, entry in enumerate(entries):
            node_id = entry_nodes.get((file, j))
            parent_id = owners.get(entry["parent"])
            if node_id is not None and parent_id is not None and node_id != parent_id:
                edges.add((parent_id, node_id, "contains"))
            owner = node_id if node_id is not None else parent_id
            owners[j] = owner
            if owner is None or entry["parent"] is None:
                continue
            # Only literal references to unambiguous named scripted definitions.
            # Dynamic scope/event dispatch cannot be reconstructed from these CSVs.
            for token in {entry["key"], entry["value"].removeprefix("script_value:")}:
                targets = local_definitions.get((file, token), definitions.get(token, []))
                if len(targets) == 1 and targets[0] != owner:
                    edges.add((owner, targets[0], "reference"))
    dataset["edges"] = sorted(edges)
    dataset["resolved"] = sum(bool(n["source"]) for n in nodes if n["measured"])
    dataset["ambiguous_source_rows"] = ambiguous


def write_report(capture: dict, baseline: dict | None, roots, output: Path, time_unit: str) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    for current, directory in ((capture, "inputs"), (baseline, "baseline_inputs")):
        if current is None:
            continue
        snapshot = output / directory
        snapshot.mkdir(exist_ok=True)
        expected = {"profiling_roots.csv" if scope == "detail" else "profiling.csv"
                    for scope in current["datasets"]}
        if current["performance"]:
            expected.add("performance_degradation.log")
        for name in ("profiling.csv", "profiling_roots.csv", "performance_degradation.log"):
            if name not in expected:
                (snapshot / name).unlink(missing_ok=True)
        for scope, dataset in current["datasets"].items():
            name = "profiling_roots.csv" if scope == "detail" else "profiling.csv"
            (snapshot / name).write_bytes(dataset.pop("_raw_bytes"))
        if current["performance"]:
            (snapshot / "performance_degradation.log").write_bytes(current["performance"].pop("_raw_bytes"))
    files = {n["file"] for d in capture["datasets"].values() for n in d["nodes"]}
    sources, warnings = build_source_index(files, roots) if roots else ({}, [])
    for dataset in capture["datasets"].values():
        enrich_dataset(dataset, sources)
    notes = [
        "The CSVs contain no caller IDs, stacks or timestamps. All graph edges are inferred from the supplied source, not measured calls.",
        "Summary and detail are separate profiler views and are never summed together. Inclusive times overlap; self shares use only the selected view's self-time sum, not wall-clock runtime.",
        "Duplicate file-location rows are aggregated within each view; original context is unavailable. Max uses the maximum and min the minimum. Per-call costs are recomputed from totals because exported averages are rounded.",
        "Bottleneck Time is preserved as exported; its engine-specific meaning is not inferred. The dump does not specify timing units.",
        "Source roots must match the capture's game/mod versions. Paths and hashes document the supplied sources, but the dump cannot verify them. Later roots override identical paths; database REPLACE/INJECT semantics and dynamic dispatch are not simulated.",
        "Reference edges cover literal names of scripted triggers, effects and values in captured source files, including file-local declarations. Dotted links associate multiple measurements with one source entry. Source-only nodes have no measured cost. Inline arithmetic is masked for structural parsing, not evaluated; ambiguous same-line entries omit measurement edges.",
    ]
    if baseline:
        notes.append("Baseline comparison matches exact kind + file + line within the same view. Line changes appear as additions/removals. Self-share percentage points normalize capture size, not workload; compare equivalent scenarios. No baseline source graph is inferred using current sources.")
    payload = {"schema_version": 1, "label": capture["label"], "unit": time_unit,
               "generated_at_utc": datetime.now(timezone.utc).isoformat(),
               "node_columns": NODE_COLUMNS, "datasets": capture["datasets"], "baseline": baseline,
               "performance": capture["performance"],
               "sources": {file: {k: v for k, v in source.items() if k != "entries"}
                           for file, source in sources.items()}, "warnings": warnings, "notes": notes,
               "source_roots": [{"name": name, "path": str(root)} for name, root in roots]}
    output.mkdir(parents=True, exist_ok=True)
    # CSV is deliberately exhaustive; the browser only renders a bounded page.
    for scope in {"summary", "detail"} - capture["datasets"].keys():
        (output / f"hotspots_{scope}.csv").unlink(missing_ok=True)
    for scope, dataset in capture["datasets"].items():
        with (output / f"hotspots_{scope}.csv").open("w", encoding="utf-8", newline="") as stream:
            fields = NODE_COLUMNS + ["self_share_percent", "self_per_call", "total_per_call"]
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            for node in sorted(dataset["nodes"], key=lambda n: n["self"], reverse=True):
                if not node["measured"]:
                    continue
                writer.writerow(dict(node, self_share_percent=100 * node["self"] / dataset["self_sum"] if dataset["self_sum"] else 0,
                                     self_per_call=node["self"] / node["calls"] if node["calls"] else "",
                                     total_per_call=node["total"] / node["calls"] if node["calls"] else ""))
    # Columnar row arrays keep the 150k-node capture portable and fast to load.
    for collection in (payload["datasets"], baseline["datasets"] if baseline else {}):
        for dataset in collection.values():
            dataset["nodes"] = [[node[column] for column in NODE_COLUMNS] for node in dataset["nodes"]]
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    (output / "profile.json").write_text(serialized, encoding="utf-8")
    encoded = base64.b64encode(gzip.compress(serialized.encode(), mtime=0)).decode()
    template = Path(__file__).with_name("profiler_explorer.html").read_text(encoding="utf-8")
    (output / "index.html").write_text(template.replace("__PROFILE_GZIP_BASE64__", encoded), encoding="utf-8")
    return payload


def new_report_directory(parent: Path, label: str) -> Path:
    """Reserve a fresh directory atomically, including concurrent same-time runs."""
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", label).strip("-_")[:64] or "capture"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    parent.mkdir(parents=True, exist_ok=True)
    stem = f"{slug}-{stamp}"
    for attempt in range(1000):
        candidate = parent / (stem if not attempt else f"{stem}-{attempt}")
        try:
            candidate.mkdir()
            return candidate
        except FileExistsError:
            continue
    raise ValueError(f"Cannot reserve a unique report directory under {parent}")


def run_profiler(args, extra, repo: Path, project: Path) -> int:
    if extra:
        raise SystemExit(f"profiler: unrecognized arguments: {' '.join(extra)}")
    try:
        roots = source_roots(args, repo)
        input_path = host_path(args.input, repo) if args.input else default_logs(repo)
        capture = read_capture(input_path)
        capture["label"] = args.label or capture["label"]
        baseline = read_capture(host_path(args.baseline, repo)) if args.baseline else None
        if baseline and not (capture["datasets"].keys() & baseline["datasets"].keys()):
            raise ValueError("Capture and baseline have no matching profiler views")
        output = new_report_directory(host_path(args.output, repo), capture["label"])
        print(f"Profiler input: {input_path}", flush=True)
        print(f"Profiler output: {output}", flush=True)
        print(f"Profiler: reading {sum(d['raw_rows'] for d in capture['datasets'].values()):,} rows; resolving {len(roots)} source roots.", flush=True)
        report = write_report(capture, baseline, roots, output, args.time_unit)
    except (OSError, ValueError, KeyError) as exc:
        raise SystemExit(f"profiler: {exc}") from exc
    for scope, dataset in report["datasets"].items():
        print(f"{scope}: {dataset['raw_rows']:,} rows, {dataset['duplicates']:,} duplicate locations, "
              f"{dataset['resolved']:,} source-resolved, {len(dataset['edges']):,} inferred edges")
        for node in sorted((n for n in dataset["nodes"] if n[14]), key=lambda n: n[5], reverse=True)[:5]:
            print(f"  self={node[5]:.6g}  calls={node[4]:,}  {node[0]}")
    print(f"Report: {output / 'index.html'}")
    print(f"Data: {output / 'profile.json'}")
    print("Timing values retain dump units; edges are source-inferred, not recorded call stacks.")
    if report["warnings"]:
        print(f"Source parse warnings: {len(report['warnings'])} (see report)")
    return 0
