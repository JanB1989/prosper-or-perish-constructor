#!/usr/bin/env python3
"""Build the tracked crop-history evidence registry from checksum-pinned sources.

This compiler intentionally emits evidence points rather than inferred country,
region, continent, or latitude/longitude-box availability.  The model maps each
point through the calibrated EU5 map transform to an exact location footprint;
all unmapped keys retain the explicit per-crop default state from
population_capacity_crop_history_registry.toml.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Iterable, Iterator

import numpy as np
import polars as pl
import shapely
from pyogrio.raw import read as read_ogr
from pyproj import Transformer
import xlrd

from prosper_or_perish_population_capacity.spatial_graph import (
    map_geographic_points_to_game_locations,
)


OWCAD_SHA256 = "6af22e9b817491590d31d35d76eebb282292f2c35ef6e0e657d264eb082ee46c"
CROP_ORIGINS_SHA256 = "3ec26347cbea737f9c101aec85bce3f43b129b022c8c6cac81667e7e9120e0fe"
OWCAD_SOURCE_ID = "fuller_owcad_2026"
CROP_ORIGINS_SOURCE_ID = "milla_crop_origins_v1_2020"
OWCAD_CITATION = "https://doi.org/10.1007/s00334-026-01114-6"
CROP_ORIGINS_CITATION = "https://doi.org/10.1111/geb.13057"
MAIZE_ARCHAEOLOGY_SHA256 = "66c2a75696b1909a9851afd27edd5ab3254d21898ad17f41c8e84ec6999fbc8c"
MAIZE_ARCHAEOLOGY_SOURCE_ID = "van_etten_hijmans_maize_2010"
MAIZE_ARCHAEOLOGY_CITATION = "https://doi.org/10.1371/journal.pone.0012060"
NATURAL_EARTH_ADMIN0_SHA256 = "5fed433373581fa648920435f937d95f2d3c0200e067409c6478dcdf1b853139"
NUNN_QIAN_SHA256 = "d4521e5ec7da33dfea99affe2749b76a54a95bd425f188d71c0160c2cd834f1e"
PHASEOLUS_EXCHANGE_SHA256 = "849510d4e7de691d604037d5d5c678e35e620a8bc217c53f1f8c80c1b7654586"
PURUHA_SHA256 = "ca005027665e75c617d81b4cde07f65507603dee411deab86ae543acdad3d7e4"
PURUHA_SOURCE_ID = "aguirre_merino_puruha_2025"
PURUHA_CITATION = "https://doi.org/10.5281/zenodo.14961467"
KUK_NOMINATION_SHA256 = "53ba1c0a355f8e4b8ff8706d4b0b36fbbbe26527ede0ab7ef6e8dea5d9252cd2"
KUK_SOURCE_ID = "unesco_kuk_nomination_2007"
KUK_CITATION = "https://whc.unesco.org/en/list/887"
RAPA_NUI_STARCH_SHA256 = "40498524d3a36f1f6b73550e36e9913dd695118be50b0a7aae9054fec9e8ba31"
RAPA_NUI_STARCH_SOURCE_ID = "berenguer_rapa_nui_starch_2024"
RAPA_NUI_STARCH_CITATION = "https://doi.org/10.1371/journal.pone.0298896"
# Frozen p95 error of 162 held-out city controls for the calibrated map
# transform.  This is a measured coordinate-model uncertainty, not a crop
# dispersal radius.  Source-specific georeference uncertainty is added below.
MAP_TRANSFORM_P95_ERROR_KM = 60.68585597165764
# These cited sites fall on unregistered pixels in the game map, and the nearest
# RGO footprint is beyond the frozen transform+source uncertainty cap.  They
# therefore have no defensible location label target; retaining them as explicit
# non-location exclusions is safer than snapping them to a nearby RGO.
KNOWN_UNREPRESENTED_SITE_RECORDS = frozenset(
    {
        "OWCAD_v1_row_410",  # MK36, Mali
        "OWCAD_v1_row_557",  # Babish-Mola, Kazakhstan
        "OWCAD_v1_row_559",  # Balanda, Kazakhstan
        "OWCAD_v1_row_561",  # Chirik-Rabat, Kazakhstan
        "OWCAD_v1_row_562",  # Inkar-kala, Kazakhstan
        "OWCAD_v1_row_565",  # Mynaral, Kazakhstan
        "OWCAD_v1_row_566",  # Sengir-Tam, Kazakhstan
    }
)
OUTPUT_COLUMNS = (
    "evidence_id",
    "crop",
    "evidence_state",
    "latitude",
    "longitude",
    "coordinate_uncertainty_km",
    "start_year",
    "end_year",
    "evidence_kind",
    "source_id",
    "source_record_id",
    "source_object_sha256",
    "citation_url",
    "notes",
)

# Zero-based OWCAD column indices.  The database's taxon columns are explicit
# presence/absence fields; wild, questionable and rejected identifications are
# downgraded below rather than silently counted as crop presences.
OWCAD_COLUMNS = {
    "wheat": (18, 19, 20, 21, 22, 23),
    "barley": (24, 25, 26, 27, 28),
    "rice_dry": (29,),
    "rice_wet": (29,),
    "foxtail_millet": (31,),
    "pearl_millet": (32,),
    "sorghum": (33,),
    "oats": (43,),
    "rye": (44,),
    "maize": (45,),
    "chickpea": (47,),
    "dry_pea": (48,),
    "soybean": (53,),
    "mung_bean": (55, 56, 57),
    "cowpea": (58,),
    "pigeonpea": (63,),
}
# OWCAD explicitly warns that Avena/Secale fields may include wild taxa.  Its
# few pre-1492 Old World Zea records conflict with the independently established
# Columbian-exchange chronology and therefore remain uncertainty evidence, not
# positive maize-availability labels.
OWCAD_WILD_AMBIGUOUS_CROPS = frozenset({"maize"})

# Crop Origins v1 species map for all 23 physical crop families.  Multiple
# taxa are intentional for composite GAEZ families (wheat, rice and yam).
CROP_ORIGINS_SPECIES = {
    "banana": ("Musa acuminata",),
    "barley": ("Hordeum vulgare",),
    "cassava": ("Manihot esculenta",),
    "chickpea": ("Cicer arietinum",),
    "cowpea": ("Vigna unguiculata",),
    "dry_pea": ("Pisum sativum",),
    "phaseolus_bean": ("Phaseolus vulgaris",),
    "mung_bean": ("Vigna radiata", "Vigna mungo"),
    "pigeonpea": ("Cajanus cajan",),
    "soybean": ("Glycine max",),
    "taro": ("Colocasia esculenta",),
    "foxtail_millet": ("Setaria italica",),
    "maize": ("Zea mays",),
    "oats": ("Avena sativa",),
    "pearl_millet": ("Pennisetum glaucum",),
    "rice_dry": ("Oryza sativa", "Oryza glaberrima"),
    "rice_wet": ("Oryza sativa", "Oryza glaberrima"),
    "rye": ("Secale cereale",),
    "sweet_potato": ("Ipomoea batatas",),
    "sorghum": ("Sorghum bicolor",),
    "wheat": (
        "Triticum aestivum",
        "Triticum dicoccum",
        "Triticum durum",
        "Triticum monococcum",
        "Triticum spelta",
    ),
    "white_potato": ("Solanum tuberosum",),
    "yam": (
        "Dioscorea alata",
        "Dioscorea cayenensis",
        "Dioscorea dumetorum",
        "Dioscorea esculenta",
        "Dioscorea japonica",
        "Dioscorea nummularia",
        "Dioscorea opposita",
        "Dioscorea pentaphylla",
        "Dioscorea rotundata",
        "Dioscorea trifida",
    ),
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--owcad", type=Path, required=True)
    parser.add_argument("--crop-origins", type=Path, required=True)
    parser.add_argument("--maize-archaeology", type=Path, required=True)
    parser.add_argument("--natural-earth-admin0", type=Path, required=True)
    parser.add_argument("--puruha-article", type=Path, required=True)
    parser.add_argument("--kuk-nomination", type=Path, required=True)
    parser.add_argument("--rapa-nui-starch", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--locations-png", type=Path, required=True)
    parser.add_argument("--coordinate-transform", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--domains-output", type=Path, required=True)
    parser.add_argument("--mapping-output", type=Path, required=True)
    parser.add_argument("--mapping-audit-output", type=Path, required=True)
    args = parser.parse_args()
    _require_hash(args.owcad, OWCAD_SHA256)
    _require_hash(args.crop_origins, CROP_ORIGINS_SHA256)
    _require_hash(args.maize_archaeology, MAIZE_ARCHAEOLOGY_SHA256)
    _require_hash(args.natural_earth_admin0, NATURAL_EARTH_ADMIN0_SHA256)
    _require_hash(args.puruha_article, PURUHA_SHA256)
    _require_hash(args.kuk_nomination, KUK_NOMINATION_SHA256)
    _require_hash(args.rapa_nui_starch, RAPA_NUI_STARCH_SHA256)
    rows = [
        *_extract_owcad(args.owcad),
        # Crop Origins is checksum-verified above because it remains part of the
        # source lineage, but its wild-progenitor ecoregion centroids are not
        # cultivation sites and therefore emit no availability labels.
        *_extract_maize_archaeology(args.maize_archaeology),
        *_extract_puruha_sites(),
        *_extract_kuk_swamp(),
        *_extract_rapa_nui_starch(),
    ]
    rows.sort(
        key=lambda row: (
            row["crop"],
            row["source_id"],
            row["source_record_id"],
            row["evidence_state"],
        )
    )
    for index, row in enumerate(rows, 1):
        row["evidence_id"] = f"crop_history_{index:06d}"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    _write_domain_evidence(args.natural_earth_admin0, args.domains_output)
    _write_exact_location_mapping(
        evidence_path=args.output,
        baseline_path=args.baseline,
        locations_png_path=args.locations_png,
        transform_path=args.coordinate_transform,
        output_path=args.mapping_output,
        audit_path=args.mapping_audit_output,
    )
    print(f"crop-history evidence rows: {len(rows)}")
    print(f"crop-history evidence crops: {len({row['crop'] for row in rows})}")
    print(f"crop-history evidence SHA-256: {_sha256(args.output)}")
    print(f"crop-history domain SHA-256: {_sha256(args.domains_output)}")
    print(f"crop-history mapping SHA-256: {_sha256(args.mapping_output)}")
    print(f"crop-history mapping audit SHA-256: {_sha256(args.mapping_audit_output)}")
    return 0


def _write_exact_location_mapping(
    *, evidence_path: Path, baseline_path: Path, locations_png_path: Path,
    transform_path: Path, output_path: Path, audit_path: Path,
) -> None:
    """Freeze cited coordinates against exact game-map footprints.

    The fallback gate is the transform's frozen held-out-city p95 error plus
    each source record's explicit coordinate uncertainty.  It represents map
    alignment uncertainty, never crop dispersal or centroid assignment.
    Unresolved points remain in the artifact and block acceptance.
    """

    evidence = pl.read_csv(
        evidence_path,
        schema_overrides={"coordinate_uncertainty_km": pl.Float64},
    ).select(
        "evidence_id",
        "longitude",
        "latitude",
        "coordinate_uncertainty_km",
        "evidence_state",
        "source_record_id",
    )
    mapped, audit = map_geographic_points_to_game_locations(
        evidence,
        baseline_path=baseline_path,
        locations_png_path=locations_png_path,
        transform=transform_path,
        coordinate_uncertainty_km_column="coordinate_uncertainty_km",
        maximum_georeferencing_displacement_km=MAP_TRANSFORM_P95_ERROR_KM,
    )
    mapped = mapped.with_columns(
        pl.when(
            pl.col("mapping_state").str.starts_with("unresolved_")
            & (pl.col("evidence_state") == "uncertain")
        )
        .then(pl.lit("excluded_non_location_evidence"))
        .when(
            pl.col("mapping_state").str.starts_with("unresolved_")
            & pl.col("source_record_id").is_in(KNOWN_UNREPRESENTED_SITE_RECORDS)
        )
        .then(pl.lit("excluded_non_location_evidence"))
        .otherwise(pl.col("mapping_state"))
        .alias("mapping_state"),
        pl.when(
            pl.col("mapping_state").str.starts_with("unresolved_")
            & (pl.col("evidence_state") == "uncertain")
        )
        .then(pl.lit("uncertain_evidence_cannot_close_a_location_label"))
        .when(
            pl.col("mapping_state").str.starts_with("unresolved_")
            & pl.col("source_record_id").is_in(KNOWN_UNREPRESENTED_SITE_RECORDS)
        )
        .then(
            pl.lit(
                "cited_site_has_no_game_rgo_footprint_within_frozen_transform_plus_source_cap"
            )
        )
        .otherwise(pl.lit(""))
        .alias("exclusion_reason_code"),
    )
    remaining_unresolved = mapped.filter(
        pl.col("mapping_state").str.starts_with("unresolved_")
    )
    state_counts = {
        str(row["mapping_state"]): int(row["len"])
        for row in mapped.group_by("mapping_state").len().to_dicts()
    }
    audit = {
        **audit,
        "accepted": remaining_unresolved.is_empty(),
        "resolved_records": mapped.filter(pl.col("location_tag").is_not_null()).height,
        "excluded_non_location_records": mapped.filter(
            pl.col("mapping_state") == "excluded_non_location_evidence"
        ).height,
        "unresolved_records": remaining_unresolved.height,
        "unresolved_evidence_ids": remaining_unresolved["evidence_id"].to_list(),
        "mapping_state_counts": state_counts,
        "exclusion_reason_counts": {
            str(row["exclusion_reason_code"]): int(row["len"])
            for row in mapped.filter(pl.col("exclusion_reason_code") != "")
            .group_by("exclusion_reason_code")
            .len()
            .to_dicts()
        },
    }
    mapping_columns = (
        "evidence_id",
        "source_lon",
        "source_lat",
        "coordinate_uncertainty_km",
        "map_pixel_x",
        "map_pixel_y",
        "location_rgb",
        "location_tag",
        "mapping_state",
        "exclusion_reason_code",
        "mapping_displacement_km",
        "base_georeferencing_cap_km",
        "effective_distance_cap_km",
        "coordinate_transform_sha256",
        "baseline_source_sha256",
        "locations_png_sha256",
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    mapped.select(mapping_columns).sort("evidence_id").write_csv(output_path)
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(
        json.dumps(audit, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def _extract_maize_archaeology(path: Path) -> list[dict[str, str]]:
    """Extract dated maize occurrences from the authors' published workbook.

    Directly dated macrobotanical remains are classified as known available.
    Indirect dates and microbotanical identifications remain uncertainty
    evidence, so their presence cannot silently close a location label.
    """

    workbook = xlrd.open_workbook(path)
    coordinate_sheet = workbook.sheet_by_name("Coord")
    coordinate_header = [str(value).strip() for value in coordinate_sheet.row_values(0)]
    if coordinate_header[:10] != [
        "ID", "Country", "Region", "Site_Name", "Site_number", "Lat", "Lon",
        "Uncertainty", "Source/Remarks", "Cont_region",
    ]:
        raise ValueError("maize archaeology coordinate header does not match source contract")
    coordinates: dict[int, dict[str, object]] = {}
    for row_number in range(1, coordinate_sheet.nrows):
        row = dict(zip(coordinate_header, coordinate_sheet.row_values(row_number)))
        location_id = _integer(row.get("ID"))
        latitude = _number(row.get("Lat"))
        longitude = _number(row.get("Lon"))
        if location_id is None or latitude is None or longitude is None:
            continue
        coordinates[location_id] = row

    date_sheet = workbook.sheet_by_name("Dates")
    date_header = [str(value).strip() for value in date_sheet.row_values(0)]
    required = {
        "ID", "Site_Name", "Type_Zea_Material", "Dating_Direct_Indirect",
        "Calibrated_median", "Reference", "Location",
    }
    if not required.issubset(date_header):
        raise ValueError("maize archaeology dates header does not match source contract")
    records: list[dict[str, str]] = []
    for row_number in range(1, date_sheet.nrows):
        row = dict(zip(date_header, date_sheet.row_values(row_number)))
        location_id = _integer(row.get("Location"))
        calibrated_bp = _number(row.get("Calibrated_median"))
        coordinate = coordinates.get(location_id) if location_id is not None else None
        if coordinate is None or calibrated_bp is None:
            continue
        evidence_year = int(round(1950.0 - calibrated_bp))
        if evidence_year > 1337:
            continue
        material = str(row.get("Type_Zea_Material", "")).strip().lower()
        dating = str(row.get("Dating_Direct_Indirect", "")).strip().lower()
        evidence_state = (
            "known_available"
            if material == "macrobotanical" and dating == "direct"
            else "uncertain"
        )
        uncertainty_m = _number(coordinate.get("Uncertainty"))
        notes = (
            f"site={row.get('Site_Name', '')}; country={coordinate.get('Country', '')}; "
            f"material={material}; dating={dating}; calibrated_median_bp={calibrated_bp:g}; "
            f"coordinate_uncertainty_m={uncertainty_m if uncertainty_m is not None else ''}; "
            f"reference={str(row.get('Reference', '')).strip()}"
        )
        records.append(
            {
                "evidence_id": "",
                "crop": "maize",
                "evidence_state": evidence_state,
                "latitude": _format_number(float(coordinate["Lat"])),
                "longitude": _format_number(float(coordinate["Lon"])),
                "coordinate_uncertainty_km": _format_number(
                    uncertainty_m / 1_000.0 if uncertainty_m is not None else 0.0
                ),
                "start_year": str(evidence_year),
                "end_year": str(evidence_year),
                "evidence_kind": "dated_maize_archaeobotanical_occurrence",
                "source_id": MAIZE_ARCHAEOLOGY_SOURCE_ID,
                "source_record_id": f"maize_s3_dates_row_{row_number + 1}",
                "source_object_sha256": MAIZE_ARCHAEOLOGY_SHA256,
                "citation_url": MAIZE_ARCHAEOLOGY_CITATION,
                "notes": notes,
            }
        )
    if not records or not any(row["evidence_state"] == "known_available" for row in records):
        raise ValueError("maize archaeology source emitted no dated positive evidence")
    return records


def _extract_puruha_sites() -> list[dict[str, str]]:
    """Compile the article's two explicitly located and dated Puruha sites."""

    transformer = Transformer.from_crs("EPSG:32717", "EPSG:4326", always_xy=True)
    sites = [
        {
            "site_id": "SC-03_Lluishi",
            "easting": 760_922.0,
            "northing": 9_821_994.0,
            "start_year": 300,
            "end_year": 390,
            "crops": (
                ("maize", "known_available", "Zea mays starch and phytoliths"),
                ("cassava", "known_available", "Manihot esculenta starch"),
                ("sweet_potato", "known_available", "Ipomoea batatas starch"),
            ),
        },
        {
            "site_id": "SI-02_Huavalac",
            "easting": 768_023.0,
            "northing": 9_821_754.0,
            "start_year": 930,
            "end_year": 970,
            "crops": (
                ("maize", "known_available", "Zea mays starch and phytoliths"),
                ("white_potato", "known_available", "Solanum tuberosum starch"),
                (
                    "phaseolus_bean",
                    "uncertain",
                    "cf. Phaseolus sp. starch does not resolve P. vulgaris",
                ),
            ),
        },
    ]
    records: list[dict[str, str]] = []
    for site in sites:
        longitude, latitude = transformer.transform(site["easting"], site["northing"])
        for crop, state, identification in site["crops"]:
            records.append(
                {
                    "evidence_id": "",
                    "crop": crop,
                    "evidence_state": state,
                    "latitude": _format_number(latitude),
                    "longitude": _format_number(longitude),
                    "coordinate_uncertainty_km": "0.1",
                    "start_year": str(site["start_year"]),
                    "end_year": str(site["end_year"]),
                    "evidence_kind": "dated_archaeological_microremain_occurrence",
                    "source_id": PURUHA_SOURCE_ID,
                    "source_record_id": f"{site['site_id']}:{crop}",
                    "source_object_sha256": PURUHA_SHA256,
                    "citation_url": PURUHA_CITATION,
                    "notes": (
                        f"site={site['site_id']}; identification={identification}; "
                        "coordinates transformed from article UTM zone 17M (WGS84 / UTM 17S); "
                        "dates are the article's archaeological context interval"
                    ),
                }
            )
    return records


def _extract_kuk_swamp() -> list[dict[str, str]]:
    """Compile Kuk's exact UNESCO coordinate and pre-1337 crop evidence.

    The nomination documents a 116 ha archaeological property, its coordinate,
    and an agricultural sequence based on bananas, taro and yam from roughly
    7,000--6,400 cal BP onward.  The coordinate is the site's mapped footprint,
    not a crop-origin centroid or an inferred New Guinea distribution.
    """

    latitude = -(5.0 + 47.0 / 60.0 + 1.36 / 3_600.0)
    longitude = 144.0 + 19.0 / 60.0 + 54.2 / 3_600.0
    records: list[dict[str, str]] = []
    for crop in ("banana", "taro", "yam"):
        records.append(
            {
                "evidence_id": "",
                "crop": crop,
                "evidence_state": "known_available",
                "latitude": _format_number(latitude),
                "longitude": _format_number(longitude),
                "coordinate_uncertainty_km": "0",
                "start_year": "-5000",
                "end_year": "-4490",
                "evidence_kind": "dated_archaeological_cultivation_occurrence",
                "source_id": KUK_SOURCE_ID,
                "source_record_id": f"UNESCO_887:{crop}",
                "source_object_sha256": KUK_NOMINATION_SHA256,
                "citation_url": KUK_CITATION,
                "notes": (
                    "site=Kuk Early Agricultural Site; UNESCO coordinate="
                    "S5 47 1.36 E144 19 54.2; property_area_ha=116; crop is named "
                    "in the nomination's vegetative-propagation agricultural sequence "
                    "around 7000-6400 cal BP; use is documented as episodically "
                    "persistent to the present"
                ),
            }
        )
    return records


def _write_domain_evidence(natural_earth_path: Path, output: Path) -> None:
    """Write cited time/domain exclusions as checksum-stable GeoJSON.

    Natural Earth supplies boundaries only.  Crop-history semantics come from
    the cited literature and are deliberately limited to the documented
    post-1492 transfer domains.  No positive dispersal is inferred from a
    continent or political boundary.
    """

    metadata, _fids, geometry_wkb, fields = read_ogr(
        natural_earth_path, columns=["ADMIN", "CONTINENT"]
    )
    if metadata.get("crs") != "EPSG:4326" or geometry_wkb is None:
        raise ValueError("Natural Earth admin-0 source must be polygon EPSG:4326")
    continents = np.asarray(fields[1], dtype=object)
    geometries = shapely.from_wkb(geometry_wkb)

    def union(names: set[str]):
        selected = geometries[np.isin(continents, sorted(names))]
        geometry = shapely.make_valid(shapely.union_all(selected))
        if geometry.is_empty or not geometry.is_valid:
            raise ValueError(f"invalid domain union for {sorted(names)}")
        return geometry

    old_world = union({"Africa", "Asia", "Europe", "Oceania"})
    eurasia_africa = union({"Africa", "Asia", "Europe"})
    americas = union({"North America", "South America"})
    features = [
        _domain_feature(
            domain_id="post_1492_old_world_staples",
            geometry=old_world,
            crops=["cassava", "maize", "white_potato"],
            source_ids=["nunn_qian_columbian_exchange_2010"],
            citation_urls=["https://doi.org/10.1257/jep.24.2.163"],
            source_hashes=[NUNN_QIAN_SHA256],
            notes=(
                "The cited synthesis defines these American staples as transfers to the "
                "Old World following Columbus's 1492 voyage."
            ),
        ),
        _domain_feature(
            domain_id="post_1493_old_world_phaseolus",
            geometry=old_world,
            crops=["phaseolus_bean"],
            source_ids=["piergiovanni_phaseolus_exchange_2022"],
            citation_urls=["https://doi.org/10.3389/fpls.2022.851029"],
            source_hashes=[PHASEOLUS_EXCHANGE_SHA256],
            notes=(
                "The cited review places Phaseolus introductions to the Old World after "
                "1493, with African and Asian dissemination in the sixteenth century."
            ),
        ),
        _domain_feature(
            domain_id="post_1492_eurasia_africa_sweet_potato",
            geometry=eurasia_africa,
            crops=["sweet_potato"],
            source_ids=["nunn_qian_columbian_exchange_2010"],
            citation_urls=["https://doi.org/10.1257/jep.24.2.163"],
            source_hashes=[NUNN_QIAN_SHA256],
            notes=(
                "Europe, Asia and Africa are excluded before 1492; Oceania is deliberately "
                "left uncertain because pre-Columbian Polynesian sweet-potato evidence exists."
            ),
        ),
        _domain_feature(
            domain_id="post_1492_new_world_soybean_banana",
            geometry=americas,
            crops=["banana", "soybean"],
            source_ids=["nunn_qian_columbian_exchange_2010"],
            citation_urls=["https://doi.org/10.1257/jep.24.2.163"],
            source_hashes=[NUNN_QIAN_SHA256],
            notes=(
                "The cited synthesis explicitly states that soybeans and bananas were "
                "introduced to the New World in the Columbian-exchange context."
            ),
        ),
    ]
    payload = {
        "type": "FeatureCollection",
        "schema_version": "crop_history_domains_v1",
        "boundary_source_id": "natural_earth_admin0_50m_2025",
        "boundary_source_sha256": NATURAL_EARTH_ADMIN0_SHA256,
        "features": features,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def _extract_rapa_nui_starch() -> list[dict[str, str]]:
    """Emit the directly mapped early-settlement Rapa Nui crop evidence.

    Berenguer et al. identify sweet-potato and taro starch in the c.1300
    Anakena context.  Manioc is reported only as a cautious, low-count
    identification and is therefore retained as ``uncertain`` rather than
    converted into a positive availability label.  The coordinate is the
    published Ahu Nau Nau/Anakena archaeological site, not the island
    centroid; the frozen map mapper assigns the point to the exact EU5
    footprint and does not expand it spatially.
    """
    latitude = "-27.07438889"
    longitude = "-109.32241667"
    rows: list[dict[str, str]] = []
    for index, (crop, state, note) in enumerate(
        (
            (
                "sweet_potato",
                "known_available",
                "Anakena Ahu Nau Nau lower settlement context dated around AD 1300; starch identification >90% confidence for Ipomoea batatas in the early occupation sequence",
            ),
            (
                "taro",
                "known_available",
                "Anakena Ahu Nau Nau lower settlement context dated around AD 1300; starch identification of Colocasia esculenta in the early occupation sequence",
            ),
            (
                "cassava",
                "uncertain",
                "Anakena Ahu Nau Nau lower settlement context dated around AD 1300; one low-count Manihot esculenta assignment is reported but the authors explicitly retain recent-introduction uncertainty",
            ),
        ),
        1,
    ):
        rows.append(
            {
                "evidence_id": "",
                "crop": crop,
                "evidence_state": state,
                "latitude": latitude,
                "longitude": longitude,
                "coordinate_uncertainty_km": "0.5",
                "start_year": "1200",
                "end_year": "1337",
                "evidence_kind": "dated_archaeological_starch_occurrence",
                "source_id": RAPA_NUI_STARCH_SOURCE_ID,
                "source_record_id": f"Berenguer2024_Anakena_AhuNauNau_{index}",
                "source_object_sha256": RAPA_NUI_STARCH_SHA256,
                "citation_url": RAPA_NUI_STARCH_CITATION,
                "notes": note,
            }
        )
    return rows


def _domain_feature(
    *, domain_id: str, geometry: object, crops: list[str], source_ids: list[str],
    citation_urls: list[str], source_hashes: list[str], notes: str,
) -> dict[str, object]:
    return {
        "type": "Feature",
        "properties": {
            "domain_id": domain_id,
            "evidence_state": "known_unavailable",
            "start_year": -9999,
            "end_year": 1337,
            "evidence_kind": "cited_domain_time_exclusion",
            "crops": crops,
            "source_ids": source_ids,
            "source_object_sha256s": source_hashes,
            "citation_urls": citation_urls,
            "notes": notes,
        },
        "geometry": json.loads(shapely.to_geojson(geometry)),
    }


def _extract_owcad(path: Path) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    rows = iter(_xlsx_rows(path, sheet_path="xl/worksheets/sheet1.xml"))
    header = next(rows)
    if header[:18] != [
        "Site  ",
        "Name in Local Script",
        "Main Region",
        "Country",
        "Province/State",
        "City, District, Prefecture, local area",
        "Latitude",
        "Longitude",
        "GeoRef Quality",
        "Sample Quality",
        "Dating Quality",
        "Broad Cultural Period",
        "Early/Late",
        "Regional phase",
        "Local/Site Phase",
        "Start Date BC/AD",
        "Finish Date BC/AD",
        "Est.Date Median BC/AD",
    ]:
        raise ValueError("OWCAD worksheet header does not match the pinned source contract")
    for row_number, row in enumerate(rows, 2):
        row += [""] * (119 - len(row))
        latitude = _number(row[6])
        longitude = _number(row[7])
        start_raw = _integer(row[15])
        finish_raw = _integer(row[16])
        if None in {latitude, longitude, start_raw, finish_raw}:
            continue
        start = min(start_raw, finish_raw)
        finish = max(start_raw, finish_raw)
        if start > 1337:
            continue
        for crop, indices in OWCAD_COLUMNS.items():
            values = [str(row[index]).strip() for index in indices if str(row[index]).strip()]
            values = [value for value in values if value.upper() != "INCOMPLETE"]
            if not values:
                continue
            quality = _owcad_evidence_state(crop, values, finish)
            if quality is None:
                continue
            notes = (
                f"site={row[0]}; country={row[3]}; taxon_codes={'|'.join(values)}; "
                f"georef_quality={row[8]}; sample_quality={row[9]}; "
                f"dating_quality={row[10]}; phase={row[13]}"
            )
            records.append(
                {
                    "evidence_id": "",
                    "crop": crop,
                    "evidence_state": quality,
                    "latitude": _format_number(latitude),
                    "longitude": _format_number(longitude),
                    "coordinate_uncertainty_km": {
                        "1": "1",
                        "2": "10",
                        "3": "50",
                    }.get(str(row[8]).strip(), "0"),
                    "start_year": str(start),
                    "end_year": str(min(finish, 1337)),
                    "evidence_kind": "dated_archaeobotanical_occurrence",
                    "source_id": OWCAD_SOURCE_ID,
                    "source_record_id": f"OWCAD_v1_row_{row_number}",
                    "source_object_sha256": OWCAD_SHA256,
                    "citation_url": OWCAD_CITATION,
                    "notes": notes,
                }
            )
    return records


def _owcad_evidence_state(crop: str, values: Iterable[str], finish: int) -> str | None:
    definite = False
    questionable = crop in OWCAD_WILD_AMBIGUOUS_CROPS or finish > 1337
    for raw in values:
        for token in re.split(r"[;,/| ]+", raw):
            token = token.strip()
            if not token:
                continue
            lower = token.lower()
            if crop == "oats":
                # OWCAD's Avena column mixes genus-level and wild-oat finds.
                # Only its explicit, unqualified A. sativa code closes crop
                # availability; Av, Avf/A. fatua, and wild/questioned codes do not.
                if token == "Avs":
                    definite = True
                else:
                    questionable = True
            elif crop == "rye":
                # Clean Sec is the database's crop occurrence code.  wSec and
                # ?Sec explicitly retain wild/status uncertainty.
                if token == "Sec":
                    definite = True
                else:
                    questionable = True
            elif (
                token.startswith("[")
                or token.startswith("(")
                or token.startswith("?")
                or lower.startswith("w")
            ):
                questionable = True
            else:
                definite = True
    if definite and not questionable:
        return "known_available"
    if definite or questionable:
        return "uncertain"
    return None


def _extract_crop_origins(path: Path) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    species_to_crops: dict[str, list[str]] = {}
    for crop, species_names in CROP_ORIGINS_SPECIES.items():
        for species in species_names:
            species_to_crops.setdefault(species, []).append(crop)
    with path.open("r", encoding="cp1252", newline="") as handle:
        reader = csv.DictReader(handle)
        for row_number, row in enumerate(reader, 2):
            species = str(row.get("species_name", "")).strip()
            crops = species_to_crops.get(species)
            if crops is None:
                continue
            latitude = _number(row.get("mode_ecoreg_centroid_lat"))
            longitude = _number(row.get("mode_ecoreg_centroid_lon"))
            antiquity = _integer(row.get("minimum_time_domestication"))
            if antiquity is None:
                antiquity = _integer(row.get("minimum_time_cultivation"))
            if latitude is None or longitude is None or antiquity is None:
                continue
            evidence_year = 1950 - antiquity
            if evidence_year > 1337:
                continue
            for crop in crops:
                records.append(
                    {
                        "evidence_id": "",
                        "crop": crop,
                        "evidence_state": "known_available",
                        "latitude": _format_number(latitude),
                        "longitude": _format_number(longitude),
                        "coordinate_uncertainty_km": "0",
                        "start_year": str(evidence_year),
                        "end_year": str(evidence_year),
                        "evidence_kind": "published_domestication_origin_ecoregion_centroid",
                        "source_id": CROP_ORIGINS_SOURCE_ID,
                        "source_record_id": f"crop_origins_v1_row_{row_number}",
                        "source_object_sha256": CROP_ORIGINS_SHA256,
                        "citation_url": CROP_ORIGINS_CITATION,
                        "notes": (
                            f"species={species}; realm={row.get('biogeografic_realm', '')}; "
                            f"ecoregion={row.get('mode_ecoreg_name', '')}; "
                            "coordinate is the published wild-progenitor origin-ecoregion centroid, "
                            "not an excavated site"
                        ),
                    }
                )
    missing = sorted(set(CROP_ORIGINS_SPECIES).difference(row["crop"] for row in records))
    if missing:
        raise ValueError(
            "Crop Origins source did not resolve modeled crop families: " + ", ".join(missing)
        )
    return records


def _xlsx_rows(path: Path, *, sheet_path: str) -> Iterator[list[object]]:
    namespace = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    with zipfile.ZipFile(path) as archive:
        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in root.findall(f"{namespace}si"):
                shared_strings.append(
                    "".join(node.text or "" for node in item.iter(f"{namespace}t"))
                )
        with archive.open(sheet_path) as handle:
            for _event, element in ET.iterparse(handle, events=("end",)):
                if element.tag != f"{namespace}row":
                    continue
                values: dict[int, object] = {}
                for cell in element.findall(f"{namespace}c"):
                    reference = str(cell.attrib.get("r", ""))
                    column = _excel_column_index(reference)
                    kind = cell.attrib.get("t")
                    value_node = cell.find(f"{namespace}v")
                    if kind == "inlineStr":
                        value: object = "".join(
                            node.text or "" for node in cell.iter(f"{namespace}t")
                        )
                    elif value_node is None or value_node.text is None:
                        value = ""
                    elif kind == "s":
                        value = shared_strings[int(value_node.text)]
                    elif kind == "b":
                        value = value_node.text == "1"
                    else:
                        value = _parse_number(value_node.text)
                    values[column] = value
                if values:
                    row = [""] * (max(values) + 1)
                    for column, value in values.items():
                        row[column] = value
                    yield row
                element.clear()


def _excel_column_index(reference: str) -> int:
    letters = "".join(character for character in reference if character.isalpha())
    result = 0
    for character in letters:
        result = result * 26 + ord(character.upper()) - ord("A") + 1
    return result - 1


def _parse_number(value: str) -> object:
    try:
        number = float(value)
    except ValueError:
        return value
    return int(number) if number.is_integer() else number


def _number(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None


def _integer(value: object) -> int | None:
    number = _number(value)
    return int(round(number)) if number is not None else None


def _format_number(value: float) -> str:
    return f"{value:.8f}".rstrip("0").rstrip(".")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_hash(path: Path, expected: str) -> None:
    actual = _sha256(path)
    if actual != expected:
        raise ValueError(f"source checksum mismatch for {path}: expected {expected}, found {actual}")


if __name__ == "__main__":
    raise SystemExit(main())
