"""Export effective Prosper or Perish goods values to Google Sheets."""

from __future__ import annotations

import argparse
import json
import os
import tomllib
import uuid
from pathlib import Path
from typing import Any, Sequence

from eu5gameparser.domain.goods import load_goods_data


SPREADSHEET_TITLE = "PP_Production"
SHEET_TITLE = "Goods"
HEADERS = (
    "good",
    "default_market_price",
    "transport_cost",
    "food",
    "base_production",
)
GOOGLE_SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"
DEFAULT_TOKEN_CACHE = Path("artifacts/local/google/pp_production_token.json")
DEFAULT_STATE_FILE = Path("artifacts/local/google/pp_production.json")


def load_adjusted_goods_rows(repo: str | Path) -> list[list[Any]]:
    """Load the final, load-order-adjusted goods values used by PP in game."""
    repo_path = Path(repo).resolve()
    project = tomllib.loads((repo_path / "constructor.toml").read_text(encoding="utf-8-sig"))
    parser = project.get("parser", {})
    profile = str(parser.get("profile", "constructor"))
    load_order = repo_path / str(parser.get("load_order", "constructor.load_order.toml"))
    goods = load_goods_data(profile=profile, load_order_path=load_order).goods

    required = {"name", "default_market_price", "transport_cost", "food", "data"}
    missing = sorted(required - set(goods.columns))
    if missing:
        raise ValueError(f"Parsed goods data is missing required columns: {', '.join(missing)}")

    rows: list[list[Any]] = []
    for good in goods.sort("name").to_dicts():
        rows.append(
            [
                str(good["name"]),
                good["default_market_price"],
                good["transport_cost"],
                good["food"],
                _base_production(good["data"]),
            ]
        )
    return rows


def _base_production(raw_data: str) -> float | None:
    """Read the effective base_production scalar retained in parser data."""
    parsed = json.loads(raw_data)
    values = [
        entry.get("value")
        for entry in parsed.get("entries", [])
        if entry.get("key") == "base_production"
    ]
    if not values:
        return None
    value = values[-1]
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"base_production must be numeric, got {value!r}")
    return float(value)


def export_data_json(repo: str | Path, destination: str | Path) -> Path:
    """Write an auditable intermediate used to build and verify the initial Sheet."""
    destination_path = Path(destination)
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "spreadsheet_title": SPREADSHEET_TITLE,
        "sheet_title": SHEET_TITLE,
        "headers": list(HEADERS),
        "rows": load_adjusted_goods_rows(repo),
    }
    destination_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return destination_path


def rebuild_google_sheet(
    service: Any,
    rows: Sequence[Sequence[Any]],
    *,
    spreadsheet_id: str | None = None,
) -> tuple[str, str]:
    """Create or atomically replace the workbook's sole Goods tab."""
    row_count = len(rows) + 1
    if spreadsheet_id:
        sheet_id = _replace_all_sheets(service, spreadsheet_id, row_count)
    else:
        spreadsheet_id, sheet_id = _create_spreadsheet(service, row_count)

    values = [
        list(HEADERS),
        *[["" if value is None else value for value in row] for row in rows],
    ]
    (
        service.spreadsheets()
        .values()
        .update(
            spreadsheetId=spreadsheet_id,
            range=f"'{SHEET_TITLE}'!A1:E{row_count}",
            valueInputOption="RAW",
            body={"majorDimension": "ROWS", "values": values},
        )
        .execute()
    )
    (
        service.spreadsheets()
        .batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": _format_requests(sheet_id, row_count)},
        )
        .execute()
    )
    verify_google_sheet(service, spreadsheet_id, rows)
    return spreadsheet_id, google_sheet_url(spreadsheet_id)


def _create_spreadsheet(service: Any, row_count: int) -> tuple[str, int]:
    response = (
        service.spreadsheets()
        .create(
            body={
                "properties": {"title": SPREADSHEET_TITLE},
                "sheets": [
                    {
                        "properties": {
                            "title": SHEET_TITLE,
                            "gridProperties": {
                                "rowCount": max(row_count, 2),
                                "columnCount": len(HEADERS),
                                "frozenRowCount": 1,
                            },
                        }
                    }
                ],
            },
            fields="spreadsheetId,sheets(properties(sheetId))",
        )
        .execute()
    )
    return str(response["spreadsheetId"]), int(response["sheets"][0]["properties"]["sheetId"])


def _replace_all_sheets(service: Any, spreadsheet_id: str, row_count: int) -> int:
    metadata = (
        service.spreadsheets()
        .get(
            spreadsheetId=spreadsheet_id,
            includeGridData=False,
            fields="sheets.properties(sheetId,title)",
        )
        .execute()
    )
    old_sheet_ids = [int(sheet["properties"]["sheetId"]) for sheet in metadata.get("sheets", [])]
    if not old_sheet_ids:
        raise ValueError(f"Spreadsheet {spreadsheet_id} has no sheets")

    temporary_title = f"__pp_rebuild_{uuid.uuid4().hex[:10]}"
    added = (
        service.spreadsheets()
        .batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={
                "requests": [
                    {
                        "addSheet": {
                            "properties": {
                                "title": temporary_title,
                                "gridProperties": {
                                    "rowCount": max(row_count, 2),
                                    "columnCount": len(HEADERS),
                                },
                            }
                        }
                    }
                ]
            },
        )
        .execute()
    )
    new_sheet_id = int(added["replies"][0]["addSheet"]["properties"]["sheetId"])
    requests = [{"deleteSheet": {"sheetId": sheet_id}} for sheet_id in old_sheet_ids]
    requests.extend(
        [
            {
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": new_sheet_id,
                        "title": SHEET_TITLE,
                        "index": 0,
                        "gridProperties": {
                            "rowCount": max(row_count, 2),
                            "columnCount": len(HEADERS),
                            "frozenRowCount": 1,
                        },
                    },
                    "fields": "title,index,gridProperties(rowCount,columnCount,frozenRowCount)",
                }
            },
            {
                "updateSpreadsheetProperties": {
                    "properties": {"title": SPREADSHEET_TITLE},
                    "fields": "title",
                }
            },
        ]
    )
    (
        service.spreadsheets()
        .batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests})
        .execute()
    )
    return new_sheet_id


def _format_requests(sheet_id: int, row_count: int) -> list[dict[str, Any]]:
    grid = {
        "sheetId": sheet_id,
        "startRowIndex": 0,
        "endRowIndex": row_count,
        "startColumnIndex": 0,
        "endColumnIndex": len(HEADERS),
    }
    requests: list[dict[str, Any]] = [
        {
            "updateSheetProperties": {
                "properties": {
                    "sheetId": sheet_id,
                    "gridProperties": {"frozenRowCount": 1},
                },
                "fields": "gridProperties.frozenRowCount",
            }
        },
        {
            "repeatCell": {
                "range": {**grid, "endRowIndex": 1},
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColorStyle": {
                            "rgbColor": {"red": 0.91, "green": 0.91, "blue": 0.91}
                        },
                        "horizontalAlignment": "LEFT",
                        "verticalAlignment": "MIDDLE",
                        "textFormat": {"bold": True},
                    }
                },
                "fields": "userEnteredFormat(backgroundColorStyle,horizontalAlignment,verticalAlignment,textFormat)",
            }
        },
        {
            "repeatCell": {
                "range": {
                    **grid,
                    "startRowIndex": 1,
                    "startColumnIndex": 1,
                },
                "cell": {
                    "userEnteredFormat": {
                        "horizontalAlignment": "RIGHT",
                        "numberFormat": {"type": "NUMBER", "pattern": "0.0###"},
                    }
                },
                "fields": "userEnteredFormat(horizontalAlignment,numberFormat)",
            }
        },
        {
            "updateBorders": {
                "range": {**grid, "endRowIndex": 1},
                "bottom": {
                    "style": "SOLID",
                    "colorStyle": {
                        "rgbColor": {"red": 0.75, "green": 0.75, "blue": 0.75}
                    },
                },
            }
        },
        {"setBasicFilter": {"filter": {"range": grid}}},
        {
            "updateDimensionProperties": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "ROWS",
                    "startIndex": 0,
                    "endIndex": 1,
                },
                "properties": {"pixelSize": 28},
                "fields": "pixelSize",
            }
        },
    ]
    widths = (180, 155, 130, 90, 140)
    requests.extend(
        {
            "updateDimensionProperties": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "COLUMNS",
                    "startIndex": index,
                    "endIndex": index + 1,
                },
                "properties": {"pixelSize": width},
                "fields": "pixelSize",
            }
        }
        for index, width in enumerate(widths)
    )
    return requests


def verify_google_sheet(service: Any, spreadsheet_id: str, rows: Sequence[Sequence[Any]]) -> None:
    """Verify native structure and every exported cell after a rebuild."""
    metadata = (
        service.spreadsheets()
        .get(
            spreadsheetId=spreadsheet_id,
            includeGridData=False,
            fields="properties.title,sheets.properties(sheetId,title,gridProperties)",
        )
        .execute()
    )
    if metadata.get("properties", {}).get("title") != SPREADSHEET_TITLE:
        raise RuntimeError("Google Sheet title verification failed")
    sheets = metadata.get("sheets", [])
    if len(sheets) != 1 or sheets[0].get("properties", {}).get("title") != SHEET_TITLE:
        raise RuntimeError("Google Sheet must contain exactly one Goods tab")
    grid = sheets[0]["properties"].get("gridProperties", {})
    if grid.get("frozenRowCount") != 1 or grid.get("columnCount") != len(HEADERS):
        raise RuntimeError("Google Sheet grid verification failed")

    expected = [list(HEADERS), *[list(row) for row in rows]]
    response = (
        service.spreadsheets()
        .values()
        .get(
            spreadsheetId=spreadsheet_id,
            range=f"'{SHEET_TITLE}'!A1:E{len(expected)}",
            majorDimension="ROWS",
            valueRenderOption="UNFORMATTED_VALUE",
        )
        .execute()
    )
    actual = [_pad_row(row) for row in response.get("values", [])]
    if actual != [_pad_row(row) for row in expected]:
        raise RuntimeError("Google Sheet value verification failed")


def _pad_row(row: Sequence[Any]) -> list[Any]:
    padded = [*row, *([None] * (len(HEADERS) - len(row)))]
    return [None if value == "" else value for value in padded]


def google_sheet_url(spreadsheet_id: str) -> str:
    return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"


def read_state_spreadsheet_id(state_path: str | Path) -> str | None:
    path = Path(state_path)
    if not path.is_file():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    value = raw.get("spreadsheet_id")
    return str(value) if value else None


def write_state(state_path: str | Path, spreadsheet_id: str) -> None:
    path = Path(state_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(
            {
                "spreadsheet_id": spreadsheet_id,
                "spreadsheet_url": google_sheet_url(spreadsheet_id),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def google_sheets_service(
    *,
    client_secrets_path: str | Path | None,
    token_cache_path: str | Path,
) -> Any:
    """Authenticate through browser OAuth and return a Sheets v4 service."""
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError as exc:  # pragma: no cover - dependency failure path
        raise RuntimeError(
            "Google Sheets export needs google-api-python-client, google-auth-oauthlib, "
            "and google-auth-httplib2."
        ) from exc

    token_path = Path(token_cache_path)
    scopes = [GOOGLE_SHEETS_SCOPE]
    credentials = None
    if token_path.is_file():
        credentials = Credentials.from_authorized_user_file(str(token_path), scopes)
    if credentials is None or not credentials.valid:
        if credentials is not None and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            raw_secrets = client_secrets_path or os.environ.get("GOOGLE_OAUTH_CLIENT_SECRETS")
            if not raw_secrets:
                raise FileNotFoundError(
                    "No writable Google token is cached. Pass --client-secrets or set "
                    "GOOGLE_OAUTH_CLIENT_SECRETS to a Desktop OAuth client JSON file."
                )
            secrets = Path(raw_secrets)
            if not secrets.is_file():
                raise FileNotFoundError(f"Google OAuth client secrets not found: {secrets}")
            flow = InstalledAppFlow.from_client_secrets_file(str(secrets), scopes)
            credentials = flow.run_local_server(port=0)
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(credentials.to_json(), encoding="utf-8")
    return build("sheets", "v4", credentials=credentials, cache_discovery=False)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Rebuild PP_Production from final Prosper or Perish parser values. "
            "Reruns keep the spreadsheet URL and replace all tabs cleanly."
        )
    )
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--spreadsheet-id", help="Override the spreadsheet id saved in local state.")
    parser.add_argument("--client-secrets", type=Path, help="Desktop OAuth client JSON file.")
    parser.add_argument("--token-cache", type=Path, default=DEFAULT_TOKEN_CACHE)
    parser.add_argument("--state-file", type=Path, default=DEFAULT_STATE_FILE)
    parser.add_argument("--export-data-json", type=Path, help="Write parsed rows for local QA.")
    parser.add_argument("--dry-run", action="store_true", help="Parse and validate without Google access.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    rows = load_adjusted_goods_rows(args.repo)
    if args.export_data_json:
        export_data_json(args.repo, args.export_data_json)
    if args.dry_run:
        print(
            json.dumps(
                {
                    "spreadsheet_title": SPREADSHEET_TITLE,
                    "sheet_title": SHEET_TITLE,
                    "headers": HEADERS,
                    "row_count": len(rows),
                },
                indent=2,
            )
        )
        return 0

    spreadsheet_id = args.spreadsheet_id or read_state_spreadsheet_id(args.state_file)
    service = google_sheets_service(
        client_secrets_path=args.client_secrets,
        token_cache_path=args.token_cache,
    )
    spreadsheet_id, url = rebuild_google_sheet(
        service,
        rows,
        spreadsheet_id=spreadsheet_id,
    )
    write_state(args.state_file, spreadsheet_id)
    print(f"Rebuilt {SPREADSHEET_TITLE} with {len(rows)} goods: {url}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
