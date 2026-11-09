"""Construction Plan test runs: one report from the saves, the plan's test log and the error log (`ppc plan-report`).

A test run is a series of saves of one game (the test world "PP Construction Test", or any game with the plan on),
optionally with a control series from the same start without the plan (the baseline). The report says what the plan
built (its log lines in debug.log, building levels in the saves, against the baseline), how the location profiles'
rules ended up, what the global rule groups look at (province food stores, market access), which constructions stood
still, and the plan's lines in error.log. Output: <out>/index.html (charts as PNG next to it, a light and a dark
copy), <out>/summary.md (plain tables for a terminal) and the CSVs behind every table.

The plan's test log (written by `debug_log` in test mode; the text may still change, so ALL of its parsing sits in
`parse_debug_log` and the regex constants below). Every line of interest contains `PPCPLAN;`:
- a construction: `PPCPLAN;B;<group>;<location key>;<building name>`, group a word of GROUPS or its why code
  (101 food, 102 logistics, 103 goods, 104 rule, 105 profile, 106 improve);
- a monthly pass: `PPCPLAN;P;<constructions started>;<gold spent>` (numbers may carry decimals);
- the game date: the engine's `debug_log_date` writes its own line before each pass; the last date seen (DATE_RE or
  DATE_WORDS_RE) on a line without the tag, or before the tag on a tagged line, is the current game date.
Lines start with a `[hh:mm:ss]` wall clock and often a `[file:line]:` prefix; the clock gives seconds per game year.
When the game date jumps back (a save was loaded), the later play replaces the earlier from that date on.

Save tables come from the Rust engine (`eu5gameparser.savegame.quick`). Not in its tables (2026-11-09): province
variables (the food rule's `pp_cplan_status`), a location's population capacity (the improvement rule's fill line),
scope-valued variables (a profile rule's target good) and a construction's missing goods. Their sections say so and
use what is there instead.
"""

from __future__ import annotations

import html
import math
import re
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date as _date
from pathlib import Path
from typing import Any

import polars as pl

# ---------------------------------------------------------------------------------------------------------------------
# The plan's test log in debug.log (one place: change these when the game's text changes)
# ---------------------------------------------------------------------------------------------------------------------
PLAN_TAG = "PPCPLAN;"
CLOCK_RE = re.compile(r"^\s*\[(\d{1,2}):(\d{2}):(\d{2})\]")                 # [hh:mm:ss] wall clock at the line start
PREFIX_RE = re.compile(r"^\s*\[\d{1,2}:\d{2}:\d{2}\](?:\[[^\]]*\])?:?\s*")  # clock + optional [file.cpp:123]:
# In game 2026-11-09: debug_log gets no data context (ROOT and saved scopes are null in its text), so the plan writes a
# static marker per construction ("PPCPLAN;B;food") and then debug_log_scopes lines for the building type and the
# location ("Building Type 'Granary' (350)", "Location 'Valladolid' (2584)"); a pass is "PPCPLAN;P" (numbers optional,
# an older format had them), and debug_log_date writes nothing, so months are counted by pass lines from the first
# save's date (parse_debug_log's start_year).
BUILD_RE = re.compile(r"PPCPLAN;B;\s*([^;\s]+)\s*(?:;\s*([^;]*?)\s*;\s*([^;]*?)\s*(?:;.*)?)?$")
PASS_RE = re.compile(r"PPCPLAN;P(?:;\s*(-?\d+(?:\.\d+)?)?\s*;\s*(-?\d+(?:\.\d+)?)?)?\s*$")
SCOPE_BTYPE_RE = re.compile(r"Building Type '(.+)' \((\d+)\)\s*$")  # names may hold an apostrophe
SCOPE_LOCATION_RE = re.compile(r"Location '(.+)' \((\d+)\)\s*$")
DATE_RE = re.compile(r"(?<![\d.])(\d{3,4})\.(\d{1,2})\.(\d{1,2})(?![\d.])")  # 1337.4.1
MONTHS = ("january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
          "november", "december")
# 1 April 1337
DATE_WORDS_RE = re.compile(r"\b(\d{1,2})\s+(" + "|".join(MONTHS) + r")\s*,?\s+(\d{3,4})\b", re.IGNORECASE)
GAME_YEARS = (1000, 1999)  # a date outside these years is not the game date (keeps out real-world dates)
GROUPS = ("food", "logistics", "goods", "rule", "profile", "improve")
WHY_CODES = {str(100 + i): g for i, g in enumerate(GROUPS, start=1)}  # the plan's why codes 101..106
# error.log lines that belong to the plan
ERROR_PATTERNS = ("pp_cplan", "pp_lprof", "pp_construction_plan", "pp_location_profiles", "construction_plan")

# ---------------------------------------------------------------------------------------------------------------------
# State codes (+ 100 in the game; docs/location_profiles.md and docs/player_construction_manager.md)
# ---------------------------------------------------------------------------------------------------------------------
RULE_STATES = {1: "started", 2: "nothing to build", 3: "under construction", 4: "code 4", 5: "payback too long",
               6: "cannot be built here", 7: "budget", 8: "market lacks construction goods",
               9: "waiting for an earlier rule"}
FOOD_STATES = {1: "building", 2: "short, nothing can be built", 3: "nothing due", 5: "hands off",
               7: "held back (budget)", 8: "stored food not counted yet", 9: "granary due, none can be built",
               10: "waiting: food building under construction"}
NO_PROFIT = 999.0  # pp_lprof_r<r>_est 1099 - 100: the rule found no profit
STORE_BANDS = ((0, 3, "under 3"), (3, 6, "3-6"), (6, 12, "6-12"), (12, 24, "12-24"), (24, math.inf, "24+"))
KINDS = ("food", "logistics", "improve", "goods", "other")

# chart colours: the run report's validated categorical order (light, and its steps for the dark surface)
LIGHT_SERIES = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948")
DARK_SERIES = ("#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767")
BANDS_RAMP = ("#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#184f95")  # ordinal blue, few -> many months
BASELINE_GREY = "#9a9a96"
STATE_COLOUR_SLOT = {1: 0, 2: 1, 3: 2, 5: 3, 6: 4, 7: 5, 8: 6, 9: 7}  # rule state -> fixed series colour
THEMES = {
    "light": {"bg": "#fcfcfb", "ink": "#1d1d1b", "muted": "#6b6b67", "grid": "#e2e2de", "series": LIGHT_SERIES},
    "dark": {"bg": "#1a1d22", "ink": "#eceef0", "muted": "#a0a6b0", "grid": "#2c3038", "series": DARK_SERIES},
}


@dataclass
class PlanLog:
    """What `parse_debug_log` found. Frames carry `clock` (wall-clock seconds since the log's first line, midnight
    wraps added), `segment` (counts up whenever the game date jumps back), `date` and `year` (fractional)."""

    builds: pl.DataFrame
    passes: pl.DataFrame
    dates: pl.DataFrame
    lines: int = 0
    plan_lines: int = 0
    unparsed: list[str] = field(default_factory=list)


BUILD_SCHEMA = {"clock": pl.Float64, "segment": pl.Int64, "date": pl.Utf8, "year": pl.Float64, "group": pl.Utf8,
                "location": pl.Utf8, "building": pl.Utf8, "location_id": pl.Int64}
PASS_SCHEMA = {"clock": pl.Float64, "segment": pl.Int64, "date": pl.Utf8, "year": pl.Float64, "started": pl.Float64,
               "gold": pl.Float64}
DATE_SCHEMA = {"clock": pl.Float64, "segment": pl.Int64, "date": pl.Utf8, "year": pl.Float64}


def year_fraction(year: int, month: int, day: int) -> float:
    return year + (month - 1) / 12 + (day - 1) / 365


def _find_date(text: str) -> tuple[str, float] | None:
    best = None
    for match in DATE_RE.finditer(text):
        y, m, d = (int(g) for g in match.groups())
        if GAME_YEARS[0] <= y <= GAME_YEARS[1] and 1 <= m <= 12 and 1 <= d <= 31:
            best = (f"{y}.{m}.{d}", year_fraction(y, m, d))
    for match in DATE_WORDS_RE.finditer(text):
        d, month, y = int(match.group(1)), MONTHS.index(match.group(2).lower()) + 1, int(match.group(3))
        if GAME_YEARS[0] <= y <= GAME_YEARS[1] and 1 <= d <= 31:
            best = (f"{y}.{month}.{d}", year_fraction(y, month, d))
    return best


def _month_date(start_year: float, months: int) -> tuple[str, float]:
    """The game date `months` monthly passes after `start_year` (the first save's date), as text and year."""
    total = int(round((start_year - math.floor(start_year)) * 12)) + months
    y, m = int(math.floor(start_year)) + total // 12, total % 12 + 1
    return f"{y}.{m}.1", year_fraction(y, m, 1)


def parse_debug_log(lines: Iterable[str], start_year: float | None = None) -> PlanLog:
    """Read the plan's test log out of debug.log lines (see the module doc and the regex constants above).

    A construction marker gives one `builds` row (its building type and location from the debug_log_scopes lines that
    follow it), a pass line one `passes` row. Game dates: from date lines when the log has any; otherwise, with
    `start_year` (the first save's date), pass n is n months after it and a construction belongs to the pass after it,
    and every pass also gives a `dates` row (the speed reads those). A tagged line that matches neither format lands
    in `unparsed` (first 20 kept)."""
    builds, passes, dates, unparsed = [], [], [], []
    clock_base = clock_prev = None
    wrap = 0.0
    clock = 0.0
    segment = 0
    current: tuple[str, float] | None = None
    count = plan_count = 0
    pending: dict[str, Any] | None = None  # the last construction, waiting for its scope lines
    month_builds: list[dict[str, Any]] = []  # constructions of the pass under way (dated by its P line)
    pass_count = 0
    for raw in lines:
        count += 1
        line = raw.rstrip("\r\n")
        if (m := CLOCK_RE.match(line)) is not None:
            seconds = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
            if clock_prev is not None and seconds < clock_prev:
                wrap += 86400.0  # past midnight
            clock_prev = seconds
            clock_base = seconds if clock_base is None else clock_base
            clock = seconds + wrap - clock_base
        tag = line.find(PLAN_TAG)
        if tag < 0 and pending is not None:
            if pending["building"] is None and (bt := SCOPE_BTYPE_RE.search(line)) is not None:
                pending["building"] = bt.group(1)
                continue
            if pending["location_id"] is None and (lc := SCOPE_LOCATION_RE.search(line)) is not None:
                pending["location"], pending["location_id"] = lc.group(1), int(lc.group(2))
                pending = None
                continue
        found = _find_date(PREFIX_RE.sub("", line) if tag < 0 else PREFIX_RE.sub("", line[:tag]))
        if found is not None:
            if current is not None and found[1] < current[1] - 1e-9:
                segment += 1  # the game date jumped back: a save was loaded
            current = found
            if tag < 0:
                dates.append({"clock": clock, "segment": segment, "date": found[0], "year": found[1]})
        if tag < 0:
            continue
        plan_count += 1
        date, year = current if current is not None else (None, None)
        if (b := BUILD_RE.search(line)) is not None:
            group = b.group(1).strip().lower()
            row = {"clock": clock, "segment": segment, "date": date, "year": year,
                   "group": WHY_CODES.get(group, group), "location": b.group(2) or None,
                   "building": b.group(3) or None, "location_id": None}
            builds.append(row)
            month_builds.append(row)
            pending = row if row["building"] is None else None
        elif (p := PASS_RE.search(line)) is not None:
            pass_count += 1
            if not dates and start_year is not None:
                date, year = _month_date(start_year, pass_count)
                for row in month_builds:
                    row["date"], row["year"] = date, year
            started = float(p.group(1)) if p.group(1) else float(len(month_builds))
            gold = float(p.group(2)) if p.group(2) else None
            passes.append({"clock": clock, "segment": segment, "date": date, "year": year,
                           "started": started, "gold": gold})
            month_builds = []
            pending = None
        elif len(unparsed) < 20:
            unparsed.append(line[tag:])
    if not dates and start_year is not None:
        dates = [{"clock": row["clock"], "segment": row["segment"], "date": row["date"], "year": row["year"]}
                 for row in passes]
    return PlanLog(pl.DataFrame(builds, schema=BUILD_SCHEMA), pl.DataFrame(passes, schema=PASS_SCHEMA),
                   pl.DataFrame(dates, schema=DATE_SCHEMA), count, plan_count, unparsed)


def latest_timeline(frame: pl.DataFrame, dates: pl.DataFrame) -> tuple[pl.DataFrame, int]:
    """Rows of `frame` on the latest timeline: where a later segment (a save loaded) covers a game date, the earlier
    segments' rows from that date on are dropped. Returns the kept rows and how many were dropped."""
    starts: dict[int, float] = {}
    for source in (dates, frame):
        for seg, year in source.filter(pl.col("year").is_not_null()).group_by("segment").agg(
                pl.col("year").min()).iter_rows():
            starts[seg] = min(starts.get(seg, math.inf), year)
    if not starts or frame.is_empty():
        return frame, 0
    cover = {}  # segment -> the earliest start of every later segment
    running = math.inf
    for seg in sorted(starts, reverse=True):
        cover[seg] = running
        running = min(running, starts[seg])
    limit = pl.col("segment").replace_strict(cover, default=math.inf, return_dtype=pl.Float64)
    kept = frame.filter(pl.col("year").is_null() | (pl.col("year") < limit))
    return kept, frame.height - kept.height


PAUSE_FACTOR = 5.0  # a step slower than this many times the median second per game year counts as a pause


def log_speed(dates: pl.DataFrame) -> tuple[pl.DataFrame, dict[str, Any]]:
    """Seconds of wall clock per game year from the date lines: per game year, and over the whole log. Steps across a
    segment break (a load) are left out, and so are steps slower than PAUSE_FACTOR x the median (pauses)."""
    if dates.height < 2:
        return pl.DataFrame(schema={"year": pl.Int64, "game_years": pl.Float64, "seconds": pl.Float64,
                                    "s_per_year": pl.Float64}), {}
    d = dates.sort("clock").with_columns(
        (pl.col("clock").shift(-1) - pl.col("clock")).alias("dt"),
        (pl.col("year").shift(-1) - pl.col("year")).alias("dy"),
        (pl.col("segment").shift(-1) == pl.col("segment")).alias("same"),
    ).filter(pl.col("same") & (pl.col("dy") > 0))
    if d.is_empty():
        return pl.DataFrame(schema={"year": pl.Int64, "game_years": pl.Float64, "seconds": pl.Float64,
                                    "s_per_year": pl.Float64}), {}
    rate = d["dt"] / d["dy"]
    moving = rate.filter(rate > 0)  # the clock has whole seconds: in a fast run most month steps read 0
    median = float(moving.median() or 0.0) if moving.len() else 0.0
    keep = d.filter((pl.col("dt") / pl.col("dy")) <= PAUSE_FACTOR * max(median, 1e-9))
    per_year = (keep.group_by(pl.col("year").floor().cast(pl.Int64).alias("year"))
                .agg(pl.col("dy").sum().alias("game_years"), pl.col("dt").sum().alias("seconds"))
                .with_columns((pl.col("seconds") / pl.col("game_years")).alias("s_per_year")).sort("year"))
    total = {"game_years": float(keep["dy"].sum()), "seconds": float(keep["dt"].sum()),
             "pauses": d.height - keep.height}
    total["s_per_year"] = total["seconds"] / total["game_years"] if total["game_years"] > 0 else None
    return per_year, total


# ---------------------------------------------------------------------------------------------------------------------
# Saves
# ---------------------------------------------------------------------------------------------------------------------
@dataclass
class Snapshot:
    """One save: its name, game date, file time and engine tables (attributes that are Polars frames)."""

    name: str
    date: str
    year: float
    mtime: float | None
    tables: Any


def parse_game_date(text: str) -> float:
    y, m, d = (int(x) for x in str(text).split(".")[:3])
    return year_fraction(y, m, d)


def load_snapshot(path: Path, load_order: Path) -> Snapshot:
    from eu5gameparser.savegame import quick

    tables = quick.load(path, load_order=load_order)
    meta = tables.metadata
    date = str(meta["date"][0])
    has_mtime = "mtime" in meta.columns and meta["mtime"][0] is not None
    mtime = float(meta["mtime"][0]) if has_mtime else path.stat().st_mtime
    return Snapshot(path.stem, date, parse_game_date(date), mtime, tables)


def _table(snap: Snapshot, name: str) -> pl.DataFrame | None:
    try:
        frame = getattr(snap.tables, name)
    except (AttributeError, FileNotFoundError, KeyError):
        return None
    return frame if isinstance(frame, pl.DataFrame) else None


def main_country(snap: Snapshot) -> str:
    """The country that owns the most locations in the save."""
    loc = _table(snap, "locations")
    if loc is None or loc.is_empty():
        raise SystemExit(f"{snap.name}: no locations table")
    top = loc.filter(pl.col("country_tag").is_not_null()).group_by("country_tag").len().sort(
        ["len", "country_tag"], descending=[True, False])
    return str(top["country_tag"][0])


def country_id(snap: Snapshot, tag: str) -> int | None:
    countries = _table(snap, "countries_raw")
    if countries is not None and "tag" in countries.columns:
        hit = countries.filter(pl.col("tag") == tag)
        if hit.height:
            return int(hit["country_id"][0])
    loc = _table(snap, "locations")
    if loc is not None and "owner_country_id" in loc.columns:
        hit = loc.filter(pl.col("country_tag") == tag)
        if hit.height:
            return int(hit["owner_country_id"][0])
    return None


def owned(snap: Snapshot, tag: str) -> set[int]:
    loc = _table(snap, "locations")
    return set() if loc is None else set(loc.filter(pl.col("country_tag") == tag)["location_id"].to_list())


def _country_vars(snap: Snapshot, cid: int | None) -> dict[str, float]:
    cv = _table(snap, "country_variables")
    if cv is None or cid is None:
        return {}
    return dict(cv.filter(pl.col("country_id") == cid).select("name", "value").iter_rows())


def overview(series: Sequence[tuple[str, Snapshot]], tag: str) -> pl.DataFrame:
    """One row per save: the country's locations, people, gold, building levels, constructions, the plan's last pass."""
    rows = []
    for label, snap in series:
        cid = country_id(snap, tag)
        loc = _table(snap, "locations")
        mine = loc.filter(pl.col("country_tag") == tag) if loc is not None else pl.DataFrame()
        row: dict[str, Any] = {"series": label, "save": snap.name, "date": snap.date,
                               "locations": mine.height,
                               "population_k": float(mine["total_population"].sum()) if mine.height else None}
        ai = _table(snap, "country_ai")
        ai = ai.filter(pl.col("country_id") == cid) if ai is not None and cid is not None else None
        for col in ("gold", "income", "expense", "tax_base"):
            present = ai is not None and ai.height and col in ai.columns and ai[col][0] is not None
            row[col] = float(ai[col][0]) if present else None
        buildings = _table(snap, "buildings")
        row["building_levels"] = (float(buildings.filter(pl.col("country_tag") == tag)["level"].sum())
                                  if buildings is not None else None)
        cons = _table(snap, "constructions")
        row["constructions"] = cons.filter(pl.col("country_id") == cid).height if cons is not None else None
        cvars = _country_vars(snap, cid)
        row["plan_on"] = "yes" if "pp_cplan_on" in cvars else "no"
        row["last_pass_started"] = cvars["pp_cplan_started"] - 100 if "pp_cplan_started" in cvars else None
        row["last_pass_gold"] = cvars["pp_cplan_spent"] - 100 if "pp_cplan_spent" in cvars else None
        rows.append(row)
    return pl.DataFrame(rows, infer_schema_length=None)


def plan_settings(snap: Snapshot, tag: str) -> pl.DataFrame:
    """The plan's country variables in a save (numbers without the + 100; switches as 'set')."""
    cvars = _country_vars(snap, country_id(snap, tag))
    rows = []
    for name, value in sorted(cvars.items()):
        if not name.startswith(("pp_cplan_", "pp_lprof_")) or name.startswith("pp_lprof_e_"):
            continue
        rows.append({"variable": name, "value": "set" if abs(value) < 0.01 else f"{value - 100:g}"})
    return pl.DataFrame(rows, schema={"variable": pl.Utf8, "value": pl.Utf8})


def save_speed(series: Sequence[tuple[str, Snapshot]]) -> pl.DataFrame:
    """Seconds per game year between consecutive saves of one series by file time (includes saving, loading and any
    pause between them: an upper bound)."""
    rows = []
    by_label: dict[str, list[Snapshot]] = {}
    for label, snap in series:
        by_label.setdefault(label, []).append(snap)
    for label, snaps in by_label.items():
        for a, b in zip(snaps, snaps[1:], strict=False):
            years = b.year - a.year
            seconds = (b.mtime - a.mtime) if a.mtime is not None and b.mtime is not None else None
            rows.append({"series": label, "from": a.name, "to": b.name, "game_years": round(years, 3),
                         "seconds": seconds,
                         "s_per_year": seconds / years if seconds is not None and years > 0 else None})
    return pl.DataFrame(rows, schema={"series": pl.Utf8, "from": pl.Utf8, "to": pl.Utf8, "game_years": pl.Float64,
                                      "seconds": pl.Float64, "s_per_year": pl.Float64})


# ---------------------------------------------------------------------------------------------------------------------
# Building levels
# ---------------------------------------------------------------------------------------------------------------------
def levels_by_location(snap: Snapshot, tag: str) -> pl.DataFrame:
    b = _table(snap, "buildings")
    if b is None:
        return pl.DataFrame(schema={"location_id": pl.Int64, "building_type": pl.Utf8, "levels": pl.Float64})
    return (b.filter(pl.col("country_tag") == tag).group_by("location_id", "building_type")
            .agg(pl.col("level").sum().cast(pl.Float64).alias("levels")))


def level_change(first: Snapshot, last: Snapshot, tag: str, locations: set[int] | None) -> pl.DataFrame:
    """Per location and building type: levels in `first`, in `last`, and the change, over `locations` (all the
    country's when None)."""
    a = levels_by_location(first, tag).rename({"levels": "before"})
    b = levels_by_location(last, tag).rename({"levels": "after"})
    d = a.join(b, on=["location_id", "building_type"], how="full", coalesce=True).with_columns(
        pl.col("before").fill_null(0.0), pl.col("after").fill_null(0.0))
    if locations is not None:
        d = d.filter(pl.col("location_id").is_in(list(locations)))
    return d.with_columns((pl.col("after") - pl.col("before")).alias("added"))


def match_save(series: Sequence[Snapshot], year: float) -> Snapshot:
    """The save of `series` whose date is nearest to `year` (the earlier one on a tie)."""
    return min(series, key=lambda s: (abs(s.year - year), s.year))


@dataclass
class Comparison:
    run_first: Snapshot
    run_last: Snapshot
    base_first: Snapshot | None
    base_last: Snapshot | None
    locations: set[int]


def comparison(run: Sequence[Snapshot], baseline: Sequence[Snapshot], tag: str) -> Comparison:
    """The saves to compare: the run from its first save to its last (with a baseline: to the save nearest the
    baseline's last date), over the locations the country owns in all of them."""
    if baseline:
        base_first, base_last = baseline[0], baseline[-1]
        run_last = match_save(run, base_last.year)
        snaps = [run[0], run_last, base_first, base_last]
    else:
        base_first = base_last = None
        run_last = run[-1]
        snaps = [run[0], run_last]
    common = set.intersection(*(owned(s, tag) for s in snaps))
    return Comparison(run[0], run_last, base_first, base_last, common)


def levels_by_type(cmp: Comparison, tag: str, kinds: dict[str, str]) -> pl.DataFrame:
    """Building levels added per type (run, and with a baseline: baseline and plan extra = run - baseline)."""
    run = (level_change(cmp.run_first, cmp.run_last, tag, cmp.locations).group_by("building_type")
           .agg(pl.col("before").sum().alias("levels_before"), pl.col("after").sum().alias("levels_after"),
                pl.col("added").sum().alias("run_added")))
    if cmp.base_first is not None and cmp.base_last is not None:
        base = (level_change(cmp.base_first, cmp.base_last, tag, cmp.locations).group_by("building_type")
                .agg(pl.col("added").sum().alias("baseline_added")))
        run = run.join(base, on="building_type", how="full", coalesce=True).with_columns(
            pl.col("levels_before", "levels_after", "run_added", "baseline_added").fill_null(0.0)).with_columns(
            (pl.col("run_added") - pl.col("baseline_added")).alias("plan_extra"))
        key = "plan_extra"
    else:
        key = "run_added"
    run = run.with_columns(pl.col("building_type").replace_strict(kinds, default="other").alias("kind"))
    run = run.filter((pl.col("run_added") != 0) | (pl.col(key) != 0))
    return run.sort([key, "building_type"], descending=[True, False]).select(
        "building_type", "kind", *[c for c in run.columns if c not in ("building_type", "kind")])


def levels_by_kind(by_type: pl.DataFrame) -> pl.DataFrame:
    cols = [c for c in ("run_added", "baseline_added", "plan_extra") if c in by_type.columns]
    out = by_type.group_by("kind").agg(*[pl.col(c).sum() for c in cols], pl.len().alias("types"))
    order = {k: i for i, k in enumerate(KINDS)}
    return out.with_columns(pl.col("kind").replace_strict(order, default=len(KINDS)).alias("_o")).sort("_o").drop("_o")


def series_levels(series: Sequence[tuple[str, Snapshot]], tag: str, kinds: dict[str, str]) -> pl.DataFrame:
    """Building levels per save and kind (all the country's locations)."""
    rows = []
    for label, snap in series:
        lv = levels_by_location(snap, tag).with_columns(
            pl.col("building_type").replace_strict(kinds, default="other").alias("kind"))
        totals = dict(lv.group_by("kind").agg(pl.col("levels").sum()).iter_rows())
        rows.append({"series": label, "save": snap.name, "date": snap.date, "year": snap.year,
                     **{k: float(totals.get(k, 0.0)) for k in KINDS}, "total": float(sum(totals.values()))})
    return pl.DataFrame(rows, schema={"series": pl.Utf8, "save": pl.Utf8, "date": pl.Utf8, "year": pl.Float64,
                                      **{k: pl.Float64 for k in KINDS}, "total": pl.Float64})


# ---------------------------------------------------------------------------------------------------------------------
# Location profiles
# ---------------------------------------------------------------------------------------------------------------------
_RULE_VAR = re.compile(r"^pp_lprof_r(\d+)_(st|est)$")


def profile_assignment(snap: Snapshot) -> pl.DataFrame:
    """location_id -> profile slot (variable pp_lprof = slot + 100)."""
    lv = _table(snap, "location_variables")
    if lv is None:
        return pl.DataFrame(schema={"location_id": pl.Int64, "slot": pl.Int64})
    return lv.filter(pl.col("name") == "pp_lprof").select(
        "location_id", (pl.col("value") - 100).round(0).cast(pl.Int64).alias("slot"))


def _rule_vars(snap: Snapshot, kind: str) -> pl.DataFrame:
    lv = _table(snap, "location_variables")
    if lv is None:
        return pl.DataFrame(schema={"location_id": pl.Int64, "rule": pl.Int64, "value": pl.Float64})
    part = lv.filter(pl.col("name").str.contains(rf"^pp_lprof_r\d+_{kind}$"))
    return part.select("location_id", pl.col("name").str.extract(r"_r(\d+)_", 1).cast(pl.Int64).alias("rule"),
                       (pl.col("value") - 100).alias("value"))


def rule_states(snap: Snapshot, tag: str) -> pl.DataFrame:
    """Per profile slot and rule: how many of the country's profile locations ended the last pass in each state."""
    slots = profile_assignment(snap).filter(pl.col("location_id").is_in(list(owned(snap, tag))))
    st = _rule_vars(snap, "st").with_columns(pl.col("value").round(0).cast(pl.Int64).alias("state"))
    st = slots.join(st, on="location_id", how="inner")
    out = st.group_by("slot", "rule", "state").agg(pl.len().alias("locations")).sort("slot", "rule", "state")
    return out.with_columns(pl.col("state").replace_strict(RULE_STATES, default=None, return_dtype=pl.Utf8)
                            .fill_null(pl.format("code {}", pl.col("state"))).alias("state_name"))


def rule_paybacks(snap: Snapshot, tag: str) -> pl.DataFrame:
    """Per profile slot and rule: the shortest payback the rule found (pp_lprof_r<r>_est, years), over the locations
    that have one; `no_profit` counts the 1099 (no profit) marks."""
    slots = profile_assignment(snap).filter(pl.col("location_id").is_in(list(owned(snap, tag))))
    est = slots.join(_rule_vars(snap, "est"), on="location_id", how="inner")
    paid = pl.col("value") < NO_PROFIT - 0.5
    return est.group_by("slot", "rule").agg(
        pl.len().alias("locations"), paid.sum().alias("with_profit"), (~paid).sum().alias("no_profit"),
        pl.col("value").filter(paid).min().alias("shortest_years"),
        pl.col("value").filter(paid).median().alias("median_years"),
    ).sort("slot", "rule")


def first_assignment(series: Sequence[Snapshot]) -> pl.DataFrame:
    """The profile slots of the first save that has any (later reassignments are not followed)."""
    for snap in series:
        slots = profile_assignment(snap)
        if slots.height:
            return slots
    return pl.DataFrame(schema={"location_id": pl.Int64, "slot": pl.Int64})


def profile_levels(cmp: Comparison, tag: str, slots: pl.DataFrame, top: int = 4) -> pl.DataFrame:
    """Per profile slot (0 = no profile): locations, levels added, per location, and with a baseline the baseline's
    change in the same locations and the plan's extra; the building types that grew most."""
    run = level_change(cmp.run_first, cmp.run_last, tag, cmp.locations)
    run = run.join(slots, on="location_id", how="left").with_columns(pl.col("slot").fill_null(0))
    locs = (pl.DataFrame({"location_id": sorted(cmp.locations)}, schema={"location_id": pl.Int64})
            .join(slots, on="location_id", how="left").with_columns(pl.col("slot").fill_null(0))
            .group_by("slot").agg(pl.len().alias("locations")))
    out = run.group_by("slot").agg(pl.col("before").sum().alias("levels_before"),
                                   pl.col("added").sum().alias("run_added"))
    out = locs.join(out, on="slot", how="left").with_columns(pl.col("levels_before", "run_added").fill_null(0.0))
    per_type = run.group_by("slot", "building_type").agg(pl.col("added").sum())
    key = "added"
    if cmp.base_first is not None and cmp.base_last is not None:
        base = level_change(cmp.base_first, cmp.base_last, tag, cmp.locations).join(
            slots, on="location_id", how="left").with_columns(pl.col("slot").fill_null(0))
        out = out.join(base.group_by("slot").agg(pl.col("added").sum().alias("baseline_added")), on="slot",
                       how="left").with_columns(pl.col("baseline_added").fill_null(0.0)).with_columns(
            (pl.col("run_added") - pl.col("baseline_added")).alias("plan_extra"))
        per_type = per_type.join(base.group_by("slot", "building_type").agg(pl.col("added").sum().alias("base")),
                                 on=["slot", "building_type"], how="full", coalesce=True).with_columns(
            pl.col("added", "base").fill_null(0.0))
        per_type = per_type.with_columns((pl.col("added") - pl.col("base")).alias("extra"))
        key = "extra"
    out = out.with_columns((pl.col("run_added") / pl.col("locations")).alias("added_per_location"))
    tops = {}
    for slot, part in per_type.filter(pl.col(key) != 0).group_by("slot"):
        part = part.sort([key, "building_type"], descending=[True, False]).head(top)
        tops[slot[0]] = ", ".join(f"{b} {v:+g}" for b, v in part.select("building_type", key).iter_rows())
    out = out.with_columns(pl.col("slot").replace_strict(tops, default="", return_dtype=pl.Utf8).alias("most_grown"))
    return out.sort("slot")


# ---------------------------------------------------------------------------------------------------------------------
# Global rule groups
# ---------------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Settings:
    """The plan's lines the report checks against ([construction_plan] in constructor.toml)."""

    access_line: float = 0.97
    famine_months: float = 3.0
    granary_months: float = 24.0
    granary_fill: float = 0.85
    grange_surplus: float = 0.05


def country_provinces(snap: Snapshot, tag: str) -> pl.DataFrame | None:
    """province_id of the country's provinces: those whose capital location it owns (provinces_raw's
    owner_country_id disagrees: at 1368 in the test world it named another country for 53 of the 84 provinces whose
    capital Castile owns)."""
    pr, loc = _table(snap, "provinces_raw"), _table(snap, "locations")
    if pr is None:
        return None
    if loc is not None and "capital_location_id" in pr.columns:
        return pr.join(loc.select(pl.col("location_id").alias("capital_location_id"), "country_tag"),
                       on="capital_location_id").filter(pl.col("country_tag") == tag).select("province_id")
    cid = country_id(snap, tag)
    return None if cid is None else pr.filter(pl.col("owner_country_id") == cid).select("province_id")


def food_stores(series: Sequence[tuple[str, Snapshot]], tag: str, settings: Settings) -> pl.DataFrame:
    """Per save: the country's provinces by stored months (food / consumption) and those where the Granary and the
    Grange rule would fire on today's numbers (approximation: the plan reads the store a year from now without this
    year's harvest and spoilage)."""
    rows = []
    for label, snap in series:
        pf, mine = _table(snap, "province_food"), country_provinces(snap, tag)
        if pf is None or mine is None:
            continue
        p = pf.join(mine, on="province_id").filter(pl.col("base_food_consumption") > 0)
        p = p.with_columns((pl.col("food_current") / pl.col("base_food_consumption")).alias("months"),
                           (pl.col("max_food_value") / pl.col("base_food_consumption")).alias("room_months"),
                           (pl.col("food_current") / pl.col("max_food_value")).alias("fill"))
        row: dict[str, Any] = {"series": label, "save": snap.name, "date": snap.date, "provinces": p.height}
        for lo, hi, name in STORE_BANDS:
            row[f"months_{name}"] = p.filter((pl.col("months") >= lo) & (pl.col("months") < hi)).height
        row["median_months"] = float(p["months"].median()) if p.height else None
        row["granary_due"] = p.filter((pl.col("room_months") < settings.granary_months)
                                      & (pl.col("fill") >= settings.granary_fill)
                                      & (pl.col("cached_food_change") > 0)).height
        row["grange_due"] = p.filter((pl.col("months") >= settings.granary_months - 0.01)
                                     & (pl.col("cached_food_change")
                                        >= settings.grange_surplus * pl.col("base_food_consumption"))).height
        rows.append(row)
    return pl.DataFrame(rows, infer_schema_length=None)


def food_statuses(series: Sequence[tuple[str, Snapshot]], tag: str) -> pl.DataFrame | None:
    """Per save: provinces by the food rule's state (province variable pp_cplan_status), when the engine extracts
    province variables (a `province_variables` table with province_id, name, value); None otherwise."""
    rows = []
    any_table = False
    for label, snap in series:
        pv, mine = _table(snap, "province_variables"), country_provinces(snap, tag)
        if pv is None or mine is None:
            continue
        any_table = True
        st = pv.filter(pl.col("name") == "pp_cplan_status").join(mine, on="province_id")
        for code, n in st.group_by((pl.col("value") - 100).round(0).cast(pl.Int64).alias("c")).len().iter_rows():
            rows.append({"series": label, "save": snap.name, "state": FOOD_STATES.get(code, f"code {code}"),
                         "provinces": n})
    if not any_table:
        return None
    return pl.DataFrame(rows, schema={"series": pl.Utf8, "save": pl.Utf8, "state": pl.Utf8, "provinces": pl.Int64})


def market_access(series: Sequence[tuple[str, Snapshot]], tag: str, kinds: dict[str, str],
                  settings: Settings) -> pl.DataFrame:
    """Per save: owned locations the country controls, those below the logistics line, and logistics levels."""
    rows = []
    logistics = [b for b, k in kinds.items() if k == "logistics"]
    for label, snap in series:
        loc = _table(snap, "locations")
        if loc is None:
            continue
        mine = loc.filter(pl.col("country_tag") == tag)
        ctrl = mine.filter(pl.col("controller") == pl.col("owner")) if "controller" in mine.columns else mine
        below = ctrl.filter(pl.col("market_access") < settings.access_line)
        b = _table(snap, "buildings")
        lv = (float(b.filter((pl.col("country_tag") == tag) & pl.col("building_type").is_in(logistics))["level"].sum())
              if b is not None else None)
        rows.append({"series": label, "save": snap.name, "date": snap.date, "year": snap.year,
                     "owned": mine.height, "controlled": ctrl.height, "below_line": below.height,
                     "below_share": below.height / ctrl.height if ctrl.height else None,
                     "median_access_below": float(below["market_access"].median()) if below.height else None,
                     "logistics_levels": lv})
    return pl.DataFrame(rows, infer_schema_length=None)


CAPACITY_COLUMNS = ("location_population_percentage", "population_capacity", "local_population_capacity")


def improvement_fill(series: Sequence[tuple[str, Snapshot]], tag: str, fill_pct: float) -> pl.DataFrame | None:
    """Locations at or above the improvement rule's fill line, when the save tables carry a capacity column."""
    rows = []
    for label, snap in series:
        loc = _table(snap, "locations")
        col = next((c for c in CAPACITY_COLUMNS if loc is not None and c in loc.columns), None)
        if col is None:
            return None
        mine = loc.filter(pl.col("country_tag") == tag)
        if col == "location_population_percentage":
            fill = pl.col(col)
        else:
            fill = pl.col("total_population") / pl.col(col) * 100
        rows.append({"series": label, "save": snap.name, "locations": mine.height,
                     "at_fill_line": mine.filter(fill >= fill_pct).height})
    return pl.DataFrame(rows)


# ---------------------------------------------------------------------------------------------------------------------
# Constructions
# ---------------------------------------------------------------------------------------------------------------------
CONSTRUCTION_SCHEMA = {"construction_id": pl.Int64, "location_id": pl.Int64, "location": pl.Utf8,
                       "building_type": pl.Utf8, "demand": pl.Utf8, "builder": pl.Utf8, "progress": pl.Float64,
                       "total": pl.Float64, "gold_spent": pl.Float64}


def constructions(snap: Snapshot, tag: str) -> pl.DataFrame:
    """The country's constructions in a save (progress 0 where the save leaves it out), building type from its
    building."""
    cons = _table(snap, "constructions")
    cid = country_id(snap, tag)
    if cons is None or cid is None:
        return pl.DataFrame(schema=CONSTRUCTION_SCHEMA)
    c = cons.filter(pl.col("country_id") == cid)
    b = _table(snap, "buildings")
    if b is not None and "building_id" in c.columns:
        c = c.join(b.select("building_id", "building_type"), on="building_id", how="left")
    else:
        c = c.with_columns(pl.lit(None, dtype=pl.Utf8).alias("building_type"))
    loc = _table(snap, "locations")
    if loc is not None:
        c = c.join(loc.select("location_id", pl.col("slug").alias("location")), on="location_id", how="left")
    else:
        c = c.with_columns(pl.lit(None, dtype=pl.Utf8).alias("location"))
    estate = pl.col("estate") if "estate" in c.columns else pl.lit(None, dtype=pl.Utf8)
    return c.select(
        pl.col("construction_id").cast(pl.Int64), pl.col("location_id").cast(pl.Int64), "location",
        pl.col("building_type").cast(pl.Utf8),
        (pl.col("demand") if "demand" in c.columns else pl.lit(None)).cast(pl.Utf8).alias("demand"),
        estate.fill_null("country").cast(pl.Utf8).alias("builder"),
        pl.col("progress").fill_null(0.0).cast(pl.Float64), pl.col("total").cast(pl.Float64),
        (pl.col("gold_spent") if "gold_spent" in c.columns else pl.lit(None)).cast(pl.Float64).alias("gold_spent"))


MOVED_DAYS = 0.5  # progress (days of work) below this between two saves = no progress
# held up: it moved this many days less than it could (the days between the saves, or the days it still needed);
# a construction speed modifier far below 1 would also show up here
SLACK_DAYS = 15.0
REASON_STUCK = "no progress"
REASON_QUEUED = "no progress, another construction here moved"
REASON_SLOW = "held up part of the time"
STALL_SCHEMA = {"from_save": pl.Utf8, "to_save": pl.Utf8, "days_between": pl.Int64, "location": pl.Utf8,
                "building_type": pl.Utf8, "demand": pl.Utf8, "builder": pl.Utf8, "progress_from": pl.Float64,
                "progress_to": pl.Float64, "moved": pl.Float64, "total": pl.Float64, "reason": pl.Utf8}


def stalled_constructions(series: Sequence[Snapshot], tag: str) -> pl.DataFrame:
    """Constructions found in two consecutive saves (same construction id) that did not work every day between them
    (progress counts days of work):
    - REASON_STUCK: no progress, and nothing else in that location moved either;
    - REASON_QUEUED: no progress while another construction in the same location moved, finished or started
      (in the 2026-11-08 test world all ten that stood still 1347-1348 sat beside one that moved);
    - REASON_SLOW: it moved, but SLACK_DAYS less than it could have (min of the days between the saves and the days
      it still needed)."""
    out = []
    for a, b in zip(series, series[1:], strict=False):
        ca, cb = constructions(a, tag), constructions(b, tag)
        if ca.is_empty() or cb.is_empty():
            continue
        days = (b.year - a.year) * 365
        j = ca.join(cb.select("construction_id", pl.col("progress").alias("progress_to")), on="construction_id",
                    how="left")
        j = j.with_columns((pl.col("progress_to") - pl.col("progress")).alias("moved"))
        gone = j.filter(pl.col("progress_to").is_null())["location_id"].to_list()  # finished or cancelled
        moved = j.filter(pl.col("moved") >= MOVED_DAYS)["location_id"].to_list()
        new = cb.join(ca.select("construction_id"), on="construction_id", how="anti").filter(
            pl.col("progress") >= MOVED_DAYS)["location_id"].to_list()
        busy = set(gone) | set(moved) | set(new)
        both = j.filter(pl.col("progress_to").is_not_null())
        both = both.with_columns(
            pl.when((pl.col("moved") < MOVED_DAYS) & pl.col("location_id").is_in(list(busy)))
            .then(pl.lit(REASON_QUEUED))
            .when(pl.col("moved") < MOVED_DAYS).then(pl.lit(REASON_STUCK))
            .when(pl.col("moved") < pl.min_horizontal(pl.lit(days), pl.col("total") - pl.col("progress")) - SLACK_DAYS)
            .then(pl.lit(REASON_SLOW))
            .otherwise(None).alias("reason")).filter(pl.col("reason").is_not_null())
        out.append(both.select(pl.lit(a.name).alias("from_save"), pl.lit(b.name).alias("to_save"),
                               pl.lit(round(days)).alias("days_between"), "location", "building_type", "demand",
                               "builder", pl.col("progress").alias("progress_from"), "progress_to", "moved", "total",
                               "reason"))
    if not out:
        return pl.DataFrame(schema=STALL_SCHEMA)
    return pl.concat(out, how="vertical_relaxed").cast(STALL_SCHEMA)


def construction_counts(series: Sequence[tuple[str, Snapshot]], tag: str, stalled: pl.DataFrame) -> pl.DataFrame:
    rows = []
    for label, snap in series:
        c = constructions(snap, tag)
        mine = stalled.filter(pl.col("to_save") == snap.name)
        rows.append({"series": label, "save": snap.name, "date": snap.date, "year": snap.year,
                     "in_progress": c.height, "by_country": c.filter(pl.col("builder") == "country").height,
                     "by_estates": c.filter(pl.col("builder") != "country").height,
                     "mean_progress_pct": float((c["progress"] / c["total"]).mean() * 100) if c.height else None,
                     "stuck": mine.filter(pl.col("reason") == REASON_STUCK).height,
                     "queued": mine.filter(pl.col("reason") == REASON_QUEUED).height,
                     "held_up": mine.filter(pl.col("reason") == REASON_SLOW).height})
    return pl.DataFrame(rows, infer_schema_length=None)


# ---------------------------------------------------------------------------------------------------------------------
# error.log
# ---------------------------------------------------------------------------------------------------------------------
_CLOCK_ONLY = re.compile(r"^\s*\[\d{1,2}:\d{2}:\d{2}\]\s*")


CONSOLE_RUN_RE = re.compile(r"^\s*\[(\d{1,2}):(\d{2}):(\d{2})\].*Running console command: (?:run|effect)\b")
CONSOLE_SECONDS = 3  # an error entry this many seconds after a console run / effect counts as the console's


def console_seconds(debug_lines: Iterable[str]) -> set[int]:
    """Seconds of the day (debug.log wall clock) at which a console run file or effect ran, and the few after it."""
    found: set[int] = set()
    for line in debug_lines:
        if (m := CONSOLE_RUN_RE.match(line)) is not None:
            start = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
            found.update(start + d for d in range(CONSOLE_SECONDS + 1))
    return found


def error_summary(lines: Iterable[str], patterns: Sequence[str] = ERROR_PATTERNS,
                  console: set[int] | None = None) -> tuple[int, pl.DataFrame]:
    """Total error entries, and the plan's grouped by message, most frequent first. An entry is a clock line with the
    indented lines under it ("  Error: ...", "  Script location: ..."); it is the plan's when a line of it matches the
    patterns, and a console artefact when its script locations go through a console run file (run/...): the console's
    description pass evaluates a run file before its effects set their variables (in game 2026-11-09), so those lines
    say nothing about the monthly pass."""
    pat = re.compile("|".join(re.escape(p) for p in patterns), re.IGNORECASE)
    entries: list[list[str]] = []
    for raw in lines:
        line = raw.rstrip("\r\n")
        if not line.strip():
            continue
        if _CLOCK_ONLY.match(line) or not entries:
            entries.append([line])
        else:
            entries[-1].append(line)
    counts: dict[tuple[str, str, str], int] = {}
    order: dict[tuple[str, str, str], int] = {}
    for index, entry in enumerate(entries, 1):
        if not any(pat.search(line) for line in entry):
            continue
        body = [_CLOCK_ONLY.sub("", line).strip() for line in entry]
        message = next((line for line in body if line.startswith("Error:")), None) or next(
            (line for line in body if line and line != "Script system error!"), body[0])
        where = next((line.removeprefix("Script location:").strip() for line in body if line.startswith("Script location:")), "")
        clock = CLOCK_RE.match(entry[0])
        second = int(clock.group(1)) * 3600 + int(clock.group(2)) * 60 + int(clock.group(3)) if clock else None
        from_console = any(line.startswith("run/") or "Script location: run/" in line for line in body) or (
            console is not None and second in console)
        source = "console run file" if from_console else "game"
        key = (message, where, source)
        counts[key] = counts.get(key, 0) + 1
        order.setdefault(key, index)
    frame = pl.DataFrame({"message": [k[0] for k in counts], "where": [k[1] for k in counts],
                          "source": [k[2] for k in counts], "count": list(counts.values()),
                          "first_entry": [order[k] for k in counts]},
                         schema={"message": pl.Utf8, "where": pl.Utf8, "source": pl.Utf8, "count": pl.Int64,
                                 "first_entry": pl.Int64})
    return len(entries), frame.sort(["source", "count", "first_entry"], descending=[True, True, False])


# ---------------------------------------------------------------------------------------------------------------------
# Building kinds (the plan's own lists)
# ---------------------------------------------------------------------------------------------------------------------
def building_kinds(repo: Path, project: Path, mod_root: Path, game_root: Path,
                   log: Callable[[str], None] = print) -> dict[str, str]:
    """building type -> food / logistics / improve / goods, from the plan's own generated lists
    (construction_plan.apply without writing); only the config's lists when that fails."""
    from prosper_or_perish_constructor import construction_plan

    kinds: dict[str, str] = {}
    try:
        res = construction_plan.apply(repo, project, mod_root, game_root, write=False)
        cfg = construction_plan.load_config(project)
        for names in res.producers.values():
            kinds.update({n: "goods" for n in names})
        food = [b for tiers in res.food_lines.values() for b in tiers]
        food += [*cfg.kitchens, *cfg.taverns, *cfg.granaries, *cfg.granges, *cfg.yards]
        kinds.update({n: "food" for n in food})
        kinds.update({n: "improve" for n in res.improvements})
        kinds.update({n: "logistics" for n in res.logistics})
    except Exception as exc:  # noqa: BLE001 - the report still works with the config's lists
        log(f"plan-report: the plan's building lists failed ({exc}); using [construction_plan] lists only")
        cfg = construction_plan.load_config(project)
        kinds.update({n: "food" for n in (*cfg.kitchens, *cfg.taverns, *cfg.granaries, *cfg.granges, *cfg.yards)})
        kinds.update({n: "logistics" for n in cfg.logistics_order})
    return kinds


def settings_from_config(project: Path) -> Settings:
    from prosper_or_perish_constructor import construction_plan

    cfg = construction_plan.load_config(project)
    return Settings(access_line=cfg.access_threshold / 100, famine_months=float(cfg.famine_months),
                    granary_months=float(cfg.granary_capacity_months), granary_fill=cfg.granary_fill_pct / 100,
                    grange_surplus=cfg.grange_surplus_pct / 100)


# ---------------------------------------------------------------------------------------------------------------------
# Charts (matplotlib, one light and one dark PNG each)
# ---------------------------------------------------------------------------------------------------------------------
def _chart(out: Path, stem: str, draw: Callable[[Any, dict[str, Any]], None], height: float = 3.2) -> str:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    for name, theme in THEMES.items():
        with plt.rc_context({"font.size": 9, "axes.edgecolor": theme["grid"], "axes.labelcolor": theme["muted"],
                             "xtick.color": theme["muted"], "ytick.color": theme["muted"], "text.color": theme["ink"],
                             "font.family": "DejaVu Sans"}):
            fig, ax = plt.subplots(figsize=(9.2, height), dpi=140)
            fig.patch.set_facecolor(theme["bg"])
            ax.set_facecolor(theme["bg"])
            for side in ("top", "right", "left"):
                ax.spines[side].set_visible(False)
            ax.tick_params(length=0)
            ax.grid(True, axis="y", color=theme["grid"], linewidth=0.8)
            ax.set_axisbelow(True)
            draw(ax, theme)
            leg = ax.get_legend()
            if leg is not None:
                leg.get_frame().set_alpha(0)
                for text in leg.get_texts():
                    text.set_color(theme["ink"])
            fig.tight_layout()
            fig.savefig(out / f"{stem}{'' if name == 'light' else '_dark'}.png", facecolor=theme["bg"])
            plt.close(fig)
    return stem


def _legend(ax: Any, n: int) -> None:
    if n >= 2:
        ax.legend(loc="upper left", bbox_to_anchor=(1.0, 1.0), fontsize=8)


def chart_series_levels(levels: pl.DataFrame, out: Path) -> str | None:
    if levels.height < 2:
        return None

    def draw(ax: Any, theme: dict[str, Any]) -> None:
        labels = levels["series"].unique(maintain_order=True).to_list()
        for i, label in enumerate(labels):
            part = levels.filter(pl.col("series") == label).sort("year")
            color = BASELINE_GREY if label == "baseline" else theme["series"][i]
            ax.plot(part["year"], part["total"], color=color, linewidth=2, marker="o", markersize=4.5, label=label)
        ax.set_ylabel("building levels")
        _legend(ax, len(labels))

    return _chart(out, "levels_over_time", draw)


def chart_builds_per_year(by_year: pl.DataFrame, out: Path) -> str | None:
    if by_year.is_empty():
        return None
    groups = [g for g in GROUPS if g in by_year.columns]
    groups += [c for c in by_year.columns if c not in GROUPS and c != "year"]

    def draw(ax: Any, theme: dict[str, Any]) -> None:
        years = by_year["year"].to_list()
        bottom = [0.0] * len(years)
        for g in groups:
            vals = by_year[g].fill_null(0).to_list()
            color = theme["series"][GROUPS.index(g)] if g in GROUPS else BASELINE_GREY
            ax.bar(years, vals, bottom=bottom, color=color, edgecolor=theme["bg"], linewidth=1, width=0.8, label=g)
            bottom = [b + v for b, v in zip(bottom, vals, strict=True)]
        ax.set_ylabel("constructions started")
        _legend(ax, len(groups))

    return _chart(out, "builds_per_year", draw)


def chart_grouped_barh(frame: pl.DataFrame, label: str, columns: Sequence[tuple[str, str]], out: Path, stem: str,
                       xlabel: str) -> str | None:
    if frame.is_empty():
        return None
    height = max(2.2, 0.32 * frame.height * max(1, len(columns)) ** 0.6 + 0.8)

    def draw(ax: Any, theme: dict[str, Any]) -> None:
        names = frame[label].cast(pl.Utf8).to_list()[::-1]
        n = len(columns)
        width = 0.8 / n
        for i, (col, name) in enumerate(columns):
            vals = frame[col].fill_null(0).to_list()[::-1]
            pos = [y - (i - (n - 1) / 2) * width for y in range(len(names))]  # first series on top
            color = BASELINE_GREY if col == "baseline_added" else theme["series"][i]
            ax.barh(pos, vals, height=width * 0.92, color=color, label=name)
        ax.set_yticks(range(len(names)), names)
        ax.grid(True, axis="x", color=theme["grid"], linewidth=0.8)
        ax.grid(False, axis="y")
        ax.axvline(0, color=theme["muted"], linewidth=0.8)
        ax.set_xlabel(xlabel)
        _legend(ax, n)

    return _chart(out, stem, draw, height=height)


def chart_rule_states(states: pl.DataFrame, out: Path) -> str | None:
    if states.is_empty():
        return None
    keys = states.select("slot", "rule").unique().sort("slot", "rule").rows()
    codes = sorted(states["state"].unique().to_list())

    def draw(ax: Any, theme: dict[str, Any]) -> None:
        names = [f"profile {s} rule {r}" for s, r in keys][::-1]
        left = [0.0] * len(keys)
        for code in codes:
            part = dict(((s, r), n) for s, r, n in states.filter(pl.col("state") == code)
                        .select("slot", "rule", "locations").iter_rows())
            vals = [float(part.get(k, 0)) for k in keys][::-1]
            slot = STATE_COLOUR_SLOT.get(code)
            ax.barh(names, vals, left=left, color=BASELINE_GREY if slot is None else theme["series"][slot],
                    edgecolor=theme["bg"], linewidth=1, label=RULE_STATES.get(code, f"code {code}"))
            left = [a + b for a, b in zip(left, vals, strict=True)]
        ax.grid(True, axis="x", color=theme["grid"], linewidth=0.8)
        ax.grid(False, axis="y")
        ax.set_xlabel("locations")
        _legend(ax, len(codes))

    return _chart(out, "rule_states", draw, height=max(2.2, 0.3 * len(keys) + 1.0))


def chart_food_bands(stores: pl.DataFrame, out: Path) -> str | None:
    if stores.is_empty():
        return None

    def draw(ax: Any, theme: dict[str, Any]) -> None:
        labels = [f"{s}\n{d}" for s, d in stores.select("save", "date").iter_rows()]
        bottom = [0.0] * stores.height
        for i, (_, _, name) in enumerate(STORE_BANDS):
            vals = stores[f"months_{name}"].fill_null(0).to_list()
            ax.bar(labels, vals, bottom=bottom, color=BANDS_RAMP[i], edgecolor=theme["bg"], linewidth=1,
                   width=0.6, label=f"{name} months")
            bottom = [b + v for b, v in zip(bottom, vals, strict=True)]
        ax.set_ylabel("provinces")
        _legend(ax, len(STORE_BANDS))

    return _chart(out, "food_stores", draw)


def chart_lines(frame: pl.DataFrame, value: str, ylabel: str, out: Path, stem: str) -> str | None:
    if frame.height < 2:
        return None

    def draw(ax: Any, theme: dict[str, Any]) -> None:
        labels = frame["series"].unique(maintain_order=True).to_list()
        for i, label in enumerate(labels):
            part = frame.filter(pl.col("series") == label).sort("year")
            color = BASELINE_GREY if label == "baseline" else theme["series"][i]
            ax.plot(part["year"], part[value], color=color, linewidth=2, marker="o", markersize=4.5, label=label)
        ax.set_ylabel(ylabel)
        ax.set_ylim(bottom=0)
        _legend(ax, len(labels))

    return _chart(out, stem, draw)


# ---------------------------------------------------------------------------------------------------------------------
# Report model, HTML and Markdown
# ---------------------------------------------------------------------------------------------------------------------
@dataclass
class Block:
    kind: str  # table, chart, note
    title: str = ""
    frame: pl.DataFrame | None = None
    csv: str | None = None
    image: str | None = None
    text: str = ""
    rows: int = 30


@dataclass
class Section:
    key: str
    title: str
    lead: str
    blocks: list[Block] = field(default_factory=list)

    def note(self, text: str) -> None:
        self.blocks.append(Block("note", text=text))

    def table(self, title: str, frame: pl.DataFrame | None, csv: str | None, rows: int = 30, text: str = "") -> None:
        if frame is None:
            return
        self.blocks.append(Block("table", title=title, frame=frame, csv=csv, rows=rows, text=text))

    def chart(self, title: str, image: str | None, text: str = "") -> None:
        if image is not None:
            self.blocks.append(Block("chart", title=title, image=image, text=text))


def _fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        if math.isnan(value):
            return ""
        if math.isinf(value):
            return "inf" if value > 0 else "-inf"
        if value == int(value) and abs(value) < 1e12:
            return f"{int(value):,}"
        if abs(value) >= 100:
            return f"{value:,.0f}"
        return f"{value:.1f}" if abs(value) >= 10 else f"{value:.2f}"
    return str(value)


def _is_num(frame: pl.DataFrame, col: str) -> bool:
    return frame.schema[col].is_numeric()


def _head(col: str) -> str:
    return col.replace("_", " ")


def _html_table(frame: pl.DataFrame, rows: int) -> str:
    cols = frame.columns
    head = "".join(f"<th{' class=num' if _is_num(frame, c) else ''}>{html.escape(_head(c))}</th>" for c in cols)
    body = []
    for row in frame.head(rows).iter_rows():
        cells = "".join(f"<td{' class=num' if _is_num(frame, c) else ''}>{html.escape(_fmt(v))}</td>"
                        for c, v in zip(cols, row, strict=True))
        body.append(f"<tr>{cells}</tr>")
    return f"<div class=table-wrap><table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table></div>"


def _md_table(frame: pl.DataFrame, rows: int) -> str:
    cols = frame.columns
    lines = ["| " + " | ".join(_head(c) for c in cols) + " |",
             "| " + " | ".join("---:" if _is_num(frame, c) else "---" for c in cols) + " |"]
    for row in frame.head(rows).iter_rows():
        lines.append("| " + " | ".join(_fmt(v).replace("|", "/") for v in row) + " |")
    return "\n".join(lines)


EXTRA_CSS = """
th{cursor:default}
.note{margin:0 0 12px;padding:10px 14px;border-left:3px solid var(--line);
  color:var(--muted);font-size:14px;max-width:110ch}
.card picture img{display:block;width:100%;height:auto} .card .src{font-size:12px;color:var(--muted)}
.card .more-rows{padding:6px 16px 12px;font-size:12px;color:var(--muted)}
"""


def render_html(title: str, lead: str, tiles: Sequence[tuple[str, str, str]], sections: Sequence[Section]) -> str:
    from prosper_or_perish_constructor.run_report import PAGE_CSS

    esc = html.escape
    tile_html = "".join(f"<div class=tile><div class=label>{esc(a)}</div><div class=value>{esc(b)}</div>"
                        f"<div class=sub>{esc(c)}</div></div>" for a, b, c in tiles)
    nav = "".join(f"<a href='#{s.key}'>{esc(s.title)}</a>" for s in sections)
    parts = []
    for s in sections:
        parts.append(f"<h2 id={s.key}>{esc(s.title)}</h2><p class=lead>{esc(s.lead)}</p>")
        for b in s.blocks:
            if b.kind == "note":
                parts.append(f"<p class=note>{esc(b.text)}</p>")
            elif b.kind == "chart":
                parts.append(
                    f"<section class=card><header><h3>{esc(b.title)}</h3></header><picture>"
                    f"<source srcset='{b.image}_dark.png' media='(prefers-color-scheme: dark)'>"
                    f"<img src='{b.image}.png' alt='{esc(b.title)}'></picture>"
                    + (f"<p class=caption>{esc(b.text)}</p>" if b.text else "") + "</section>")
            elif b.kind == "table" and b.frame is not None:
                src = f"<a class=src href='{b.csv}'>{esc(b.csv)}</a>" if b.csv else ""
                more = (f"<div class=more-rows>first {b.rows} of {b.frame.height} rows"
                        + (f", all in {esc(b.csv)}" if b.csv else "") + "</div>") if b.frame.height > b.rows else ""
                body = _html_table(b.frame, b.rows) if b.frame.height else "<p class=caption>none</p>"
                parts.append(f"<section class=card><header><h3>{esc(b.title)}</h3>{src}</header>"
                             + (f"<p class=caption>{esc(b.text)}</p>" if b.text else "") + body + more + "</section>")
    return (f"<!doctype html><html lang=en><head><meta charset=utf-8>"
            f"<meta name=viewport content='width=device-width,initial-scale=1'><title>{esc(title)}</title>"
            f"<style>{PAGE_CSS}{EXTRA_CSS}</style></head><body><main><h1>{esc(title)}</h1><p class=lead>{esc(lead)}</p>"
            f"<div class=tiles>{tile_html}</div><nav>{nav}</nav>{''.join(parts)}"
            f"<footer>ppc plan-report, {_date.today().isoformat()}</footer></main></body></html>")


def render_markdown(title: str, lead: str, tiles: Sequence[tuple[str, str, str]], sections: Sequence[Section]) -> str:
    lines = [f"# {title}", "", lead, ""]
    lines += [f"- {a}: {b}" + (f" ({c})" if c else "") for a, b, c in tiles]
    for s in sections:
        lines += ["", f"## {s.title}", "", s.lead]
        for b in s.blocks:
            if b.kind == "note":
                lines += ["", f"> {b.text}"]
            elif b.kind == "chart":
                lines += ["", f"Chart: {b.title} ({b.image}.png)"]
            elif b.kind == "table" and b.frame is not None:
                lines += ["", f"### {b.title}" + (f" ({b.csv})" if b.csv else "")]
                if b.text:
                    lines += ["", b.text]
                lines += ["", _md_table(b.frame, min(b.rows, 25)) if b.frame.height else "none"]
                if b.frame.height > min(b.rows, 25):
                    lines += ["", f"first {min(b.rows, 25)} of {b.frame.height} rows"]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------------------------------------------------
# The report
# ---------------------------------------------------------------------------------------------------------------------
def _write_csv(frame: pl.DataFrame | None, out: Path, name: str) -> str | None:
    if frame is None:
        return None
    frame.write_csv(out / name)
    return name


def _pivot_groups(frame: pl.DataFrame, index: str) -> pl.DataFrame:
    if frame.is_empty():
        return pl.DataFrame(schema={index: pl.Utf8, "total": pl.Int64})
    counts = frame.group_by(index, "group").len()
    wide = counts.pivot(on="group", index=index, values="len", aggregate_function="sum").fill_null(0)
    cols = [g for g in GROUPS if g in wide.columns] + sorted(c for c in wide.columns if c not in GROUPS and c != index)
    wide = wide.select(index, *cols).with_columns(pl.sum_horizontal(cols).alias("total"))
    return wide


def build_report(run: Sequence[Snapshot], out: Path, *, baseline: Sequence[Snapshot] = (), country: str | None = None,
                 debug_lines: Iterable[str] | None = None, debug_source: str = "",
                 error_lines: Iterable[str] | None = None, error_source: str = "",
                 kinds: dict[str, str] | None = None, settings: Settings | None = None,
                 improve_fill_pct: float = 90.0, log: Callable[[str], None] = print) -> Path:
    """Write the report for one save series (and an optional baseline series) to `out`; returns index.html."""
    settings = settings or Settings()
    if not run:
        raise SystemExit("plan-report needs at least one save (--save or --glob)")
    run = sorted(run, key=lambda s: s.year)
    baseline = sorted(baseline, key=lambda s: s.year)
    out.mkdir(parents=True, exist_ok=True)
    kinds = kinds or {}
    tag = country or main_country(run[0])
    series = [("run", s) for s in run] + [("baseline", s) for s in baseline]
    sections: list[Section] = []
    tiles: list[tuple[str, str, str]] = []

    # 1. run overview
    sec = Section("overview", "Run overview",
                  f"{tag}, saves ordered by game date. Population in thousands, gold and income as the save holds "
                  "them, the plan's last pass from its country variables.")
    ov = overview(series, tag)
    sec.table("Saves", ov, _write_csv(ov, out, "overview.csv"))
    first_on = next((s for s in run if "pp_cplan_on" in _country_vars(s, country_id(s, tag))), None)
    if first_on is not None:
        settings_frame = plan_settings(first_on, tag)
        sec.table(f"Plan settings in {first_on.name}", settings_frame, _write_csv(settings_frame, out, "settings.csv"),
                  rows=60, text="Country variables without the + 100; 'set' = a switch that is on.")
    else:
        sec.note("The plan is off in every save of the run (no pp_cplan_on).")
    sspeed = save_speed(series)
    plog: PlanLog | None = parse_debug_log(debug_lines, run[0].year) if debug_lines is not None else None
    speed_total: dict[str, Any] = {}
    if plog is not None and plog.dates.height >= 2:
        per_year, speed_total = log_speed(plog.dates)
        sec.table("Speed from the log (wall clock per game year)", per_year,
                  _write_csv(per_year, out, "speed_log.csv"),
                  text=f"{speed_total.get('s_per_year') or 0:.1f} s per game year over "
                       f"{speed_total.get('game_years', 0):.1f} game years; {speed_total.get('pauses', 0)} steps "
                       f"slower than {PAUSE_FACTOR:g}x the median left out as pauses; loads (date jumps back) "
                       "left out.")
    else:
        sec.note("No game dates in the debug log, so no speed from the log. Speed from the save files' times below "
                 "(includes saving, loading and pauses: an upper bound).")
    sec.table("Speed from save file times", sspeed, _write_csv(sspeed, out, "speed_saves.csv"))
    sections.append(sec)
    years = run[-1].year - run[0].year
    tiles.append(("Run", f"{run[0].date} to {run[-1].date}", f"{len(run)} saves, {years:.1f} game years"))

    # 2. what the plan built
    cmp = comparison(run, baseline, tag)
    sec = Section("built", "What the plan built",
                  "From the plan's log lines (constructions it started) and from the saves (building levels added "
                  f"between {cmp.run_first.name} and {cmp.run_last.name}, in the {len(cmp.locations)} locations "
                  f"{tag} owns in every save compared)"
                  + (f"; the baseline {cmp.base_first.name} to {cmp.base_last.name} without the plan."
                     if cmp.base_first is not None else "."))
    if plog is None:
        sec.note("No debug log read.")
    elif plog.plan_lines == 0:
        sec.note(f"No {PLAN_TAG} lines in {debug_source or 'the debug log'} ({plog.lines:,} lines read). The plan "
                 "writes them only in test mode.")
    if plog is not None and plog.plan_lines:
        builds, dropped_b = latest_timeline(plog.builds, plog.dates)
        passes, dropped_p = latest_timeline(plog.passes, plog.dates)
        if dropped_b or dropped_p:
            sec.note(f"{dropped_b} construction and {dropped_p} pass lines left out: a later load replayed those "
                     "dates (the latest play counts).")
        if plog.unparsed:
            sec.note(f"{len(plog.unparsed)}+ {PLAN_TAG} lines in neither format, e.g. {plog.unparsed[0]!r}.")
        undated = builds.filter(pl.col("year").is_null()).height
        if undated:
            sec.note(f"{undated} construction lines came before any game date and count as year 'unknown'.")
        by = builds.with_columns(pl.col("year").floor().cast(pl.Int64).cast(pl.Utf8).fill_null("unknown").alias("year"))
        by_year = _pivot_groups(by, "year").sort("year")
        by_building = _pivot_groups(builds, "building").sort(["total", "building"], descending=[True, False])
        sec.chart("Constructions started per game year, by rule group",
                  chart_builds_per_year(by_year.filter(pl.col("year") != "unknown").with_columns(
                      pl.col("year").cast(pl.Int64)), out) if by_year.height else None)
        sec.table("Constructions per game year and rule group", by_year, _write_csv(by_year, out, "builds_by_year.csv"))
        sec.table("Constructions per building and rule group", by_building,
                  _write_csv(by_building, out, "builds_by_building.csv"), rows=40)
        builds.write_csv(out / "builds.csv")
        if passes.height:
            py = (passes.with_columns(pl.col("year").floor().cast(pl.Int64).alias("year")).group_by("year")
                  .agg(pl.len().alias("passes"), pl.col("started").sum(), pl.col("gold").sum(),
                       pl.col("started").max().alias("most_in_a_pass")).sort("year"))
            sec.table("Monthly passes per game year", py, _write_csv(py, out, "passes_by_year.csv"),
                      text="started and gold as the pass lines report them.")
        tiles.append(("Constructions logged", f"{builds.height:,}",
                      (f"{passes.height:,} passes" + (f", {passes['gold'].sum():,.0f} gold"
                                                       if passes["gold"].null_count() < passes.height else ""))
                      if passes.height else ""))
    by_type = levels_by_type(cmp, tag, kinds)
    by_kind = levels_by_kind(by_type)
    lv_series = series_levels(series, tag, kinds)
    sec.chart("Building levels per save", chart_series_levels(lv_series, out),
              "All the country's locations (territory lost or won moves this line too).")
    sec.table("Building levels per save and kind", lv_series.drop("year"),
              _write_csv(lv_series, out, "levels_by_save.csv"))
    cols = [("run_added", "run")] + ([("baseline_added", "baseline"), ("plan_extra", "plan extra")]
                                     if "plan_extra" in by_type.columns else [])
    sec.chart("Levels added per kind of building", chart_grouped_barh(by_kind, "kind", cols, out, "levels_by_kind",
                                                                       "building levels added"),
              "Kinds from the plan's own lists: food (farms, kitchens, Taverns, Granaries, Granges, Yards), logistics, "
              "improvements, goods producers; other = everything else.")
    sec.table("Levels added per kind", by_kind, _write_csv(by_kind, out, "levels_by_kind.csv"))
    key = "plan_extra" if "plan_extra" in by_type.columns else "run_added"
    top = by_type.sort(key, descending=True).head(15)
    sec.chart(f"Building types: {'plan extra over the baseline' if key == 'plan_extra' else 'levels added'} (top 15)",
              chart_grouped_barh(top, "building_type", [(key, key.replace('_', ' '))], out, "levels_top_types",
                                 "building levels"))
    sec.table("Levels added per building type", by_type, _write_csv(by_type, out, "levels_by_type.csv"), rows=50)
    total_added = float(by_type["run_added"].sum()) if by_type.height else 0.0
    if key == "plan_extra":
        extra = float(by_type["plan_extra"].sum())
        tiles.append(("Plan extra levels", f"{extra:+,.0f}", f"run {total_added:+,.0f}, baseline "
                      f"{float(by_type['baseline_added'].sum()):+,.0f} ({cmp.run_last.date})"))
    else:
        tiles.append(("Levels added", f"{total_added:+,.0f}", f"{cmp.run_first.date} to {cmp.run_last.date}"))
    if cmp.base_last is not None and abs(cmp.run_last.year - cmp.base_last.year) > 0.01:
        sec.note(f"The run has no save at the baseline's last date {cmp.base_last.date}; compared with "
                 f"{cmp.run_last.name} ({cmp.run_last.date}).")
    sections.append(sec)

    # 3. location profiles
    sec = Section("profiles", "Location profiles",
                  "Profile slots from the location variable pp_lprof (slot + 100); each rule's state after the last "
                  "pass (pp_lprof_r<r>_st) and the shortest payback it found (pp_lprof_r<r>_est, years). A profile "
                  "rule's target good is a scope variable, which the save tables leave out.")
    slots = first_assignment(run)
    if slots.is_empty():
        sec.note("No location has a profile in any save of the run.")
    else:
        rows = []
        for label, snap in series:
            mine = profile_assignment(snap).filter(pl.col("location_id").is_in(list(owned(snap, tag))))
            for slot, n in mine.group_by("slot").len().sort("slot").iter_rows():
                rows.append({"series": label, "save": snap.name, "slot": slot, "locations": n})
        per_save = pl.DataFrame(rows, schema={"series": pl.Utf8, "save": pl.Utf8, "slot": pl.Int64,
                                              "locations": pl.Int64})
        sec.table("Profile locations per save", per_save, _write_csv(per_save, out, "profile_locations.csv"))
        all_states = pl.concat([rule_states(s, tag).with_columns(pl.lit(s.name).alias("save")) for s in run],
                               how="vertical_relaxed")
        all_states.write_csv(out / "profile_rule_states.csv")
        last = run[-1]
        st_last = rule_states(last, tag)
        sec.chart(f"Rule states after the last pass, {last.name}", chart_rule_states(st_last, out))
        if st_last.height:
            wide = st_last.pivot(on="state_name", index=["slot", "rule"], values="locations",
                                 aggregate_function="sum").fill_null(0).sort("slot", "rule")
            names = st_last.sort("state")["state_name"].unique(maintain_order=True).to_list()
            wide = wide.select("slot", "rule", *names)
            sec.table(f"Rule states in {last.name} (locations)", wide, "profile_rule_states.csv",
                      text="All saves in the CSV.")
        pb = pl.concat([rule_paybacks(s, tag).with_columns(pl.lit(s.name).alias("save")) for s in run],
                       how="vertical_relaxed")
        sec.table(f"Shortest payback found, {last.name}", rule_paybacks(last, tag),
                  _write_csv(pb, out, "profile_paybacks.csv"),
                  text="years; no profit = the rule found no level that makes a profit (1099).")
        pl_levels = profile_levels(cmp, tag, slots)
        sec.table("Levels added in profile locations and the rest (slot 0 = no profile)", pl_levels,
                  _write_csv(pl_levels, out, "profile_levels.csv"),
                  text=f"Slots as first assigned; {cmp.run_first.name} to {cmp.run_last.name}"
                       + (f", baseline {cmp.base_first.name} to {cmp.base_last.name} in the same locations."
                          if cmp.base_first is not None else "."))
    sections.append(sec)

    # 4. global rule groups
    sec = Section("global", "Global rule groups",
                  "What the food, logistics and improvement rules look at, in every save.")
    statuses = food_statuses(series, tag)
    if statuses is None:
        sec.note("Food: the save tables have no province variables, so the food rule's state per province "
                 "(pp_cplan_status) is not shown. The province stores below are the numbers it reads.")
    else:
        sec.table("Food rule state per province", statuses, _write_csv(statuses, out, "food_status.csv"))
    stores = food_stores(series, tag, settings)
    if stores.height:
        sec.chart("Provinces by stored months", chart_food_bands(stores, out),
                  f"Stored food over normal consumption. Famine line {settings.famine_months:g} months.")
        sec.table("Province food stores", stores, _write_csv(stores, out, "food_stores.csv"),
                  text=f"granary due: room below {settings.granary_months:g} months, at least "
                       f"{settings.granary_fill:.0%} full and gaining; grange due: {settings.granary_months:g}+ months "
                       f"and gaining {settings.grange_surplus:.0%} of consumption a month. Approximations on today's "
                       "store (the plan reads a year ahead without harvest and spoilage).")
    else:
        sec.note("Food: no province_food table in the saves.")
    access = market_access(series, tag, kinds, settings)
    if access.height:
        sec.chart(f"Locations below {settings.access_line:.0%} market access", chart_lines(
            access, "below_line", "locations", out, "market_access"))
        sec.table("Market access (owned and controlled locations)", access.drop("year"),
                  _write_csv(access, out, "market_access.csv"))
    fill = improvement_fill(series, tag, improve_fill_pct)
    if fill is None:
        sec.note("Improvements: a location's population capacity is not in the save tables, so locations at the fill "
                 "line cannot be counted. Improvement levels per save are in 'Building levels per save and kind'.")
    else:
        sec.table(f"Locations at {improve_fill_pct:g} % fill or more", fill, _write_csv(fill, out, "improve_fill.csv"))
    sections.append(sec)

    # 5. constructions
    sec = Section("constructions", "Constructions in progress",
                  "The country's constructions in each save (the plan's and the player's under 'country', estates' "
                  "under their estate). The same construction in two saves in a row that did not work every day "
                  f"between them (progress counts days): '{REASON_STUCK}' (nothing in its location moved), "
                  f"'{REASON_QUEUED}' (waiting behind another construction in the same location), "
                  f"'{REASON_SLOW}' (it moved, but {SLACK_DAYS:g}+ days less than it could). The save tables do not "
                  "say which goods a construction misses. Saves a year or less apart show this best: a construction "
                  "rarely lives through a 10-year gap.")
    stalled = stalled_constructions(run, tag)
    base_stalled = stalled_constructions(baseline, tag) if baseline else stalled.clear()
    counts = construction_counts(series, tag, pl.concat([stalled, base_stalled], how="vertical_relaxed"))
    sec.chart("Constructions in progress per save", chart_lines(counts, "in_progress", "constructions", out,
                                                                "constructions"))
    sec.table("Constructions per save", counts.drop("year"), _write_csv(counts, out, "constructions.csv"))
    detail = pl.concat([constructions(s, tag).with_columns(pl.lit(lab).alias("series"), pl.lit(s.name).alias("save"))
                        for lab, s in series], how="vertical_relaxed")
    detail.write_csv(out / "constructions_detail.csv")
    if detail.height:
        by_type_c = (detail.group_by("series", "save", "building_type").len("constructions")
                     .sort(["series", "save", "constructions", "building_type"], descending=[True, False, True, False]))
        sec.table("Constructions per save and building type", by_type_c, "constructions_detail.csv", rows=40)
    sec.table("Constructions held up between saves (run)", stalled,
              _write_csv(stalled, out, "stalled_constructions.csv"), rows=60)
    stuck = stalled.filter(pl.col("reason") == REASON_STUCK).height
    tiles.append(("Stuck constructions", f"{stuck}",
                  f"{stalled.height - stuck} more queued or held up part of the time"))
    sections.append(sec)

    # 6. errors
    sec = Section("errors", "Errors",
                  f"error.log lines that mention the plan ({', '.join(ERROR_PATTERNS)}), grouped by message with the "
                  "wall clock stripped.")
    if error_lines is None:
        sec.note("No error log read.")
    else:
        total, errors = error_summary(error_lines, console=console_seconds(debug_lines) if debug_lines else None)
        game = errors.filter(pl.col("source") == "game") if errors.height else errors
        console = errors.filter(pl.col("source") != "game") if errors.height else errors
        game_n = int(game["count"].sum()) if game.height else 0
        console_n = int(console["count"].sum()) if console.height else 0
        sec.note(f"{game_n} plan entries from the game ({game.height} different) and {console_n} from console run files "
                 f"(the console's description pass, not the monthly pass) of {total:,} error entries in "
                 f"{error_source or 'the error log'}.")
        sec.table("Plan entries in error.log", errors, _write_csv(errors, out, "errors.csv"), rows=40)
        tiles.append(("Plan errors", f"{game_n}", f"in the game; {console_n} from console run files; {total:,} entries in all"))
    sections.append(sec)
    if speed_total.get("s_per_year"):
        tiles.append(("Speed", f"{speed_total['s_per_year']:.1f} s", "wall clock per game year (log)"))

    title = "Construction Plan test"
    lead = (f"{tag}: run {', '.join(s.name for s in run)}"
            + (f"; baseline {', '.join(s.name for s in baseline)}" if baseline else "; no baseline")
            + (f". Log {debug_source}." if debug_source else "."))
    page = out / "index.html"
    page.write_text(render_html(title, lead, tiles, sections), encoding="utf-8")
    (out / "summary.md").write_text(render_markdown(title, lead, tiles, sections), encoding="utf-8")
    log(f"plan-report: {tag}, {len(run)} run saves, {len(baseline)} baseline saves -> {page}")
    return page


def read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
