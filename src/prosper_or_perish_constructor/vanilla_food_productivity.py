"""Net vanilla food productivity per object: Prosper or Perish keeps it at exactly 0.

The mod has no vanilla food productivity (food comes from farms, crops and storage). EU5 1.4 writes almost every
vanilla food percentage as a named script value ``monthly_food_productivity_<tier>``; the mod sets all of them to 0
(``main_menu/common/script_values/pp_food_productivity_nil.txt``). The few plain numbers left, and the 1.4
multiplier ``local_food_production_mult``, are cancelled where they are defined (an INJECT of the negative, or a
REPLACE without the line). A cancelling negative written against an older plain number would push food below zero
once vanilla switched that object to a zeroed script value, so the merged result is checked, not the patch files.

``food_productivity_rows`` merges every database folder over vanilla and the mod the way the engine does
(``eu5gameparser.load_order.load_merged_directory``; the mod's ``in_game/common/static_modifiers`` patch the same
static modifiers as ``main_menu``) and sums each food key per modifier block, resolving script values.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from eu5gameparser.clausewitz.parser import parse_file
from eu5gameparser.clausewitz.syntax import CList
from eu5gameparser.load_order import DataProfile, GameLayer, LoadOrderConfig, load_merged_directory

FOOD_PRODUCTIVITY_KEYS = ("local_monthly_food_modifier", "global_monthly_food_modifier", "local_food_production_mult")
FOOD_SCRIPT_VALUE_PREFIX = "monthly_food_productivity_"
NIL_SCRIPT_VALUES_PATH = Path("main_menu/common/script_values/pp_food_productivity_nil.txt")
SKIPPED_DIRS = {"script_values", "modifier_type_definitions", "modifier_icons"}


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


def script_values(*roots: Path) -> dict[str, float]:
    """Plain-number script values under ``<root>/{main_menu,in_game}/common/script_values``; later roots win."""
    values: dict[str, float] = {}
    for root in roots:
        for scope in ("main_menu", "in_game"):
            folder = Path(root) / scope / "common" / "script_values"
            for path in sorted(folder.glob("*.txt")) if folder.is_dir() else ():
                for entry in parse_file(path).entries:
                    if isinstance(entry.value, (int, float)) and not isinstance(entry.value, bool):
                        values[entry.key.split(":", 1)[-1]] = float(entry.value)
    return values


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
