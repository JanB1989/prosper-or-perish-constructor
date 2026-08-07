"""Run the official PyAEZ 2.2 maize low-input example as a provenance smoke test.

This is intentionally not an EU5 label: the official repository ships only a
Laos maize/sugarcane tutorial parameter bundle.  The receipt proves the pinned
engine and bundled parameter path execute reproducibly; the separate exact
coverage audit decides whether any EU5 rows may be emitted.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import platform
import sys
import types
from pathlib import Path

import numpy as np
import pandas as pd


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    root = Path("artifacts/data/population_capacity/pyaez_1337/exact_engine_wave27/PyAEZ")
    data = root / "data_input"
    # Import the pinned source checkout, not an unrelated installed wheel.
    sys.path.insert(0, str(root.resolve()))
    if "gdal" not in sys.modules and "osgeo" not in sys.modules:
        sys.modules["gdal"] = types.ModuleType("gdal")
    from pyaez import CropSimulation

    params = pd.read_excel(data / "input_crop_TSUM_parameters_maiz_sugar.xlsx")
    maize_rows = params[params["Crop_name"].astype(str).str.lower() == "maize"]
    if maize_rows.empty:
        raise ValueError(f"official parameter workbook has no maize row: {params[['Crop_name', 'input_level']].to_dict('records')}")
    row = maize_rows.iloc[0]
    arrays = {
        name: np.load(data / "climate" / f"{name}.npy")
        for name in ("min_temp", "max_temp", "precipitation", "short_rad", "wind_speed", "relative_humidity")
    }
    # Tutorial arrays are [rows, columns, months]; use the first valid cell.
    shape = arrays["min_temp"].shape
    if len(shape) != 3 or shape[-1] != 12:
        raise ValueError(f"unexpected official climate array shape: {shape}")
    cell = (0, 0)
    monthly = {name: values[cell][None, None, :] for name, values in arrays.items()}
    simulation = CropSimulation.CropSimulation()
    simulation.setLocationTerrainData(18.0, 18.0, np.asarray([[100.0]], dtype=np.float64))
    simulation.setMonthlyClimateData(
        monthly["min_temp"], monthly["max_temp"], monthly["precipitation"],
        monthly["short_rad"], monthly["wind_speed"], monthly["relative_humidity"],
    )
    simulation.setCropParameters(
        LAI=float(row["LAI"]), HI=float(row["HI"]), legume=int(row["legume"]),
        adaptability=int(row["adaptability"]), cycle_len=int(row["cycle_len"]),
        D1=float(row["D1"]), D2=float(row["D2"]), min_temp=float(row["min_temp"]),
        aLAI=float(row["aLAI"]), bLAI=float(row["bLAI"]), aHI=float(row["aHI"]),
        bHI=float(row["bHI"]), min_cycle_len=int(row["min_cycle_len"]),
        max_cycle_len=int(row["max_cycle_len"]), plant_height=float(row["height"]),
    )
    simulation.setCropCycleParameters(
        stage_per=[float(row[f"stage_per_{i}"]) for i in range(1, 5)],
        kc=[float(row[f"kc_{i}"]) for i in range(3)], kc_all=float(row["kc_all"]),
        yloss_f=[float(row[f"yloss_f{i}"]) for i in range(4)],
        yloss_f_all=float(row["yloss_f_all"]),
    )
    simulation.perennial = False
    simulation.setSoilWaterParameters(Sa=np.asarray([[150.0]], dtype=np.float64), pc=0.5)
    lgpt5 = simulation.getThermalLGP5()
    lgpt10 = simulation.getThermalLGP10()
    lgp = simulation.getLGP(Sa=150.0, D=1.0)
    simulation.ImportLGPandLGPT(lgp, lgpt5, lgpt10)
    with contextlib.redirect_stdout(io.StringIO()):
        simulation.simulateCropCycle(1, 365, 1, False)
    rain = float(simulation.getEstimatedYieldRainfed()[0, 0])
    irr = float(simulation.getEstimatedYieldIrrigated()[0, 0])
    receipt = {
        "schema_version": "pyaez-official-runtime-smoke-v1",
        "engine": "PyAEZ 2.2",
        "source_commit": "b314640710a3ec398482b0065f4f26f45494eefa",
        "scope": "official_repository_Laos_tutorial_not_EU5",
        "crop": "maize",
        "input_level": "low",
        "rainfed_yield_kg_dm_ha": rain,
        "irrigated_yield_kg_dm_ha": irr,
        "official_parameter_sha256": sha256(data / "input_crop_TSUM_parameters_maiz_sugar.xlsx"),
        "official_climate_sha256": {
            name: sha256(data / "climate" / f"{name}.npy")
            for name in ("min_temp", "max_temp", "precipitation", "short_rad", "wind_speed", "relative_humidity")
        },
        "eu5_rows_emitted": 0,
        "exact_eu5_ready": False,
        "reason": "official_package_and_bundled_maize_path_execute; no exact 1337 EU5 crop/mode contract is supplied",
        "runtime": {
            "python": platform.python_version(),
            "numpy": np.__version__,
        },
    }
    try:
        import numba

        receipt["runtime"]["numba"] = numba.__version__
    except Exception as exc:  # pragma: no cover - environment diagnostic
        receipt["runtime"]["numba_error"] = f"{type(exc).__name__}:{exc}"
    output = Path("artifacts/data/population_capacity/pyaez_1337/exact_engine_wave27/official_runtime_smoke.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
