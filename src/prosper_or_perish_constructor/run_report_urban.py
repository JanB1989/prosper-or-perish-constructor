"""Town rights and industry promotions in the run report: what the AI grants, where, and whether it fits.

Saves carry the engine tables `town_rights` (one row per right a location holds: town_right_id, location_id, type)
and `industry_promotions` (one row per promotion: country_id, area, type). The game files give each town right its
goods (`local_<good>_output_modifier` or a `local_<good>_guild_building_levels` in its location_modifier), whether it
is a specialization and what it upgrades to, and each industry type its goods list (`load_urban_catalog`).

Fit is measured on production per location (buildings and RGOs, the save's nominal output, at base price):

- a specialization right fits best when no generic specialization right (a charter that upgrades, or the right a
  charter upgrades to: the lines open to every town, not the country-specific rights) covers more of the town's
  production than the one it holds;
- a promotion's area is ranked among the promoting country's areas by the output of the industry's goods there.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any

import polars as pl

from prosper_or_perish_constructor.run_report_charts import (
    CATEGORICAL,
    DUMMY_GOODS,
    OTHER_GREY,
    PRICE_HEAT,
    SEQUENTIAL_HEAT,
    WORLD,
    _r,
    _series,
    chart,
    heat_option,
    land_region_expr,
    line_option,
    region_palette,
    titleize,
    view,
)

if TYPE_CHECKING:
    from prosper_or_perish_constructor.run_report import RunData

SECTION = "towns"
TOWN_RANKS = ("town", "city", "megalopolis")
# display order and colour of the town right categories
RIGHT_CATEGORIES: tuple[tuple[str, str, str], ...] = (
    ("specialization", "Specialization", "#2a78d6"),
    ("raw", "Raw materials", "#c98a00"),
    ("trade", "Markets & trade", "#1baf7a"),
    ("military", "Military", "#e34948"),
    ("other", "Privileges & other", "#4a3aa7"),
)
CATEGORY_LABELS = {key: label for key, label, _ in RIGHT_CATEGORIES}
MILITARY_MODIFIERS = frozenset({"local_garrison_size", "local_manpower_modifier", "local_levy_size_modifier"})
RAW_MODIFIERS = frozenset({"local_max_rgo_size_modifier", "local_raw_material_output"})
TRADE_MODIFIERS = frozenset({"local_marketplace_building_levels", "local_market_access", "local_trades_per_burgher",
                             "local_merchant_capacity_modifier", "harbor_suitability"})
GOOD_MODIFIER = re.compile(r"^local_(\w+?)_(?:output_modifier|guild_building_levels)$")
# a name function in a localized string, e.g. [ShowLocationNameWithNoTooltip('magdeburg')]
LOC_NAME_CALL = re.compile(r"\[Show\w*?Name\w*\('(\w+)'\)\]")
SEVERAL = "#9a9a96"  # a location whose owner promotes more than one industry in its area


@dataclass(frozen=True)
class RightInfo:
    category: str
    goods: tuple[str, ...]  # goods whose output (or guild) the right raises in its town
    upgrades_to: str | None = None
    specialization: bool = False
    generic: bool = False  # a specialization open to every town: a charter that upgrades, or what a charter upgrades to


@dataclass
class UrbanCatalog:
    rights: dict[str, RightInfo] = field(default_factory=dict)
    industries: dict[str, tuple[str, ...]] = field(default_factory=dict)  # industry type -> goods, in file order


def right_category(specialization: bool, modifiers: set[str]) -> str:
    if specialization:
        return "specialization"
    if modifiers & MILITARY_MODIFIERS:
        return "military"
    if modifiers & RAW_MODIFIERS:
        return "raw"
    if modifiers & TRADE_MODIFIERS:
        return "trade"
    return "other"


def load_urban_catalog(repo: Path, project: Path) -> UrbanCatalog:
    """Town right and industry type definitions of the constructor's parser profile (vanilla + mods, merged)."""
    from eu5gameparser.clausewitz.syntax import CList
    from eu5gameparser.load_order import load_merged_directory, load_profile

    from prosper_or_perish_constructor.free_building_levels import resolve_parser_config

    config = resolve_parser_config(repo, project)
    profile = load_profile(str(config.get("profile") or "constructor"),
                           repo / str(config.get("load_order") or "constructor.load_order.toml"))
    catalog = UrbanCatalog()
    for entry in load_merged_directory(profile, "town_rights", scope="in_game").entries:
        block = entry.value
        if not isinstance(block, CList):
            continue
        modifier_block = block.first("location_modifier")
        modifiers = [e.key for e in modifier_block.entries] if isinstance(modifier_block, CList) else []
        goods: list[str] = []
        for key in modifiers:
            match = GOOD_MODIFIER.match(key)
            if match and match.group(1) not in DUMMY_GOODS and match.group(1) not in goods:
                goods.append(match.group(1))
        specialization = block.first("is_specialization") in (True, "yes")
        upgrades = block.first("upgrades_to")
        catalog.rights[entry.key] = RightInfo(
            category=right_category(specialization, set(modifiers)), goods=tuple(goods),
            upgrades_to=upgrades if isinstance(upgrades, str) else None, specialization=specialization)
    # the charter -> rights lines are open to every town; country-specific rights stand alone
    chains = {k for k, v in catalog.rights.items() if v.upgrades_to} | {
        v.upgrades_to for v in catalog.rights.values() if v.upgrades_to}
    catalog.rights = {k: replace(v, generic=v.specialization and bool(v.goods) and k in chains)
                      for k, v in catalog.rights.items()}
    for entry in load_merged_directory(profile, "industry_types", scope="in_game").entries:
        block = entry.value
        goods_block = block.first("goods") if isinstance(block, CList) else None
        if isinstance(goods_block, CList):
            catalog.industries[entry.key] = tuple(str(g) for g in goods_block.items)
    return catalog


# --------------------------------------------------------------------------------------------------------
# Helpers


def right_label(run: RunData, key: str) -> str:
    text = run.labels._text(key) or titleize(key)
    return LOC_NAME_CALL.sub(lambda m: run.labels._text(m.group(1)) or titleize(m.group(1)), text)


def industry_label(run: RunData, key: str) -> str:
    return run.labels._text(f"industry_type_{key}") or run.labels._text(key) or titleize(key)


def area_label(run: RunData, key: str) -> str:
    return run.labels._text(key) or titleize(key)


def industry_colours(run: RunData) -> dict[str, str]:
    """Fixed colour per industry type: the catalog's order, then any type only the saves know."""
    keys = list(run.urban.industries)
    if not run.promotions.is_empty():
        keys += sorted(t for t in run.promotions["type"].unique().to_list() if t not in keys)
    return {key: CATEGORICAL[i % len(CATEGORICAL)] for i, key in enumerate(keys)}


def _counts(frame: pl.DataFrame, key: str, x: pl.DataFrame, have: list[str]) -> dict[Any, list[float | None]]:
    """{key: rows per save aligned with x}: 0 in saves that have the table but no row, None in saves without it."""
    position = {s: i for i, s in enumerate(x["snapshot_id"].to_list())}
    known = set(have)
    base = [0.0 if s in known else None for s in x["snapshot_id"].to_list()]
    out: dict[Any, list[float | None]] = {}
    for k, snapshot, n in frame.group_by(key, "snapshot_id").agg(pl.len().alias("_n")).select(key, "snapshot_id", "_n").iter_rows():
        if snapshot in position:
            out.setdefault(k, list(base))[position[snapshot]] = float(n)
    return out


def _total(counts: dict[Any, list[float | None]], x: pl.DataFrame, have: list[str]) -> list[float | None]:
    known = set(have)
    totals = [0.0 if s in known else None for s in x["snapshot_id"].to_list()]
    for values in counts.values():
        totals = [None if t is None else t + (v or 0.0) for t, v in zip(totals, values)]
    return totals


def _location_info(run: RunData) -> pl.DataFrame:
    """snapshot_id, location_id, slug, owner_id, area, region (land regions only), town (rank town or larger)."""
    locs = run.locations
    columns = locs.columns
    return locs.select(
        "snapshot_id", "location_id", "slug",
        (pl.col("owner_country_id") if "owner_country_id" in columns else pl.lit(None, dtype=pl.Int64)).alias("owner_id"),
        (pl.col("area") if "area" in columns else pl.lit(None, dtype=pl.String)).alias("area"),
        pl.when(land_region_expr()).then(pl.col("macro_region")).alias("region"),
        (pl.col("rank").is_in(TOWN_RANKS) if "rank" in columns else pl.lit(None, dtype=pl.Boolean)).alias("town"),
    )


def _held(run: RunData) -> pl.DataFrame:
    """Every town right held, per save, with its category and town."""
    category = {k: v.category for k, v in run.urban.rights.items()}
    return (
        run.town_rights.join(_location_info(run), on=["snapshot_id", "location_id"], how="left")
        .with_columns(pl.col("type").replace_strict(category, default="other", return_dtype=pl.String).alias("category"))
    )


def bar_option(xs: list[float], series: list[dict[str, Any]], *, unit: str) -> dict[str, Any]:
    """Stacked bars on the time axis (positive and negative values stack apart)."""
    option = line_option(xs, series, unit=unit, y_min=None)
    for item in option["series"]:
        item.update({"type": "bar", "stack": "total", "barMaxWidth": 22, "barMinWidth": 3})
        item.pop("lineStyle", None)
        item.pop("showSymbol", None)
        item.pop("symbolSize", None)
    option["tooltip"]["axisPointer"] = {"type": "shadow"}
    return option


def _region_lines(run: RunData, values: dict[Any, list[float | None]]) -> list[dict[str, Any]]:
    return [_series(label, values[key], colour) for key, label, colour in region_palette(run) if key in values]


def _top_text(frame: pl.DataFrame, keys: list[str], label: str, n: int = 3) -> pl.DataFrame:
    """keys + top_<label>: "A 12 · B 5 · C 1", the n most frequent values of `label` per group."""
    return (
        frame.filter(pl.col(label).is_not_null()).group_by(*keys, label).agg(pl.len().alias("_n"))
        .sort("_n", descending=True).group_by(keys, maintain_order=True).head(n)
        .with_columns((pl.col(label) + " " + pl.col("_n").cast(pl.String)).alias("_s"))
        .group_by(keys, maintain_order=True).agg(pl.col("_s").str.join(" · ").alias(f"top_{label}"))
    )


# --------------------------------------------------------------------------------------------------------
# Town rights


def right_changes(run: RunData, have: list[str]) -> pl.DataFrame:
    """Per pair of consecutive saves (snapshot_id = the later one): rights granted, upgraded (a right replaced by the
    one it upgrades to), swapped (one right out and another in at the same town), removed, and removed where the town
    changed owner. A right that went and came back between two saves is not seen."""
    upgrades = {k: v.upgrades_to for k, v in run.urban.rights.items() if v.upgrades_to}
    by_save: dict[str, dict[int, set[str]]] = {}
    for snapshot, location, kind in run.town_rights.select("snapshot_id", "location_id", "type").iter_rows():
        by_save.setdefault(snapshot, {}).setdefault(location, set()).add(kind)
    owners: dict[str, dict[int, Any]] = {}
    if "owner_country_id" in run.locations.columns and "location_id" in run.locations.columns:
        for snapshot, location, owner in run.locations.select("snapshot_id", "location_id", "owner_country_id").iter_rows():
            owners.setdefault(snapshot, {})[location] = owner
    order = [s for s in run.snapshots["snapshot_id"].to_list() if s in set(have)]
    rows = []
    for before, after in zip(order, order[1:]):
        a, b = by_save.get(before, {}), by_save.get(after, {})
        counts = {"granted": 0, "upgraded": 0, "swapped": 0, "removed": 0, "conquered": 0}
        for location in set(a) | set(b):
            lost, gained = a.get(location, set()) - b.get(location, set()), b.get(location, set()) - a.get(location, set())
            for kind in sorted(lost):
                if upgrades.get(kind) in gained:
                    counts["upgraded"] += 1
                    lost.discard(kind)
                    gained.discard(upgrades[kind])
            swaps = min(len(lost), len(gained))
            counts["swapped"] += swaps
            counts["granted"] += len(gained) - swaps
            changed = owners and owners.get(before, {}).get(location) != owners.get(after, {}).get(location)
            counts["conquered" if changed else "removed"] += len(lost) - swaps
        rows.append({"snapshot_id": after, **counts})
    schema = {"snapshot_id": pl.String, **{k: pl.Int64 for k in ("granted", "upgraded", "swapped", "removed", "conquered")}}
    return pl.DataFrame(rows, schema=schema)


def right_fit(run: RunData) -> pl.DataFrame:
    """Per specialization right held with goods: snapshot_id, town_right_id, type, covered (gold per month of the
    right's goods made in the town), best (the most any generic specialization right would cover there), total (all
    the town makes), fit ("best", "weaker", "none")."""
    spec = {k: v for k, v in run.urban.rights.items() if v.specialization and v.goods}
    if run.production.is_empty() or not spec or run.town_rights.is_empty():
        return pl.DataFrame()
    right_goods = pl.DataFrame([(k, g) for k, v in spec.items() for g in v.goods], schema=["type", "good_id"], orient="row")
    generic_goods = right_goods.filter(pl.col("type").is_in([k for k, v in spec.items() if v.generic]))
    held = run.town_rights.filter(pl.col("type").is_in(list(spec)))
    places = held.select("snapshot_id", "location_id").unique()
    production = run.production.join(places, on=["snapshot_id", "location_id"], how="semi")
    keys = ["snapshot_id", "location_id"]
    covered = (held.join(right_goods, on="type").join(production, on=[*keys, "good_id"], how="left")
               .group_by("snapshot_id", "town_right_id").agg(pl.col("value").sum().alias("covered")))
    best = (production.join(generic_goods, on="good_id").group_by(*keys, "type").agg(pl.col("value").sum())
            .group_by(keys).agg(pl.col("value").max().alias("best")))
    total = production.group_by(keys).agg(pl.col("value").sum().alias("total"))
    return (
        held.join(covered, on=["snapshot_id", "town_right_id"], how="left").join(best, on=keys, how="left")
        .join(total, on=keys, how="left")
        .with_columns(pl.col("covered", "best", "total").fill_null(0.0))
        .with_columns(pl.when(pl.col("covered") <= 0).then(pl.lit("none"))
                      .when(pl.col("covered") >= 0.999 * pl.col("best")).then(pl.lit("best"))
                      .otherwise(pl.lit("weaker")).alias("fit"))
    )


FIT_SERIES = (("best", "Best fit", "#1baf7a"), ("weaker", "Weaker fit", "#eda100"), ("none", "Goods not made there", "#e34948"))


def town_right_charts(run: RunData, x: pl.DataFrame) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if run.town_rights.is_empty():
        return [], []
    xs = x["x"].to_list()
    have = run.urban_saves or run.town_rights["snapshot_id"].unique().to_list()
    held = _held(run)
    charts = []

    by_category = _counts(held, "category", x, have)
    by_region = _counts(held.filter(pl.col("region").is_not_null()), "region", x, have)
    views = [
        view("By category", "count", line_option(xs, [_series(label, by_category[k], colour) for k, label, colour in RIGHT_CATEGORIES
                                                      if k in by_category], unit="count", stack=True)),
        view("By world region", "count", line_option(xs, _region_lines(run, by_region), unit="count", stack=True)),
    ]
    towns = _location_info(run).filter(pl.col("town").fill_null(False))
    if towns.height:
        with_right = towns.join(held.select("snapshot_id", "location_id").unique(), on=["snapshot_id", "location_id"], how="semi")
        world_all, world_with = _counts(towns, "town", x, have), _counts(with_right, "town", x, have)
        region_all = _counts(towns.filter(pl.col("region").is_not_null()), "region", x, have)
        region_with = _counts(with_right.filter(pl.col("region").is_not_null()), "region", x, have)

        def share(a: list[float | None], b: list[float | None]) -> list[float | None]:
            return [None if (p is None or not q) else p / q * 100 for p, q in zip(a, b)]

        lines = [_series("World", share(world_with.get(True, []), world_all.get(True, [])), WORLD, width=3)] + [
            _series(label, share(region_with.get(k, [0.0] * len(xs)), region_all[k]), colour, width=1.6)
            for k, label, colour in region_palette(run) if k in region_all]
        views.append(view("Towns with a right", "pct", line_option(xs, lines, unit="pct", y_max=100)))
    charts.append(chart(
        "town_rights", SECTION, "Town rights held",
        "Every town right held at each save, by category (specialization: raises some goods' output and lowers the rest; "
        "raw materials: RGO size and output; markets & trade; military; privileges & other) and by world region. Towns "
        "with a right: the share of towns and cities (rank town or larger) that hold at least one.", views, height=460))

    # heatmap: towns per right type and save
    types = held.group_by("type").agg(pl.col("category").first(),
                                      pl.col("snapshot_id").filter(pl.col("snapshot_id") == x["snapshot_id"][-1]).len().alias("last"),
                                      pl.len().alias("ever"))
    rank = {k: i for i, (k, _, _) in enumerate(RIGHT_CATEGORIES)}
    types = types.with_columns(pl.col("category").replace_strict(rank, default=99, return_dtype=pl.Int64).alias("rank")).sort(
        "rank", "last", "ever", descending=[False, True, True])
    order = types["type"].to_list()
    ylabels = [right_label(run, t) for t in order]
    counts = _counts(held, "type", x, have)
    xlabels = x["label"].to_list()
    held_data, change_data, peak = [], [], 1.0
    for yi, kind in enumerate(order):
        values = counts.get(kind, [])
        for xi, v in enumerate(values):
            prev = values[xi - 1] if xi > 0 else None
            change = None if (v is None or prev is None) else v - prev
            if v:
                held_data.append([xi, yi, _r(math.log2(v), 3), v, change])
                peak = max(peak, v)
            if change:
                change_data.append([xi, yi, change, v, change])
    span = max([1.0] + [abs(row[2]) for row in change_data])
    fields = [["Towns", 3, "count"], ["Change since the previous save", 4, "count"]]
    reverse = (list(reversed(PRICE_HEAT[0])), list(reversed(PRICE_HEAT[1])))
    height = max(360, 20 * len(order) + 120)
    charts.append(chart(
        "town_rights_heatmap", SECTION, "Town rights by type",
        "Towns holding each right at each save (colour on a log scale), grouped by category in the order of the chart "
        "above, the most held first. Change: rights gained (blue) or lost (red) since the previous save.",
        [view("Towns", "count", heat_option(xlabels, ylabels, held_data, vmin=0.0, vmax=_r(max(1.0, math.log2(peak)), 3),
                                            colors=SEQUENTIAL_HEAT, scale_label="fn:pow2n"), fields=fields),
         view("Change since the previous save", "count", heat_option(xlabels, ylabels, change_data, vmin=-span, vmax=span,
                                                                     colors=reverse, scale_label="fn:unit:count"), fields=fields)],
        height=height))

    changes = right_changes(run, have)
    if changes.height:
        at = {s: r for s, r in zip(changes["snapshot_id"].to_list(), changes.iter_rows(named=True))}
        snaps = x["snapshot_id"].to_list()

        def col(key: str, sign: float = 1.0) -> list[float | None]:
            return [None if s not in at else sign * at[s][key] for s in snaps]

        series = [_series("Granted", col("granted"), "#1baf7a"), _series("Upgraded", col("upgraded"), "#2a78d6"),
                  _series("Swapped (one out, one in)", col("swapped"), "#eda100"), _series("Removed", col("removed", -1.0), "#e34948"),
                  _series("Removed, town changed owner", col("conquered", -1.0), "#7d5a5a")]
        charts.append(chart(
            "town_right_changes", SECTION, "Town rights granted, upgraded, swapped and removed",
            "Changes between two consecutive saves, shown at the later save. Upgraded: a right replaced by the one it "
            "upgrades to (a charter by its royal right). Swapped: a town lost one right and gained another. Removed below "
            "zero, split by whether the town changed owner between the saves. A right that went and came back between "
            "two saves is not seen.", [view("Rights", "count", bar_option(xs, series, unit="count"))], height=400))

    fit = right_fit(run)
    if fit.height:
        fit_counts = _counts(fit, "fit", x, have)
        totals = _total(fit_counts, x, have)
        shares = [_series(label, [None if (v is None or not t) else v / t * 100 for v, t in zip(fit_counts.get(k, [0.0] * len(xs)), totals)], colour)
                  for k, label, colour in FIT_SERIES]
        numbers = [_series(label, fit_counts.get(k, [0.0] * len(xs)), colour) for k, label, colour in FIT_SERIES]
        mean = fit.group_by("snapshot_id").agg(
            (pl.col("covered").sum() / pl.col("total").sum() * 100).alias("covered"),
            (pl.col("best").sum() / pl.col("total").sum() * 100).alias("best"))
        position = x.select("snapshot_id").join(mean, on="snapshot_id", how="left")
        output = [_series("Goods of the held right", position["covered"].to_list(), "#2a78d6", width=2.5),
                  _series("Goods of the best generic right", position["best"].to_list(), OTHER_GREY, dashed=True)]
        charts.append(chart(
            "town_right_fit", SECTION, "Do specialization rights fit their towns?",
            "Every specialization right held, against what its town makes (buildings and RGO, nominal output at base "
            "price). Best fit: no charter or right of the specialization lines open to every town covers more of the "
            "town's production than the held one. Weaker fit: another would cover more. Goods not made there: the town makes none of the right's goods. Share of town "
            "output: the part of all the holding towns' production in the held right's goods, against the best generic "
            "right's.",
            [view("Share of rights", "pct", line_option(xs, shares, unit="pct", stack=True, y_max=100)),
             view("Rights", "count", line_option(xs, numbers, unit="count", stack=True)),
             view("Share of town output", "pct", line_option(xs, output, unit="pct"))], height=420))

    return charts, [town_right_table(run, x, held, fit)]


def town_right_table(run: RunData, x: pl.DataFrame, held: pl.DataFrame, fit: pl.DataFrame) -> dict[str, Any]:
    keys = ["snapshot_id", "type"]
    per_type = held.group_by(keys).agg(pl.len().alias("towns"))
    snapshots = x["snapshot_id"].to_list()
    previous = dict(zip(snapshots[1:], snapshots[:-1]))
    before = per_type.select(pl.col("snapshot_id").replace_strict({v: k for k, v in previous.items()}, default=None, return_dtype=pl.String).alias("snapshot_id"),
                             "type", pl.col("towns").alias("before")).filter(pl.col("snapshot_id").is_not_null())
    per_type = per_type.join(before, on=keys, how="left")
    regions = _top_text(held.with_columns(pl.col("region").map_elements(titleize, return_dtype=pl.String)), keys, "region")
    per_type = per_type.join(regions, on=keys, how="left")
    if fit.height:
        share = fit.group_by(keys).agg(((pl.col("fit") == "best").mean() * 100).alias("best_share"))
        per_type = per_type.join(share, on=keys, how="left")
    else:
        per_type = per_type.with_columns(pl.lit(None, dtype=pl.Float64).alias("best_share"))
    goods_value: dict[tuple[str, str], list[list[Any]]] = {}
    if not run.production.is_empty():
        right_goods = pl.DataFrame([(k, g) for k, v in run.urban.rights.items() for g in v.goods], schema=["type", "good_id"], orient="row")
        made = (held.select("snapshot_id", "location_id", "type").join(right_goods, on="type")
                .join(run.production, on=["snapshot_id", "location_id", "good_id"], how="left")
                .group_by(*keys, "good_id").agg(pl.col("value").sum()).sort("value", descending=True))
        for snapshot, kind, good, value in made.select(*keys, "good_id", "value").iter_rows():
            goods_value.setdefault((snapshot, kind), []).append([good, _r(value)])
    first_save = set(snapshots[:1])
    rows: list[list[list[Any]]] = []
    by_snapshot = per_type.partition_by("snapshot_id", as_dict=True)
    for snapshot in snapshots:
        frame = by_snapshot.get((snapshot,), pl.DataFrame())
        out = []
        for r in frame.sort(["towns", "type"], descending=[True, False]).iter_rows(named=True) if frame.height else []:
            info = run.urban.rights.get(r["type"])
            change = None if snapshot in first_save else r["towns"] - (r["before"] or 0)
            out.append([right_label(run, r["type"]), CATEGORY_LABELS.get(info.category if info else "other", ""), r["towns"], change,
                        goods_value.get((snapshot, r["type"]), []), _r(r["best_share"]), r["top_region"] or ""])
        rows.append(out)
    columns = [
        {"key": "right", "label": "Town right", "kind": "text"},
        {"key": "category", "label": "Category", "kind": "text"},
        {"key": "towns", "label": "Towns", "kind": "num", "unit": "count"},
        {"key": "change", "label": "Change", "kind": "num", "unit": "count", "signed": True, "title": "since the previous save"},
        {"key": "goods", "label": "Its goods made there", "kind": "goods", "unit": "gold",
         "title": "gold per month of the right's goods made in the towns holding it (base price)"},
        {"key": "best", "label": "Best fit", "kind": "num", "unit": "pct0",
         "title": "specialization rights: share held where no other charter or right would cover more of the town's production"},
        {"key": "regions", "label": "Main world regions", "kind": "text", "wide": True},
    ]
    return {
        "key": "town_rights", "section": SECTION, "title": "Town rights",
        "caption": "Every town right held in the save: how many towns hold it, the change since the previous save, the "
                   "value of its goods those towns make, how often it is the best fit, and where it is held.",
        "columns": columns, "snapshots": x["label"].to_list(), "rows": rows, "sort": "towns", "limit": 40,
    }


# --------------------------------------------------------------------------------------------------------
# Industry promotions


def promotion_fit(run: RunData) -> pl.DataFrame:
    """Per promotion: snapshot_id, promotion_id, country_id, area, type, value (gold per month of the industry's goods
    the country makes in the area), rank (of the area among the country's areas making them, 1 = most; null if none
    there), areas (the country's areas making them), share (of the country's output of them), fit."""
    if run.promotions.is_empty() or run.production.is_empty() or not run.urban.industries:
        return pl.DataFrame()
    info = _location_info(run).filter(pl.col("owner_id").is_not_null() & pl.col("area").is_not_null())
    industry_goods = pl.DataFrame([(k, g) for k, goods in run.urban.industries.items() for g in goods],
                                  schema=["type", "good_id"], orient="row")
    wanted = run.promotions.select("snapshot_id", pl.col("country_id").alias("owner_id"), "type").unique()
    output = (
        run.production.join(info.select("snapshot_id", "location_id", "owner_id", "area"), on=["snapshot_id", "location_id"])
        .join(industry_goods, on="good_id")
        .join(wanted, on=["snapshot_id", "owner_id", "type"], how="semi")
        .group_by("snapshot_id", "owner_id", "type", "area").agg(pl.col("value").sum())
        .filter(pl.col("value") > 0)
        .with_columns(pl.col("value").rank("ordinal", descending=True).over("snapshot_id", "owner_id", "type").alias("rank"),
                      pl.len().over("snapshot_id", "owner_id", "type").alias("areas"),
                      (pl.col("value") / pl.col("value").sum().over("snapshot_id", "owner_id", "type") * 100).alias("share"))
        .rename({"owner_id": "country_id"})
    )
    return (
        run.promotions.join(output, on=["snapshot_id", "country_id", "type", "area"], how="left")
        .with_columns(pl.col("value").fill_null(0.0))
        .with_columns(pl.when((pl.col("rank") == 1) & (pl.col("areas") == 1)).then(pl.lit("only"))
                      .when(pl.col("rank") == 1).then(pl.lit("top"))
                      .when(pl.col("rank") <= 3).then(pl.lit("top3"))
                      .when(pl.col("rank").is_not_null()).then(pl.lit("lower"))
                      .otherwise(pl.lit("none")).alias("fit"))
    )


PROMOTION_FIT = (("only", "Country's only area making it", "#9a9a96"), ("top", "Country's top area", "#1baf7a"), ("top3", "2nd or 3rd area", "#2a78d6"),
                 ("lower", "Lower area", "#eda100"), ("none", "Goods not made there", "#e34948"))


def promotion_charts(run: RunData, x: pl.DataFrame) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if run.promotions.is_empty():
        return [], []
    xs = x["x"].to_list()
    have = run.urban_saves or run.promotions["snapshot_id"].unique().to_list()
    colours = industry_colours(run)
    promotions = run.promotions
    by_type = _counts(promotions, "type", x, have)
    region_of = (_location_info(run).filter(pl.col("area").is_not_null() & pl.col("region").is_not_null())
                 .group_by("snapshot_id", "area").agg(pl.col("region").mode().first()))
    with_region = promotions.join(region_of, on=["snapshot_id", "area"], how="left")
    by_region = _counts(with_region.filter(pl.col("region").is_not_null()), "region", x, have)
    countries = promotions.group_by("snapshot_id").agg(pl.col("country_id").n_unique().alias("countries"),
                                                       pl.col("area").n_unique().alias("areas"))
    known = set(have)
    position = x.select("snapshot_id").join(countries, on="snapshot_id", how="left")

    def filled(column: str) -> list[float | None]:
        return [None if s not in known else float(v or 0) for s, v in zip(position["snapshot_id"].to_list(), position[column].to_list())]

    charts = [chart(
        "industry_promotions", SECTION, "Industry promotions",
        "Every industry a country promotes in one of its areas (the goods' output there rises, the country's pops want "
        "more of them), by industry and by world region (the region of most of the area's locations).",
        [view("By industry", "count", line_option(xs, [_series(industry_label(run, k), by_type[k], colours[k])
                                                       for k in colours if k in by_type], unit="count", stack=True)),
         view("By world region", "count", line_option(xs, _region_lines(run, by_region), unit="count", stack=True)),
         view("Countries and areas", "count", line_option(xs, [
             _series("Countries promoting", filled("countries"), WORLD, width=2.5),
             _series("Areas promoted", filled("areas"), "#2a78d6")], unit="count"))], height=440)]

    fit = promotion_fit(run)
    tables: list[dict[str, Any]] = []
    if fit.height:
        fit_counts = _counts(fit, "fit", x, have)
        totals = _total(fit_counts, x, have)
        shares = [_series(label, [None if (v is None or not t) else v / t * 100 for v, t in zip(fit_counts.get(k, [0.0] * len(xs)), totals)], colour)
                  for k, label, colour in PROMOTION_FIT]
        numbers = [_series(label, fit_counts.get(k, [0.0] * len(xs)), colour) for k, label, colour in PROMOTION_FIT]
        charts.append(chart(
            "industry_promotion_fit", SECTION, "Are industries promoted where they are made?",
            "Each promotion's area ranked among the promoting country's areas by the output of the industry's goods "
            "(buildings and RGOs, nominal output at base price): the only area where the country makes the goods (no "
            "choice), its top area of several, its 2nd or 3rd, a lower one, or an area where it makes none of them.",
            [view("Share of promotions", "pct", line_option(xs, shares, unit="pct", stack=True, y_max=100)),
             view("Promotions", "count", line_option(xs, numbers, unit="count", stack=True))], height=400))
        tables.append(promotion_table(run, x, fit.join(region_of, on=["snapshot_id", "area"], how="left")))
    return charts, tables


def promotion_table(run: RunData, x: pl.DataFrame, fit: pl.DataFrame) -> dict[str, Any]:
    tags = run.countries.select("snapshot_id", "country_id", "country_tag", "country_name").unique(["snapshot_id", "country_id"])
    frame = fit.join(tags, on=["snapshot_id", "country_id"], how="left")
    rows: list[list[list[Any]]] = []
    by_snapshot = frame.partition_by("snapshot_id", as_dict=True)
    for snapshot in x["snapshot_id"].to_list():
        f = by_snapshot.get((snapshot,), pl.DataFrame())
        rows.append([[
            run.labels.country(r["country_tag"], r["country_name"]) if r["country_tag"] else f"Country {r['country_id']}",
            area_label(run, r["area"]), titleize(r["region"]) if r["region"] else "", industry_label(run, r["type"]),
            _r(r["value"]), r["rank"], r["areas"], _r(r["share"]),
        ] for r in (f.sort("value", descending=True).iter_rows(named=True) if f.height else [])])
    columns = [
        {"key": "country", "label": "Country", "kind": "text"},
        {"key": "area", "label": "Area", "kind": "text"},
        {"key": "region", "label": "World region", "kind": "text"},
        {"key": "industry", "label": "Industry", "kind": "text"},
        {"key": "output", "label": "Output there", "kind": "num", "unit": "gold",
         "title": "gold per month of the industry's goods the country makes in the area (base price)"},
        {"key": "rank", "label": "Area rank", "kind": "num", "unit": "count",
         "title": "1 = the country's area making the most of the industry's goods; empty: none made there"},
        {"key": "areas", "label": "Areas making it", "kind": "num", "unit": "count", "title": "the country's areas making any of the goods"},
        {"key": "share", "label": "Share", "kind": "num", "unit": "pct", "title": "of the country's output of the industry's goods"},
    ]
    return {
        "key": "industry_promotions", "section": SECTION, "title": "Industry promotions",
        "caption": "Every industry promotion of the save with the output of the industry's goods in the promoted area and "
                   "how that area ranks among the country's areas.",
        "columns": columns, "snapshots": x["label"].to_list(), "rows": rows, "sort": "output", "limit": 40,
    }


def urban_charts(run: RunData, x: pl.DataFrame) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    charts, tables = town_right_charts(run, x)
    more_charts, more_tables = promotion_charts(run, x)
    return charts + more_charts, tables + more_tables
