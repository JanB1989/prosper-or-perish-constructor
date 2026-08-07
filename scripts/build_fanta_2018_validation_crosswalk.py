"""Build a point-level, validation-only EU5 crosswalk for Fanta et al. (2018).

The supplementary workbook contains 88 Central-European rural settlements and
population before/after the Thirty Years' War.  It is useful as a stress test
for local equilibrium behavior, but it is not a 1337 aggregate capacity target:
the settlements are post-period, the cadastre boundaries are not supplied as
polygons, and the paper's population unit is farmers in a village.  This script
therefore emits nearest-EU5-location diagnostics only and explicitly marks the
rows as ineligible for training.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import polars as pl


NS = {
    "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}


def _dms(value: str) -> float:
    value = value.strip()
    sign = -1.0 if value.endswith(("S", "W")) else 1.0
    digits = value.replace("°", " ").replace("'", " ").replace('"', " ")
    parts = digits[:-1].split()
    deg, minute, second = (float(x) for x in parts[:3])
    return sign * (deg + minute / 60.0 + second / 3600.0)


def _xlsx_rows(path: Path) -> list[dict[str, str]]:
    with zipfile.ZipFile(path) as archive:
        strings: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in root.findall("m:si", NS):
                strings.append("".join(t.text or "" for t in item.findall(".//m:t", NS)))
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {item.attrib["Id"]: item.attrib["Target"] for item in rels}
        sheet = workbook.find("m:sheets/m:sheet", NS)
        if sheet is None:
            raise ValueError("Fanta workbook has no sheet")
        target = targets[sheet.attrib["{" + NS["r"] + "}id"]]
        if not target.startswith("xl/"):
            target = "xl/" + target
        root = ET.fromstring(archive.read(target))
        rows: list[list[str]] = []
        for row in root.findall(".//m:sheetData/m:row", NS):
            values: list[str] = []
            for cell in row.findall("m:c", NS):
                value = cell.find("m:v", NS)
                text = value.text if value is not None else ""
                if cell.attrib.get("t") == "s" and text:
                    text = strings[int(text)]
                values.append(text)
            rows.append(values)
    if len(rows) < 7:
        raise ValueError("Fanta workbook is missing its header rows")
    # Row 3 contains the variable names from column D onward.  The first
    # three columns are named in row 6, while column D is the source-note
    # field; combine those two header sections explicitly.
    headers = ["village name", "latitude φ", "longitude λ", "data sources (for citations see references in our paper)"] + rows[2][4:]
    result = []
    for values in rows[6:]:
        if not values or not values[0]:
            continue
        padded = values + [""] * (len(headers) - len(values))
        result.append(dict(zip(headers, padded)))
    return result


def _haversine_km(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    radius = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius * math.asin(min(1.0, math.sqrt(a)))


def build(workbook: Path, geometry: Path, output_csv: Path, output_json: Path) -> dict[str, object]:
    locations = pl.read_parquet(geometry).select(["location_tag", "approx_lon", "approx_lat", "area"])
    candidates = locations.to_dicts()
    rows = []
    for item in _xlsx_rows(workbook):
        lon, lat = _dms(item["longitude λ"]), _dms(item["latitude φ"])
        nearest = min(candidates, key=lambda x: _haversine_km(lon, lat, x["approx_lon"], x["approx_lat"]))
        rows.append(
            {
                "source_record": item["village name"],
                "latitude": lat,
                "longitude": lon,
                "eu5_location_tag": nearest["location_tag"],
                "eu5_centroid_distance_km": _haversine_km(lon, lat, nearest["approx_lon"], nearest["approx_lat"]),
                "eu5_area_km2": nearest["area"],
                "settlement_size_before_war_farmers": item["Settlement size before war"],
                "settlement_size_after_war_farmers": item["Settlement size after war"],
                "settlement_size_after_regeneration_farmers": item["Settlement size after regeneration period "],
                "cadastre_size_m2": item["Cadastre size"],
                "soil_fertility_percent": item["Soil fertility"],
                "mapping_status": "nearest_point_diagnostic",
                "role": "validation_only",
                "training_eligible": False,
                "rejection_reason": "post-1337 rural settlement sample; no supplied aggregate boundary polygon or local-food capacity interval",
            }
        )
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    manifest = {
        "schema_version": "fanta_2018_validation_crosswalk_v1",
        "source_citation": "Fanta et al. (2018), Proc. R. Soc. B 285:20172500, DOI 10.1098/rspb.2017.2500",
        "supplementary_dataset": "10.6084/m9.figshare.5802615.v2",
        "workbook_sha256": hashlib.sha256(workbook.read_bytes()).hexdigest(),
        "record_count": len(rows),
        "mapping": "nearest calibrated EU5 centroid, point diagnostic only",
        "role": "validation_only",
        "training_eligible": False,
        "reason": "The sample is 17th-century post-war/regeneration village farmer counts, not a 1337 capacity interval, and the workbook does not provide mappable aggregate village cadastre polygons.",
        "output_csv": str(output_csv),
    }
    output_json.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workbook", type=Path, required=True)
    parser.add_argument("--geometry", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.workbook, args.geometry, args.output_csv, args.output_json), indent=2))


if __name__ == "__main__":
    main()
