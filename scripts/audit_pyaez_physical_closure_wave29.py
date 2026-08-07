"""Synthesize the strict wave29 PyAEZ physical closure gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from prosper_or_perish_population_capacity.pyaez_physical_closure import audit_physical_closure


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exact-audit", type=Path, required=True)
    parser.add_argument("--uncertainty-audit", type=Path, required=True)
    parser.add_argument("--constraint-audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit_physical_closure(
        exact_engine_audit_path=args.exact_audit,
        uncertainty_audit_path=args.uncertainty_audit,
        constraint_source_audit_path=args.constraint_audit,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["exact_pyaez_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

