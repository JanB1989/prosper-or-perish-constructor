"""Market membership from one save (docs/market_rulebook.md): rule inputs, access to every market, predicted market.

The save needs the `pp_mk.txt` dump (copy to Documents/.../run/, `run pp_mk.txt` in the console, then save): centre
power, protection and local market access come from its location variables. Everything else is in the save.

usage (from the constructor root):
  uv run python tools/markets/save_inputs.py --build-cache            # map graph cache, after a map change
  uv run python tools/markets/save_inputs.py SAVE [--pure] [--truth LATER_SAVE] [--csv OUT]
      fit of the attraction toward the current market, fit of the access model, and the predicted market of every
      location (argmax) against SAVE itself or against LATER_SAVE (e.g. the save after the next tick).
"""

from __future__ import annotations

import argparse
import sys
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path

import polars as pl

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
from prosper_or_perish_constructor.worldbuilder import market_access as ma  # noqa: E402
from prosper_or_perish_constructor.worldbuilder import markets as mk  # noqa: E402
from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root  # noqa: E402

PROJECT = REPO / "constructor.toml"


def mod_root() -> Path:
    configured = Path(tomllib.loads(PROJECT.read_text(encoding="utf-8"))["project"]["mod_root"])
    return configured if configured.is_absolute() else REPO / configured


def map_dirs() -> tuple[Path, Path]:
    return mod_root() / "in_game" / "map_data", vanilla_root(REPO, PROJECT) / "game" / "in_game" / "map_data"


@dataclass
class SaveInputs:
    date: str
    locations: pl.DataFrame              # eu5save locations + model inputs
    markets_table: pl.DataFrame          # market_id, center_location_id, language
    roads: pl.DataFrame
    lma: pl.DataFrame                    # location_id, lma_live, acc_live
    places: dict[str, mk.Place]
    markets: dict[str, mk.Market]
    market_key: dict[int, str]
    family: dict[str, str | None]


def truth(save: Path) -> pl.DataFrame:
    """Markets of a save without the dump: slug, country_tag, market (centre slug), market_access, total_population."""
    from eu5gameparser.savegame.engine import EngineContext

    work = Path(tempfile.mkdtemp(prefix="pp_markets_"))
    ctx = EngineContext.load(profile="constructor", load_order_path=REPO / "constructor.load_order.toml", work_dir=work)
    tables = ctx.assemble(ctx.extract([save], work / "out", jobs=1)[0])
    slug = dict(tables.locations.select("location_id", "slug").iter_rows())
    key = {m: slug.get(c) for m, c in tables.markets.select("market_id", "center_location_id").iter_rows()}
    return tables.locations.with_columns(
        pl.col("market_id").replace_strict(key, default=None, return_dtype=pl.String).alias("market"))


def read(save: Path, *, work: Path | None = None) -> SaveInputs:
    from eu5gameparser.savegame.engine import EngineContext

    work = work or Path(tempfile.mkdtemp(prefix="pp_markets_"))
    ctx = EngineContext.load(profile="constructor", load_order_path=REPO / "constructor.load_order.toml", work_dir=work)
    result = ctx.extract([save], work / "out", jobs=1)[0]
    tables = ctx.assemble(result)
    out = result.out
    family, parent = mk.languages(vanilla_root(REPO, PROJECT))

    variables = pl.read_parquet(out / "location_variables.parquet").filter(pl.col("name").str.starts_with("pp_mk_"))
    if variables.is_empty():
        raise SystemExit(f"{save.name}: no pp_mk_* variables; run tools/markets/pp_mk.txt in the console before saving")
    variables = variables.pivot(index="location_id", on="name", values="value", aggregate_function="first")
    power = dict(pl.read_parquet(out / "languages.parquet").iter_rows())
    culture_language = {cid: parent.get(lang, lang) for cid, _, lang in pl.read_parquet(out / "cultures.parquet").iter_rows()}
    countries = pl.read_parquet(out / "countries_raw.parquet").select("country_id", "tag", "primary_culture")
    tag = dict(countries.select("country_id", "tag").iter_rows())
    common = {tag[c]: culture_language.get(int(p)) for c, _, p in countries.iter_rows() if p is not None}
    overlords: dict[str, set[str]] = {}
    for subject, overlord in pl.read_parquet(out / "subjects_raw.parquet").select("subject_id", "overlord_country_id").iter_rows():
        if subject in tag and overlord in tag:
            overlords.setdefault(tag[subject], set()).add(tag[overlord])

    loc = tables.locations.join(variables, on="location_id", how="left").with_columns(
        (pl.col("pp_mk_ltpf").fill_null(0.0) + pl.col("pp_mk_gtpf").fill_null(0.0)).alias("protection"),
        (pl.col("pp_mk_ltcp").fill_null(0.0) + pl.col("pp_mk_gtcp").fill_null(0.0)).alias("center_power"))
    by_id = {r["location_id"]: r for r in loc.iter_rows(named=True)}
    markets: dict[str, mk.Market] = {}
    market_key: dict[int, str] = {}
    for row in tables.markets.iter_rows(named=True):
        center = by_id.get(row["center_location_id"])
        if center is None:
            continue
        key = center["slug"]
        market_key[row["market_id"]] = key
        markets[key] = mk.Market(key, key, center["country_tag"], float(center["center_power"] or 0.0),
                                 row.get("language"), float(power.get(row.get("language"), 0.0) or 0.0),
                                 center["province_slug"], center["area"])
    places: dict[str, mk.Place] = {}
    for r in loc.iter_rows(named=True):
        owner = r["country_tag"]
        places[r["slug"]] = mk.Place(
            r["slug"], owner, r["province_slug"], r["area"], r.get("language"), common.get(owner) if owner else None,
            protection=float(r["protection"] or 0.0), overlords=frozenset(overlords.get(owner, ())) if owner else frozenset(),
            market=market_key.get(r["market_id"]))
    loc = loc.with_columns(
        pl.col("market_id").replace_strict(market_key, default=None, return_dtype=pl.String).alias("market"),
        pl.col("second_best_market_id").replace_strict(market_key, default=None, return_dtype=pl.String).alias("best_access_market"))
    lma = loc.select("location_id", pl.col("pp_mk_lma").alias("lma_live"), pl.col("pp_mk_acc").alias("acc_live"))
    return SaveInputs(str(result.date), loc, tables.markets.select("market_id", "center_location_id", "language"),
                      pl.read_parquet(out / "roads.parquet"), lma, places, markets, market_key, family)


def access(inputs: SaveInputs, *, calibrated: bool = True, field: bool = False) -> pl.DataFrame:
    map_dir, vanilla_map = map_dirs()
    cache = REPO / ma.CACHE
    if not (cache / "positions.parquet").exists():
        ma.build_map_cache(map_dir, vanilla_map, cache)
    cols = ["location_id", "slug", "owner", "market_id", "market_access", "second_best_market_id",
            "second_best_market_access", "market_parent"]
    return ma.access_matrix(inputs.locations.select(cols), inputs.markets_table, inputs.roads, inputs.lma, map_dir=map_dir,
                            vanilla_root=vanilla_root(REPO, PROJECT), mod_root=mod_root(), cache=cache,
                            calibrated=calibrated, field=field)


def predict(inputs: SaveInputs, acc: pl.DataFrame) -> dict[str, tuple[str, float, float]]:
    """location slug -> (predicted market, its attraction, the runner-up's attraction)."""
    slug = dict(inputs.locations.select("location_id", "slug").iter_rows())
    table: dict[str, dict[str, float]] = {}
    for lid, mid, a in acc.iter_rows():
        key = inputs.market_key.get(mid)
        if key is not None:
            table.setdefault(slug[lid], {})[key] = a
    out = {}
    for name, row in table.items():
        place = inputs.places[name]
        scores = sorted(((mk.attraction(place, inputs.markets[m], a, inputs.family), m) for m, a in row.items()), reverse=True)
        out[name] = (scores[0][1], scores[0][0], scores[1][0] if len(scores) > 1 else float("-inf"))
    return out


def current_fit(inputs: SaveInputs) -> pl.DataFrame:
    """Model attraction toward each location's current market (saved access) against the saved attraction."""
    rows = []
    for r in inputs.locations.iter_rows(named=True):
        market = inputs.markets.get(r["market"]) if r["market"] else None
        if market is None or r["market_access"] is None or r["market_attraction"] is None:
            continue
        model = mk.attraction(inputs.places[r["slug"]], market, r["market_access"], inputs.family)
        rows.append({"slug": r["slug"], "market": r["market"], "saved": r["market_attraction"], "model": model})
    return pl.DataFrame(rows).with_columns((pl.col("saved") - pl.col("model")).alias("error"))


def _share(x: pl.DataFrame, cond: pl.Expr) -> str:
    return f"{x.filter(cond).height / max(1, x.height):.1%}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("save", type=Path, nargs="?")
    ap.add_argument("--build-cache", action="store_true", help="rebuild the map graph cache (after a map change)")
    ap.add_argument("--pure", action="store_true", help="access from the rules only (no calibration on the save)")
    ap.add_argument("--truth", type=Path, help="compare the prediction with the markets of this (later) save")
    ap.add_argument("--csv", type=Path, help="write location, market, predicted market, attraction, runner-up")
    ap.add_argument("--pool-markets", type=Path, help="write the predicted market per owner/province pool (population "
                    "majority) for the food-sim switch market_assignment, e.g. config/start_markets.csv")
    args = ap.parse_args()
    if args.build_cache:
        map_dir, vanilla_map = map_dirs()
        print(ma.build_map_cache(map_dir, vanilla_map, REPO / ma.CACHE))
        if args.save is None:
            return
    inputs = read(args.save)
    fit = current_fit(inputs)
    err = pl.col("error").abs()
    print(f"{args.save.name} {inputs.date}: {len(inputs.markets)} markets; attraction toward the current market, model vs "
          f"save within 0.001 / 0.005 / 0.02: {_share(fit, err < 0.001)} / {_share(fit, err < 0.005)} / {_share(fit, err < 0.02)}")
    acc = access(inputs, calibrated=not args.pure, field=True)
    check = (inputs.locations.select("location_id", "market_id", "market_access").drop_nulls()
             .join(acc, on=["location_id", "market_id"], how="left").with_columns((pl.col("access").fill_null(0) - pl.col("market_access")).abs().alias("e")))
    print(f"access ({'rules only' if args.pure else 'calibrated'}) vs saved access to the current market within 0.005 / 0.05: "
          f"{_share(check, pl.col('e') < 0.005)} / {_share(check, pl.col('e') < 0.05)}")
    pred = predict(inputs, access(inputs, calibrated=not args.pure))   # live local_market_access: the next tick's

    truth_rows = truth(args.truth) if args.truth else inputs.locations
    rows = [(r["slug"], r["country_tag"], r["market"], *pred.get(r["slug"], (None, None, None)), r["total_population"])
            for r in truth_rows.iter_rows(named=True) if r["market"] and r["market_access"]]
    res = pl.DataFrame(rows, schema=["slug", "owner", "market", "predicted", "attraction", "runner_up", "population"], orient="row")
    hit = pl.col("predicted") == pl.col("market")
    owned = res.filter(pl.col("owner").is_not_null())
    people = res.filter(hit)["population"].fill_null(0).sum() / max(1e-9, res["population"].fill_null(0).sum())
    print(f"predicted market = {'the later save' if args.truth else 'the save'}: {_share(res, hit)} of {res.height} locations "
          f"with access, {_share(owned, hit)} of owned, {people:.1%} of people; misses within 0.01 of the runner-up: "
          f"{res.filter(~hit & ((pl.col('attraction') - pl.col('runner_up')) < 0.01)).height} of {res.filter(~hit).height}")
    if args.csv:
        res.write_csv(args.csv)
    if args.pool_markets:
        choice = {k: v[0] for k, v in pred.items()}
        pools = (inputs.locations.filter(pl.col("country_tag").is_not_null())
                 .select("slug", pl.col("country_tag").alias("owner"), pl.col("province_slug").alias("province"),
                         pl.col("total_population").fill_null(0.0).alias("population"))
                 .with_columns(pl.col("slug").replace_strict(choice, default=None, return_dtype=pl.String).alias("market"))
                 .drop_nulls("market").group_by("owner", "province", "market")
                 .agg(pl.col("population").sum(), pl.len().alias("locations"))
                 .sort(["owner", "province", "population", "locations"], descending=[False, False, True, True])
                 .unique(["owner", "province"], keep="first", maintain_order=True).select("owner", "province", "market"))
        header = (f"# Market of every owner/province pool after the first monthly tick, predicted by the engine rule "
                  f"(docs/market_rulebook.md) from {args.save.name} ({inputs.date}, with the pp_mk dump): the population\n"
                  f"# majority of its locations. Read by the food sim with market_assignment = true. Refresh from a new "
                  f"start save: uv run python tools/markets/save_inputs.py SAVE --pool-markets config/start_markets.csv\n")
        args.pool_markets.write_text(header + pools.write_csv(), encoding="utf-8")
        print(f"{pools.height} pools -> {args.pool_markets}")


if __name__ == "__main__":
    main()
