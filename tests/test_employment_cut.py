"""Workers per level (2026-10-03, Jan): [building_scaling.employment_cut], the footprint at the reference, the Cookshop
counters in raw_modifier, farms open to estates, the estate price multiplier."""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

from prosper_or_perish_constructor import building_footprint, building_scaling

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "constructor.toml"
MOD = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
BUILDING_TYPES = MOD / "in_game" / "common" / "building_types"
BLUEPRINTS = ROOT / "blueprints" / "accepted" / "buildings"
COUNTER = re.compile(r"^[ \t]*local_pp_(farm|staple)_levels\s*=", re.M)


def test_config_cuts_laborers_and_burghers() -> None:
    cuts = building_scaling.load_employment_cut(PROJECT)
    assert cuts["laborers"] == building_scaling.EmploymentCut(Decimal("1.0"), Decimal("0.8"))
    assert cuts["burghers"] == building_scaling.EmploymentCut(Decimal("0.3"), Decimal("0.25"))
    assert "peasants" not in cuts   # farms keep their crews


def test_footprint_reads_the_reference_of_a_cut_line() -> None:
    body = "\n\tpop_type = laborers\n\temployment_size = 0.8   # [building_scaling.employment_cut] reference 1\n"
    assert building_footprint._employment(body) == "1"
    assert building_footprint._employment("\n\temployment_size = 0.8\n") == "0.8"


def test_compiled_buildings_carry_the_cut_with_its_reference() -> None:
    cut_lines = []
    for path in sorted(BUILDING_TYPES.glob("zz_pp_*.txt")):
        for match in re.finditer(r"employment_size = (\S+)\s+# \[building_scaling\.employment_cut\] reference (\S+)",
                                 path.read_text(encoding="utf-8-sig")):
            cut_lines.append((path.name, match.group(1), match.group(2)))
    # > 150 before 2026-10-06; the manufacturing tiers 2+ of the refined end goods carry their own size since then
    assert len(cut_lines) > 120
    assert {(new, ref) for _name, new, ref in cut_lines} <= {("0.8", "1"), ("0.25", "0.3")}


def test_cookshop_counters_count_standing_levels() -> None:
    """The counters sit in raw_modifier (staffing ignored), never in the staffing-scaled modifier block."""
    carriers = 0
    for path in sorted(BLUEPRINTS.glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        modifier = re.search(r"^[ \t]*modifier\s*=\s*\{(?P<body>.*?)^[ \t]*\}", text, re.M | re.S)
        if modifier:
            assert not COUNTER.search(modifier.group("body")), path.name
        raw = re.search(r"^[ \t]*raw_modifier\s*=\s*\{(?P<body>.*?)^[ \t]*\}", text, re.M | re.S)
        carriers += bool(raw and COUNTER.search(raw.group("body")))
    assert carriers >= 32 + 11   # every crop farm tier, the orchards, fisheries and flocks


def test_estates_may_build_crop_farms_and_pay_twice() -> None:
    assert "forbidden_for_estates = no" in (BUILDING_TYPES / "zz_pp_wheat_farm_tier0.txt").read_text(encoding="utf-8-sig")
    defines = (MOD / "loading_screen" / "common" / "defines" / "pp_defines_adjustments.txt").read_text(encoding="utf-8-sig")
    assert re.search(r"^\s*ESTATE_MAX_PRICE_MULTIPLIER = 2\.0\b", defines, re.M)
