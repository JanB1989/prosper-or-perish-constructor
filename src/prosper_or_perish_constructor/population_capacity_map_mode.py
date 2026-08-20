"""Compile the population-capacity map-mode scale from the accepted start table."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path


POPULATION_CAPACITY_MAP_MODE_RELATIVE_THRESHOLDS = (
    0.10,
    0.20,
    0.30,
    0.40,
    0.50,
    0.625,
    0.775,
    1.00,
)
POPULATION_CAPACITY_MAP_MODE_CONSTANTS = (
    "very_low",
    "low",
    "middle",
    "high",
    "strong",
    "very_strong",
    "exceptional",
    "cap",
)
POPULATION_CAPACITY_MAP_MODE_LEGEND_KEYS = (
    "MAPMODE_PP_POPULATION_CAPACITY_RANGE_0_20",
    "MAPMODE_PP_POPULATION_CAPACITY_RANGE_20_40",
    "MAPMODE_PP_POPULATION_CAPACITY_RANGE_40_60",
    "MAPMODE_PP_POPULATION_CAPACITY_RANGE_60_80",
    "MAPMODE_PP_POPULATION_CAPACITY_RANGE_80_100",
    "MAPMODE_PP_POPULATION_CAPACITY_RANGE_100_125",
    "MAPMODE_PP_POPULATION_CAPACITY_RANGE_125_155",
    "MAPMODE_PP_POPULATION_CAPACITY_RANGE_155_200",
)


def load_start_capacity_values(path: Path) -> list[int]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    if not rows or "location_tag" not in rows[0] or "population_capacity" not in rows[0]:
        raise ValueError(
            "population-capacity map-mode input must contain location_tag and population_capacity"
        )
    values: list[int] = []
    seen: set[str] = set()
    for row in rows:
        tag = str(row["location_tag"]).strip()
        if not tag or tag in seen:
            raise ValueError(f"population-capacity map-mode input has duplicate/empty location: {tag!r}")
        seen.add(tag)
        try:
            value = int(row["population_capacity"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid population capacity for {tag!r}") from exc
        if value < 0:
            raise ValueError(f"population capacity cannot be negative for {tag!r}")
        values.append(value)
    return values


def population_capacity_map_mode_thresholds(
    values: list[int] | tuple[int, ...], *, max_multiplier: float = 2.0
) -> tuple[int, ...]:
    """Return eight readable buckets ending at roughly 2x the start maximum."""

    if not values:
        raise ValueError("population-capacity map-mode scale needs at least one value")
    if max_multiplier <= 0:
        raise ValueError("population-capacity map-mode max multiplier must be positive")
    start_max = max(values)
    display_cap = max(8, int(round(start_max * max_multiplier)))
    thresholds: list[int] = []
    previous = 0
    for relative in POPULATION_CAPACITY_MAP_MODE_RELATIVE_THRESHOLDS:
        threshold = int(round(display_cap * relative))
        threshold = max(previous + 1, threshold)
        thresholds.append(threshold)
        previous = threshold
    thresholds[-1] = display_cap
    return tuple(thresholds)


def compile_population_capacity_map_mode(
    *,
    capacity_table: Path,
    map_mode_path: Path,
    localization_path: Path,
    calibration_path: Path | None = None,
    max_multiplier: float = 2.0,
) -> dict[str, object]:
    values = load_start_capacity_values(capacity_table)
    return compile_population_capacity_map_mode_values(
        values=values,
        map_mode_path=map_mode_path,
        localization_path=localization_path,
        calibration_path=calibration_path,
        max_multiplier=max_multiplier,
    )


def compile_population_capacity_map_mode_values(
    *,
    values: list[int] | tuple[int, ...],
    map_mode_path: Path,
    localization_path: Path,
    calibration_path: Path | None = None,
    max_multiplier: float = 2.0,
) -> dict[str, object]:
    """Compile the map scale from full game-visible starting capacities."""

    thresholds = population_capacity_map_mode_thresholds(values, max_multiplier=max_multiplier)
    map_mode_text = _replace_map_mode_thresholds(
        _read_text_preserving_newlines(map_mode_path), thresholds
    )
    _write_if_changed(map_mode_path, map_mode_text, encoding="utf-8-sig")
    localization_text = _replace_population_capacity_legend_text(
        _read_text_preserving_newlines(localization_path), thresholds
    )
    _write_if_changed(localization_path, localization_text, encoding="utf-8-sig")
    if calibration_path is not None:
        _update_calibration(calibration_path, thresholds)
    return {
        "locations": len(values),
        "start_max_capacity": max(values),
        "display_cap": thresholds[-1],
        "thresholds": list(thresholds),
        "max_multiplier": max_multiplier,
    }


def _replace_map_mode_thresholds(text: str, thresholds: tuple[int, ...]) -> str:
    for name, value in zip(POPULATION_CAPACITY_MAP_MODE_CONSTANTS, thresholds, strict=True):
        pattern = re.compile(rf"(^@pp_population_capacity_{name}\s*=\s*)[-+]?\d+(?:\.\d+)?$", re.MULTILINE)
        text, replacements = pattern.subn(rf"\g<1>{value}", text, count=1)
        if replacements != 1:
            raise ValueError(f"population-capacity map mode is missing @{name}")

    start = text.index("pp_population_capacity = {")
    end = text.index("# Map mode for local population growth", start)
    prefix, block, suffix = text[:start], text[start:end], text[end:]
    divide_pattern = re.compile(
        r"(factor\s*=\s*\{\s*value\s*=\s*location_max_population\b.*?\n\s*divide\s*=\s*)([^\r\n]+)",
        re.DOTALL,
    )
    matches = list(divide_pattern.finditer(block))
    if len(matches) != len(thresholds):
        raise ValueError(
            f"population-capacity map mode has {len(matches)} bucket factors; expected {len(thresholds)}"
        )
    divisors = [thresholds[0], *(right - left for left, right in zip(thresholds, thresholds[1:]))]
    chunks: list[str] = []
    cursor = 0
    for index, match in enumerate(matches):
        chunks.append(block[cursor : match.start(2)])
        divisor = "@pp_population_capacity_very_low" if index == 0 else str(divisors[index])
        chunks.append(divisor)
        cursor = match.end(2)
    chunks.append(block[cursor:])
    return prefix + "".join(chunks) + suffix


def _replace_population_capacity_legend_text(
    text: str, thresholds: tuple[int, ...]
) -> str:
    ranges = [(0, thresholds[0]), *list(zip(thresholds, thresholds[1:]))]
    for key, (lower, upper) in zip(POPULATION_CAPACITY_MAP_MODE_LEGEND_KEYS, ranges, strict=True):
        pattern = re.compile(rf"(^\s*{re.escape(key)}:\s*).*$", re.MULTILINE)
        text, replacements = pattern.subn(
            rf'\g<1>"{lower}-{upper} capacity"', text, count=1
        )
        if replacements != 1:
            raise ValueError(f"population-capacity localization is missing {key}")
    capped_pattern = re.compile(
        r"(^\s*MAPMODE_PP_POPULATION_CAPACITY_CAPPED:\s*).*$", re.MULTILINE
    )
    text, replacements = capped_pattern.subn(
        rf'\g<1>"{thresholds[-1]}+ capacity"', text, count=1
    )
    if replacements != 1:
        raise ValueError("population-capacity localization is missing capped legend text")
    return text


def _update_calibration(path: Path, thresholds: tuple[int, ...]) -> None:
    raw = json.loads(path.read_text(encoding="utf-8"))
    scale = raw.setdefault("scales", {}).setdefault("population_capacity", {})
    scale["thresholds"] = [float(value) for value in thresholds]
    scale["source"] = "accepted_start_capacity_max_times_two"
    path.write_text(json.dumps(raw, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_text_preserving_newlines(path: Path) -> str:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return handle.read()


def _write_if_changed(path: Path, text: str, *, encoding: str) -> None:
    data = text.encode(encoding)
    if path.is_file() and path.read_bytes() == data:
        return
    path.write_bytes(data)
