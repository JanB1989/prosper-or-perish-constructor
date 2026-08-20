"""Prosperity state loading and scaling (devastation ignored for now)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from eu5gameparser.clausewitz.parser import parse_file
from eu5gameparser.clausewitz.syntax import CList
from eu5gameparser.domain._modifier_blocks import load_modifier_block_data
from eu5gameparser.domain.static_modifiers import load_static_modifier_data
from eu5gameparser.load_order import load_profile

PROSPERITY_MODIFIER_NAME = "prosperity"
DEVELOPMENT_MODIFIER_NAME = "development"
LOCATION_BASE_VALUES_NAME = "location_base_values"
COUNTRY_BASE_VALUES_NAME = "country_base_values"
GLOBAL_PROSPERITY_DECAY_KEY = "global_prosperity_decay"
LOCAL_PROSPERITY_DECAY_KEY = "local_prosperity_decay"
LOCAL_MONTHLY_PROSPERITY_KEY = "local_monthly_prosperity"
LOCAL_MONTHLY_DEVELOPMENT_KEY = "local_monthly_development"
LOCAL_MONTHLY_DEVELOPMENT_MODIFIER_KEY = "local_monthly_development_modifier"
LOCAL_POPULATION_GROWTH_KEY = "local_population_growth"

PROSPERITY_COLUMN = "prosperity"
DEVELOPMENT_COLUMN = "development"
PROSPERITY_MAX = 100.0
DEVELOPMENT_MAX = 100.0

# Comment on the PoP inject: effects are at 100 prosperity, scaled linearly below that.
PROSPERITY_FULL_SCALE = 100.0


@dataclass(frozen=True)
class ProsperityBaselines:
    """Parsed prosperity drivers used by the monthly tick."""

    # Flat / scaled additive income sources for the prosperity state.
    base_monthly_prosperity: float
    food_growth_monthly_prosperity: float
    # Fractional decay of current prosperity value per month.
    global_prosperity_decay: float
    # Scaled with prosperity (0..1): extra fractional decay at full prosperity.
    local_prosperity_decay: float
    # Scaled prosperity static-modifier effects (at full 100 prosperity).
    effects: Mapping[str, float]
    # The development static modifier is applied once per development point.
    development_monthly_per_point: float = 0.0

    def scale(self, prosperity: float) -> float:
        """Map stored prosperity (0..100) onto the engine's 0..1 multiplier."""
        if prosperity <= 0.0:
            return 0.0
        return min(float(prosperity) / PROSPERITY_FULL_SCALE, 1.0)

    def get_effect(self, key: str, default: float = 0.0) -> float:
        return float(self.effects.get(key, default) or 0.0)

    def food_consumption_effect(self, pop_type: str) -> float:
        return self.get_effect(f"local_{pop_type}_food_consumption", 0.0)


def _scalar_entries(value: Any) -> dict[str, float]:
    """Flatten a Clausewitz modifier block into summed float effects."""
    out: dict[str, float] = {}
    if not isinstance(value, CList):
        return out
    for entry in value.entries:
        key = str(entry.key)
        if key in {"game_data"}:
            continue
        child = entry.value
        if isinstance(child, CList):
            continue
        try:
            number = float(child)
        except (TypeError, ValueError):
            continue
        out[key] = out.get(key, 0.0) + number
    return out


def _merge_effect_dicts(*parts: Mapping[str, float]) -> dict[str, float]:
    merged: dict[str, float] = {}
    for part in parts:
        for key, value in part.items():
            merged[key] = merged.get(key, 0.0) + float(value)
    return merged


def _load_prosperity_inject_effects(repo: Path) -> dict[str, float]:
    """Read in_game TRY_INJECT:prosperity (cross-scope; not auto-merged by parser)."""
    path = (
        repo
        / "mod"
        / "Prosper or Perish (Population Growth & Food Rework)"
        / "in_game"
        / "common"
        / "static_modifiers"
        / "pp_population_growth_and_food_adjustments.txt"
    )
    if not path.is_file():
        return {}
    document = parse_file(path)
    for entry in document.entries:
        key = str(entry.key)
        # Parser keeps the TRY_INJECT: prefix on the entry key.
        if key == "TRY_INJECT:prosperity" or key.endswith("INJECT:prosperity"):
            return _scalar_entries(entry.value)
    return {}


def load_prosperity_baselines(
    *,
    profile: str,
    load_order_path: str | Path,
    food_growth_monthly_prosperity: float,
    repo: Path | None = None,
) -> ProsperityBaselines:
    """Load prosperity income, decay, and scaled static effects for the simulation."""
    load_order = Path(load_order_path)
    static = load_static_modifier_data(profile=profile, load_order_path=load_order)
    vanilla_prosperity = {
        str(key): float(value)
        for key, value in dict(static._by_name[PROSPERITY_MODIFIER_NAME].modifiers).items()
        if not isinstance(value, bool)
    }
    development_monthly_per_point = float(
        static._by_name[DEVELOPMENT_MODIFIER_NAME].modifiers.get(
            LOCAL_MONTHLY_DEVELOPMENT_KEY,
            0.0,
        )
        or 0.0
    )
    try:
        base_monthly = float(
            static.modifier_baseline(LOCATION_BASE_VALUES_NAME, None, LOCAL_MONTHLY_PROSPERITY_KEY)
        )
    except Exception:
        base_monthly = 0.0

    profile_obj = load_profile(profile, load_order)
    auto = load_modifier_block_data(profile_obj, relative_dir="auto_modifiers", scope="in_game")
    global_decay = float(
        auto._by_name[COUNTRY_BASE_VALUES_NAME].modifiers.get(GLOBAL_PROSPERITY_DECAY_KEY, 0.0) or 0.0
    )

    repo_path = repo or load_order.resolve().parent
    inject = _load_prosperity_inject_effects(repo_path)
    effects = _merge_effect_dicts(vanilla_prosperity, inject)

    return ProsperityBaselines(
        base_monthly_prosperity=base_monthly,
        food_growth_monthly_prosperity=float(food_growth_monthly_prosperity),
        global_prosperity_decay=global_decay,
        local_prosperity_decay=float(effects.get(LOCAL_PROSPERITY_DECAY_KEY, 0.0) or 0.0),
        effects=effects,
        development_monthly_per_point=development_monthly_per_point,
    )
