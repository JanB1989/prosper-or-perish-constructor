"""Maghreb control gifts (2026-11-27, Jan: "the control bonuses from the game and the DLC, these can be reduced as well,
most definitely. It's fine if their cities have decent control, but inland should be hard").

In four observer runs Morocco, Tlemcen and Tunis climbed from about 0.32 population-weighted control in 1342 to
0.85-0.91 in 1837, inland and desert included. The mod's copies keep every vanilla line except the cut ones: flat
monthly control to a fifth (the size of the 0.0005 base rate), maximum rural control and the Atlas proximity relief
halved, separatism and rebel growth reliefs by a third. The ratios are taken against today's vanilla files, so a game
update that changes one of these values fails here and asks for a review (docs/country_finetunes.md).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from eu5gameparser.clausewitz.parser import parse_file
from eu5gameparser.clausewitz.serializer import render_value
from eu5gameparser.clausewitz.syntax import CList
from eu5gameparser.load_order import LoadOrderConfig

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mod" / "pp"
GAME = LoadOrderConfig.load(ROOT / "constructor.load_order.toml").vanilla_root / "game"
D009 = "dlc/D009_across_the_pillars"

FLAT = (0.18, 0.27)  # a fifth to a quarter
HALF = (0.49, 0.51)
THIRD_OFF = (0.6, 0.72)

# mod file, mod key, vanilla file, vanilla key, {leaf: ratio band}, extra mod leaves {leaf: value}
CASES = [
    ("in_game/common/bureaucracies/pp_bureaucracy_adjustments.txt", "TRY_REPLACE:makhzan_bureaucracy",
     f"{D009}/in_game/common/bureaucracies/d009_andalusi_maghrebi.txt", "makhzan_bureaucracy",
     {"neutral_modifier[0]/global_monthly_control[0]": FLAT}, {}),
    ("in_game/common/estate_privileges/pp_estate_privilege_adjustments.txt", "TRY_REPLACE:desert_power",
     "in_game/common/estate_privileges/tribes_estate.txt", "desert_power",
     {"country_modifier[1]/global_monthly_control[0]": FLAT}, {"country_modifier[0]/research_speed[0]": "-0.075"}),
    ("in_game/common/government_reforms/pp_government_reform_adjustments.txt",
     "REPLACE:maghreb_ibadi_majlis_ammi_said",
     "in_game/common/government_reforms/country_specific.txt", "maghreb_ibadi_majlis_ammi_said",
     {"country_modifier[0]/global_monthly_control[0]": FLAT}, {}),
    ("in_game/common/estate_privileges/pp_estate_privilege_adjustments.txt", "TRY_REPLACE:local_tribal_strongholds",
     "in_game/common/estate_privileges/tribes_estate.txt", "local_tribal_strongholds",
     # the mod's older changes on this privilege (2026-10-11): tribes power doubled, max tax and research cost added
     {"country_modifier[0]/global_max_rural_control[0]": HALF, "country_modifier[0]/global_tribes_estate_power[0]": (2, 2)},
     {"country_modifier[0]/tribes_estate_max_tax[0]": "-0.075", "country_modifier[0]/research_speed[0]": "-0.075"}),
    ("in_game/common/laws/pp_law_adjustments.txt", "TRY_REPLACE:bled_makhzen_siba_law",
     f"{D009}/in_game/common/laws/d009_02_country_specific.txt", "bled_makhzen_siba_law",
     {"negotiated_authority_policy[0]/country_modifier[0]/global_max_rural_control[0]": HALF}, {}),
    ("in_game/common/advances/pp_country_advances_adjustments.txt", "TRY_REPLACE:mor_atlas_strongholds",
     "in_game/common/advances/country_mor.txt", "mor_atlas_strongholds",
     {"hills_proximity_impact[0]": HALF, "mountains_proximity_impact[0]": HALF}, {}),
    ("in_game/common/advances/pp_country_advances_adjustments.txt", "TRY_REPLACE:moroccan_bay_a",
     "in_game/common/advances/country_mor.txt", "moroccan_bay_a", {"global_separatism[0]": THIRD_OFF}, {}),
    ("in_game/common/advances/pp_country_advances_adjustments.txt", "TRY_REPLACE:amazigh_group_agraw_council",
     "in_game/common/advances/country_tle.txt", "amazigh_group_agraw_council", {"global_separatism[0]": THIRD_OFF}, {}),
    ("in_game/common/advances/pp_country_advances_adjustments.txt", "TRY_REPLACE:tun_caliphal_claim",
     "in_game/common/advances/country_tun.txt", "tun_caliphal_claim", {"global_separatism[0]": THIRD_OFF}, {}),
    ("in_game/common/government_reforms/pp_government_reform_adjustments.txt", "REPLACE:guardians_of_ifriqiya",
     "in_game/common/government_reforms/country_specific.txt", "guardians_of_ifriqiya",
     {"country_modifier[0]/global_separatism[0]": THIRD_OFF, "country_modifier[0]/monthly_rebel_growth[0]": THIRD_OFF},
     {}),
    ("in_game/common/government_reforms/pp_government_reform_adjustments.txt", "TRY_REPLACE:agraw_federation_reform",
     f"{D009}/in_game/common/government_reforms/d009_country_specific.txt", "agraw_federation_reform",
     {"country_modifier[0]/global_separatism[0]": THIRD_OFF}, {}),
    ("in_game/common/government_reforms/pp_government_reform_adjustments.txt",
     "TRY_REPLACE:amenokal_paramountcy_reform",
     f"{D009}/in_game/common/government_reforms/d009_country_specific.txt", "amenokal_paramountcy_reform",
     {"country_modifier[0]/global_separatism[0]": THIRD_OFF}, {}),
    ("in_game/common/government_reforms/pp_government_reform_adjustments.txt", "TRY_REPLACE:diwan_of_the_azzaba_reform",
     f"{D009}/in_game/common/government_reforms/d009_country_specific.txt", "diwan_of_the_azzaba_reform",
     {"country_modifier[0]/global_separatism[0]": THIRD_OFF}, {}),
]


def _block(path: Path, key: str) -> CList:
    blocks = [e.value for e in parse_file(path).entries if e.key == key]
    assert len(blocks) == 1, (path, key, len(blocks))
    return blocks[0]


def _leaves(node: CList, prefix: str = "") -> dict[str, str]:
    """Every scalar of a block by its path; a repeated key is told apart by its index among its siblings."""
    out: dict[str, str] = {}
    seen: dict[str, int] = {}
    for entry in node.entries:
        index = seen.get(entry.key, 0)
        seen[entry.key] = index + 1
        path = f"{prefix}{entry.key}[{index}]"
        if isinstance(entry.value, CList):
            out.update(_leaves(entry.value, path + "/"))
            for k, item in enumerate(entry.value.items):
                out[f"{path}/item[{k}]"] = render_value(item)
        else:
            out[path] = f"{entry.op} {render_value(entry.value)}"
    return out


def _number(text: str) -> float:
    return float(text.split()[-1])


@pytest.mark.parametrize("mod_file,mod_key,vanilla_file,vanilla_key,bands,extra", CASES,
                         ids=[case[3] for case in CASES])
def test_gift_cut_against_vanilla(mod_file, mod_key, vanilla_file, vanilla_key, bands, extra) -> None:
    own = _leaves(_block(MOD / mod_file, mod_key))
    old = _leaves(_block(GAME / vanilla_file, vanilla_key))
    assert set(own) == set(old) | set(extra), (set(own) ^ (set(old) | set(extra)))
    for leaf, (lo, hi) in bands.items():
        ratio = _number(own[leaf]) / _number(old[leaf])
        assert lo <= ratio <= hi, (leaf, own[leaf], old[leaf])
    for leaf, value in old.items():
        if leaf not in bands:
            assert own[leaf] == value, (leaf, own[leaf], value)
    for leaf, value in extra.items():
        assert _number(own[leaf]) == pytest.approx(float(value)), leaf


def _control_modifiers(block: CList) -> list[CList]:
    return [m for m in block.values("country_modifier") if isinstance(m, CList) and m.values("global_monthly_control")]


def test_tlemcen_tribes_support_cut_only_while_content() -> None:
    """Tlemcen's reform: vanilla 0.01 x (tribes satisfaction - 0.5) control a month, so -0.005 .. +0.005. The content
    side is a fifth now; the discontent side keeps vanilla's strength. Every other modifier, the DLC's inject included,
    is vanilla."""
    own = _block(MOD / "in_game/common/government_reforms/pp_government_reform_adjustments.txt",
                 "REPLACE:tle_support_of_banu_al_wad")
    old = _block(GAME / "in_game/common/government_reforms/country_specific.txt", "tle_support_of_banu_al_wad")
    inject = _block(GAME / f"{D009}/in_game/common/government_reforms/d009_country_specific.txt",
                    "INJECT:tle_support_of_banu_al_wad")
    (old_control,) = _control_modifiers(old)
    vanilla_rate = float(old_control.first("global_monthly_control"))
    assert _leaves(old_control.first("scale")) == {"value[0]": "= estate_satisfaction:tribes_estate",
                                                   "subtract[0]": "= 0.5"}
    content, discontent = sorted(_control_modifiers(own), key=lambda m: m.first("scale").first("min") is None)
    assert _leaves(content.first("scale")) == {"value[0]": "= estate_satisfaction:tribes_estate",
                                               "subtract[0]": "= 0.5", "min[0]": "= 0"}
    assert _leaves(discontent.first("scale")) == {"value[0]": "= estate_satisfaction:tribes_estate",
                                                  "subtract[0]": "= 0.5", "max[0]": "= 0"}
    assert FLAT[0] <= float(content.first("global_monthly_control")) / vanilla_rate <= FLAT[1]
    assert float(discontent.first("global_monthly_control")) == pytest.approx(vanilla_rate)
    rendered = lambda block: sorted(render_value(m) for m in block.values("country_modifier")  # noqa: E731
                                    if not (isinstance(m, CList) and m.values("global_monthly_control")))
    assert rendered(own) == sorted(rendered(old) + rendered(inject))
    for key in ("age", "potential", "allow", "locked", "major", "years"):
        assert render_value(own.first(key)) == render_value(old.first(key)), key


def _tribes_privileges() -> list[str]:
    names = []
    for root in [GAME / "in_game/common/estate_privileges",
                 *sorted(GAME.glob("dlc/*/in_game/common/estate_privileges"))]:
        for path in sorted(root.glob("*.txt")):
            for entry in parse_file(path).entries:
                if isinstance(entry.value, CList) and entry.value.first("estate") == "tribes_estate":
                    names.append(entry.key.split(":")[-1])
    return names


def test_every_tribes_privilege_costs_research() -> None:
    """The mod's rule (2026-10-11, Jan): every tribes estate privilege costs -0.075 research a month, Across the
    Pillars' included (2026-11-27). Written once: an inject in zz_pp_tribes_privileges_research.txt, or the line in
    the block that replaces the privilege (an inject misses a replaced block)."""
    rows: dict[str, list[str]] = {}
    for path in sorted((MOD / "in_game/common/estate_privileges").glob("*.txt")):
        for entry in parse_file(path).entries:
            if not isinstance(entry.value, CList):
                continue
            form, _, name = entry.key.rpartition(":")
            for modifier in entry.value.values("country_modifier"):
                if isinstance(modifier, CList) and modifier.values("research_speed"):
                    rows.setdefault(name, []).append(f"{form}:{float(modifier.first('research_speed'))}")
    privileges = _tribes_privileges()
    assert len(privileges) >= 24
    missing = [name for name in privileges if name not in rows]
    assert not missing, missing
    for name in privileges:
        assert len(rows[name]) == 1, (name, rows[name])
        assert rows[name][0].endswith(":-0.075"), (name, rows[name])
