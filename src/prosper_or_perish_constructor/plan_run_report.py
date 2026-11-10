"""Unattended Construction Plan runs: the plan run against a control run, for one country (`ppc plan-run-report`).

A plan run is a played country whose buildings only the Construction Plan builds (everything else on the game's own
automation, pp_testing README "Unattended plan runs"); the control run is the same start with the normal AI building
for that country (an observer game), or the same played country with the game's Buildings automation. Both are series
of yearly saves. The report compares them save by save for the one country: building levels by kind and what stands
closed or under-staffed, treasury, income, tax base and population, stored food per province, market access, what
the plan started per rule group and what its groups spent and saved for, prices and stock of the goods whose producers
the plan built, whether the game ran without a stop, and a verdict table at the last common year.

Saves are read the way `ppc plan-report` reads them (plan_test_report.load_snapshot, the Rust engine's tables); this
module only adds the comparison. Inputs beside the saves:
- debug.log of the plan run: the plan's test lines (plan_test_report.parse_debug_log), the dump lines of
  `run pp_run_dump.txt` (what a group saves for: `PPRUN;D;begin`, `PPRUN;S;<why>` + the building type's scope line,
  `PPRUN;L;<why>` + the location's, `PPRUN;D;end`) and the console command lines (they explain a stop);
- run.log of pp_run_loop.ps1: its `PAUSE <n> at game date <date>` lines are the pauses the test layer did not prevent.

Not in the save tables (2026-11-10): a location's unsupported building levels (the market access section says so and
gives building levels per location instead), scope-valued variables (what a group saves for comes from the dump
lines), a building's workers per level (under-staffed is judged against the fullest level of its type in the saves).
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import polars as pl

from prosper_or_perish_constructor import plan_test_report as ptr

PLAN, CONTROL = "plan", "control"
PAIR_YEARS = 0.26          # saves of the two runs this close in game time are the same check-in
UNDERSTAFFED = 0.9         # a building works below this share of its type's fullest level = under-staffed
STOP_FACTOR = 5.0          # a game month slower than this many times the median month ...
STOP_SECONDS = 20.0        # ... and slower than this many seconds is a stop
CRASH_RATIO = 0.6          # price / default price below this = the market is flooded
TOP_GOODS = 8
GROUP_NAMES = dict(ptr.WHY_CODES)                      # why code -> rule group
DUMP_RE = re.compile(r"PPRUN;([DSL]);\s*([A-Za-z0-9]+)")
CONSOLE_RE = re.compile(r"Running console command:\s*(.+?)\s*$")
RUNLOG_PAUSE_RE = re.compile(r"PAUSE (\d+) at game date (\d+\.\d+\.\d+)")
SAVE_YEAR_RE = re.compile(r"_y(\d{3,4})$")


@dataclass
class Run:
    """One series of saves and the country followed in it (by id: its tag may change, Castile becomes Spain)."""

    label: str
    snaps: list[ptr.Snapshot]
    cid: int

    def tag(self, snap: ptr.Snapshot) -> str:
        return tag_of(snap, self.cid) or "?"


def tag_of(snap: ptr.Snapshot, cid: int) -> str | None:
    countries = ptr._table(snap, "countries_raw")
    if countries is not None and "tag" in countries.columns:
        hit = countries.filter(pl.col("country_id") == cid)
        if hit.height:
            return str(hit["tag"][0])
    loc = ptr._table(snap, "locations")
    if loc is not None and "owner_country_id" in loc.columns:
        hit = loc.filter(pl.col("owner_country_id") == cid)
        if hit.height:
            return str(hit["country_tag"][0])
    return None


def plan_country_id(snaps: Sequence[ptr.Snapshot]) -> int | None:
    """The country that runs the Construction Plan: the first one with pp_cplan_on in any save."""
    for snap in snaps:
        cv = ptr._table(snap, "country_variables")
        if cv is None:
            continue
        hit = cv.filter(pl.col("name") == "pp_cplan_on")
        if hit.height:
            return int(hit["country_id"][0])
    return None


def make_runs(plan: Sequence[ptr.Snapshot], control: Sequence[ptr.Snapshot],
              country: str | None = None) -> tuple[Run, Run | None, str]:
    """The two runs with the country to follow: `country` (a tag in the plan run's first save), else the country that
    runs the plan, else the one owning most locations. The control run follows the country with the same tag in its
    own first save."""
    plan = sorted(plan, key=lambda s: s.year)
    control = sorted(control, key=lambda s: s.year)
    if not plan:
        raise SystemExit("plan-run-report needs the plan run's saves")
    if country is not None:
        cid = ptr.country_id(plan[0], country)
        if cid is None:
            raise SystemExit(f"no country {country!r} in {plan[0].name}")
    else:
        cid = plan_country_id(plan)
        if cid is None:
            cid = ptr.country_id(plan[0], ptr.main_country(plan[0]))
    tag = tag_of(plan[0], cid) or "?"
    control_run = None
    if control:
        ccid = ptr.country_id(control[0], tag)
        if ccid is None:
            raise SystemExit(f"the control run's first save {control[0].name} has no country {tag}")
        control_run = Run(CONTROL, list(control), ccid)
    return Run(PLAN, list(plan), cid), control_run, tag


def pairs(plan: Run, control: Run | None) -> list[tuple[ptr.Snapshot, ptr.Snapshot]]:
    """Saves of the two runs at the same game date (within PAIR_YEARS), in order."""
    if control is None:
        return []
    out = []
    for snap in plan.snaps:
        other = min(control.snaps, key=lambda s: abs(s.year - snap.year))
        if abs(other.year - snap.year) <= PAIR_YEARS:
            out.append((snap, other))
    return out


def _rows(runs: Sequence[Run | None]) -> Iterable[tuple[Run, ptr.Snapshot]]:
    for run in runs:
        if run is not None:
            for snap in run.snaps:
                yield run, snap


def _head(run: Run, snap: ptr.Snapshot) -> dict[str, Any]:
    return {"series": run.label, "save": snap.name, "date": snap.date, "year": snap.year}


# ---------------------------------------------------------------------------------------------------------------------
# Country: money and people
# ---------------------------------------------------------------------------------------------------------------------
def country_series(runs: Sequence[Run | None]) -> pl.DataFrame:
    """Per save: the country's locations, people (thousands), gold, income, expense, tax base, building levels."""
    rows = []
    for run, snap in _rows(runs):
        tag = run.tag(snap)
        loc = ptr._table(snap, "locations")
        mine = loc.filter(pl.col("country_tag") == tag) if loc is not None else pl.DataFrame()
        row = {**_head(run, snap), "tag": tag, "locations": mine.height,
               "population_k": float(mine["total_population"].sum()) if mine.height else None}
        ai = ptr._table(snap, "country_ai")
        ai = ai.filter(pl.col("country_id") == run.cid) if ai is not None else None
        for col in ("gold", "income", "expense", "tax_base"):
            present = ai is not None and ai.height and col in ai.columns and ai[col][0] is not None
            row[col] = float(ai[col][0]) if present else None
        row["balance"] = (row["income"] - row["expense"]
                          if row["income"] is not None and row["expense"] is not None else None)
        b = ptr._table(snap, "buildings")
        row["building_levels"] = float(b.filter(pl.col("country_tag") == tag)["level"].sum()) if b is not None else None
        rows.append(row)
    return pl.DataFrame(rows, infer_schema_length=None)


# ---------------------------------------------------------------------------------------------------------------------
# Buildings
# ---------------------------------------------------------------------------------------------------------------------
BUILDING_SCHEMA = {"building_type": pl.Utf8, "level": pl.Float64, "employed": pl.Float64, "open": pl.Boolean}


def building_rows(snap: ptr.Snapshot, tag: str) -> pl.DataFrame:
    """The country's buildings: type, level, workers employed (null = the save has none) and open (null = open)."""
    b = ptr._table(snap, "buildings")
    if b is None:
        return pl.DataFrame(schema=BUILDING_SCHEMA)
    mine = b.filter(pl.col("country_tag") == tag)
    cols = [pl.col("building_type").cast(pl.Utf8), pl.col("level").cast(pl.Float64)]
    cols.append((pl.col("employed") if "employed" in mine.columns else pl.lit(None)).cast(pl.Float64).alias("employed"))
    cols.append((pl.col("open") if "open" in mine.columns else pl.lit(None)).cast(pl.Boolean).alias("open"))
    return mine.select(cols)


def full_staffing(runs: Sequence[Run | None]) -> dict[str, float]:
    """building type -> the most workers per level seen on an open building in any save of the runs."""
    best: dict[str, float] = {}
    for run, snap in _rows(runs):
        b = building_rows(snap, run.tag(snap)).filter(
            (pl.col("level") > 0) & pl.col("employed").is_not_null() & pl.col("open").fill_null(True))
        for name, value in b.group_by("building_type").agg((pl.col("employed") / pl.col("level")).max()).iter_rows():
            if value is not None and value > best.get(name, 0.0):
                best[name] = float(value)
    return best


def staffing(runs: Sequence[Run | None], full: dict[str, float] | None = None) -> pl.DataFrame:
    """Per save: building levels, levels of closed buildings, levels of open buildings that work below UNDERSTAFFED of
    their type's fullest level, and the levels whose staffing the save does not tell."""
    full = full if full is not None else full_staffing(runs)
    rows = []
    for run, snap in _rows(runs):
        b = building_rows(snap, run.tag(snap)).with_columns(
            pl.col("building_type").replace_strict(full, default=None, return_dtype=pl.Float64).alias("full"))
        closed = b.filter(~pl.col("open").fill_null(True))
        is_open = b.filter(pl.col("open").fill_null(True))
        known = is_open.filter(pl.col("employed").is_not_null() & (pl.col("full") > 0) & (pl.col("level") > 0))
        under = known.filter(pl.col("employed") / pl.col("level") < UNDERSTAFFED * pl.col("full"))
        rows.append({**_head(run, snap), "levels": float(b["level"].sum()),
                     "closed_levels": float(closed["level"].sum()),
                     "understaffed_levels": float(under["level"].sum()),
                     "staffing_unknown_levels": float(is_open["level"].sum() - known["level"].sum())})
    return pl.DataFrame(rows, schema={"series": pl.Utf8, "save": pl.Utf8, "date": pl.Utf8, "year": pl.Float64,
                                      "levels": pl.Float64, "closed_levels": pl.Float64,
                                      "understaffed_levels": pl.Float64, "staffing_unknown_levels": pl.Float64})


def trouble_by_type(run: Run, snap: ptr.Snapshot, full: dict[str, float]) -> pl.DataFrame:
    """Per building type in one save: levels, closed levels, under-staffed levels (types with any of the two)."""
    b = building_rows(snap, run.tag(snap)).with_columns(
        pl.col("building_type").replace_strict(full, default=None, return_dtype=pl.Float64).alias("full"),
        pl.col("open").fill_null(True).alias("is_open"))
    under = (pl.col("is_open") & pl.col("employed").is_not_null() & (pl.col("full") > 0) & (pl.col("level") > 0)
             & (pl.col("employed") / pl.col("level") < UNDERSTAFFED * pl.col("full")))
    out = b.group_by("building_type").agg(
        pl.col("level").sum().alias("levels"),
        pl.col("level").filter(~pl.col("is_open")).sum().alias("closed_levels"),
        pl.col("level").filter(under).sum().alias("understaffed_levels"))
    return out.filter((pl.col("closed_levels") > 0) | (pl.col("understaffed_levels") > 0)).sort(
        ["closed_levels", "understaffed_levels", "building_type"], descending=[True, True, False])


def _kind(kinds: dict[str, str]) -> pl.Expr:
    if not kinds:
        return pl.lit("other").alias("kind")
    return pl.col("building_type").replace_strict(kinds, default="other").alias("kind")


def kind_series(runs: Sequence[Run | None], kinds: dict[str, str]) -> pl.DataFrame:
    """Building levels per save and kind (food, logistics, improve, business, other) and their total."""
    rows = []
    for run, snap in _rows(runs):
        lv = ptr.levels_by_location(snap, run.tag(snap)).with_columns(
            _kind(kinds))
        totals = dict(lv.group_by("kind").agg(pl.col("levels").sum()).iter_rows())
        rows.append({**_head(run, snap), **{k: float(totals.get(k, 0.0)) for k in ptr.KINDS},
                     "total": float(sum(totals.values()))})
    return pl.DataFrame(rows, schema={"series": pl.Utf8, "save": pl.Utf8, "date": pl.Utf8, "year": pl.Float64,
                                      **{k: pl.Float64 for k in ptr.KINDS}, "total": pl.Float64})


def kind_difference(levels: pl.DataFrame, plan: Run, control: Run | None) -> pl.DataFrame:
    """Plan minus control per kind at every common check-in."""
    rows = []
    by_save = {(r["series"], r["save"]): r for r in levels.iter_rows(named=True)}
    for a, b in pairs(plan, control):
        pa, cb = by_save[(PLAN, a.name)], by_save[(CONTROL, b.name)]
        rows.append({"date": a.date, "year": a.year, **{k: pa[k] - cb[k] for k in ptr.KINDS},
                     "total": pa["total"] - cb["total"]})
    return pl.DataFrame(rows, schema={"date": pl.Utf8, "year": pl.Float64, **{k: pl.Float64 for k in ptr.KINDS},
                                      "total": pl.Float64})


def _type_levels(snap: ptr.Snapshot, tag: str) -> pl.DataFrame:
    return ptr.levels_by_location(snap, tag).group_by("building_type").agg(pl.col("levels").sum())


def type_compare(plan: Run, control: Run | None, kinds: dict[str, str],
                 at: tuple[ptr.Snapshot, ptr.Snapshot] | None = None) -> pl.DataFrame:
    """Per building type: levels at the plan run's start, at the plan run's last save (or the last common check-in)
    and in the control run there; added in each run and the plan's lead (plan - control)."""
    first = plan.snaps[0]
    last, other = at if at is not None else (plan.snaps[-1], None)
    out = _type_levels(first, plan.tag(first)).rename({"levels": "start"}).join(
        _type_levels(last, plan.tag(last)).rename({"levels": "plan"}), on="building_type", how="full", coalesce=True)
    cols = ["start", "plan"]
    if control is not None and other is not None:
        out = out.join(_type_levels(other, control.tag(other)).rename({"levels": "control"}), on="building_type",
                       how="full", coalesce=True)
        cols.append("control")
    out = out.with_columns(pl.col(cols).fill_null(0.0)).with_columns((pl.col("plan") - pl.col("start")).alias("plan_added"))
    if "control" in cols:
        out = out.with_columns((pl.col("control") - pl.col("start")).alias("control_added"),
                               (pl.col("plan") - pl.col("control")).alias("plan_lead"))
        key = "plan_lead"
    else:
        key = "plan_added"
    out = out.with_columns(_kind(kinds))
    out = out.filter((pl.col("plan_added") != 0) | (pl.col(key) != 0))
    return out.select("building_type", "kind", *[c for c in out.columns if c not in ("building_type", "kind")]).sort(
        [pl.col(key).abs(), pl.col("building_type")], descending=[True, False])


# ---------------------------------------------------------------------------------------------------------------------
# Food
# ---------------------------------------------------------------------------------------------------------------------
def province_months(snap: ptr.Snapshot, tag: str) -> pl.DataFrame:
    """The country's provinces: stored months (food / consumption), room in months and fill."""
    schema = {"province_id": pl.Int64, "months": pl.Float64, "room_months": pl.Float64, "fill": pl.Float64}
    pf, mine = ptr._table(snap, "province_food"), ptr.country_provinces(snap, tag)
    if pf is None or mine is None:
        return pl.DataFrame(schema=schema)
    p = pf.join(mine, on="province_id").filter(pl.col("base_food_consumption") > 0)
    return p.select(pl.col("province_id").cast(pl.Int64),
                    (pl.col("food_current") / pl.col("base_food_consumption")).alias("months"),
                    (pl.col("max_food_value") / pl.col("base_food_consumption")).alias("room_months"),
                    (pl.col("food_current") / pl.col("max_food_value")).alias("fill"))


def food_series(runs: Sequence[Run | None], settings: ptr.Settings) -> pl.DataFrame:
    """Per save: provinces, those under the famine line, median and lowest stored months, those at 24 months."""
    rows = []
    for run, snap in _rows(runs):
        p = province_months(snap, run.tag(snap))
        rows.append({**_head(run, snap), "provinces": p.height,
                     "under_famine_line": p.filter(pl.col("months") < settings.famine_months).height,
                     "median_months": float(p["months"].median()) if p.height else None,
                     "lowest_months": float(p["months"].min()) if p.height else None,
                     "at_24_months": p.filter(pl.col("months") >= settings.granary_months - 0.01).height})
    return pl.DataFrame(rows, schema={"series": pl.Utf8, "save": pl.Utf8, "date": pl.Utf8, "year": pl.Float64,
                                      "provinces": pl.Int64, "under_famine_line": pl.Int64,
                                      "median_months": pl.Float64, "lowest_months": pl.Float64,
                                      "at_24_months": pl.Int64})


def food_compare(plan: Run, control: Run, at: tuple[ptr.Snapshot, ptr.Snapshot]) -> pl.DataFrame:
    """Per province the country holds in both runs at the check-in: stored months in each and plan - control."""
    a, b = at
    pa = province_months(a, plan.tag(a)).select("province_id", pl.col("months").alias("plan_months"))
    cb = province_months(b, control.tag(b)).select("province_id", pl.col("months").alias("control_months"))
    out = pa.join(cb, on="province_id", how="inner").with_columns(
        (pl.col("plan_months") - pl.col("control_months")).alias("plan_minus_control"))
    return out.sort("plan_minus_control")


# ---------------------------------------------------------------------------------------------------------------------
# Market access
# ---------------------------------------------------------------------------------------------------------------------
def access_series(runs: Sequence[Run | None], kinds: dict[str, str], settings: ptr.Settings) -> pl.DataFrame:
    """Per save: mean and lowest market access of the locations the country owns and controls, those below the
    logistics line, logistics levels, and building levels per location (unsupported levels are not in the tables)."""
    logistics = [b for b, k in kinds.items() if k == "logistics"]
    rows = []
    for run, snap in _rows(runs):
        tag = run.tag(snap)
        loc = ptr._table(snap, "locations")
        if loc is None:
            continue
        mine = loc.filter(pl.col("country_tag") == tag)
        ctrl = mine.filter(pl.col("controller") == pl.col("owner")) if "controller" in mine.columns else mine
        below = ctrl.filter(pl.col("market_access") < settings.access_line)
        per_loc = ptr.levels_by_location(snap, tag).group_by("location_id").agg(pl.col("levels").sum())
        b = ptr._table(snap, "buildings")
        lv = (float(b.filter((pl.col("country_tag") == tag) & pl.col("building_type").is_in(logistics))["level"].sum())
              if b is not None else None)
        rows.append({**_head(run, snap), "locations": ctrl.height,
                     "mean_access": float(ctrl["market_access"].mean()) if ctrl.height else None,
                     "lowest_access": float(ctrl["market_access"].min()) if ctrl.height else None,
                     "below_line": below.height, "logistics_levels": lv,
                     "levels_per_location": float(per_loc["levels"].sum()) / mine.height if mine.height else None,
                     "most_levels_in_a_location": float(per_loc["levels"].max()) if per_loc.height else None})
    return pl.DataFrame(rows, infer_schema_length=None)


# ---------------------------------------------------------------------------------------------------------------------
# The plan's purses and what its groups save for
# ---------------------------------------------------------------------------------------------------------------------
PURSE_SCHEMA = {"save": pl.Utf8, "date": pl.Utf8, "year": pl.Float64, "group": pl.Utf8, "purse": pl.Float64,
                "saving_for_cost": pl.Float64, "spent_last_12_passes": pl.Float64, "wanted_last_12_passes": pl.Float64}


def _history(cvars: dict[str, float], kind: str, why: str) -> float:
    """The sum of a rule group's twelve history slots (each + 100; a missing slot counts nothing)."""
    names = (f"pp_cplan_{kind}_{why}_{n}" for n in range(1, 13))
    return float(sum(max(0.0, cvars[name] - 100) for name in names if name in cvars))


def purse_series(run: Run) -> pl.DataFrame:
    """Per save and rule group: the purse (gold kept for the group), the cost of what it saves for, and the gold it
    spent and wanted in the last twelve passes (the window's history, pp_cplan_hs_ / _hn_<why>_<1..12>). All country
    variables carry + 100."""
    rows = []
    for snap in run.snaps:
        cvars = ptr._country_vars(snap, run.cid)
        if "pp_cplan_on" not in cvars:
            continue
        for why, group in GROUP_NAMES.items():
            purse, cost = cvars.get(f"pp_cplan_purse_{why}"), cvars.get(f"pp_cplan_save_cost_{why}")
            rows.append({"save": snap.name, "date": snap.date, "year": snap.year, "group": group,
                         "purse": purse - 100 if purse is not None else None,
                         "saving_for_cost": cost - 100 if cost is not None else None,
                         "spent_last_12_passes": _history(cvars, "hs", why),
                         "wanted_last_12_passes": _history(cvars, "hn", why)})
    return pl.DataFrame(rows, schema=PURSE_SCHEMA)


DUMP_SCHEMA = {"dump": pl.Int64, "clock": pl.Float64, "console_save": pl.Utf8, "group": pl.Utf8, "building": pl.Utf8,
               "location": pl.Utf8}


def parse_dumps(lines: Iterable[str]) -> pl.DataFrame:
    """The `run pp_run_dump.txt` lines of a debug.log: one row per dump and rule group that saves for something, with
    the building type and location it saves for, and the console save that followed the dump (the save it belongs to)."""
    rows: list[dict[str, Any]] = []
    dump = 0
    current: dict[str, dict[str, Any]] = {}
    pending: tuple[str, str] | None = None
    open_dump = False
    waiting: list[dict[str, Any]] = []  # rows of the last closed dump, until a console save names them
    clock = 0.0
    for raw in lines:
        line = raw.rstrip("\r\n")
        if (m := ptr.CLOCK_RE.match(line)) is not None:
            clock = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
        if (d := DUMP_RE.search(line)) is not None:
            kind, value = d.group(1), d.group(2).lower()
            if kind == "D" and value == "begin":
                dump += 1
                current, open_dump, waiting, pending = {}, True, [], None
            elif kind == "D" and value == "end" and open_dump:
                open_dump = False
                waiting = [{"dump": dump, "clock": float(clock), "console_save": None, "group": g,
                            "building": v.get("building"), "location": v.get("location")}
                           for g, v in current.items()]
                if not waiting:  # a dump in which no group saves still counts
                    waiting = [{"dump": dump, "clock": float(clock), "console_save": None, "group": None,
                                "building": None, "location": None}]
                rows += waiting
            elif kind in "SL" and open_dump:
                group = GROUP_NAMES.get(value, value)
                current.setdefault(group, {})
                pending = ("building" if kind == "S" else "location", group)
            continue
        if pending is not None:
            regex = ptr.SCOPE_BTYPE_RE if pending[0] == "building" else ptr.SCOPE_LOCATION_RE
            if (s := regex.search(line)) is not None:
                current[pending[1]][pending[0]] = s.group(1)
                pending = None
                continue
        if waiting and (c := CONSOLE_RE.search(line)) is not None and c.group(1).startswith("save "):
            for row in waiting:
                row["console_save"] = c.group(1)[5:].strip()
            waiting = []
    return pl.DataFrame(rows, schema=DUMP_SCHEMA)


def dump_saves(dumps: pl.DataFrame, run: Run) -> pl.DataFrame:
    """Dumps with the save of the run they belong to: `<label>_start` is the first save, `<label>_y<year>` the save of
    that year (pp_run_loop.ps1's names; a pause save `_p<n>` belongs to no kept save)."""
    by_year = {int(math.floor(s.year)): s for s in run.snaps[1:]}
    names, dates = [], []
    for console in dumps["console_save"].to_list():
        snap = None
        if console is not None:
            if console.endswith("_start") and run.snaps:
                snap = run.snaps[0]
            elif (m := SAVE_YEAR_RE.search(console)) is not None:
                snap = by_year.get(int(m.group(1)))
        names.append(snap.name if snap is not None else None)
        dates.append(snap.date if snap is not None else None)
    return dumps.with_columns(pl.Series("save", names, dtype=pl.Utf8), pl.Series("date", dates, dtype=pl.Utf8))


# ---------------------------------------------------------------------------------------------------------------------
# Did the game run without a stop
# ---------------------------------------------------------------------------------------------------------------------
STEP_SCHEMA = {"date": pl.Utf8, "year": pl.Float64, "seconds": pl.Float64, "console": pl.Utf8}


def month_steps(plog: ptr.PlanLog, debug_lines: Iterable[str]) -> pl.DataFrame:
    """Wall-clock seconds from each monthly pass of the plan to the next (one segment only: no loads), with the
    console commands typed in between (a save or a run_until explains a stop)."""
    passes = plog.passes.filter(pl.col("year").is_not_null()).sort("clock")
    if passes.height < 2:
        return pl.DataFrame(schema=STEP_SCHEMA)
    commands: list[tuple[float, str]] = []
    base = prev = None
    wrap = 0.0
    for raw in debug_lines:
        m = ptr.CLOCK_RE.match(raw)
        if m is None:
            continue
        seconds = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
        if prev is not None and seconds < prev:
            wrap += 86400.0
        prev = seconds
        base = seconds if base is None else base
        if (c := CONSOLE_RE.search(raw)) is not None:
            commands.append((seconds + wrap - base, c.group(1)))
    rows = []
    listed = passes.select("clock", "segment", "date", "year").rows()
    for (c0, s0, _, _), (c1, s1, date, year) in zip(listed, listed[1:], strict=False):
        if s0 != s1:
            continue
        typed = [text for at, text in commands if c0 <= at <= c1]
        rows.append({"date": date, "year": year, "seconds": c1 - c0, "console": "; ".join(typed) or None})
    return pl.DataFrame(rows, schema=STEP_SCHEMA)


def stops(steps: pl.DataFrame) -> tuple[pl.DataFrame, dict[str, Any]]:
    """Months slower than STOP_FACTOR x the median month and STOP_SECONDS: `explained` when a console command was
    typed in that month (the loop's save and run_until), else unexplained (the game stood still by itself)."""
    if steps.is_empty():
        return steps.with_columns(pl.lit(None, dtype=pl.Boolean).alias("explained")), {}
    moving = steps.filter(pl.col("seconds") > 0)["seconds"]
    median = float(moving.median() or 0.0) if moving.len() else 0.0
    line = max(STOP_FACTOR * median, STOP_SECONDS)
    slow = steps.filter(pl.col("seconds") > line).with_columns(pl.col("console").is_not_null().alias("explained"))
    info = {"months": steps.height, "median_seconds": median, "line_seconds": line, "stops": slow.height,
            "unexplained": slow.filter(~pl.col("explained")).height}
    return slow, info


def run_log_pauses(lines: Iterable[str]) -> pl.DataFrame:
    """pp_run_loop.ps1's PAUSE lines: the stops before a target date (the pauses the test layer did not prevent)."""
    rows = []
    for raw in lines:
        if (m := RUNLOG_PAUSE_RE.search(raw)) is not None:
            rows.append({"pause": int(m.group(1)), "game_date": m.group(2), "line": raw.strip()})
    return pl.DataFrame(rows, schema={"pause": pl.Int64, "game_date": pl.Utf8, "line": pl.Utf8})


# ---------------------------------------------------------------------------------------------------------------------
# Goods whose producers the plan built
# ---------------------------------------------------------------------------------------------------------------------
def plan_goods(plan: Run, type_table: pl.DataFrame, top: int = TOP_GOODS) -> pl.DataFrame:
    """The goods made by the building types the plan run added (more than the control did, where there is one), by
    their output in the plan run's last save: good, output a month, the building types."""
    schema = {"good": pl.Utf8, "output": pl.Float64, "building_types": pl.Utf8}
    key = "plan_lead" if "plan_lead" in type_table.columns else "plan_added"
    types = type_table.filter((pl.col("plan_added") > 0) & (pl.col(key) > 0))["building_type"].to_list()
    last = plan.snaps[-1]
    flows = ptr._table(last, "production_method_good_flows")
    if flows is None or not types:
        return pl.DataFrame(schema=schema)
    own = list(ptr.owned(last, plan.tag(last)))
    f = flows.filter((pl.col("direction") == "output") & pl.col("building_type").is_in(types)
                     & pl.col("location_id").is_in(own))
    amount = "allocated_amount" if "allocated_amount" in f.columns else "nominal_amount"
    out = f.group_by(pl.col("good_id").alias("good")).agg(
        pl.col(amount).sum().alias("output"),
        pl.col("building_type").unique().sort().str.join(", ").alias("building_types"))
    return out.sort(["output", "good"], descending=[True, False]).head(top).cast(schema)


GOODS_SCHEMA = {"series": pl.Utf8, "save": pl.Utf8, "date": pl.Utf8, "year": pl.Float64, "good": pl.Utf8,
                "price_ratio": pl.Float64, "stock_months": pl.Float64, "supply": pl.Float64, "demand": pl.Float64}


def goods_series(runs: Sequence[Run | None], goods: Sequence[str]) -> pl.DataFrame:
    """Per save and good, over the markets the country's locations belong to (weighted by its locations in each):
    price over default price, and stock in months of demand, supply and demand summed."""
    rows = []
    for run, snap in _rows(runs):
        loc, mg = ptr._table(snap, "locations"), ptr._table(snap, "market_goods")
        if loc is None or mg is None or not goods:
            continue
        weights = loc.filter(pl.col("country_tag") == run.tag(snap)).group_by("market_id").agg(pl.len().alias("w"))
        m = mg.filter(pl.col("good_id").is_in(list(goods))).join(weights, on="market_id", how="inner")
        m = m.with_columns((pl.col("price") / pl.col("default_price")).alias("ratio"),
                           pl.col("supply", "demand", "stockpile").fill_null(0.0))
        agg = m.group_by("good_id").agg(
            ((pl.col("ratio") * pl.col("w")).sum() / pl.col("w").sum()).alias("price_ratio"),
            pl.col("stockpile").sum().alias("stock"), pl.col("supply").sum(), pl.col("demand").sum())
        for good, ratio, stock, supply, demand in agg.iter_rows():
            rows.append({**_head(run, snap), "good": good, "price_ratio": ratio,
                         "stock_months": stock / demand if demand and demand > 0 else None,
                         "supply": supply, "demand": demand})
    return pl.DataFrame(rows, schema=GOODS_SCHEMA)


def goods_verdict(series: pl.DataFrame, plan: Run, control: Run | None) -> pl.DataFrame:
    """Per good: price ratio at the plan run's start and end, its lowest point, the control's end, and `flooded` when
    the plan run's price fell below CRASH_RATIO of the default while the control's (or its own start) did not."""
    rows = []
    p = series.filter(pl.col("series") == PLAN)
    c = series.filter(pl.col("series") == CONTROL)
    common = pairs(plan, control)
    last_plan = common[-1][0].name if common else (plan.snaps[-1].name if plan.snaps else None)
    last_control = common[-1][1].name if common else None
    for good in p["good"].unique(maintain_order=True).to_list():
        part = p.filter(pl.col("good") == good).sort("year")
        start, low = float(part["price_ratio"][0]), float(part["price_ratio"].min())
        end_row = part.filter(pl.col("save") == last_plan)
        end = float(end_row["price_ratio"][0]) if end_row.height else float(part["price_ratio"][-1])
        row: dict[str, Any] = {"good": good, "plan_start": start, "plan_lowest": low, "plan_end": end,
                               "plan_stock_months_end": (end_row["stock_months"][0] if end_row.height
                                                         else part["stock_months"][-1])}
        reference = start
        if last_control is not None:
            ctrl = c.filter((pl.col("good") == good) & (pl.col("save") == last_control))
            row["control_end"] = float(ctrl["price_ratio"][0]) if ctrl.height else None
            row["control_stock_months_end"] = ctrl["stock_months"][0] if ctrl.height else None
            reference = row["control_end"] if row["control_end"] is not None else start
        row["flooded"] = bool(end < CRASH_RATIO and reference >= CRASH_RATIO)
        rows.append(row)
    return pl.DataFrame(rows, infer_schema_length=None)


# ---------------------------------------------------------------------------------------------------------------------
# Verdict
# ---------------------------------------------------------------------------------------------------------------------
def verdict(country: pl.DataFrame, staff: pl.DataFrame, food: pl.DataFrame, access: pl.DataFrame,
            plan: Run, control: Run | None) -> tuple[pl.DataFrame, str]:
    """Plan against control at the last common check-in (the plan run's last save without a control): one row per
    measure with both values, the difference and whether more is better."""
    common = pairs(plan, control)
    a = common[-1][0] if common else plan.snaps[-1]
    b = common[-1][1] if common else None

    def pick(frame: pl.DataFrame, series: str, snap: ptr.Snapshot | None, col: str) -> float | None:
        if snap is None or frame.is_empty() or col not in frame.columns:
            return None
        hit = frame.filter((pl.col("series") == series) & (pl.col("save") == snap.name))
        return float(hit[col][0]) if hit.height and hit[col][0] is not None else None

    measures = [
        ("building levels", country, "building_levels", "more"),
        ("closed building levels", staff, "closed_levels", "less"),
        ("under-staffed building levels", staff, "understaffed_levels", "less"),
        ("population (thousands)", country, "population_k", "more"),
        ("treasury (gold)", country, "gold", "more"),
        ("monthly income", country, "income", "more"),
        ("monthly balance", country, "balance", "more"),
        ("tax base", country, "tax_base", "more"),
        ("provinces under the famine line", food, "under_famine_line", "less"),
        ("median stored months", food, "median_months", "more"),
        ("mean market access", access, "mean_access", "more"),
        ("locations below the access line", access, "below_line", "less"),
    ]
    rows = []
    for name, frame, col, better in measures:
        pv, cv = pick(frame, PLAN, a, col), pick(frame, CONTROL, b, col)
        diff = pv - cv if pv is not None and cv is not None else None
        if diff is None or abs(diff) < 1e-9:
            who = ""
        else:
            who = PLAN if (diff > 0) == (better == "more") else CONTROL
        rows.append({"measure": name, "plan": pv, "control": cv, "plan_minus_control": diff,
                     "in_percent": diff / abs(cv) * 100 if diff is not None and cv else None,
                     "better_is": better, "ahead": who})
    where = f"{a.date}" + (f" (control {b.date})" if b is not None else ", no control run")
    return pl.DataFrame(rows, schema={"measure": pl.Utf8, "plan": pl.Float64, "control": pl.Float64,
                                      "plan_minus_control": pl.Float64, "in_percent": pl.Float64,
                                      "better_is": pl.Utf8, "ahead": pl.Utf8}), where


# ---------------------------------------------------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------------------------------------------------
def chart_two(frame: pl.DataFrame, value: str, ylabel: str, out: Path, stem: str, zero: bool = True) -> str | None:
    """Plan (colour) against control (grey) over game time."""
    if frame.is_empty() or value not in frame.columns or frame.filter(pl.col(value).is_not_null()).height < 2:
        return None

    def draw(ax: Any, theme: dict[str, Any]) -> None:
        labels = frame["series"].unique(maintain_order=True).to_list()
        for label in labels:
            part = frame.filter((pl.col("series") == label) & pl.col(value).is_not_null()).sort("year")
            color = ptr.BASELINE_GREY if label == CONTROL else theme["series"][0]
            ax.plot(part["year"], part[value], color=color, linewidth=2, marker="o", markersize=4, label=label)
        ax.set_ylabel(ylabel)
        if zero:
            ax.set_ylim(bottom=0)
        _year_axis(ax)
        ptr._legend(ax, len(labels))

    return ptr._chart(out, stem, draw)


def _year_axis(ax: Any) -> None:
    """Whole game years on the x axis."""
    from matplotlib.ticker import MaxNLocator

    ax.xaxis.set_major_locator(MaxNLocator(integer=True))


def chart_columns(frame: pl.DataFrame, columns: Sequence[str], ylabel: str, out: Path, stem: str) -> str | None:
    """One line per column over game time (a zero line when values go below it)."""
    if frame.height < 2:
        return None

    def draw(ax: Any, theme: dict[str, Any]) -> None:
        part = frame.sort("year")
        for i, col in enumerate(columns):
            ax.plot(part["year"], part[col], color=theme["series"][i % len(theme["series"])], linewidth=2, marker="o",
                    markersize=4, label=col.replace("_", " "))
        ax.axhline(0, color=theme["muted"], linewidth=0.8)
        ax.set_ylabel(ylabel)
        _year_axis(ax)
        ptr._legend(ax, len(columns))

    return ptr._chart(out, stem, draw)


def chart_by(frame: pl.DataFrame, key: str, value: str, ylabel: str, out: Path, stem: str,
             dashed: pl.DataFrame | None = None, line: float | None = None) -> str | None:
    """One line per `key` value over game time; `dashed` (same columns) draws the control in the same colours."""
    frame = frame.filter(pl.col(value).is_not_null()) if frame.height else frame
    names = frame[key].unique(maintain_order=True).to_list() if frame.height else []
    if not names or frame.height < 2:
        return None

    def draw(ax: Any, theme: dict[str, Any]) -> None:
        for i, name in enumerate(names):
            color = theme["series"][i % len(theme["series"])]
            part = frame.filter((pl.col(key) == name) & pl.col(value).is_not_null()).sort("year")
            ax.plot(part["year"], part[value], color=color, linewidth=2, marker="o", markersize=3.5, label=str(name))
            if dashed is not None and dashed.height:
                other = dashed.filter((pl.col(key) == name) & pl.col(value).is_not_null()).sort("year")
                ax.plot(other["year"], other[value], color=color, linewidth=1.2, linestyle="--")
        if line is not None:
            ax.axhline(line, color=theme["muted"], linewidth=0.8, linestyle=":")
        ax.set_ylabel(ylabel)
        ax.set_ylim(bottom=0)
        _year_axis(ax)
        ptr._legend(ax, len(names))

    return ptr._chart(out, stem, draw)


# ---------------------------------------------------------------------------------------------------------------------
# The report
# ---------------------------------------------------------------------------------------------------------------------
def build_run_report(plan_saves: Sequence[ptr.Snapshot], out: Path, *, control_saves: Sequence[ptr.Snapshot] = (),
                     country: str | None = None, debug_lines: Sequence[str] | None = None, debug_source: str = "",
                     error_lines: Iterable[str] | None = None, error_source: str = "",
                     run_log_lines: Sequence[str] | None = None, kinds: dict[str, str] | None = None,
                     settings: ptr.Settings | None = None, log: Callable[[str], None] = print) -> Path:
    """Write the comparison of a plan run with a control run (optional) to `out`; returns index.html."""
    settings = settings or ptr.Settings()
    kinds = kinds or {}
    out.mkdir(parents=True, exist_ok=True)
    plan, control, tag = make_runs(plan_saves, control_saves, country)
    runs = [plan, control]
    common = pairs(plan, control)
    at = common[-1] if common else None
    sections: list[ptr.Section] = []
    tiles: list[tuple[str, str, str]] = []
    write = ptr._write_csv

    country_frame = country_series(runs)
    full = full_staffing(runs)
    staff = staffing(runs, full)
    food = food_series(runs, settings)
    access = access_series(runs, kinds, settings)
    levels = kind_series(runs, kinds)
    types = type_compare(plan, control, kinds, at)

    # 1. verdict
    table, where = verdict(country_frame, staff, food, access, plan, control)
    sec = ptr.Section("verdict", "Verdict",
                      f"{tag} at {where}. 'ahead' names the run that does better on the measure; an empty cell is a "
                      "tie or a measure only one run has. A played country and an AI country differ in more than the "
                      "builder (wars, diplomacy, events), so read the building measures first.")
    sec.table("Plan against control", table, write(table, out, "verdict.csv"))
    if control is None:
        sec.note("No control run given: only the plan run's numbers.")
    elif not common:
        sec.note("The two runs have no save at the same game date; the verdict shows the plan run's last save only.")
    sections.append(sec)
    ahead = table.filter(pl.col("ahead") == PLAN).height
    behind = table.filter(pl.col("ahead") == CONTROL).height
    first, last = plan.snaps[0], plan.snaps[-1]
    tiles.append(("Plan run", f"{first.date} to {last.date}", f"{len(plan.snaps)} saves"
                  + (f"; control {len(control.snaps)} saves, {len(common)} common dates" if control else "")))
    if control is not None and common:
        tiles.append(("Measures", f"plan ahead {ahead}, control ahead {behind}", f"of {table.height} at {where}"))

    # 2. did the game run without a stop
    sec = ptr.Section("stops", "Did the game run without a stop",
                      "Wall clock between the plan's monthly passes in debug.log (a stop is a month slower than "
                      f"{STOP_FACTOR:g} times the median and {STOP_SECONDS:g} s; the loop's own save and run_until "
                      "explain one), and the pauses pp_run_loop.ps1 logged (stops before a target date).")
    plog = ptr.parse_debug_log(debug_lines, first.year) if debug_lines is not None else None
    if plog is None:
        sec.note("No debug log read.")
    else:
        steps = month_steps(plog, debug_lines or [])
        slow, info = stops(steps)
        if not info:
            sec.note("Fewer than two monthly passes in the debug log: no timing.")
        else:
            sec.note(f"{info['months']} game months timed, median {info['median_seconds']:.1f} s a month; "
                     f"{info['stops']} stops, {info['unexplained']} of them without a console command.")
            sec.table("Stops", slow, write(slow, out, "stops.csv"), rows=40)
            steps.write_csv(out / "month_steps.csv")
            tiles.append(("Stops without a cause", f"{info['unexplained']}",
                          f"{info['stops']} stops in {info['months']} months, median {info['median_seconds']:.1f} s a month"))
    if run_log_lines is not None:
        paused = run_log_pauses(run_log_lines)
        sec.table("Pauses the loop logged", paused, write(paused, out, "loop_pauses.csv"), rows=40,
                  text="None = the game never stopped before a target date.")
        tiles.append(("Pauses (loop)", f"{paused.height}", "stops before a target date in run.log"))
    else:
        sec.note("No run.log of pp_run_loop.ps1 given (--run-log).")
    sections.append(sec)

    # 3. buildings
    sec = ptr.Section("buildings", "Buildings",
                      "Building levels of the country in every save, by kind (the plan's own lists: food, logistics, "
                      "improvements, businesses; other = the rest), and the levels that stand closed or under-staffed "
                      f"(open, but below {UNDERSTAFFED:.0%} of the workers per level of the fullest building of its "
                      "type in these saves). Territory won or lost moves these lines too.")
    sec.chart("Building levels", chart_two(levels, "total", "building levels", out, "levels_total"))
    diff = kind_difference(levels, plan, control)
    sec.chart("Plan minus control, by kind", chart_columns(diff, list(ptr.KINDS), "building levels, plan - control",
                                                           out, "levels_kind_lead"))
    sec.table("Building levels per save and kind", levels.drop("year"), write(levels, out, "levels_by_save.csv"), rows=60)
    if diff.height:
        sec.table("Plan minus control per kind", diff.drop("year"), write(diff, out, "levels_kind_lead.csv"), rows=60)
    sec.chart("Closed building levels", chart_two(staff, "closed_levels", "levels", out, "closed_levels"))
    sec.chart("Under-staffed building levels", chart_two(staff, "understaffed_levels", "levels", out,
                                                         "understaffed_levels"))
    sec.table("Closed and under-staffed levels per save", staff.drop("year"), write(staff, out, "staffing.csv"), rows=60)
    trouble = trouble_by_type(plan, at[0] if at else last, full)
    sec.table(f"Plan run, {(at[0] if at else last).date}: building types with closed or under-staffed levels", trouble,
              write(trouble, out, "trouble_by_type.csv"), rows=30)
    sec.table("Levels per building type: start, plan, control", types, write(types, out, "levels_by_type.csv"), rows=50,
              text="start = the plan run's first save; plan lead = plan - control at the last common date.")
    sections.append(sec)
    if types.height and "plan_lead" in types.columns:
        tiles.append(("Plan lead in levels", f"{float(types['plan_lead'].sum()):+,.0f}",
                      f"plan {float(types['plan_added'].sum()):+,.0f}, control "
                      f"{float(types['control_added'].sum()):+,.0f} since the start"))

    # 4. money and people
    sec = ptr.Section("country", "Treasury, income, tax base, population",
                      "As the saves hold them: gold, last month's income and expense, tax base; people in thousands.")
    for col, label in (("gold", "gold"), ("income", "monthly income"), ("tax_base", "tax base"),
                       ("population_k", "people (thousands)")):
        sec.chart(label.capitalize(), chart_two(country_frame, col, label, out, f"country_{col}"))
    sec.table("The country per save", country_frame.drop("year"), write(country_frame, out, "country.csv"), rows=80)
    sections.append(sec)

    # 5. food
    sec = ptr.Section("food", "Stored food",
                      "Stored months per province = food in store over normal monthly consumption, for the provinces "
                      f"whose capital the country owns. Famine line {settings.famine_months:g} months.")
    sec.chart("Median stored months", chart_two(food, "median_months", "months", out, "food_median"))
    sec.chart("Provinces under the famine line", chart_two(food, "under_famine_line", "provinces", out, "food_famine"))
    sec.table("Province stores per save", food.drop("year"), write(food, out, "food.csv"), rows=80)
    if control is not None and at is not None:
        fc = food_compare(plan, control, at)
        sec.table(f"Stored months per province at {at[0].date}: plan, control", fc,
                  write(fc, out, "food_by_province.csv"), rows=30,
                  text="Provinces the country holds in both runs; the plan's worst first.")
    sections.append(sec)

    # 6. market access
    sec = ptr.Section("access", "Market access",
                      f"Locations the country owns and controls; the logistics line is {settings.access_line:.0%}. "
                      "Unsupported building levels are not in the save tables: building levels per location stand in "
                      "(every level over a location's free levels costs market access).")
    sec.chart("Mean market access", chart_two(access, "mean_access", "market access", out, "access_mean", zero=False))
    sec.chart("Locations below the logistics line", chart_two(access, "below_line", "locations", out, "access_below"))
    sec.table("Market access per save", access.drop("year") if access.height else access,
              write(access, out, "market_access.csv"), rows=80)
    sections.append(sec)

    # 7. what the plan started, spent and saved for
    sec = ptr.Section("plan", "The plan: constructions, gold, savings",
                      "Constructions per rule group from the plan's test lines in debug.log; gold from the plan's own "
                      "ledger in the saves (each group's last twelve passes, so a yearly save covers the year); the "
                      "purse = gold kept for the group, saving for = the cost of the thing it waits for.")
    if plog is not None and plog.plan_lines:
        builds, _ = ptr.latest_timeline(plog.builds, plog.dates)
        by = builds.with_columns(pl.col("year").floor().cast(pl.Int64).cast(pl.Utf8).fill_null("unknown").alias("year"))
        by_year = ptr._pivot_groups(by, "year").sort("year")
        by_building = ptr._pivot_groups(builds, "building").sort(["total", "building"], descending=[True, False])
        sec.chart("Constructions started per game year, by rule group",
                  ptr.chart_builds_per_year(by_year.filter(pl.col("year") != "unknown").with_columns(
                      pl.col("year").cast(pl.Int64)), out) if by_year.height else None)
        sec.table("Constructions per game year and rule group", by_year, write(by_year, out, "builds_by_year.csv"), rows=80)
        sec.table("Constructions per building and rule group", by_building, write(by_building, out, "builds_by_building.csv"),
                  rows=40)
        tiles.append(("Constructions logged", f"{builds.height:,}", f"{plog.passes.height:,} monthly passes"))
    else:
        sec.note(f"No {ptr.PLAN_TAG} lines read ({debug_source or 'no debug log'}): the plan writes them only with "
                 "pp_cplan_ai_test set (run pp_run_setup.txt).")
    purses = purse_series(plan)
    if purses.height:
        sec.chart("Gold spent in the last twelve passes, by rule group",
                  chart_by(purses, "group", "spent_last_12_passes", "gold", out, "plan_spent"))
        sec.chart("Purse per rule group", chart_by(purses, "group", "purse", "gold", out, "plan_purses"))
        sec.table("Purses, savings and gold spent per save and rule group", purses.drop("year"),
                  write(purses, out, "purses.csv"), rows=120)
        spent = float(purses["spent_last_12_passes"].sum())
        tiles.append(("Gold spent by the plan", f"{spent:,.0f}", "sum of the yearly ledgers (saves a year apart)"))
    else:
        sec.note("The plan is off in every save of the plan run (no pp_cplan_on): no purses.")
    if debug_lines is not None:
        dumps = dump_saves(parse_dumps(debug_lines), plan).filter(pl.col("group").is_not_null())
        if dumps.height:
            sec.table("What each group saved for at each save", dumps.select("date", "save", "group", "building", "location",
                                                                            "console_save"),
                      write(dumps, out, "saving_for.csv"), rows=120,
                      text="From run pp_run_dump.txt before each save; a group that is missing saved for nothing.")
        else:
            sec.note("No dump lines (run pp_run_dump.txt) in the debug log: what the groups saved for is not known; "
                     "the cost is in the purse table.")
    sections.append(sec)

    # 8. goods
    goods = plan_goods(plan, types)
    sec = ptr.Section("goods", "Markets of the goods the plan built for",
                      f"The {TOP_GOODS} goods with the largest output from the building types the plan run added "
                      "(more than the control). Price over default price and stock in months of demand, over the "
                      "markets the country's locations belong to (weighted by its locations in each). Flooded = the "
                      f"plan run's price ended below {CRASH_RATIO:g} of the default while the control's did not.")
    if goods.is_empty():
        sec.note("No building type grew in the plan run (or the saves hold no production flows).")
    else:
        gs = goods_series(runs, goods["good"].to_list())
        gp, gc = gs.filter(pl.col("series") == PLAN), gs.filter(pl.col("series") == CONTROL)
        sec.chart("Price over default price (solid plan, dashed control)",
                  chart_by(gp, "good", "price_ratio", "price / default price", out, "goods_price", dashed=gc, line=1.0))
        sec.chart("Stock in months of demand (solid plan, dashed control)",
                  chart_by(gp, "good", "stock_months", "months", out, "goods_stock", dashed=gc))
        gv = goods_verdict(gs, plan, control)
        sec.table("The goods", goods, write(goods, out, "goods.csv"))
        sec.table("Price and stock: start, lowest, end", gv, write(gv, out, "goods_verdict.csv"))
        sec.table("Price and stock per save", gs.drop("year"), write(gs, out, "goods_by_save.csv"), rows=40)
        flooded = gv.filter(pl.col("flooded"))["good"].to_list() if gv.height else []
        tiles.append(("Flooded markets", f"{len(flooded)}", ", ".join(flooded) or f"none of {goods.height} goods"))
    sections.append(sec)

    # 9. errors
    sec = ptr.Section("errors", "Errors", f"error.log entries that mention the plan ({', '.join(ptr.ERROR_PATTERNS)}).")
    if error_lines is None:
        sec.note("No error log read.")
    else:
        total, errors = ptr.error_summary(error_lines, console=ptr.console_seconds(debug_lines) if debug_lines else None)
        game = int(errors.filter(pl.col("source") == "game")["count"].sum()) if errors.height else 0
        sec.note(f"{game} plan entries from the game of {total:,} error entries in {error_source or 'the error log'}.")
        sec.table("Plan entries in error.log", errors, write(errors, out, "errors.csv"), rows=40)
        tiles.append(("Plan errors", f"{game}", f"in the game; {total:,} entries in all"))
    sections.append(sec)

    title = f"Construction Plan run: {tag}"
    lead = (f"Plan run {first.name} to {last.name}"
            + (f"; control run {control.snaps[0].name} to {control.snaps[-1].name}" if control else "; no control run")
            + (f". Log {debug_source}." if debug_source else "."))
    page = out / "index.html"
    page.write_text(ptr.render_html(title, lead, tiles, sections), encoding="utf-8")
    (out / "summary.md").write_text(ptr.render_markdown(title, lead, tiles, sections), encoding="utf-8")
    log(f"plan-run-report: {tag}, {len(plan.snaps)} plan saves, {len(control.snaps) if control else 0} control saves "
        f"-> {page}")
    return page
