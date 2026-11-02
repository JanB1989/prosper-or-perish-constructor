"""The data of the run report's budget page (`budget.html`): where the money comes from, who gets it, where it goes.

One save at a time, per country (`save_budget`, cached per save as parquet, filled in worker processes before the run
loads), then summed to the world, the world regions (a country counts in the region of its capital) and the largest
countries of each save (`write_budget_page`: `budget/index.js`, `budget/<n>.js`, `budget/summary.js`).

What is booked and what is worked out:
- Only countries that own land count: a dead country keeps the gold and last ledger it died with in the save (about 2,000
  of them by 1747, a tenth of the booked tax base and most of the tribes' gold).
- Booked by the game, last month: a country's income and expense, tax, trade balance, tariffs, foreign buildings, the
  spending of each budget line; an estate's ledger (its balance is exactly its incomes minus its expenses); the tax and
  possible tax of each location and estate; each building's profit.
- Stocks: gold of countries and estates, debt; goods in the markets at market price, building levels at list price.
- Off the budget: what a country earned above its budget lines and did not keep (income - expense - the monthly change
  of its gold since the last save). No line of the save holds it; it follows building capital closely (construction).
- By source: a location's tax base is the profit of its buildings plus what is left, which goes to its RGO (location tax
  base = 1.02 x profit + RGO part at 1697, r2 0.99). A building's profit goes to the goods it makes by output value at
  market price, not to Province Food or bookkeeping goods; a building with no real good stays a source of its own. Each
  country's sources are scaled to its estates' ledger (the location figures are this month's, the ledger last month's),
  and the state's tax follows each location's estates' tax at the rate those estates really paid.
- Trade by good: (price at the destination - price at the source) x size per route, scaled to what the country and its
  estates booked as trade income.
"""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import get_context
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

import polars as pl

from prosper_or_perish_constructor.run_report_charts import DUMMY_GOODS, land_region_expr, region_palette, titleize
from prosper_or_perish_constructor.run_report_data import write_data
from prosper_or_perish_constructor.run_report_goods import OTHER_REGION, PAGE_GROUPS, RGO, _read, _sig, page_groups

if TYPE_CHECKING:
    from prosper_or_perish_constructor.run_report import RunData

CACHE_VERSION = "budget-1"
TABLES = ("country", "estates", "sources", "trade", "stock")
TOP_COUNTRIES = 40  # countries of each save with figures of their own on the page
SMALL_SOURCE = 0.0003  # a scope's sources below this share of its tax base are summed up
WORKERS = 6
WORKER_POLARS_THREADS = 4
WORLD = "world"

ESTATE_NAMES = {
    "nobles_estate": ("Nobles", "#4a3aa7"), "clergy_estate": ("Clergy", "#e87ba4"), "burghers_estate": ("Burghers", "#2a78d6"),
    "peasants_estate": ("Peasants", "#1baf7a"), "tribes_estate": ("Tribes", "#a0522d"), "dhimmi_estate": ("Dhimmi", "#eda100"),
    "cossacks_estate": ("Cossacks", "#e34948"), "crown_estate": ("Crown", "#9a9a96"),
}
SPENT = ("upkeep", "navy", "army", "court", "fort", "diplomatic", "colonial", "exploration", "cultural", "food")
# an estate's ledger of last month (in the save's names); its balance is the sum of IN minus the sum of OUT
ESTATE_IN = ("taxable_income", "uncontrolled_income", "trade_income", "tariff_income", "interest_income", "other")
ESTATE_OUT = ("paid_taxes", "pop_expense", "building_expense", "invest_expense", "infra_expense", "io_expense", "rebel_expense",
              "food_expense", "private_army_expense")
ESTATE_FIELDS = ("gold", "balance", *ESTATE_IN, *ESTATE_OUT)
# one number per scope and save, in this order (budget/<n>.js `L`, budget/index.js `fields`)
FIELDS = (
    "income", "expense", "tax", "trade", "tariff", "foreign", "rest",
    *SPENT, "mercenaries", "other_budget", "treasury", "off_budget", "has_previous",
    "gold", "debt", "capital", "population", *[f"e_{f}" for f in ESTATE_FIELDS],
)


class Index:
    """Names to the page's numbers, per kind, in first-seen order."""

    def __init__(self) -> None:
        self.lists: dict[str, list[str]] = {k: [] for k in ("good", "building", "estate", "scope", "region")}
        self.maps: dict[str, dict[str, int]] = {k: {} for k in self.lists}

    def of(self, kind: str, key: str) -> int:
        found = self.maps[kind].get(key)
        if found is None:
            found = self.maps[kind][key] = len(self.lists[kind])
            self.lists[kind].append(key)
        return found


# --------------------------------------------------------------------------------------------------------
# one save, per country
def _numbers(frame: pl.DataFrame, columns: tuple[str, ...] | list[str]) -> pl.DataFrame:
    return frame.with_columns(pl.col(c).cast(pl.Float64).fill_null(0.0) for c in columns)


def good_shares(flows: pl.DataFrame, prices: pl.DataFrame) -> pl.DataFrame:
    """building_id, good_id, share: the real goods a building makes, by output value at market price."""
    made = (
        flows.filter((pl.col("direction") == "output") & ~pl.col("good_id").is_in(sorted(DUMMY_GOODS)))
        .join(prices, on=["market_id", "good_id"], how="inner")
        .with_columns((pl.col("nominal_amount") * pl.col("price")).alias("value"))
        .group_by("building_id", "good_id").agg(pl.col("value").sum())
        .filter(pl.col("value") > 0)
    )
    return made.with_columns((pl.col("value") / pl.col("value").sum().over("building_id")).alias("share")).select("building_id", "good_id", "share")


def tax_sources(buildings: pl.DataFrame, shares: pl.DataFrame, locations: pl.DataFrame, estate_tax: pl.DataFrame,
                estates: pl.DataFrame) -> pl.DataFrame:
    """country_id, good_id (null: no good), building_type (RGO for what the buildings leave), tax_base, state_tax."""
    places = locations.filter(pl.col("owner_country_id").is_not_null() & (pl.col("possible_tax") > 0))
    profit = (
        buildings.filter(pl.col("last_months_profit") != 0)
        .join(shares, on="building_id", how="left")
        .with_columns((pl.col("last_months_profit") * pl.col("share").fill_null(1.0)).alias("value"))
        .select("location_id", "building_type", "good_id", "value")
        .join(places.select("location_id"), on="location_id", how="semi")
        .group_by("location_id", "building_type", "good_id").agg(pl.col("value").sum())
    )
    earned = profit.group_by("location_id").agg(pl.col("value").sum().alias("earned"))
    placed = places.join(earned, on="location_id", how="left").with_columns(pl.col("earned").fill_null(0.0))
    # more profit than tax base: the profits shrink to it; else the rest is the RGO's
    scale = placed.select("location_id", pl.when(pl.col("earned") > pl.col("possible_tax")).then(pl.col("possible_tax") / pl.col("earned")).otherwise(1.0).alias("scale"))
    rgo = placed.filter(pl.col("possible_tax") > pl.col("earned")).select(
        "location_id", pl.lit(RGO).alias("building_type"), pl.col("raw_material").alias("good_id"), (pl.col("possible_tax") - pl.col("earned")).alias("value"))
    parts = pl.concat([
        profit.join(scale, on="location_id").with_columns(pl.col("value") * pl.col("scale")).drop("scale").select("location_id", "building_type", pl.col("good_id").cast(pl.String), "value"),
        rgo.select("location_id", "building_type", pl.col("good_id").cast(pl.String), "value"),
    ])
    # the state's tax of a location: its estates' tax at the rate each estate of that country really paid
    owners = places.select("location_id", "owner_country_id")
    taxed = estate_tax.join(owners, on="location_id").rename({"owner_country_id": "country_id", "estate": "estate_type"})
    ledger = estates.select("country_id", "estate_type", "paid_taxes", (pl.col("taxable_income") + pl.col("uncontrolled_income")).alias("base"))
    rates = (
        taxed.group_by("country_id", "estate_type").agg(pl.col("tax").sum().alias("taxed"))
        .join(ledger, on=["country_id", "estate_type"], how="left")
        .with_columns(pl.when(pl.col("taxed") > 0).then(pl.col("paid_taxes").fill_null(0.0) / pl.col("taxed")).otherwise(0.0).alias("rate"))
    )
    state = (
        taxed.join(rates.select("country_id", "estate_type", "rate"), on=["country_id", "estate_type"])
        .with_columns((pl.col("tax") * pl.col("rate")).alias("state"))
        .group_by("location_id").agg(pl.col("state").sum())
    )
    # scaled to the estates' ledger per country
    base = ledger.group_by("country_id").agg(pl.col("base").sum())
    possible = places.group_by("owner_country_id").agg(pl.col("possible_tax").sum().alias("possible")).rename({"owner_country_id": "country_id"})
    factor = possible.join(base, on="country_id", how="left").with_columns((pl.col("base").fill_null(0.0) / pl.col("possible")).alias("factor")).select("country_id", "factor")
    out = (
        parts.join(places.select("location_id", pl.col("owner_country_id").alias("country_id"), "possible_tax"), on="location_id")
        .join(state, on="location_id", how="left")
        .join(factor, on="country_id", how="left")
        .with_columns(
            (pl.col("value") * pl.col("factor").fill_null(1.0)).alias("tax_base"),
            (pl.col("value") / pl.col("possible_tax") * pl.col("state").fill_null(0.0)).alias("state_tax"),
        )
        .group_by("country_id", "good_id", "building_type").agg(pl.col("tax_base").sum(), pl.col("state_tax").sum())
    )
    return out


def trade_by_good(trades: pl.DataFrame, prices: pl.DataFrame, booked: pl.DataFrame) -> pl.DataFrame:
    """country_id, good_id (null: booked, but no route of the country to spread it over), trade. `booked`: country_id, booked."""
    frm = prices.select(pl.col("market_id").alias("from_market"), "good_id", pl.col("price").alias("price_from"))
    to = prices.select(pl.col("market_id").alias("to_market"), "good_id", pl.col("price").alias("price_to"))
    gross = (
        trades.filter((pl.col("happened") == "yes") & ~pl.col("good_id").is_in(sorted(DUMMY_GOODS)))
        .join(frm, on=["from_market", "good_id"]).join(to, on=["to_market", "good_id"])
        .with_columns(((pl.col("price_to") - pl.col("price_from")) * pl.col("size")).clip(lower_bound=0.0).alias("gross"))
        .group_by("country_id", "good_id").agg(pl.col("gross").sum())
        .filter(pl.col("gross") > 0)
    )
    totals = gross.group_by("country_id").agg(pl.col("gross").sum().alias("all"))
    positive = booked.filter(pl.col("booked") > 0)
    spread = gross.join(totals, on="country_id").join(positive, on="country_id").with_columns((pl.col("gross") / pl.col("all") * pl.col("booked")).alias("trade")).select("country_id", pl.col("good_id").cast(pl.String), "trade")
    none = positive.join(totals, on="country_id", how="anti").select("country_id", pl.lit(None, dtype=pl.String).alias("good_id"), pl.col("booked").alias("trade"))
    return pl.concat([spread, none])


def save_budget(dataset: Path, playthrough: str, snapshot: str, previous: str | None = None, months: int = 0) -> dict[str, pl.DataFrame] | None:
    """The tables of one save, or None when its snapshot has no estate ledger (ingested before the dataset kept it)."""
    def read(table: str, columns: list[str], at: str = snapshot) -> pl.DataFrame:
        return _read(dataset, table, playthrough, at, columns)

    estates = read("estate_ledger", ["country_id", "estate_type", *ESTATE_FIELDS])
    budget = read("country_budget", ["country_id", *[f"spent_{s}" for s in SPENT], "last_months_mercenary_maintenance"])
    if estates.is_empty() or budget.is_empty():
        return None
    estates = _numbers(estates, ESTATE_FIELDS).filter(pl.col("country_id").is_not_null())
    money = ["gold", "income", "expense", "total_debt", "last_months_tax_income", "monthly_trade_balance", "last_months_tariff_income", "last_months_foreign_building_income"]
    economy = _numbers(read("country_ai", ["country_id", *money]), money)
    budget = _numbers(budget, [c for c in budget.columns if c != "country_id"])
    locations = read("locations", ["location_id", "owner_country_id", "tax", "possible_tax", "raw_material", "total_population", "macro_region", "super_region", "market_id"])
    locations = _numbers(locations, ["tax", "possible_tax", "total_population"]).with_columns(
        pl.when(land_region_expr()).then(pl.col("macro_region")).otherwise(pl.lit(OTHER_REGION)).alias("region"))
    meta = read("countries", ["country_id", "country_tag", "country_name", "capital"])
    investment = read("building_investment", ["location_id", "investment"])
    buildings = _numbers(read("buildings", ["building_id", "building_type", "location_id", "last_months_profit"]), ["last_months_profit"])
    estate_tax = _numbers(read("location_estate_tax", ["location_id", "estate", "tax"]), ["tax"])
    flows = read("production_method_good_flows", ["building_id", "market_id", "good_id", "direction", "nominal_amount"])
    goods = read("market_goods", ["market_id", "good_id", "price", "stockpile"])
    prices = goods.select("market_id", "good_id", pl.col("price").cast(pl.Float64)).filter(pl.col("price").is_not_null())
    trades = read("trades", ["good_id", "size", "from_market", "to_market", "country_id", "happened"]).with_columns(pl.col("size").cast(pl.Float64).fill_null(0.0))

    # a dead country still has its last ledger in the save
    alive = locations.filter(pl.col("owner_country_id").is_not_null()).select(pl.col("owner_country_id").alias("country_id")).unique()
    estates = estates.join(alive, on="country_id", how="semi")
    economy = economy.join(alive, on="country_id", how="semi")

    sources = tax_sources(buildings, good_shares(flows, prices), locations, estate_tax, estates)

    ledger = estates.group_by("country_id").agg(pl.col(c).sum().alias(f"e_{c}") for c in ESTATE_FIELDS)
    country = (
        economy.join(ledger, on="country_id", how="left").join(budget, on="country_id", how="left")
        .with_columns(pl.exclude("country_id").fill_null(0.0))
        .with_columns(
            pl.col("monthly_trade_balance").clip(lower_bound=0.0).alias("trade"),
            pl.col("last_months_tax_income").alias("tax"),
            pl.col("last_months_tariff_income").alias("tariff"),
            pl.col("last_months_foreign_building_income").alias("foreign"),
            pl.col("total_debt").alias("debt"),
            pl.col("last_months_mercenary_maintenance").alias("mercenaries"),
            *[pl.col(f"spent_{s}").alias(s) for s in SPENT],
        )
        .with_columns(
            (pl.col("income") - pl.col("tax") - pl.col("trade") - pl.col("tariff") - pl.col("foreign")).clip(lower_bound=0.0).alias("rest"),
            (pl.col("expense") - pl.sum_horizontal(*SPENT, "mercenaries")).clip(lower_bound=0.0).alias("other_budget"),
        )
    )
    # the change of a country's gold since the last save; a country new since then counts as keeping its gold level
    earlier = read("country_ai", ["country_id", "gold"], previous) if previous and months > 0 else pl.DataFrame()
    if earlier.is_empty():
        country = country.with_columns(pl.lit(0.0).alias("treasury"), pl.lit(0.0).alias("has_previous"))
    else:
        country = country.join(earlier.select("country_id", pl.col("gold").cast(pl.Float64).alias("gold_before")), on="country_id", how="left").with_columns(
            ((pl.col("gold") - pl.col("gold_before")) / months).fill_null(0.0).alias("treasury"), pl.lit(1.0).alias("has_previous"))
    country = country.with_columns((pl.col("income") - pl.col("expense") - pl.col("treasury")).alias("off_budget"))

    owned = locations.filter(pl.col("owner_country_id").is_not_null())
    people = owned.group_by("owner_country_id").agg(pl.col("total_population").sum().alias("population")).rename({"owner_country_id": "country_id"})
    biggest = owned.sort("total_population", descending=True).unique("owner_country_id", keep="first", maintain_order=True).select(pl.col("owner_country_id").alias("country_id"), pl.col("region").alias("largest_region"))
    capitals = meta.join(locations.select(pl.col("location_id").alias("capital"), pl.col("region").alias("capital_region")), on="capital", how="left") if "capital" in meta.columns else meta
    capital_value = pl.DataFrame({"country_id": [], "capital": []}, schema={"country_id": pl.Int64, "capital": pl.Float64})
    if not investment.is_empty():
        capital_value = investment.join(owned.select("location_id", pl.col("owner_country_id").alias("country_id")), on="location_id").group_by("country_id").agg(pl.col("investment").cast(pl.Float64).sum().alias("capital"))
    country = (
        country.join(people, on="country_id", how="left")
        .join(capital_value, on="country_id", how="left")
        .join(biggest, on="country_id", how="left")
        .join(capitals.select("country_id", pl.col("country_tag").alias("tag"), pl.col("country_name").alias("name"), "capital_region"), on="country_id", how="left")
        .with_columns(
            pl.coalesce(pl.col("capital_region").cast(pl.String), pl.col("largest_region").cast(pl.String), pl.lit(OTHER_REGION)).alias("region"),
            pl.col("population").fill_null(0.0), pl.col("capital").fill_null(0.0),
        )
        .select("country_id", "tag", "name", "region", *FIELDS)
    )
    region_of_market = read("markets", ["market_id", "center_location_id"]).join(
        locations.select(pl.col("location_id").alias("center_location_id"), "region"), on="center_location_id", how="left").select("market_id", pl.col("region").fill_null(OTHER_REGION))
    stock = (
        goods.filter(~pl.col("good_id").is_in(sorted(DUMMY_GOODS)))
        .join(region_of_market, on="market_id", how="left")
        .with_columns((pl.col("stockpile").cast(pl.Float64).fill_null(0.0) * pl.col("price").cast(pl.Float64).fill_null(0.0)).alias("value"), pl.col("region").fill_null(OTHER_REGION))
        .group_by("region").agg(pl.col("value").sum())
    )
    booked = country.select("country_id", (pl.col("trade") + pl.col("e_trade_income")).alias("booked"))
    return {
        "country": country,
        "estates": estates.select("country_id", "estate_type", *ESTATE_FIELDS),
        "sources": sources,
        "trade": trade_by_good(trades, prices, booked),
        "stock": stock,
    }


def _write(folder: Path, flows: dict[str, pl.DataFrame]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for name in TABLES:
        flows[name].write_parquet(folder / f"{name}.parquet")
    (folder / "done").write_text("", encoding="utf-8")


def _read_cached(folder: Path) -> dict[str, pl.DataFrame] | None:
    if not (folder / "done").is_file():
        return None
    try:
        return {name: pl.read_parquet(folder / f"{name}.parquet") for name in TABLES}
    except (OSError, pl.exceptions.PolarsError):
        return None


def _fill_save(job: tuple[Path, str, str, str | None, int, Path]) -> str:
    dataset, playthrough, snapshot, previous, months, folder = job
    flows = save_budget(dataset, playthrough, snapshot, previous, months)
    if flows is not None:
        _write(folder, flows)
    return snapshot


def _months_between(earlier: dict[str, Any], later: dict[str, Any]) -> int:
    return (later["year"] - earlier["year"]) * 12 + (later["month"] - earlier["month"])


def _jobs(snapshots: list[dict[str, Any]], dataset: Path, playthrough: str, cache: Path) -> list[tuple[Path, str, str, str | None, int, Path]]:
    jobs = []
    for n, snap in enumerate(snapshots):
        previous = snapshots[n - 1] if n else None
        jobs.append((dataset, playthrough, snap["snapshot_id"], previous["snapshot_id"] if previous else None,
                     _months_between(previous, snap) if previous else 0, cache / f"{snap['snapshot_id']}.{CACHE_VERSION}"))
    return jobs


def prepare_budget_flows(playthrough: str, snapshots: list[dict[str, Any]], *, dataset: Path, cache: Path, workers: int = WORKERS,
                         log: Callable[[str], None] = print) -> None:
    """Every save's budget tables into the cache, in worker processes (before the report loads the run, as the goods
    flows). `snapshots`: snapshot_id, year, month in game order. A save a worker could not do is left to the page builder."""
    import os
    import time

    todo = [job for job in _jobs(snapshots, dataset, playthrough, cache) if not (job[-1] / "done").is_file()]
    if not todo:
        return
    started = time.perf_counter()
    workers = min(workers, len(todo), max(1, (os.cpu_count() or 1) // WORKER_POLARS_THREADS))
    previous = os.environ.get("POLARS_MAX_THREADS")
    os.environ["POLARS_MAX_THREADS"] = str(WORKER_POLARS_THREADS)
    failed = 0
    try:
        with ProcessPoolExecutor(workers, mp_context=get_context("spawn")) as pool:
            for future in as_completed([pool.submit(_fill_save, job) for job in todo]):
                try:
                    future.result()
                except Exception as error:  # noqa: BLE001 - the page builder redoes the save serially
                    failed += 1
                    log(f"budget: a worker failed ({type(error).__name__}: {error}); computed serially instead")
    finally:
        if previous is None:
            os.environ.pop("POLARS_MAX_THREADS", None)
        else:
            os.environ["POLARS_MAX_THREADS"] = previous
    log(f"budget: {len(todo) - failed} saves in {workers} workers, {time.perf_counter() - started:.1f}s")


# --------------------------------------------------------------------------------------------------------
# from countries to the page's scopes
def _scope_key(kind: str, value: object = None) -> str:
    return WORLD if kind == WORLD else f"{kind}:{value}"


def _sum_scope(country: pl.DataFrame, estates: pl.DataFrame, sources: pl.DataFrame, trade: pl.DataFrame, stock: float | None,
               index: Index, min_share: float = SMALL_SOURCE) -> dict[str, Any]:
    """One scope of a save: L its FIELDS plus goods stock, E per estate, G sources, T trade by good."""
    totals = country.select(pl.col(f).sum() for f in FIELDS).row(0, named=True)
    payload: dict[str, Any] = {"L": [_sig(totals[f]) for f in FIELDS], "stock": _sig(stock) if stock is not None else None}
    payload["E"] = [
        [index.of("estate", row["estate_type"]), *[_sig(row[f]) for f in ESTATE_FIELDS]]
        for row in estates.group_by("estate_type").agg(pl.col(f).sum() for f in ESTATE_FIELDS).sort("estate_type").iter_rows(named=True)
        if row["gold"] or row["taxable_income"] or row["pop_expense"]
    ]
    grouped = sources.group_by("good_id", "building_type").agg(pl.col("tax_base").sum(), pl.col("state_tax").sum()).sort("tax_base", descending=True)
    base = max(float(grouped["tax_base"].sum()), 1e-9) if grouped.height else 1e-9
    rows, small_base, small_state = [], 0.0, 0.0
    for good, building, tax_base, state_tax in grouped.iter_rows():
        if abs(tax_base) < min_share * base:
            small_base += tax_base
            small_state += state_tax
        else:
            rows.append([index.of("good", good) if good else -1, index.of("building", building), _sig(tax_base), _sig(state_tax)])
    if small_base:
        rows.append([-1, -1, _sig(small_base), _sig(small_state)])
    payload["G"] = rows
    payload["T"] = [[index.of("good", g) if g else -1, _sig(v)] for g, v in trade.group_by("good_id").agg(pl.col("trade").sum()).sort("trade", descending=True).iter_rows()
                    if v and abs(v) >= min_share * base]
    return payload


def _load(cache: Path | None, job: tuple[Path, str, str, str | None, int, Path]) -> dict[str, pl.DataFrame] | None:
    dataset, playthrough, snapshot, previous, months, folder = job
    flows = _read_cached(folder) if cache else None
    if flows is None:
        flows = save_budget(dataset, playthrough, snapshot, previous, months)
        if flows is not None and cache:
            _write(folder, flows)
    return flows


def build_budget_data(run: RunData, dataset: Path, out: Path, cache: Path, log: Callable[[str], None] = print) -> dict[str, Any] | None:
    """Write budget/<n>.js and budget/summary.js; returns the pieces of the index, or None when no save has estates."""
    folder = out / "budget"
    folder.mkdir(parents=True, exist_ok=True)
    index = Index()
    palette = region_palette(run)
    for key, _, _ in palette:
        index.of("region", key)
    index.of("region", OTHER_REGION)
    for estate in ESTATE_NAMES:
        index.of("estate", estate)
    index.of("scope", WORLD)
    for key, _, _ in palette:
        index.of("scope", _scope_key("r", key))
    index.of("scope", _scope_key("r", OTHER_REGION))

    snapshots = run.snapshots.select("snapshot_id", "date", "year").to_dicts()
    for snap in snapshots:
        snap["month"] = int(str(snap.get("date") or "1.1.1").split(".")[1])
    jobs = _jobs(snapshots, dataset, run.playthrough_id, cache)

    # the countries with figures of their own: the largest of each save, once
    names: dict[str, dict[str, Any]] = {}
    saves_top: list[list[int]] = []
    loaded: list[dict[str, pl.DataFrame] | None] = []
    for job in jobs:
        flows = _load(cache, job)
        loaded.append(flows)
        if flows is None:
            saves_top.append([])
            continue
        top = flows["country"].sort("income", descending=True).head(TOP_COUNTRIES)
        saves_top.append(top["country_id"].to_list())
        for row in top.select("country_id", "tag", "name").iter_rows(named=True):
            names[_scope_key("c", row["country_id"])] = {"tag": row["tag"], "name": row["name"]}
    if not any(flows is not None for flows in loaded):
        return None
    known = sorted({c for top in saves_top for c in top})
    for country_id in known:
        index.of("scope", _scope_key("c", country_id))

    saves: list[dict[str, Any]] = []
    series: dict[int, dict[str, list[Any]]] = {}
    gold_series: dict[int, dict[int, list[Any]]] = {}
    by_good: dict[int, dict[int, list[float]]] = {}
    count = len(jobs)

    def note(scope: int, n: int, payload: dict[str, Any]) -> None:
        entry = series.setdefault(scope, {f: [None] * count for f in (*FIELDS, "stock")})
        for f, value in zip(FIELDS, payload["L"]):
            entry[f][n] = value
        entry["stock"][n] = payload["stock"]
        golds = gold_series.setdefault(scope, {})
        for row in payload["E"]:
            golds.setdefault(row[0], [None] * count)[n] = row[1]
        goods = by_good.setdefault(scope, {})
        for good, _, tax_base, _ in payload["G"]:
            if good >= 0:
                entry_good = goods.setdefault(good, [0.0] * count)
                entry_good[n] += tax_base or 0.0

    for n, (snap, flows) in enumerate(zip(snapshots, loaded)):
        name = f"budget/{n:03d}.js"
        saves.append({"id": snap["snapshot_id"], "label": str(snap.get("year") or snap.get("date")), "date": snap.get("date"), "file": name})
        if flows is None:
            write_data(out, name, {"scopes": {}, "top": [], "regionOf": {}})
            continue
        country, estates, sources, trade = flows["country"], flows["estates"], flows["sources"], flows["trade"]
        region_stock = dict(flows["stock"].iter_rows())
        region_of = dict(country.select("country_id", "region").iter_rows())
        scopes: dict[str, Any] = {}
        world = _sum_scope(country, estates, sources, trade, sum(region_stock.values()), index)
        scopes[str(index.of("scope", WORLD))] = world
        note(index.of("scope", WORLD), n, world)
        for region, members in country.group_by("region"):
            key = _scope_key("r", region[0])
            ids = members["country_id"].to_list()
            payload = _sum_scope(members, estates.filter(pl.col("country_id").is_in(ids)), sources.filter(pl.col("country_id").is_in(ids)),
                                 trade.filter(pl.col("country_id").is_in(ids)), region_stock.get(region[0], 0.0), index)
            scope = index.of("scope", key)
            scopes[str(scope)] = payload
            note(scope, n, payload)
        wanted = set(saves_top[n])
        for country_id in known:
            members = country.filter(pl.col("country_id") == country_id)
            if members.is_empty():
                continue
            payload = _sum_scope(members, estates.filter(pl.col("country_id") == country_id), sources.filter(pl.col("country_id") == country_id),
                                 trade.filter(pl.col("country_id") == country_id), None, index)
            scope = index.of("scope", _scope_key("c", country_id))
            note(scope, n, payload)
            if country_id in wanted:
                scopes[str(scope)] = payload
        write_data(out, name, {
            "scopes": scopes,
            "top": [index.of("scope", _scope_key("c", c)) for c in saves_top[n]],
            "regionOf": {str(index.of("scope", _scope_key("c", c))): index.of("scope", _scope_key("r", region_of.get(c) or OTHER_REGION)) for c in saves_top[n]},
        })
    summary: dict[str, Any] = {}
    for scope, entry in series.items():
        goods = by_good.get(scope, {})
        top = sorted(goods, key=lambda g: -max(goods[g]))[:10]
        rest = [sum(goods[g][n] for g in goods if g not in top) for n in range(count)]
        summary[str(scope)] = {
            "L": {f: entry[f] for f in entry},
            "gold": {str(k): v for k, v in gold_series.get(scope, {}).items()},
            "goods": {str(g): [_sig(v) for v in goods[g]] for g in top},
            "rest": [_sig(v) for v in rest],
        }
    write_data(out, "budget/summary.js", summary)
    log(f"budget page: {len(saves)} saves, {len(known)} countries with figures of their own")
    return {"saves": saves, "index": index, "palette": palette, "names": names}


def index_payload(run: RunData, built: dict[str, Any], dataset: Path, repo: Path | None = None) -> dict[str, Any]:
    from prosper_or_perish_constructor.run_report_urban import LOC_NAME_CALL

    index: Index = built["index"]
    labels = run.labels

    def clean(text: str | None, key: str) -> str:
        text = text or labels._text(key) or titleize(key)
        return LOC_NAME_CALL.sub(lambda m: labels._text(m.group(1)) or titleize(m.group(1)), text)

    path = dataset / "tables" / "building_catalog" / f"playthrough_id={run.playthrough_id}" / f"{run.snapshots['snapshot_id'][-1]}.parquet"
    building_names = dict(pl.read_parquet(path, columns=["building_type", "building_name"]).iter_rows()) if path.is_file() else {}
    groups = page_groups(repo) if repo else {}
    regions = {key: (label, colour) for key, label, colour in built["palette"]}
    scopes = []
    for key in index.lists["scope"]:
        if key == WORLD:
            scopes.append({"id": key, "name": "World", "kind": "world"})
        elif key.startswith("r:"):
            region = key[2:]
            label, colour = regions.get(region, ("Seas and other" if region == OTHER_REGION else titleize(region), "#9a9a96"))
            scopes.append({"id": key, "name": label, "kind": "region", "color": colour})
        else:
            who = built["names"].get(key, {})
            scopes.append({"id": key, "name": labels.country(who.get("tag"), who.get("name")), "kind": "country", "tag": who.get("tag")})
    return {
        "run": run.name, "years": list(run.years), "saves": built["saves"], "fields": list(FIELDS), "estateFields": list(ESTATE_FIELDS),
        "goods": [{"id": g, "name": labels.good(g), "group": groups.get(g, "other"), "icon": run.good_icons.get(g)} for g in index.lists["good"]],
        "groups": [{"key": k, "label": label, "color": colour} for k, label, colour in PAGE_GROUPS],
        "buildings": [{"id": b, "name": "RGO" if b == RGO else clean(building_names.get(b), b)} for b in index.lists["building"]],
        "estates": [{"id": e, "name": ESTATE_NAMES.get(e, (titleize(e), ""))[0], "color": ESTATE_NAMES.get(e, ("", "#9a9a96"))[1]} for e in index.lists["estate"]],
        "scopes": scopes,
    }


def write_budget_page(run: RunData, out: Path, *, repo: Path, dataset: Path, cache: Path, log: Callable[[str], None] = print) -> Path | None:
    """The budget page; none for a run whose saves were ingested before the dataset kept the estate ledger and are gone."""
    built = build_budget_data(run, dataset, out, cache, log)
    if built is None:
        log("budget page: no save of this run has the estate ledger")
        return None
    write_data(out, "budget/index.js", index_payload(run, built, dataset, repo))
    from prosper_or_perish_constructor.run_report_budget_page import budget_page_html

    path = out / "budget.html"
    path.write_text(budget_page_html(run.name, run.years), encoding="utf-8")
    return path


