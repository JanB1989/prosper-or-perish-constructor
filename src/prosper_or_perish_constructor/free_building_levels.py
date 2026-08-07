"""Game-start free-building-level statistics from a Google Sheet source of truth."""

from __future__ import annotations

import csv
import io
import os
import re
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl
import yaml
from eu5gameparser.clausewitz.parser import parse_file
from eu5gameparser.clausewitz.syntax import CEntry, CList
from eu5gameparser.domain._modifier_blocks import ModifierBlockData, load_modifier_block_data
from eu5gameparser.domain.building_types import BuildingTypeData, load_building_type_data
from eu5gameparser.domain.location_ranks import LocationRankData, load_location_rank_data
from eu5gameparser.domain.static_modifiers import StaticModifierData, load_static_modifier_data
from eu5gameparser.domain.topography import TopographyData, load_topography_data
from eu5gameparser.domain.vegetation import VegetationData, load_vegetation_data
from eu5gameparser.load_order import DataProfile, GameLayer, LoadOrderConfig
from PIL import Image

from prosper_or_perish_constructor.farming_village_unlocks import load_current_location_frame
from prosper_or_perish_population_capacity.geometry import build_location_geometry_frame


SPREADSHEET_ID = "1d_zH-wxb9ufW6RgVZgJdGqToJ-VZP_XPS7WhhUAa18U"
SHEET_NAME = "free_building_levels"
SHEET_GID = "602606501"
SHEET_RANGE = f"{SHEET_NAME}!A1:H"
GOOGLE_SHEETS_READONLY_SCOPE = "https://www.googleapis.com/auth/spreadsheets.readonly"
FREE_BUILDING_LEVELS_DATA_DIR = Path("graphs/building_capacity/data")
LOCAL_SHEET_CSV_NAME = "free_building_levels_sheet.csv"
LOCAL_WEIGHTS_PARQUET_NAME = "free_building_levels_weights.parquet"
LOCAL_BUILD_BUILDINGS_EFFICIENCY_COLUMN = "local_build_buildings_efficiency"
LOCAL_CONSTRUCTION_SPEED_COLUMN = "local_construction_speed"
LOCAL_BUILD_BUILDINGS_EFFICIENCY_FACTORS = frozenset(
    {"topography", "vegetation", "climate", "river_level", "is_port", "location_rank"}
)
LOCAL_CONSTRUCTION_SPEED_FACTORS = LOCAL_BUILD_BUILDINGS_EFFICIENCY_FACTORS
NON_PORT_LOCAL_BUILD_EFFICIENCY_PENALTY = -0.15
WEIGHTS_CSV_COLUMNS = (
    "section",
    "factor",
    "value",
    "free_building_levels",
    LOCAL_BUILD_BUILDINGS_EFFICIENCY_COLUMN,
    LOCAL_CONSTRUCTION_SPEED_COLUMN,
)
WEIGHTS_FRAME_SCHEMA = {
    "section": pl.String,
    "factor": pl.String,
    "value": pl.String,
    "free_building_levels": pl.Float64,
    LOCAL_BUILD_BUILDINGS_EFFICIENCY_COLUMN: pl.Float64,
    LOCAL_CONSTRUCTION_SPEED_COLUMN: pl.Float64,
}

CATEGORICAL_FACTORS = (
    "topography",
    "vegetation",
    "climate",
    "river_level",
    "location_rank",
    "road_level",
)
BOOLEAN_FACTORS = (
    "province_capital",
    "is_port",
    "market_center",
    "capital",
    "naval_governor",
    "local_governor",
)
EFFICIENCY_CATEGORICAL_FACTORS = tuple(
    factor for factor in CATEGORICAL_FACTORS if factor in LOCAL_BUILD_BUILDINGS_EFFICIENCY_FACTORS
)
EFFICIENCY_BOOLEAN_FACTORS = tuple(
    factor for factor in BOOLEAN_FACTORS if factor in LOCAL_BUILD_BUILDINGS_EFFICIENCY_FACTORS
)
CONSTRUCTION_SPEED_CATEGORICAL_FACTORS = tuple(
    factor for factor in CATEGORICAL_FACTORS if factor in LOCAL_CONSTRUCTION_SPEED_FACTORS
)
CONSTRUCTION_SPEED_BOOLEAN_FACTORS = tuple(
    factor for factor in BOOLEAN_FACTORS if factor in LOCAL_CONSTRUCTION_SPEED_FACTORS
)
NUMERIC_FACTORS = ("development",)
FLAG_HEADERS = {"fixed_flag", "dynamic_flag"}
SHEET_FACTOR_HEADERS = {*CATEGORICAL_FACTORS, *NUMERIC_FACTORS, *FLAG_HEADERS}
ALL_FACTORS = (*CATEGORICAL_FACTORS, *BOOLEAN_FACTORS, *NUMERIC_FACTORS)
DEFAULT_DISPLAY_DECIMALS = 2
MIN_EFFECTIVE_DEVELOPMENT = 0.0
MAX_EFFECTIVE_DEVELOPMENT = 100.0
FACTOR_GROUPS = {
    "topography": "fixed",
    "vegetation": "fixed",
    "climate": "fixed",
    "river_level": "fixed",
    "is_port": "fixed",
    "location_rank": "dynamic",
    "road_level": "dynamic",
    "province_capital": "dynamic",
    "market_center": "dynamic",
    "capital": "dynamic",
    "naval_governor": "dynamic",
    "local_governor": "dynamic",
    "development": "dynamic",
}

RIVER_INDEX_LEVELS = {
    0: 1,
    1: 1,
    2: 1,
    4: 4,
    5: 5,
    11: 5,
    15: 1,
}


@dataclass(frozen=True)
class FreeBuildingLevelResult:
    frame: pl.DataFrame
    diagnostics: pl.DataFrame


def public_google_sheet_csv_url(
    *,
    spreadsheet_id: str = SPREADSHEET_ID,
    gid: str = SHEET_GID,
) -> str:
    query = urllib.parse.urlencode({"format": "csv", "gid": gid})
    return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?{query}"


def google_sheet_browser_url(
    *,
    spreadsheet_id: str = SPREADSHEET_ID,
    gid: str = SHEET_GID,
) -> str:
    return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit#gid={gid}"


def read_public_google_sheet_values(
    *,
    spreadsheet_id: str = SPREADSHEET_ID,
    gid: str = SHEET_GID,
    timeout: float = 20.0,
) -> list[list[str]]:
    """Read the sheet through its public CSV export URL.

    This requires the sheet/tab to be shared so anyone with the link can view it.
    It avoids OAuth entirely and is the default notebook path.
    """
    url = public_google_sheet_csv_url(spreadsheet_id=spreadsheet_id, gid=gid)
    request = urllib.request.Request(url, headers={"User-Agent": "ppc-free-building-levels/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            content_type = response.headers.get("content-type", "")
            raw = response.read()
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not read public Google Sheet CSV export: {url}") from exc

    text = raw.decode("utf-8-sig")
    lowered = text[:2000].lower()
    if "text/html" in content_type.lower() or "<html" in lowered or "google sign in" in lowered:
        raise RuntimeError(
            "Google returned an HTML/login page instead of CSV. Share the sheet/tab "
            "as viewable by anyone with the link, or use read_google_sheet_values(...) "
            "with OAuth."
        )
    return parse_google_sheet_csv_text(text)


def parse_google_sheet_csv_text(text: str) -> list[list[str]]:
    return [list(row) for row in csv.reader(io.StringIO(text))]


def resolve_free_building_levels_data_dir(repo: Path) -> Path:
    return repo / FREE_BUILDING_LEVELS_DATA_DIR


def local_free_building_levels_sheet_csv_path(repo: Path) -> Path:
    return resolve_free_building_levels_data_dir(repo) / LOCAL_SHEET_CSV_NAME


def local_free_building_levels_weights_parquet_path(repo: Path) -> Path:
    return resolve_free_building_levels_data_dir(repo) / LOCAL_WEIGHTS_PARQUET_NAME


def _resolve_weights_csv_path(
    csv_path: str | Path | None = None,
    *,
    repo: Path | None = None,
) -> Path:
    if csv_path is not None:
        path = Path(csv_path)
    elif repo is not None:
        path = local_free_building_levels_sheet_csv_path(repo)
    else:
        raise ValueError("A weights CSV path or repo is required")
    if not path.is_file():
        raise FileNotFoundError(f"Local free-building-levels CSV not found: {path}")
    return path


def read_local_free_building_level_sheet_csv(
    csv_path: str | Path | None = None,
    *,
    repo: Path | None = None,
) -> pl.DataFrame:
    """Read and normalize the tidy local weights CSV."""
    return parse_free_building_level_weights_csv(
        _resolve_weights_csv_path(csv_path, repo=repo)
    )


def write_local_free_building_level_sheet_copy(
    repo: Path,
    weights: pl.DataFrame,
) -> tuple[Path, Path]:
    """Write the tidy weights CSV and parquet cache beside the workbench."""
    data_dir = resolve_free_building_levels_data_dir(repo)
    data_dir.mkdir(parents=True, exist_ok=True)

    normalized = normalize_free_building_level_weights(weights)
    csv_path = local_free_building_levels_sheet_csv_path(repo)
    _write_weights_csv(csv_path, normalized)
    parquet_path = local_free_building_levels_weights_parquet_path(repo)
    normalized.write_parquet(parquet_path)
    return csv_path, parquet_path


def load_free_building_level_weights(
    repo: Path,
    *,
    csv_path: Path | None = None,
    parquet_path: Path | None = None,
    prefer: str = "csv",
) -> pl.DataFrame:
    """Load parsed weights from the local CSV copy (optionally cached parquet)."""
    resolved_csv = csv_path or local_free_building_levels_sheet_csv_path(repo)
    resolved_parquet = parquet_path or local_free_building_levels_weights_parquet_path(repo)

    if prefer == "parquet" and resolved_parquet.is_file():
        return normalize_free_building_level_weights(pl.read_parquet(resolved_parquet))
    if resolved_csv.is_file():
        return parse_free_building_level_weights_csv(resolved_csv)
    if resolved_parquet.is_file():
        return normalize_free_building_level_weights(pl.read_parquet(resolved_parquet))
    raise FileNotFoundError(
        "No local free-building-levels copy found. Expected "
        f"{resolved_parquet} or {resolved_csv}."
    )


def sync_free_building_level_weights_from_google(
    repo: Path,
    *,
    spreadsheet_id: str = SPREADSHEET_ID,
    gid: str = SHEET_GID,
) -> pl.DataFrame:
    """Refresh the committed local CSV + parquet copy from the public Google export."""
    values = read_public_google_sheet_values(spreadsheet_id=spreadsheet_id, gid=gid)
    weights = parse_free_building_level_sheet(values)
    write_local_free_building_level_sheet_copy(repo, weights)
    return weights


def read_google_sheet_values(
    *,
    spreadsheet_id: str = SPREADSHEET_ID,
    sheet_range: str = SHEET_RANGE,
    client_secrets_path: str | Path | None = None,
    token_cache_path: str | Path | None = None,
) -> list[list[Any]]:
    """Read the source-of-truth sheet through browser OAuth.

    The notebook calls this directly. Credentials stay local: pass
    ``client_secrets_path`` or set ``GOOGLE_OAUTH_CLIENT_SECRETS``; cached tokens
    default to ``artifacts/local/google/free_building_levels_token.json``.
    """
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError as exc:  # pragma: no cover - exercised by notebook users
        raise RuntimeError(
            "Google Sheets access needs google-api-python-client, "
            "google-auth-oauthlib, and google-auth-httplib2 installed."
        ) from exc

    token_path = Path(
        token_cache_path
        or os.environ.get(
            "GOOGLE_SHEETS_TOKEN_CACHE",
            "artifacts/local/google/free_building_levels_token.json",
        )
    )
    scopes = [GOOGLE_SHEETS_READONLY_SCOPE]
    creds = None
    if token_path.is_file():
        creds = Credentials.from_authorized_user_file(str(token_path), scopes)
    if creds is None or not creds.valid:
        if creds is not None and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            raw_secrets = client_secrets_path or os.environ.get("GOOGLE_OAUTH_CLIENT_SECRETS")
            if not raw_secrets:
                raise FileNotFoundError(
                    "No cached Google token found. Use the notebook login button with "
                    "an OAuth client JSON path, set GOOGLE_OAUTH_CLIENT_SECRETS, or pass "
                    "client_secrets_path=..."
                )
            secrets = Path(raw_secrets)
            if not secrets.is_file():
                raise FileNotFoundError(f"Google OAuth client secrets not found: {secrets}")
            flow = InstalledAppFlow.from_client_secrets_file(str(secrets), scopes)
            creds = flow.run_local_server(port=0)
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")

    service = build("sheets", "v4", credentials=creds)
    response = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=sheet_range)
        .execute()
    )
    return response.get("values", [])


def parse_free_building_level_weights_csv(source: str | Path) -> pl.DataFrame:
    """Load the tidy weights CSV into a normalized Polars frame."""
    path = Path(source)
    frame = pl.read_csv(path, comment_prefix="#")
    return normalize_free_building_level_weights(frame)


def normalize_free_building_level_weights(frame: pl.DataFrame) -> pl.DataFrame:
    """Normalize factor/value keys and validate the tidy weights table."""
    _require_columns(frame, set(WEIGHTS_CSV_COLUMNS))
    normalized = frame.select(WEIGHTS_CSV_COLUMNS).with_columns(
        pl.col("section").cast(pl.String).str.strip_chars().str.to_lowercase(),
        pl.col("factor").map_elements(_normalize_key, return_dtype=pl.String),
        pl.col("value").map_elements(_normalize_factor_value, return_dtype=pl.String),
        pl.col("free_building_levels").map_elements(_cell_to_float, return_dtype=pl.Float64),
        pl.col(LOCAL_BUILD_BUILDINGS_EFFICIENCY_COLUMN).map_elements(
            _optional_cell_to_float,
            return_dtype=pl.Float64,
        ),
        pl.col(LOCAL_CONSTRUCTION_SPEED_COLUMN).map_elements(
            _optional_cell_to_float,
            return_dtype=pl.Float64,
        ),
    )
    duplicates = (
        normalized.group_by("factor", "value")
        .len()
        .filter(pl.col("len") > 1)
        .select("factor", "value")
    )
    if duplicates.height:
        formatted = ", ".join(
            f"{row['factor']}:{row['value']}" for row in duplicates.to_dicts()
        )
        raise ValueError(f"Duplicate free-building-level rows: {formatted}")

    invalid_efficiency = normalized.filter(
        pl.col(LOCAL_BUILD_BUILDINGS_EFFICIENCY_COLUMN).is_not_null()
        & ~pl.col("factor").is_in(sorted(LOCAL_BUILD_BUILDINGS_EFFICIENCY_FACTORS))
    )
    if invalid_efficiency.height:
        formatted = ", ".join(
            f"{row['factor']}:{row['value']}" for row in invalid_efficiency.to_dicts()
        )
        raise ValueError(
            f"{LOCAL_BUILD_BUILDINGS_EFFICIENCY_COLUMN} is only valid for "
            f"{sorted(LOCAL_BUILD_BUILDINGS_EFFICIENCY_FACTORS)}; got {formatted}"
        )
    invalid_construction_speed = normalized.filter(
        pl.col(LOCAL_CONSTRUCTION_SPEED_COLUMN).is_not_null()
        & ~pl.col("factor").is_in(sorted(LOCAL_CONSTRUCTION_SPEED_FACTORS))
    )
    if invalid_construction_speed.height:
        formatted = ", ".join(
            f"{row['factor']}:{row['value']}" for row in invalid_construction_speed.to_dicts()
        )
        raise ValueError(
            f"{LOCAL_CONSTRUCTION_SPEED_COLUMN} is only valid for "
            f"{sorted(LOCAL_CONSTRUCTION_SPEED_FACTORS)}; got {formatted}"
        )
    return normalized


def parse_free_building_level_sheet(values: Sequence[Sequence[Any]]) -> pl.DataFrame:
    """Parse the legacy visual sheet layout into normalized factor/value rows."""
    active_pairs: dict[int, str] = {}
    section = ""
    rows: list[dict[str, object]] = []

    for raw_row in values:
        row = [_cell_text(value) for value in raw_row]
        first = _cell_text(row[0] if row else "")
        if "FACTORS" in first.upper():
            section = "fixed" if "FIXED" in first.upper() else "dynamic"
            active_pairs = {}
            continue

        header_pairs: dict[int, str] = {}
        for column in range(0, max(len(row) - 1, 0), 2):
            header = _normalize_key(row[column])
            score_header = _normalize_key(row[column + 1])
            if header in SHEET_FACTOR_HEADERS and score_header == "free_building_levels":
                header_pairs[column] = header
        if header_pairs:
            active_pairs = header_pairs
            continue

        for column, header in active_pairs.items():
            value = _cell_text(row[column] if column < len(row) else "")
            if not value:
                continue
            weight = _cell_to_float(row[column + 1] if column + 1 < len(row) else "")
            if header in FLAG_HEADERS:
                factor = _normalize_key(value)
                normalized_value = "true"
            else:
                factor = header
                normalized_value = _normalize_factor_value(value)
            rows.append(
                {
                    "section": section,
                    "factor": factor,
                    "value": normalized_value,
                    "free_building_levels": weight,
                    LOCAL_BUILD_BUILDINGS_EFFICIENCY_COLUMN: None,
                    LOCAL_CONSTRUCTION_SPEED_COLUMN: None,
                }
            )

    return normalize_free_building_level_weights(pl.DataFrame(rows, schema=WEIGHTS_FRAME_SCHEMA))


def _write_weights_csv(path: Path, weights: pl.DataFrame) -> None:
    buffer = io.StringIO()
    normalize_free_building_level_weights(weights).write_csv(buffer)
    path.write_text(
        "# Free building level weights — one row per factor/value pair.\n"
        f"# {LOCAL_BUILD_BUILDINGS_EFFICIENCY_COLUMN} and {LOCAL_CONSTRUCTION_SPEED_COLUMN} "
        "apply to topography, vegetation, climate, river_level (1-5), is_port, and location_rank.\n"
        "# river_level 0 means no river in map data and carries no modifier.\n"
        + buffer.getvalue(),
        encoding="utf-8",
    )


def efficiency_lookup(weights: pl.DataFrame) -> dict[tuple[str, str], float]:
    return _optional_modifier_lookup(weights, LOCAL_BUILD_BUILDINGS_EFFICIENCY_COLUMN)


def construction_speed_lookup(weights: pl.DataFrame) -> dict[tuple[str, str], float]:
    return _optional_modifier_lookup(weights, LOCAL_CONSTRUCTION_SPEED_COLUMN)


def _optional_modifier_lookup(
    weights: pl.DataFrame,
    column: str,
) -> dict[tuple[str, str], float]:
    allowed_factors = (
        LOCAL_BUILD_BUILDINGS_EFFICIENCY_FACTORS
        if column == LOCAL_BUILD_BUILDINGS_EFFICIENCY_COLUMN
        else LOCAL_CONSTRUCTION_SPEED_FACTORS
    )
    _require_columns(weights, {"factor", "value", column})
    lookup: dict[tuple[str, str], float] = {}
    for row in weights.to_dicts():
        factor = _normalize_key(row["factor"])
        if factor not in allowed_factors:
            continue
        value = _normalize_factor_value(row["value"])
        raw = row[column]
        if raw is None:
            continue
        lookup[(factor, value)] = float(raw)
    return lookup


def weights_lookup(weights: pl.DataFrame) -> dict[tuple[str, str], float]:
    _require_columns(weights, {"factor", "value", "free_building_levels"})
    lookup: dict[tuple[str, str], float] = {}
    duplicates: list[tuple[str, str]] = []
    for row in weights.to_dicts():
        key = (_normalize_key(row["factor"]), _normalize_factor_value(row["value"]))
        if key in lookup:
            duplicates.append(key)
        lookup[key] = float(row["free_building_levels"] or 0.0)
    if duplicates:
        formatted = ", ".join(f"{factor}:{value}" for factor, value in sorted(set(duplicates)))
        raise ValueError(f"Duplicate free-building-level sheet rows: {formatted}")
    return lookup


def load_free_building_level_location_frame(
    repo: Path,
    project: Path,
    *,
    profile: str | None = None,
    load_order_path: Path | None = None,
) -> pl.DataFrame:
    """Load static overlaid locations and add game-start fields needed by the sheet."""
    base = load_current_location_frame(repo, project)
    parser_config = resolve_parser_config(repo, project)
    resolved_profile = profile or str(parser_config.get("profile") or "constructor")
    resolved_load_order = load_order_path or repo / str(
        parser_config.get("load_order") or "constructor.load_order.toml"
    )
    return build_game_start_location_frame(
        base,
        profile=LoadOrderConfig.load(resolved_load_order).profile(resolved_profile),
    )


def validate_sheet_values_against_game_sources(
    weights: pl.DataFrame,
    locations: pl.DataFrame,
    *,
    repo: Path,
    project: Path,
) -> pl.DataFrame:
    """Validate sheet factor/value names against game files and derived sources."""
    parser_config = resolve_parser_config(repo, project)
    profile = LoadOrderConfig.load(
        repo / str(parser_config.get("load_order") or "constructor.load_order.toml")
    ).profile(str(parser_config.get("profile") or "constructor"))
    defined_values = {
        "topography": _defined_entry_keys(profile, "topography", "00_default.txt"),
        "vegetation": _defined_entry_keys(profile, "vegetation", "00_default.txt"),
        "climate": _defined_entry_keys(profile, "climates", "00_default.txt"),
        "location_rank": _defined_entry_keys(profile, "location_ranks", "00_default.txt"),
        "road_level": {str(level) for level in load_road_type_levels(profile).values()} | {"0"},
        "river_level": {str(level) for level in range(0, 6)},
        "development": {"per_point"},
    }
    defined_values.update({factor: {"true"} for factor in BOOLEAN_FACTORS})
    source_details = {
        "topography": "in_game/common/topography/00_default.txt",
        "vegetation": "in_game/common/vegetation/00_default.txt",
        "climate": "in_game/common/climates/00_default.txt",
        "location_rank": "in_game/common/location_ranks/00_default.txt",
        "road_level": "in_game/common/road_types/00_generic.txt plus no-road level 0",
        "river_level": "map_data/rivers.png palette-derived levels",
        "development": "sheet convention: development.per_point",
        "province_capital": "game concept/static modifier key province_capital",
        "is_port": "ports.csv / is_port trigger key",
        "market_center": "static modifier key market_center",
        "capital": "country capital scope/key capital",
        "naval_governor": "building_type key naval_governor",
        "local_governor": "building_type key local_governor",
    }

    rows: list[dict[str, object]] = []
    for row in weights.select("factor", "value").to_dicts():
        factor = str(row["factor"])
        value = str(row["value"])
        allowed = defined_values.get(factor, set())
        rows.append(
            {
                "factor": factor,
                "value": value,
                "status": "ok" if value in allowed else "mismatch",
                "source": source_details.get(factor, "unknown"),
                "present_in_locations": _sheet_value_present_in_locations(locations, factor, value),
                "allowed_values": ", ".join(sorted(allowed, key=_natural_sort_key)),
            }
        )
    return pl.DataFrame(rows).sort(["status", "factor", "value"])


def load_game_start_development_weights(
    repo: Path,
    project: Path,
    *,
    profile: str | None = None,
    load_order_path: Path | None = None,
) -> dict[str, float]:
    """Load the parsed game-start development weights used by the location enrichment."""
    parser_config = resolve_parser_config(repo, project)
    resolved_profile = profile or str(parser_config.get("profile") or "constructor")
    resolved_load_order = load_order_path or repo / str(
        parser_config.get("load_order") or "constructor.load_order.toml"
    )
    data_profile = LoadOrderConfig.load(resolved_load_order).profile(resolved_profile)
    return load_development_weights(data_profile)


def build_game_start_location_frame(locations: pl.DataFrame, *, profile: DataProfile) -> pl.DataFrame:
    """Add game-start ranks, markets, roads, capitals, ports, river levels, and development."""
    _require_columns(
        locations,
        {
            "location_tag",
            "location_id",
            "province",
            "region",
            "area",
            "topography",
            "vegetation",
            "climate",
            "is_coastal",
            "has_river",
            "natural_harbor_suitability",
            "named_location_hex",
        },
    )
    ranks = load_location_ranks(profile)
    market_centers = load_market_centers(profile)
    road_locations = load_road_locations(profile)
    capitals = load_country_capitals(profile)
    ports = load_port_locations(profile)
    river_levels = extract_river_levels_from_maps(
        locations,
        locations_png_path=resolve_map_data_file(profile, "locations.png"),
        rivers_png_path=resolve_map_data_file(profile, "rivers.png"),
    )
    development_weights = load_development_weights(profile)

    enriched = enrich_locations_with_game_start_data(
        locations,
        ranks=ranks,
        market_centers=market_centers,
        road_locations=road_locations,
        capitals=capitals,
        ports=ports,
        river_levels=river_levels,
        development_weights=development_weights,
    )
    return enriched


def enrich_locations_with_game_start_data(
    locations: pl.DataFrame,
    *,
    ranks: Mapping[str, str],
    market_centers: Iterable[str],
    road_locations: Iterable[str],
    capitals: Iterable[str],
    ports: Iterable[str],
    river_levels: Mapping[str, int] | pl.DataFrame,
    development_weights: Mapping[str, float],
) -> pl.DataFrame:
    market_set = set(market_centers)
    road_set = set(road_locations)
    capital_set = set(capitals)
    port_set = set(ports)
    province_capitals = set(_province_capitals(locations))
    river_frame = _river_level_frame(river_levels)

    enriched = (
        locations.join(river_frame, on="location_tag", how="left")
        .with_columns(
            pl.col("location_tag")
            .map_elements(lambda value: ranks.get(str(value), "rural_settlement"), return_dtype=pl.String)
            .alias("location_rank"),
            pl.lit(0.0).alias("prosperity"),
            pl.col("location_tag").cast(pl.String).is_in(sorted(market_set)).alias("market_center"),
            pl.col("location_tag").cast(pl.String).is_in(sorted(capital_set)).alias("capital"),
            pl.col("location_tag").cast(pl.String).is_in(sorted(port_set)).alias("is_port"),
            pl.col("location_tag").cast(pl.String).is_in(sorted(province_capitals)).alias("province_capital"),
            pl.when(pl.col("location_tag").cast(pl.String).is_in(sorted(road_set)))
            .then(pl.lit(1))
            .otherwise(pl.lit(0))
            .alias("road_level"),
            pl.lit(False, dtype=pl.Boolean).alias("local_governor"),
            pl.lit(False, dtype=pl.Boolean).alias("naval_governor"),
            pl.lit("lowest_location_id_in_province", dtype=pl.String).alias("province_capital_source"),
        )
        .with_columns(pl.col("river_level").fill_null(0).cast(pl.Int64))
    )
    return (
        enriched.with_columns(_development_expr(development_weights).alias("development"))
        .with_columns(_effective_development_expr().alias("effective_development"))
    )


def explain_development_components(
    locations: pl.DataFrame,
    development_weights: Mapping[str, float],
) -> pl.DataFrame:
    """Return per-location game-start development with component columns."""
    _require_columns(
        locations,
        {
            "location_tag",
            "topography",
            "vegetation",
            "climate",
            "location_rank",
            "region",
            "area",
            "province",
            "natural_harbor_suitability",
            "river_level",
            "road_level",
        },
    )
    return round_numeric_columns(
        locations.select(
            "location_tag",
            "province",
            "region",
            "area",
            "topography",
            "vegetation",
            "climate",
            "location_rank",
            "river_level",
            "road_level",
            pl.lit(float(development_weights.get("base", 0.0))).alias("base_development"),
            _lookup_development_expr("topography", development_weights).alias("topography_development"),
            _lookup_development_expr("vegetation", development_weights).alias("vegetation_development"),
            _lookup_development_expr("climate", development_weights).alias("climate_development"),
            _lookup_development_expr("location_rank", development_weights).alias("location_rank_development"),
            _lookup_development_expr("region", development_weights).alias("region_development"),
            _lookup_development_expr("area", development_weights).alias("area_development"),
            _lookup_development_expr("province", development_weights).alias("province_development"),
            _lookup_development_expr("location_tag", development_weights).alias("location_development"),
            (
                pl.col("natural_harbor_suitability")
                .fill_null(0.0)
                .cast(pl.Float64)
                * pl.lit(float(development_weights.get("coastal", 0.0)))
            ).alias("coastal_development"),
            (
                pl.col("river_level").fill_null(0).cast(pl.Float64)
                * pl.lit(float(development_weights.get("river", 0.0)))
            ).alias("river_development"),
            (
                pl.col("road_level").fill_null(0).cast(pl.Float64)
                * pl.lit(float(development_weights.get("road", 0.0)))
            ).alias("road_development"),
            pl.col("development"),
            _effective_development_expr().alias("effective_development"),
        )
    )


def compute_free_building_levels(
    locations: pl.DataFrame,
    weights: pl.DataFrame,
) -> FreeBuildingLevelResult:
    """Apply sheet weights to an enriched location frame."""
    _require_columns(locations, {"location_tag", "river_level", "development", *CATEGORICAL_FACTORS, *BOOLEAN_FACTORS})
    lookup = weights_lookup(weights)
    diagnostics = _diagnostics(locations, lookup)

    component_exprs: list[pl.Expr] = []
    component_columns: list[str] = []
    for factor in CATEGORICAL_FACTORS:
        column = f"{factor}_free_building_levels"
        mapping = {value: weight for (lookup_factor, value), weight in lookup.items() if lookup_factor == factor}
        component_columns.append(column)
        component_exprs.append(
            pl.col(factor)
            .map_elements(
                lambda value, mapping=mapping: mapping.get(_normalize_factor_value(value), 0.0),
                return_dtype=pl.Float64,
            )
            .alias(column)
        )
    for factor in BOOLEAN_FACTORS:
        column = f"{factor}_free_building_levels"
        weight = lookup.get((factor, "true"), 0.0)
        component_columns.append(column)
        component_exprs.append(
            pl.when(pl.col(factor).fill_null(False))
            .then(pl.lit(weight))
            .otherwise(pl.lit(0.0))
            .alias(column)
        )

    development_per_point = lookup.get(("development", "per_point"), 0.0)
    component_columns.append("development_free_building_levels")
    component_exprs.append(
        (_effective_development_expr() * pl.lit(development_per_point)).alias("development_free_building_levels")
    )

    frame = locations.with_columns(component_exprs).with_columns(
        pl.sum_horizontal(component_columns).alias("free_building_levels")
    )
    return FreeBuildingLevelResult(frame=frame, diagnostics=diagnostics)


def compute_local_build_buildings_efficiency(
    locations: pl.DataFrame,
    weights: pl.DataFrame,
) -> pl.DataFrame:
    """Sum fixed-factor building-efficiency modifiers for each location."""
    _require_columns(
        locations,
        {"location_tag", *EFFICIENCY_CATEGORICAL_FACTORS, *EFFICIENCY_BOOLEAN_FACTORS},
    )
    lookup = efficiency_lookup(weights)
    component_exprs: list[pl.Expr] = []
    component_columns: list[str] = []

    for factor in EFFICIENCY_CATEGORICAL_FACTORS:
        column = f"{factor}_{LOCAL_BUILD_BUILDINGS_EFFICIENCY_COLUMN}"
        mapping = {
            value: weight
            for (lookup_factor, value), weight in lookup.items()
            if lookup_factor == factor
        }
        component_columns.append(column)
        component_exprs.append(
            pl.col(factor)
            .map_elements(
                lambda value, mapping=mapping: mapping.get(_normalize_factor_value(value), 0.0),
                return_dtype=pl.Float64,
            )
            .alias(column)
        )

    for factor in EFFICIENCY_BOOLEAN_FACTORS:
        column = f"{factor}_{LOCAL_BUILD_BUILDINGS_EFFICIENCY_COLUMN}"
        port_bonus = lookup.get((factor, "true"), 0.0)
        component_columns.append(column)
        component_exprs.append(
            pl.when(pl.col(factor).fill_null(False))
            .then(pl.lit(port_bonus))
            .otherwise(pl.lit(NON_PORT_LOCAL_BUILD_EFFICIENCY_PENALTY))
            .alias(column)
        )

    return locations.with_columns(component_exprs).with_columns(
        pl.sum_horizontal(component_columns).alias(LOCAL_BUILD_BUILDINGS_EFFICIENCY_COLUMN)
    )


def compute_local_construction_speed(
    locations: pl.DataFrame,
    weights: pl.DataFrame,
) -> pl.DataFrame:
    """Sum fixed-factor construction-speed modifiers for each location."""
    _require_columns(
        locations,
        {"location_tag", *CONSTRUCTION_SPEED_CATEGORICAL_FACTORS, *CONSTRUCTION_SPEED_BOOLEAN_FACTORS},
    )
    lookup = construction_speed_lookup(weights)
    component_exprs: list[pl.Expr] = []
    component_columns: list[str] = []

    for factor in CONSTRUCTION_SPEED_CATEGORICAL_FACTORS:
        column = f"{factor}_{LOCAL_CONSTRUCTION_SPEED_COLUMN}"
        mapping = {
            value: weight
            for (lookup_factor, value), weight in lookup.items()
            if lookup_factor == factor
        }
        component_columns.append(column)
        component_exprs.append(
            pl.col(factor)
            .map_elements(
                lambda value, mapping=mapping: mapping.get(_normalize_factor_value(value), 0.0),
                return_dtype=pl.Float64,
            )
            .alias(column)
        )

    for factor in CONSTRUCTION_SPEED_BOOLEAN_FACTORS:
        column = f"{factor}_{LOCAL_CONSTRUCTION_SPEED_COLUMN}"
        port_bonus = lookup.get((factor, "true"), 0.0)
        component_columns.append(column)
        component_exprs.append(
            pl.when(pl.col(factor).fill_null(False))
            .then(pl.lit(port_bonus))
            .otherwise(pl.lit(NON_PORT_LOCAL_BUILD_EFFICIENCY_PENALTY))
            .alias(column)
        )

    return locations.with_columns(component_exprs).with_columns(
        pl.sum_horizontal(component_columns).alias(LOCAL_CONSTRUCTION_SPEED_COLUMN)
    )


def build_location_map_frame(
    scores: pl.DataFrame,
    *,
    repo: Path,
    project: Path,
) -> pl.DataFrame:
    """Join scored locations with map geometry for notebook plotting."""
    parser_config = resolve_parser_config(repo, project)
    load_order_path = repo / str(parser_config.get("load_order") or "constructor.load_order.toml")
    profile_name = str(parser_config.get("profile") or "constructor")
    profile = LoadOrderConfig.load(load_order_path).profile(profile_name)
    locations_png = resolve_map_data_file(profile, "locations.png")
    baseline_path = resolve_labeling_baseline_path(repo, project)
    geometry = build_location_geometry_frame(
        baseline_path=baseline_path,
        locations_png_path=locations_png,
        equator_y=3340,
    )
    return (
        scores.join(
            geometry.select("location_tag", "geometry_status", "approx_lon", "approx_lat"),
            on="location_tag",
            how="left",
        )
        .filter(pl.col("geometry_status") == "ok")
    )


FREE_BUILDING_LEVELS_MODIFIER_KEY = "free_building_levels"
EFFICIENCY_MODIFIER_KEY = LOCAL_BUILD_BUILDINGS_EFFICIENCY_COLUMN
CONSTRUCTION_SPEED_MODIFIER_KEY = LOCAL_CONSTRUCTION_SPEED_COLUMN
COMPILED_MODIFIER_KEYS = (
    FREE_BUILDING_LEVELS_MODIFIER_KEY,
    EFFICIENCY_MODIFIER_KEY,
    CONSTRUCTION_SPEED_MODIFIER_KEY,
)
LOCAL_OUTPUT_MODIFIER_PATTERN = re.compile(r"^local_[A-Za-z0-9_]+_output_modifier$")
COMPILE_TOPOGRAPHY_RELATIVE = Path(
    "in_game/common/topography/pp_topography_changes.txt"
)
COMPILE_VEGETATION_RELATIVE = Path(
    "in_game/common/vegetation/pp_vegetation_changes.txt"
)
COMPILE_CLIMATE_RELATIVE = Path(
    "in_game/common/climates/pp_climate_changes.txt"
)
COMPILE_LOCATION_RANKS_RELATIVE = Path(
    "in_game/common/location_ranks/pp_location_rank_adjustments.txt"
)
COMPILE_STATIC_MODIFIERS_RELATIVE = Path(
    "main_menu/common/static_modifiers/pp_location_modifier_adjustments.txt"
)
COMPILE_BUILDING_TYPES_RELATIVE = Path(
    "in_game/common/building_types/pp_governor_building_adjustments.txt"
)
STATIC_MODIFIER_BLOCK_BY_FACTOR: dict[tuple[str, str], str] = {
    ("river_level", "1"): "river_flowing_through_1",
    ("river_level", "2"): "river_flowing_through_2",
    ("river_level", "3"): "river_flowing_through_3",
    ("river_level", "4"): "river_flowing_through_4",
    ("river_level", "5"): "river_flowing_through_5",
    ("road_level", "1"): "has_road",
    ("is_port", "true"): "is_port",
    ("market_center", "true"): "market_center",
    ("capital", "true"): "capital",
    ("province_capital", "true"): "province_capital",
}
BUILDING_TYPE_BLOCK_BY_FACTOR: dict[tuple[str, str], str] = {
    ("naval_governor", "true"): "naval_governor",
    ("local_governor", "true"): "local_governor",
}
BUILDING_TYPE_INNER_HEADER = "modifier"
CompileMode = str  # "inject_delta" | "replace_absolute"


@dataclass
class ModifierBaselineResolver:
    """Resolve vanilla modifier baselines for TRY_INJECT delta compilation."""

    location_ranks: LocationRankData
    static_modifiers: StaticModifierData
    topography: TopographyData
    vegetation: VegetationData
    climates: ModifierBlockData
    building_types: BuildingTypeData
    _cache: dict[tuple[str, str, str | None, str], float] = field(default_factory=dict, repr=False)

    def inject_value(
        self,
        *,
        source: str,
        block_name: str,
        inner_header: str | None,
        modifier_key: str,
        csv_final: float,
    ) -> float:
        baseline = self.baseline(
            source=source,
            block_name=block_name,
            inner_header=inner_header,
            modifier_key=modifier_key,
        )
        return csv_final - baseline

    def baseline(
        self,
        *,
        source: str,
        block_name: str,
        inner_header: str | None,
        modifier_key: str,
    ) -> float:
        cache_key = (source, block_name, inner_header, modifier_key)
        if cache_key not in self._cache:
            self._cache[cache_key] = self._load_baseline(
                source=source,
                block_name=block_name,
                inner_header=inner_header,
                modifier_key=modifier_key,
            )
        return self._cache[cache_key]

    def _load_baseline(
        self,
        *,
        source: str,
        block_name: str,
        inner_header: str | None,
        modifier_key: str,
    ) -> float:
        if source == "static_modifier":
            return self.static_modifiers.modifier_baseline(block_name, inner_header, modifier_key)
        if source == "location_rank":
            return self.location_ranks.modifier_baseline(block_name, inner_header, modifier_key)
        if source == "topography":
            return self.topography.modifier_baseline(block_name, inner_header, modifier_key)
        if source == "vegetation":
            return self.vegetation.modifier_baseline(block_name, inner_header, modifier_key)
        if source == "climate":
            return self.climates.modifier_baseline(block_name, inner_header, modifier_key)
        if source == "building_type":
            return self.building_types.modifier_baseline(block_name, inner_header, modifier_key)
        return 0.0


def load_modifier_baseline_resolver(repo: Path) -> ModifierBaselineResolver:
    load_order_path = repo / "constructor.load_order.toml"
    profile = LoadOrderConfig.load(load_order_path).profile("vanilla")
    return ModifierBaselineResolver(
        location_ranks=load_location_rank_data(profile=profile, load_order_path=load_order_path),
        static_modifiers=load_static_modifier_data(profile=profile, load_order_path=load_order_path),
        topography=load_topography_data(profile=profile, load_order_path=load_order_path),
        vegetation=load_vegetation_data(profile=profile, load_order_path=load_order_path),
        climates=load_modifier_block_data(profile, relative_dir="climates"),
        building_types=load_building_type_data(profile=profile, load_order_path=load_order_path),
    )


def audit_compile_modifier_baselines(repo: Path) -> pl.DataFrame:
    """Report parser-resolved vanilla baselines for every compiled sheet target."""
    weights = read_local_free_building_level_sheet_csv(repo=repo)
    baselines = load_modifier_baseline_resolver(repo)
    rows: list[dict[str, object]] = []

    for row in weights.to_dicts():
        factor = str(row["factor"])
        value = str(row["value"])
        if factor in {"topography", "vegetation", "climate", "location_rank"}:
            inner_header = "location_modifier" if factor != "location_rank" else "rank_modifier"
            block_name = value
            baseline_source = factor
            compiled = True
        elif factor == "development":
            block_name = "development"
            inner_header = None
            baseline_source = "static_modifier"
            compiled = True
        elif (factor, value) in BUILDING_TYPE_BLOCK_BY_FACTOR:
            block_name = BUILDING_TYPE_BLOCK_BY_FACTOR[(factor, value)]
            baseline_source = "building_type"
            inner_header = BUILDING_TYPE_INNER_HEADER
            compiled = True
        elif (factor, value) in STATIC_MODIFIER_BLOCK_BY_FACTOR:
            block_name = STATIC_MODIFIER_BLOCK_BY_FACTOR[(factor, value)]
            baseline_source = "static_modifier"
            inner_header = None
            compiled = True
        elif factor == "road_level" and value != "0":
            block_name = STATIC_MODIFIER_BLOCK_BY_FACTOR.get((factor, value), "")
            baseline_source = "static_modifier"
            inner_header = None
            compiled = bool(block_name)
        else:
            continue

        for modifier_key in COMPILED_MODIFIER_KEYS:
            csv_value = row.get(modifier_key)
            if csv_value is None or (isinstance(csv_value, float) and np.isnan(csv_value)):
                continue
            vanilla_baseline = baselines.baseline(
                source=baseline_source,
                block_name=block_name,
                inner_header=inner_header,
                modifier_key=modifier_key,
            )
            entry_exists = _compile_target_exists(
                baselines,
                baseline_source=baseline_source,
                block_name=block_name,
            )
            rows.append(
                {
                    "factor": factor,
                    "value": value,
                    "block_name": block_name,
                    "baseline_source": baseline_source,
                    "inner_header": inner_header,
                    "modifier_key": modifier_key,
                    "csv_final": float(csv_value),
                    "vanilla_baseline": vanilla_baseline,
                    "compiled_inject": float(csv_value) - vanilla_baseline
                    if factor != "development"
                    else float(csv_value),
                    "entry_exists_in_parser": entry_exists,
                    "compiled_to_mod": compiled,
                }
            )

    return pl.DataFrame(rows).sort(["factor", "value", "modifier_key"])


def _compile_target_exists(
    baselines: ModifierBaselineResolver,
    *,
    baseline_source: str,
    block_name: str,
) -> bool:
    if baseline_source == "static_modifier":
        return block_name in baselines.static_modifiers._by_name
    if baseline_source == "location_rank":
        return block_name in baselines.location_ranks._by_name
    if baseline_source == "topography":
        return block_name in baselines.topography._by_name
    if baseline_source == "vegetation":
        return block_name in baselines.vegetation._by_name
    if baseline_source == "climate":
        return block_name in baselines.climates._by_name
    if baseline_source == "building_type":
        return block_name in baselines.building_types._by_name
    return False


def compile_free_building_level_modifiers(repo: Path, mod_root: Path) -> None:
    """Compile sheet weights into mod TRY_INJECT / TRY_REPLACE modifier blocks."""
    weights = read_local_free_building_level_sheet_csv(repo=repo)
    baselines = load_modifier_baseline_resolver(repo)
    updated_files = 0
    updated_files += _compile_category_file(
        mod_root / COMPILE_TOPOGRAPHY_RELATIVE,
        weights,
        baselines=baselines,
        factor="topography",
        inner_header="location_modifier",
    )
    updated_files += _compile_category_file(
        mod_root / COMPILE_VEGETATION_RELATIVE,
        weights,
        baselines=baselines,
        factor="vegetation",
        inner_header="location_modifier",
    )
    updated_files += _compile_category_file(
        mod_root / COMPILE_CLIMATE_RELATIVE,
        weights,
        baselines=baselines,
        factor="climate",
        inner_header="location_modifier",
    )
    updated_files += _compile_local_output_neutralizers(
        mod_root / COMPILE_TOPOGRAPHY_RELATIVE,
        baselines=baselines,
        factor="topography",
        inner_header="location_modifier",
    )
    updated_files += _compile_local_output_neutralizers(
        mod_root / COMPILE_VEGETATION_RELATIVE,
        baselines=baselines,
        factor="vegetation",
        inner_header="location_modifier",
    )
    updated_files += _compile_local_output_neutralizers(
        mod_root / COMPILE_CLIMATE_RELATIVE,
        baselines=baselines,
        factor="climate",
        inner_header="location_modifier",
    )
    updated_files += _compile_category_file(
        mod_root / COMPILE_LOCATION_RANKS_RELATIVE,
        weights,
        baselines=baselines,
        factor="location_rank",
        inner_header="rank_modifier",
    )
    updated_files += _compile_static_modifier_file(
        mod_root / COMPILE_STATIC_MODIFIERS_RELATIVE,
        weights,
        baselines=baselines,
    )
    updated_files += _compile_building_type_file(
        mod_root / COMPILE_BUILDING_TYPES_RELATIVE,
        weights,
        baselines=baselines,
    )
    if updated_files:
        print(
            f"Compiled free building level modifiers into {updated_files} mod file(s).",
            flush=True,
        )


def _compile_category_file(
    path: Path,
    weights: pl.DataFrame,
    *,
    baselines: ModifierBaselineResolver,
    factor: str,
    inner_header: str,
) -> int:
    if not path.is_file():
        raise FileNotFoundError(f"Cannot compile building modifiers; missing file: {path}")
    text = _read_compile_text(path)
    changed = False
    baseline_source = factor
    for row in weights.filter(pl.col("factor") == factor).to_dicts():
        block_name = str(row["value"])
        updates = _modifier_updates_from_row(
            row,
            baselines=baselines,
            block_name=block_name,
            inner_header=inner_header,
            baseline_source=baseline_source,
            compile_mode="inject_delta",
        )
        if not updates:
            continue
        result = _update_clausewitz_file_text(
            text,
            block_name,
            inner_header=inner_header,
            updates=updates,
        )
        if result is None:
            text = _append_try_inject_block(
                text,
                block_name,
                inner_header=inner_header,
                updates=updates,
            )
            changed = True
        else:
            new_text, block_changed = result
            if block_changed:
                text = new_text
                changed = True
    if changed and _write_compile_text_if_changed(path, text):
        return 1
    return 1 if changed else 0


def _compile_local_output_neutralizers(
    path: Path,
    *,
    baselines: ModifierBaselineResolver,
    factor: str,
    inner_header: str,
) -> int:
    if not path.is_file():
        raise FileNotFoundError(f"Cannot compile local output neutralizers; missing file: {path}")
    text = _read_compile_text(path)
    changed = False
    for block_name, updates in local_output_neutralizer_updates(
        baselines,
        factor=factor,
        inner_header=inner_header,
    ).items():
        result = _update_clausewitz_file_text(
            text,
            block_name,
            inner_header=inner_header,
            updates=updates,
        )
        if result is None:
            text = _append_try_inject_block(
                text,
                block_name,
                inner_header=inner_header,
                updates=updates,
            )
            changed = True
        else:
            new_text, block_changed = result
            if block_changed:
                text = new_text
                changed = True
    if changed and _write_compile_text_if_changed(path, text):
        return 1
    return 1 if changed else 0


def local_output_neutralizer_updates(
    baselines: ModifierBaselineResolver,
    *,
    factor: str,
    inner_header: str,
) -> dict[str, dict[str, float]]:
    """Return TRY_INJECT values that make vanilla local goods output modifiers net zero."""
    updates: dict[str, dict[str, float]] = {}
    for block_name, modifiers in _local_output_baselines_by_block(
        baselines,
        factor=factor,
        inner_header=inner_header,
    ).items():
        updates[block_name] = {
            modifier_key: -baseline
            for modifier_key, baseline in sorted(modifiers.items())
            if baseline != 0
        }
    return {block_name: block_updates for block_name, block_updates in updates.items() if block_updates}


def _local_output_baselines_by_block(
    baselines: ModifierBaselineResolver,
    *,
    factor: str,
    inner_header: str,
) -> dict[str, dict[str, float]]:
    entries: Mapping[str, Any]
    if factor == "topography":
        entries = baselines.topography._by_name
    elif factor == "vegetation":
        entries = baselines.vegetation._by_name
    elif factor == "climate":
        entries = baselines.climates._by_name
    else:
        raise ValueError(f"Unsupported local output neutralizer factor: {factor}")

    result: dict[str, dict[str, float]] = {}
    for block_name, entry in sorted(entries.items()):
        modifiers = _entry_modifier_mapping(entry, inner_header)
        output_modifiers = {
            key: value
            for key, value in modifiers.items()
            if LOCAL_OUTPUT_MODIFIER_PATTERN.fullmatch(key)
        }
        if output_modifiers:
            result[block_name] = output_modifiers
    return result


def _entry_modifier_mapping(entry: Any, inner_header: str | None) -> Mapping[str, float]:
    if inner_header == "location_modifier" and hasattr(entry, "location_modifiers"):
        return entry.location_modifiers
    if inner_header is None:
        return entry.modifiers
    return entry.nested_modifiers.get(inner_header, {})


def _compile_static_modifier_file(
    path: Path,
    weights: pl.DataFrame,
    *,
    baselines: ModifierBaselineResolver,
) -> int:
    if not path.is_file():
        raise FileNotFoundError(f"Cannot compile building modifiers; missing file: {path}")
    text = _read_compile_text(path)
    changed = False

    for (factor, value), block_name in STATIC_MODIFIER_BLOCK_BY_FACTOR.items():
        row = weights.filter(
            (pl.col("factor") == factor) & (pl.col("value") == value)
        )
        if row.is_empty():
            continue
        updates = _modifier_updates_from_row(
            row.to_dicts()[0],
            baselines=baselines,
            block_name=block_name,
            inner_header=None,
            baseline_source="static_modifier",
            compile_mode="inject_delta",
        )
        if not updates:
            continue
        result = _update_clausewitz_file_text(text, block_name, inner_header=None, updates=updates)
        if result is None:
            text = _append_try_inject_block(text, block_name, inner_header=None, updates=updates)
            changed = True
        else:
            new_text, block_changed = result
            if block_changed:
                text = new_text
                changed = True

    development_row = weights.filter(
        (pl.col("factor") == "development") & (pl.col("value") == "per_point")
    )
    if not development_row.is_empty():
        updates = _modifier_updates_from_row(
            development_row.to_dicts()[0],
            baselines=baselines,
            block_name="development",
            inner_header=None,
            baseline_source="static_modifier",
            compile_mode="replace_absolute",
        )
        if updates:
            result = _update_clausewitz_file_text(
                text,
                "development",
                inner_header=None,
                updates=updates,
            )
            if result is not None:
                new_text, block_changed = result
                if block_changed:
                    text = new_text
                    changed = True

    if changed and _write_compile_text_if_changed(path, text):
        return 1
    return 1 if changed else 0


def _compile_building_type_file(
    path: Path,
    weights: pl.DataFrame,
    *,
    baselines: ModifierBaselineResolver,
) -> int:
    if not path.is_file():
        raise FileNotFoundError(f"Cannot compile building modifiers; missing file: {path}")
    text = _read_compile_text(path)
    changed = False

    for (factor, value), block_name in BUILDING_TYPE_BLOCK_BY_FACTOR.items():
        row = weights.filter(
            (pl.col("factor") == factor) & (pl.col("value") == value)
        )
        if row.is_empty():
            continue
        updates = _modifier_updates_from_row(
            row.to_dicts()[0],
            baselines=baselines,
            block_name=block_name,
            inner_header=BUILDING_TYPE_INNER_HEADER,
            baseline_source="building_type",
            compile_mode="inject_delta",
        )
        if not updates:
            continue
        result = _update_clausewitz_file_text(
            text,
            block_name,
            inner_header=BUILDING_TYPE_INNER_HEADER,
            updates=updates,
        )
        if result is None:
            text = _append_try_inject_block(
                text,
                block_name,
                inner_header=BUILDING_TYPE_INNER_HEADER,
                updates=updates,
            )
            changed = True
        else:
            new_text, block_changed = result
            if block_changed:
                text = new_text
                changed = True

    if changed and _write_compile_text_if_changed(path, text):
        return 1
    return 1 if changed else 0


def _modifier_updates_from_row(
    row: Mapping[str, object],
    *,
    baselines: ModifierBaselineResolver,
    block_name: str,
    inner_header: str | None,
    baseline_source: str,
    compile_mode: CompileMode,
) -> dict[str, float]:
    updates: dict[str, float] = {}
    for modifier_key in COMPILED_MODIFIER_KEYS:
        raw_value = row.get(modifier_key)
        if raw_value is None or (isinstance(raw_value, float) and np.isnan(raw_value)):
            continue
        csv_final = float(raw_value)
        if compile_mode == "replace_absolute":
            updates[modifier_key] = csv_final
        else:
            updates[modifier_key] = baselines.inject_value(
                source=baseline_source,
                block_name=block_name,
                inner_header=inner_header,
                modifier_key=modifier_key,
                csv_final=csv_final,
            )
    return updates


def _update_clausewitz_file_text(
    text: str,
    block_name: str,
    *,
    inner_header: str | None,
    updates: dict[str, float],
) -> tuple[str, bool] | None:
    located = _locate_top_level_block(text, block_name)
    if located is None:
        return None
    start, end, block_text = located
    if inner_header is not None:
        inner = _locate_inner_block(block_text, inner_header)
        if inner is None:
            return None
        inner_start, inner_end, inner_text = inner
        updated_inner, changed = _update_block_keys(inner_text, updates)
        if not changed:
            return text, False
        new_block = (
            block_text[:inner_start]
            + updated_inner
            + block_text[inner_end:]
        )
    else:
        new_block, changed = _update_block_keys(block_text, updates)
        if not changed:
            return text, False
    return text[:start] + new_block + text[end:], True


def _update_block_keys(block_text: str, updates: dict[str, float]) -> tuple[str, bool]:
    lines = block_text.splitlines(keepends=True)
    if not lines:
        return block_text, False
    indent = _detect_key_indent(lines)
    key_pattern = re.compile(rf"^({re.escape(indent)})([A-Za-z0-9_]+)\s*=\s*(-?[0-9.]+)")
    seen: set[str] = set()
    changed = False
    new_lines: list[str] = []
    for line in lines:
        match = key_pattern.match(line)
        if match and match.group(2) in updates:
            key = match.group(2)
            seen.add(key)
            formatted = _format_modifier_value(updates[key])
            stripped = line.rstrip("\r\n")
            comment_match = re.search(r"(\s#.*)$", stripped)
            comment = comment_match.group(1) if comment_match else ""
            newline = line[len(stripped) :]
            new_line = f"{indent}{key} = {formatted}{comment}{newline}"
            new_lines.append(new_line)
            if new_line != line:
                changed = True
        else:
            new_lines.append(line)

    missing = [key for key in updates if key not in seen]
    if missing:
        insert_at = _insertion_index_before_closing_brace(new_lines)
        newline = new_lines[insert_at - 1][len(new_lines[insert_at - 1].rstrip("\r\n")) :] if insert_at else "\n"
        additions = [
            f"{indent}{key} = {_format_modifier_value(updates[key])}{newline}"
            for key in missing
        ]
        new_lines[insert_at:insert_at] = additions
        changed = True
    return "".join(new_lines), changed


def _append_try_inject_block(
    text: str,
    block_name: str,
    *,
    inner_header: str | None,
    updates: dict[str, float],
) -> str:
    newline = "\r\n" if "\r\n" in text else "\n"
    if text and not text.endswith(("\n", "\r\n")):
        text += newline
    body_indent = "\t"
    key_indent = f"{body_indent}\t" if inner_header else body_indent
    lines = [f"TRY_INJECT:{block_name} = {{{newline}"]
    if inner_header is not None:
        lines.append(f"{body_indent}{inner_header} = {{{newline}")
    for key, value in updates.items():
        lines.append(f"{key_indent}{key} = {_format_modifier_value(value)}{newline}")
    if inner_header is not None:
        lines.append(f"{body_indent}}}{newline}")
    lines.append(f"}}{newline}")
    return text + "".join(lines)


def _locate_top_level_block(text: str, block_name: str) -> tuple[int, int, str] | None:
    pattern = re.compile(
        rf"TRY_(?:INJECT|REPLACE):{re.escape(block_name)}\s*=\s*\{{",
        re.MULTILINE,
    )
    match = pattern.search(text)
    if not match:
        return None
    open_brace, close_brace = _find_block_bounds(text, match.start())
    return match.start(), close_brace + 1, text[match.start() : close_brace + 1]


def _locate_inner_block(outer: str, inner_name: str) -> tuple[int, int, str] | None:
    pattern = re.compile(rf"{re.escape(inner_name)}\s*=\s*\{{", re.MULTILINE)
    match = pattern.search(outer)
    if not match:
        return None
    open_brace, close_brace = _find_block_bounds(outer, match.start())
    return match.start(), close_brace + 1, outer[match.start() : close_brace + 1]


def _find_block_bounds(text: str, start_index: int) -> tuple[int, int]:
    open_brace = text.index("{", start_index)
    depth = 0
    for index in range(open_brace, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return open_brace, index
    raise ValueError(f"Unbalanced braces near index {start_index}")


def _detect_key_indent(lines: list[str]) -> str:
    for line in lines:
        match = re.match(r"^(\s+)[A-Za-z0-9_]+\s*=", line)
        if match:
            return match.group(1)
    return "\t"


def _insertion_index_before_closing_brace(lines: list[str]) -> int:
    for index in range(len(lines) - 1, -1, -1):
        if lines[index].strip() == "}":
            return index
    return len(lines)


def _format_modifier_value(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _read_compile_text(path: Path) -> str:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return handle.read()


def _write_compile_text_if_changed(path: Path, text: str) -> bool:
    existing = _read_compile_text(path) if path.is_file() else ""
    if existing == text:
        return False
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        handle.write(text)
    return True


def summarize_free_building_levels(frame: pl.DataFrame, group_by: str) -> pl.DataFrame:
    _require_columns(frame, {group_by, "free_building_levels"})
    summary = (
        frame.group_by(group_by)
        .agg(
            pl.len().alias("locations"),
            pl.col("free_building_levels").mean().alias("mean_free_building_levels"),
            pl.col("free_building_levels").median().alias("median_free_building_levels"),
            pl.col("free_building_levels").min().alias("min_free_building_levels"),
            pl.col("free_building_levels").max().alias("max_free_building_levels"),
            pl.col("free_building_levels").sum().alias("total_free_building_levels"),
        )
        .sort("total_free_building_levels", descending=True)
    )
    return round_numeric_columns(summary)


def round_numeric_columns(frame: pl.DataFrame, decimals: int = DEFAULT_DISPLAY_DECIMALS) -> pl.DataFrame:
    """Round floating-point columns for notebook-friendly display."""
    float_columns = [
        column
        for column, dtype in frame.schema.items()
        if dtype in (pl.Float32, pl.Float64)
    ]
    if not float_columns:
        return frame
    return frame.with_columns(pl.col(column).round(decimals).alias(column) for column in float_columns)


def contribution_category_summary(frame: pl.DataFrame) -> pl.DataFrame:
    """Summarize each sheet factor's contribution to the global total."""
    _require_scored_columns(frame)
    global_total = _column_total(frame, "free_building_levels")
    global_absolute_total = _global_absolute_component_total(frame)
    rows = []
    for factor in ALL_FACTORS:
        component = _component_column(factor)
        total = _column_total(frame, component)
        absolute_total = _column_absolute_total(frame, component)
        rows.append(
            {
                "factor_group": FACTOR_GROUPS[factor],
                "factor": factor,
                "locations": frame.height,
                "nonzero_locations": _nonzero_count(frame, component),
                "total_contribution": total,
                "share_of_global_total_pct": _percentage(total, global_total),
                "absolute_contribution": absolute_total,
                "share_of_global_absolute_contribution_pct": _percentage(
                    absolute_total,
                    global_absolute_total,
                ),
                "mean_contribution_per_location": _column_mean(frame, component),
            }
        )
    return round_numeric_columns(pl.DataFrame(rows).sort("absolute_contribution", descending=True))


def contribution_factor_group_summary(frame: pl.DataFrame) -> pl.DataFrame:
    """Summarize fixed-vs-dynamic factor groups."""
    _require_scored_columns(frame)
    global_total = _column_total(frame, "free_building_levels")
    global_absolute_total = _global_absolute_component_total(frame)
    group_totals: dict[str, dict[str, float | int]] = defaultdict(
        lambda: {"factors": 0, "active_factors": 0, "total": 0.0, "absolute_total": 0.0}
    )
    for factor in ALL_FACTORS:
        component = _component_column(factor)
        group = FACTOR_GROUPS[factor]
        total = _column_total(frame, component)
        absolute_total = _column_absolute_total(frame, component)
        group_totals[group]["factors"] += 1
        group_totals[group]["active_factors"] += int(absolute_total > 0)
        group_totals[group]["total"] += total
        group_totals[group]["absolute_total"] += absolute_total

    rows = []
    for group, totals in group_totals.items():
        total = float(totals["total"] or 0.0)
        absolute_total = float(totals["absolute_total"] or 0.0)
        rows.append(
            {
                "factor_group": group,
                "factors": int(totals["factors"]),
                "active_factors": int(totals["active_factors"]),
                "total_contribution": total,
                "share_of_global_total_pct": _percentage(total, global_total),
                "absolute_contribution": absolute_total,
                "share_of_global_absolute_contribution_pct": _percentage(
                    absolute_total,
                    global_absolute_total,
                ),
            }
        )
    return round_numeric_columns(pl.DataFrame(rows).sort("absolute_contribution", descending=True))


def contribution_value_summary(frame: pl.DataFrame) -> pl.DataFrame:
    """Summarize each factor/value split's contribution to the global total."""
    _require_scored_columns(frame)
    global_total = _column_total(frame, "free_building_levels")
    global_absolute_total = _global_absolute_component_total(frame)
    factor_totals = {
        factor: _column_total(frame, _component_column(factor))
        for factor in ALL_FACTORS
    }
    factor_absolute_totals = {
        factor: _column_absolute_total(frame, _component_column(factor))
        for factor in ALL_FACTORS
    }

    rows: list[dict[str, object]] = []
    for factor in ALL_FACTORS:
        component = _component_column(factor)
        value_frame = _factor_value_frame(frame, factor, component)
        for row in value_frame.to_dicts():
            total = float(row["total_contribution"] or 0.0)
            absolute_total = float(row["absolute_contribution"] or 0.0)
            rows.append(
                {
                    "factor_group": FACTOR_GROUPS[factor],
                    "factor": factor,
                    "value": str(row["value"]),
                    "locations": int(row["locations"]),
                    "nonzero_locations": int(row["nonzero_locations"]),
                    "total_contribution": total,
                    "share_of_global_total_pct": _percentage(total, global_total),
                    "share_of_factor_total_pct": _percentage(total, factor_totals[factor]),
                    "absolute_contribution": absolute_total,
                    "share_of_global_absolute_contribution_pct": _percentage(
                        absolute_total,
                        global_absolute_total,
                    ),
                    "share_of_factor_absolute_contribution_pct": _percentage(
                        absolute_total,
                        factor_absolute_totals[factor],
                    ),
                    "mean_contribution_per_location": float(row["mean_contribution_per_location"] or 0.0),
                }
            )
    return round_numeric_columns(
        pl.DataFrame(rows).sort(
            ["factor_group", "factor", "absolute_contribution"],
            descending=[False, False, True],
        )
    )


def resolve_labeling_baseline_path(repo: Path, project: Path) -> Path:
    with project.open("rb") as handle:
        project_config = tomllib.load(handle)
    labeling = project_config.get("labeling")
    if not isinstance(labeling, dict):
        raise ValueError(f"{project}: missing [labeling] section")
    config_path = _resolve_path(repo, labeling.get("config") or "labeling_output_modifiers.yaml")
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{config_path}: expected mapping")
    return _resolve_path(config_path.parent, raw.get("baseline_parquet"))


def resolve_parser_config(repo: Path, project: Path) -> dict[str, object]:
    with project.open("rb") as handle:
        project_config = tomllib.load(handle)
    parser = project_config.get("parser") or {}
    if not isinstance(parser, dict):
        raise ValueError(f"{project}: [parser] must be a mapping")
    return parser


def load_location_ranks(profile: DataProfile) -> dict[str, str]:
    ranks: dict[str, str] = {}
    for path in _setup_start_files(profile, "07_cities_and_buildings.txt"):
        for entry in _entries_under_key(path, "locations"):
            if not isinstance(entry.value, CList):
                continue
            rank = entry.value.first("rank")
            if isinstance(rank, str):
                ranks[entry.key] = rank
    return ranks


def load_market_centers(profile: DataProfile) -> set[str]:
    markets: set[str] = set()
    for path in _setup_start_files(profile, "03_markets.txt"):
        for entry in _entries_under_key(path, "market_manager"):
            if entry.key == "add_market" and isinstance(entry.value, str):
                markets.add(entry.value)
    return markets


def load_road_locations(profile: DataProfile) -> set[str]:
    roads: set[str] = set()
    for path in _setup_start_files(profile, "09_roads.txt"):
        for entry in _entries_under_key(path, "road_network"):
            if isinstance(entry.value, str):
                roads.add(entry.key)
                roads.add(entry.value)
    return roads


def load_road_type_levels(profile: DataProfile) -> dict[str, int]:
    road_types: dict[str, int] = {}
    for path in _in_game_common_files(profile, "road_types", "00_generic.txt"):
        for entry in parse_file(path).entries:
            if not isinstance(entry.value, CList):
                continue
            level = entry.value.first("level")
            if isinstance(level, int | float):
                road_types[entry.key] = int(level)
    return road_types


def load_country_capitals(profile: DataProfile) -> set[str]:
    capitals: set[str] = set()
    for path in _setup_start_files(profile, "10_countries.txt"):
        for entry in _walk_entries(parse_file(path).entries):
            if entry.key == "capital" and isinstance(entry.value, str):
                capitals.add(entry.value)
    return capitals


def load_development_weights(profile: DataProfile) -> dict[str, float]:
    weights: dict[str, float] = {}
    for path in _setup_start_files(profile, "14_development.txt"):
        for entry in _entries_under_key(path, "development"):
            if isinstance(entry.value, int | float):
                weights[entry.key] = float(entry.value)
    return weights


def load_port_locations(profile: DataProfile) -> set[str]:
    ports: set[str] = set()
    for path in _map_data_files(profile, "ports.csv"):
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle, delimiter=";")
            for row in reader:
                tag = (row.get("LandProvince") or "").strip()
                if tag:
                    ports.add(tag)
    return ports


def extract_river_levels_from_maps(
    locations: pl.DataFrame,
    *,
    locations_png_path: str | Path,
    rivers_png_path: str | Path,
    chunk_rows: int = 256,
) -> pl.DataFrame:
    """Return per-location river level from the game map rasters.

    Palette values 4 and 5 line up with the game-start development comment.
    Marker/border colors are collapsed to level 1 or 5, then the result is
    clamped to the baseline ``has_river`` column so raster-edge noise does not
    create new river locations.
    """
    _require_columns(locations, {"location_tag", "named_location_hex", "has_river"})
    if chunk_rows <= 0:
        raise ValueError("chunk_rows must be positive")

    color_to_tag = {
        _hex_to_rgb_int(str(row["named_location_hex"])): str(row["location_tag"])
        for row in locations.select("location_tag", "named_location_hex").drop_nulls("named_location_hex").to_dicts()
    }
    has_river = {
        str(row["location_tag"]): bool(row["has_river"])
        for row in locations.select("location_tag", "has_river").to_dicts()
    }
    target_values = np.array(sorted(color_to_tag), dtype=np.uint32)
    river_indices = np.array(sorted(RIVER_INDEX_LEVELS), dtype=np.uint8)
    levels: defaultdict[str, int] = defaultdict(int)

    Image.MAX_IMAGE_PIXELS = None
    with Image.open(locations_png_path) as location_image, Image.open(rivers_png_path) as river_image:
        location_image = location_image.convert("RGB")
        if location_image.size != river_image.size:
            raise ValueError(
                f"locations/rivers map sizes differ: {location_image.size} != {river_image.size}"
            )
        width, height = location_image.size
        for y0 in range(0, height, chunk_rows):
            y1 = min(height, y0 + chunk_rows)
            location_chunk = np.asarray(location_image.crop((0, y0, width, y1)), dtype=np.uint32)
            packed_locations = (
                (location_chunk[:, :, 0] << 16)
                | (location_chunk[:, :, 1] << 8)
                | location_chunk[:, :, 2]
            )
            river_chunk = np.asarray(river_image.crop((0, y0, width, y1)), dtype=np.uint8)
            flat_locations = packed_locations.reshape(-1)
            flat_rivers = river_chunk.reshape(-1)
            mask = np.isin(flat_locations, target_values) & np.isin(flat_rivers, river_indices)
            if not bool(mask.any()):
                continue
            for color_raw, river_raw in zip(flat_locations[mask], flat_rivers[mask], strict=True):
                tag = color_to_tag.get(int(color_raw))
                if tag is None:
                    continue
                level = RIVER_INDEX_LEVELS[int(river_raw)]
                if level > levels[tag]:
                    levels[tag] = level

    rows = []
    for tag, has_any_river in has_river.items():
        level = levels.get(tag, 0)
        if has_any_river and level <= 0:
            level = 1
        if not has_any_river:
            level = 0
        rows.append({"location_tag": tag, "river_level": level})
    return pl.DataFrame(rows, schema={"location_tag": pl.String, "river_level": pl.Int64})


def resolve_map_data_file(profile: DataProfile, filename: str) -> Path:
    paths = _map_data_files(profile, filename)
    if not paths:
        raise FileNotFoundError(f"{filename} not found in profile {profile.name!r} map_data")
    return paths[-1]


def _diagnostics(locations: pl.DataFrame, lookup: Mapping[tuple[str, str], float]) -> pl.DataFrame:
    rows: list[dict[str, object]] = []
    known = {*CATEGORICAL_FACTORS, *BOOLEAN_FACTORS, *NUMERIC_FACTORS}
    for factor, value in sorted(lookup):
        if factor not in known:
            rows.append(
                {
                    "severity": "warning",
                    "diagnostic": "unknown_sheet_factor",
                    "factor": factor,
                    "value": value,
                    "detail": "Sheet factor is not used by the capacity model.",
                }
            )

    for factor in CATEGORICAL_FACTORS:
        present = {
            _normalize_factor_value(value)
            for value in locations.select(factor).unique().get_column(factor).to_list()
        }
        weighted = {value for lookup_factor, value in lookup if lookup_factor == factor}
        for value in sorted(present - weighted):
            rows.append(
                {
                    "severity": "info",
                    "diagnostic": "location_value_missing_weight",
                    "factor": factor,
                    "value": value,
                    "detail": "Location value has no sheet row and will score as 0.",
                }
            )
        for value in sorted(weighted - present):
            rows.append(
                {
                    "severity": "info",
                    "diagnostic": "sheet_value_not_present",
                    "factor": factor,
                    "value": value,
                    "detail": "Sheet row is currently unused by game-start locations.",
                }
            )

    for factor in BOOLEAN_FACTORS:
        if (factor, "true") not in lookup:
            rows.append(
                {
                    "severity": "info",
                    "diagnostic": "boolean_factor_missing_weight",
                    "factor": factor,
                    "value": "true",
                    "detail": "Boolean flag has no sheet row and will score as 0.",
                }
            )

    schema = {
        "severity": pl.String,
        "diagnostic": pl.String,
        "factor": pl.String,
        "value": pl.String,
        "detail": pl.String,
    }
    return pl.DataFrame(rows, schema=schema)


def _development_expr(weights: Mapping[str, float]) -> pl.Expr:
    additive_keys = (
        "topography",
        "vegetation",
        "climate",
        "location_rank",
        "region",
        "area",
        "province",
        "location_tag",
    )
    expr = pl.lit(float(weights.get("base", 0.0)))
    for column in additive_keys:
        expr += pl.col(column).map_elements(
            lambda value, weights=weights: float(weights.get(str(value), 0.0)),
            return_dtype=pl.Float64,
        )
    expr += (
        pl.col("natural_harbor_suitability")
        .fill_null(0.0)
        .cast(pl.Float64)
        * pl.lit(float(weights.get("coastal", 0.0)))
    )
    expr += pl.col("river_level").fill_null(0).cast(pl.Float64) * pl.lit(
        float(weights.get("river", 0.0))
    )
    expr += pl.col("road_level").fill_null(0).cast(pl.Float64) * pl.lit(
        float(weights.get("road", 0.0))
    )
    return expr


def _effective_development_expr() -> pl.Expr:
    return (
        pl.col("development")
        .fill_null(0.0)
        .cast(pl.Float64)
        .clip(MIN_EFFECTIVE_DEVELOPMENT, MAX_EFFECTIVE_DEVELOPMENT)
    )


def _lookup_development_expr(column: str, weights: Mapping[str, float]) -> pl.Expr:
    return pl.col(column).map_elements(
        lambda value, weights=weights: float(weights.get(str(value), 0.0)),
        return_dtype=pl.Float64,
    )


def _require_scored_columns(frame: pl.DataFrame) -> None:
    _require_columns(frame, {"free_building_levels", *(_component_column(factor) for factor in ALL_FACTORS)})


def _factor_value_frame(frame: pl.DataFrame, factor: str, component: str) -> pl.DataFrame:
    if factor in CATEGORICAL_FACTORS:
        value_expr = pl.col(factor).map_elements(_normalize_factor_value, return_dtype=pl.String)
    elif factor in BOOLEAN_FACTORS:
        value_expr = (
            pl.when(pl.col(factor).fill_null(False))
            .then(pl.lit("true"))
            .otherwise(pl.lit("false"))
        )
    elif factor in NUMERIC_FACTORS:
        value_expr = pl.lit("per_point")
    else:
        raise ValueError(f"Unsupported contribution factor: {factor}")
    return (
        frame.select(value_expr.alias("value"), pl.col(component).cast(pl.Float64).alias("contribution"))
        .group_by("value")
        .agg(
            pl.len().alias("locations"),
            (pl.col("contribution").abs() > 0).sum().alias("nonzero_locations"),
            pl.col("contribution").sum().alias("total_contribution"),
            pl.col("contribution").abs().sum().alias("absolute_contribution"),
            pl.col("contribution").mean().alias("mean_contribution_per_location"),
        )
        .sort("absolute_contribution", descending=True)
    )


def _component_column(factor: str) -> str:
    return f"{factor}_free_building_levels"


def _column_total(frame: pl.DataFrame, column: str) -> float:
    value = frame.select(pl.col(column).sum()).item()
    return float(value or 0.0)


def _column_absolute_total(frame: pl.DataFrame, column: str) -> float:
    value = frame.select(pl.col(column).abs().sum()).item()
    return float(value or 0.0)


def _column_mean(frame: pl.DataFrame, column: str) -> float:
    value = frame.select(pl.col(column).mean()).item()
    return float(value or 0.0)


def _nonzero_count(frame: pl.DataFrame, column: str) -> int:
    return int(frame.select((pl.col(column).abs() > 0).sum()).item() or 0)


def _global_absolute_component_total(frame: pl.DataFrame) -> float:
    return sum(_column_absolute_total(frame, _component_column(factor)) for factor in ALL_FACTORS)


def _percentage(numerator: float, denominator: float) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator * 100.0


def _entries_under_key(path: Path, key: str) -> list[CEntry]:
    entries: list[CEntry] = []
    for entry in parse_file(path).entries:
        if entry.key == key and isinstance(entry.value, CList):
            entries.extend(entry.value.entries)
    return entries


def _walk_entries(entries: Iterable[CEntry]) -> Iterable[CEntry]:
    for entry in entries:
        yield entry
        if isinstance(entry.value, CList):
            yield from _walk_entries(entry.value.entries)
            for item in entry.value.items:
                if isinstance(item, CList):
                    yield from _walk_entries(item.entries)


def _setup_start_files(profile: DataProfile, filename: str) -> list[Path]:
    return [
        path
        for layer in profile.layers
        if (path := _setup_start_dir(layer) / filename).is_file()
    ]


def _map_data_files(profile: DataProfile, filename: str) -> list[Path]:
    return [
        path
        for layer in profile.layers
        if (path := _map_data_dir(layer) / filename).is_file()
    ]


def _in_game_common_files(profile: DataProfile, folder: str, filename: str) -> list[Path]:
    return [
        path
        for layer in profile.layers
        if (path := _in_game_common_dir(layer) / folder / filename).is_file()
    ]


def _defined_entry_keys(profile: DataProfile, folder: str, filename: str) -> set[str]:
    keys: set[str] = set()
    for path in _in_game_common_files(profile, folder, filename):
        for entry in parse_file(path).entries:
            key = entry.key.removeprefix("TRY_INJECT:")
            keys.add(key)
    return keys


def _sheet_value_present_in_locations(locations: pl.DataFrame, factor: str, value: str) -> bool | None:
    if factor in CATEGORICAL_FACTORS and factor in locations.columns:
        present = {
            _normalize_factor_value(item)
            for item in locations.select(factor).unique().get_column(factor).to_list()
        }
        return value in present
    if factor in BOOLEAN_FACTORS and factor in locations.columns:
        return bool(locations.select(pl.col(factor).fill_null(False).any()).item())
    if factor == "development":
        return True
    return None


def _natural_sort_key(value: str) -> tuple[int, int | str]:
    try:
        return (0, int(value))
    except ValueError:
        return (1, value)


def _setup_start_dir(layer: GameLayer) -> Path:
    relative = Path("game") / "main_menu" / "setup" / "start"
    if layer.kind != "vanilla":
        relative = Path("main_menu") / "setup" / "start"
    return layer.root / relative


def _map_data_dir(layer: GameLayer) -> Path:
    relative = Path("game") / "in_game" / "map_data"
    if layer.kind != "vanilla":
        relative = Path("in_game") / "map_data"
    return layer.root / relative


def _in_game_common_dir(layer: GameLayer) -> Path:
    relative = Path("game") / "in_game" / "common"
    if layer.kind != "vanilla":
        relative = Path("in_game") / "common"
    return layer.root / relative


def _province_capitals(locations: pl.DataFrame) -> tuple[str, ...]:
    return tuple(
        str(row["location_tag"])
        for row in locations.sort("location_id")
        .group_by("province", maintain_order=True)
        .first()
        .select("location_tag")
        .to_dicts()
    )


def _river_level_frame(river_levels: Mapping[str, int] | pl.DataFrame) -> pl.DataFrame:
    if isinstance(river_levels, pl.DataFrame):
        _require_columns(river_levels, {"location_tag", "river_level"})
        return river_levels.select("location_tag", pl.col("river_level").cast(pl.Int64))
    rows = [{"location_tag": tag, "river_level": int(level)} for tag, level in river_levels.items()]
    return pl.DataFrame(rows, schema={"location_tag": pl.String, "river_level": pl.Int64})


def _resolve_path(base: Path, raw: object) -> Path:
    if raw is None:
        raise ValueError(f"missing path relative to {base}")
    path = Path(str(raw)).expanduser()
    if path.is_absolute():
        return path
    return base / path


def _require_columns(frame: pl.DataFrame, columns: set[str]) -> None:
    missing = sorted(columns - set(frame.columns))
    if missing:
        raise ValueError(f"DataFrame missing required columns: {missing}")


def _cell_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _cell_to_float(value: Any) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    text = _cell_text(value)
    if not text:
        return 0.0
    if "," in text and "." not in text:
        text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError as exc:
        raise ValueError(f"Expected numeric free_building_levels value, got {value!r}") from exc


def _optional_cell_to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, float) and np.isnan(value):
        return None
    text = _cell_text(value)
    if not text:
        return None
    return _cell_to_float(text)


def _normalize_key(value: Any) -> str:
    return _cell_text(value).lower().replace(" ", "_")


def _normalize_factor_value(value: Any) -> str:
    text = _cell_text(value)
    if not text:
        return ""
    try:
        numeric = float(text)
    except ValueError:
        return text
    if numeric.is_integer():
        return str(int(numeric))
    return text


def _hex_to_rgb_int(value: str) -> int:
    cleaned = value.strip().lower().lstrip("#")
    return int(cleaned, 16)
