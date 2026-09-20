"""Guards the baked population baseline that the pop-delta map modes read."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
BASE_DATA = (
    MOD_ROOT
    / "in_game"
    / "common"
    / "scripted_effects"
    / "pp_population_baseline_base_data.txt"
)
GAME_START = MOD_ROOT / "in_game" / "common" / "on_action" / "pp_game_start.txt"
EVENTS = MOD_ROOT / "in_game" / "events" / "debug" / "pp_population_baseline_debug.txt"
DEBUG_LOC = MOD_ROOT / "main_menu" / "localization" / "english" / "pp_debug_l_english.yml"

SCOPE_VARIABLES = (
    "pp_pop_baseline",
    "pp_province_pop_baseline",
    "pp_area_pop_baseline",
    "pp_region_pop_baseline",
    "pp_macro_region_pop_baseline",
    "pp_super_region_pop_baseline",
)

# Slugs are mostly lowercase, but a few carry an uppercase country suffix (al_khadra_ALG).
LINE = re.compile(r"^location:([A-Za-z_0-9]+) = \{ (.*) \}$")


def _rows() -> list[tuple[str, str]]:
    rows = []
    for line in BASE_DATA.read_text(encoding="utf-8-sig").splitlines():
        if not line.startswith("location:"):
            continue
        match = LINE.match(line)
        assert match, f"malformed row: {line[:80]}"
        rows.append((match.group(1), match.group(2)))
    return rows


def test_base_data_is_a_single_well_formed_effect() -> None:
    text = BASE_DATA.read_text(encoding="utf-8-sig")

    assert text.count("{") == text.count("}")
    assert "pp_load_base_population_baselines = {" in text
    # Exactly one effect: the opening line plus one closing brace at column 0.
    assert len(re.findall(r"^[a-z_0-9]+ = \{$", text, flags=re.MULTILINE)) == 1


def test_every_row_sets_all_six_scopes_with_positive_values() -> None:
    rows = _rows()
    assert len(rows) > 15000, f"suspiciously few locations: {len(rows)}"

    slugs = [slug for slug, _ in rows]
    assert len(slugs) == len(set(slugs)), "duplicate location rows"
    assert slugs == sorted(slugs), "rows are not sorted by slug"

    bad: list[str] = []
    for slug, body in rows:
        values = dict(
            re.findall(r"set_variable = \{ name = ([a-z_]+) value = (-?[\d.]+) \}", body)
        )
        if tuple(values) != SCOPE_VARIABLES:
            bad.append(f"{slug}: scopes {tuple(values)}")
            continue
        numbers = {name: float(raw) for name, raw in values.items()}
        if any(value <= 0 for value in numbers.values()):
            bad.append(f"{slug}: non-positive {numbers}")
        # A parent can never hold less population than the location inside it.
        if not (
            numbers["pp_pop_baseline"]
            <= numbers["pp_province_pop_baseline"]
            <= numbers["pp_area_pop_baseline"]
            <= numbers["pp_region_pop_baseline"]
            <= numbers["pp_macro_region_pop_baseline"]
            <= numbers["pp_super_region_pop_baseline"]
        ):
            bad.append(f"{slug}: parent scopes not monotonic {numbers}")

    assert not bad, bad[:5]


def test_baseline_is_loaded_at_game_start_and_via_console_event() -> None:
    start = GAME_START.read_text(encoding="utf-8-sig")
    events = EVENTS.read_text(encoding="utf-8-sig")
    loc = DEBUG_LOC.read_text(encoding="utf-8-sig")

    assert "pp_load_base_population_baselines_on_start" in start
    assert "pp_load_base_population_baselines = yes" in start
    # Runs once per campaign, so a reloaded save keeps whatever baseline it already has.
    assert "has_global_variable = pp_pop_baseline_snapshot_taken" in start

    # .1 rebases on current population, .2 restores the reference baseline.
    assert "pp_snapshot_population_baselines = yes" in events
    assert "pp_load_base_population_baselines = yes" in events
    for key in (
        "pp_population_baseline_debug.2.title",
        "pp_population_baseline_debug.2.desc",
        "pp_population_baseline_debug.2.a",
    ):
        assert key in loc, key
