"""Start market stock (2026-11-04, Jan): a new game's markets start with roughly the stock they settle at.

A market's target price falls as its stock fills (stock_prices: supply side + 6.7 x 5 % of stock), so a new game slid for
about a decade while stocks went from 2 to 45+ months of supply. No script can set a price or a default price, but
``add_goods_supply`` can add stock, so the on_action this module writes fills every market once, a few days into the game:
on day 0 the location modifiers and the stock ceilings they set may not be in place yet, and prices only step on the 1st of
the month, so nothing is lost before 1 May 1337. The price then only has to step down to its target at MONTHLY_PRICE_CHANGE.

The stock of a market and good comes out of game, from what the build itself places:

    stock = min(months(x) x flow, 0.85 x ceiling) - existing_months x flow,  flow = max(use, make)
    months(x) = ((1 - 0.2 x) / (x - 0.2) - 1) / 0.335

Solving the price law at supply = demand for the good's settled price x (price / default): that many months of flow put
the target at x. use and make are start flows per market: people x the goods' pop demand, building levels x inputs and
outputs (each slot's methods averaged), RGO workers by rank, land quality from the World Builder rows. The ceiling is the
market's stock ceiling from its centre's development: at 90 % of it the AI stops building producers of the good there
(LOCAL_OVERSUPPLY_STOCKPILE_THRESHOLD), so the injection stays below that.

``start_market_stock.csv`` holds one row per good: the settled price and one engine factor for each of those four
flows, because the engine's wealth rules and method choice are not modelled. Demand, recipes, levels and pops all move
the result at every build; the table needs a new run only when a good's settled price itself moves
(``ppc start-stock calibrate``). Numbers: docs/market_rulebook.md "Start market stock".
"""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from dataclasses import dataclass, field
import hashlib
import json
import math
from pathlib import Path
import re
import tomllib

from eu5gameparser.domain.buildings import load_building_data
from eu5gameparser.domain.goods import load_goods_data
from eu5gameparser.domain.pop_types import load_pop_type_data
import polars as pl

from prosper_or_perish_constructor.worldbuilder import start_placement as sp
from prosper_or_perish_constructor.worldbuilder.contract import load_config as load_worldbuilder_config
from prosper_or_perish_constructor.worldbuilder.development import SETUP_RELATIVE_PATH
from prosper_or_perish_constructor.worldbuilder.start_simulation import setup_levels

OUTPUT = Path("in_game/common/on_action/pp_start_market_stock.txt")
TABLE = Path("start_market_stock.csv")
LOCATIONS = Path("data/vanilla/locations_with_raw_material.parquet")
START_MARKETS = Path("config/start_markets.csv")
LOAD_ORDER = Path("constructor.load_order.toml")
POP_DEMAND_FILE = Path("in_game/common/goods_demand/pp_new_goods_demands.txt")
ON_ACTION = "pp_start_market_stock"
DELAY_DAYS = 5             # after the first daily ticks, before the first monthly price step
LAND_ATTRIBUTES = ("climate", "topography", "vegetation", "soil_type", "fertility")
SUPPLY_FROM_STOCK = 0.335  # STOCKPILE_TRADE_IMPACT_ON_SUPPLY_SCALE 6.7 x MARKET_STOCKPILE_PERCENTAGE_FOR_EXTRA_TRADE 0.05
PRICE_C = 0.2              # c of the price law, target = default x (D + c S) / (S + c D)
LOWEST_GAP = 0.02          # a settled price at the .2 floor would need endless stock
FACTORS = ("pop_factor", "input_factor", "rgo_factor", "output_factor")
CEILING_BASE = 275.0      # market_center 250 + 25 at every location (day-0 save)
CEILING_PER_DEVELOPMENT = 100.0  # maximum_stockpile_capacity of the development static modifier
CEILING_SHARE = 0.85      # below LOCAL_OVERSUPPLY_STOCKPILE_THRESHOLD 0.9
INPUT_FOLDERS = ("in_game/common/goods", "in_game/common/goods_demand", "in_game/common/pop_types", "in_game/common/building_types",
                 "in_game/common/production_methods", "main_menu/setup/1337")

MarketGood = tuple[str, str]


@dataclass(frozen=True)
class Config:
    existing_months: float
    min_amount: float
    not_goods: frozenset[str]


@dataclass(frozen=True)
class Row:
    settled_price: float
    pop_factor: float = 0.0
    input_factor: float = 0.0
    rgo_factor: float = 0.0
    output_factor: float = 0.0
    rest_per_k: float = 0.0  # flow the model cannot place, per 1,000 people of the market


@dataclass
class Flows:
    """Model flows at game start, before the engine factors."""

    pop: Counter = field(default_factory=Counter)
    inputs: Counter = field(default_factory=Counter)
    rgo: Counter = field(default_factory=Counter)
    outputs: Counter = field(default_factory=Counter)
    people: Counter = field(default_factory=Counter)  # thousands per market
    ceiling: dict[str, float] = field(default_factory=dict)  # stock ceiling per market


@dataclass
class Result:
    markets: int = 0
    goods: int = 0
    lines: int = 0
    gold: float = 0.0
    changed: bool = False
    skipped: bool = False
    missing_goods: list[str] = field(default_factory=list)


def load_project_config(project: Path) -> Config:
    raw = tomllib.loads(project.read_text(encoding="utf-8"))["start_market_stock"]
    return Config(float(raw["existing_months"]), float(raw["min_amount"]), frozenset(raw["not_goods"]))


def stock_months(settled_price: float) -> float:
    """Months of flow in stock that put the target at this price / default when supply = demand."""
    x = settled_price
    return ((1 - PRICE_C * x) / max(x - PRICE_C, LOWEST_GAP) - 1) / SUPPLY_FROM_STOCK


def target_price(supply: float, demand: float, stock: float) -> float:
    """The price law's target / default for these flows and this stock (ramp full, the offsets left in)."""
    s = max(0.0, supply + SUPPLY_FROM_STOCK * stock) + 0.5
    d = max(0.0, demand) + 0.5
    return min(3.0, max(PRICE_C, (d + PRICE_C * s) / (s + PRICE_C * d)))


def load_table(repo: Path) -> dict[str, Row]:
    lines = (repo / TABLE).read_text(encoding="utf-8").splitlines()
    rows = csv.DictReader(line for line in lines if not line.startswith("#"))
    return {r["good"]: Row(*(float(r[k]) for k in ("settled_price", *FACTORS, "rest_per_k"))) for r in rows}


def _markets_of_locations(repo: Path, mod_root: Path, vanilla_root: Path, locations: pl.DataFrame) -> dict[str, str]:
    lines = (repo / START_MARKETS).read_text(encoding="utf-8-sig").splitlines()
    by_pool = {(r["owner"], r["province"]): r["market"] for r in csv.DictReader(line for line in lines if not line.startswith("#"))}
    owners = sp.load_owners(vanilla_root, mod_root)
    out = {}
    for tag, province in locations.select("location_tag", "province").iter_rows():
        market = by_pool.get((owners.get(tag), province))
        if market:
            out[tag] = market
    return out


def _land_output(repo: Path, project: Path):
    """location, good -> the World Builder rows' local output modifier."""
    handover = load_worldbuilder_config(repo, project).handover
    with (handover / "location_attributes.csv").open(encoding="utf-8-sig") as handle:
        attributes = {r["location_tag"]: r for r in csv.DictReader(handle)}
    rows: dict[str, dict[str, dict[str, float]]] = defaultdict(dict)
    with (handover / "attribute_rows.csv").open(encoding="utf-8-sig") as handle:
        for r in csv.DictReader(handle):
            rows[r["attribute"]][r["value"]] = {k.removeprefix("output_"): float(v) for k, v in r.items() if k.startswith("output_") and v}
    intercept = rows["reference"]["intercept"]

    def output(tag: str, good: str) -> float:
        place = attributes.get(tag)
        if not place:
            return 0.0
        return intercept.get(good, 0.0) + sum(rows[a].get(place[a], {}).get(good, 0.0) for a in LAND_ATTRIBUTES)

    return output


def _per_person_demand(goods: pl.DataFrame, pop_types: pl.DataFrame, pop_demand: dict[str, float]) -> dict[str, dict[str, float]]:
    """good -> pop type -> the goods file's demand per 1,000 people, before the engine's wealth rules."""
    upper = {r["name"]: bool(r["upper"]) for r in pop_types.to_dicts()}
    out: dict[str, dict[str, float]] = {}
    for r in goods.to_dicts():
        add = json.loads(r["demand_add"] or "{}")
        multiply = json.loads(r["demand_multiply"] or "{}")
        per_type = {}
        for name, is_upper in upper.items():
            amount = add.get("all", 0.0) + add.get(name, 0.0) + (add.get("upper", 0.0) if is_upper else 0.0)
            factor = multiply.get(name, 1.0) * (multiply.get("upper", 1.0) if is_upper else 1.0)
            if amount * factor > 0:
                per_type[name] = amount * factor * pop_demand.get(r["name"], 1.0)
        if per_type:
            out[r["name"]] = per_type
    return out


def _pop_demand_values(mod_root: Path) -> dict[str, float]:
    text = (mod_root / POP_DEMAND_FILE).read_text(encoding="utf-8-sig")
    block = text.split("REPLACE:pop_demand", 1)[1].split("\n}", 1)[0]
    return {m.group(1): float(m.group(2)) for m in re.finditer(r"^\s*([a-z_]+)\s*=\s*([0-9.]+)", block, re.M)}


def _slot_flows(buildings: pl.DataFrame, methods: pl.DataFrame) -> tuple[dict[str, dict[str, float]], dict[str, dict[str, float]]]:
    """building -> good -> input and output per level, each slot's methods averaged (the engine picks among them)."""
    by_name = {r["name"]: r for r in methods.to_dicts()}
    inputs: dict[str, dict[str, float]] = defaultdict(dict)
    outputs: dict[str, dict[str, float]] = defaultdict(dict)
    for building in buildings.to_dicts():
        name = building["name"]
        for slot in building["unique_production_method_groups"] or []:
            found = [by_name[m] for m in slot if m in by_name]
            for method in found:
                for good, amount in zip(method["input_goods"] or [], method["input_amounts"] or []):
                    inputs[name][good] = inputs[name].get(good, 0.0) + amount / len(found)
                if method["produced"] and method["output"]:
                    good = method["produced"]
                    outputs[name][good] = outputs[name].get(good, 0.0) + method["output"] / len(found)
    return inputs, outputs


def model_flows(repo: Path, project: Path, mod_root: Path, vanilla_root: Path) -> Flows:
    load_order = repo / LOAD_ORDER
    goods_data = load_goods_data(profile="constructor", load_order_path=load_order)
    building_data = load_building_data(profile="constructor", load_order_path=load_order, goods_data=goods_data)
    pop_types = load_pop_type_data(profile="constructor", load_order_path=load_order).pop_types
    per_person = _per_person_demand(goods_data.goods, pop_types, _pop_demand_values(mod_root))
    locations = pl.read_parquet(repo / LOCATIONS, columns=["location_tag", "province", "raw_material"])
    market_of = _markets_of_locations(repo, mod_root, vanilla_root, locations)
    flows = Flows()
    development = dict(re.findall(r"^\s*(\w+) = ([0-9.]+)", (mod_root / SETUP_RELATIVE_PATH).read_text(encoding="utf-8-sig"), re.M))
    flows.ceiling = {m: CEILING_BASE + CEILING_PER_DEVELOPMENT * float(development.get(m, 0.0)) for m in set(market_of.values())}

    pops = sp.parse_pops((mod_root / sp.POPS_SETUP_PATH).read_text(encoding="utf-8-sig"))
    for tag, rows in pops.items():
        market = market_of.get(tag)
        if not market:
            continue
        for pop in rows:
            flows.people[market] += pop.size_k
            for good, per_type in per_person.items():
                if pop.type in per_type:
                    flows.pop[(market, good)] += pop.size_k * per_type[pop.type]

    land_output = _land_output(repo, project)
    inputs, outputs = _slot_flows(building_data.buildings, building_data.production_methods)
    for tag, levels in setup_levels(vanilla_root, mod_root).items():
        market = market_of.get(tag)
        if not market:
            continue
        for building, level in levels.items():
            for good, amount in inputs.get(building, {}).items():
                flows.inputs[(market, good)] += level * amount
            for good, amount in outputs.get(building, {}).items():
                flows.outputs[(market, good)] += level * amount * max(0.05, 1 + land_output(tag, good))

    start = sp.StartConfig.from_raw(tomllib.loads(project.read_text(encoding="utf-8"))["worldbuilder"]["start"])
    ranks = sp.load_ranks(vanilla_root, mod_root)
    for tag, raw_material in locations.select("location_tag", "raw_material").iter_rows():
        market = market_of.get(tag)
        if market and raw_material:
            workers = start.rgo_workers_k.get(ranks.get(tag, "rural_settlement"), start.rgo_workers_k["rural_settlement"])
            flows.rgo[(market, raw_material)] += workers * max(0.05, 1 + land_output(tag, raw_material))
    return flows


def plan(flows: Flows, table: dict[str, Row], config: Config) -> dict[MarketGood, float]:
    """(market, good) -> goods to add at game start."""
    out: dict[MarketGood, float] = {}
    for market in sorted(flows.people):
        for good, row in table.items():
            if good in config.not_goods:
                continue
            key = (market, good)
            use = flows.pop[key] * row.pop_factor + flows.inputs[key] * row.input_factor + flows.people[market] * row.rest_per_k
            make = flows.rgo[key] * row.rgo_factor + flows.outputs[key] * row.output_factor
            flow = max(use, make)
            total = min(stock_months(row.settled_price) * flow, CEILING_SHARE * flows.ceiling.get(market, math.inf))
            amount = total - config.existing_months * flow
            if amount >= config.min_amount:
                out[key] = round(amount, 1)
    return out


def _fingerprint(repo: Path, project: Path, mod_root: Path) -> str:
    """Everything the plan reads; the finalize pass skips the parser while this holds (ppc sync must stay fast)."""
    handover = load_worldbuilder_config(repo, project).handover
    files = [repo / TABLE, repo / START_MARKETS, repo / LOCATIONS, project, Path(__file__), handover / "location_attributes.csv", handover / "attribute_rows.csv"]
    for folder in INPUT_FOLDERS:
        files.extend(sorted((mod_root / folder).glob("*.txt")))
    digest = hashlib.sha1()
    for path in files:
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()[:16]


def _without_fingerprint(text: str) -> str:
    """Later finalize passes touch the fingerprint's inputs, so ``changed`` looks at the plan alone."""
    return re.sub(r"^# inputs \w*\n", "", text, count=1, flags=re.M)


def render(stock: dict[MarketGood, float], fingerprint: str = "") -> str:
    lines = [
        "# Generated by ppc finalize (start_market_stock.py); do not edit by hand.",
        f"# Every market gets roughly the stock it settles at, once, {DELAY_DAYS} days into a new game.",
        f"# inputs {fingerprint}",
        "on_game_start = {",
        "\ton_actions = {",
        f"\t\tdelay = {{ days = {DELAY_DAYS} }}",
        f"\t\t{ON_ACTION}",
        "\t}",
        "}",
        "",
        f"{ON_ACTION} = {{",
        "\teffect = {",
    ]
    by_market: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for (market, good), amount in sorted(stock.items()):
        by_market[market].append((good, amount))
    for market, rows in by_market.items():
        lines.append(f"\t\tlocation:{market}.market = {{")
        lines.extend(f"\t\t\tadd_goods_supply = {{ goods = goods:{good} amount = {amount:g} }}" for good, amount in rows)
        lines.append("\t\t}")
    lines += ["\t}", "}", ""]
    return "\n".join(lines)


def apply(repo: Path, project: Path, mod_root: Path, vanilla_root: Path, write: bool = True) -> Result:
    fingerprint = _fingerprint(repo, project, mod_root)
    path = mod_root / OUTPUT
    if write and path.is_file() and f"# inputs {fingerprint}\n" in path.read_text(encoding="utf-8-sig")[:400]:
        return Result(skipped=True)
    config = load_project_config(project)
    table = load_table(repo)
    prices = {r["name"]: r["default_market_price"] or 0.0 for r in load_goods_data(profile="constructor", load_order_path=repo / LOAD_ORDER).goods.to_dicts()}
    flows = model_flows(repo, project, mod_root, vanilla_root)
    stock = plan(flows, table, config)
    text = render(stock, fingerprint)
    at_start = {good for part in (flows.pop, flows.inputs, flows.rgo, flows.outputs) for (_, good), value in part.items() if value > 0}
    before = path.read_text(encoding="utf-8-sig") if path.is_file() else None
    result = Result(
        markets=len({market for market, _ in stock}),
        goods=len({good for _, good in stock}),
        lines=len(stock),
        gold=sum(amount * prices.get(good, 0.0) for (_, good), amount in stock.items()),
        changed=before is None or _without_fingerprint(before) != _without_fingerprint(text),
        missing_goods=sorted(at_start - set(table) - config.not_goods),
    )
    if write and before != text:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8-sig")
    return result


# ---------------------------------------------------------------------------------------------
# calibration: only when a good's settled price has moved, or a new good came in
# ---------------------------------------------------------------------------------------------
def _save_tables(save: Path, repo: Path) -> Path:
    """The engine tables of a day-0 save (a folder of tables is taken as it is)."""
    if save.is_dir():
        return save
    from eu5gameparser.savegame.engine import EngineContext

    work = Path.home() / ".cache/eu5save/start_market_stock"
    work.mkdir(parents=True, exist_ok=True)
    context = EngineContext.load(profile="constructor", load_order_path=repo / LOAD_ORDER, work_dir=work)
    result = context.extract([save], work, jobs=1)[0]
    if not result.ok:
        raise SystemExit(f"{save}: {result.error}")
    return Path(result.out)


def _start_flows(tables: Path, config: Config) -> pl.DataFrame:
    flows = ["supply", "demand", "demanded_Trade", "demanded_BurgherTrades", "supplied_Trade", "supplied_BurgherTrades", "demanded_Pops", "stockpile"]
    goods = pl.read_parquet(tables / "market_goods.parquet", columns=["market_center_slug", "good_id", "default_price", *flows])
    goods = goods.filter(~pl.col("good_id").is_in(list(config.not_goods))).with_columns(pl.col(c).fill_null(0.0).fill_nan(0.0) for c in flows)
    goods = goods.with_columns(
        use=(pl.col("demand") - pl.col("demanded_Trade") - pl.col("demanded_BurgherTrades")).clip(0, None),
        make=(pl.col("supply") - pl.col("supplied_Trade") - pl.col("supplied_BurgherTrades")).clip(0, None),
    )
    rgo = pl.read_parquet(tables / "rgo_flows.parquet").filter(pl.col("direction") == "output")
    rgo = rgo.group_by("market_center_slug", "good_id").agg(pl.col("allocated_amount").sum().alias("rgo"))
    return goods.join(rgo, on=["market_center_slug", "good_id"], how="left").with_columns(pl.col("rgo").fill_null(0.0))


def _settled_prices(dataset: Path, runs: list[str], year: int, config: Config) -> dict[str, float]:
    if not runs:
        manifest = pl.read_parquet(dataset / "manifest.parquet")
        full = manifest.group_by("playthrough_id").agg(n=pl.len(), first=pl.col("year").min(), last=pl.col("date_sort").max())
        runs = full.filter(pl.col("n") >= 90, pl.col("first") <= 1345).sort("last", descending=True)["playthrough_id"].to_list()[:5]
    if not runs:
        raise SystemExit(f"{dataset}: no full run in the dataset, name one with --runs")
    frames = []
    for run in runs:
        files = sorted((dataset / "tables/market_goods" / f"playthrough_id={run}").glob(f"{year}_*.parquet"))
        if not files:
            raise SystemExit(f"run {run} has no save from {year}")
        one = pl.read_parquet(files[0], columns=["good_id", "price", "default_price", "supply", "demand"]).filter(pl.col("price").is_not_null(), pl.col("default_price") > 0)
        one = one.with_columns(x=pl.col("price") / pl.col("default_price"), w=pl.max_horizontal(pl.col("supply").fill_null(0.0), pl.col("demand").fill_null(0.0)) + 0.01)
        # by volume, not the median market: large markets sit above small ones, and it is their price the world feels
        frames.append(one.group_by("good_id").agg(((pl.col("x") * pl.col("w")).sum() / pl.col("w").sum()).alias("x")))
    settled = pl.concat(frames).group_by("good_id").agg(pl.col("x").mean())
    return {good: x for good, x in settled.iter_rows() if good not in config.not_goods}


def calibrate(repo: Path, project: Path, mod_root: Path, vanilla_root: Path, *, save: Path, runs: list[str], year: int = 1362) -> int:
    """Write the table from a day-0 save and the settled prices of full runs. Returns the number of goods."""
    config = load_project_config(project)
    flows = model_flows(repo, project, mod_root, vanilla_root)
    start = _start_flows(_save_tables(save, repo), config)
    settled = _settled_prices(repo / "graphs/dataset", runs, year, config)
    world = start.group_by("good_id").agg(pl.col("demanded_Pops", "use", "make", "rgo").sum())
    people = sum(flows.people.values())

    def total(part: Counter) -> Counter:
        out: Counter = Counter()
        for (_, good), value in part.items():
            out[good] += value
        return out

    model = {name: total(getattr(flows, name)) for name in ("pop", "inputs", "rgo", "outputs")}
    rows = []
    for good, pop, use, make, rgo in world.sort("good_id").iter_rows():
        if good not in settled:
            continue
        real = {"pop": pop, "inputs": max(0.0, use - pop), "rgo": min(rgo, make), "outputs": max(0.0, make - rgo)}
        factor = {name: real[name] / model[name][good] if model[name][good] > 0 else 0.0 for name in real}
        rest_use = sum(real[n] for n in ("pop", "inputs") if model[n][good] <= 0)
        rest_make = sum(real[n] for n in ("rgo", "outputs") if model[n][good] <= 0)
        rows.append((good, settled[good], factor["pop"], factor["inputs"], factor["rgo"], factor["outputs"], max(rest_use, rest_make) / people))
    out = repo / TABLE
    with out.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("# Generated by ppc start-stock calibrate; settled price from full runs, engine factors from one day-0 save.\n")
        handle.write(f"# save {save.name}, settled year {year}, runs {', '.join(r[:8] for r in runs) or 'newest five'}. See start_market_stock.py.\n")
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["good", "settled_price", *FACTORS, "rest_per_k"])
        for row in rows:
            writer.writerow([row[0], *(f"{v:.5g}" for v in row[1:])])
    return len(rows)


def check_against_save(repo: Path, project: Path, mod_root: Path, vanilla_root: Path, save: Path) -> dict[str, float]:
    """Put the planned stock into a day-0 save's real markets: how far is the target from the settled price?"""
    config = load_project_config(project)
    table = load_table(repo)
    stock = plan(model_flows(repo, project, mod_root, vanilla_root), table, config)
    start = _start_flows(_save_tables(save, repo), config)
    misses = {"with": [0.0, 0.0], "without": [0.0, 0.0]}
    weight_sum = 0.0
    for r in start.to_dicts():
        row = table.get(r["good_id"])
        if row is None or r["use"] + r["make"] <= 0:
            continue
        net = min(r["supplied_Trade"], r["demanded_Trade"]) + min(r["supplied_BurgherTrades"], r["demanded_BurgherTrades"])
        added = stock.get((r["market_center_slug"], r["good_id"]), 0.0)
        weight = max(r["use"], r["make"]) * (r["default_price"] or 0.0)
        weight_sum += weight
        for name, amount in (("with", r["stockpile"] + added), ("without", r["stockpile"])):
            gap = math.log(target_price(r["supply"] - net, r["demand"] - net, amount) / row.settled_price)
            misses[name][0] += abs(gap) * weight
            misses[name][1] += gap * weight
    return {
        "typical_miss": 100 * (math.exp(misses["with"][0] / weight_sum) - 1),
        "mean_miss": 100 * (math.exp(misses["with"][1] / weight_sum) - 1),
        "typical_miss_without": 100 * (math.exp(misses["without"][0] / weight_sum) - 1),
        "mean_miss_without": 100 * (math.exp(misses["without"][1] / weight_sum) - 1),
    }
