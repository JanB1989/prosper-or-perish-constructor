"""Write config/start_laborers.csv: per owned location, the RGO's size and the laborers that work in no building.

Why (job_room.py, AGENTS.md "Job Room"): with laborers under the job room rule every laborer takes room, and the game
sizes the classes at game start once, with the laborers the pops setup holds. The setup therefore has to hold the
laborers that are not building workers: the RGO's workers and its spare half place. This file is the reference for
that, read by the World Builder stage when it writes the pops setup.

Run it on a save about a month into a new game WITHOUT the laborer rule, or on any new game for the rgo_level column
alone (--levels-only keeps the free_laborers column of the file as it is):

    uv run python tools/start_laborers.py --save SP_Observer_1337_05_02_<id>

Columns: location, rgo_level (the RGO's size in thousands of workers, whole levels at game start), free_laborers
(thousands: the location's laborers minus those at work in buildings), slaves (thousands). free_laborers caps the
setup's laborers only where the location has slaves: they do the RGO's work first, and the game's start leaves the
laborers out there.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import polars as pl

REPO = Path(__file__).resolve().parents[1]
TARGET = REPO / "config" / "start_laborers.csv"


def laborer_jobs() -> pl.DataFrame:
    from prosper_or_perish_constructor import building_footprint as bf
    from prosper_or_perish_constructor import job_room
    from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

    mod_root = REPO / "mod" / "pp"
    vr = vanilla_root(REPO, REPO / "constructor.toml")
    owners = bf.owner_blocks(mod_root, vr)
    vanilla = bf.vanilla_definitions(vr)
    rows = []
    for key, block in sorted(owners.items()):
        text = bf._read(block.path)
        body = text[block.open + 1: block.close]
        inherited = vanilla.get(key, "") if block.mode in bf._INJECT_MODES else ""
        tops = bf._depth_zero_text(body) + "\n" + (bf._depth_zero_text(inherited) if inherited else "")
        pop = job_room._POP_RE.search(tops)
        if pop and pop.group("pop") == "laborers":
            rows.append(key)
    return pl.DataFrame({"building_type": rows})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--save", required=True, help="save name (as eu5q takes it), about a month into a new game")
    parser.add_argument("--levels-only", action="store_true", help="refresh rgo_level only; keep the file's free_laborers")
    args = parser.parse_args()
    from eu5gameparser.savegame import quick

    x = quick.load(args.save)
    date = str(x._read("metadata")["date"][0])
    loc = x.locations.filter((pl.col("total_population") > 0) & pl.col("country_tag").is_not_null() & (pl.col("country_tag") != ""))
    at_work = (x.buildings.filter(pl.col("level") > 0).join(laborer_jobs(), on="building_type", how="inner")
               .group_by("location_id").agg(at_work=pl.col("employed").fill_null(0.0).sum()))
    table = (loc.join(at_work, on="location_id", how="left").with_columns(pl.col("at_work").fill_null(0.0))
             .select(location="slug", rgo_level=pl.col("max_raw_material_workers").fill_null(0.0),
                     free_laborers=(pl.col("population_laborers").fill_null(0.0) - pl.col("at_work")).clip(lower_bound=0.0),
                     slaves=pl.col("population_slaves").fill_null(0.0))
             .sort("location"))
    old: dict[str, str] = {}
    if args.levels_only and TARGET.is_file():
        with TARGET.open(encoding="utf-8", newline="") as handle:
            old = {row["location"]: row["free_laborers"] for row in csv.DictReader(handle)}
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    with TARGET.open("w", encoding="utf-8", newline="\n") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["location", "rgo_level", "free_laborers", "slaves"])
        for location, level, free, slaves in table.iter_rows():
            writer.writerow([location, f"{level:g}", old.get(location, f"{free:.3f}"), f"{slaves:.3f}"])
    print(f"{TARGET.relative_to(REPO)}: {table.height} owned locations from {args.save} ({date}); RGO size "
          f"{table['rgo_level'].sum():.0f} k, laborers outside buildings {table['free_laborers'].sum():.0f} k")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
