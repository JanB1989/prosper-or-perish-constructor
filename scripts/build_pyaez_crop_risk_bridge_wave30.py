"""Build the source-backed crop-specific GAEZ risk bridge audit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import polars as pl

from prosper_or_perish_population_capacity.pyaez_crop_risk_bridge import (
    build_crop_risk_bridge,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--lut-registry", type=Path, required=True)
    parser.add_argument("--water-source", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--matrix", type=Path, required=True)
    args = parser.parse_args()
    report = build_crop_risk_bridge(
        labels_path=args.labels,
        lut_registry_path=args.lut_registry,
        water_source_path=args.water_source,
    )
    matrix = report.pop("crop_mode_matrix")
    args.audit.parent.mkdir(parents=True, exist_ok=True)
    args.matrix.parent.mkdir(parents=True, exist_ok=True)
    args.audit.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    pl.DataFrame(matrix).write_parquet(args.matrix)
    print(json.dumps(report, indent=2, sort_keys=True))
    # This bridge is intentionally diagnostic-only: it is not exact PyAEZ and
    # must not unlock acceptance while unresolved families remain.
    return 0 if report["exact_pyaez_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

