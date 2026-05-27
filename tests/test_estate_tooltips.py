from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
ESTATE_TOOLTIP = MOD_ROOT / "in_game" / "gui" / "shared" / "zz_pp_estate_tooltips.gui"


def test_estate_tooltip_body_is_scrollable() -> None:
    assert ESTATE_TOOLTIP.exists()

    text = ESTATE_TOOLTIP.read_text(encoding="utf-8-sig")

    assert "template Estate_tooltip" in text
    assert "TooltipScrolledContentSection" in text
    assert 'blockoverride "block_scrollarea" { maximumsize = { -1 700 } }' in text
    assert 'blockoverride "section_content"' in text
    assert "ESTATE_BREAKDOWN" in text
    assert "[Estate.GetEconomyInfo]" in text
    assert "[Estate.GetType.GetFlavorText]" in text
    estate_start = text.index("template Estate_tooltip")
    estate_scroll = text.index("TooltipScrolledContentSection", estate_start)
    assert estate_scroll < text.index("[Estate.GetEconomyInfo]", estate_start)


def test_estate_type_tooltip_body_is_scrollable() -> None:
    assert ESTATE_TOOLTIP.exists()

    text = ESTATE_TOOLTIP.read_text(encoding="utf-8-sig")

    assert "template EstateType_tooltip" in text
    assert "[EstateType.GetTooltip]" in text
    assert "[EstateType.GetFlavorText]" in text
    estate_type_start = text.index("template EstateType_tooltip")
    estate_type_scroll = text.index("TooltipScrolledContentSection", estate_type_start)
    assert estate_type_scroll < text.index("[EstateType.GetTooltip]", estate_type_start)
