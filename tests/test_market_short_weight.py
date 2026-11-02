"""[market_short_weight] -> the last line of every producer's ai_construct_weight (src/prosper_or_perish_constructor/market_short_weight.py)."""

from __future__ import annotations

from pathlib import Path

from prosper_or_perish_constructor import market_short_weight as msw
from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "constructor.toml"
MOD = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
CONFIG = msw.Config(amount=20, demand_floor=1, tax_base_full=2000, not_goods=frozenset({"offset", "logistics", "local_food"}))
PRICES = {"iron": 3.0, "dyes": 8.0, "tools": 6.0}


def method(name: str, produced: str | None, output: float) -> msw.Method:
    return msw.Method(name, produced, output)


def test_built_mod_is_in_step() -> None:
    result = msw.apply(PROJECT, MOD, vanilla_root(ROOT, PROJECT), write=False)
    assert result.files_changed == 0, "run ppc finalize"
    assert result.not_in_mod == []
    assert result.producers > 200
    assert result.main_good["iron_mine"] == "iron"


def test_main_good_is_the_market_leg_else_the_largest_output_by_value() -> None:
    leg = [[method("a", "dyes", 5.0)], [method("pp_x_market_sales", "iron", 0.1)]]
    assert msw.main_good(leg, PRICES, CONFIG.not_goods) == "iron"
    no_leg = [[method("a", "iron", 2.0), method("b", "tools", 1.5)]]
    assert msw.main_good(no_leg, PRICES, CONFIG.not_goods) == "tools"


def test_dummy_outputs_make_no_producer() -> None:
    assert msw.main_good([[method("a", "offset", 1.0), method("b", "local_food", 9.0)]], PRICES, CONFIG.not_goods) is None
    assert msw.main_good([[method("a", None, 0.0)]], PRICES, CONFIG.not_goods) is None


def test_value_reads_stock_against_demand_and_the_owner_tax_base() -> None:
    text = msw.render_value("iron", CONFIG)
    assert text.startswith("pp_market_short_iron = {")
    assert '"goods_demand_in_market(goods:iron)" > 1' in text
    assert 'subtract = { value = "market.stockpile_in_market(goods:iron)" divide = "market.goods_demand_in_market(goods:iron)" }' in text
    assert "multiply = 20" in text
    assert "multiply = { value = owner.country_tax_base divide = 2000 max = 1 }" in text
    assert msw.parse(text)[0].key == "pp_market_short_iron"


def _mod(tmp_path: Path, building: str) -> Path:
    (tmp_path / "game").mkdir()
    mod = tmp_path / "mod"
    for folder in (msw.GOODS, msw.PRODUCTION_METHODS, msw.BUILDING_TYPES):
        (mod / folder).mkdir(parents=True)
    (mod / msw.GOODS / "goods.txt").write_text("iron = { default_market_price = 3 }\n", encoding="utf-8")
    (mod / msw.BUILDING_TYPES / "b.txt").write_text(building, encoding="utf-8")
    return mod


def _config(tmp_path: Path) -> Path:
    project = tmp_path / "constructor.toml"
    project.write_text('[market_short_weight]\namount = 20\ndemand_floor = 1\ntax_base_full = 2000\nnot_goods = ["offset"]\n', encoding="utf-8")
    return project


METHODS = "unique_production_methods = { m = { produced = iron output = 1 } }"


def test_term_goes_last_in_the_weight_and_a_rerun_changes_nothing(tmp_path: Path) -> None:
    mod = _mod(tmp_path, f"mine = {{\n{METHODS}\nai_construct_weight = {{\n    value = 5\n    divide = 2\n}}\n}}\n")
    project = _config(tmp_path)
    assert msw.apply(project, mod, tmp_path).new_blocks == 0
    text = (mod / msw.BUILDING_TYPES / "b.txt").read_text(encoding="utf-8")
    assert "    divide = 2\n    add = pp_market_short_iron\n}" in text
    assert msw.apply(project, mod, tmp_path).files_changed == 0
    assert (mod / msw.BUILDING_TYPES / "b.txt").read_text(encoding="utf-8") == text


def test_weight_on_one_line_keeps_the_line(tmp_path: Path) -> None:
    mod = _mod(tmp_path, f"mine = {{\n{METHODS}\nai_construct_weight = {{ value = 5 }}\n}}\n")
    msw.apply(_config(tmp_path), mod, tmp_path)
    assert "ai_construct_weight = { value = 5  add = pp_market_short_iron }" in (mod / msw.BUILDING_TYPES / "b.txt").read_text(encoding="utf-8")


def test_producer_without_a_weight_gets_a_block_and_others_nothing(tmp_path: Path) -> None:
    mod = _mod(tmp_path, f"mine = {{\n{METHODS}\n}}\nfort = {{\nprice = x\n}}\n")
    result = msw.apply(_config(tmp_path), mod, tmp_path)
    assert result.new_blocks == 1 and result.main_good == {"mine": "iron"}
    text = (mod / msw.BUILDING_TYPES / "b.txt").read_text(encoding="utf-8")
    assert "ai_construct_weight = {\n    value = 0\n    add = pp_market_short_iron\n}\n}\nfort = {\nprice = x\n}" in text
    assert (mod / msw.OUTPUT).read_text(encoding="utf-8").count("pp_market_short_iron = {") == 1


def test_a_bom_is_not_part_of_the_first_key(tmp_path: Path) -> None:
    mod = _mod(tmp_path, "")
    (mod / msw.BUILDING_TYPES / "b.txt").write_bytes(("﻿" + f"REPLACE:mine = {{\n{METHODS}\n}}\n").encode("utf-8"))
    result = msw.apply(_config(tmp_path), mod, tmp_path)
    assert result.main_good == {"mine": "iron"}
    assert (mod / msw.BUILDING_TYPES / "b.txt").read_bytes().startswith("﻿".encode("utf-8") + b"REPLACE:mine")


def test_crlf_files_stay_crlf(tmp_path: Path) -> None:
    mod = _mod(tmp_path, "")
    (mod / msw.BUILDING_TYPES / "b.txt").write_bytes(f"mine = {{\r\n{METHODS}\r\nai_construct_weight = {{\r\n    value = 5\r\n}}\r\n}}\r\n".encode())
    msw.apply(_config(tmp_path), mod, tmp_path)
    assert b"    add = pp_market_short_iron\r\n}" in (mod / msw.BUILDING_TYPES / "b.txt").read_bytes()
