"""Interactive charts and tables of the run report.

The page (`run_report.write_page`) renders them with Apache ECharts from one JSON payload:

- a chart is ``{key, section, title, caption, height, views: [{label, unit, option, fields?}]}``; ``option`` is an
  ECharts option in which strings ``fn:<name>[:<arg>]`` stand for the page's formatter functions (JSON carries no
  functions): ``fn:axis:<unit>`` (axis tooltip), ``fn:heat`` (heatmap tooltip from the view's ``fields``),
  ``fn:year``, ``fn:unit:<unit>``, ``fn:pow2`` (log2 colour scale labels);
- a table is ``{key, section, title, caption, columns, snapshots, rows, sort}``: ``rows[i]`` are the rows of save
  ``i`` (one list per row, in column order), the page shows the last save and offers the others;
- ``goods`` is ``{good_id: {name, group, icon?}}`` (icon: page-relative PNG) in display order and ``groups`` the goods
  groups: goods appear by id in heatmap axes (``fn:goodlabel`` / ``fn:goodrich`` draw the icon) and in table columns
  of kind ``good`` (one id) and ``goods`` (``[[id, value], ...]``), the page shows icons and keeps names in tooltips;
  a chart with ``goods_legend`` gets the goods groups under its caption ("goods": with every group's goods).

Units are the dataset's: population in thousands (charts show millions), goods in units per month, gold per month
at base prices (amount x the good's default price, so volumes compare across saves).
"""

from __future__ import annotations

import math
import statistics
from datetime import datetime
from typing import TYPE_CHECKING, Any

import polars as pl

if TYPE_CHECKING:
    from prosper_or_perish_constructor.run_report import RunData

# Mod bookkeeping goods without a real market (pinned 1-gold offsets, province food accounting, labour, logistics).
DUMMY_GOODS = frozenset({"offset", "logistics", "local_food", "manual_labor", "province_food_sales"})

# Goods groups (display order): key, label, colour on a light surface, colour on the dark video map.
GOODS_GROUPS: tuple[tuple[str, str, str, str], ...] = (
    ("farming", "Farming", "#1baf7a", "#5fd1a2"),
    ("mining", "Mining", "#c98a00", "#f2c14e"),
    ("wild", "Gathering, hunting & forestry", "#e8692e", "#f39a5b"),
    ("produced", "Manufactured", "#2a78d6", "#6da7ec"),
)
GROUP_LABELS = {key: label for key, label, _, _ in GOODS_GROUPS}
GROUP_ORDER = {key: i for i, (key, _, _, _) in enumerate(GOODS_GROUPS)}

# Pop types bottom to top; peasants split into employed and subsistence (unemployed) peasants.
POP_SERIES: tuple[tuple[str, str, str], ...] = (
    ("tribesmen", "Tribesmen", "#9c7a3c"),
    ("subsistence", "Subsistence peasants", "#d6c38f"),
    ("peasants", "Peasants", "#1baf7a"),
    ("slaves", "Slaves", "#7d5a5a"),
    ("laborers", "Laborers", "#2a78d6"),
    ("soldiers", "Soldiers", "#e34948"),
    ("burghers", "Burghers", "#eda100"),
    ("clergy", "Clergy", "#4a3aa7"),
    ("nobles", "Nobles", "#e87ba4"),
)

# World regions (the dataset's macro_region) coloured by continent family, largest region first.
CONTINENT_ORDER = ("europe", "asia", "africa", "america", "oceania")
CONTINENT_SHADES = {
    "europe": ("#1f5fae", "#5b9be6", "#9cc3f2"),
    "asia": ("#b8420f", "#e8692e", "#c98a00", "#f2a65a", "#8f3a1c", "#e0b84a"),
    "africa": ("#0f7a52", "#1baf7a", "#2f8f3a", "#6cc79f", "#a6d98f"),
    "america": ("#5b3fb8", "#9a85e0", "#7d5bd0"),
    "oceania": ("#2f7f88", "#7cc0c8", "#4aa3ad"),
}
OTHER_SHADES = ("#7a7a76", "#a5a5a0", "#5f5f5b")
WORLD = "#1d1d1b"
OTHER_GREY = "#9a9a96"
CATEGORICAL = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948",
               "#5fb8c4", "#a0522d", "#7d8b2a", "#c45ab3", "#00a3a3", "#b8860b", "#8c8c88", "#6a5acd")


def goods_group_expr() -> pl.Expr:
    """Goods group key from the dataset's goods_category / goods_designation."""
    return (
        pl.when(pl.col("goods_category") == "produced").then(pl.lit("produced"))
        .when(pl.col("goods_designation") == "farming").then(pl.lit("farming"))
        .when(pl.col("goods_designation") == "mining").then(pl.lit("mining"))
        .otherwise(pl.lit("wild"))
    )


def land_region_expr() -> pl.Expr:
    """Locations of real land regions: no ocean pseudo-continents, no mod waterway regions."""
    return (
        pl.col("macro_region").is_not_null()
        & pl.col("super_region").is_not_null()
        & ~pl.col("super_region").str.starts_with("pp_")
        & ~pl.col("super_region").str.ends_with("ocean_continent")
    )


def titleize(value: object) -> str:
    text = "" if value is None else str(value).strip()
    return " ".join(part for part in text.replace("-", "_").split("_") if part).title()


# --------------------------------------------------------------------------------------------------------
# Helpers


def _r(value: Any, digits: int = 4) -> float | None:
    if value is None:
        return None
    value = float(value)
    if not math.isfinite(value):
        return None
    return float(f"{value:.{digits}g}")


def xaxis(run: RunData) -> pl.DataFrame:
    """snapshot_id, year, x (fractional year), label - one row per save in date order."""
    return (
        run.snapshots.select("snapshot_id", "year", "date_sort")
        .with_columns((pl.col("year") + ((pl.col("date_sort") // 100) % 100 - 1) / 12).alias("x"),
                      pl.col("year").cast(pl.String).alias("label"))
        .sort("date_sort")
    )


def _by_key(frame: pl.DataFrame, key: str, value: str, x: pl.DataFrame) -> dict[Any, list[float | None]]:
    """{key: values aligned with the saves of x} (None where the key has no row in a save)."""
    position = {s: i for i, s in enumerate(x["snapshot_id"].to_list())}
    out: dict[Any, list[float | None]] = {}
    for k, snapshot, v in frame.select(key, "snapshot_id", value).iter_rows():
        if snapshot in position:
            out.setdefault(k, [None] * len(position))[position[snapshot]] = v
    return out


def _aligned(frame: pl.DataFrame, value: str, x: pl.DataFrame) -> list[float | None]:
    return x.select("snapshot_id").join(frame.select("snapshot_id", value), on="snapshot_id", how="left")[value].to_list()


def _ratio(a: list[float | None], b: list[float | None], scale: float = 1.0) -> list[float | None]:
    return [None if (p is None or q is None or q == 0) else p / q * scale for p, q in zip(a, b)]


def _index(values: list[float | None]) -> list[float | None]:
    base = next((v for v in values if v), None)
    return [None if (v is None or not base) else v / base * 100 for v in values]


def _growth(values: list[float | None], xs: list[float]) -> list[float | None]:
    out: list[float | None] = [None]
    for i in range(1, len(values)):
        a, b, dt = values[i - 1], values[i], xs[i] - xs[i - 1]
        out.append(None if (not a or b is None or dt <= 0) else ((b / a) ** (1 / dt) - 1) * 100)
    return out


EPOCH = datetime(1970, 1, 1)


def _ms(x: float) -> int:
    """Fractional year (year + (month - 1) / 12) as a JavaScript timestamp: ECharts stacks along a time axis, while
    with two value axes it stacks along x."""
    year = math.floor(x + 1e-9)
    month = min(12, max(1, round((x - year) * 12) + 1))
    return int((datetime(year, month, 1) - EPOCH).total_seconds() * 1000)


def _year_ticks(xs: list[float]) -> list[int]:
    """Round years inside the run (every 10, 20, 25, 50 or 100 years, about eight ticks) as timestamps."""
    first, last = xs[0], xs[-1]
    step = next((s for s in (5, 10, 20, 25, 50, 100, 200) if (last - first) / s <= 9), 500)
    year = math.ceil(first / step) * step
    out = []
    while year <= last:
        out.append(_ms(year))
        year += step
    return out


def _series(name: str, values: list[float | None], color: str, **style: Any) -> dict[str, Any]:
    return {"name": name, "values": values, "color": color, **style}


def line_option(xs: list[float], series: list[dict[str, Any]], *, unit: str, stack: bool = False,
                y_min: float | None = 0.0, y_max: float | None = None, reference: float | None = None) -> dict[str, Any]:
    out = []
    for s in series:
        item: dict[str, Any] = {
            "type": "line", "name": s["name"], "showSymbol": len(xs) <= 12, "symbolSize": 5,
            "data": [[_ms(x), _r(v)] for x, v in zip(xs, s["values"])],
            "lineStyle": {"width": s.get("width", 2), "type": "dashed" if s.get("dashed") else "solid"},
            "emphasis": {"focus": "series"},
        }
        if stack:
            item.update({"stack": "total", "areaStyle": {"opacity": 0.9}, "lineStyle": {"width": 0.6}})
        out.append(item)
    if reference is not None and out:
        out[0]["markLine"] = {"silent": True, "symbol": "none", "label": {"show": False},
                              "lineStyle": {"type": "dashed", "color": "#8a8a86", "width": 1},
                              "data": [{"yAxis": reference}]}
    y_axis: dict[str, Any] = {"type": "value", "axisLabel": {"formatter": f"fn:unit:{unit}"}}
    if y_min is not None:
        y_axis["min"] = y_min
    else:
        y_axis["scale"] = True
    if y_max is not None:
        y_axis["max"] = y_max
    return {
        "color": [s["color"] for s in series],
        "tooltip": {"trigger": "axis", "formatter": f"fn:axis:{unit}", "confine": True},
        "legend": {"type": "scroll", "top": 0, "left": 0, "right": 0},
        "grid": {"left": 8, "right": 20, "top": 44, "bottom": 46, "containLabel": True},
        "xAxis": {"type": "time", "min": _ms(xs[0]), "max": _ms(xs[-1]),
                  "axisLabel": {"formatter": "fn:year", "hideOverlap": True, "customValues": _year_ticks(xs)},
                  "axisTick": {"customValues": _year_ticks(xs)}, "splitLine": {"show": False}},
        "yAxis": y_axis,
        "dataZoom": [{"type": "inside"}, {"type": "slider", "height": 14, "bottom": 4, "labelFormatter": "fn:year"}],
        "series": out,
    }


def heat_option(xlabels: list[str], ylabels: list[str], data: list[list[Any]], *, vmin: float, vmax: float,
                colors: tuple[list[str], list[str]], scale_label: str, goods_axis: bool = False) -> dict[str, Any]:
    """data rows are [x index, y index, colour value (clamped to vmin..vmax), tooltip fields...]; colors: the ramp
    on a light and on a dark page (the page picks one). goods_axis: ylabels are good ids, drawn as group bar + icon."""
    y_label: dict[str, Any] = {"interval": 0, "fontSize": 11}
    if goods_axis:
        y_label.update({"formatter": "fn:goodlabel", "rich": "fn:goodrich"})
    return {
        "tooltip": {"formatter": "fn:heat", "confine": True},
        "grid": {"left": 8, "right": 20, "top": 8, "bottom": 58, "containLabel": True},
        "xAxis": {"type": "category", "data": xlabels, "axisLabel": {"hideOverlap": True}, "splitArea": {"show": False}},
        "yAxis": {"type": "category", "data": ylabels, "inverse": True, "axisLabel": y_label, "triggerEvent": goods_axis},
        "visualMap": {"min": vmin, "max": vmax, "dimension": 2, "calculable": True, "orient": "horizontal",
                      "left": "center", "bottom": 2, "itemWidth": 12, "itemHeight": 280, "inRange": {"color": colors[0]},
                      "darkColors": colors[1],
                      "formatter": scale_label, "text": None},
        "series": [{"type": "heatmap", "data": data, "progressive": 0,
                    "emphasis": {"itemStyle": {"borderColor": "#1d1d1b", "borderWidth": 1}}}],
    }


def chart(key: str, section: str, title: str, caption: str, views: list[dict[str, Any]], height: int = 460,
          goods_legend: str | None = None) -> dict[str, Any]:
    """goods_legend: "goods" lists every group's goods under the caption, "groups" only the group colours."""
    out = {"key": key, "section": section, "title": title, "caption": caption, "height": height, "views": views}
    if goods_legend:
        out["goods_legend"] = goods_legend
    return out


def view(label: str, unit: str, option: dict[str, Any], **extra: Any) -> dict[str, Any]:
    return {"label": label, "unit": unit, "option": option, **extra}


# Heatmap ramps (low -> high) on a light and on a dark page: the middle / low end fades into the page.
PRICE_HEAT = (["#123055", "#256abf", "#6da7ec", "#bcd5f2", "#eef0f2", "#f1d9d4", "#e67a73", "#c63b3b", "#8f1f1f"],
              ["#9ec5f4", "#3987e5", "#184f95", "#1f3350", "#2a2d33", "#4a2626", "#8f1f1f", "#c63b3b", "#e67a73"])
SEQUENTIAL_HEAT = (["#f2f7fe", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#123055"],
                   ["#22262d", "#132c4d", "#184f95", "#256abf", "#3987e5", "#6da7ec", "#9ec5f4", "#e3eefc"])
WARM_HEAT = (["#fdf3e7", "#f9d9b0", "#f3b26d", "#e8692e", "#c63b3b", "#8f1f1f"],
             ["#22262d", "#4a2a1c", "#8f3a1c", "#e8692e", "#f3b26d", "#fde3c4"])


# --------------------------------------------------------------------------------------------------------
# Population


def _regions(run: RunData) -> pl.DataFrame:
    """snapshot_id, region, continent, population, subsistence (land regions only)."""
    return (
        run.locations.filter(land_region_expr())
        .group_by("snapshot_id", "macro_region")
        .agg(pl.col("super_region").first().alias("continent"), pl.col("total_population").sum().alias("population"),
             pl.col("unemployed_peasants").sum().alias("subsistence"))
        .rename({"macro_region": "region"})
    )


def region_palette(run: RunData) -> list[tuple[str, str, str]]:
    """[(region, label, colour)] in continent order, largest region (at the last save) first within a continent."""
    regions = _regions(run)
    if regions.is_empty():
        return []
    last = run.snapshots.sort("date_sort")["snapshot_id"][-1]
    order = (
        regions.group_by("region").agg(pl.col("continent").first(),
                                       pl.col("population").filter(pl.col("snapshot_id") == last).sum().alias("last"))
        .with_columns(pl.col("continent").replace_strict({c: i for i, c in enumerate(CONTINENT_ORDER)}, default=99,
                                                         return_dtype=pl.Int64).alias("rank"))
        .sort("rank", "last", descending=[False, True])
    )
    out, used = [], {}
    for region, continent in order.select("region", "continent").iter_rows():
        shades = CONTINENT_SHADES.get(continent, OTHER_SHADES)
        i = used.get(continent, 0)
        used[continent] = i + 1
        out.append((region, titleize(region), shades[i % len(shades)]))
    return out


def population_charts(run: RunData, x: pl.DataFrame) -> list[dict[str, Any]]:
    xs = x["x"].to_list()
    charts = []
    agg = run.locations.group_by("snapshot_id").agg(
        *[pl.col(f"population_{p}").sum().alias(p) for p in ("tribesmen", "peasants", "slaves", "laborers", "soldiers",
                                                             "burghers", "clergy", "nobles")],
        pl.col("unemployed_peasants").sum().alias("subsistence"),
        pl.col("total_population").sum().alias("total"),
    ).with_columns((pl.col("peasants") - pl.col("subsistence")).clip(lower_bound=0).alias("peasants"))
    agg = x.select("snapshot_id").join(agg, on="snapshot_id", how="left")
    people = [_series(label, (agg[key] / 1000).to_list(), color) for key, label, color in POP_SERIES]
    total = agg.select(sum(pl.col(key) for key, _, _ in POP_SERIES).alias("t"))["t"]
    share = [_series(label, (agg[key] / total * 100).to_list(), color) for key, label, color in POP_SERIES]
    charts.append(chart(
        "population_by_type", "population", "World population by pop type",
        "Every location's pops, summed per save. Peasants with a job (farms, RGOs, buildings) are Peasants; peasants "
        "without one live off subsistence farming (Subsistence peasants).",
        [view("People", "mpeople", line_option(xs, people, unit="mpeople", stack=True)),
         view("Share", "pct", line_option(xs, share, unit="pct", stack=True, y_max=100))], height=480))

    regions = _regions(run)
    palette = region_palette(run)
    pop = _by_key(regions, "region", "population", x)
    world = _aligned(agg, "total", x)
    people = [_series(label, [None if v is None else v / 1000 for v in pop.get(key, [])], color) for key, label, color in palette]
    index = [_series("World", _index(world), WORLD, width=3)] + [
        _series(label, _index(pop.get(key, [])), color, width=1.6) for key, label, color in palette]
    growth = [_series("World", _growth(world, xs), WORLD, width=3)] + [
        _series(label, _growth(pop.get(key, []), xs), color, width=1.6) for key, label, color in palette]
    charts.append(chart(
        "population_by_region", "population", "Population by world region",
        "Population of each world region (EU5 sub-continent; ocean and river-navigation pseudo-regions left out). "
        "Growth per year is the average yearly rate between two saves.",
        [view("People", "mpeople", line_option(xs, people, unit="mpeople")),
         view("Index", "index", line_option(xs, index, unit="index", y_min=None, reference=100.0)),
         view("Growth per year", "pct2", line_option(xs, growth, unit="pct2", y_min=None, reference=0.0))], height=500))

    subsistence = _by_key(regions, "region", "subsistence", x)
    world_sub = _ratio(_aligned(agg, "subsistence", x), world, 100)
    rates = [_series("World", world_sub, WORLD, width=3)] + [
        _series(label, _ratio(subsistence.get(key, []), pop.get(key, []), 100), color, width=1.6) for key, label, color in palette]
    charts.append(chart(
        "unemployment", "population", "Unemployment",
        "Subsistence peasants (peasants without a job) as a share of all people, world and per world region.",
        [view("Share of population", "pct", line_option(xs, rates, unit="pct", y_max=100))], height=460))
    return charts


# --------------------------------------------------------------------------------------------------------
# Institutions


def institution_charts(run: RunData, x: pl.DataFrame) -> list[dict[str, Any]]:
    """Institutions per person (population-weighted count present per location), world and world regions, and the
    share of the world's people living where each institution is present."""
    if run.institutions.is_empty() or "institutions" not in run.locations.columns:
        return []
    xs = x["x"].to_list()
    known = run.locations.filter(pl.col("institutions").is_not_null())
    weighted = (pl.col("institutions") * pl.col("total_population")).sum() / pl.col("total_population").sum()
    world = known.group_by("snapshot_id").agg(weighted.alias("per_person"), pl.col("total_population").sum().alias("population"))
    regions = known.filter(land_region_expr()).group_by("snapshot_id", "macro_region").agg(weighted.alias("per_person"))
    per_region = _by_key(regions, "macro_region", "per_person", x)
    per_person = [_series("World", _aligned(world, "per_person", x), WORLD, width=3)] + [
        _series(label, per_region.get(key, []), colour, width=1.6) for key, label, colour in region_palette(run)]
    shares = run.institutions.join(world.select("snapshot_id", "population").rename({"population": "world"}), on="snapshot_id").with_columns(
        (pl.col("population") / pl.col("world") * 100).alias("share"))
    first_seen = shares.join(x.select("snapshot_id", "x"), on="snapshot_id").group_by("institution").agg(pl.col("x").min()).sort("x", "institution")
    by_institution = _by_key(shares, "institution", "share", x)
    spread = [_series(titleize(name), by_institution.get(name, []), CATEGORICAL[i % len(CATEGORICAL)])
              for i, name in enumerate(first_seen["institution"].to_list())]
    return [chart(
        "institutions", "institutions", "Institutions",
        "Per person: the institutions present in each location (spread at 100 %), averaged over the people, world and "
        "world regions. Share of people: the part of the world's population that lives where an institution is present, "
        "per institution in the order they appeared.",
        [view("Per person", "num", line_option(xs, per_person, unit="num")),
         view("Share of people", "pct", line_option(xs, spread, unit="pct", y_max=100))], height=480)]


# --------------------------------------------------------------------------------------------------------
# Goods: prices, production and trade


def _goods_world(run: RunData) -> pl.DataFrame:
    """Per save and good: world production, use, imports, unmet demand, price ratio, markets short / in surplus."""
    mg = run.market_goods
    return (
        mg.with_columns(
            (pl.col("demand") - pl.col("exports") - pl.col("burgher_trade")).clip(lower_bound=0).alias("use"),
            (pl.col("demand") - pl.col("supply")).clip(lower_bound=0).alias("unmet"),
            (pl.col("supply") + pl.col("demand")).alias("volume"),
            ((pl.col("demand") > 0.01) & (pl.col("supply") < 0.9 * pl.col("demand"))).alias("short"),
            ((pl.col("production") > 0.01) & (pl.col("supply") > 1.1 * pl.col("demand"))).alias("surplus"),
        )
        .group_by("snapshot_id", "good_id")
        .agg(
            pl.col("group").first(), pl.col("default_price").first(),
            pl.col("production").sum(), pl.col("use").sum(), pl.col("demand").sum(), pl.col("supply").sum(),
            pl.col("imports").sum(), pl.col("unmet").sum(),
            ((pl.col("price") * pl.col("volume")).sum() / pl.col("volume").sum() / pl.col("default_price").first()).alias("price_ratio"),
            pl.col("short").sum().alias("markets_short"), pl.col("surplus").sum().alias("markets_surplus"),
            (pl.col("demand") > 0.01).sum().alias("markets"),
        )
    )


HEAT_ROW = 20  # px per good in the goods heatmaps (fits the 18 px icon)


def _heat_height(goods: list[Any]) -> int:
    return max(420, HEAT_ROW * len(goods) + 120)


def goods_info(run: RunData, world: pl.DataFrame, x: pl.DataFrame) -> dict[str, dict[str, Any]]:
    """{good_id: {name, group, icon?}} in heatmap order (group, then the most produced first)."""
    out: dict[str, dict[str, Any]] = {}
    for good, label, group in _goods_rows(world, run, x):
        out[good] = {"name": label, "group": group}
        if good in run.good_icons:
            out[good]["icon"] = run.good_icons[good]
    return out


def _goods_rows(world: pl.DataFrame, run: RunData, x: pl.DataFrame) -> list[tuple[str, str, str]]:
    """[(good_id, label, group)] grouped, the largest production value at the last save first within a group."""
    last = x["snapshot_id"][-1]
    order = (
        world.group_by("good_id").agg(
            pl.col("group").first(),
            (pl.col("production") * pl.col("default_price")).filter(pl.col("snapshot_id") == last).sum().alias("value"),
            (pl.col("production") + pl.col("demand")).max().alias("seen"))
        .filter(pl.col("seen") > 0)
        .with_columns(pl.col("group").replace_strict(GROUP_ORDER, default=99, return_dtype=pl.Int64).alias("rank"))
        .sort("rank", "value", descending=[False, True])
    )
    return [(g, run.labels.good(g), grp) for g, grp in order.select("good_id", "group").iter_rows()]


def _heat_data(world: pl.DataFrame, x: pl.DataFrame, goods: list[tuple[str, str, str]], colour: pl.Expr,
               fields: list[pl.Expr], lo: float, hi: float) -> list[list[Any]]:
    xpos = {s: i for i, s in enumerate(x["snapshot_id"].to_list())}
    ypos = {g: i for i, (g, _, _) in enumerate(goods)}
    frame = world.filter(pl.col("good_id").is_in(list(ypos))).select(
        "snapshot_id", "good_id", colour.alias("_c"), *[f.alias(f"_f{i}") for i, f in enumerate(fields)])
    data = []
    for row in frame.iter_rows():
        snapshot, good, c, *rest = row
        if c is None or (isinstance(c, float) and not math.isfinite(c)):
            continue
        data.append([xpos[snapshot], ypos[good], _r(min(hi, max(lo, c)), 3), *[_r(v) for v in rest]])
    return data


def price_charts(run: RunData, x: pl.DataFrame, world: pl.DataFrame) -> list[dict[str, Any]]:
    xs = x["x"].to_list()
    labels = x["label"].to_list()
    goods = _goods_rows(world, run, x)
    ylabels = [good for good, _, _ in goods]
    first = world.join(x.head(1).select("snapshot_id"), on="snapshot_id").select("good_id", pl.col("price_ratio").alias("first_ratio"))
    w = world.join(first, on="good_id", how="left")
    fields = [pl.col("price_ratio"), (pl.col("price_ratio") / pl.col("first_ratio")), pl.col("production"), pl.col("use"),
              pl.col("markets_short")]
    tip = [["Price ÷ base", 3, "ratio"], ["Change since first save", 4, "ratio"], ["World production", 5, "num"],
           ["World use", 6, "num"], ["Markets short", 7, "count"]]
    price = heat_option(labels, ylabels, _heat_data(w, x, goods, pl.col("price_ratio").log(2), fields, -1.0, 1.0),
                        vmin=-1.0, vmax=1.0, colors=PRICE_HEAT, scale_label="fn:pow2", goods_axis=True)
    change = heat_option(labels, ylabels,
                         _heat_data(w, x, goods, (pl.col("price_ratio") / pl.col("first_ratio")).log(2), fields, -1.0, 1.0),
                         vmin=-1.0, vmax=1.0, colors=PRICE_HEAT, scale_label="fn:pow2", goods_axis=True)
    charts = [chart(
        "price_heatmap", "prices", "Prices of every good",
        "World price of each good (markets weighted by traded volume) as a multiple of its base price; red = dearer, "
        "blue = cheaper. Goods grouped (the coloured bar: farming, mining, gathering/hunting/forestry, manufactured), "
        "the most produced first; hover a cell or an icon for the name. Mod bookkeeping goods (offset, logistics, "
        "province food, labour) are left out.",
        [view("Price ÷ base", "ratio", price, fields=tip), view("Change since first save", "ratio", change, fields=tip)],
        height=_heat_height(goods), goods_legend="groups")]

    # price index, use and production by goods group (weights: world use at base price)
    g = world.with_columns((pl.col("use") * pl.col("default_price")).alias("w"),
                           (pl.col("production") * pl.col("default_price")).alias("pv"))
    by_group = g.group_by("snapshot_id", "group").agg(
        ((pl.col("price_ratio") * pl.col("w")).sum() / pl.col("w").sum()).alias("index"),
        (pl.col("w").sum() / pl.col("pv").sum()).alias("use_ratio"), pl.col("pv").sum())
    total = g.group_by("snapshot_id").agg(
        ((pl.col("price_ratio") * pl.col("w")).sum() / pl.col("w").sum()).alias("index"),
        (pl.col("w").sum() / pl.col("pv").sum()).alias("use_ratio"))
    idx, use, pv = (_by_key(by_group, "group", c, x) for c in ("index", "use_ratio", "pv"))
    groups = [(k, label, colour) for k, label, colour, _ in GOODS_GROUPS if k in idx]
    charts.append(chart(
        "price_index", "prices", "Prices, use and production by goods group",
        "Price index: price ÷ base of every good, weighted by its world use at base price. Use ÷ production: what pops, "
        "buildings, construction and armies take (without trade between markets) against what is produced; above 1 "
        "the world uses more than it makes (stocks run down, prices climb). Production at base prices.",
        [view("Price index", "ratio", line_option(xs, [_series("All goods", _aligned(total, "index", x), WORLD, width=3)] + [
            _series(label, idx[k], colour) for k, label, colour in groups], unit="ratio", y_min=None, reference=1.0)),
         view("Use ÷ production", "ratio", line_option(xs, [_series("All goods", _aligned(total, "use_ratio", x), WORLD, width=3)] + [
             _series(label, use[k], colour) for k, label, colour in groups], unit="ratio", y_min=None, reference=1.0)),
         view("Production value", "gold", line_option(xs, [_series(label, pv[k], colour) for k, label, colour in groups],
                                                      unit="gold", stack=True))], goods_legend="goods"))
    return charts


def trade_charts(run: RunData, x: pl.DataFrame, world: pl.DataFrame) -> list[dict[str, Any]]:
    xs = x["x"].to_list()
    labels = x["label"].to_list()
    g = world.with_columns((pl.col("imports") * pl.col("default_price")).alias("iv"),
                           (pl.col("production") * pl.col("default_price")).alias("pv"))
    by_group = g.group_by("snapshot_id", "group").agg(pl.col("iv").sum(), pl.col("pv").sum()).with_columns(
        (pl.col("iv") / (pl.col("iv") + pl.col("pv")) * 100).alias("share"))
    total = g.group_by("snapshot_id").agg(pl.col("iv").sum(), pl.col("pv").sum()).with_columns(
        (pl.col("iv") / (pl.col("iv") + pl.col("pv")) * 100).alias("share"))
    iv, share = _by_key(by_group, "group", "iv", x), _by_key(by_group, "group", "share", x)
    groups = [(k, label, colour) for k, label, colour, _ in GOODS_GROUPS if k in iv]
    views = [
        view("Traded value", "gold", line_option(xs, [_series(label, iv[k], colour) for k, label, colour in groups],
                                                 unit="gold", stack=True)),
        view("Imported share of supply", "pct", line_option(xs, [_series("All goods", _aligned(total, "share", x), WORLD, width=3)] + [
            _series(label, share[k], colour) for k, label, colour in groups], unit="pct")),
    ]
    if not run.trades.is_empty():
        routes = run.trades.group_by("snapshot_id").agg(pl.len().alias("routes"), pl.col("from_market").n_unique().alias("exporters"),
                                                       pl.col("to_market").n_unique().alias("importers"))
        markets = run.market_goods.group_by("snapshot_id").agg(pl.col("market_id").n_unique().alias("markets"))
        views.append(view("Routes and markets", "count", line_option(xs, [
            _series("Trade routes", _aligned(routes, "routes", x), WORLD, width=3),
            _series("Markets exporting", _aligned(routes, "exporters", x), "#2a78d6"),
            _series("Markets importing", _aligned(routes, "importers", x), "#e8692e"),
            _series("Markets", _aligned(markets, "markets", x), OTHER_GREY, dashed=True)], unit="count")))
    charts = [chart(
        "world_trade", "trade", "World trade",
        "Goods imported by markets from other markets, valued at base prices (gold per month), by goods group; the "
        "imported share is imports ÷ (production + imports) of all markets together.", views, goods_legend="goods")]

    goods = _goods_rows(world, run, x)
    ylabels = [good for good, _, _ in goods]
    w = world.with_columns(
        (pl.col("imports") / (pl.col("production") + pl.col("imports")) * 100).alias("import_share"),
        (pl.col("unmet") / pl.col("demand") * 100).alias("unmet_share"))
    fields = [pl.col("import_share"), pl.col("unmet_share"), pl.col("imports"), pl.col("production"), pl.col("markets_short"),
              pl.col("markets_surplus")]
    tip = [["Imported share of supply", 3, "pct"], ["Unmet demand", 4, "pct"], ["Imports", 5, "num"], ["Production", 6, "num"],
           ["Markets short", 7, "count"], ["Markets in surplus", 8, "count"]]
    charts.append(chart(
        "trade_heatmap", "trade", "What was traded and what was not",
        "Per good and save. Imported share: imports ÷ (production + imports) of all markets. Unmet demand: demand no "
        "market could supply (Σ max(0, demand − supply) ÷ Σ demand). Markets short: supply below 90 % of demand; in "
        "surplus: producing and supply above 110 % of demand. A good with markets short and markets in surplus at the "
        "same time is one trade does not carry.",
        [view("Imported share", "pct", heat_option(labels, ylabels, _heat_data(w, x, goods, pl.col("import_share"), fields, 0.0, 60.0),
                                                    vmin=0.0, vmax=60.0, colors=SEQUENTIAL_HEAT, scale_label="fn:unit:pct0",
                                                    goods_axis=True), fields=tip),
         view("Unmet demand", "pct", heat_option(labels, ylabels, _heat_data(w, x, goods, pl.col("unmet_share"), fields, 0.0, 40.0),
                                                 vmin=0.0, vmax=40.0, colors=WARM_HEAT, scale_label="fn:unit:pct0",
                                                 goods_axis=True), fields=tip)],
        height=_heat_height(goods), goods_legend="groups"))
    return charts


def region_trade(run: RunData) -> pl.DataFrame:
    """snapshot_id, from_region, to_region, good_id, group, value: the routes that ran, summed per pair of world
    regions (the region of each market's centre; value = amount x base price, gold per month). from == to is trade
    between markets of one region."""
    schema = {"snapshot_id": pl.String, "from_region": pl.String, "to_region": pl.String, "good_id": pl.String,
              "group": pl.String, "value": pl.Float64}
    if run.trades.is_empty() or run.markets.is_empty() or run.market_goods.is_empty():
        return pl.DataFrame(schema=schema)
    region_of = run.locations.filter(land_region_expr()).select(
        "snapshot_id", pl.col("slug").alias("center_slug"), pl.col("macro_region").alias("region"))
    market_region = run.markets.select("snapshot_id", "market_id", "center_slug").join(
        region_of, on=["snapshot_id", "center_slug"], how="inner").select("snapshot_id", "market_id", "region")
    prices = run.market_goods.group_by("snapshot_id", "good_id").agg(pl.col("default_price").first(), pl.col("group").first())
    return (
        run.trades.filter(~pl.col("good_id").is_in(list(DUMMY_GOODS)))
        .join(prices, on=["snapshot_id", "good_id"], how="left")
        .with_columns((pl.col("amount") * pl.col("default_price").fill_null(1.0)).alias("value"), pl.col("group").fill_null("produced"))
        .join(market_region.rename({"market_id": "from_market", "region": "from_region"}), on=["snapshot_id", "from_market"], how="inner")
        .join(market_region.rename({"market_id": "to_market", "region": "to_region"}), on=["snapshot_id", "to_market"], how="inner")
        .group_by("snapshot_id", "from_region", "to_region", "good_id")
        .agg(pl.col("group").first(), pl.col("value").sum())
        .select(list(schema))
    )


def region_trade_totals(flows: pl.DataFrame) -> pl.DataFrame:
    """snapshot_id, region, exports (to other regions), imports (from other regions), inside (between the region's
    own markets), net (exports - imports); gold per month at base prices."""
    cross = flows.filter(pl.col("from_region") != pl.col("to_region"))
    out = cross.group_by("snapshot_id", pl.col("from_region").alias("region")).agg(pl.col("value").sum().alias("exports"))
    inn = cross.group_by("snapshot_id", pl.col("to_region").alias("region")).agg(pl.col("value").sum().alias("imports"))
    inside = flows.filter(pl.col("from_region") == pl.col("to_region")).group_by(
        "snapshot_id", pl.col("from_region").alias("region")).agg(pl.col("value").sum().alias("inside"))
    return (
        out.join(inn, on=["snapshot_id", "region"], how="full", coalesce=True)
        .join(inside, on=["snapshot_id", "region"], how="full", coalesce=True)
        .with_columns(pl.col("exports", "imports", "inside").fill_null(0.0))
        .with_columns((pl.col("exports") - pl.col("imports")).alias("net"))
    )


def region_trade_charts(run: RunData, x: pl.DataFrame, flows: pl.DataFrame) -> list[dict[str, Any]]:
    if flows.is_empty():
        return []
    xs = x["x"].to_list()
    totals = region_trade_totals(flows)
    palette = [(k, label, colour) for k, label, colour in region_palette(run) if k in set(totals["region"].to_list())]
    series = {value: _by_key(totals, "region", value, x) for value in ("exports", "imports", "net", "inside")}
    world = totals.group_by("snapshot_id").agg(pl.col("exports").sum().alias("cross"), pl.col("inside").sum())

    def lines(value: str) -> list[dict[str, Any]]:
        return [_series(label, series[value].get(k, [None] * len(xs)), colour, width=1.6) for k, label, colour in palette]

    return [chart(
        "region_trade", "trade", "Trade between world regions",
        "Goods moved by the trade routes that ran, summed per world region (the region of each market's centre), gold "
        "per month at base prices. Exports and imports count only trade with other regions; inside is trade between "
        "markets of the same region. Net = exports − imports.",
        [view("Exports to other regions", "gold", line_option(xs, lines("exports"), unit="gold", stack=True)),
         view("Imports from other regions", "gold", line_option(xs, lines("imports"), unit="gold", stack=True)),
         view("Net", "gold", line_option(xs, lines("net"), unit="gold", y_min=None, reference=0.0)),
         view("Inside the region", "gold", line_option(xs, lines("inside"), unit="gold", stack=True)),
         view("World", "gold", line_option(xs, [
             _series("Between regions", _aligned(world, "cross", x), "#2a78d6", width=2.5),
             _series("Inside regions", _aligned(world, "inside", x), "#1baf7a", width=2.5)], unit="gold"))])]


def region_trade_tables(run: RunData, x: pl.DataFrame, flows: pl.DataFrame) -> list[dict[str, Any]]:
    if flows.is_empty():
        return []
    snapshots = x["snapshot_id"].to_list()
    labels = x["label"].to_list()
    keys = ["snapshot_id", "region"]
    cross = flows.filter(pl.col("from_region") != pl.col("to_region"))
    totals = region_trade_totals(flows)
    goods_out = cross.group_by("snapshot_id", pl.col("from_region").alias("region"), "good_id").agg(pl.col("value").sum().alias("ex"))
    goods_in = cross.group_by("snapshot_id", pl.col("to_region").alias("region"), "good_id").agg(pl.col("value").sum().alias("im"))
    partners_out = cross.group_by("snapshot_id", pl.col("from_region").alias("region"), "to_region").agg(pl.col("value").sum().alias("to_v"))
    partners_in = cross.group_by("snapshot_id", pl.col("to_region").alias("region"), "from_region").agg(pl.col("value").sum().alias("from_v"))
    totals = (totals.join(_top_goods(goods_out, keys, "ex"), on=keys, how="left")
              .join(_top_goods(goods_in, keys, "im"), on=keys, how="left")
              .join(_top(partners_out.with_columns(pl.col("to_region").map_elements(titleize, return_dtype=pl.String).alias("to_name")),
                         keys, "to_v", "to_name"), on=keys, how="left")
              .join(_top(partners_in.with_columns(pl.col("from_region").map_elements(titleize, return_dtype=pl.String).alias("from_name")),
                         keys, "from_v", "from_name"), on=keys, how="left"))
    columns = [
        {"key": "region", "label": "World region", "kind": "text"},
        {"key": "exports", "label": "Exports", "kind": "num", "unit": "gold", "title": "to other regions, gold per month at base prices"},
        {"key": "imports", "label": "Imports", "kind": "num", "unit": "gold", "title": "from other regions"},
        {"key": "net", "label": "Net", "kind": "num", "unit": "gold", "signed": True, "title": "exports − imports"},
        {"key": "inside", "label": "Inside", "kind": "num", "unit": "gold", "title": "between markets of the region"},
        {"key": "top_exports", "label": "Main exports", "kind": "goods", "unit": "gold"},
        {"key": "top_imports", "label": "Main imports", "kind": "goods", "unit": "gold"},
        {"key": "to", "label": "Exports go to", "kind": "text", "wide": True},
        {"key": "from", "label": "Imports come from", "kind": "text", "wide": True},
    ]
    rows: list[list[list[Any]]] = []
    by_snapshot = totals.partition_by("snapshot_id", as_dict=True)
    for snapshot in snapshots:
        frame = by_snapshot.get((snapshot,), pl.DataFrame())
        rows.append([] if frame.is_empty() else [
            [titleize(r["region"]), _r(r["exports"]), _r(r["imports"]), _r(r["net"]), _r(r["inside"]),
             _goods_cell(r["top_ex"]), _goods_cell(r["top_im"]), r["top_to_v"] or "", r["top_from_v"] or ""]
            for r in frame.sort(pl.col("exports") + pl.col("imports"), descending=True).iter_rows(named=True)])
    pairs = cross.group_by("snapshot_id", "from_region", "to_region").agg(pl.col("value").sum())
    pairs = pairs.join(_top_goods(cross, ["snapshot_id", "from_region", "to_region"], "value"),
                       on=["snapshot_id", "from_region", "to_region"], how="left")
    share = pairs.group_by("snapshot_id").agg(pl.col("value").sum().alias("all"))
    pairs = pairs.join(share, on="snapshot_id").with_columns((pl.col("value") / pl.col("all") * 100).alias("share"))
    pcolumns = [
        {"key": "from", "label": "From (exporter)", "kind": "text"},
        {"key": "to", "label": "To (importer)", "kind": "text"},
        {"key": "value", "label": "Value", "kind": "num", "unit": "gold", "title": "gold per month at base prices"},
        {"key": "share", "label": "Share", "kind": "num", "unit": "pct", "title": "of all trade between regions"},
        {"key": "goods", "label": "Main goods", "kind": "goods", "unit": "gold"},
    ]
    prows: list[list[list[Any]]] = []
    by_snapshot = pairs.partition_by("snapshot_id", as_dict=True)
    for snapshot in snapshots:
        frame = by_snapshot.get((snapshot,), pl.DataFrame())
        prows.append([] if frame.is_empty() else [
            [titleize(r["from_region"]), titleize(r["to_region"]), _r(r["value"]), _r(r["share"]), _goods_cell(r["top_value"])]
            for r in frame.sort("value", descending=True).iter_rows(named=True)])
    return [{
        "key": "regions", "section": "trade", "title": "World regions: trade in and out",
        "caption": "Every world region of the save: what it sent to and received from other regions, trade inside it, "
                   "its main goods and partners (gold per month at base prices).",
        "columns": columns, "snapshots": labels, "rows": rows, "sort": "exports", "limit": 40,
    }, {
        "key": "region_pairs", "section": "trade", "title": "Flows between world regions",
        "caption": "Every pair of world regions that traded, exporter to importer, with the goods that made up the flow.",
        "columns": pcolumns, "snapshots": labels, "rows": prows, "sort": "value", "limit": 30,
    }]


def _top(frame: pl.DataFrame, keys: list[str], value: str, label: str, n: int = 3) -> pl.DataFrame:
    """keys + one string "A 12 · B 5 · C 1" of the n largest positive values per group."""
    return (
        frame.filter(pl.col(value) > 0.005).sort(value, descending=True).group_by(keys, maintain_order=True).head(n)
        .with_columns((pl.col(label) + " " + pl.col(value).map_elements(_short, return_dtype=pl.String)).alias("_s"))
        .group_by(keys, maintain_order=True).agg(pl.col("_s").str.join(" · ").alias(f"top_{value}"))
    )


def _top_goods(frame: pl.DataFrame, keys: list[str], value: str, n: int = 3) -> pl.DataFrame:
    """keys + a list of {good_id, value} structs: the n largest positive values per group (a `goods` table cell)."""
    return (
        frame.filter(pl.col(value) > 0.005).sort(value, descending=True).group_by(keys, maintain_order=True).head(n)
        .group_by(keys, maintain_order=True).agg(pl.struct("good_id", pl.col(value).alias("v")).alias(f"top_{value}"))
    )


def _goods_cell(items: list[dict[str, Any]] | None) -> list[list[Any]]:
    return [[item["good_id"], _r(item["v"])] for item in items or []]


def _short(value: float) -> str:
    a = abs(value)
    for limit, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "k")):
        if a >= limit:
            return f"{value / limit:.1f}{suffix}"
    return f"{value:.0f}" if a >= 10 else f"{value:.1f}"


def trade_tables(run: RunData, x: pl.DataFrame, world: pl.DataFrame) -> list[dict[str, Any]]:
    snapshots = x["snapshot_id"].to_list()
    labels = x["label"].to_list()
    mg = run.market_goods.with_columns(
        (pl.col("production") * pl.col("default_price")).alias("prod_v"),
        (pl.col("imports") * pl.col("default_price")).alias("imp_v"),
        (pl.col("exports") * pl.col("default_price")).alias("exp_v"),
        ((pl.col("demand") - pl.col("supply")).clip(lower_bound=0) * pl.col("default_price")).alias("unmet_v"),
        (pl.col("demand") * pl.col("default_price")).alias("dem_v"),
    )
    keys = ["snapshot_id", "market_id"]
    markets = mg.group_by(keys).agg(pl.col("prod_v").sum(), pl.col("imp_v").sum(), pl.col("exp_v").sum(),
                                    pl.col("unmet_v").sum(), pl.col("dem_v").sum())
    for value in ("exp_v", "imp_v", "unmet_v"):
        markets = markets.join(_top_goods(mg, keys, value), on=keys, how="left")
    people = run.locations.filter(pl.col("market_id").is_not_null()).group_by(keys).agg(
        pl.col("total_population").sum().alias("population"))
    centres = run.markets.select(*keys, "center_slug")
    owners = run.locations.select("snapshot_id", pl.col("slug").alias("center_slug"), "country_tag")
    markets = (markets.join(people, on=keys, how="left").join(centres, on=keys, how="left")
               .join(owners, on=["snapshot_id", "center_slug"], how="left"))
    columns = [
        {"key": "market", "label": "Market", "kind": "text"},
        {"key": "owner", "label": "Owner of the centre", "kind": "text"},
        {"key": "population", "label": "Population", "kind": "num", "unit": "kpeople"},
        {"key": "production", "label": "Production", "kind": "num", "unit": "gold", "title": "gold per month at base prices"},
        {"key": "imports", "label": "Imports", "kind": "num", "unit": "gold"},
        {"key": "exports", "label": "Exports", "kind": "num", "unit": "gold"},
        {"key": "net", "label": "Net", "kind": "num", "unit": "gold", "signed": True, "title": "exports − imports"},
        {"key": "import_share", "label": "Imported", "kind": "num", "unit": "pct", "title": "imports ÷ (production + imports)"},
        {"key": "unmet", "label": "Unmet", "kind": "num", "unit": "pct", "title": "demand no supply covered, share of demand (value)"},
        {"key": "top_exports", "label": "Main exports", "kind": "goods", "unit": "gold"},
        {"key": "top_imports", "label": "Main imports", "kind": "goods", "unit": "gold"},
        {"key": "top_unmet", "label": "Largest shortages", "kind": "goods", "unit": "gold"},
    ]
    rows: list[list[list[Any]]] = []
    by_snapshot = markets.partition_by("snapshot_id", as_dict=True)
    for snapshot in snapshots:
        frame = by_snapshot.get((snapshot,), pl.DataFrame())
        out = []
        for r in frame.sort("prod_v", descending=True).iter_rows(named=True):
            supply = (r["prod_v"] or 0) + (r["imp_v"] or 0)
            out.append([
                run.labels.location(r["center_slug"]) if r["center_slug"] else f"Market {r['market_id']}",
                run.labels.country(r["country_tag"]) if r["country_tag"] else "",
                _r(r["population"]), _r(r["prod_v"]), _r(r["imp_v"]), _r(r["exp_v"]), _r((r["exp_v"] or 0) - (r["imp_v"] or 0)),
                _r((r["imp_v"] or 0) / supply * 100) if supply else None,
                _r((r["unmet_v"] or 0) / r["dem_v"] * 100) if r["dem_v"] else None,
                _goods_cell(r["top_exp_v"]), _goods_cell(r["top_imp_v"]), _goods_cell(r["top_unmet_v"]),
            ])
        rows.append(out)
    tables = [{
        "key": "markets", "section": "trade", "title": "Markets",
        "caption": "Every market of the save: what it produced, imported and exported (gold per month at base prices; "
                   "main goods with their value), how much of its supply came from other markets and how much demand "
                   "nothing covered. Click a column to sort; pick another save above the table.",
        "columns": columns, "snapshots": labels, "rows": rows, "sort": "production", "limit": 40,
    }]

    # goods: world view per save, with the markets that export and import most
    centre_label = {r: run.labels.location(r) for r in run.markets["center_slug"].drop_nulls().unique().to_list()}
    market_names = run.markets.select(*keys, pl.col("center_slug").replace_strict(centre_label, default=None,
                                                                                  return_dtype=pl.String).alias("market"))
    per_market = mg.join(market_names, on=keys, how="left").with_columns(pl.col("market").fill_null("?"))
    gkeys = ["snapshot_id", "good_id"]
    top_exporters = _top(per_market.with_columns(pl.col("exports").alias("ex")), gkeys, "ex", "market")
    top_importers = _top(per_market.with_columns(pl.col("imports").alias("im")), gkeys, "im", "market")
    top_short = _top(per_market.with_columns((pl.col("demand") - pl.col("supply")).clip(lower_bound=0).alias("sh")), gkeys, "sh", "market")
    goods = world.join(top_exporters, on=gkeys, how="left").join(top_importers, on=gkeys, how="left").join(top_short, on=gkeys, how="left")
    gcolumns = [
        {"key": "good", "label": "Good", "kind": "good"},
        {"key": "group", "label": "Group", "kind": "text"},
        {"key": "production", "label": "Production", "kind": "num", "unit": "num", "title": "units per month"},
        {"key": "use", "label": "Use", "kind": "num", "unit": "num", "title": "pops, buildings, construction, armies (no trade)"},
        {"key": "price", "label": "Price ÷ base", "kind": "num", "unit": "ratio"},
        {"key": "imports", "label": "Imports", "kind": "num", "unit": "num"},
        {"key": "import_share", "label": "Imported", "kind": "num", "unit": "pct", "title": "imports ÷ (production + imports)"},
        {"key": "unmet", "label": "Unmet", "kind": "num", "unit": "pct", "title": "Σ max(0, demand − supply) ÷ Σ demand"},
        {"key": "short", "label": "Markets short", "kind": "num", "unit": "count"},
        {"key": "surplus", "label": "Markets in surplus", "kind": "num", "unit": "count"},
        {"key": "exporters", "label": "Main exporters", "kind": "text", "wide": True},
        {"key": "importers", "label": "Main importers", "kind": "text", "wide": True},
        {"key": "shortages", "label": "Largest shortages", "kind": "text", "wide": True},
    ]
    grows = []
    by_snapshot = goods.partition_by("snapshot_id", as_dict=True)
    for snapshot in snapshots:
        frame = by_snapshot.get((snapshot,), pl.DataFrame())
        out = []
        for r in frame.filter((pl.col("production") + pl.col("demand")) > 0).sort("production", descending=True).iter_rows(named=True):
            supply = (r["production"] or 0) + (r["imports"] or 0)
            out.append([
                r["good_id"], GROUP_LABELS.get(r["group"], ""), _r(r["production"]), _r(r["use"]),
                _r(r["price_ratio"]), _r(r["imports"]), _r(r["imports"] / supply * 100) if supply else None,
                _r(r["unmet"] / r["demand"] * 100) if r["demand"] else None, r["markets_short"], r["markets_surplus"],
                r["top_ex"] or "", r["top_im"] or "", r["top_sh"] or "",
            ])
        grows.append(out)
    tables.append({
        "key": "goods", "section": "trade", "title": "Goods",
        "caption": "Every good of the save (units per month): world production and use, price, how much markets "
                   "imported, demand nothing covered, how many markets were short or in surplus, and the markets that "
                   "exported, imported or lacked it most.",
        "columns": gcolumns, "snapshots": labels, "rows": grows, "sort": "production", "limit": 100,
    })

    if not run.trades.is_empty():
        routes = (
            run.trades
            .join(run.market_goods.select("snapshot_id", "good_id", "default_price").unique(["snapshot_id", "good_id"]),
                  on=["snapshot_id", "good_id"], how="left")
            .with_columns((pl.col("amount") * pl.col("default_price").fill_null(1.0)).alias("value"))
            .join(market_names.rename({"market_id": "from_market", "market": "from_name"}), on=["snapshot_id", "from_market"], how="left")
            .join(market_names.rename({"market_id": "to_market", "market": "to_name"}), on=["snapshot_id", "to_market"], how="left")
        )
        rcolumns = [
            {"key": "from", "label": "From (exporter)", "kind": "text"},
            {"key": "to", "label": "To (importer)", "kind": "text"},
            {"key": "good", "label": "Good", "kind": "good"},
            {"key": "amount", "label": "Amount", "kind": "num", "unit": "num", "title": "units per month"},
            {"key": "value", "label": "Value", "kind": "num", "unit": "gold", "title": "gold per month at base price"},
            {"key": "trader", "label": "Trader", "kind": "text", "title": "country whose merchants run the route"},
        ]
        rrows = []
        by_snapshot = routes.partition_by("snapshot_id", as_dict=True)
        tags = run.countries.select("snapshot_id", "country_id", "country_tag")
        for snapshot in snapshots:
            frame = by_snapshot.get((snapshot,), pl.DataFrame())
            if frame.is_empty():
                rrows.append([])
                continue
            frame = frame.sort("value", descending=True).head(150).join(tags, on=["snapshot_id", "country_id"], how="left")
            rrows.append([[r["from_name"] or "?", r["to_name"] or "?", r["good_id"], _r(r["amount"]), _r(r["value"]),
                           run.labels.country(r["country_tag"]) if r["country_tag"] else ""] for r in frame.iter_rows(named=True)])
        tables.append({
            "key": "routes", "section": "trade", "title": "Largest trade routes",
            "caption": "The 150 largest routes of the save by value at base price (amount moved per month).",
            "columns": rcolumns, "snapshots": labels, "rows": rrows, "sort": "value", "limit": 30,
        })
    return tables


# --------------------------------------------------------------------------------------------------------
# Buildings


def building_charts(run: RunData, x: pl.DataFrame) -> list[dict[str, Any]]:
    from prosper_or_perish_constructor.building_investment import CATEGORIES

    xs = x["x"].to_list()
    charts = []
    if not run.buildings_by_category.is_empty():
        last = x["snapshot_id"][-1]
        order = (run.buildings_by_category.filter(pl.col("snapshot_id") == last).sort("levels", descending=True)
                 ["building_category"].to_list())
        top = order[:9]
        grouped = run.buildings_by_category.with_columns(
            pl.when(pl.col("building_category").is_in(top)).then(pl.col("building_category")).otherwise(pl.lit("other")).alias("group")
        ).group_by("snapshot_id", "group").agg(pl.col("levels").sum())
        levels = _by_key(grouped, "group", "levels", x)
        series = [_series(titleize(str(g).replace("_category", "")), levels.get(g, []), CATEGORICAL[i % len(CATEGORICAL)])
                  for i, g in enumerate(top)]
        if "other" in levels:
            series.append(_series("Other", levels["other"], OTHER_GREY))
        charts.append(chart("buildings_by_category", "buildings", "Building levels by category",
                            "All building levels, grouped by the game's building category (largest nine, the rest as other).",
                            [view("Levels", "num", line_option(xs, series, unit="num", stack=True))]))
    if run.investment_by_category.is_empty():
        return charts
    inv = _by_key(run.investment_by_category, "investment_category", "investment", x)
    cats = [(key, label, CATEGORICAL[i]) for i, (key, label) in enumerate(CATEGORIES) if key in inv]
    total = [sum(v or 0.0 for v in vals) for vals in zip(*[inv[k] for k, _, _ in cats])]
    added = [_series("World", [t - total[0] for t in total], WORLD, width=3)] + [
        _series(label, [None if v is None else v - (inv[k][0] or 0.0) for v in inv[k]], colour) for k, label, colour in cats]
    charts.append(chart(
        "investment_by_category", "buildings", "Building investment",
        f"What the standing buildings cost to build {run.investment_prices}; level n costs price × (1 + increase per "
        "level × (n − 1)), today's mod prices, no country-wide cost modifiers. Added: change against the first save "
        "(negative: levels lost to destruction, downgrades or obsolete buildings).",
        [view("By category", "gold", line_option(xs, [_series(label, inv[k], colour) for k, label, colour in cats], unit="gold", stack=True)),
         view("Added since the first save", "gold", line_option(xs, added, unit="gold", y_min=None, reference=0.0))]))
    per_location = run.locations.filter(land_region_expr()).select("snapshot_id", "slug", "macro_region", "total_population").join(
        run.investment_by_location, on=["snapshot_id", "slug"], how="left")
    regions = per_location.group_by("snapshot_id", "macro_region").agg(pl.col("investment").sum(), pl.col("total_population").sum()).with_columns(
        (pl.col("investment") / pl.col("total_population")).alias("per_k"))
    world = per_location.group_by("snapshot_id").agg(pl.col("investment").sum(), pl.col("total_population").sum()).with_columns(
        (pl.col("investment") / pl.col("total_population")).alias("per_k"))
    per_k = _by_key(regions, "macro_region", "per_k", x)
    series = [_series("World", _aligned(world, "per_k", x), WORLD, width=3)] + [
        _series(label, per_k.get(key, []), colour, width=1.6) for key, label, colour in region_palette(run)]
    charts.append(chart("investment_per_capita", "buildings", "Building investment per capita",
                        f"Building investment {run.investment_prices} per 1,000 people, world and world regions.",
                        [view("Gold per 1,000 people", "gold", line_option(xs, series, unit="gold"))]))
    return charts


# --------------------------------------------------------------------------------------------------------
# Countries


def _country_frame(run: RunData) -> pl.DataFrame:
    """Landed countries per save: tag, label, population (thousands), locations, income, expense, tax base, gold."""
    countries = run.countries.filter(pl.col("owned_locations_count").fill_null(0) > 0)
    if not run.economy.is_empty() and "country_id" in countries.columns:
        countries = countries.join(run.economy, on=["snapshot_id", "country_id"], how="left")
    else:
        countries = countries.with_columns(pl.lit(None, dtype=pl.Float64).alias("income"), pl.lit(None, dtype=pl.Float64).alias("expense"))
    tax = run.locations.filter(pl.col("country_tag").is_not_null()).group_by("snapshot_id", "country_tag").agg(
        pl.col("possible_tax").sum().alias("tax_base"))
    # one row per tag and save (a landless pretender can share a tag with the landed country)
    return (countries.join(tax, on=["snapshot_id", "country_tag"], how="left")
            .sort("population", descending=True, nulls_last=True).unique(["snapshot_id", "country_tag"], keep="first"))


def _leaders(frame: pl.DataFrame, value: str, x: pl.DataFrame, n_last: int = 10, n_any: int = 3) -> list[str]:
    last = x["snapshot_id"][-1]
    ranked = frame.filter(pl.col(value).is_not_null()).with_columns(
        pl.col(value).rank("ordinal", descending=True).over("snapshot_id").alias("_rank"))
    at_end = ranked.filter((pl.col("snapshot_id") == last) & (pl.col("_rank") <= n_last)).sort("_rank")["country_tag"].to_list()
    ever = ranked.filter(pl.col("_rank") <= n_any).group_by("country_tag").agg(pl.col("_rank").min()).sort("_rank")["country_tag"].to_list()
    return at_end + [t for t in ever if t not in at_end]


def country_charts(run: RunData, x: pl.DataFrame) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    xs = x["x"].to_list()
    frame = _country_frame(run)
    world = run.locations.group_by("snapshot_id").agg(pl.col("total_population").sum().alias("world"))
    frame = frame.join(world, on="snapshot_id", how="left").with_columns(
        (pl.col("population") / pl.col("world") * 100).alias("share"),
        (pl.col("income") / pl.col("population") * 1000).alias("income_per_m"))
    names = {t: run.labels.country(t, n) for t, n in frame.sort("snapshot_id").select("country_tag", "country_name").iter_rows()}
    charts = []
    leaders = _leaders(frame, "population", x)
    pop, share = _by_key(frame, "country_tag", "population", x), _by_key(frame, "country_tag", "share", x)
    colour = {t: CATEGORICAL[i % len(CATEGORICAL)] for i, t in enumerate(leaders)}
    charts.append(chart(
        "countries_population", "countries", "Largest countries by population",
        "The ten most populous countries at the last save and every country that was among the three largest at any "
        "save (population of the locations they own; subjects count on their own).",
        [view("Population", "mpeople", line_option(xs, [_series(names[t], [None if v is None else v / 1000 for v in pop[t]], colour[t])
                                                         for t in leaders], unit="mpeople")),
         view("Share of the world", "pct", line_option(xs, [_series(names[t], share[t], colour[t]) for t in leaders], unit="pct"))]))
    if frame["income"].drop_nulls().len():
        leaders = _leaders(frame, "income", x)
        income, per_m = _by_key(frame, "country_tag", "income", x), _by_key(frame, "country_tag", "income_per_m", x)
        colour = {t: CATEGORICAL[i % len(CATEGORICAL)] for i, t in enumerate(leaders)}
        charts.append(chart(
            "countries_income", "countries", "Largest countries by income",
            "Monthly income of the ten richest countries at the last save and every country that was among the three "
            "richest at any save. Per million people: income ÷ population (the in-game GDP per capita idea).",
            [view("Monthly income", "gold", line_option(xs, [_series(names[t], income[t], colour[t]) for t in leaders], unit="gold")),
             view("Income per million people", "gold", line_option(xs, [_series(names[t], per_m[t], colour[t]) for t in leaders], unit="gold"))]))

    investment = run.investment_by_country if not run.investment_by_country.is_empty() else pl.DataFrame(
        schema={"snapshot_id": pl.String, "country_tag": pl.String, "investment": pl.Float64})
    table = frame.join(investment, on=["snapshot_id", "country_tag"], how="left")
    columns = [
        {"key": "country", "label": "Country", "kind": "text"},
        {"key": "overlord", "label": "Subject of", "kind": "text"},
        {"key": "population", "label": "Population", "kind": "num", "unit": "kpeople"},
        {"key": "share", "label": "Share", "kind": "num", "unit": "pct", "title": "share of the world population"},
        {"key": "locations", "label": "Locations", "kind": "num", "unit": "count"},
        {"key": "income", "label": "Income", "kind": "num", "unit": "gold", "title": "gold per month"},
        {"key": "expense", "label": "Expense", "kind": "num", "unit": "gold", "title": "gold per month"},
        {"key": "income_per_m", "label": "Income per million", "kind": "num", "unit": "gold", "title": "monthly income per million people"},
        {"key": "tax_base", "label": "Tax base", "kind": "num", "unit": "gold", "title": "possible tax of the owned locations"},
        {"key": "gold", "label": "Treasury", "kind": "num", "unit": "gold"},
        {"key": "investment", "label": "Building investment", "kind": "num", "unit": "gold", "title": f"buildings {run.investment_prices}"},
    ]
    rows = []
    by_snapshot = table.partition_by("snapshot_id", as_dict=True)
    for snapshot in x["snapshot_id"].to_list():
        f = by_snapshot.get((snapshot,), pl.DataFrame())
        rows.append([[
            names.get(r["country_tag"]) or run.labels.country(r["country_tag"], r["country_name"]),
            run.labels.country(r["overlord_tag"], r.get("overlord_name")) if r.get("is_subject") and r.get("overlord_tag") else "",
            _r(r["population"]), _r(r["share"]), r["owned_locations_count"], _r(r["income"]), _r(r["expense"]),
            _r(r["income_per_m"]), _r(r["tax_base"]), _r(r["gold"]), _r(r.get("investment")),
        ] for r in (f.sort("population", descending=True, nulls_last=True).head(60).iter_rows(named=True) if f.height else [])])
    tables = [{
        "key": "countries", "section": "countries", "title": "Largest countries",
        "caption": "The 60 most populous countries of the save. Income and expense are the last month's.",
        "columns": columns, "snapshots": x["label"].to_list(), "rows": rows, "sort": "population", "limit": 20,
    }]
    return charts, tables


# --------------------------------------------------------------------------------------------------------
# Game speed: wall-clock seconds per game year between consecutive saves (file time and game date), the same rule
# as profile-analyzer's game_speed: a stretch more than PAUSE_FACTOR x slower than the median of its neighbours
# was paused (menus, alt-tab, the observer auto pause) and stays out of the averages.

PAUSE_FACTOR = 1.6
PAUSE_NEIGHBOURS = 3
SPEED_WINDOW = 10.0  # game years of the running average (centred)


def speed_segments(x: pl.DataFrame, snapshots: pl.DataFrame) -> list[dict[str, Any]]:
    """[{start, end, years, seconds, per_year, pause}] in date order; empty without save file times."""
    if "mtime" not in snapshots.columns:
        return []
    points = x.join(snapshots.select("snapshot_id", "mtime"), on="snapshot_id", how="left").sort("date_sort")
    out: list[dict[str, Any]] = []
    previous = None
    for game, wall in points.select("x", "mtime").iter_rows():
        if wall is None:
            continue
        if previous is not None and game > previous[0] and wall > previous[1]:
            years, seconds = game - previous[0], wall - previous[1]
            out.append({"start": previous[0], "end": game, "years": years, "seconds": seconds, "per_year": seconds / years})
        previous = (game, wall)
    for i, s in enumerate(out):
        near = [o["per_year"] for j, o in enumerate(out) if j != i and abs(j - i) <= PAUSE_NEIGHBOURS]
        s["pause"] = bool(near) and s["per_year"] > PAUSE_FACTOR * statistics.median(near)
    return out


def speed_running(segments: list[dict[str, Any]], window: float = SPEED_WINDOW) -> list[tuple[float, float]]:
    """(midpoint, seconds per game year over the window centred there), pauses left out."""
    kept = [s for s in segments if not s["pause"]]
    out = []
    for s in kept:
        mid = (s["start"] + s["end"]) / 2
        weights = [(o["per_year"], min(mid + window / 2, o["end"]) - max(mid - window / 2, o["start"])) for o in kept]
        total = sum(w for _, w in weights if w > 0)
        if total:
            out.append((mid, sum(v * w for v, w in weights if w > 0) / total))
    return out


def speed_average(segments: list[dict[str, Any]]) -> float | None:
    """Seconds per game year over the whole run, pauses left out; None without save file times."""
    kept = [s for s in segments if not s["pause"]]
    return sum(s["seconds"] for s in kept) / sum(s["years"] for s in kept) if kept else None


def speed_charts(run: RunData, x: pl.DataFrame) -> list[dict[str, Any]]:
    segments = speed_segments(x, run.snapshots)
    kept = [s for s in segments if not s["pause"]]
    average = speed_average(segments)
    if average is None:
        return []
    paused = sum(s["seconds"] - s["years"] * average for s in segments if s["pause"])
    running = speed_running(segments)
    # each stretch is a flat step from its start to its end; a pause leaves a gap
    steps: list[list[Any]] = []
    for s in segments:
        if s["pause"]:
            steps.append([_ms(s["start"]), None])
        else:
            steps += [[_ms(s["start"]), _r(s["per_year"])], [_ms(s["end"]), _r(s["per_year"])]]
    xs = [segments[0]["start"], segments[-1]["end"]]
    option = line_option(xs, [], unit="sec")
    option["color"] = [CATEGORICAL[0], WORLD]
    option["series"] = [
        {"type": "line", "name": "Between two saves", "data": steps, "showSymbol": False, "connectNulls": False,
         "lineStyle": {"width": 1.5}, "areaStyle": {"opacity": 0.18}, "emphasis": {"focus": "series"},
         "markLine": {"silent": True, "symbol": "none", "label": {"formatter": f"average {average:.1f} s", "position": "insideEndTop"},
                      "lineStyle": {"type": "dashed", "color": "#8a8a86", "width": 1}, "data": [{"yAxis": _r(average)}]}},
        {"type": "line", "name": f"{SPEED_WINDOW:.0f}-year running average", "data": [[_ms(m), _r(v)] for m, v in running],
         "showSymbol": False, "smooth": 0.3, "lineStyle": {"width": 3}, "emphasis": {"focus": "series"}},
    ]
    pauses = len(segments) - len(kept)
    caption = (f"Wall-clock seconds the game took per game year between two consecutive saves (the saves' file times), "
               f"{average:.1f} s on average. Includes saving. "
               + (f"{pauses} stretch{'es' if pauses != 1 else ''} more than {PAUSE_FACTOR}× slower than {'their' if pauses != 1 else 'its'} "
                  f"neighbours (paused, about {paused / 60:.0f} min) left out." if pauses else "No paused stretches found."))
    return [chart("seconds_per_year", "speed", "Seconds per game year", caption, [view("Seconds", "sec", option)], height=380)]


def build_payload(run: RunData) -> dict[str, Any]:
    """Every chart and table of the page, in section order."""
    x = xaxis(run)
    charts = population_charts(run, x) + institution_charts(run, x)
    tables: list[dict[str, Any]] = []
    goods: dict[str, dict[str, Any]] = {}
    if not run.market_goods.is_empty():
        world = _goods_world(run)
        goods = goods_info(run, world, x)
        flows = region_trade(run)
        charts += trade_charts(run, x, world)
        charts += region_trade_charts(run, x, flows)
        tables += region_trade_tables(run, x, flows)
        tables += trade_tables(run, x, world)
        charts += price_charts(run, x, world)
    charts += building_charts(run, x)
    country, country_tables = country_charts(run, x)
    charts += country
    tables += country_tables
    charts += speed_charts(run, x)
    groups = [{"key": key, "label": label, "color": colour} for key, label, colour, _ in GOODS_GROUPS]
    return {"charts": charts, "tables": tables, "goods": goods, "groups": groups}


def world_trade_share(run: RunData) -> dict[str, float]:
    """snapshot_id -> imports ÷ (production + imports) at base prices, all markets together (for the summary)."""
    if run.market_goods.is_empty():
        return {}
    g = run.market_goods.group_by("snapshot_id").agg(
        (pl.col("imports") * pl.col("default_price")).sum().alias("iv"),
        (pl.col("production") * pl.col("default_price")).sum().alias("pv"))
    return {s: (iv / (iv + pv) if (iv + pv) else 0.0) for s, iv, pv in g.iter_rows()}
