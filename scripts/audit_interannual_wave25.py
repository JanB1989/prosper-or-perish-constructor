"""Audit the wave-25 interannual source manifest."""

from __future__ import annotations

import json
from pathlib import Path

from prosper_or_perish_population_capacity.interannual_source_coverage import (
    audit_source_acquisition_manifest,
)


if __name__ == "__main__":
    path = Path(__file__).resolve().parents[1] / "research/population_capacity/physical_validation/interannual_source_acquisition_wave25.json"
    print(json.dumps(audit_source_acquisition_manifest(path), indent=2, sort_keys=True))
