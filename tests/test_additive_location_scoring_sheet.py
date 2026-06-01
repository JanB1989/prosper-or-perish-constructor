import zipfile
from pathlib import Path

import polars as pl

from prosper_or_perish_constructor import additive_location_scoring_sheet as scoring


def test_additive_location_scoring_sheet_uses_configured_artifacts_root(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo = tmp_path
    project = repo / "constructor.toml"
    project.write_text(
        '[project]\nname = "Test"\n\n[artifacts]\nroot = "custom_artifacts"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(scoring, "load_current_location_frame", _fake_location_frame)

    result = scoring.build_additive_location_scoring_sheet(repo, project)

    assert result.path == repo / "custom_artifacts" / "spreadsheets" / "additive_location_scoring.xlsx"
    assert result.location_count == 10
    assert result.value_count == 24
    assert result.path.is_file()

    with zipfile.ZipFile(result.path) as archive:
        workbook = archive.read("xl/workbook.xml").decode("utf-8")
        calculator = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
        values = archive.read("xl/worksheets/sheet2.xml").decode("utf-8")

    assert 'sheet name="Calculator"' in workbook
    assert 'sheet name="Values"' in workbook
    assert 'MATCH("topography|flatland"' in calculator
    assert 'MATCH("climate|arid"' in calculator
    assert 'MATCH("vegetation|sparse"' in calculator
    assert 'MATCH("river_access|no_river"' in calculator
    assert "<f>SUM(I2:L2)</f>" in calculator
    assert "Demo scores only. Edit score values in column C." in values
    assert "topography|flatland" in values
    assert "river_access|no_river" in values


def _fake_location_frame(repo: Path, project: Path) -> pl.DataFrame:
    del repo, project
    examples = {
        "sallum": ("north_africa", "egypt_region", "flatland", "arid", "sparse", False, False, "sand", "soil_verypoor"),
        "cairo": ("north_africa", "egypt_region", "flatland", "arid", "farmland", True, False, "wheat", "soil_poor"),
        "gao": ("west_africa", "sahel_region", "flatland", "arid", "desert", True, False, "rice", "soil_verypoor"),
        "timbuktu": ("west_africa", "sahel_region", "flatland", "arid", "desert", False, False, "livestock", "soil_awful"),
        "paris": ("western_europe", "france_region", "flatland", "oceanic", "farmland", True, False, "wine", "soil_average"),
        "chartres": ("western_europe", "france_region", "flatland", "oceanic", "farmland", False, False, "fruit", "soil_average"),
        "waswanipi": ("north_america", "canada_region", "flatland", "arctic", "forest", True, True, "fur", "soil_verypoor"),
        "pangnirtung": ("north_america", "canada_region", "flatland", "arctic", "sparse", False, False, "ivory", "soil_awful"),
        "angkor": ("south_east_asia", "indochina_region", "flatland", "tropical", "farmland", True, True, "rice", "soil_verypoor"),
        "male_atoll": ("south_asia", "deccan_region", "atoll", "tropical", "forest", False, False, "lumber", "soil_verypoor"),
    }
    return pl.DataFrame(
        [
            {
                "location_tag": tag,
                "macro_region": values[0],
                "region": values[1],
                "topography": values[2],
                "climate": values[3],
                "vegetation": values[4],
                "has_river": values[5],
                "is_adjacent_to_lake": values[6],
                "raw_material": values[7],
                "soil_quality": values[8],
            }
            for tag, values in examples.items()
        ]
    )
