from __future__ import annotations

import json
from pathlib import Path

from prosper_or_perish_population_capacity import build_location_land_potential


REPO = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = REPO / "artifacts/data/population_capacity"
MANIFEST = ARTIFACT_ROOT / "sources/source_manifest.json"


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    downloaded = {
        str(row["source"]): _resolve_source_path(str(row["path"]))
        for row in manifest["sources"]
        if row.get("status") in {"downloaded", "exists"}
    }

    def paths(*source_ids: str) -> str:
        return ",".join(str(downloaded[source_id]) for source_id in source_ids if source_id in downloaded)

    sources = {
        # GAEZ v5 crop-physics composites retained for sensitivity reports.
        "gaez_rice": paths("gaez_v5_yxx_rice_wetland_rainfed", "gaez_v5_yxx_rice_dryland_rainfed"),
        "gaez_wheat": paths("gaez_v5_yxx_wheat_rainfed", "gaez_v5_yxx_barley_rainfed", "gaez_v5_yxx_rye_rainfed", "gaez_v5_yxx_oat_rainfed"),
        "gaez_maize": paths("gaez_v5_yxx_maize_rainfed"),
        "gaez_millet": paths("gaez_v5_yxx_foxtail_millet_rainfed", "gaez_v5_yxx_pearl_millet_rainfed", "gaez_v5_yxx_sorghum_rainfed"),
        "gaez_potato": paths(
            "gaez_v5_yxx_white_potato_rainfed",
            "gaez_v5_yxx_sweet_potato_rainfed",
            "gaez_v5_yxx_cassava_rainfed",
            "gaez_v5_yxx_yam_rainfed",
        ),
        "gaez_tropical": paths("gaez_v5_yxx_banana_rainfed"),
        # Individual physical yields used by the 1337 historical crop masks.
        "gaez_v5_barley": paths("gaez_v5_yxx_barley_rainfed"),
        "gaez_v5_rye": paths("gaez_v5_yxx_rye_rainfed"),
        "gaez_v5_oats": paths("gaez_v5_yxx_oat_rainfed"),
        "gaez_v5_wheat": paths("gaez_v5_yxx_wheat_rainfed"),
        "gaez_v5_foxtail_millet": paths("gaez_v5_yxx_foxtail_millet_rainfed"),
        "gaez_v5_pearl_millet": paths("gaez_v5_yxx_pearl_millet_rainfed"),
        "gaez_v5_sorghum": paths("gaez_v5_yxx_sorghum_rainfed"),
        "gaez_v5_rice_wet": paths("gaez_v5_yxx_rice_wetland_rainfed"),
        "gaez_v5_rice_dry": paths("gaez_v5_yxx_rice_dryland_rainfed"),
        "gaez_v5_maize": paths("gaez_v5_yxx_maize_rainfed"),
        "gaez_v5_white_potato": paths("gaez_v5_yxx_white_potato_rainfed"),
        "gaez_v5_sweet_potato": paths("gaez_v5_yxx_sweet_potato_rainfed"),
        "gaez_v5_cassava": paths("gaez_v5_yxx_cassava_rainfed"),
        "gaez_v5_yam": paths("gaez_v5_yxx_yam_rainfed"),
        "gaez_v5_taro": paths("gaez_v5_yxx_taro_rainfed"),
        "gaez_v5_banana": paths("gaez_v5_yxx_banana_rainfed"),
        # Matching GAEZ v5 LILM crop physics. These are the only sources
        # allowed to populate irrigated-yield fields.
        "gaez_v5_irrigated_barley": paths("gaez_v5_yxx_barley_irrigated"),
        "gaez_v5_irrigated_rye": paths("gaez_v5_yxx_rye_irrigated"),
        "gaez_v5_irrigated_oats": paths("gaez_v5_yxx_oat_irrigated"),
        "gaez_v5_irrigated_wheat": paths("gaez_v5_yxx_wheat_irrigated"),
        "gaez_v5_irrigated_foxtail_millet": paths("gaez_v5_yxx_foxtail_millet_irrigated"),
        "gaez_v5_irrigated_pearl_millet": paths("gaez_v5_yxx_pearl_millet_irrigated"),
        "gaez_v5_irrigated_sorghum": paths("gaez_v5_yxx_sorghum_irrigated"),
        "gaez_v5_irrigated_rice_wet": paths("gaez_v5_yxx_rice_wetland_irrigated"),
        "gaez_v5_irrigated_rice_dry": paths("gaez_v5_yxx_rice_dryland_irrigated"),
        "gaez_v5_irrigated_maize": paths("gaez_v5_yxx_maize_irrigated"),
        "gaez_v5_irrigated_white_potato": paths("gaez_v5_yxx_white_potato_irrigated"),
        "gaez_v5_irrigated_sweet_potato": paths("gaez_v5_yxx_sweet_potato_irrigated"),
        "gaez_v5_irrigated_cassava": paths("gaez_v5_yxx_cassava_irrigated"),
        "gaez_v5_irrigated_yam": paths("gaez_v5_yxx_yam_irrigated"),
        "gaez_v5_irrigated_taro": paths("gaez_v5_yxx_taro_irrigated"),
        "gaez_v5_irrigated_banana": paths("gaez_v5_yxx_banana_irrigated"),
        # GAEZ v4 yxLr0 is explicitly rain-fed sensitivity evidence.
        "gaez_v4_rainfed_rice": paths("gaez_yx_rice_wetland", "gaez_yx_rice_dryland"),
        "gaez_v4_rainfed_wheat": paths("gaez_yx_wheat"),
        "gaez_v4_rainfed_maize": paths("gaez_yx_maize"),
        "gaez_v4_rainfed_millet": paths("gaez_yx_pearl_millet", "gaez_yx_sorghum"),
        "gaez_v4_rainfed_potato": paths("gaez_yx_white_potato"),
        "gaez_rice_sc": paths("gaez_sc_rice_wetland", "gaez_sc_rice_dryland"),
        "gaez_wheat_sc": paths("gaez_sc_wheat"),
        "gaez_maize_sc": paths("gaez_sc_maize"),
        "gaez_millet_sc": paths("gaez_sc_pearl_millet", "gaez_sc_sorghum"),
        "gaez_potato_sc": paths("gaez_sc_white_potato"),
        "gaez_rice_yl": paths("gaez_yl_rice_wetland", "gaez_yl_rice_dryland"),
        "gaez_wheat_yl": paths("gaez_yl_wheat"),
        "gaez_maize_yl": paths("gaez_yl_maize"),
        "gaez_millet_yl": paths("gaez_yl_pearl_millet", "gaez_yl_sorghum"),
        "gaez_potato_yl": paths("gaez_yl_white_potato"),
        # Climate nearest to game start.
        "chelsa_temperature": paths("chelsa_trace21k_annual_mean_temperature_600bp"),
        "chelsa_precipitation": paths("chelsa_trace21k_annual_precipitation_600bp"),
        "chelsa_precipitation_seasonality": paths("chelsa_trace21k_precipitation_seasonality_600bp"),
    }
    sources = {name: path for name, path in sources.items() if path}
    print(
        build_location_land_potential(
            geometry_path=ARTIFACT_ROOT / "location_geometry_calibrated.parquet",
            output_path=ARTIFACT_ROOT / "location_land_potential.parquet",
            sources=[f"{name}={path}" for name, path in sources.items()],
            sample_points_path=ARTIFACT_ROOT / "location_sample_points.parquet",
        )
    )


def _resolve_source_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (REPO / path).resolve()


if __name__ == "__main__":
    main()
