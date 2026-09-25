import json
from pathlib import Path

import pytest

from prosper_or_perish_constructor.europedia import (
    EuropediaExportError,
    build_europedia_payload,
    write_europedia_export,
)


def test_build_europedia_payload_preserves_gui_order_and_decodes_localization(
    tmp_path: Path,
) -> None:
    mod_root = _write_europedia_sources(
        tmp_path,
        {
            "game_concept_pp_food": "P&P: Food Production",
            "game_concept_pp_food_desc": (
                '#T Food "Export"#!\n'
                "$BULLET$ Read [pp_food|e] and inspect [ShowGoodsName('victuals')|e].\n"
                "[ShowModifierEffect('province_starving')]\n"
                "Workers include [ShowPopTypeName('peasants')]."
            ),
            "game_concept_pp_faq": "F.A.Q.",
            "game_concept_pp_faq_desc": "Question text with an escaped quote: \"yes\".",
        },
    )

    payload = build_europedia_payload(mod_root)

    assert [entry["title"] for entry in payload["entries"]] == [
        "P&P: Food Production",
        "F.A.Q.",
    ]
    first = payload["entries"][0]
    assert first["filter"] == "food"
    assert first["icon_texture"] == "gfx/interface/icons/flat_icons/trade_market/food_stockpile.dds"
    assert first["definition"]["aliases"] == ["pp_grub"]
    assert '#T Food "Export"#!\n$BULLET$ Read' in first["body_raw"]
    assert "[Victuals|e]" not in first["body_plain"]
    assert "Victuals" in first["body_plain"]
    assert "Province Starving" in first["body_plain"]
    assert "Peasants" in first["body_plain"]
    assert "<h3>Food &quot;Export&quot;</h3>" in first["body_html"]
    assert '<a class="concept-link" href="#pp-food">P&amp;P: Food Production</a>' in first["body_html"]
    assert '<span class="token token-good">Victuals</span>' in first["body_html"]
    assert '<span class="token token-effect">modifier effects: Province Starving</span>' in first["body_html"]
    assert '<span class="token token-pop">Peasants</span>' in first["body_html"]
    assert "[<span" not in first["body_html"]
    assert payload["filters"][0] == {"id": "all", "label": "All", "count": 2}
    assert {"id": "food", "label": "Food Production", "count": 1} in payload["filters"]


def test_build_europedia_payload_reports_missing_localization_keys(tmp_path: Path) -> None:
    mod_root = _write_europedia_sources(
        tmp_path,
        {
            "game_concept_pp_food": "P&P: Food Production",
        },
    )

    with pytest.raises(EuropediaExportError, match="game_concept_pp_food_desc"):
        build_europedia_payload(mod_root)


def test_write_europedia_export_writes_html_and_json_smoke(tmp_path: Path) -> None:
    mod_root = _write_europedia_sources(
        tmp_path,
        {
            "game_concept_pp_food": "P&P: Food Production",
            "game_concept_pp_food_desc": "#T Food#!\n$BULLET$ Build [ShowBuildingTypeName('cookshop')|e].",
            "game_concept_pp_faq": "F.A.Q.",
            "game_concept_pp_faq_desc": "Question text.",
        },
    )

    html_path, json_path = write_europedia_export(
        mod_root,
        tmp_path / "graphs" / "europedia.html",
        tmp_path / "graphs" / "europedia_entries.json",
    )

    html = html_path.read_text(encoding="utf-8")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert "const europediaPayload =" in html
    assert 'id="searchInput"' in html
    assert 'id="filterButtons"' in html
    assert "Export JSON" in html
    assert "europedia_entries.json" in html
    assert "P&P: Food Production" in html
    assert payload["metadata"]["entry_count"] == 2
    assert payload["entries"][0]["source"]["gui"] == "in_game/gui/encyclopedia_lateralview.gui"


def _write_europedia_sources(tmp_path: Path, localization: dict[str, str]) -> Path:
    mod_root = tmp_path / "mod" / "test-mod"
    gui = mod_root / "in_game" / "gui" / "encyclopedia_lateralview.gui"
    loc = mod_root / "main_menu" / "localization" / "english" / "pp_europedia_l_english.yml"
    concepts = mod_root / "main_menu" / "common" / "game_concepts"
    gui.parent.mkdir(parents=True)
    loc.parent.mkdir(parents=True)
    concepts.mkdir(parents=True)

    gui.write_text(
        """
button_regular = {
  raw_text = "All"
  onclick = "[GetVariableSystem.Set('pp_filter', 'all')]"
}
button_regular = {
  raw_text = "Food Production"
  onclick = "[GetVariableSystem.Set('pp_filter', 'food')]"
}
button_regular = {
  raw_text = "F.A.Q."
  onclick = "[GetVariableSystem.Set('pp_filter', 'faq')]"
}
vbox = {
  visible = "[Or(GetVariableSystem.HasValue('pp_filter', 'all'), GetVariableSystem.HasValue('pp_filter', 'food'))]"
  icon = { texture = "gfx/interface/icons/flat_icons/trade_market/food_stockpile.dds" size = { 45 45 } }
  text_single = { text = "game_concept_pp_food" }
  text_multi = { text = "game_concept_pp_food_desc" }
}
vbox = {
  visible = "[Or(GetVariableSystem.HasValue('pp_filter', 'all'), GetVariableSystem.HasValue('pp_filter', 'faq'))]"
  icon = { texture = "gfx/interface/icons/flat_icons/effect.dds" size = { 45 45 } }
  text_single = { text = "game_concept_pp_faq" }
  text_multi = { text = "game_concept_pp_faq_desc" }
}
""",
        encoding="utf-8",
    )
    loc.write_text(
        "l_english:\n"
        + "".join(
            f"  {key}: {json.dumps(value, ensure_ascii=False)}\n"
            for key, value in localization.items()
        ),
        encoding="utf-8-sig",
    )
    (concepts / "pp_food_production.txt").write_text(
        'pp_food = { family = food alias = { pp_grub } texture = "flat_icons/trade_market/food_stockpile" }\n',
        encoding="utf-8",
    )
    (concepts / "pp_faq.txt").write_text(
        'pp_faq = { family = food texture = "flat_icons/effect" }\n',
        encoding="utf-8",
    )
    return mod_root
