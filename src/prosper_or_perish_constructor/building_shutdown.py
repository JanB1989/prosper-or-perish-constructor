"""Building shutdown: which buildings without goods output may be closed.

The AI closes buildings without goods output (temples, libraries, universities, marketplaces, docks, ...) when its
building maintenance passes AI_ALLOWED_BUILDING_MAINTENANCE x AI_BUILDING_MAINTENANCE_LEEWAY of its income and reopens
them later, so they flipped open and closed many times a game (docs/ai_building_rulebook.md, "Maintenance budget").
``[building_shutdown.classes]`` in constructor.toml maps every footprint class (the blueprint's ``footprint:``) to
``"never"`` or ``"keep"``; a blueprint may override its class with a top-level ``shutdown: never | keep``.

``ppc build`` and ``ppc sync`` write ``can_close = no`` (the player) and ``ai_forbid_shutdown = yes`` (the AI's
maintenance and profit closing) into the block that owns each "never" building in the compiled mod, like the footprint
step. Buildings with a goods output are never touched: a producer that loses money must stay closable. The lines carry
a marker comment, so a building switched back to "keep" loses them again.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
import tomllib

from prosper_or_perish_constructor import yaml_io
from prosper_or_perish_constructor.building_footprint import (
    BLUEPRINT_ROOT_RELATIVE,
    _brace_pairs,
    _depth_zero_text,
    _read,
    blocks,
    owner_blocks,
    vanilla_definitions,
)

CONFIG_SECTION = "building_shutdown"
NEVER, KEEP = "never", "keep"
MARKER = "# building_shutdown"
FLAGS = (("can_close", "no"), ("ai_forbid_shutdown", "yes"))
PRODUCTION_METHOD_DIRS = (Path("in_game/common/production_methods"),)
_INJECT = {"INJECT", "TRY_INJECT", "INJECT_OR_CREATE"}

_FLAG_LINE_RE = re.compile(r"^[ \t]*(?:can_close|ai_forbid_shutdown)\s*=\s*\S+[ \t]*#\s*building_shutdown[^\n]*\n?", re.MULTILINE)
_ANY_FLAG_RE = {key: re.compile(rf"^[ \t]*{key}\s*=\s*(?P<value>\S+)", re.MULTILINE) for key, _ in FLAGS}
_METHOD_LIST_RE = re.compile(r"possible_production_methods\s*=\s*\{(?P<body>[^{}]*)\}")
_UNIQUE_RE = re.compile(r"unique_production_methods\s*=\s*\{")
_PRODUCED_RE = re.compile(r"(?<![A-Za-z_0-9])produced\s*=")


@dataclass(frozen=True)
class ShutdownConfig:
    classes: dict[str, str]  # footprint class -> never | keep


@dataclass
class ShutdownResult:
    locked: list[str] = field(default_factory=list)
    kept: int = 0
    producing_skipped: int = 0
    files_changed: int = 0
    not_in_mod: list[str] = field(default_factory=list)


def load_config(project: Path) -> ShutdownConfig:
    raw = tomllib.loads(project.read_text(encoding="utf-8-sig"))
    section = raw.get(CONFIG_SECTION)
    if not isinstance(section, dict) or not isinstance(section.get("classes"), dict):
        raise ValueError(f"{project}: [{CONFIG_SECTION}.classes] must map every footprint class to \"never\" or \"keep\"")
    classes: dict[str, str] = {}
    for name, value in section["classes"].items():
        if value not in (NEVER, KEEP):
            raise ValueError(f"{project}: {CONFIG_SECTION}.classes.{name} must be \"never\" or \"keep\", got {value!r}")
        classes[name] = value
    return ShutdownConfig(classes=classes)


def blueprint_rules(repo: Path) -> dict[str, tuple[str, str, Path]]:
    """Building key -> (footprint class, shutdown override or "", blueprint path)."""
    out: dict[str, tuple[str, str, Path]] = {}
    for path in sorted((repo / BLUEPRINT_ROOT_RELATIVE).glob("*.yml")):
        data = yaml_io.safe_load(path.read_text(encoding="utf-8-sig")) or {}
        building = data.get("building") if isinstance(data.get("building"), dict) else {}
        key = str(building.get("key") or data.get("tag") or path.stem)
        out[key] = (str(data.get("footprint") or ""), str(data.get("shutdown") or ""), path)
    return out


def validate(repo: Path, config: ShutdownConfig) -> list[str]:
    errors: list[str] = []
    for key, (footprint, override, path) in sorted(blueprint_rules(repo).items()):
        if override and override not in (NEVER, KEEP):
            errors.append(f"{path.name}: shutdown must be never or keep, got {override!r}")
        elif not override and footprint and footprint not in config.classes:
            errors.append(f"{path.name}: footprint class {footprint!r} is not in [{CONFIG_SECTION}.classes]")
    return errors


def rule(config: ShutdownConfig, footprint: str, override: str) -> str:
    return override or config.classes.get(footprint, KEEP)


def producing_methods(vanilla_root: Path, mod_root: Path) -> dict[str, bool]:
    """Shared production method name -> has a goods output (vanilla, then the mod's files)."""
    out: dict[str, bool] = {}
    for root in (Path(vanilla_root) / "game", mod_root):
        for folder in PRODUCTION_METHOD_DIRS:
            for path in sorted((root / folder).glob("*.txt")):
                text = _read(path)
                for block in blocks(path, text):
                    out[block.key] = bool(_PRODUCED_RE.search(text[block.open + 1: block.close]))
    return out


def has_output(body: str, shared: dict[str, bool]) -> bool:
    """A building body makes goods: one of its unique methods has ``produced``, or one of its shared methods does."""
    pairs = _brace_pairs(body)
    for match in _UNIQUE_RE.finditer(body):
        open_ = match.end() - 1
        if _PRODUCED_RE.search(body[open_ + 1: pairs.get(open_, open_)]):
            return True
    for match in _METHOD_LIST_RE.finditer(body):
        if any(shared.get(name) for name in re.findall(r"[A-Za-z_0-9]+", match.group("body"))):
            return True
    return False


def set_flags(body: str, lock: bool, inherited: str = "") -> str:
    """Drop the marked flag lines; when locking, add them as top-level lines at the end of the body. inherited is
    the vanilla definition an INJECT adds to: a flag it already sets is not repeated (the engine drops INJECT dupes)."""
    body = _FLAG_LINE_RE.sub("", body)
    if not lock:
        return body
    tops = _depth_zero_text(body) + "\n" + (_depth_zero_text(inherited) if inherited else "")
    indent = "\t"
    for line in body.splitlines():
        if line.strip() and not line.strip().startswith("#"):
            indent = line[: len(line) - len(line.lstrip())] or "\t"
            break
    lines = "".join(f"{indent}{key} = {value} {MARKER}\n" for key, value in FLAGS if not _ANY_FLAG_RE[key].search(tops))
    head = body.rstrip(" \t")
    return head + ("" if head.endswith("\n") or not head else "\n") + lines


def apply(repo: Path, mod_root: Path, project: Path, vanilla_root: Path) -> ShutdownResult:
    config = load_config(project)
    errors = validate(repo, config)
    if errors:
        raise ValueError("building shutdown:\n" + "\n".join(f"- {e}" for e in errors))
    shared = producing_methods(vanilla_root, mod_root)
    vanilla = vanilla_definitions(vanilla_root)
    owners = owner_blocks(mod_root, vanilla_root)
    result = ShutdownResult()
    edits: dict[Path, list[tuple[object, bool, str]]] = {}
    for key, (footprint, override, _path) in sorted(blueprint_rules(repo).items()):
        block = owners.get(key)
        if block is None:
            result.not_in_mod.append(key)
            continue
        text = _read(block.path)
        body = text[block.open + 1: block.close]
        # an INJECT adds to the vanilla definition: the building's methods are the union
        full = body + ("\n" + vanilla.get(key, "") if block.mode in _INJECT else "")
        lock = rule(config, footprint, override) == NEVER
        if lock and has_output(full, shared):
            result.producing_skipped += 1
            lock = False
        elif lock:
            result.locked.append(key)
        else:
            result.kept += 1
        inherited = vanilla.get(key, "") if block.mode in _INJECT else ""
        edits.setdefault(block.path, []).append((block, lock, inherited))
    for path, items in edits.items():
        original = _read(path)
        text = original
        for block, lock, inherited in sorted(items, key=lambda item: -item[0].open):
            body = text[block.open + 1: block.close]
            text = text[: block.open + 1] + set_flags(body, lock, inherited) + text[block.close:]
        if text != original:
            path.write_text(text, encoding="utf-8-sig", newline="\n")
            result.files_changed += 1
    return result


def check(repo: Path, mod_root: Path, project: Path, vanilla_root: Path) -> list[str]:
    """Problems: config errors, and locked buildings in the compiled mod without both flags (run ppc build/sync)."""
    config = load_config(project)
    problems = validate(repo, config)
    if problems:
        return problems
    shared = producing_methods(vanilla_root, mod_root)
    vanilla = vanilla_definitions(vanilla_root)
    owners = owner_blocks(mod_root, vanilla_root)
    for key, (footprint, override, path) in sorted(blueprint_rules(repo).items()):
        block = owners.get(key)
        if block is None or rule(config, footprint, override) != NEVER:
            continue
        text = _read(block.path)
        body = text[block.open + 1: block.close]
        full = body + ("\n" + vanilla.get(key, "") if block.mode in _INJECT else "")
        if has_output(full, shared):
            continue
        tops = _depth_zero_text(body) + ("\n" + _depth_zero_text(vanilla.get(key, "")) if block.mode in _INJECT else "")
        missing = [k for k, v in FLAGS if not (m := _ANY_FLAG_RE[k].search(tops)) or m.group("value") != v]
        if missing:
            problems.append(f"{key} ({path.name}): {', '.join(missing)} not written (run ppc build)")
    return problems

