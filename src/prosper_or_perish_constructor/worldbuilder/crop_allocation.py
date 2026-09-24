"""Game-start crop allocation: split a location's farm levels across the crop farms.

The single farming village is split into one farm per crop. At game start a location that would have received
``N`` farming-village levels receives ``N`` levels spread over the crop farms by how productive each crop is there
and what the location farmed:

- crop weight = ``max(0, 1 + sum of the good's World Builder output rows over the location's attribute classes)``
  (the same rows the mod writes as ``local_<good>_output_modifier``; the fit intercept is folded into the climate
  rows by :func:`modifiers.class_rows`),
- livestock has no rows and is not weighed against the crops: it takes a separate share of the levels, the
  location's grazing share ``g`` (World Builder ``grazing_area_ha / (grazing_area_ha + source_starting_crop_ha)``,
  a default where unknown), raised on pastoral RGOs and open vegetation and clipped. The weights mapping carries
  ``g`` itself under ``"livestock"``; the crops share the levels livestock leaves,
- the New World and regional crops (``gated_goods``) are only candidates inside their native sub-continents and
  regions (the gates of :func:`farming_village_unlocks.derive_rgo_unlock_gates`); a caller filter can further
  exclude goods whose building fails its ``location_potential`` in a location.

Pure and deterministic: no randomness, fixed good order for every tie.
"""

from __future__ import annotations

import csv
import math
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import polars as pl

from prosper_or_perish_constructor.farming_village_unlocks import RgoUnlockGate, derive_rgo_unlock_gates
from prosper_or_perish_constructor.worldbuilder.contract import Contract
from prosper_or_perish_constructor.worldbuilder.modifiers import class_rows

LIVESTOCK = "livestock"
DEFAULT_BUILDINGS: dict[str, str] = {
    "wheat": "wheat_farm",
    "rice": "rice_farm",
    "millet": "millet_farm",
    "maize": "maize_farm",
    "legumes": "legume_farm",
    "potato": "potato_farm",
    "olives": "olive_grove",
    LIVESTOCK: "cattle_farm",
}
REPORT_COLUMNS = ("location_tag", "good", "building", "available", "weight", "levels")
_EPS = 1e-9


@dataclass(frozen=True)
class CropConfig:
    """``[worldbuilder.start.crops]`` of constructor.toml."""

    floor_share: float = 0.6                 # candidates under this share of the heaviest weight are dropped
    rgo_bonus: float = 0.5                   # added to the RGO good's weight when it is a candidate
    grain_min_levels_from: int = 3           # from this many levels on at least one staple crop is placed
    livestock_share_default: float = 0.2     # grazing share where the World Builder table has no value
    livestock_share_min: float = 0.1
    livestock_share_max: float = 0.7
    livestock_bonus: float = 0.2             # grazing share added on pastoral RGOs and open vegetation
    livestock_rgos: tuple[str, ...] = ("livestock", "wool", "horses")
    livestock_vegetation: tuple[str, ...] = ("grasslands", "sparse")
    livestock_source: Path | None = None     # EU5WorldBuilder artifacts/locations/locations.csv
    gated_goods: tuple[str, ...] = ("rice", "maize", "potato", "olives")
    grains: tuple[str, ...] = ("wheat", "millet", "rice", "maize", "legumes", "potato")
    buildings: Mapping[str, str] = field(default_factory=lambda: dict(DEFAULT_BUILDINGS))

    @property
    def goods(self) -> tuple[str, ...]:
        """All allocated goods in their fixed order (the order of ``buildings``), used to break every tie."""
        return tuple(self.buildings)

    @property
    def row_goods(self) -> tuple[str, ...]:
        """Goods whose weight comes from the World Builder output rows (all but livestock)."""
        return tuple(g for g in self.goods if g != LIVESTOCK)


def load_crop_config(project_toml: Mapping[str, Any], repo: Path | None = None) -> CropConfig:
    """Read ``[worldbuilder.start.crops]`` from a parsed constructor.toml, with defaults for missing keys.
    ``livestock_source`` resolves against ``repo`` when it is relative and a repo is given."""
    wb = project_toml.get("worldbuilder") if isinstance(project_toml.get("worldbuilder"), Mapping) else {}
    start = wb.get("start") if isinstance(wb.get("start"), Mapping) else {}
    raw = start.get("crops") if isinstance(start.get("crops"), Mapping) else {}
    kwargs: dict[str, Any] = {}
    for name in ("floor_share", "rgo_bonus", "livestock_share_default", "livestock_share_min", "livestock_share_max", "livestock_bonus"):
        if name in raw:
            kwargs[name] = float(raw[name])
    if "grain_min_levels_from" in raw:
        kwargs["grain_min_levels_from"] = int(raw["grain_min_levels_from"])
    for name in ("livestock_rgos", "livestock_vegetation", "gated_goods", "grains"):
        if name in raw:
            kwargs[name] = tuple(str(x) for x in raw[name])
    if isinstance(raw.get("buildings"), Mapping):
        kwargs["buildings"] = {str(k): str(v) for k, v in raw["buildings"].items()}
    source = raw.get("livestock_source")
    if source:
        path = Path(str(source)).expanduser()
        kwargs["livestock_source"] = path if path.is_absolute() or repo is None else (Path(repo) / path).resolve()
    cfg = CropConfig(**kwargs)
    if not 0.0 <= cfg.livestock_share_min <= cfg.livestock_share_max < 1.0:
        raise ValueError("[worldbuilder.start.crops]: need 0 <= livestock_share_min <= livestock_share_max < 1")
    unknown = [g for g in (*cfg.gated_goods, *cfg.grains) if g not in cfg.buildings]
    if unknown:
        raise ValueError(f"[worldbuilder.start.crops]: goods without a building: {', '.join(sorted(set(unknown)))}")
    return cfg


def load_grazing_shares(path: Path) -> dict[str, float]:
    """location tag -> ``grazing_area_ha / (grazing_area_ha + source_starting_crop_ha)`` from the World Builder
    locations table; locations with no grazing and no crop area are left out (they take the default)."""
    columns = ("location_tag", "grazing_area_ha", "source_starting_crop_ha")
    frame = pl.read_csv(path, columns=list(columns), infer_schema_length=100000).select(columns)   # read_csv keeps file order
    out: dict[str, float] = {}
    for tag, grazing, crop in frame.iter_rows():
        grazing = float(grazing or 0.0)
        crop = float(crop or 0.0)
        if tag and grazing + crop > 0:
            out[str(tag)] = grazing / (grazing + crop)
    return out


def livestock_share(grazing: float | None, rgo: str | None, vegetation: str | None, cfg: CropConfig) -> float:
    """Grazing share of a location: the World Builder value (default where unknown), plus ``livestock_bonus`` on a
    pastoral RGO or open vegetation, clipped to ``[livestock_share_min, livestock_share_max]``."""
    g = cfg.livestock_share_default if grazing is None or math.isnan(grazing) else float(grazing)
    if (rgo or "") in cfg.livestock_rgos or _vegetation_class(vegetation) in cfg.livestock_vegetation:
        g += cfg.livestock_bonus
    return min(cfg.livestock_share_max, max(cfg.livestock_share_min, g))


def crop_weights(
    contract: Contract,
    locations_frame: pl.DataFrame,
    cfg: CropConfig,
    *,
    grazing_shares: Mapping[str, float] | None = None,
) -> dict[str, dict[str, float]]:
    """location tag -> good -> value for every good of ``cfg.goods``, over the contract's locations: the crop
    weight for each crop, and for ``"livestock"`` the location's clipped grazing share (see :func:`livestock_share`),
    which :func:`allocate` turns into a share of the levels.

    ``grazing_shares`` defaults to :func:`load_grazing_shares` of ``cfg.livestock_source`` (when the file exists).
    """
    if grazing_shares is None:
        source = cfg.livestock_source
        grazing_shares = load_grazing_shares(source) if source is not None and Path(source).is_file() else {}
    rows = class_rows(contract)
    attrs = contract.location_attributes
    columns = sorted(a for a in {attr for attr, _ in rows} if a in attrs.columns)
    keys = {g: f"local_{g}_output_modifier" for g in cfg.row_goods if g in contract.goods}
    frame = _frame_index(locations_frame)

    out: dict[str, dict[str, float]] = {}
    for row in attrs.select("location_tag", *columns).iter_rows(named=True):
        tag = str(row["location_tag"])
        classes = [rows.get((a, str(row[a])), {}) for a in columns]
        weights: dict[str, float] = {}
        for good in cfg.row_goods:
            key = keys.get(good)
            total = sum(c.get(key, 0.0) for c in classes) if key else -1.0   # a good without rows is never a candidate
            weights[good] = round(max(0.0, 1.0 + total), 6)
        info = frame.get(tag, {})
        vegetation = row.get("vegetation") or info.get("vegetation")   # World Builder class first, game key otherwise
        weights[LIVESTOCK] = round(livestock_share(grazing_shares.get(tag), info.get("raw_material"), vegetation, cfg), 6)
        out[tag] = {g: weights.get(g, 0.0) for g in cfg.goods}
    return out


def availability(gates: Sequence[RgoUnlockGate] | Mapping[str, RgoUnlockGate], macro_region: str | None, region: str | None, cfg: CropConfig) -> frozenset[str]:
    """Goods a location may farm at game start: every ungated good, and a gated good only inside its native
    sub-continents (``macro_region``) or regions. A gated good without a gate is nowhere available."""
    by_good = dict(gates) if isinstance(gates, Mapping) else {g.good: g for g in gates}
    out = set()
    for good in cfg.goods:
        if good not in cfg.gated_goods:
            out.add(good)
            continue
        gate = by_good.get(good)
        if gate is not None and ((macro_region and macro_region in gate.subcontinents) or (region and region in gate.regions)):
            out.add(good)
    return frozenset(out)


def crop_gates(locations_frame: pl.DataFrame, cfg: CropConfig, threshold: float) -> tuple[RgoUnlockGate, ...]:
    """Native gates of the gated crops, derived exactly as the farming-village RGO unlocks
    (``threshold`` = ``[farming_village_rgo_unlocks].subcontinent_region_threshold``)."""
    return derive_rgo_unlock_gates(locations_frame, list(cfg.gated_goods), threshold)


def available_by_location(locations_frame: pl.DataFrame, gates: Sequence[RgoUnlockGate] | Mapping[str, RgoUnlockGate], cfg: CropConfig) -> dict[str, frozenset[str]]:
    """location tag -> :func:`availability` for every location of the frame."""
    return {tag: availability(gates, info.get("macro_region"), info.get("region"), cfg) for tag, info in _frame_index(locations_frame).items()}


def allocate(
    levels: int,
    weights: Mapping[str, float],
    available: frozenset[str],
    rgo: str | None,
    cfg: CropConfig,
    *,
    candidate_filter: Callable[[str], bool] | None = None,
) -> dict[str, int]:
    """Split ``levels`` farm levels across goods (good -> levels, only goods with levels).

    ``weights`` holds the crop weights and, under ``"livestock"``, the location's grazing share ``g`` (as returned by
    :func:`crop_weights`). ``candidate_filter`` (good -> allowed) removes goods the caller knows cannot be built in
    the location (its building's ``location_potential`` fails); filtered goods count as unavailable.

    0. livestock (when available) takes ``round(g x levels)`` levels, ``g`` raised by ``rgo_bonus`` on a livestock
       RGO and capped at ``livestock_share_max``; it is never dropped by the floor. Without any crop candidate it
       takes every level;
    1. crop candidates = available crops with weight > 0; the RGO crop gets ``rgo_bonus`` on top;
    2. crop candidates under ``floor_share`` x the heaviest crop weight are dropped (never the RGO crop);
    3. the crops share the remaining levels: each gets ``floor(rest x w / sum w)``; what is left goes one each to the
       RGO crop (or, without it, the heaviest crop) first, then by largest fractional remainder, ties by the fixed
       good order;
    4. from ``grain_min_levels_from`` levels on, when no staple crop got a level, one level moves from the largest
       allocation (livestock included) to the heaviest available staple crop.
    Totals ``levels`` exactly whenever a candidate exists; ``{}`` otherwise.
    """
    if levels <= 0:
        return {}
    order = {g: i for i, g in enumerate(cfg.goods)}
    rank = lambda g: order.get(g, len(order))  # noqa: E731
    allowed = frozenset(g for g in available if candidate_filter is None or candidate_filter(g))
    crops = {g: float(w) for g, w in sorted(weights.items(), key=lambda kv: rank(kv[0]))
             if g != LIVESTOCK and g in allowed and w > 0}
    has_livestock = LIVESTOCK in allowed
    if not crops:
        return {LIVESTOCK: levels} if has_livestock else {}

    out: dict[str, int] = {}
    if has_livestock:
        share = max(0.0, float(weights.get(LIVESTOCK, 0.0)))
        if rgo == LIVESTOCK:
            share = min(cfg.livestock_share_max, share + cfg.rgo_bonus)
        out[LIVESTOCK] = min(levels, int(math.floor(share * levels + 0.5)))   # half up, not banker's rounding
    rest = levels - out.get(LIVESTOCK, 0)

    has_rgo = rgo is not None and rgo in crops
    if has_rgo:
        crops[rgo] += cfg.rgo_bonus
    heaviest = max(crops.values())
    crops = {g: w for g, w in crops.items() if w >= cfg.floor_share * heaviest - _EPS or (has_rgo and g == rgo)}
    total = sum(crops.values())
    exact = {g: rest * w / total for g, w in crops.items()}
    for g, x in exact.items():
        out[g] = int(math.floor(x + _EPS))
    first = rgo if has_rgo else min(crops, key=lambda g: (-crops[g], rank(g)))
    queue = [first] + sorted((g for g in crops if g != first), key=lambda g: (-(exact[g] - out[g]), rank(g)))
    remainder = levels - sum(out.values())
    for i in range(remainder):
        out[queue[i % len(queue)]] += 1

    if levels >= cfg.grain_min_levels_from and not any(out.get(g, 0) > 0 for g in cfg.grains):
        staples = [g for g in cfg.grains if g in allowed and weights.get(g, 0.0) > 0]
        if staples:
            grain = min(staples, key=lambda g: (-float(weights[g]), rank(g)))
            donor = min((g for g in out if out[g] > 0), key=lambda g: (-out[g], rank(g)))
            out[donor] -= 1
            out[grain] = out.get(grain, 0) + 1
    return {g: n for g, n in sorted(out.items(), key=lambda kv: rank(kv[0])) if n > 0}


def plan_all(
    contract: Contract,
    locations_frame: pl.DataFrame,
    gates: Sequence[RgoUnlockGate] | Mapping[str, RgoUnlockGate],
    cfg: CropConfig,
    levels_by_tag: Mapping[str, int],
    *,
    grazing_shares: Mapping[str, float] | None = None,
    weights: Mapping[str, Mapping[str, float]] | None = None,
    candidate_filter: Callable[[str, str], bool] | None = None,
) -> dict[str, dict[str, int]]:
    """location tag -> crop building -> levels for every tag with levels and at least one candidate.

    ``weights`` may be passed in (from :func:`crop_weights`) to avoid recomputing them. ``candidate_filter`` takes
    ``(location_tag, good)`` and returns whether that good's building may stand there (its ``location_potential``);
    it is bound per location and handed to :func:`allocate`."""
    available = available_by_location(locations_frame, gates, cfg)
    if weights is None:
        weights = crop_weights(contract, locations_frame, cfg, grazing_shares=grazing_shares)
    frame = _frame_index(locations_frame)
    plan: dict[str, dict[str, int]] = {}
    for tag in sorted(levels_by_tag):
        levels = int(levels_by_tag[tag])
        if levels <= 0 or tag not in weights:
            continue
        info = frame.get(tag, {})
        avail = available.get(tag) or availability(gates, None, None, cfg)
        allowed = None if candidate_filter is None else (lambda good, _tag=tag: candidate_filter(_tag, good))
        split = allocate(levels, weights[tag], avail, info.get("raw_material"), cfg, candidate_filter=allowed)
        if split:
            plan[tag] = {cfg.buildings[g]: n for g, n in split.items()}
    return plan


def write_report(
    plan: Mapping[str, Mapping[str, int]],
    weights: Mapping[str, Mapping[str, float]],
    path: Path,
    *,
    cfg: CropConfig | None = None,
    available: Mapping[str, frozenset[str]] | None = None,
    tags: Iterable[str] | None = None,
) -> int:
    """CSV ``location_tag, good, building, available, weight, levels``: one row per location (``tags``, default the
    planned ones) and good. ``weight`` is the crop weight, for livestock the grazing share. ``available`` is empty
    when no availability map is given. Returns the row count."""
    cfg = cfg or CropConfig()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(REPORT_COLUMNS)
        for tag in sorted(set(tags) if tags is not None else set(plan)):
            by_building = plan.get(tag, {})
            for good in cfg.goods:
                building = cfg.buildings[good]
                avail = "" if available is None else str(good in available.get(tag, frozenset())).lower()
                writer.writerow([tag, good, building, avail, f"{float(weights.get(tag, {}).get(good, 0.0)):.4f}", int(by_building.get(building, 0))])
                count += 1
    return count


def _vegetation_class(value: str | None) -> str:
    """World Builder vegetation class of a game vegetation key (``ha1300_veg_sparse`` -> ``sparse``)."""
    return str(value or "").removeprefix("ha1300_veg_")


def _frame_index(frame: pl.DataFrame) -> dict[str, dict[str, str | None]]:
    """location tag -> raw_material / vegetation / region / macro_region (stripped strings, None when missing)."""
    wanted = [c for c in ("raw_material", "vegetation", "region", "macro_region") if c in frame.columns]
    out: dict[str, dict[str, str | None]] = {}
    for row in frame.select("location_tag", *wanted).iter_rows(named=True):
        info = {}
        for c in wanted:
            v = row[c]
            v = str(v).strip() if v is not None else ""
            info[c] = v or None
        out[str(row["location_tag"])] = info
    return out
