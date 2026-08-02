import polars as pl

from prosper_or_perish_constructor.population_capacity_experiments import (
    MODEL_NAMES,
    capacity_from_score,
    model_comparison_frame,
    rank_matched_capacities,
    score_model,
)
from prosper_or_perish_population_capacity.staple_capacity import (
    StapleCapacityConfig,
    staple_capacity_rows,
)


def test_current_experiment_matches_production_formula() -> None:
    scores = pl.DataFrame(
        {
            "location_tag": ["alpha", "beta", "gamma"] * 5,
            "good": [good for good in ("rice", "wheat", "maize", "millet", "potato") for _ in range(3)],
            "mmr": [3.0, 2.0, 1.0, 1.0, 3.0, 2.0, 2.0, 1.0, 3.0, 1.0, 2.0, 3.0, 2.5, 1.5, 0.5],
        }
    )
    production = {
        str(row["location_tag"]): int(row["local_population_capacity"])
        for row in staple_capacity_rows(
            scores,
            config=StapleCapacityConfig(capacity_min=10, capacity_max=100),
        )
    }
    experiment = {
        str(row["location_tag"]): int(row["current_capacity"])
        for row in model_comparison_frame(scores).to_dicts()
    }

    assert experiment == production


def test_candidate_models_rescue_specialized_non_crop_food_systems() -> None:
    livestock_only = {"livestock": 1.0}
    fish_only = {"fish": 1.0}
    sugar_only = {"sugar": 1.0}

    assert capacity_from_score(score_model("current", livestock_only).score) == 13
    assert capacity_from_score(score_model("current", fish_only).score) == 13
    assert capacity_from_score(score_model("current", sugar_only).score) == 10

    for model in set(MODEL_NAMES) - {"current"}:
        assert capacity_from_score(score_model(model, livestock_only).score) >= 60
        assert capacity_from_score(score_model(model, fish_only).score) >= 54
        assert capacity_from_score(score_model(model, sugar_only).score) >= 53


def test_rank_matching_preserves_reference_distribution() -> None:
    matched = rank_matched_capacities(
        ["a", "b", "c", "d"],
        [0.4, 0.1, 0.3, 0.2],
        [10, 20, 30, 40],
    )

    assert matched == [40, 10, 30, 20]
    assert sorted(matched) == [10, 20, 30, 40]
