"""Net vanilla food productivity per object: Prosper or Perish keeps it at exactly 0.

The mod has no vanilla food productivity (food comes from farms, crops and storage). EU5 1.4 writes almost every
vanilla food percentage as a named script value ``monthly_food_productivity_<tier>``; the mod sets all of them to 0.
The few plain numbers left, and the 1.4 multiplier ``local_food_production_mult``, are cancelled where they are
defined (an INJECT of the negative, or a REPLACE without the line). A cancelling negative written against an older
plain number would push food below zero once vanilla switched that object to a zeroed script value, so the merged
result is checked, not the patch files.

Script values in EU5 1.4 (in-game error.log, the executable and a 1.3 run, 2026-10-01): a scalar
``REPLACE:name = 0`` is read as the scope link ``replace:name`` (error.log: "Feeding data into an event target link
that doesn't require data. Link replace") and leaves vanilla's ``name`` untouched; that is why the first 1.4 nil
(``pp_food_productivity_nil.txt``) showed vanilla food percentages in game. ``REPLACE:name = { ... }`` (block form) does
replace (the mod's building caps, levels above vanilla's cap in a 1.3 run). A plain redefinition is rejected at load
("Duplicated key ... will not be created"): the first definition wins (files sorted by name, a mod file of the same
relative path replacing vanilla's), while a hot reload re-creates every entry in that order, so there the last one
wins. The mod therefore replaces the vanilla file by its name, which holds whatever the rule:
``write_nil_script_values`` (``ppc build``/``sync`` finalize) writes vanilla's ``default_values.txt`` (every vanilla
script value file that defines a food value) into the mod, byte for byte, with those values set to 0, and
``script_values`` resolves names by the rule above.

``food_productivity_rows`` merges every database folder over vanilla and the mod the way the engine does
(``eu5gameparser.load_order.load_merged_directory``; the mod's ``in_game/common/static_modifiers`` patch the same
static modifiers as ``main_menu``) and sums each food key per modifier block, resolving script values.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from eu5gameparser.clausewitz.parser import parse_file
from eu5gameparser.clausewitz.syntax import CList
from eu5gameparser.load_order import DataProfile, GameLayer, LoadOrderConfig, load_merged_directory

FOOD_PRODUCTIVITY_KEYS = ("local_monthly_food_modifier", "global_monthly_food_modifier", "local_food_production_mult")
FOOD_SCRIPT_VALUE_PREFIX = "monthly_food_productivity_"
SCRIPT_VALUE_SCOPES = ("main_menu", "in_game")
NIL_SCRIPT_VALUES_PATH = Path("main_menu/common/script_values/default_values.txt")   # same name as vanilla's: replaces it
LEGACY_NIL_PATHS = (Path("main_menu/common/script_values/pp_food_productivity_nil.txt"),)   # scalar REPLACE:, ignored
SKIPPED_DIRS = {"script_values", "modifier_type_definitions", "modifier_icons"}
_FOOD_VALUE_LINE = re.compile(
    rf"^(?P<head>\ufeff?[ \t]*{FOOD_SCRIPT_VALUE_PREFIX}[A-Za-z0-9_]*[ \t]*=[ \t]*)(?P<value>[-+]?\d+(?:\.\d+)?)(?P<tail>[ \t]*(?:#[^\r\n]*)?\r?)$",
    re.M,
)
_FOOD_KEY = re.compile(rf"(?<![A-Za-z0-9_:.]){FOOD_SCRIPT_VALUE_PREFIX}[A-Za-z0-9_]*\s*=")


@dataclass(frozen=True)
class _InGameStaticModifiersLayer(GameLayer):
    """The mod's ``in_game/common/static_modifiers`` files, read as a later layer of the main_menu folder."""

    def common_dir_for(self, scope: str = "in_game") -> Path:
        return self.root / "in_game" / "common"


@dataclass(frozen=True)
class FoodRow:
    scope: str
    directory: str
    obj: str
    in_vanilla: bool
    source: str          # mode and file of the object's last definition or patch
    block: str           # path of the modifier block inside the object ("" = top level)
    key: str
    vanilla: float       # vanilla value (vanilla script values)
    net: float           # value with the mod loaded (the mod's script values)
    raw: tuple[str, ...]  # the merged right-hand sides

    @property
    def unresolved(self) -> bool:
        return self.net != self.net  # NaN: a value that is neither a number nor a known script value


def script_value_files(*roots: Path | None) -> list[Path]:
    """The script value files the game loads, in load order: per scope folder (main_menu, then in_game), every
    file name of every root, a later root's file replacing an earlier root's file of the same name, sorted by name."""
    files: list[Path] = []
    for scope in SCRIPT_VALUE_SCOPES:
        by_name: dict[str, Path] = {}
        for root in roots:
            if root is None:
                continue
            folder = Path(root) / scope / "common" / "script_values"
            for path in folder.glob("*.txt") if folder.is_dir() else ():
                by_name[path.name] = path
        files.extend(by_name[name] for name in sorted(by_name))
    return files


def script_values(*roots: Path | None) -> dict[str, float]:
    """Plain-number script values as the game resolves them (``roots``: vanilla ``game`` folder, then mod roots).

    EU5 1.4 rule: a same-name file replaces the earlier root's file, files load sorted by name, and the first
    definition of a name wins (later plain ones are rejected as duplicated keys). ``REPLACE:name = { ... }`` (block
    form, in a file that sorts after the definition) replaces it; a scalar ``REPLACE:name = 0`` is read as the scope
    link ``replace:name`` and does nothing. Other prefixes are not modelled and change nothing here."""
    values: dict[str, float] = {}
    for path in script_value_files(*roots):
        for entry in parse_file(path).entries:
            prefix, _, name = entry.key.rpartition(":")
            value = entry.value
            if prefix:
                if prefix not in ("REPLACE", "TRY_REPLACE") or not isinstance(value, CList) or name not in values:
                    continue
            elif name in values:
                continue
            if isinstance(value, CList) and [e.key for e in value.entries] == ["value"]:
                value = value.entries[0].value   # `name = { value = N }`
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                values[name] = float(value)
            else:
                values[name] = float("nan")   # a formula: defined, but not a plain number
    return values


def nil_bytes(name: str, data: bytes) -> tuple[bytes, int]:
    """A vanilla script value file, byte for byte, with every food productivity value set to 0 (BOM, line endings,
    comments and every other value kept), and how many values were zeroed."""
    text = data.decode("utf-8")
    zeroed = 0

    def zero(match: re.Match[str]) -> str:
        nonlocal zeroed
        zeroed += 1
        return f"{match['head']}0{match['tail']}"

    out = _FOOD_VALUE_LINE.sub(zero, text)
    defined = sum(len(_FOOD_KEY.findall(line.split("#", 1)[0])) for line in text.splitlines())
    if defined != zeroed:
        raise ValueError(
            f"{name}: {defined} {FOOD_SCRIPT_VALUE_PREFIX}* definitions but {zeroed} plain-number lines; "
            "vanilla changed their form, extend vanilla_food_productivity.nil_bytes"
        )
    return out.encode("utf-8"), zeroed


def nil_script_value_files(vanilla_game: Path) -> dict[Path, tuple[bytes, int]]:
    """{mod-relative path: (bytes, zeroed)}: a same-name copy of every vanilla script value file that defines a food
    productivity value (EU5 1.4: ``main_menu/common/script_values/default_values.txt``)."""
    out: dict[Path, tuple[bytes, int]] = {}
    for scope in SCRIPT_VALUE_SCOPES:
        folder = Path(vanilla_game) / scope / "common" / "script_values"
        for path in sorted(folder.glob("*.txt")) if folder.is_dir() else ():
            data = path.read_bytes()
            if FOOD_SCRIPT_VALUE_PREFIX.encode() in data:
                nil, zeroed = nil_bytes(path.name, data)
                out[Path(scope) / "common" / "script_values" / path.name] = (zero_ramp_targets(nil), zeroed)
    return out


# Establishment (branch establishment-know-how, 2026-10-06): only the final-goods manufacturing lines ramp, with their
# own startup_ramp_target in the blueprints. Vanilla's shared ramp values (guilds, workshops, manufactories, mills,
# rural buildings) are 0 in the same-name copy, so every other building stays out of the system.
RAMP_TARGET_VALUES = ("guild", "workshop", "manufactory", "mills", "rural")
_RAMP_TARGET = re.compile(rb"(?m)^((?:" + b"|".join(k.encode() for k in RAMP_TARGET_VALUES) + rb")_startup_ramp_target\s*=\s*)\d+")


def zero_ramp_targets(data: bytes) -> bytes:
    return _RAMP_TARGET.sub(rb"\g<1>0", data)


@dataclass(frozen=True)
class NilResult:
    files: tuple[str, ...]
    zeroed: int
    files_changed: int
    removed: tuple[str, ...]


def write_nil_script_values(mod_root: Path, vanilla_game: Path) -> NilResult:
    """Write the zeroed same-name copies into the mod; remove stale copies and the old REPLACE: file."""
    wanted = nil_script_value_files(vanilla_game)
    if not wanted:
        raise ValueError(f"{vanilla_game}: no vanilla {FOOD_SCRIPT_VALUE_PREFIX}* script values; revisit the nil")
    changed = 0
    for rel, (data, _) in wanted.items():
        path = Path(mod_root) / rel
        if not path.is_file() or path.read_bytes() != data:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            changed += 1
    removed: list[str] = []
    for path in (Path(mod_root) / rel for rel in LEGACY_NIL_PATHS):
        if path.is_file():
            path.unlink()
            removed.append(str(path.relative_to(mod_root)))
    return NilResult(
        tuple(str(rel) for rel in wanted), sum(z for _, z in wanted.values()), changed + len(removed), tuple(removed)
    )


def _walk(value: object, path: str, sink: list[tuple[str, str, object]]) -> None:
    if not isinstance(value, CList):
        return
    seen: dict[str, int] = defaultdict(int)
    for entry in value.entries:
        index = seen[entry.key]
        seen[entry.key] += 1
        if entry.key in FOOD_PRODUCTIVITY_KEYS:
            sink.append((path, entry.key, entry.value))
        elif isinstance(entry.value, CList):
            _walk(entry.value, f"{path}/{entry.key}[{index}]" if path else f"{entry.key}[{index}]", sink)


def _resolve(value: object, values: dict[str, float]) -> float:
    if isinstance(value, bool):
        return float("nan")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value in values:
        return values[value]
    return float("nan")


def _mentions_food(folder: Path) -> bool:
    if not folder.is_dir():
        return False
    for path in folder.rglob("*.txt"):
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        if any(key in text for key in FOOD_PRODUCTIVITY_KEYS):
            return True
    return False


def food_productivity_rows(load_order_path: Path, mod_id: str = "constructor") -> list[FoodRow]:
    """Every food productivity key in every object, vanilla value and value with the mod, summed per block."""
    config = LoadOrderConfig.load(load_order_path)
    vanilla = config.layer("vanilla")
    mod = config.layer(mod_id)
    vanilla_game = config.vanilla_root / "game"
    values_vanilla = script_values(vanilla_game)
    values_mod = script_values(vanilla_game, mod.root)
    rows: list[FoodRow] = []
    for scope in ("main_menu", "in_game"):
        names: set[str] = set()
        for base in (vanilla_game / scope / "common", mod.root / scope / "common"):
            if base.is_dir():
                names |= {p.name for p in base.iterdir() if p.is_dir()}
        for directory in sorted(names - SKIPPED_DIRS):
            if (scope, directory) == ("in_game", "static_modifiers"):
                continue  # read with the main_menu folder
            folders = [vanilla_game / scope / "common" / directory, mod.root / scope / "common" / directory]
            extra: tuple[GameLayer, ...] = ()
            if (scope, directory) == ("main_menu", "static_modifiers"):
                folders.append(mod.root / "in_game/common/static_modifiers")
                extra = (_InGameStaticModifiersLayer(id=f"{mod_id}_in_game", name=mod.name, root=mod.root, kind="mod"),)
            if not any(_mentions_food(folder) for folder in folders):
                continue
            base = {e.key: e for e in load_merged_directory(DataProfile("vanilla", (vanilla,)), directory, scope=scope).entries}
            merged = {e.key: e for e in load_merged_directory(DataProfile(mod_id, (vanilla, mod, *extra)), directory, scope=scope).entries}
            for obj in sorted(set(base) | set(merged)):
                found_vanilla: list[tuple[str, str, object]] = []
                found_mod: list[tuple[str, str, object]] = []
                if obj in base:
                    _walk(base[obj].value, "", found_vanilla)
                if obj in merged:
                    _walk(merged[obj].value, "", found_mod)
                if not found_vanilla and not found_mod:
                    continue
                sums: dict[tuple[str, str], list] = defaultdict(lambda: [0.0, 0.0, []])
                for block, key, value in found_vanilla:
                    sums[(block, key)][0] += _resolve(value, values_vanilla)
                for block, key, value in found_mod:
                    sums[(block, key)][1] += _resolve(value, values_mod)
                    sums[(block, key)][2].append(str(value))
                source = f"{merged[obj].source_mode}:{Path(merged[obj].source_file).name}" if obj in merged else "-"
                for (block, key), (v, n, raw) in sums.items():
                    rows.append(FoodRow(scope, directory, obj, obj in base, source, block, key, v, n, tuple(raw)))
    return rows
