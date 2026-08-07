"""Build the wave-25 area-weighted drought-atlas coverage artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from prosper_or_perish_population_capacity.interannual_source_coverage import (
    build_atlas_coverage,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=Path, required=True)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build_atlas_coverage(args.samples, args.sources, args.output)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["state"] == "resolved" else 1


if __name__ == "__main__":
    raise SystemExit(main())
