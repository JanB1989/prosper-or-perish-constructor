"""debug_max_profit carries each method's base-price profit, so the engine's load check stays quiet."""
from prosper_or_perish_constructor import profit_margins as pm

PRICES = {"lumber": 1.0, "tar": 2.0, "manual_labor_cost": 1.0, "iron": 3.0, "tools": 3.0}
TARGETS = {"rural_profit_margin": 0.2}

BUILDING = """\
REPLACE:tar_kiln = {
    # unique_production_methods = { commented = { } }
    unique_production_methods = {
        pp_tar_kiln_maintenance = {
            produced = tar
            output = 1.0
            lumber = 0.91
            manual_labor_cost = 0.35
            debug_max_profit = rural_profit_margin
        }
        pp_tar_kiln_base = {
            manual_labor_cost = 0.5
            produced = tar
            output = 0.25
        }
        pp_tar_kiln_losing = {
            lumber = 1
            produced = tar
            output = 0.25
        }
    }
}
"""


def test_the_profit_is_output_value_over_input_cost_like_the_engine():
    # 2.0 / (0.91 + 0.35) - 1: the formula matched all 618 methods error.log listed on 2026-09-23
    assert round(pm.profit("{ produced = tar output = 1.0 lumber = 0.91 manual_labor_cost = 0.35 }", PRICES), 4) == 0.5873
    assert pm.profit("{ lumber = 0.1 }", PRICES) is None   # produces nothing: not checked


def test_keyed_and_flagged_mod_methods_get_their_profit_and_a_rerun_changes_nothing():
    text, count = pm.rewrite(BUILDING, PRICES, TARGETS, shared=False)
    assert count == 1
    assert "debug_max_profit = 0.587\n        }" in text and "rural_profit_margin" not in text
    assert "output = 0.25\n        }\n        pp_tar_kiln_losing" in text   # break-even base method: untouched
    assert "output = 0.25\n        }\n    }" in text   # losing method: no key silences it, left as authored
    assert "# unique_production_methods = { commented = { } }" in text
    assert pm.rewrite(text, PRICES, TARGETS, shared=False) == (text, 0)


def test_the_key_is_added_where_missing():
    body = "{\n\tproduced = tools\n\toutput = 0.5\n\tiron = 0.417\n}"
    assert pm.set_debug_profit(body, 0.2) == "{\n\tproduced = tools\n\toutput = 0.5\n\tiron = 0.417\n\tdebug_max_profit = 0.200\n}"
    assert pm.set_debug_profit("{ produced = tools output = 1 }", 0.2) == "{ produced = tools output = 1 debug_max_profit = 0.200 }"
    assert pm.set_debug_profit("{ debug_max_profit = rural_profit_margin produced = tools }", 0.2) == (
        "{ debug_max_profit = 0.200 produced = tools }"
    )


def test_the_engine_check_uses_named_targets_and_a_negative_target_counts_as_none():
    assert not pm.fails("{ debug_max_profit = rural_profit_margin }", 0.2 + 0.005, TARGETS)
    assert pm.fails("{ debug_max_profit = rural_profit_margin }", 0.113, TARGETS)
    assert not pm.fails("{ debug_max_profit = -1 }", 5.0, TARGETS)
    assert pm.fails("{ debug_max_profit = -0.4 }", -0.4, TARGETS)   # the 2026-09-23 start still flagged these
    assert pm.fails("{ }", -0.01, TARGETS) and not pm.fails("{ }", 0.0, TARGETS)


def test_flagged_vanilla_shared_methods_are_replaced_and_unique_ones_are_only_counted(tmp_path):
    mod, vanilla = tmp_path / "mod", tmp_path / "vanilla"
    for root in (mod, vanilla / "game"):
        (root / pm.BUILDING_TYPES).mkdir(parents=True)
        (root / pm.PRODUCTION_METHODS).mkdir(parents=True)
    (vanilla / "game/in_game/common/script_values").mkdir(parents=True)
    (vanilla / "game/in_game/common/script_values/margins.txt").write_text("rural_profit_margin = 0.2\n")
    (vanilla / "game" / pm.PRODUCTION_METHODS / "village.txt").write_text(
        "in_band = { produced = tools output = 0.5 iron = 0.417 debug_max_profit = rural_profit_margin }\n"
        "off_band = { produced = tools output = 0.5 iron = 0.5 debug_max_profit = rural_profit_margin }\n"
        "mod_owned = { produced = tar output = 0.1 lumber = 1 }\n")
    (mod / pm.PRODUCTION_METHODS / "pp_mod.txt").write_text("TRY_REPLACE:mod_owned = { produced = tar output = 1 lumber = 1 }\n")
    (vanilla / "game" / pm.BUILDING_TYPES / "production_tar.txt").write_text(BUILDING.replace("REPLACE:", ""))

    result = pm.apply(mod, vanilla, PRICES)

    assert result.vanilla_replaced == ["off_band"]
    assert pm._read(mod / pm.GENERATED_PATH).endswith(
        "TRY_REPLACE:off_band = { produced = tools output = 0.5 iron = 0.5 debug_max_profit = 0.000 }\n")
    assert result.vanilla_unchanged == ["pp_tar_kiln_maintenance", "pp_tar_kiln_losing"]
    assert not (mod / pm.BUILDING_TYPES / "production_tar.txt").exists()   # never a copy of a vanilla file
    assert "debug_max_profit" not in pm._read(mod / pm.PRODUCTION_METHODS / "pp_mod.txt")   # profitable, unkeyed
    assert result.mod_losing == []
