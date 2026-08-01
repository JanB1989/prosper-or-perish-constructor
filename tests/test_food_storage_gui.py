from pathlib import Path

import pytest

from prosper_or_perish_constructor import food_storage_gui


def _write_gui_overrides(mod_root: Path, *, divisor: str = "24") -> None:
    formula = (
        "value = \"[Divide_CFixedPoint("
        "Province.GetCapital.GetModifierValueFixed("
        "'pp_province_food_storage_months'), "
        f"'(CFixedPoint){divisor}')]\""
    )
    for relative_path, expected_divisors in (
        food_storage_gui.FOOD_STORAGE_GUI_DIVISOR_COUNTS
    ):
        path = mod_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "\n".join(formula for _ in range(expected_divisors)) + "\n",
            encoding="utf-8-sig",
        )
    map_mode = mod_root / food_storage_gui.FOOD_STORAGE_MAP_MODE
    map_mode.parent.mkdir(parents=True, exist_ok=True)
    map_mode.write_text(
        "\r\n".join(
            (
                "@pp_province_food_storage_months_low = 6",
                "@pp_province_food_storage_months_moderate = 12",
                "@pp_province_food_storage_months_high = 18",
                "@pp_province_food_storage_months_max = 24",
                "@pp_province_food_storage_months_step = 6",
            )
        )
        + "\r\n",
        encoding="utf-8-sig",
        newline="",
    )


def test_food_storage_gui_compiler_tracks_growth_cap_define(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path
    mod_root = repo / "mod" / "test-mod"
    _write_gui_overrides(mod_root)
    configured_months = 42.0
    monkeypatch.setattr(
        food_storage_gui,
        "load_food_storage_max_months",
        lambda **_kwargs: configured_months,
    )

    result = food_storage_gui.compile_food_storage_gui(
        repo=repo,
        mod_root=mod_root,
    )

    assert result.max_years == 3.5
    assert result.max_months == configured_months
    assert result.divisor_literal == "42"
    assert result.files_changed == len(
        food_storage_gui.FOOD_STORAGE_GUI_DIVISOR_COUNTS
    )
    assert result.replacements == sum(
        count for _, count in food_storage_gui.FOOD_STORAGE_GUI_DIVISOR_COUNTS
    )
    assert result.localization_changed
    assert result.map_mode_changed
    for relative_path, expected_divisors in (
        food_storage_gui.FOOD_STORAGE_GUI_DIVISOR_COUNTS
    ):
        text = (mod_root / relative_path).read_text(encoding="utf-8-sig")
        assert text.count("'(CFixedPoint)42'") == expected_divisors
        assert "'(CFixedPoint)24'" not in text

    map_mode = (mod_root / food_storage_gui.FOOD_STORAGE_MAP_MODE).read_text(
        encoding="utf-8-sig"
    )
    assert "@pp_province_food_storage_months_low = 10.5" in map_mode
    assert "@pp_province_food_storage_months_moderate = 21" in map_mode
    assert "@pp_province_food_storage_months_high = 31.5" in map_mode
    assert "@pp_province_food_storage_months_max = 42" in map_mode
    assert "@pp_province_food_storage_months_step = 10.5" in map_mode

    localization = (mod_root / food_storage_gui.FOOD_STORAGE_LOCALIZATION).read_text(
        encoding="utf-8-sig"
    )
    assert "EFFECTS_FROM_STORAGE" in localization
    assert "maximum of #Y 42#! Months" in localization
    assert "maximum of #Y 120#! Months" not in localization
    assert 'MAPMODE_PP_POSITIVE_PROVINCE_FOOD_GROWTH_LOW: "10.5 months"' in localization
    assert 'MAPMODE_PP_POSITIVE_PROVINCE_FOOD_GROWTH_MODERATE: "21 months"' in localization
    assert 'MAPMODE_PP_POSITIVE_PROVINCE_FOOD_GROWTH_HIGH: "31.5 months"' in localization
    assert 'MAPMODE_PP_POSITIVE_PROVINCE_FOOD_GROWTH_MAX: "42+ months"' in localization
    assert "MAPMODE_PP_POSITIVE_PROVINCE_FOOD_GROWTH_STRIPED" in localization
    assert "MAPMODE_PP_POSITIVE_PROVINCE_FOOD_GROWTH_STARVING" in localization

    unchanged = food_storage_gui.compile_food_storage_gui(
        repo=repo,
        mod_root=mod_root,
    )
    assert unchanged.files_changed == 0
    assert unchanged.replacements == result.replacements
    assert not unchanged.localization_changed
    assert not unchanged.map_mode_changed


def test_food_storage_gui_compiler_requires_complete_override_set(
    tmp_path: Path,
) -> None:
    repo = tmp_path
    mod_root = repo / "mod" / "test-mod"
    first_path, _ = food_storage_gui.FOOD_STORAGE_GUI_DIVISOR_COUNTS[0]
    path = mod_root / first_path
    path.parent.mkdir(parents=True)
    path.write_text("placeholder\n", encoding="utf-8")

    with pytest.raises(SystemExit, match="required overrides are missing"):
        food_storage_gui.compile_food_storage_gui(
            repo=repo,
            mod_root=mod_root,
        )
