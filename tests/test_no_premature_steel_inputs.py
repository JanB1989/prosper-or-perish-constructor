from __future__ import annotations

from pathlib import Path

from eu5gameparser.domain.availability import annotate_building_data_availability
from eu5gameparser.domain.eu5 import load_eu5_data


ROOT = Path(__file__).resolve().parents[1]
STEEL_AGE = "age_6_revolutions"
AGE_ORDER = {
    "age_1_traditions": 1,
    "age_2_renaissance": 2,
    "age_3_discovery": 3,
    "age_4_reformation": 4,
    "age_5_absolutism": 5,
    "age_6_revolutions": 6,
}


def test_constructor_methods_do_not_require_steel_before_steel_exists() -> None:
    data = load_eu5_data(profile="constructor", load_order_path=ROOT / "constructor.load_order.toml")
    annotated = annotate_building_data_availability(data.building_data, data.advancements)
    methods = annotated.production_methods.select(
        [
            "name",
            "building",
            "input_goods",
            "effective_unlock_age",
            "effective_availability_kind",
            "source_file",
            "source_line",
            "source_layer",
        ]
    ).to_dicts()

    premature: list[str] = []
    for method in methods:
        if method["source_layer"] != "constructor":
            continue
        if "steel" not in (method["input_goods"] or []):
            continue

        unlock_age = method["effective_unlock_age"]
        if unlock_age is None or AGE_ORDER[unlock_age] < AGE_ORDER[STEEL_AGE]:
            premature.append(
                f"{method['name']} ({method['building']}, "
                f"{method['effective_availability_kind']} {unlock_age}) "
                f"{method['source_file']}:{method['source_line']}"
            )

    assert not premature
