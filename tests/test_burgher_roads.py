from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
GRANT = re.compile(r"^\s*nobles_estate_allowed_to_build_roads\s*=\s*yes", re.M)
TOP_LEVEL = re.compile(r"^(?:[A-Z_]+:)?(\w+)\s*=\s*\{", re.M)


def script_files(root: Path) -> list[Path]:
    return [p for d in ("in_game/common", "main_menu/common") for p in (root / d).rglob("*.txt")]


def granting_definitions(path: Path) -> set[str]:
    """Top-level definitions in the file whose body grants the nobles road building."""
    text = re.sub(r"#[^\n]*", "", path.read_text(encoding="utf-8-sig", errors="replace"))
    found = set()
    for grant in GRANT.finditer(text):
        owners = [m.group(1) for m in TOP_LEVEL.finditer(text, 0, grant.start())]
        if owners:
            found.add(owners[-1])
    return found


def vanilla_game_root() -> Path | None:
    raw = tomllib.loads((ROOT / "constructor.load_order.toml").read_text(encoding="utf-8"))["paths"]["vanilla_root"]
    for candidate in (Path(raw), Path("/mnt/c") / Path(raw.replace("\\", "/")[3:])):
        if (candidate / "game").is_dir():
            return candidate / "game"
    return None


def test_mod_never_grants_nobles_road_building() -> None:
    offenders = {p.relative_to(MOD_ROOT).as_posix(): granting_definitions(p) for p in script_files(MOD_ROOT)}
    assert {k: v for k, v in offenders.items() if v} == {}


def test_every_vanilla_noble_road_grant_is_replaced() -> None:
    game = vanilla_game_root()
    if game is None:
        pytest.skip("EU5 install not found")
    vanilla = set().union(*(granting_definitions(p) for p in script_files(game)))
    replaced = set()
    for path in script_files(MOD_ROOT):
        replaced |= set(re.findall(r"^(?:TRY_)?REPLACE:(\w+)\s*=", path.read_text(encoding="utf-8-sig"), re.M))
    assert vanilla, "vanilla grants not found; the scan is broken"
    assert vanilla - replaced == set()
