"""Inspect the exact-engine input artifacts without changing them."""
from __future__ import annotations

from pathlib import Path

import polars as pl
import pandas as pd


def show(path: Path) -> None:
    print(path, path.stat().st_size)
    frame = pl.read_parquet(path)
    print("shape", frame.shape)
    print("columns", frame.columns)
    print(frame.head(2))


if __name__ == "__main__":
    root = Path("artifacts/data/population_capacity")
    for path in (
        root / "sources/pyaez_1337/all_samples/climate_inputs_600bp.parquet",
        root / "sources/pyaez_1337/gap_scope/sample_points.parquet",
        root / "sources/pyaez_1337/gap_scope/required_crop_modes.parquet",
        root / "pyaez_1337/crop_risk_scenarios/sample_axis.parquet",
        root / "crop_mode_labels.parquet",
        root / "crop_mode_samples/gaez_v5/maize_rainfed.parquet",
        root / "sources/pyaez_1337/gap_scope/on_land_soil_alignment.parquet",
        root / "location_land_potential.parquet",
    ):
        show(path)
    print("candidate soil/constraint columns:")
    for path in sorted(root.rglob("*.parquet")):
        try:
            schema = pl.scan_parquet(path).collect_schema()
        except Exception:
            continue
        columns = list(schema.names())
        if any(
            token in column.lower()
            for column in columns
            for token in ("available_water", "rootable", "constraint_factor", "soil_factor")
        ):
            print(path, columns)
    source = Path("artifacts/data/population_capacity/pyaez_1337/exact_engine_wave27/PyAEZ/data_input")
    for path in sorted(source.glob("*.xlsx")):
        sheets = pd.ExcelFile(path).sheet_names
        print("xlsx", path.name, sheets)
        for sheet in sheets[:3]:
            frame = pd.read_excel(path, sheet_name=sheet, header=None)
            print(" sheet", sheet, "shape", frame.shape, "head", frame.iloc[:4, :8].to_dict())
