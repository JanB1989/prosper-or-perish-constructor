from __future__ import annotations

from pathlib import Path

from prosper_or_perish_constructor import method_icons


VANILLA_BUILDINGS = """\
tannery = {
\tunique_production_methods = {
\t\ttannery_maintenance = {
\t\t\ticon_type = goods
\t\t\ticon = wild_game
\t\t\twild_game = 1.6
\t\t\tproduced = leather
\t\t\toutput = 1
\t\t}
\t}
}
"""
VANILLA_METHODS = """\
library_maintenance = {
\ticon_type = building_type
\ticon = library
\tpaper = 0.2
\tcategory = building_maintenance
}
"""
MOD_BUILDINGS = """\
REPLACE:tannery = {
\tunique_production_methods = {
\t\tpp_tannery_tannery_maintenance = {
\t\t\twild_game = 1.4
\t\t\tmanual_labor = 0.2
\t\t\tproduced = leather
\t\t\toutput = 1
\t\t}
\t\tpp_tannery_bark_pits = {
\t\t\tlumber = 0.3 # bark
\t\t\tproduced = leather
\t\t\toutput = 0.5
\t\t}
\t}
\tunique_production_methods = {
\t\tpp_tannery_market_sales = {
\t\t\toffset = 0.012
\t\t\tproduced = leather
\t\t\toutput = 0.004
\t\t}
\t\tpp_tannery_provision = { wild_game = 0.05 produced = local_food output = 0.6 }
\t\tpp_tannery_no_primary = {
\t\t}
\t\tpp_tannery_own_icon = {
\t\t\ticon_type = goods
\t\t\ticon = tar
\t\t\ttar = 0.1
\t\t}
\t}
}
"""
MOD_METHODS = """\
pp_library_maintenance = {
\tpaper = 0.4
\tcategory = building_maintenance
}
pp_road_upkeep = {
\tstone = 0.1
\ttools = 0.05
\tcategory = building_maintenance
}
"""


def _world(tmp_path: Path) -> tuple[Path, Path]:
    vanilla = tmp_path / "vanilla"
    (vanilla / "game/in_game/common/building_types").mkdir(parents=True)
    (vanilla / "game/in_game/common/production_methods").mkdir(parents=True)
    (vanilla / "game/in_game/common/building_types/production_leather.txt").write_text(VANILLA_BUILDINGS, encoding="utf-8")
    (vanilla / "game/in_game/common/production_methods/unsorted_building_inputs.txt").write_text(VANILLA_METHODS, encoding="utf-8")
    mod = tmp_path / "mod"
    (mod / "in_game/common/building_types").mkdir(parents=True)
    (mod / "in_game/common/production_methods").mkdir(parents=True)
    (mod / "in_game/common/building_types/zz_pp_tannery.txt").write_text(MOD_BUILDINGS, encoding="utf-8")
    (mod / "in_game/common/production_methods/pp_methods.txt").write_text(MOD_METHODS, encoding="utf-8")
    return vanilla, mod


def _icons(text: str) -> dict[str, tuple[str, str]]:
    """Method key -> icon of every method: top-level methods, and the methods of each unique_production_methods block."""
    out = {}
    methods = []
    for top in method_icons.child_entries(text, -1, len(text)):
        groups = [g for g in method_icons.child_entries(text, top.open, top.close) if g.key == "unique_production_methods"]
        if not groups:
            methods.append(top)
        for group in groups:
            methods.extend(method_icons.child_entries(text, group.open, group.close))
    for method in methods:
        icon = method_icons._icon(text[method.open + 1 : method.close])
        if icon:
            out[method.key] = icon
    return out


def test_icons_follow_vanilla_then_market_leg_provision_and_building(tmp_path: Path) -> None:
    vanilla, mod = _world(tmp_path)
    result = method_icons.apply(mod, vanilla)
    text = (mod / "in_game/common/building_types/zz_pp_tannery.txt").read_text(encoding="utf-8-sig")
    icons = _icons(text)

    assert icons["pp_tannery_tannery_maintenance"] == ("goods", "wild_game")  # renamed vanilla method keeps its icon
    assert icons["pp_tannery_bark_pits"] == ("building_type", "tannery")
    assert icons["pp_tannery_market_sales"] == ("goods", "leather")
    assert icons["pp_tannery_provision"] == ("goods", "wild_game")
    assert icons["pp_tannery_no_primary"] == ("building_type", "tannery")
    assert icons["pp_tannery_own_icon"] == ("goods", "tar")  # a hand-set icon stays
    assert text.count("icon_type") == 6
    assert method_icons.missing(mod, vanilla) == []

    methods = (mod / "in_game/common/production_methods/pp_methods.txt").read_text(encoding="utf-8-sig")
    assert _icons(methods) == {"pp_library_maintenance": ("building_type", "library"), "pp_road_upkeep": ("goods", "stone")}
    assert result.methods_written == 7


def test_icons_are_idempotent_and_keep_the_method_body(tmp_path: Path) -> None:
    vanilla, mod = _world(tmp_path)
    method_icons.apply(mod, vanilla)
    path = mod / "in_game/common/building_types/zz_pp_tannery.txt"
    once = path.read_text(encoding="utf-8-sig")
    again = method_icons.apply(mod, vanilla)

    assert again.methods_written == 0
    assert path.read_text(encoding="utf-8-sig") == once
    assert "\t\tpp_tannery_bark_pits = {\n\t\t\ticon_type = building_type\n\t\t\ticon = tannery\n\t\t\tlumber = 0.3 # bark\n" in once
    assert "pp_tannery_provision = {\n\t\t\ticon_type = goods\n\t\t\ticon = wild_game\n\t\t\t wild_game = 0.05 produced = local_food output = 0.6 }" in once


def test_icons_follow_the_body_indentation(tmp_path: Path) -> None:
    vanilla, mod = _world(tmp_path)
    path = mod / "in_game/common/building_types/zz_pp_yard.txt"
    path.write_text(
        "yard = {\nunique_production_methods = {\n  pp_yard_work = {\n    tools = 0.1\n    produced = logistics\n  }\n}\n}\n",
        encoding="utf-8",
    )
    method_icons.apply(mod, vanilla)

    assert "  pp_yard_work = {\n    icon_type = building_type\n    icon = yard\n    tools = 0.1\n" in path.read_text(encoding="utf-8-sig")


def test_vanilla_named_copies_are_left_alone(tmp_path: Path) -> None:
    vanilla, mod = _world(tmp_path)
    copy = mod / "in_game/common/building_types/production_leather.txt"
    copy.write_text(MOD_BUILDINGS.replace("REPLACE:", ""), encoding="utf-8")
    method_icons.apply(mod, vanilla)

    assert copy.read_text(encoding="utf-8-sig") == MOD_BUILDINGS.replace("REPLACE:", "")
