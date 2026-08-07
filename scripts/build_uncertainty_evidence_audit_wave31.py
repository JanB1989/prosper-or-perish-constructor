"""Build the independent uncertainty-evidence audit for wave31."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from prosper_or_perish_population_capacity.uncertainty_evidence_audit import (
    build_uncertainty_evidence_audit,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bahs", type=Path, required=True)
    parser.add_argument("--faostat", type=Path, required=True)
    parser.add_argument("--gdhy", type=Path, required=True)
    parser.add_argument("--isimip", type=Path, required=True)
    parser.add_argument("--drought-atlas", type=Path, required=True)
    parser.add_argument("--lut-inventory", type=Path, required=True)
    parser.add_argument("--crop-bridge", type=Path, required=True)
    parser.add_argument("--historical-registry", type=Path, required=True)
    parser.add_argument("--climate-registry", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = build_uncertainty_evidence_audit(
        source_paths={
            "bahs": args.bahs,
            "faostat": args.faostat,
            "gdhy": args.gdhy,
            "isimip": args.isimip,
            "drought_atlas": args.drought_atlas,
        },
        lut_inventory_path=args.lut_inventory,
        crop_bridge_path=args.crop_bridge,
        historical_registry_path=args.historical_registry,
        climate_registry_path=args.climate_registry,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    # This is an evidence audit, not an acceptance operation.  It returns
    # non-zero until all source contracts themselves are resolved.
    return 0 if report["state"] == "resolved" else 1


if __name__ == "__main__":
    raise SystemExit(main())

