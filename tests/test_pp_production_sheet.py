from __future__ import annotations

import json
from pathlib import Path
import tomllib

from eu5gameparser.domain.goods import load_goods_data
from prosper_or_perish_constructor.pp_production_sheet import (
    HEADERS,
    SHEET_TITLE,
    SPREADSHEET_TITLE,
    _base_production,
    _format_requests,
    _pad_row,
    _replace_all_sheets,
    load_adjusted_goods_rows,
)


ROOT = Path(__file__).resolve().parents[1]


def test_adjusted_goods_rows_match_constructor_parser_output() -> None:
    project = tomllib.loads((ROOT / "constructor.toml").read_text(encoding="utf-8-sig"))
    parser = project["parser"]
    parsed = load_goods_data(
        profile=parser["profile"],
        load_order_path=ROOT / parser["load_order"],
    ).goods
    rows = load_adjusted_goods_rows(ROOT)

    assert HEADERS == (
        "good",
        "default_market_price",
        "transport_cost",
        "food",
        "base_production",
    )
    assert [row[0] for row in rows] == sorted(parsed["name"].to_list())
    assert len(rows) == parsed.height

    parsed_by_name = {row["name"]: row for row in parsed.to_dicts()}
    exported_by_name = {row[0]: row for row in rows}
    for name, parsed_row in parsed_by_name.items():
        exported = exported_by_name[name]
        assert exported[1:4] == [
            parsed_row["default_market_price"],
            parsed_row["transport_cost"],
            parsed_row["food"],
        ]
        assert exported[4] == _base_production(parsed_row["data"])


def test_pp_specific_adjustments_are_present_in_export() -> None:
    rows = {row[0]: row[1:] for row in load_adjusted_goods_rows(ROOT)}

    assert rows["wheat"] == [1.0, 1.0, 0.0, None]
    assert rows["victuals"] == [3.0, 3.0, 0.0, 0.003]
    assert rows["province_food_sales"] == [5.0, 100.0, None, 1.0]
    assert rows["local_food"] == [0.0, 100.0, 1.0, 0.0]


def test_base_production_uses_effective_scalar_and_allows_missing_value() -> None:
    assert _base_production('{"entries":[],"items":[]}') is None
    assert (
        _base_production(
            json.dumps(
                {
                    "entries": [
                        {"key": "base_production", "op": "=", "value": 0.012},
                    ],
                    "items": [],
                }
            )
        )
        == 0.012
    )


def test_sheet_format_plan_is_scoped_to_the_five_column_table() -> None:
    requests = _format_requests(sheet_id=42, row_count=81)

    assert SPREADSHEET_TITLE == "PP_Production"
    assert SHEET_TITLE == "Goods"
    filter_range = next(request["setBasicFilter"]["filter"]["range"] for request in requests if "setBasicFilter" in request)
    assert filter_range == {
        "sheetId": 42,
        "startRowIndex": 0,
        "endRowIndex": 81,
        "startColumnIndex": 0,
        "endColumnIndex": 5,
    }
    column_widths = [
        request["updateDimensionProperties"]["properties"]["pixelSize"]
        for request in requests
        if request.get("updateDimensionProperties", {}).get("range", {}).get("dimension")
        == "COLUMNS"
    ]
    assert column_widths == [180, 155, 130, 90, 140]


def test_google_values_verification_normalizes_internal_and_trailing_blanks() -> None:
    assert _pad_row(["clay", 0.5, 2, "", 0.02]) == ["clay", 0.5, 2, None, 0.02]
    assert _pad_row(["alum", 3, 1]) == ["alum", 3, 1, None, None]


def test_rerun_replaces_every_old_tab_with_one_fresh_goods_tab() -> None:
    class Request:
        def __init__(self, result: dict[str, object]) -> None:
            self.result = result

        def execute(self) -> dict[str, object]:
            return self.result

    class SheetsService:
        def __init__(self) -> None:
            self.batches: list[dict[str, object]] = []

        def spreadsheets(self) -> "SheetsService":
            return self

        def get(self, **_: object) -> Request:
            return Request(
                {
                    "sheets": [
                        {"properties": {"sheetId": 10, "title": "Goods"}},
                        {"properties": {"sheetId": 11, "title": "Old notes"}},
                    ]
                }
            )

        def batchUpdate(self, **kwargs: object) -> Request:  # noqa: N802 - Google API name
            body = kwargs["body"]
            assert isinstance(body, dict)
            self.batches.append(body)
            if "addSheet" in body["requests"][0]:
                return Request(
                    {"replies": [{"addSheet": {"properties": {"sheetId": 99}}}]}
                )
            return Request({})

    service = SheetsService()
    new_sheet_id = _replace_all_sheets(service, "spreadsheet-id", row_count=81)

    assert new_sheet_id == 99
    final_requests = service.batches[1]["requests"]
    assert [request["deleteSheet"]["sheetId"] for request in final_requests[:2]] == [10, 11]
    assert final_requests[2]["updateSheetProperties"]["properties"] == {
        "sheetId": 99,
        "title": "Goods",
        "index": 0,
        "gridProperties": {
            "rowCount": 81,
            "columnCount": 5,
            "frozenRowCount": 1,
        },
    }
