"""The staple foods: the one list every food mechanic reads (2026-10-04, Jan).

Staple foods are the goods a population lived on. They come in three groups, set by the staple_group column of
config/goods_categories.csv (empty for every other good):

- crops   staple crops: wheat, rice, millet, maize, potato, legumes
- animals staple animals: livestock, fish, wild_game, wool (wool stands for sheep, which were eaten)
- fruits  staple fruits: fruit, olives

The category and subcategory columns describe how a good is produced (and carry the RGO expansion cost); the staple
group cuts across them. Readers: the store curve (stored_food.py: every staple food follows the province store),
the logistics bulk shares ([logistics] bulky_staples), the crop allocation (staple_crops), the Cookshop cap
counters and their tests. No other file keeps its own list.
"""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path

GOODS_CATEGORIES = Path(__file__).resolve().parents[2] / "config" / "goods_categories.csv"
COLUMN = "staple_group"
GROUPS = ("crops", "animals", "fruits")
GROUP_NAMES = {"crops": "Staple Crops", "animals": "Staple Animals", "fruits": "Staple Fruits"}


@lru_cache(maxsize=None)
def _groups(path: Path = GOODS_CATEGORIES) -> dict[str, str]:
    """Good -> staple group, in file order."""
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    groups: dict[str, str] = {}
    for row in rows:
        group = (row.get(COLUMN) or "").strip()
        if not group:
            continue
        if group not in GROUPS:
            raise ValueError(f"{path}: {row['good']} has an unknown {COLUMN} {group!r} (allowed: {', '.join(GROUPS)})")
        groups[row["good"]] = group
    return groups


def staple_group(good: str) -> str | None:
    """The staple group of good, None for a good that is not a staple food."""
    return _groups().get(good)


def staple_foods() -> tuple[str, ...]:
    """Every staple food, grouped (crops, animals, fruits), each group in file order."""
    groups = _groups()
    return tuple(good for group in GROUPS for good, g in groups.items() if g == group)


def goods_in_group(group: str) -> tuple[str, ...]:
    if group not in GROUPS:
        raise ValueError(f"unknown staple group {group!r} (allowed: {', '.join(GROUPS)})")
    return tuple(good for good, g in _groups().items() if g == group)


def is_staple_food(good: str) -> bool:
    return good in _groups()
