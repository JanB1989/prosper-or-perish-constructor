from pathlib import Path

from prosper_or_perish_constructor.worldbuilder import buildings as b
from prosper_or_perish_constructor.worldbuilder.contract import load_config


ROOT = Path(__file__).resolve().parents[1]


def test_field_management_tiers_upgrade_in_order():
    cfg = load_config(ROOT, ROOT / "constructor.toml")
    assert b.lower_tiers(cfg, "field_management_convertible") == ["field_management"]
    assert b.lower_tiers(cfg, "field_management_improved") == ["field_management_convertible", "field_management"]
    assert b.lower_tiers(cfg, "jiangnan_hill_terraces") == []


def test_tier_caps_leave_the_levels_they_convert_out():
    caps = (ROOT / "mod/Prosper or Perish (Population Growth & Food Rework)" / b.CAPS_PATH).read_text(encoding="utf-8-sig")
    blocks = {block.split(" = {", 1)[0]: block for block in caps.split("\n\n") if block.startswith("pp_wb_cap_field_management")}
    base = blocks["pp_wb_cap_field_management"]
    assert "pp_wb_levels_field_management_convertible" in base and "pp_wb_levels_field_management_improved" in base
    convertible = blocks["pp_wb_cap_field_management_convertible"]
    assert "modifier:pp_wb_levels_field_management\n" not in convertible
    assert "pp_wb_levels_field_management_improved" in convertible
    improved = blocks["pp_wb_cap_field_management_improved"]
    assert "pp_wb_levels_field_management\n" not in improved and "field_management_convertible" not in improved
    assert "pp_wb_levels_jiangnan_hill_terraces" in improved
