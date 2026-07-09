from pathlib import Path

from eu5gameparser.clausewitz.syntax import CList
from eu5gameparser.load_order import load_merged_directory, load_profile


ROOT = Path(__file__).resolve().parents[1]


def test_all_diseases_reduce_local_migration_attraction() -> None:
    profile = load_profile("constructor", ROOT / "constructor.load_order.toml")
    diseases = {
        entry.key: entry.value
        for entry in load_merged_directory(profile, "diseases").entries
        if isinstance(entry.value, CList)
    }

    assert diseases

    offenders: list[str] = []
    for disease, body in sorted(diseases.items()):
        location_modifiers = [
            value for value in body.values("location_modifier") if isinstance(value, CList)
        ]
        values = [
            value
            for modifier in location_modifiers
            for value in modifier.values("local_migration_attraction")
        ]
        if not values or min(values) > -1.5:
            offenders.append(f"{disease}: {values!r}")

    assert not offenders


def test_bubonic_plague_keeps_stronger_vanilla_migration_penalty() -> None:
    profile = load_profile("constructor", ROOT / "constructor.load_order.toml")
    diseases = {
        entry.key: entry.value
        for entry in load_merged_directory(profile, "diseases").entries
        if isinstance(entry.value, CList)
    }
    bubonic_plague = diseases["bubonic_plague"]
    location_modifier = bubonic_plague.values("location_modifier")[0]

    assert isinstance(location_modifier, CList)
    assert location_modifier.values("local_migration_attraction") == [-5.0]
