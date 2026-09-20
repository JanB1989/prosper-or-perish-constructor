"""Constructor-owned location baseline.

The vanilla per-location table (``data/vanilla/locations_with_raw_material.parquet``: tag, province,
region, area, vanilla climate/topography/vegetation, RGO, coast, river, harbour) plus the current
``location_templates.txt`` overlay from the configured load order. This replaces the labeling
pipeline's baseline; nothing here depends on the retired pipelines.
"""

from __future__ import annotations

import re
import tomllib
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import polars as pl

DEFAULT_BASELINE_RELATIVE_PATH = Path("data/vanilla/locations_with_raw_material.parquet")
LOCATION_TEMPLATES_RELATIVE_PATH = Path("in_game/map_data/location_templates.txt")
MODELED_LOCATION_TEMPLATE_FIELDS: tuple[str, ...] = (
    "raw_material",
    "topography",
    "vegetation",
    "climate",
    "religion",
    "culture",
    "natural_harbor_suitability",
    "modifier",
)
_LOCATION_TEMPLATE_RE = re.compile(r"^\s*(?P<key>[A-Za-z0-9_:.+-]+)\s*=\s*\{(?P<body>[^{}]*)\}\s*$")
_TOKEN_RE = re.compile(r"\b(?P<key>[A-Za-z0-9_:.+-]+)\s*=\s*(?P<value>[A-Za-z0-9_:.+-]+)")
_WINDOWS_DRIVE_RE = re.compile(r"^(?P<drive>[A-Za-z]):[\\/](?P<rest>.*)$")


@dataclass(frozen=True)
class LocationTemplateSource:
    paths: tuple[Path, ...]
    profile: str


def parse_template_value(value: str) -> Any:
    value = value.strip()
    if value.startswith("goods:"):
        value = value.removeprefix("goods:")
    try:
        if any(ch in value for ch in (".", "e", "E")):
            return float(value)
        if value.startswith("-") and value[1:].isdigit():
            return int(value)
        if value.isdigit():
            return int(value)
    except ValueError:
        pass
    return value


def parse_location_templates_text(text: str) -> dict[str, dict[str, Any]]:
    """Parse flat EU5 location-template rows into ``location -> field -> value``."""
    templates: dict[str, dict[str, Any]] = {}
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        match = _LOCATION_TEMPLATE_RE.match(line)
        if match is None:
            continue
        templates[match.group("key")] = {
            token.group("key"): parse_template_value(token.group("value"))
            for token in _TOKEN_RE.finditer(match.group("body"))
        }
    return templates


def load_location_template_files(paths: Iterable[Path | str]) -> dict[str, dict[str, Any]]:
    """Load template files in order; later files replace earlier location rows."""
    merged: dict[str, dict[str, Any]] = {}
    for raw_path in paths:
        path = Path(raw_path)
        merged.update(parse_location_templates_text(path.read_text(encoding="utf-8-sig")))
    return merged


def resolve_load_order_path(raw: str, base: Path) -> Path:
    raw = raw.strip()
    match = _WINDOWS_DRIVE_RE.match(raw)
    if match is not None:
        rest = match.group("rest").replace("\\", "/")
        return Path("/mnt") / match.group("drive").lower() / rest
    path = Path(raw.replace("\\", "/")).expanduser()
    return path.resolve() if path.is_absolute() else (base / path).resolve()


def location_template_paths_from_load_order(
    load_order_path: Path | str, *, profile: str = "constructor", layers: Sequence[str] | None = None
) -> LocationTemplateSource:
    """Resolve profile-ordered ``location_templates.txt`` paths from the constructor load-order TOML.

    ``layers`` restricts the layers to consider (for example ``("vanilla",)`` for the vanilla-only view).
    """
    path = Path(load_order_path).expanduser().resolve()
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    base = path.parent
    profiles = raw.get("profiles")
    if not isinstance(profiles, dict) or profile not in profiles:
        raise ValueError(f"{path}: profile {profile!r} not found")
    layer_names = [str(layer) for layer in profiles[profile]]
    if layers is not None:
        layer_names = [layer for layer in layer_names if layer in set(layers)]
    paths_section = raw.get("paths") if isinstance(raw.get("paths"), dict) else {}
    vanilla_root_raw = paths_section.get("vanilla_root")
    if not vanilla_root_raw:
        raise ValueError(f"{path}: missing [paths].vanilla_root")
    vanilla_root = resolve_load_order_path(str(vanilla_root_raw), base)
    mods: dict[str, Path] = {}
    for item in raw.get("mods", []) or []:
        if isinstance(item, dict) and item.get("id") and item.get("root"):
            mods[str(item["id"])] = resolve_load_order_path(str(item["root"]), base)
    paths: list[Path] = []
    for layer_id in layer_names:
        if layer_id == "vanilla":
            candidate = vanilla_root / "game" / LOCATION_TEMPLATES_RELATIVE_PATH
        else:
            if layer_id not in mods:
                raise ValueError(f"{path}: profile {profile!r} references unknown mod {layer_id!r}")
            candidate = mods[layer_id] / LOCATION_TEMPLATES_RELATIVE_PATH
        if candidate.is_file():
            paths.append(candidate)
    if not paths:
        raise FileNotFoundError(f"{path}: no location_templates.txt files found for profile {profile!r}")
    return LocationTemplateSource(paths=tuple(paths), profile=profile)


def apply_location_template_overlay(
    baseline: pl.DataFrame,
    templates: Mapping[str, Mapping[str, Any]],
    *,
    fields: Sequence[str] = MODELED_LOCATION_TEMPLATE_FIELDS,
) -> pl.DataFrame:
    """Return ``baseline`` with current location-template field values overlaid by tag."""
    if "location_tag" not in baseline.columns or not templates:
        return baseline
    overlay_fields = [field for field in fields if field in baseline.columns]
    if not overlay_fields:
        return baseline
    rows = [{"location_tag": str(tag), **{f"{f}__t": values.get(f) for f in overlay_fields}} for tag, values in templates.items()]
    overlay = pl.DataFrame(rows)
    for field in overlay_fields:
        dtype = baseline.schema[field]
        overlay = overlay.with_columns(pl.col(f"{field}__t").cast(dtype if dtype.is_numeric() else pl.String, strict=False))
    joined = baseline.join(overlay, on="location_tag", how="left")
    return joined.with_columns(
        [pl.coalesce([pl.col(f"{f}__t"), pl.col(f)]).alias(f) for f in overlay_fields]
    ).drop([f"{f}__t" for f in overlay_fields])


def baseline_path(repo: Path, project: Path | None = None) -> Path:
    """The frozen vanilla baseline table; ``[worldbuilder].vanilla_baseline`` in constructor.toml overrides it."""
    if project is not None and project.is_file():
        raw = tomllib.loads(project.read_text(encoding="utf-8"))
        section = raw.get("worldbuilder") if isinstance(raw.get("worldbuilder"), dict) else {}
        configured = section.get("vanilla_baseline")
        if configured:
            path = Path(str(configured))
            return path if path.is_absolute() else repo / path
    return repo / DEFAULT_BASELINE_RELATIVE_PATH


def load_baseline(repo: Path, project: Path | None = None) -> pl.DataFrame:
    path = baseline_path(repo, project)
    if not path.is_file():
        raise FileNotFoundError(f"vanilla location baseline missing: {path}")
    return pl.read_parquet(path)


def _load_order_path(repo: Path, project: Path | None) -> Path:
    if project is not None and project.is_file():
        raw = tomllib.loads(project.read_text(encoding="utf-8"))
        parser = raw.get("parser") if isinstance(raw.get("parser"), dict) else {}
        candidate = parser.get("load_order")
        if candidate:
            path = Path(str(candidate))
            return path if path.is_absolute() else repo / path
    return repo / "constructor.load_order.toml"


def load_current_location_frame(repo: Path, project: Path | None = None, *, profile: str = "constructor") -> pl.DataFrame:
    """Baseline with the current (vanilla + mod) location-template overlay."""
    source = location_template_paths_from_load_order(_load_order_path(repo, project), profile=profile)
    return apply_location_template_overlay(load_baseline(repo, project), load_location_template_files(source.paths))


def load_vanilla_location_frame(repo: Path, project: Path | None = None, *, profile: str = "constructor") -> pl.DataFrame:
    """Baseline with the vanilla location-template overlay only (vanilla class names, vanilla RGOs)."""
    source = location_template_paths_from_load_order(_load_order_path(repo, project), profile=profile, layers=("vanilla",))
    return apply_location_template_overlay(load_baseline(repo, project), load_location_template_files(source.paths))


def build_location_geometry_frame(
    *, baseline_path: str | Path, locations_png_path: str | Path, equator_y: int, chunk_rows: int = 256, **_ignored
) -> pl.DataFrame:
    """Approximate lon/lat per location from the centroid of its colour in locations.png.

    Columns: location_tag, named_location_hex, map_color_rgb, geometry_status ('ok' | 'missing_color'),
    pixel_count, centroid_x, centroid_y, approx_lon, approx_lat.
    """
    import numpy as np
    from PIL import Image

    baseline = pl.read_parquet(baseline_path)
    if "named_location_hex" not in baseline.columns:
        raise ValueError(f"{baseline_path}: missing named_location_hex column")
    rows = baseline.filter(pl.col("named_location_hex").is_not_null()).select("location_tag", "named_location_hex")
    colors = {str(h).lower(): int(str(h), 16) for h in rows["named_location_hex"].unique().to_list()}
    counts: dict[int, int] = {}
    sum_x: dict[int, float] = {}
    sum_y: dict[int, float] = {}
    Image.MAX_IMAGE_PIXELS = None
    with Image.open(locations_png_path) as image:
        image = image.convert("RGB")
        width, height = image.size
        for y0 in range(0, height, chunk_rows):
            chunk = np.asarray(image.crop((0, y0, width, min(height, y0 + chunk_rows))), dtype=np.int64)
            packed = (chunk[:, :, 0] << 16) | (chunk[:, :, 1] << 8) | chunk[:, :, 2]
            values, inverse = np.unique(packed, return_inverse=True)
            inverse = inverse.reshape(packed.shape)
            ys, xs = np.indices(packed.shape)
            for index, value in enumerate(values.tolist()):
                mask = inverse == index
                n = int(mask.sum())
                counts[value] = counts.get(value, 0) + n
                sum_x[value] = sum_x.get(value, 0.0) + float(xs[mask].sum())
                sum_y[value] = sum_y.get(value, 0.0) + float(ys[mask].sum()) + float(y0) * n
    out = []
    for tag, hex_value in rows.iter_rows():
        color = colors[str(hex_value).lower()]
        n = counts.get(color, 0)
        if not n:
            out.append({"location_tag": str(tag), "named_location_hex": str(hex_value), "map_color_rgb": f"{color:06x}", "geometry_status": "missing_color",
                        "pixel_count": 0, "centroid_x": None, "centroid_y": None, "approx_lon": None, "approx_lat": None})
            continue
        cx, cy = sum_x[color] / n, sum_y[color] / n
        out.append({"location_tag": str(tag), "named_location_hex": str(hex_value), "map_color_rgb": f"{color:06x}", "geometry_status": "ok", "pixel_count": n,
                    "centroid_x": cx, "centroid_y": cy, "approx_lon": (cx / width * 360.0) - 180.0, "approx_lat": (float(equator_y) - cy) / (width / 360.0)})
    return pl.DataFrame(out)
