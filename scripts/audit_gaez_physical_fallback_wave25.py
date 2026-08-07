"""Audit the complete same-geography GAEZ fallback and annual-risk receipt."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from prosper_or_perish_population_capacity.pyaez_fallback_audit import (
    audit_gaez_physical_fallback,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--geometry", type=Path, required=True)
    parser.add_argument("--scenario-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    audit = audit_gaez_physical_fallback(
        args.labels,
        geometry_path=args.geometry,
        scenario_manifest_path=args.scenario_manifest,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(audit, indent=2, sort_keys=True))
    return 0 if audit["state"] == "resolved" else 1


if __name__ == "__main__":
    raise SystemExit(main())
