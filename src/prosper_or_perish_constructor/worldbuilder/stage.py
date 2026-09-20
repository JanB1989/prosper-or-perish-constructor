"""``ppc worldbuilder apply``: consume the World Builder handover and write the mod inputs.

Order: geography sync -> attribute rows (class injects, static modifiers, rivers, goods floor,
overpopulation, on_action) -> improvement caps and blueprints -> farm blueprints -> game-start setup
(improvement levels, vanilla development). Blueprint edits are rendered by the normal ``ppc build``.
"""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl

from prosper_or_perish_constructor.location_baseline import resolve_load_order_path
from prosper_or_perish_constructor.worldbuilder import buildings as wb_buildings
from prosper_or_perish_constructor.worldbuilder import compat as wb_compat
from prosper_or_perish_constructor.worldbuilder import development as wb_development
from prosper_or_perish_constructor.worldbuilder import geography as wb_geography
from prosper_or_perish_constructor.worldbuilder import modifiers as wb_modifiers
from prosper_or_perish_constructor.worldbuilder.contract import Contract, WorldBuilderConfig, load_config, load_contract

REPORT_RELATIVE_PATH = Path("artifacts/data/worldbuilder/apply_report.json")


def vanilla_root(repo: Path, project: Path) -> Path:
    import tomllib

    raw = tomllib.loads(project.read_text(encoding="utf-8"))
    parser = raw.get("parser") if isinstance(raw.get("parser"), dict) else {}
    load_order = repo / str(parser.get("load_order") or "constructor.load_order.toml")
    lo = tomllib.loads(load_order.read_text(encoding="utf-8"))
    return resolve_load_order_path(str(lo["paths"]["vanilla_root"]), load_order.parent)


def start_owners(repo: Path) -> dict[str, str]:
    """location tag -> owning country tag at game start (vanilla setup)."""
    from prosper_or_perish_constructor.food_building_startup import _load_start_location_owners, load_food_startup_config

    frame = _load_start_location_owners(load_food_startup_config(repo))
    tag_column = "slug" if "slug" in frame.columns else "location_tag"
    return {str(tag): str(owner) for tag, owner in frame.select(tag_column, "country_tag").iter_rows() if owner}


def apply(repo: Path, project: Path, mod_root: Path, *, contract_root: Path | None = None) -> dict[str, object]:
    cfg: WorldBuilderConfig = load_config(repo, project)
    contract: Contract = load_contract(contract_root or cfg.handover)
    report: dict[str, object] = {"handover": str(contract.root), "version": contract.version, "worldbuilder_commit": contract.meta.get("worldbuilder_commit")}
    if cfg.sync_geography:
        report["geography"] = wb_geography.sync_geography(cfg.geography_export, mod_root, repo)
    report["class_injects"] = wb_modifiers.write_class_injects(contract, cfg.geography_export, mod_root, repo, vanilla_root(repo, project))
    if cfg.compat_files:
        families = wb_compat.load_families(cfg.geography_export)
        report["compat_patches"] = wb_compat.write_compat_patches(vanilla_root(repo, project), mod_root, repo, families, cfg.compat_files)
    from prosper_or_perish_constructor.location_baseline import load_current_location_frame

    current = load_current_location_frame(repo, project)
    rgo_by_location = {str(tag): str(rgo) for tag, rgo in current.select("location_tag", "raw_material").iter_rows() if rgo}
    report["static_modifiers"] = wb_modifiers.write_static_modifiers(contract, cfg, mod_root, vanilla_root(repo, project), rgo_by_location)
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
    report["setup"] = wb_buildings.write_setup(contract, cfg, caps, start_owners(repo), mod_root)
    development = wb_development.compute_vanilla_development(repo, project)
    (mod_root / wb_development.SETUP_RELATIVE_PATH).write_text("﻿" + wb_development.render_development_setup(development), encoding="utf-8", newline="\n")
    wb_development.write_development_export(development, repo / wb_development.EXPORT_RELATIVE_PATH)
    report["development"] = {"locations": int(development.height), "median": float(development["development"].median() or 0.0), "max": float(development["development"].max() or 0.0)}
    out = repo / REPORT_RELATIVE_PATH
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def export_development(repo: Path, project: Path) -> dict[str, object]:
    development = wb_development.compute_vanilla_development(repo, project)
    path = repo / wb_development.EXPORT_RELATIVE_PATH
    wb_development.write_development_export(development, path)
    return {"path": str(path), "locations": int(development.height), "median": float(development["development"].median() or 0.0), "max": float(development["development"].max() or 0.0)}


def check(repo: Path, project: Path, mod_root: Path) -> dict[str, object]:
    """Recompute the capacity model from the constructor-side levels (setup file) and report the fit."""
    cfg = load_config(repo, project)
    contract = load_contract(cfg.handover)
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
    inverse = {v: k for k, v in cfg.building_map.items()}
    levels = levels.with_columns(pl.col("building").replace_strict(inverse, default=None).alias("kind")).drop_nulls("kind")
    scales = {kind: float(cfg.level_scale.get(key, cfg.level_scale.get(kind, 1.0))) for kind, key in cfg.building_map.items()}
    caps = {str(r["building"]): float(r["unit_people_per_level"]) / scales.get(str(r["building"]), 1.0) for r in contract.building_types.iter_rows(named=True)}
    c = float(contract.meta["attributes"].get("capacity_percent_per_point", 0.0))
    targets = contract.location_targets
    start = levels.group_by("location_tag").agg((pl.col("starting_levels") * pl.col("kind").replace_strict(caps, default=0.0)).sum().alias("start_people"))
    joined = targets.join(start, on="location_tag", how="left").with_columns(pl.col("start_people").fill_null(0.0))
    model = (joined["attribute_flat_people"] + joined["start_people"]) * (1 + c * joined["development"])
    target = joined["starting_target_people"]
    err = (model - target)
    rel = (err.abs() / target.clip(1.0))
    ss = float(((target - target.mean()) ** 2).sum())
    return {"locations": int(joined.height), "r2": float(1 - (err ** 2).sum() / ss) if ss else None, "median_error_percent": float(rel.median() * 100), "total_model": float(model.sum()), "total_target": float(target.sum()), "note": "Starting model from the setup file's levels (owned locations only) against the World Builder targets."}
