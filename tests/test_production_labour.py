from __future__ import annotations

from pathlib import Path

import pytest

from prosper_or_perish_constructor import production_labour as pl

ROOT = Path(__file__).resolve().parents[1]

CONFIG = """
[production_labour]
good = "manual_labor"
price_floor_share = 0.2
tolerance = 0.02
min_good_share = 0.05
max_goods = 3

[production_labour.classes]
keep = "keep"
base = { output_share = 0.20 }
craft = 0.20
"""

PRICES = {"manual_labor": 5.0, "wheat": 1.0, "lumber": 2.0, "tools": 4.0, "stone": 1.0, "alum": 3.0, "beer": 2.0, "sand": 0.5}

BREWERY = """version: 2
tag: brewery
footprint: manufactory
labour:
  class: craft
  methods:
    pp_brewery_base: base
    pp_brewery_market: keep
building:
  key: brewery
  mode: REPLACE
  body: |
    pop_type = burghers
    unique_production_methods = {
        pp_brewery_base = {
            produced = beer
            output = 0.5
            category = guild_input
        }
    }
    unique_production_methods = {
        pp_brewery_wheat = {
            wheat = 1.0 # malt
            lumber = 0.25
            tools = 0.125
            stone = 0.0
            produced = beer
            output = 1.0
            category = guild_input
        }
        pp_brewery_market = {
            wheat = 2
            manual_labor = 0.3
            produced = beer
            output = 1.0
        }
        pp_brewery_idle = {
            category = guild_input
        }
    }
localization:
  entries:
    pp_brewery_wheat: Wheat Brewery
"""


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "constructor.toml").write_text(CONFIG, encoding="utf-8")
    folder = tmp_path / pl.BLUEPRINT_ROOT_RELATIVE / "buildings"
    folder.mkdir(parents=True)
    (folder / "brewery.yml").write_text(BREWERY, encoding="utf-8")
    (tmp_path / pl.MANIFEST_RELATIVE).write_text("enabled:\n  buildings/brewery.yml: true\n", encoding="utf-8")
    return tmp_path


def _methods(repo: Path) -> dict[str, pl.Method]:
    return {m.name: m for m in pl.blueprint_methods(repo / pl.BLUEPRINT_ROOT_RELATIVE / "buildings/brewery.yml")}


def test_config_classes(repo: Path) -> None:
    config = pl.load_config(repo / "constructor.toml")
    assert config.classes["keep"].keep
    assert config.classes["base"].output_share == 0.20
    assert config.classes["craft"].share == 0.20
    assert config.max_goods == 3


def test_nice_rounds_to_readable_steps() -> None:
    assert pl.nice(1.109) == 1.1
    assert pl.nice(1.13) == 1.15
    assert pl.nice(0.277) == 0.28
    assert pl.nice(0.0123) == 0.012
    assert pl.nice(1.13, pl.GOODS_STEPS) == 1.13
    assert pl.nice(12.34) == 12.3
    assert pl.nice(0.0) == 0.0


def test_apply_moves_the_class_share_onto_labour_and_keeps_the_cost(repo: Path) -> None:
    before = _methods(repo)["pp_brewery_wheat"]
    cost_before = sum(a * PRICES[g] for g, a in before.inputs.items())
    result = pl.apply(repo, repo / "constructor.toml", PRICES)
    assert not result.problems
    after = _methods(repo)["pp_brewery_wheat"]
    labour = after.inputs["manual_labor"]
    cost_after = sum(a * (PRICES[g] * (0.2 if g == "manual_labor" else 1)) for g, a in after.inputs.items())
    assert cost_after == pytest.approx(cost_before, abs=0.01)
    assert labour * 1.0 / cost_after == pytest.approx(0.20, abs=0.01)
    assert after.inputs["stone"] == 0.0  # zero lines stay
    text = (repo / pl.BLUEPRINT_ROOT_RELATIVE / "buildings/brewery.yml").read_text(encoding="utf-8")
    assert "wheat = 0.8 # malt" in text  # comments survive
    # the new labour line follows the last goods line, inside the literal block
    assert "            stone = 0.0\n            manual_labor = 0.4\n" in text


def test_base_methods_pay_labour_worth_a_share_of_their_output(repo: Path) -> None:
    pl.apply(repo, repo / "constructor.toml", PRICES)
    base = _methods(repo)["pp_brewery_base"]
    # 20 % of 0.5 beer x 2 gold = 0.2 gold = 0.2 labour at 1 gold
    assert base.inputs == {"manual_labor": 0.2}


def test_keep_methods_and_idle_methods_are_untouched(repo: Path) -> None:
    pl.apply(repo, repo / "constructor.toml", PRICES)
    methods = _methods(repo)
    assert methods["pp_brewery_market"].inputs == {"wheat": 2.0, "manual_labor": 0.3}
    assert methods["pp_brewery_idle"].inputs == {}


def test_apply_is_stable(repo: Path) -> None:
    first = pl.apply(repo, repo / "constructor.toml", PRICES)
    assert {p.method.name for p in first.changed} == {"pp_brewery_wheat", "pp_brewery_base"}
    assert first.files_changed == 1
    text = (repo / pl.BLUEPRINT_ROOT_RELATIVE / "buildings/brewery.yml").read_text(encoding="utf-8")
    assert not pl.apply(repo, repo / "constructor.toml", PRICES, write=False).changed
    second = pl.apply(repo, repo / "constructor.toml", PRICES)
    assert not second.changed
    assert (repo / pl.BLUEPRINT_ROOT_RELATIVE / "buildings/brewery.yml").read_text(encoding="utf-8") == text


def test_small_goods_and_goods_beyond_max_are_dropped(repo: Path) -> None:
    path = repo / pl.BLUEPRINT_ROOT_RELATIVE / "buildings/brewery.yml"
    path.write_text(
        BREWERY.replace("            tools = 0.125\n", "            tools = 0.125\n            alum = 0.01\n            sand = 0.2\n"),
        encoding="utf-8",
    )
    result = pl.apply(repo, repo / "constructor.toml", PRICES)
    plan = next(p for p in result.plans if p.method.name == "pp_brewery_wheat")
    # alum (0.03 gold of 2.13) is under 5 %; sand (0.1 gold) is the fourth good with max_goods = 3
    assert plan.dropped == ["alum", "sand"]
    assert set(_methods(repo)["pp_brewery_wheat"].inputs) == {"wheat", "lumber", "tools", "stone", "manual_labor"}


def test_check_reports_untagged_and_unknown_classes(repo: Path) -> None:
    path = repo / pl.BLUEPRINT_ROOT_RELATIVE / "buildings/brewery.yml"
    path.write_text(BREWERY.replace("  class: craft\n", "").replace("pp_brewery_market: keep", "pp_brewery_market: nope"), encoding="utf-8")
    result = pl.apply(repo, repo / "constructor.toml", PRICES, write=False)
    assert any("pp_brewery_wheat has no labour class" in p for p in result.problems)
    assert any("'nope' is not in" in p for p in result.problems)


def test_methods_producing_labour_are_not_labour_methods() -> None:
    method = pl.Method(Path("x.yml"), "yard", "pp_yard", {"victuals": 2.0}, "manual_labor", 8.0)
    assert not pl.is_labour_method(method, "manual_labor")


def test_every_enabled_producing_method_is_tagged_and_on_its_class() -> None:
    result = pl.apply(ROOT, ROOT / "constructor.toml", write=False)
    assert result.problems == []
    assert [f"{p.method.blueprint.name}: {p.method.name}" for p in result.changed] == []
