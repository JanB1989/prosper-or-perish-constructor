"""Check the start-food model against a saved campaign (``ppc worldbuilder food-check``).

Reads the parquet export of a save (``artifacts/data/savegame``) plus the province food block of the save file itself,
and reports, per province-and-owner group, the engine's consumption and production next to the model's formula
evaluated on the engine's own pops and buildings. Food decay is ignored on purpose: the engine's structural change
(production minus consumption) is the reference, the starting stock is deliberately generous.

It also refits the engine's setup promotion and RGO hiring by rank, so ``[worldbuilder.start]`` can be updated from
any fresh save without touching code.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any

import polars as pl

from . import start_placement as sp

REPORT_RELATIVE_PATH = Path("artifacts/data/worldbuilder/food_check")
EXPORT_RELATIVE_PATH = Path("artifacts/data/savegame")
POP_TYPES = ("nobles", "clergy", "burghers", "laborers", "soldiers", "peasants", "slaves", "tribesmen")
PROMOTED_TYPES = ("nobles", "clergy", "burghers", "laborers", "soldiers")
RANKS = ("rural_settlement", "town", "city", "megalopolis")


def parse_provinces(path: Path) -> pl.DataFrame:
    """The ``provinces = { database = { id = { ... } } }`` block of a text save as one row per province."""
    rows: list[dict[str, Any]] = []
    in_db, depth, section, prev = False, 0, None, ""
    cur: dict[str, Any] | None = None
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            s = line.strip()
            if not in_db:
                if s == "database={" and prev == "provinces={":
                    in_db = True
                prev = s
                continue
            if depth == 0:
                m = re.match(r"^(\d+)=\{$", s)
                if m:
                    cur, depth = {"province_id": int(m.group(1))}, 1
                elif s == "}":
                    break
                continue
            if s.endswith("={"):
                depth += 1
                section = s[:-2]
                continue
            if s == "}":
                depth -= 1
                if depth == 1:
                    section = None
                elif depth == 0 and cur is not None:
                    rows.append(cur)
                    cur = None
                continue
            if "=" in s and cur is not None:
                key, value = s.split("=", 1)
                value = value.strip().strip('"')
                if depth == 1:
                    cur[key.strip()] = value
                elif section == "food":
                    cur["food_" + key.strip()] = value

    frame = pl.DataFrame(rows, infer_schema_length=None) if rows else pl.DataFrame({"province_id": []})
    wanted = ["base_food_consumption", "cached_structural_food_change", "cached_food_change", "food_current", "max_food_value", "wanted"]
    for name in wanted:
        if name not in frame.columns:
            frame = frame.with_columns(pl.lit(None, dtype=pl.Utf8).alias(name))
    if "owner" not in frame.columns:
        frame = frame.with_columns(pl.lit(None, dtype=pl.Utf8).alias("owner"))
    if "province_definition" not in frame.columns:
        frame = frame.with_columns(pl.lit(None, dtype=pl.Utf8).alias("province_definition"))
    return frame.select(
        pl.col("province_id").cast(pl.Int64, strict=False),
        pl.col("province_definition").cast(pl.Utf8),
        pl.col("owner").cast(pl.Int64, strict=False).alias("owner_country_id"),
        *[pl.col(name).cast(pl.Float64, strict=False) for name in wanted],
    )


def _pop_frame(pops: dict[str, list[sp.Pop]], prefix: str) -> pl.DataFrame:
    rows = []
    for tag, group in pops.items():
        c: Counter = Counter()
        for p in group:
            c[p.type] += p.size_k
        rows.append({"slug": tag, **{f"{prefix}{t}": float(c.get(t, 0.0)) for t in POP_TYPES}})
    return pl.DataFrame(rows)


def run(repo: Path, project: Path, mod_root: Path) -> dict[str, Any]:
    from .contract import load_config, load_contract
    from .stage import vanilla_root as vanilla_root_of
    from .start_rules import Rules

    export = repo / EXPORT_RELATIVE_PATH
    meta = pl.read_parquet(export / "save_metadata.parquet")
    save_path = Path(str(meta["path"][0]))
    provinces = parse_provinces(save_path).filter(pl.col("owner_country_id").is_not_null())
    locations = pl.read_parquet(export / "locations.parquet").filter(pl.col("owner_country_id").is_not_null())
    buildings = pl.read_parquet(export / "buildings.parquet")
    countries = pl.read_parquet(export / "countries.parquet").select("country_id", "country_tag")
    vanilla = vanilla_root_of(repo, project)
    cfg = load_config(repo, project)
    start = sp.StartConfig.from_raw(cfg.raw.get("start") if isinstance(cfg.raw.get("start"), dict) else None)
    rules = Rules(repo, project)
    food = sp.load_pop_food_consumption(vanilla, mod_root)
    attrs = {r["location_tag"]: r for r in load_contract(cfg.handover).location_attributes.iter_rows(named=True)}
    subsistence_types = cfg.raw.get("start", {}).get("subsistence_pop_types", ["peasants", "laborers", "slaves"])

    # --- the model's formula on the engine's own pops and buildings -------------------------------------------
    numbers: dict[str, dict[str, float]] = {}

    def num(key: str) -> dict[str, float]:
        if key not in numbers:
            numbers[key] = rules.numbers(key) if key in rules.buildings else {"employment_size": 0.0, "pop_type": "", "local_monthly_food": 0.0}
        return numbers[key]

    from .start_simulation import province_food_per_level

    province_food = province_food_per_level(rules, start.province_food)   # Province Food: not scaled by the modifier
    bfood: Counter = Counter()
    pfood: Counter = Counter()
    for row in buildings.iter_rows(named=True):
        key = str(row["building_type"])
        n = num(key)
        if (n["local_monthly_food"] or province_food.get(key)) and n["employment_size"] > 0:
            levels = min(float(row["employed"] or 0.0) / n["employment_size"], float(row["level"] or 0.0))
            bfood[int(row["location_id"])] += levels * n["local_monthly_food"]
            pfood[int(row["location_id"])] += levels * province_food.get(key, 0.0)
    mults = {}
    for row in locations.select("location_id", "slug", "rank").iter_rows(named=True):
        a = attrs.get(row["slug"], {})
        mults[row["location_id"]] = max(0.0, 1.0 + rules.food_modifier(row["rank"] or "rural_settlement", {k: a.get(k) for k in ("climate", "vegetation", "topography")}))
    frame = locations.with_columns(
        pl.col("location_id").replace_strict(bfood, default=0.0, return_dtype=pl.Float64).alias("building_food"),
        pl.col("location_id").replace_strict(pfood, default=0.0, return_dtype=pl.Float64).alias("province_food"),
        pl.col("location_id").replace_strict(mults, default=1.0, return_dtype=pl.Float64).alias("food_mult"),
        sum(pl.col(f"population_{t}").fill_null(0.0) * float(food.get(t, 0.0)) for t in POP_TYPES).alias("demand_formula"),
        sum(pl.col(f"unemployed_{t}").fill_null(0.0) for t in subsistence_types).alias("subsistence_pops_k"),
    ).with_columns(
        ((pl.col("subsistence_pops_k") * rules.subsistence + pl.col("building_food")) * pl.col("food_mult") + pl.col("province_food")).alias("supply_formula"),
    )
    groups = frame.group_by(["province_slug", "owner_country_id"]).agg(
        pl.col("region").first(),
        pl.col("total_population").sum().alias("pop_k"),
        pl.col("demand_formula").sum(),
        pl.col("supply_formula").sum(),
        pl.col("subsistence_pops_k").sum(),
        pl.col("building_food").sum(),
    )
    joined = groups.join(
        provinces.rename({"province_definition": "province_slug"}),
        on=["province_slug", "owner_country_id"],
        how="inner",
    ).drop_nulls(["base_food_consumption", "cached_structural_food_change"]).with_columns(
        (pl.col("base_food_consumption") + pl.col("cached_structural_food_change")).alias("engine_production"),
    ).join(countries.rename({"country_id": "owner_country_id", "country_tag": "owner"}), on="owner_country_id", how="left")

    def r2(actual: pl.Series, predicted: pl.Series) -> float | None:
        ss = float(((actual - actual.mean()) ** 2).sum())
        return round(1.0 - float(((actual - predicted) ** 2).sum()) / ss, 4) if ss else None

    # --- the last build's budget for the same groups -------------------------------------------------------
    budget_path = repo / "artifacts/data/worldbuilder/food_simulation/provinces.csv"
    model_short = None
    if budget_path.is_file():
        budget = pl.read_csv(budget_path).select(pl.col("owner"), pl.col("province").alias("province_slug"), pl.col("demand").alias("model_demand"), pl.col("supply").alias("model_supply"))
        joined = joined.join(budget, on=["owner", "province_slug"], how="left")
        both = joined.drop_nulls(["model_demand"])
        engine_short = both["engine_production"] < both["base_food_consumption"]
        model_short_flag = both["model_supply"] < both["model_demand"]
        model_short = {
            "groups_compared": both.height,
            "engine_short": int(engine_short.sum()),
            "model_short": int(model_short_flag.sum()),
            "both_short": int((engine_short & model_short_flag).sum()),
            "engine_short_model_fed": int((engine_short & ~model_short_flag).sum()),
            "model_demand": round(float(both["model_demand"].sum())),
            "model_supply": round(float(both["model_supply"].sum())),
            "r2_demand": r2(both["base_food_consumption"], both["model_demand"]),
            "r2_production": r2(both["engine_production"], both["model_supply"]),
        }

    # --- refit the engine's start state ----------------------------------------------------------------------
    vanilla_pops = _pop_frame(sp.load_pops(vanilla), "v_")
    with_vanilla = locations.join(vanilla_pops, on="slug", how="left")
    by_rank = with_vanilla.group_by("rank").agg(
        pl.len().alias("locations"),
        pl.col("total_population").sum().alias("pop_k"),
        *[(pl.col(f"population_{t}") - pl.col(f"v_{t}").fill_null(0.0)).sum().alias(f"d_{t}") for t in PROMOTED_TYPES],
        pl.col("max_raw_material_workers").mean().alias("rgo_k"),
    )
    promotion = {}
    rgo = {}
    linear: dict[str, dict[str, list[float]]] = {}
    import numpy as np

    fit_rows = with_vanilla.drop_nulls(["total_population", "development"])
    for rank in RANKS:
        part = fit_rows.filter(pl.col("rank") == rank)
        if part.height < 3:
            continue
        x = np.column_stack([np.ones(part.height), part["total_population"].to_numpy(), part["development"].to_numpy()])
        for t in PROMOTED_TYPES:
            y = (part[f"population_{t}"].fill_null(0.0) - part[f"v_{t}"].fill_null(0.0)).to_numpy()
            coef, *_ = np.linalg.lstsq(x, y, rcond=None)
            linear.setdefault(rank, {})[t] = [round(float(c), 4) for c in coef]
    for row in by_rank.iter_rows(named=True):
        rank = str(row["rank"])
        if rank not in RANKS or not row["pop_k"]:
            continue
        promotion[rank] = {t: round(max(0.0, row[f"d_{t}"] / row["pop_k"] * 1000), 1) for t in PROMOTED_TYPES}
        rgo[rank] = round(float(row["rgo_k"] or 0.0), 1)

    # --- victuals per building level as the market shows them ----------------------------------------------
    victuals = {}
    goods_path = export / "market_goods.parquet"
    if goods_path.is_file():
        import numpy as np

        market_goods = pl.read_parquet(goods_path).filter(pl.col("good_id") == "victuals")
        producers = list(start.victuals["producers"])
        consumers = [k for k in start.victuals["consumers"]]
        per_market = buildings.filter(pl.col("building_type").is_in(producers + consumers)).group_by(["market_id", "building_type"]).agg(pl.col("level").sum())
        levels = per_market.pivot("building_type", index="market_id", values="level").fill_null(0)
        joined_v = market_goods.join(levels, on="market_id", how="left").fill_null(0)
        for key in producers + consumers:
            if key not in joined_v.columns:
                joined_v = joined_v.with_columns(pl.lit(0.0).alias(key))

        def fit(target, keys):
            x = np.column_stack([joined_v[k].to_numpy().astype(float) for k in keys])
            y = joined_v[target].fill_null(0.0).to_numpy().astype(float)
            if not len(y) or not x.any():
                return {}
            coef, *_ = np.linalg.lstsq(x, y, rcond=None)
            return {k: round(float(c), 3) for k, c in zip(keys, coef)}

        pop_nominal = sum(float(locations[f"population_{t}"].fill_null(0.0).sum()) * f for t, f in rules.victuals_pop_factors().items() if f"population_{t}" in locations.columns)
        pop_observed = float(market_goods["demanded_Pops"].fill_null(0.0).sum())
        victuals = {
            "note": "least squares per market on building levels; paste into [worldbuilder.start.victuals] when they drift",
            "supply": round(float(market_goods["supply"].fill_null(0.0).sum())),
            "demand": round(float(market_goods["demand"].fill_null(0.0).sum())),
            "price_median": round(float(market_goods["price"].median() or 0.0), 2),
            "producers_per_level": fit("supplied_Production", producers),
            "consumers_per_level": fit("demanded_Building", consumers),
            "pop_demand_scale": round(pop_observed / pop_nominal, 3) if pop_nominal else None,
            "configured": start.victuals,
        }

    v2 = model_v2_on_engine_state(repo, rules, cfg, locations, buildings, joined, attrs)
    if "pools" in v2:
        joined = joined.join(v2.pop("pools"), on=["province_slug", "owner_country_id"], how="left")

    out = repo / REPORT_RELATIVE_PATH
    out.mkdir(parents=True, exist_ok=True)
    joined.sort("cached_structural_food_change").write_csv(out / "groups.csv")
    short = joined.filter(pl.col("engine_production") < pl.col("base_food_consumption"))
    summary = {
        "save": str(save_path),
        "date": str(meta["date"][0]),
        "groups": joined.height,
        "engine": {
            "consumption": round(float(joined["base_food_consumption"].sum())),
            "production": round(float(joined["engine_production"].sum())),
            "groups_short": short.height,
            "food_missing": round(float((short["base_food_consumption"] - short["engine_production"]).sum())),
        },
        "formula_on_engine_state": {
            "note": "model formula evaluated on the save's own pops and buildings; decay ignored",
            "demand": round(float(joined["demand_formula"].sum())),
            "supply": round(float(joined["supply_formula"].sum())),
            "r2_consumption": r2(joined["base_food_consumption"], joined["demand_formula"]),
            "r2_production": r2(joined["engine_production"], joined["supply_formula"]),
            "subsistence_define": rules.subsistence,
        },
        "last_build_budget": model_short,
        "model_v2": v2,
        "engine_promotion_per_1000_pops": promotion,
        "engine_promotion_linear": {"note": "k promoted per location = const + per 1,000 pops x pop k + per development point x development; paste into [worldbuilder.start.engine_promotion_linear]", **linear},
        "rgo_workers_k": rgo,
        "victuals": victuals,
        "configured": {"engine_promotion": start.engine_promotion, "rgo_workers_k": start.rgo_workers_k},
        "report": str(out / "groups.csv"),
    }
    (out / "summary.json").write_text(__import__("json").dumps(summary, indent=2, default=str) + "\n", encoding="utf-8")
    return summary


def model_v2_on_engine_state(repo: Path, rules, cfg, locations: pl.DataFrame, buildings: pl.DataFrame, joined: pl.DataFrame, attrs: dict) -> dict[str, Any]:
    """Food model v2 (``start_food_model_v2``) evaluated on the save's own pops, jobless workers, staffed levels and
    running methods, the yields refitted per rank and climate, and the last build's day-0 budget against the engine.

    Location capacity (for the overpopulation term) is the last build's ``start_placement.csv``: the save must come
    from that build."""
    import numpy as np

    from . import start_food_model_v2 as fm
    from .contract import load_contract
    from .modifiers import setup_modifier_keys
    from .start_simulation import method_output

    model = fm.FoodModelConfig.from_raw((cfg.raw.get("start") or {}).get("food_model"))
    table = repo / sp.TABLE_RELATIVE_PATH
    if not table.is_file():
        return {"skipped": f"no {sp.TABLE_RELATIVE_PATH}: run ppc worldbuilder apply first"}
    capacity = {r["location_tag"]: float(r["capacity_people"] or 0.0) / 1000.0 for r in pl.read_csv(table).iter_rows(named=True)}
    static_keys = setup_modifier_keys(load_contract(cfg.handover))
    # building food of the staffed levels by the methods that actually run
    cache: dict[tuple[str, str], float] = {}
    numbers: dict[str, dict[str, Any] | None] = {}
    flat: Counter = Counter()
    province_food: Counter = Counter()
    for row in buildings.iter_rows(named=True):
        key = str(row["building_type"])
        if key not in numbers:
            numbers[key] = rules.numbers(key) if key in rules.buildings else None
        n = numbers[key]
        if not n or n["employment_size"] <= 0:
            continue
        levels = min(float(row["employed"] or 0.0) / n["employment_size"], float(row["level"] or 0.0))
        lid = int(row["location_id"])
        flat[lid] += levels * float(n["local_monthly_food"] or 0.0)
        for method in row["active_method_ids"] or []:
            if (key, method) not in cache:
                cache[key, method] = method_output(rules.buildings.get(key), str(method))
            province_food[lid] += levels * cache[key, method]
    keys = ["province_slug", "owner_country_id"]
    pools = joined.select(*keys, "base_food_consumption", "engine_production")
    index = {k: i for i, k in enumerate(pools.select(keys).iter_rows())}
    pool_index, jobless, stack, ranks, climates, overpop, fixed = [], [], [], [], [], [], []
    for r in locations.iter_rows(named=True):
        slot = index.get((r["province_slug"], r["owner_country_id"]))
        if slot is None:
            continue
        tag = str(r["slug"])
        a = attrs.get(tag, {})
        rank = str(r["rank"] or "rural_settlement")
        river = int(a.get("river_level") or 0)
        keys_here = list(static_keys.get(tag, ())) + ([f"river_flowing_through_{river}"] if river else [])
        s = fm.static_food_modifier(rules, rank, {k: a.get(k) for k in ("climate", "vegetation", "topography")}, keys_here)
        pool_index.append(slot)
        jobless.append(sum(float(r.get(f"unemployed_{t}") or 0.0) for t in model.subsistence_pop_types))
        stack.append(s)
        ranks.append(rank)
        climates.append(str(a.get("climate") or "none"))
        pop = float(r["total_population"] or 0.0)
        peasants = sum(float(r.get(f"population_{t}") or 0.0) for t in model.overpopulation_pop_types)
        overpop.append(fm.overpopulation_food(peasants, pop, capacity.get(tag, pop), model))
        lid = int(r["location_id"])
        fixed.append(flat[lid] * max(0.0, 1.0 + s) + province_food[lid])
    idx = np.array(pool_index, dtype=int)
    n = pools.height
    production = pools["engine_production"].to_numpy().astype(float)
    fixed_pool = np.bincount(idx, np.array(fixed), n)
    overpop_pool = np.bincount(idx, np.array(overpop), n)
    fit = fm.fit_yields(idx, np.array(jobless), np.array(stack), ranks, climates, overpop_pool, fixed_pool, production,
                        define=rules.subsistence, overpopulation_consumption=model.overpopulation_consumption)
    # the configured model (not the refit) on the engine state
    y = np.array([fm.location_yield(rules.subsistence, s, r, c, model) for s, r, c in zip(stack, ranks, climates)])
    subsistence = np.bincount(idx, y * np.array(jobless), n)
    predicted = subsistence + fixed_pool - overpop_pool
    frame = pools.select(keys).with_columns(
        pl.Series("v2_subsistence", subsistence),
        pl.Series("v2_building_food", fixed_pool),
        pl.Series("v2_overpopulation", overpop_pool),
        pl.Series("v2_production", predicted),
    )
    result: dict[str, Any] = {
        "note": "production = base_food_consumption + cached_structural_food_change; model = subsistence (jobless peasants and "
                "slaves x yield) + building food of the running methods - overpopulation consumption",
        "configured": {"r2_production": fm.r2(production, predicted), "aggregate_model": round(float(predicted.sum())),
                       "aggregate_engine": round(float(production.sum())),
                       "aggregate_error": round(float(predicted.sum() / production.sum() - 1.0), 4) if production.sum() else None,
                       "subsistence": round(float(subsistence.sum())), "building_food": round(float(fixed_pool.sum())),
                       "overpopulation": round(float(overpop_pool.sum()))},
        "refit": {**fit, "note": "paste yield_rank and yield_climate into [worldbuilder.start.food_model] when they drift"},
        "pools": frame,
    }
    # the last build's plan against the engine at day 0 (no farm on Provisioning, no cookery on Serve yet)
    budget_path = repo / "artifacts/data/worldbuilder/food_simulation/provinces.csv"
    if budget_path.is_file():
        budget = pl.read_csv(budget_path)
        if "day0_production" in budget.columns:
            plan = joined.select("owner", "province_slug", "engine_production", "base_food_consumption").join(
                budget.select(pl.col("owner"), pl.col("province").alias("province_slug"), "day0_production", "demand_base"),
                on=["owner", "province_slug"], how="inner")
            if plan.height:
                result["last_build_day0"] = {
                    "note": "the last build's plan with day-0 methods (no Provisioning, no Serve) against the engine",
                    "groups_compared": plan.height,
                    "r2_production": fm.r2(plan["engine_production"].to_numpy(), plan["day0_production"].to_numpy()),
                    "aggregate_model": round(float(plan["day0_production"].sum())),
                    "aggregate_engine": round(float(plan["engine_production"].sum())),
                    "aggregate_error": round(float(plan["day0_production"].sum() / plan["engine_production"].sum() - 1.0), 4),
                    "r2_demand": fm.r2(plan["base_food_consumption"].to_numpy(), plan["demand_base"].to_numpy()),
                    "engine_short": int((plan["engine_production"] < plan["base_food_consumption"]).sum()),
                    "model_short": int((plan["day0_production"] < plan["demand_base"]).sum()),
                }
    return result
