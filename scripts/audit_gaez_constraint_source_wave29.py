"""Inventory official GAEZ agro-climatic constraint source coverage.

This is intentionally an inventory, not a parser that invents PyAEZ runtime
tables.  It records which registered crop names occur in the official PDF and
whether the extracted text is sufficiently tabular for a future exact mapping.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from prosper_or_perish_population_capacity.pyaez_constraint_source_audit import (
    audit_gaez_constraint_source,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    pdf = args.pdf
    report = audit_gaez_constraint_source(pdf)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
