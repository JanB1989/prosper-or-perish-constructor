from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


CALIBRATION_PATH = Path(__file__).with_name("map_mode_scale_calibration.json")

MAP_COLOR_MIN = "define:NMapColors|MAP_COLOR_MIN"
MAP_COLOR_LOW = "define:NMapColors|MAP_COLOR_LOW"
MAP_COLOR_MID = "define:NMapColors|MAP_COLOR_MID"
MAP_COLOR_HIGH = "define:NMapColors|MAP_COLOR_HIGH"
MAP_COLOR_MAX = "define:NMapColors|MAP_COLOR_MAX"
MAP_COLOR_TOP = "define:NMapColors|MAP_COLOR_TOP"
STARVATION_STRIPE = "define:NMapColors|POPULATION_STARVING_COLOR_STRIPE"
NO_DATA_GREY = "rgb { 128 128 128 }"


@dataclass(frozen=True)
class MapColorBucket:
    suffix: str
    condition: str | None
    lower_bound: float | None
    width: float | None
    min_color: str
    max_color: str
    legend_color: str


@dataclass(frozen=True)
class SequentialScale:
    thresholds: tuple[float, float, float, float]


@dataclass(frozen=True)
class ReferenceCenteredScale:
    reference: float
    low_thresholds: tuple[float, float]
    high_thresholds: tuple[float, float]


@dataclass(frozen=True)
class SignedCenteredScale:
    negative_thresholds: tuple[float, float]
    neutral_low: float
    neutral_high: float
    positive_thresholds: tuple[float, ...]


FALLBACK_SEQUENTIAL_SCALE = SequentialScale((0.25, 1.0, 4.0, 16.0))
FALLBACK_LOCAL_OUTPUT_SCALE = SignedCenteredScale(
    negative_thresholds=(-0.70, -0.25),
    neutral_low=-0.05,
    neutral_high=0.05,
    positive_thresholds=(0.15, 0.30, 0.75),
)
FALLBACK_FOOD_PRICE_SCALE = ReferenceCenteredScale(
    reference=0.12,
    low_thresholds=(0.02, 0.08),
    high_thresholds=(0.18, 0.30),
)


def load_scale_calibration(path: Path = CALIBRATION_PATH) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def savegame_goods_output_samples(savegame_root: Path) -> dict[str, list[float]]:
    """Return per-good, per-location output samples from exported savegame tables."""
    try:
        import polars as pl
    except ImportError:
        return {}

    sample_frames = []
    production = savegame_root / "production_method_good_flows.parquet"
    buildings = savegame_root / "buildings.parquet"
    if production.exists():
        flow = pl.read_parquet(production).filter(
            (pl.col("direction") == "output")
            & (pl.col("save_side") == "supplied_Production")
            & (pl.col("nominal_amount") > 0)
        )
        if buildings.exists() and flow.height:
            building_basis = (
                pl.read_parquet(buildings)
                .select(["building_id", "level", "employed", "employment"])
                .rename({"level": "building_level"})
                .with_columns(
                    pl.coalesce(["employed", "employment", "building_level"]).alias("basis"),
                )
                .select(["building_id", "building_level", "basis"])
            )
            flow = flow.join(building_basis, on="building_id", how="left").with_columns(
                pl.when(
                    (pl.col("basis") > 0)
                    & (pl.col("building_level") > 0)
                )
                .then(pl.col("nominal_amount") * pl.col("building_level") / pl.col("basis"))
                .otherwise(pl.col("nominal_amount"))
                .alias("output")
            )
        else:
            flow = flow.with_columns(pl.col("nominal_amount").alias("output"))
        sample_frames.append(
            flow.group_by(["good_id", "location_id"]).agg(pl.col("output").sum().alias("output"))
        )

    rgo = savegame_root / "rgo_flows.parquet"
    if rgo.exists():
        flow = pl.read_parquet(rgo)
        sample_frames.append(
            flow.filter(
                (pl.col("direction") == "output")
                & (pl.col("save_side") == "supplied_Production")
                & (pl.col("nominal_amount") > 0)
            )
            .group_by(["good_id", "location_id"])
            .agg(pl.col("nominal_amount").sum().alias("output"))
        )

    if not sample_frames:
        return {}

    samples = pl.concat(sample_frames, how="vertical_relaxed").group_by(["good_id", "location_id"]).agg(
        pl.col("output").sum().alias("output")
    )
    return {
        row["good_id"]: row["outputs"]
        for row in samples.group_by("good_id")
        .agg(pl.col("output").sort().alias("outputs"))
        .to_dicts()
    }


def sequential_good(thresholds: Sequence[float]) -> tuple[MapColorBucket, ...]:
    return _sequential_buckets(thresholds, (MAP_COLOR_MIN, MAP_COLOR_LOW, MAP_COLOR_MID, MAP_COLOR_HIGH, MAP_COLOR_MAX))


def sequential_bad(thresholds: Sequence[float]) -> tuple[MapColorBucket, ...]:
    return _sequential_buckets(thresholds, (MAP_COLOR_MAX, MAP_COLOR_HIGH, MAP_COLOR_MID, MAP_COLOR_LOW, MAP_COLOR_MIN))


def reference_centered(scale: ReferenceCenteredScale, low_is_good: bool) -> tuple[MapColorBucket, ...]:
    low_a, low_b = scale.low_thresholds
    high_a, high_b = scale.high_thresholds
    _ensure_increasing((low_a, low_b, scale.reference, high_a, high_b), "reference centered scale")
    low_extreme, low_mid, mid, high_mid, high_extreme = (
        (MAP_COLOR_MAX, MAP_COLOR_HIGH, MAP_COLOR_MID, MAP_COLOR_LOW, MAP_COLOR_MIN)
        if low_is_good
        else (MAP_COLOR_MIN, MAP_COLOR_LOW, MAP_COLOR_MID, MAP_COLOR_HIGH, MAP_COLOR_MAX)
    )
    return (
        MapColorBucket("VERY_LOW", f"< {_format_number(low_a)}", None, None, low_extreme, low_extreme, low_extreme),
        MapColorBucket("LOW", f"< {_format_number(low_b)}", low_a, low_b - low_a, low_extreme, low_mid, low_mid),
        MapColorBucket("BASE_LOW", f"< {_format_number(scale.reference)}", low_b, scale.reference - low_b, low_mid, mid, mid),
        MapColorBucket("BASE_HIGH", f"< {_format_number(high_a)}", scale.reference, high_a - scale.reference, mid, high_mid, high_mid),
        MapColorBucket("HIGH", f"< {_format_number(high_b)}", high_a, high_b - high_a, high_mid, high_extreme, high_extreme),
        MapColorBucket("VERY_HIGH", None, None, None, high_extreme, high_extreme, high_extreme),
    )


def signed_centered(scale: SignedCenteredScale) -> tuple[MapColorBucket, ...]:
    neg_a, neg_b = scale.negative_thresholds
    positives = scale.positive_thresholds
    if len(positives) not in {2, 3}:
        raise ValueError(f"signed centered scale supports 2 or 3 positive thresholds: {positives}")
    _ensure_increasing(
        (neg_a, neg_b, scale.neutral_low, scale.neutral_high, *positives),
        "signed centered scale",
    )
    negative_and_neutral = (
        MapColorBucket("EXTREME_DEFICIT", f"< {_format_number(neg_a)}", None, None, MAP_COLOR_MIN, MAP_COLOR_MIN, MAP_COLOR_MIN),
        MapColorBucket("DEFICIT", f"< {_format_number(neg_b)}", neg_a, neg_b - neg_a, MAP_COLOR_MIN, MAP_COLOR_LOW, MAP_COLOR_LOW),
        MapColorBucket("LOW", f"< {_format_number(scale.neutral_low)}", neg_b, scale.neutral_low - neg_b, MAP_COLOR_LOW, MAP_COLOR_MID, MAP_COLOR_LOW),
        MapColorBucket("NEUTRAL", f"< {_format_number(scale.neutral_high)}", None, None, MAP_COLOR_MID, MAP_COLOR_MID, MAP_COLOR_MID),
    )
    if len(positives) == 2:
        pos_a, pos_b = positives
        return negative_and_neutral + (
            MapColorBucket("GOOD", f"< {_format_number(pos_a)}", scale.neutral_high, pos_a - scale.neutral_high, MAP_COLOR_MID, MAP_COLOR_HIGH, MAP_COLOR_HIGH),
            MapColorBucket("STRONG", f"< {_format_number(pos_b)}", pos_a, pos_b - pos_a, MAP_COLOR_HIGH, MAP_COLOR_MAX, MAP_COLOR_HIGH),
            MapColorBucket("EXCEPTIONAL", None, None, None, MAP_COLOR_MAX, MAP_COLOR_MAX, MAP_COLOR_MAX),
        )

    pos_a, pos_b, pos_c = positives
    return negative_and_neutral + (
        MapColorBucket("GOOD", f"< {_format_number(pos_a)}", scale.neutral_high, pos_a - scale.neutral_high, MAP_COLOR_MID, MAP_COLOR_HIGH, MAP_COLOR_HIGH),
        MapColorBucket("STRONG", f"< {_format_number(pos_b)}", pos_a, pos_b - pos_a, MAP_COLOR_HIGH, MAP_COLOR_MAX, MAP_COLOR_HIGH),
        MapColorBucket("EXCELLENT", f"< {_format_number(pos_c)}", pos_b, pos_c - pos_b, MAP_COLOR_MAX, MAP_COLOR_TOP, MAP_COLOR_MAX),
        MapColorBucket("EXCEPTIONAL", None, None, None, MAP_COLOR_TOP, MAP_COLOR_TOP, MAP_COLOR_TOP),
    )


def bucketed_color_cases(
    value_name: str,
    buckets: Iterable[MapColorBucket],
    *,
    first_branch: str = "if",
    indent_level: int = 2,
    extra_limit_lines: Sequence[str] = (),
) -> str:
    lines: list[str] = []
    indent = "\t" * indent_level
    limit_indent = "\t" * (indent_level + 1)
    inner_indent = "\t" * (indent_level + 2)

    for index, bucket in enumerate(buckets):
        branch = first_branch if index == 0 else "else_if"
        if bucket.condition is None and not extra_limit_lines:
            branch = "else"
            lines.append(f"{indent}{branch} = {{")
        else:
            lines.append(f"{indent}{branch} = {{")
            lines.append(f"{limit_indent}limit = {{")
            for extra in extra_limit_lines:
                lines.append(f"{inner_indent}{extra}")
            if bucket.condition is not None:
                lines.append(f"{inner_indent}{value_name} {bucket.condition}")
            lines.append(f"{limit_indent}}}")

        if bucket.width is None:
            lines.append(f"{limit_indent}value = {bucket.min_color}")
        else:
            lines.extend(_lerp_lines(value_name, bucket.lower_bound, bucket.width, bucket.min_color, bucket.max_color, indent_level + 1))
        lines.append(f"{indent}}}")

    return "\n".join(lines)


def legend_keys(desc_prefix: str, buckets: Iterable[MapColorBucket], suffixes: Iterable[str] | None = None) -> str:
    wanted = set(suffixes) if suffixes is not None else None
    return "\n".join(
        f'\tlegend_key = {{ desc = "{desc_prefix}_{bucket.suffix}" color = {bucket.legend_color} }}'
        for bucket in buckets
        if wanted is None or bucket.suffix in wanted
    )


def sequential_scale_from_data(raw: dict | None, fallback: SequentialScale = FALLBACK_SEQUENTIAL_SCALE) -> SequentialScale:
    if not raw:
        return fallback
    return SequentialScale(_number_tuple(raw.get("thresholds"), 4, fallback.thresholds))


def reference_scale_from_data(raw: dict | None, fallback: ReferenceCenteredScale = FALLBACK_FOOD_PRICE_SCALE) -> ReferenceCenteredScale:
    if not raw:
        return fallback
    return ReferenceCenteredScale(
        reference=float(raw.get("reference", fallback.reference)),
        low_thresholds=_number_tuple(raw.get("low_thresholds"), 2, fallback.low_thresholds),
        high_thresholds=_number_tuple(raw.get("high_thresholds"), 2, fallback.high_thresholds),
    )


def signed_scale_from_data(raw: dict | None, fallback: SignedCenteredScale = FALLBACK_LOCAL_OUTPUT_SCALE) -> SignedCenteredScale:
    if not raw:
        return fallback
    positive_thresholds = _number_tuple_one_of(raw.get("positive_thresholds"), {2, 3}, fallback.positive_thresholds)
    return SignedCenteredScale(
        negative_thresholds=_number_tuple(raw.get("negative_thresholds"), 2, fallback.negative_thresholds),
        neutral_low=float(raw.get("neutral_low", fallback.neutral_low)),
        neutral_high=float(raw.get("neutral_high", fallback.neutral_high)),
        positive_thresholds=positive_thresholds,
    )


def _sequential_buckets(thresholds: Sequence[float], colors: Sequence[str]) -> tuple[MapColorBucket, ...]:
    t1, t2, t3, t4 = _number_tuple(thresholds, 4, FALLBACK_SEQUENTIAL_SCALE.thresholds)
    _ensure_increasing((0, t1, t2, t3, t4), "sequential scale")
    suffixes = ("VERY_LOW", "LOW", "MEDIUM", "HIGH", "CAPPED")
    return (
        MapColorBucket(suffixes[0], f"< {_format_number(t1)}", 0, t1, colors[0], colors[1], colors[0]),
        MapColorBucket(suffixes[1], f"< {_format_number(t2)}", t1, t2 - t1, colors[1], colors[2], colors[1]),
        MapColorBucket(suffixes[2], f"< {_format_number(t3)}", t2, t3 - t2, colors[2], colors[3], colors[2]),
        MapColorBucket(suffixes[3], f"< {_format_number(t4)}", t3, t4 - t3, colors[3], colors[4], colors[3]),
        MapColorBucket(suffixes[4], None, None, None, colors[4], colors[4], colors[4]),
    )


def _lerp_lines(
    value_name: str,
    lower_bound: float | None,
    width: float,
    min_color: str,
    max_color: str,
    indent_level: int,
) -> list[str]:
    if lower_bound is None:
        raise ValueError("Gradient map color buckets require a lower bound")
    indent = "\t" * indent_level
    factor_indent = "\t" * (indent_level + 1)
    operation_indent = "\t" * (indent_level + 2)
    lines = [
        f"{indent}lerp = {{",
        f"{factor_indent}min_color = {min_color}",
        f"{factor_indent}max_color = {max_color}",
        f"{factor_indent}factor = {{",
        f"{operation_indent}value = {value_name}",
    ]
    if lower_bound < 0:
        lines.append(f"{operation_indent}add = {_format_number(abs(lower_bound))}")
    elif lower_bound > 0:
        lines.append(f"{operation_indent}subtract = {_format_number(lower_bound)}")
    lines.extend(
        [
            f"{operation_indent}divide = {_format_number(width)}",
            f"{operation_indent}max = 1",
            f"{operation_indent}min = 0",
            f"{factor_indent}}}",
            f"{indent}}}",
        ]
    )
    return lines


def _number_tuple(values: object, length: int, fallback: Sequence[float]) -> tuple[float, ...]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        values = fallback
    numbers = tuple(float(value) for value in values)
    if len(numbers) != length:
        numbers = tuple(float(value) for value in fallback)
    return numbers


def _number_tuple_one_of(values: object, lengths: set[int], fallback: Sequence[float]) -> tuple[float, ...]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        values = fallback
    numbers = tuple(float(value) for value in values)
    if len(numbers) not in lengths:
        numbers = tuple(float(value) for value in fallback)
    return numbers


def _ensure_increasing(values: Sequence[float], label: str) -> None:
    for left, right in zip(values, values[1:]):
        if not left < right:
            raise ValueError(f"{label} is not strictly increasing: {values}")


def _format_number(value: float) -> str:
    text = f"{value:.5f}"
    text = text.rstrip("0").rstrip(".")
    return text if text and text != "-0" else "0"
