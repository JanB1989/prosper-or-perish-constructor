"""Generate an additive location scoring workbook for Google Sheets import."""

from __future__ import annotations

import tomllib
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence
from xml.sax.saxutils import escape

import polars as pl

from prosper_or_perish_constructor.farming_village_unlocks import load_current_location_frame


DEFAULT_OUTPUT = Path("spreadsheets/additive_location_scoring.xlsx")
EXAMPLE_TAGS = (
    "sallum",
    "cairo",
    "gao",
    "timbuktu",
    "paris",
    "chartres",
    "waswanipi",
    "pangnirtung",
    "angkor",
    "male_atoll",
)
LOCATION_LABELS = {
    "sallum": "Sallum",
    "cairo": "Cairo",
    "gao": "Gao",
    "timbuktu": "Timbuktu",
    "paris": "Paris",
    "chartres": "Chartres",
    "waswanipi": "Waswanipi",
    "pangnirtung": "Pangnirtung",
    "angkor": "Angkor",
    "male_atoll": "Male Atoll",
}
VALUE_ROWS = (
    ("topography", "flatland", 5),
    ("topography", "hills", 0),
    ("topography", "plateau", 2),
    ("topography", "mountains", -15),
    ("topography", "wetlands", 0),
    ("topography", "atoll", -10),
    ("topography", "mountain_wasteland", -25),
    ("climate", "arid", -20),
    ("climate", "cold_arid", -15),
    ("climate", "arctic", -25),
    ("climate", "continental", 5),
    ("climate", "oceanic", 10),
    ("climate", "mediterranean", 5),
    ("climate", "subtropical", 8),
    ("climate", "tropical", 0),
    ("vegetation", "desert", -25),
    ("vegetation", "sparse", -10),
    ("vegetation", "grasslands", 5),
    ("vegetation", "farmland", 15),
    ("vegetation", "woods", 5),
    ("vegetation", "forest", 0),
    ("vegetation", "jungle", -5),
    ("river_access", "river", 20),
    ("river_access", "no_river", 0),
)
LOCATION_COLUMNS = (
    "location_tag",
    "macro_region",
    "region",
    "topography",
    "climate",
    "vegetation",
    "has_river",
    "is_adjacent_to_lake",
    "raw_material",
    "soil_quality",
)


@dataclass(frozen=True)
class AdditiveLocationScoringSheet:
    path: Path
    location_count: int
    value_count: int


@dataclass(frozen=True)
class _Cell:
    value: str | int | float | None = None
    formula: str | None = None
    style: int = 0


def build_additive_location_scoring_sheet(
    repo: Path,
    project: Path,
    *,
    output: Path | None = None,
) -> AdditiveLocationScoringSheet:
    """Write the additive location scoring workbook and return its path."""

    output_path = output or _default_output_path(repo, project)
    locations = _example_location_rows(load_current_location_frame(repo, project))
    values = _value_rows()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_workbook(output_path, locations, values)
    return AdditiveLocationScoringSheet(
        path=output_path,
        location_count=len(locations),
        value_count=len(values),
    )


def _default_output_path(repo: Path, project: Path) -> Path:
    with project.open("rb") as handle:
        config = tomllib.load(handle)
    artifacts = config.get("artifacts", {})
    if not isinstance(artifacts, dict):
        artifacts = {}
    root_value = artifacts.get("root", "artifacts")
    if not isinstance(root_value, str):
        raise ValueError(f"[artifacts].root must be a string in {project}")
    artifact_root = Path(root_value)
    if not artifact_root.is_absolute():
        artifact_root = repo / artifact_root
    return artifact_root / DEFAULT_OUTPUT


def _example_location_rows(locations: pl.DataFrame) -> list[dict[str, Any]]:
    _require_columns(locations, LOCATION_COLUMNS)
    selected = (
        locations.filter(pl.col("location_tag").is_in(EXAMPLE_TAGS))
        .select(LOCATION_COLUMNS)
        .to_dicts()
    )
    by_tag = {str(row["location_tag"]): row for row in selected}
    missing = [tag for tag in EXAMPLE_TAGS if tag not in by_tag]
    if missing:
        raise ValueError(f"Location data is missing example locations: {', '.join(missing)}")

    rows: list[dict[str, Any]] = []
    for tag in EXAMPLE_TAGS:
        source = by_tag[tag]
        rows.append(
            {
                "location_label": LOCATION_LABELS[tag],
                "location_tag": tag,
                "macro_region": source["macro_region"],
                "region": source["region"],
                "topography": source["topography"],
                "climate": source["climate"],
                "vegetation": source["vegetation"],
                "river_access": "river" if bool(source["has_river"]) else "no_river",
                "raw_material": source["raw_material"],
                "soil_quality": source["soil_quality"],
                "lake_access": "lake" if bool(source["is_adjacent_to_lake"]) else "no_lake",
            }
        )
    return rows


def _value_rows() -> list[dict[str, str | int]]:
    return [
        {
            "category": category,
            "value": value,
            "score": score,
            "lookup_key": f"{category}|{value}",
        }
        for category, value, score in VALUE_ROWS
    ]


def _write_workbook(
    output_path: Path,
    locations: Sequence[dict[str, Any]],
    values: Sequence[dict[str, str | int]],
) -> None:
    workbook_parts = {
        "[Content_Types].xml": _content_types_xml(),
        "_rels/.rels": _root_relationships_xml(),
        "docProps/app.xml": _app_properties_xml(),
        "docProps/core.xml": _core_properties_xml(),
        "xl/workbook.xml": _workbook_xml(),
        "xl/_rels/workbook.xml.rels": _workbook_relationships_xml(),
        "xl/styles.xml": _styles_xml(),
        "xl/worksheets/sheet1.xml": _worksheet_xml(
            _calculator_sheet_rows(locations, values),
            widths=(20, 18, 18, 22, 16, 16, 16, 16, 17, 15, 18, 20, 12, 16, 16, 14),
            autofilter=f"A1:P{len(locations) + 1}",
            freeze_top_row=True,
        ),
        "xl/worksheets/sheet2.xml": _worksheet_xml(
            _values_sheet_rows(values),
            widths=(18, 22, 12, 32, 4, 58),
            autofilter=f"A1:D{len(values) + 1}",
            freeze_top_row=True,
        ),
    }
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in workbook_parts.items():
            archive.writestr(name, content.encode("utf-8"))


def _calculator_sheet_rows(
    locations: Sequence[dict[str, Any]],
    values: Sequence[dict[str, str | int]],
) -> list[list[_Cell | None]]:
    headers = (
        "location_label",
        "location_tag",
        "macro_region",
        "region",
        "topography",
        "climate",
        "vegetation",
        "river_access",
        "topography_value",
        "climate_value",
        "vegetation_value",
        "river_access_value",
        "total",
        "raw_material",
        "soil_quality",
        "lake_access",
    )
    rows: list[list[_Cell | None]] = [[_Cell(header, style=1) for header in headers]]
    value_last_row = len(values) + 1
    value_range = f"Values!$C$2:$C${value_last_row}"
    key_range = f"Values!$D$2:$D${value_last_row}"
    scores = {str(row["lookup_key"]): int(row["score"]) for row in values}

    for offset, location in enumerate(locations, start=2):
        topography_score = scores[f"topography|{location['topography']}"]
        climate_score = scores[f"climate|{location['climate']}"]
        vegetation_score = scores[f"vegetation|{location['vegetation']}"]
        river_score = scores[f"river_access|{location['river_access']}"]
        total_score = topography_score + climate_score + vegetation_score + river_score
        rows.append(
            [
                _Cell(str(location["location_label"]), style=2),
                _Cell(str(location["location_tag"]), style=2),
                _Cell(str(location["macro_region"]), style=2),
                _Cell(str(location["region"]), style=2),
                _Cell(str(location["topography"]), style=2),
                _Cell(str(location["climate"]), style=2),
                _Cell(str(location["vegetation"]), style=2),
                _Cell(str(location["river_access"]), style=2),
                _Cell(
                    topography_score,
                    formula=_lookup_formula("topography", str(location["topography"]), value_range, key_range),
                    style=3,
                ),
                _Cell(
                    climate_score,
                    formula=_lookup_formula("climate", str(location["climate"]), value_range, key_range),
                    style=3,
                ),
                _Cell(
                    vegetation_score,
                    formula=_lookup_formula("vegetation", str(location["vegetation"]), value_range, key_range),
                    style=3,
                ),
                _Cell(
                    river_score,
                    formula=_lookup_formula(
                        "river_access",
                        str(location["river_access"]),
                        value_range,
                        key_range,
                    ),
                    style=3,
                ),
                _Cell(total_score, formula=f"SUM(I{offset}:L{offset})", style=5),
                _Cell(str(location["raw_material"]), style=2),
                _Cell(str(location["soil_quality"]), style=2),
                _Cell(str(location["lake_access"]), style=2),
            ]
        )
    return rows


def _lookup_formula(category: str, value: str, value_range: str, key_range: str) -> str:
    lookup_key = f"{category}|{value}".replace('"', '""')
    return f'INDEX({value_range},MATCH("{lookup_key}",{key_range},0))'


def _values_sheet_rows(values: Sequence[dict[str, str | int]]) -> list[list[_Cell | None]]:
    rows: list[list[_Cell | None]] = [
        [
            _Cell("category", style=1),
            _Cell("value", style=1),
            _Cell("score", style=1),
            _Cell("lookup_key", style=1),
            None,
            _Cell("Demo scores only. Edit score values in column C.", style=7),
        ]
    ]
    for row in values:
        rows.append(
            [
                _Cell(str(row["category"]), style=2),
                _Cell(str(row["value"]), style=2),
                _Cell(int(row["score"]), style=4),
                _Cell(str(row["lookup_key"]), style=6),
            ]
        )
    return rows


def _worksheet_xml(
    rows: Sequence[Sequence[_Cell | None]],
    *,
    widths: Sequence[int],
    autofilter: str,
    freeze_top_row: bool,
) -> str:
    max_cols = max(len(row) for row in rows)
    dimension = f"A1:{_column_name(max_cols)}{len(rows)}"
    col_xml = "".join(
        f'<col min="{index}" max="{index}" width="{width}" customWidth="1"/>'
        for index, width in enumerate(widths, start=1)
    )
    pane_xml = (
        '<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>'
        '<selection pane="bottomLeft"/>'
        if freeze_top_row
        else ""
    )
    row_xml = []
    for row_index, row in enumerate(rows, start=1):
        cells = []
        for column_index, cell in enumerate(row, start=1):
            if cell is None:
                continue
            cells.append(_cell_xml(row_index, column_index, cell))
        row_xml.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<dimension ref="{dimension}"/>'
        '<sheetViews><sheetView workbookViewId="0" showGridLines="0">'
        f"{pane_xml}"
        "</sheetView></sheetViews>"
        f"<cols>{col_xml}</cols>"
        f'<sheetData>{"".join(row_xml)}</sheetData>'
        f'<autoFilter ref="{autofilter}"/>'
        "</worksheet>"
    )


def _cell_xml(row_index: int, column_index: int, cell: _Cell) -> str:
    ref = f"{_column_name(column_index)}{row_index}"
    style = f' s="{cell.style}"' if cell.style else ""
    if cell.formula is not None:
        cached = "" if cell.value is None else f"<v>{cell.value}</v>"
        return f'<c r="{ref}"{style}><f>{escape(cell.formula)}</f>{cached}</c>'
    if isinstance(cell.value, int | float):
        return f'<c r="{ref}"{style}><v>{cell.value}</v></c>'
    value = "" if cell.value is None else str(cell.value)
    return f'<c r="{ref}" t="inlineStr"{style}><is><t>{escape(value)}</t></is></c>'


def _column_name(index: int) -> str:
    parts: list[str] = []
    while index:
        index, remainder = divmod(index - 1, 26)
        parts.append(chr(65 + remainder))
    return "".join(reversed(parts))


def _require_columns(frame: pl.DataFrame, columns: Sequence[str]) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"Location data is missing required columns: {', '.join(missing)}")


def _content_types_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
        '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '<Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        "</Types>"
    )


def _root_relationships_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
        '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
        "</Relationships>"
    )


def _workbook_relationships_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/>'
        '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
        "</Relationships>"
    )


def _workbook_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        "<workbookPr/>"
        '<sheets><sheet name="Calculator" sheetId="1" r:id="rId1"/>'
        '<sheet name="Values" sheetId="2" r:id="rId2"/></sheets>'
        "</workbook>"
    )


def _styles_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<fonts count="4">'
        '<font><sz val="11"/><color rgb="FF1F2937"/><name val="Calibri"/></font>'
        '<font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font>'
        '<font><sz val="11"/><color rgb="FF1F2937"/><name val="Calibri"/></font>'
        '<font><b/><sz val="11"/><color rgb="FF1F2937"/><name val="Calibri"/></font>'
        "</fonts>"
        '<fills count="7">'
        '<fill><patternFill patternType="none"/></fill>'
        '<fill><patternFill patternType="gray125"/></fill>'
        '<fill><patternFill patternType="solid"><fgColor rgb="FF264653"/><bgColor indexed="64"/></patternFill></fill>'
        '<fill><patternFill patternType="solid"><fgColor rgb="FFF8FAFC"/><bgColor indexed="64"/></patternFill></fill>'
        '<fill><patternFill patternType="solid"><fgColor rgb="FFE9F5DB"/><bgColor indexed="64"/></patternFill></fill>'
        '<fill><patternFill patternType="solid"><fgColor rgb="FFE8F1FF"/><bgColor indexed="64"/></patternFill></fill>'
        '<fill><patternFill patternType="solid"><fgColor rgb="FFFFF4CC"/><bgColor indexed="64"/></patternFill></fill>'
        "</fills>"
        '<borders count="2">'
        "<border><left/><right/><top/><bottom/><diagonal/></border>"
        '<border><left style="thin"><color rgb="FFD9E2EC"/></left>'
        '<right style="thin"><color rgb="FFD9E2EC"/></right>'
        '<top style="thin"><color rgb="FFD9E2EC"/></top>'
        '<bottom style="thin"><color rgb="FFD9E2EC"/></bottom><diagonal/></border>'
        "</borders>"
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="8">'
        '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
        '<xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1"><alignment horizontal="center"/></xf>'
        '<xf numFmtId="0" fontId="0" fillId="3" borderId="1" xfId="0" applyFill="1" applyBorder="1"><alignment horizontal="left"/></xf>'
        '<xf numFmtId="1" fontId="0" fillId="5" borderId="1" xfId="0" applyNumberFormat="1" applyFill="1" applyBorder="1"><alignment horizontal="right"/></xf>'
        '<xf numFmtId="1" fontId="3" fillId="4" borderId="1" xfId="0" applyNumberFormat="1" applyFont="1" applyFill="1" applyBorder="1"><alignment horizontal="right"/></xf>'
        '<xf numFmtId="1" fontId="3" fillId="6" borderId="1" xfId="0" applyNumberFormat="1" applyFont="1" applyFill="1" applyBorder="1"><alignment horizontal="right"/></xf>'
        '<xf numFmtId="0" fontId="0" fillId="3" borderId="1" xfId="0" applyFill="1" applyBorder="1"><alignment horizontal="left"/></xf>'
        '<xf numFmtId="0" fontId="3" fillId="6" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1"><alignment horizontal="left"/></xf>'
        "</cellXfs>"
        '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
        "</styleSheet>"
    )


def _app_properties_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
        'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
        "<Application>Prosper or Perish Constructor</Application>"
        "</Properties>"
    )


def _core_properties_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:dcmitype="http://purl.org/dc/dcmitype/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        "<dc:title>Additive Location Scoring</dc:title>"
        "<dc:creator>Prosper or Perish Constructor</dc:creator>"
        "<dc:description>Pure additive scoring workbook for demonstrating geography modifier limits.</dc:description>"
        "</cp:coreProperties>"
    )
