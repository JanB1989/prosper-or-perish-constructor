"""Build the source-backed GAEZ parameter uncertainty coverage artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import polars as pl

from prosper_or_perish_population_capacity.pyaez_parameter_uncertainty import (
    build_parameter_uncertainty_coverage,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--samples-root", type=Path, required=True)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--official-source-audit", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    args = parser.parse_args()

    report = build_parameter_uncertainty_coverage(
        args.registry,
        args.samples_root,
        args.labels,
        official_source_audit_path=args.official_source_audit,
    )
    matrix = report.pop("crop_mode_matrix")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.audit.parent.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(matrix).write_parquet(args.output)
    args.audit.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    # This artifact intentionally remains diagnostic-only until exact PyAEZ
    # water/constraint contracts are independently resolved.
    return 0 if report["training_challenger_eligible"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
