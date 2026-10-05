"""``ppc worldbuilder apply``: consume the World Builder handover and write the mod inputs.

Order: geography sync -> attribute rows (class injects, static modifiers, rivers, goods floor,
overpopulation, on_action) -> improvement caps and blueprints -> farm blueprints -> game-start setup
(improvement levels, game-start development: vanilla's rules, development_geography). Blueprint edits are rendered by the normal ``ppc build``.
"""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl

from prosper_or_perish_constructor.location_baseline import resolve_load_order_path
from prosper_or_perish_constructor.setup_layout import LEGACY_SETUP_DIR, check_setup_folder
from prosper_or_perish_constructor.worldbuilder import buildings as wb_buildings
from prosper_or_perish_constructor.worldbuilder import compat as wb_compat
from prosper_or_perish_constructor.worldbuilder import development as wb_development
from prosper_or_perish_constructor.worldbuilder import geography as wb_geography
from prosper_or_perish_constructor.worldbuilder import modifiers as wb_modifiers
from prosper_or_perish_constructor.worldbuilder import start_placement as wb_start
from prosper_or_perish_constructor.worldbuilder.contract import Contract, WorldBuilderConfig, load_config, load_contract

REPORT_RELATIVE_PATH = Path("artifacts/data/worldbuilder/apply_report.json")


def vanilla_root(repo: Path, project: Path) -> Path:
    import tomllib

    raw = tomllib.loads(project.read_text(encoding="utf-8"))
    parser = raw.get("parser") if isinstance(raw.get("parser"), dict) else {}
    load_order = repo / str(parser.get("load_order") or "constructor.load_order.toml")
    from eu5gameparser.load_order import read_load_order

    lo = read_load_order(load_order)
    return resolve_load_order_path(str(lo["paths"]["vanilla_root"]), load_order.parent)



def apply(repo: Path, project: Path, mod_root: Path, *, contract_root: Path | None = None) -> dict[str, object]:
    cfg: WorldBuilderConfig = load_config(repo, project)
    contract: Contract = load_contract(contract_root or cfg.handover)
    from . import navigation
    # every setup file below goes into the active bookmark's setup folder; the pre-1.4 folder is no longer read
    check_setup_folder(vanilla_root(repo, project) / "game", mod_root)
    report: dict[str, object] = {"handover": str(contract.root), "version": contract.version, "worldbuilder_commit": contract.meta.get("worldbuilder_commit")}
    if cfg.sync_geography:
        report["geography"] = wb_geography.sync_geography(cfg.geography_export, mod_root, repo)
    # channel tiles take the topography of their navigation state (Navigable River, Shallows, Falls)
    if cfg.raw.get("navigation_config"):
        nav_settings = json.loads((repo / str(cfg.raw["navigation_config"])).read_text(encoding="utf-8"))
        if nav_settings.get("enabled") and nav_settings.get("topographies"):
            report["channel_topographies"] = navigation.write_topographies(mod_root, vanilla_root(repo, project), contract, nav_settings, repo)
    # water access from the mod's own map: the Sea Coast modifier, gates and start model follow the game's sea coast
    from . import coast

    water = coast.load(repo, mod_root, vanilla_root(repo, project))
    contract = coast.with_sea_coast(contract, water)
    # game-start development = vanilla's rules on the configured map (after the geography sync); every step below (navigation
    # sites, improvement caps at start, start placement) reads it instead of the handover's development
    development = wb_development.compute_start_development(repo, project)
    report["development_vs_handover"] = wb_development.handover_difference(contract, development)
    contract = wb_development.with_development(contract, development)
    import dataclasses

    cfg = dataclasses.replace(cfg, raw={**cfg.raw, "_water_access": water})
    report["water_access"] = {state: sum(1 for v in water.values() if v == state) for state in ("sea_coast", "waterway")}
    coast.write_runtime(mod_root)
    report["class_injects"] = wb_modifiers.write_class_injects(contract, cfg.geography_export, mod_root, repo, vanilla_root(repo, project))
    if cfg.compat_files:
        families = wb_compat.load_families(cfg.geography_export)
        report["compat_patches"] = wb_compat.write_compat_patches(vanilla_root(repo, project), mod_root, repo, families, cfg.compat_files)
    # terrain look: the World Builder classes and channel topographies take their vanilla parent's biome
    from . import biomes

    channels = []
    if cfg.raw.get("navigation_config"):
        nav = json.loads((repo / str(cfg.raw["navigation_config"])).read_text(encoding="utf-8"))
        if nav.get("enabled"):
            channels = [str(t["key"]) for t in (nav.get("topographies") or {}).values()]
    if cfg.raw.get("terrain_biomes"):
        report["biomes"] = biomes.write(vanilla_root(repo, project), mod_root, wb_compat.load_families(cfg.geography_export),
                                        channels, biomes.load_design(repo / str(cfg.raw["terrain_biomes"])))
    # vanilla scripts that route fleets over the open sea must not pick a river channel (after the widening above)
    from . import navigation_scripts

    report["navigation_scripts"] = navigation_scripts.write(vanilla_root(repo, project), mod_root, repo,
                                                           navigation_scripts.load(cfg.raw.get("navigation_scripts")), cfg.compat_files)
    from prosper_or_perish_constructor.location_baseline import load_current_location_frame

    current = load_current_location_frame(repo, project)
    cfg = navigation.prepare(repo, cfg, contract, locations=current)
    report["static_modifiers"] = wb_modifiers.write_static_modifiers(contract, cfg, mod_root, vanilla_root(repo, project))
    # the geography chips' tooltips (attribute_tooltips.py) and the location window are written in finalize (location_view.py)
    # raw-material placement is the mod's: the goods lose vanilla's location_potential (EU5 1.4), the Columbian exchange
    # actions test the mod's placement rules instead
    from . import raw_material_placement

    report["raw_material_placement"] = raw_material_placement.write(mod_root, vanilla_root(repo, project), repo)
    caps = wb_buildings.write_caps(contract, cfg, mod_root)
    report["improvement_buildings"] = {k: {"unit_units": v["unit_units"], "scale": v["scale"], "limit": v["limit"]} for k, v in caps.items()}
    report["blueprints_patched"] = wb_buildings.patch_improvement_blueprints(contract, cfg, repo, caps)
    leaks = wb_buildings.vanilla_capacity_leaks(repo, vanilla_root(repo, project))
    if leaks:
        raise ValueError("vanilla population capacity would leak through: " + "; ".join(f"{k}: {v}" for k, v in leaks.items()))
    report["vanilla_capacity_buildings"] = sorted(wb_buildings.vanilla_capacity_buildings(vanilla_root(repo, project)))
    from prosper_or_perish_constructor.rural_capacity import LAND_FARM_BUILDINGS

    report["farm_blueprints_patched"] = wb_buildings.patch_farm_blueprints(cfg, repo, list(LAND_FARM_BUILDINGS))
    # farm / fish / forest capacity script values from the same land constants
    import runpy

    runpy.run_path(str(repo / "scripts/generate_rural_capacity_values.py"), run_name="__main__")
    report["rural_capacity_values"] = "regenerated"
    # goods output map modes read the engine's own local_<good>_output_modifier
    runpy.run_path(str(repo / "scripts/generate_raw_material_local_map_modes.py"), run_name="__main__")
    report["goods_output_map_modes"] = "regenerated"
    start_cfg = wb_start.StartConfig.from_raw(cfg.raw.get("start") if isinstance(cfg.raw.get("start"), dict) else None)
    demand = wb_start.improvement_demand(contract, start_cfg, vanilla_root(repo, project), mod_root) if start_cfg.fill_improvements_to_pops else None
    cultures = wb_start.dominant_cultures(wb_start.load_pops(vanilla_root(repo, project)))
    report["setup"] = wb_buildings.write_setup(contract, cfg, caps, wb_start.load_owners(vanilla_root(repo, project), mod_root), mod_root, demand=demand, cultures=cultures)
    report["start_placement"] = wb_start.apply(repo=repo, project=project, mod_root=mod_root, vanilla_root=vanilla_root(repo, project), cfg=cfg, contract=contract, caps=caps, locations=current, development=development)
    report["navigation"] = navigation.write_runtime(repo, cfg, contract, mod_root, vanilla_root(repo, project))
    (mod_root / wb_development.SETUP_RELATIVE_PATH).write_text("﻿" + wb_development.render_development_setup(development, wb_development.configured_geography(repo, project)), encoding="utf-8", newline="\n")
    wb_development.write_development_export(development, repo / wb_development.EXPORT_RELATIVE_PATH)
    report["development"] = {"geography": wb_development.configured_geography(repo, project), "locations": int(development.height), "median": float(development["development"].median() or 0.0), "max": float(development["development"].max() or 0.0)}
    # the setup files are all written to the active setup folder now; a pre-1.4 copy would only be dead weight
    if (mod_root / LEGACY_SETUP_DIR).is_dir():
        import shutil

        shutil.rmtree(mod_root / LEGACY_SETUP_DIR)
    out = repo / REPORT_RELATIVE_PATH
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def export_development(repo: Path, project: Path) -> dict[str, object]:
    development = wb_development.compute_start_development(repo, project)
    path = repo / wb_development.EXPORT_RELATIVE_PATH
    wb_development.write_development_export(development, path)
    return {"path": str(path), "locations": int(development.height), "median": float(development["development"].median() or 0.0), "max": float(development["development"].max() or 0.0)}


def check(repo: Path, project: Path, mod_root: Path) -> dict[str, object]:
    """Recompute the capacity model from the constructor-side levels (setup file) and report the fit."""
    cfg = load_config(repo, project)
    contract = load_contract(cfg.handover)
    from .navigation import prepare
    from prosper_or_perish_constructor.location_baseline import load_current_location_frame
    locations = load_current_location_frame(repo, project) if cfg.raw.get("navigation_config") else None
    cfg = prepare(repo, cfg, contract, write_blueprints=False, locations=locations)
    setup = mod_root / wb_buildings.SETUP_PATH
    if not setup.is_file():
        raise FileNotFoundError(f"run ppc worldbuilder apply first: {setup}")
    import re

    rows = []
    for line in setup.read_text(encoding="utf-8-sig").splitlines():
        m = re.match(r"\s*(\w+) = \{ tag = \w+ level = (\d+) location = (\w+) \}", line)
        if m:
            rows.append({"building": m.group(1), "starting_levels": int(m.group(2)), "location_tag": m.group(3)})
    levels = pl.DataFrame(rows)
    scales = {kind: float(cfg.level_scale.get(key, cfg.level_scale.get(kind, 1.0))) for kind, key in cfg.building_map.items()}
    from prosper_or_perish_constructor.worldbuilder.contract import units

    people = {cfg.building_map[str(r["building"])]: units(float(r["unit_people_per_level"]) / scales.get(str(r["building"]), 1.0)) * 1000 for r in contract.building_types.iter_rows(named=True)}
    for key, spec in cfg.niche.items():
        row = next(r for r in contract.building_types.iter_rows(named=True) if cfg.building_map[str(r["building"])] == spec["family"])
        people[key] = units(float(row["unit_people_per_level"]) / scales[str(row["building"])] * float(spec["strength"])) * 1000
    c = float(contract.meta["attributes"].get("capacity_percent_per_point", 0.0))
    # the development the game starts with is the one the last apply wrote (vanilla's rules, development_geography)
    shipped = repo / wb_development.EXPORT_RELATIVE_PATH
    if shipped.is_file():
        contract = wb_development.with_development(contract, pl.read_csv(shipped, schema={"location_tag": pl.String, "development": pl.Float64}))
    targets = contract.location_targets
    start = levels.group_by("location_tag").agg((pl.col("starting_levels") * pl.col("building").replace_strict(people, default=0.0)).sum().alias("start_people"))
    joined = targets.join(start, on="location_tag", how="left").with_columns(pl.col("start_people").fill_null(0.0))
    model = (joined["attribute_flat_people"] + joined["start_people"]) * (1 + c * joined["development"]) + contract.people_per_development_point * joined["development"]
    target = joined["starting_target_people"]
    err = (model - target)
    rel = (err.abs() / target.clip(1.0))
    ss = float(((target - target.mean()) ** 2).sum())
    return {"locations": int(joined.height), "r2": float(1 - (err ** 2).sum() / ss) if ss else None, "median_error_percent": float(rel.median() * 100), "total_model": float(model.sum()), "total_target": float(target.sum()), "note": "Starting model from the setup file's levels (owned locations only) against the World Builder targets."}
