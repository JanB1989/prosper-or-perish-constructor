"""EU5 market membership: which market a location belongs to (engine rules measured in game 2026-09-27;
docs/market_rulebook.md).

Every location belongs to the market with the highest market attraction, recomputed at every monthly tick; there is
no hysteresis. ``attraction`` rebuilds the engine value for any (location, market) pair from its parts and ``assign``
takes the argmax. Access (1 - transport cost to the market centre) comes from outside: a save stores it for the
current and the best-access market only, ``market_access`` for every pair. ``tools/markets/save_inputs.py`` runs
both on a save and writes ``config/start_markets.csv``, which ``food_sim`` reads to put province pools into the
engine's markets instead of the nearest-centre proxy (``market_assignment = true``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping

# NMarket (loading_screen/common/defines/00_defines.txt), unchanged by the mod
COUNTRY_COMMON_LANGUAGE = 0.05          # market language = common language of the location's owner
COUNTRY_COMMON_LANGUAGE_FAMILY = 0.01
LOCATION_DOMINANT_LANGUAGE = 0.05       # market language = the location's dominant language
LOCATION_DOMINANT_LANGUAGE_FAMILY = 0.01
SAME_PROVINCE = 0.2                     # smallest shared unit only: province, else area (region and larger 0)
SAME_AREA = 0.1
LANGUAGE_POWER = 0.1                    # x language power (0..1) of the market language
PROTECTION_PER_CONTROL = 0.5            # static modifier `control`: local_trade_protection_factor 0.5 x control


@dataclass(frozen=True)
class Market:
    """A market as a location sees it. ``power`` = local_trade_center_power of the centre + global_trade_center_power
    of its owner (development, building levels, rank, market buildings, prestige, ...)."""

    key: str
    center: str
    owner: str | None
    power: float
    language: str | None
    language_power: float = 0.0          # 0..1 (language_manager)
    province: str | None = None
    area: str | None = None


@dataclass
class Place:
    """A location's side of the attraction. ``protection`` = local + global trade protection factor."""

    key: str
    owner: str | None
    province: str | None
    area: str | None
    language: str | None                 # dominant language of the location
    common_language: str | None          # language of the owner's primary culture
    protection: float = 0.0
    overlords: frozenset = field(default_factory=frozenset)   # countries the owner is a subject of
    market: str | None = None            # current market (ties keep it)


def languages(vanilla_root: Path) -> tuple[dict[str, str | None], dict[str, str]]:
    """(language -> language family, dialect -> language) from ``in_game/common/languages``. Cultures may carry a
    dialect as their language; the attraction compares languages, so map dialects to their parent first."""
    family: dict[str, str | None] = {}
    parent: dict[str, str] = {}
    folder = vanilla_root / "game" / "in_game" / "common" / "languages"
    for path in sorted(folder.glob("*.txt")):
        text = path.read_text(encoding="utf-8-sig")
        for block in re.finditer(r"^(\w+_language)\s*=\s*\{(.*?)^\}", text, re.S | re.M):
            found = re.search(r"^\tfamily\s*=\s*(\w+)", block.group(2), re.M)
            family[block.group(1)] = found.group(1) if found else None
            for dialect in re.finditer(r"^\t\t(\w+)\s*=\s*\{", block.group(2), re.M):
                parent[dialect.group(1)] = block.group(1)
    return family, parent


def _language(a: str | None, b: str | None, family: Mapping[str, str | None], same: float, near: float) -> float:
    if not a or not b:
        return 0.0
    if a == b:
        return same
    fa, fb = family.get(a), family.get(b)
    return near if fa and fa == fb else 0.0


def terms(place: Place, market: Market, access: float, family: Mapping[str, str | None]) -> dict[str, float]:
    """The engine's attraction breakdown (market tooltip) for one location and one market."""
    geo = (SAME_PROVINCE if place.province and place.province == market.province
           else SAME_AREA if place.area and place.area == market.area else 0.0)
    foreign = place.owner is not None and place.owner != market.owner and market.owner not in place.overlords
    return {
        "access": access,
        "power": market.power,
        "language_power": LANGUAGE_POWER * market.language_power,
        "geography": geo,
        "country_language": (_language(place.common_language, market.language, family, COUNTRY_COMMON_LANGUAGE,
                                       COUNTRY_COMMON_LANGUAGE_FAMILY) if place.owner else 0.0),
        "location_language": _language(place.language, market.language, family, LOCATION_DOMINANT_LANGUAGE,
                                       LOCATION_DOMINANT_LANGUAGE_FAMILY),
        "protection": -place.protection if foreign else 0.0,
    }


def attraction(place: Place, market: Market, access: float, family: Mapping[str, str | None]) -> float:
    return sum(terms(place, market, access, family).values())


def assign(places: Iterable[Place], markets: Mapping[str, Market],
           access: Mapping[str, Mapping[str, float]], family: Mapping[str, str | None]) -> dict[str, str]:
    """Market per location: the highest attraction over the markets it has access to (``access[location][market]``,
    access > 0). A location without access to any market keeps its current one."""
    out: dict[str, str] = {}
    for place in places:
        best, score = place.market, float("-inf")
        for key, acc in access.get(place.key, {}).items():
            market = markets.get(key)
            if market is None or acc <= 0:
                continue
            value = attraction(place, market, acc, family)
            if value > score or (value == score and key == place.market):
                best, score = key, value
        if best is not None:
            out[place.key] = best
    return out
