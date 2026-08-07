"""Audit official PyAEZ source/runtime versus the EU5 exact matrix."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import polars as pl
from prosper_or_perish_population_capacity.pyaez_exact_engine_audit import (
    audit_exact_engine_coverage,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--smoke-receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--matrix-output", type=Path)
    args = parser.parse_args()
    audit = audit_exact_engine_coverage(
        args.labels,
        source_root=args.source_root,
        smoke_receipt_path=args.smoke_receipt,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.matrix_output is not None:
        args.matrix_output.parent.mkdir(parents=True, exist_ok=True)
        pl.DataFrame(audit.get("crop_mode_matrix", [])).write_parquet(args.matrix_output)
    print(json.dumps(audit, indent=2, sort_keys=True))
    # This diagnostic intentionally remains non-zero until the exact EU5
    # matrix is complete; callers must not mistake a package smoke pass for
    # challenger readiness.
    return 0 if audit["exact_engine_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
