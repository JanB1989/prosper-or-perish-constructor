"""Propagate paired annual crop evidence through existing physical accounts."""
import argparse
import gc
import json
from pathlib import Path
import numpy as np
import polars as pl
from prosper_or_perish_population_capacity import carrying_capacity as cc
from prosper_or_perish_constructor.simulation.cache import fingerprint
ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "artifacts/data/population_capacity"
OUT = SOURCE / "repair_round_37"


def run(case):
    folders = {"cached_replay": SOURCE / "pyaez_1337/crop_risk_scenarios",
        "fresh_baseline": OUT / "baseline_crop_risk_scenarios", "historical_exclusion": OUT / "crop_risk_scenarios"}
    original_path = SOURCE / "current_capacity_map/location_candidates.parquet"
    physical_path = SOURCE / "physical_parameter_scenarios.parquet"
    candidates = pl.read_parquet(original_path)
    crops, crop_hash = cc.load_crop_risk_scenario_artifacts(folders[case])
    physical = pl.read_parquet(physical_path)
    scenarios, contract = cc.build_joint_capacity_scenarios(candidates, crops,
        crop_risk_manifest_hash=crop_hash, scale_factor=1., physical_parameter_scenarios=physical)
    del crops, physical
    gc.collect()
    revised = cc.apply_joint_capacity_scenario_quantiles(candidates, scenarios)
    from prosper_or_perish_constructor.simulation.scenario_evidence import select_joint_land_evidence, verify_joint_land_evidence
    verify_joint_land_evidence(select_joint_land_evidence(scenarios), revised)
    output = OUT / case
    output.mkdir(parents=True, exist_ok=True)
    residuals = {}
    for q in ("p10", "p50", "p90"):
        column = f"rainfed_crop_capacity_people_{q}"
        values = candidates.select("location_tag",column).join(revised.select("location_tag",column),on="location_tag",suffix="_new",validate="1:1")
        residuals[column] = float((values[column] - values[column+"_new"]).abs().max())
        if case == "cached_replay" and not np.allclose(values[column], values[column+"_new"], rtol=1e-10, atol=1e-6):
            (output / "replay_failure.json").write_text(json.dumps(dict(model_accepted=False,
                failed_column=column, maximum_absolute_residual=residuals[column],
                explanation="Post-optimization allocations are not proven to reconstruct original input caps."),indent=2)+"\n")
            raise ValueError(f"Original crop source does not replay: {column}, residual {residuals[column]}")
    scenarios.write_parquet(output / "capacity_scenarios.parquet")
    del scenarios
    gc.collect()
    labels_path = SOURCE / "crop_mode_labels.parquet"
    if case == "historical_exclusion":
        labels_path = OUT / "crop_history/crop_mode_labels.parquet"
        primary = pl.read_parquet(labels_path).filter(pl.col("engine") == "gaez_v5")
        sampled = cc._build_gaez_sample_system_frame(labels_path, primary)
        if sampled is None:
            raise ValueError("Missing physical sample system")
        columns = [c for c in sampled.columns if c != "location_tag"]
        revised = revised.drop([c for c in columns if c in revised.columns]).join(sampled,on="location_tag",how="left",validate="1:1")
    revised.write_parquet(output / "location_candidates.parquet")
    (output / "capacity_scenario_contract.json").write_text(json.dumps(contract,indent=2)+"\n")
    identity = fingerprint([__file__,Path(cc.__file__),original_path,physical_path,labels_path,
        folders[case] / "crop_risk_scenarios.manifest.json", folders[case] / "crop_system_scenarios.parquet"], {"case":case})
    report = dict(case=case,model_accepted=False,game_export_ready=False,input_fingerprint=identity,
        crop_residuals_from_cached_candidate=residuals,location_count=revised.height,
        interpretation="Preserved physical optimization and source calendar; direct historical model removes its reference calendar/development effects as before. No population fitting.")
    (output / "manifest.json").write_text(json.dumps(report,indent=2)+"\n")
    print(report,flush=True)


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case",choices=["cached_replay","fresh_baseline","historical_exclusion"],required=True)
    run(parser.parse_args().case)
