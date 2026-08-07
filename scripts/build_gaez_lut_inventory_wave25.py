"""Materialize the source-backed GAEZ v5 LUT inventory for all 23 crops."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from prosper_or_perish_population_capacity.pyaez_crop_registry import (
    build_gaez_lut_registry,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--biomass", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    registry = build_gaez_lut_registry(args.biomass)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "schema_version": "gaez-v5-lut-inventory-audit-v1",
        "registry_path": str(args.output),
        "registry_sha256": registry["registry_sha256"],
        "crop_count": len(registry["crops"]),
        "lut_count": sum(len(crop["biomass_variants"]) for crop in registry["crops"]),
        "biomass_source_sha256": registry["sources"]["biomass"]["sha256"],
        "water_source_sha256": registry["sources"]["water"]["sha256"],
        "biomass_states": sorted({crop["biomass_state"] for crop in registry["crops"]}),
        "water_states": sorted({crop["water_parameter_state"] for crop in registry["crops"]}),
        "constraint_states": sorted({crop["constraint_state"] for crop in registry["crops"]}),
        "selection_policy": registry["selection_method"],
        "exact_pyaez_ready": False,
        "reason": "GAEZ v5 biomass LUT families are source-resolved for all registered crops; PyAEZ 2.2 water and crop/mode constraint mappings remain unresolved and this inventory is not an exact PyAEZ output.",
    }
    audit_path = args.output.with_name(args.output.stem + ".audit.json")
    audit_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
