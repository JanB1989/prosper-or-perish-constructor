"""Game-start free-building-level statistics from a Google Sheet source of truth."""

from __future__ import annotations

import csv
import io
import os
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl
import yaml
from eu5gameparser.clausewitz.parser import parse_file
from eu5gameparser.clausewitz.syntax import CEntry, CList
from eu5gameparser.load_order import DataProfile, GameLayer, LoadOrderConfig
from PIL import Image

from prosper_or_perish_constructor.farming_village_unlocks import load_current_location_frame


SPREADSHEET_ID = "1d_zH-wxb9ufW6RgVZgJdGqToJ-VZP_XPS7WhhUAa18U"
SHEET_NAME = "free_building_levels"
SHEET_GID = "602606501"
SHEET_RANGE = f"{SHEET_NAME}!A1:H"
GOOGLE_SHEETS_READONLY_SCOPE = "https://www.googleapis.com/auth/spreadsheets.readonly"

CATEGORICAL_FACTORS = ("topography", "vegetation", "river_level", "location_rank", "road_level")
BOOLEAN_FACTORS = (
    "province_capital",
    "is_port",
    "market_center",
    "capital",
    "naval_governor",
    "local_governor",
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


def parse_free_building_level_sheet(values: Sequence[Sequence[Any]]) -> pl.DataFrame:
    """Parse the visual Google Sheet layout into factor/value/weight rows."""
    active_pairs: dict[int, str] = {}
    section = ""
    rows: list[dict[str, object]] = []

    for row_index, raw_row in enumerate(values, start=1):
        row = [_cell_text(value) for value in raw_row]
        first = _cell_text(row[0] if row else "")
        if "FACTORS" in first.upper():
            section = first
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
                    "factor": factor,
                    "value": normalized_value,
                    "free_building_levels": weight,
                    "section": section,
                    "sheet_row": row_index,
                    "sheet_column": column + 1,
                }
            )

    schema = {
        "factor": pl.String,
        "value": pl.String,
        "free_building_levels": pl.Float64,
        "section": pl.String,
        "sheet_row": pl.Int64,
        "sheet_column": pl.Int64,
    }
    return pl.DataFrame(rows, schema=schema)


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
        "location_rank": _defined_entry_keys(profile, "location_ranks", "00_default.txt"),
        "road_level": {str(level) for level in load_road_type_levels(profile).values()} | {"0"},
        "river_level": {str(level) for level in range(0, 6)},
        "development": {"per_point"},
    }
    defined_values.update({factor: {"true"} for factor in BOOLEAN_FACTORS})
    source_details = {
        "topography": "in_game/common/topography/00_default.txt",
        "vegetation": "in_game/common/vegetation/00_default.txt",
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
    text = _cell_text(value)
    if not text:
        return 0.0
    if "," in text and "." not in text:
        text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError as exc:
        raise ValueError(f"Expected numeric free_building_levels value, got {value!r}") from exc


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
