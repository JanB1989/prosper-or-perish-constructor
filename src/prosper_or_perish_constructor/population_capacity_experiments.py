"""Experimental population-capacity scoring models.

These formulas are analysis-only.  The production generator continues to use
``prosper_or_perish_population_capacity.staple_capacity``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import polars as pl


PRIMARY_STAPLES = ("rice", "wheat", "maize", "millet", "potato")

CALORIE_TIER_WEIGHTS = {
    "rice": 1.00,
    "wheat": 1.00,
    "maize": 1.00,
    "millet": 0.90,
    "potato": 0.90,
    "livestock": 0.70,
    "sugar": 0.65,
    "fish": 0.60,
    "legumes": 0.55,
    "olives": 0.45,
    "fruit": 0.35,
    "wild_game": 0.35,
    "horses": 0.30,
    "wine": 0.25,
    "cocoa": 0.15,
    "beeswax": 0.10,
}

MODEL_NAMES = (
    "current",
    "current_plus_rescue",
    "smooth_support",
    "regime_paths",
    "tiered_top3",
)


@dataclass(frozen=True)
class ModelScore:
    score: float
    driver: str


def normalized_good_percentiles(scores: pl.DataFrame) -> pl.DataFrame:
    """Normalize raw MMR to the production generator's per-good 0..1 scale."""

    required = {"location_tag", "good", "mmr"}
    missing = required.difference(scores.columns)
    if missing:
        raise ValueError(f"scores missing required columns: {', '.join(sorted(missing))}")

    base = (
        scores.select("location_tag", "good", "mmr")
        .filter(pl.col("location_tag").is_not_null() & pl.col("good").is_not_null())
        .group_by(["location_tag", "good"])
        .agg(pl.col("mmr").mean().alias("mmr"))
        .with_columns(pl.col("mmr").is_not_null().sum().over("good").alias("good_mmr_count"))
    )
    ranked = base.with_columns(pl.col("mmr").rank("average").over("good").alias("mmr_rank"))
    return ranked.with_columns(
        pl.when(pl.col("mmr").is_null())
        .then(None)
        .when(pl.col("good_mmr_count") <= 1)
        .then(1.0)
        .otherwise((pl.col("mmr_rank") - 1.0) / (pl.col("good_mmr_count") - 1.0))
        .alias("suitability")
    ).select("location_tag", "good", "suitability")


def model_comparison_frame(
    scores: pl.DataFrame,
    *,
    capacity_min: int = 10,
    capacity_max: int = 100,
) -> pl.DataFrame:
    """Calculate every experimental model for every scored location."""

    normalized = normalized_good_percentiles(scores)
    by_location: dict[str, dict[str, float]] = {}
    for row in normalized.to_dicts():
        suitability = row["suitability"]
        if suitability is None:
            continue
        tag = str(row["location_tag"])
        by_location.setdefault(tag, {})[str(row["good"])] = float(suitability)

    rows: list[dict[str, object]] = []
    for location_tag in sorted(by_location):
        goods = by_location[location_tag]
        row: dict[str, object] = {"location_tag": location_tag}
        for model in MODEL_NAMES:
            result = score_model(model, goods)
            row[f"{model}_score"] = result.score
            row[f"{model}_capacity"] = capacity_from_score(
                result.score,
                capacity_min=capacity_min,
                capacity_max=capacity_max,
            )
            row[f"{model}_driver"] = result.driver
        rows.append(row)
    return pl.DataFrame(rows)


def score_model(model: str, goods: Mapping[str, float]) -> ModelScore:
    if model == "current":
        return _current_model(goods)
    if model == "current_plus_rescue":
        return _current_plus_rescue_model(goods)
    if model == "smooth_support":
        return _smooth_support_model(goods)
    if model == "regime_paths":
        return _regime_paths_model(goods)
    if model == "tiered_top3":
        return _tiered_top3_model(goods)
    raise ValueError(f"unknown capacity model: {model}")


def capacity_from_score(score: float, *, capacity_min: int = 10, capacity_max: int = 100) -> int:
    if capacity_max < capacity_min:
        raise ValueError("capacity_max must be greater than or equal to capacity_min")
    bounded = _clamp01(score)
    capacity = round(capacity_min + ((capacity_max - capacity_min) * bounded))
    return max(capacity_min, min(capacity_max, capacity))


def rank_matched_capacities(
    locations: Sequence[str],
    scores: Sequence[float],
    reference_capacities: Sequence[int],
) -> list[int]:
    """Assign the reference distribution according to a candidate model's rank."""

    if not (len(locations) == len(scores) == len(reference_capacities)):
        raise ValueError("locations, scores, and reference_capacities must have equal lengths")
    order = sorted(range(len(locations)), key=lambda index: (float(scores[index]), str(locations[index])))
    reference = sorted(int(value) for value in reference_capacities)
    out = [0] * len(order)
    for rank, index in enumerate(order):
        out[index] = reference[rank]
    return out


def _current_model(goods: Mapping[str, float]) -> ModelScore:
    staple_pairs = sorted(
        ((good, _good(goods, good)) for good in PRIMARY_STAPLES),
        key=lambda item: (item[1], item[0]),
        reverse=True,
    )
    best_good, best_staple = staple_pairs[0]
    second_staple = staple_pairs[1][1]
    staple_diversity = (best_staple + second_staple) / 2.0
    secondary_food = _mean(goods, ("legumes", "fruit", "olives"))
    protein_support = _mean(goods, ("livestock", "fish", "wild_game"))

    if best_staple >= 0.80:
        food_score = (
            0.82 * best_staple
            + 0.10 * staple_diversity
            + 0.05 * secondary_food
            + 0.03 * protein_support
        )
    elif best_staple >= 0.55:
        food_score = (
            0.68 * best_staple
            + 0.17 * staple_diversity
            + 0.10 * secondary_food
            + 0.05 * protein_support
        )
    else:
        food_score = (
            0.55 * best_staple
            + 0.20 * staple_diversity
            + 0.15 * secondary_food
            + 0.10 * protein_support
        )
    if best_staple < 0.35:
        food_score = min(food_score, 0.35)
    return ModelScore(_clamp01(food_score), f"staple:{best_good}")


def _smooth_support_model(goods: Mapping[str, float]) -> ModelScore:
    staple_pairs = _ranked_goods(goods, PRIMARY_STAPLES)
    best_good, best_staple = staple_pairs[0]
    second_staple = staple_pairs[1][1]
    crop_score = (
        0.78 * best_staple
        + 0.12 * second_staple
        + 0.04 * _good(goods, "legumes")
        + 0.03 * _good(goods, "sugar")
        + 0.03 * max(_good(goods, "fruit"), _good(goods, "olives"))
    )
    support_routes = {
        "livestock": 0.55 * _good(goods, "livestock"),
        "sugar": 0.48 * _good(goods, "sugar"),
        "fish": 0.50 * _good(goods, "fish"),
        "wild_game": 0.28 * _good(goods, "wild_game"),
        "horses": 0.20 * _good(goods, "horses"),
        "wine": 0.12 * _good(goods, "wine"),
        "cocoa": 0.10 * _good(goods, "cocoa"),
        "beeswax": 0.08 * _good(goods, "beeswax"),
    }
    support_good, support_score = max(support_routes.items(), key=lambda item: (item[1], item[0]))
    score = crop_score + ((1.0 - crop_score) * support_score)
    driver = f"crop:{best_good}" if crop_score >= support_score else f"support:{support_good}"
    return ModelScore(_clamp01(score), driver)


def _current_plus_rescue_model(goods: Mapping[str, float]) -> ModelScore:
    current = _current_model(goods)
    rescue_paths = _non_crop_paths(goods)
    rescue_driver, rescue_score = max(
        rescue_paths.items(), key=lambda item: (item[1], item[0])
    )
    if current.score >= rescue_score:
        return current
    return ModelScore(_clamp01(rescue_score), rescue_driver)


def _regime_paths_model(goods: Mapping[str, float]) -> ModelScore:
    staple_pairs = _ranked_goods(goods, PRIMARY_STAPLES)
    best_good, best_staple = staple_pairs[0]
    second_staple = staple_pairs[1][1]
    paths = {
        f"crop:{best_good}": (
            0.78 * best_staple
            + 0.12 * second_staple
            + 0.04 * _good(goods, "legumes")
            + 0.03 * _good(goods, "sugar")
            + 0.03 * max(_good(goods, "fruit"), _good(goods, "olives"))
        ),
        **_non_crop_paths(goods),
    }
    ranked_paths = sorted(paths.items(), key=lambda item: (item[1], item[0]), reverse=True)
    driver, strongest = ranked_paths[0]
    second = ranked_paths[1][1]
    score = strongest + (0.10 * (1.0 - strongest) * second)
    return ModelScore(_clamp01(score), driver)


def _non_crop_paths(goods: Mapping[str, float]) -> dict[str, float]:
    return {
        "pastoral": (
            0.58 * _good(goods, "livestock")
            + 0.12 * _good(goods, "horses")
            + 0.10 * _good(goods, "wild_game")
        ),
        "fishing": 0.62 * _good(goods, "fish") + 0.08 * _good(goods, "wild_game"),
        "horticultural": (
            0.48 * _good(goods, "sugar")
            + 0.12 * _good(goods, "fruit")
            + 0.12 * _good(goods, "olives")
            + 0.05 * _good(goods, "legumes")
            + 0.03 * _good(goods, "cocoa")
        ),
        "foraging": 0.35 * _good(goods, "wild_game") + 0.10 * _good(goods, "beeswax"),
    }


def _tiered_top3_model(goods: Mapping[str, float]) -> ModelScore:
    weighted = sorted(
        (
            (good, weight * _good(goods, good))
            for good, weight in CALORIE_TIER_WEIGHTS.items()
        ),
        key=lambda item: (item[1], item[0]),
        reverse=True,
    )
    score = 0.82 * weighted[0][1] + 0.13 * weighted[1][1] + 0.05 * weighted[2][1]
    return ModelScore(_clamp01(score), f"good:{weighted[0][0]}")


def _ranked_goods(goods: Mapping[str, float], names: Sequence[str]) -> list[tuple[str, float]]:
    return sorted(
        ((good, _good(goods, good)) for good in names),
        key=lambda item: (item[1], item[0]),
        reverse=True,
    )


def _good(goods: Mapping[str, float], good: str) -> float:
    return _clamp01(float(goods.get(good, 0.0)))


def _mean(goods: Mapping[str, float], names: Sequence[str]) -> float:
    return sum(_good(goods, good) for good in names) / len(names)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
