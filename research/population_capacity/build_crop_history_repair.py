"""Build an isolated, source-pinned South American cereal-exclusion candidate."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tomllib
import numpy as np
import polars as pl
import shapely
from pyogrio.raw import read as read_ogr
from prosper_or_perish_population_capacity.crop_history import load_crop_history_registry, build_crop_history_location_frame

ROOT = Path(__file__).resolve().parents[2]
CROPS = ["wheat", "barley", "rye", "rice_dry", "rice_wet"]


def build(output):
    evidence = json.loads((ROOT / "research/population_capacity/crop_availability_repair_evidence.json").read_text())
    source = ROOT / evidence["local_path"]
    if hashlib.sha256(source.read_bytes()).hexdigest() != evidence["sha256"]:
        raise ValueError("Historical source checksum mismatch")
    original = ROOT / "population_capacity_crop_history_registry.toml"
    raw = tomllib.loads(original.read_text())
    boundary = ROOT / "artifacts/data/population_capacity/crop_history_sources/natural_earth_admin0/ne_50m_admin_0_countries.zip"
    if hashlib.sha256(boundary.read_bytes()).hexdigest() != raw["domains"]["boundary_object_sha256"]:
        raise ValueError("Boundary checksum mismatch")
    metadata, _, wkb, fields = read_ogr(boundary, columns=["CONTINENT"])
    if metadata["crs"] != "EPSG:4326":
        raise ValueError("Unexpected geometry CRS")
    geometry = shapely.make_valid(shapely.union_all(shapely.from_wkb(wkb)[np.asarray(fields[0]) == "South America"]))
    if geometry.is_empty or not geometry.is_valid:
        raise ValueError("Invalid historical exclusion geometry")
    spec = importlib.util.spec_from_file_location("crop_registry_compiler", ROOT / "scripts/build_population_capacity_crop_history_registry.py")
    compiler = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(compiler)
    domains = json.loads((ROOT / raw["domains"]["path"]).read_text())
    domains["features"].append(compiler._domain_feature(
        domain_id="post_1492_south_american_old_world_cereals", geometry=geometry, crops=CROPS,
        source_ids=[evidence["source_id"]], citation_urls=[evidence["url"]], source_hashes=[evidence["sha256"]],
        notes="FAO 1994, printed pp. 25 and 29: colonial introduction of wheat, barley, rye and rice. South America only in this staged correction; North America and Greenland require separate scoped review. Oryza keys do not represent Zizania. No positive crop adoption is inferred."))
    output.mkdir(parents=True, exist_ok=True)
    domain_path = output / "crop_history_domains.geojson"
    domain_path.write_text(json.dumps(domains, sort_keys=True, separators=(",", ":")) + "\n")
    text = original.read_text()
    for section, key in (("evidence", "path"), ("mapping", "path"), ("mapping", "audit_path")):
        old = raw[section][key]
        text = text.replace(f'{key} = "{old}"', f'{key} = "{os.path.relpath(ROOT / old, output)}"')
    text = text.replace(raw["domains"]["path"], domain_path.name)
    text = text.replace(raw["domains"]["sha256"], hashlib.sha256(domain_path.read_bytes()).hexdigest())
    text += "\n[[source]]\n" + "\n".join(f"{key} = {json.dumps(value)}" for key, value in dict(
        source_id=evidence["source_id"],title=evidence["title"],citation_url=evidence["url"],
        object_url=evidence["url"],object_sha256=evidence["sha256"],role="Dated negative crop availability; no population or yield fit").items()) + "\n"
    registry_path = output / "crop_history_registry.toml"
    registry_path.write_text(text)
    registry = load_crop_history_registry(registry_path, ROOT / raw["evidence"]["path"], expected_crops=[c["crop"] for c in raw["crop"]])
    checks = {"pisaq_inside": bool(shapely.intersects_xy(geometry, -71.85, -13.42)),
        "la_plata_inside": bool(shapely.intersects_xy(geometry, -58.38, -34.60)),
        "mexico_unchanged": not bool(shapely.intersects_xy(geometry, -99.13, 19.43)),
        "greenland_unchanged": not bool(shapely.intersects_xy(geometry, -45., 61.)),
        "old_world_unchanged": not bool(shapely.intersects_xy(geometry, 31.24, 30.04))}
    # Count against the original feature list, not registry metadata fields.
    checks["domain_added_once"] = len(registry.domains) == len(domains["features"])
    if not all(checks.values()):
        raise ValueError(checks)
    (output / "manifest.json").write_text(json.dumps(dict(model_accepted=False, applied_to_capacity=False,
        registry_sha256=hashlib.sha256(registry_path.read_bytes()).hexdigest(),
        source_sha256=evidence["sha256"], checks=checks,
        remaining="Rebuild labels and annual crop scenarios, then recalculate both current and potential support. North American scope remains separate."), indent=2) + "\n")
    config = tomllib.loads((ROOT / "population_capacity.toml").read_text())
    from prosper_or_perish_population_capacity.crop_labels import _location_frame
    locations = _location_frame(pl.read_parquet(ROOT / config["carrying_capacity"]["geometry"]))
    original_registry = load_crop_history_registry(original, ROOT / raw["evidence"]["path"], expected_crops=CROPS + [c["crop"] for c in raw["crop"] if c["crop"] not in CROPS])
    old_history = build_crop_history_location_frame(locations, original_registry, resolve_uncertain=True)
    new_history = build_crop_history_location_frame(locations, registry, resolve_uncertain=True)
    labels = pl.read_parquet(ROOT / "artifacts/data/population_capacity/crop_mode_labels.parquet")
    differences = labels.select("location_tag", "crop", "historical_availability").unique().join(
        old_history.select("location_tag", "crop", pl.col("historical_availability").alias("rebuilt_availability")),
        on=["location_tag", "crop"], how="left", validate="m:1").filter(
            pl.col("rebuilt_availability").is_null() | (pl.col("historical_availability") != pl.col("rebuilt_availability")))
    if differences.height:
        differences.write_csv(output / "baseline_replay_mismatches.csv")
        raise ValueError(f"Baseline history replay differs for {differences.height} crop/location rows")
    replaced = [c for c in new_history.columns if c in labels.columns and c not in ("location_tag", "crop")]
    corrected = labels.drop(replaced).join(new_history.select("location_tag", "crop", *replaced),
        on=["location_tag", "crop"], how="left", validate="m:1").select(labels.columns)
    if corrected.height != labels.height:
        raise ValueError("Crop label row count changed")
    corrected.write_parquet(output / "crop_mode_labels.parquet")
    delta = old_history.select("location_tag", "crop", pl.col("historical_availability").alias("before")).join(
        new_history.select("location_tag", "crop", pl.col("historical_availability").alias("after")), on=["location_tag", "crop"], validate="1:1").filter(pl.col("before") != pl.col("after"))
    if delta.filter(~pl.col("crop").is_in(CROPS) | (pl.col("after") != 0.)).height:
        raise ValueError("Correction changed an out-of-scope crop or added availability")
    delta.write_csv(output / "availability_changes.csv")
    manifest_path = output / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest.update(label_sha256=hashlib.sha256((output / "crop_mode_labels.parquet").read_bytes()).hexdigest(),
        baseline_availability_replay_mismatches=0, changed_crop_location_pairs=delta.height,
        changed_locations=delta["location_tag"].n_unique(),
        builder_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    sample_link = output / "crop_mode_samples"
    sample_target = ROOT / "artifacts/data/population_capacity/crop_mode_samples"
    if sample_link.exists():
        if sample_link.resolve() != sample_target.resolve():
            raise ValueError("Candidate sample link points at different physical data")
    else:
        sample_link.symlink_to(sample_target, target_is_directory=True)
    original_config = (ROOT / "population_capacity.toml").read_text()
    for suffix, label_path, risk_path in (
        ("", output / "crop_mode_labels.parquet", output.parent / "crop_risk_scenarios"),
        (".baseline", ROOT / "artifacts/data/population_capacity/crop_mode_labels.parquet", output.parent / "baseline_crop_risk_scenarios")):
        configured = original_config.replace(
            config["carrying_capacity"]["crop_mode_labels"], os.path.relpath(label_path, ROOT)).replace(
            config["carrying_capacity"]["crop_risk_scenarios_root"], os.path.relpath(risk_path, ROOT))
        (ROOT / f"population_capacity.round37{suffix}.local.toml").write_text(configured)
    print(f"Built {delta.height} changed crop/location availability values; no capacity accepted.")
    print(registry_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    build(parser.parse_args().output.resolve())
