import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyogrio
from shapely import STRtree, from_wkb, points, simplify
from shapely.geometry import mapping


ROOT = Path(__file__).resolve().parents[2]
LOCATIONS = ROOT / "artifacts/data/population_capacity/current_capacity_map/location_candidates.parquet"
COUNTRIES = ROOT / "tmp/hyde_country_modifier/ne_50m_admin_0_countries.geojson"
FACTORS = ROOT / "tmp/hyde1300/cropland_per_person.csv"
OUTPUT = Path(r"/mnt/c/Users/Anwender/.codex/visualizations/2026/08/26/01a03ef1-d992-7233-8e49-f652259f19b2/hyde-country-cropland-factor-1337-1837.html")


def interpolate(frame, year, left, right):
    values = frame[frame.Year.isin([left, right])].pivot(index=["Entity", "Code"], columns="Year", values="Land use (per capita): Cropland")
    fraction = (year - left) / (right - left)
    return (values[left] + fraction * (values[right] - values[left])).rename(str(year))


locations = pd.read_parquet(LOCATIONS, columns=["location_tag", "calibrated_lon", "calibrated_lat"]).dropna()
metadata, arrow = pyogrio.read_arrow(COUNTRIES)
geometry_column = metadata.get("geometry_name") or next(name for name in arrow.column_names if name.lower() in {"geometry", "wkb_geometry"})
country_fields = {name: arrow[name].to_pylist() for name in ("ADMIN", "ADM0_A3")}
country_geometry = from_wkb(arrow[geometry_column].to_pylist())
factors = pd.read_csv(FACTORS)

start = interpolate(factors, 1337, 1300, 1400)
end = interpolate(factors, 1837, 1830, 1840)
factor_table = pd.concat([start, end], axis=1).reset_index()

# Natural Earth exceptions where its three-letter code differs from OWID's standard entity code.
code_aliases = {"SOL": "SOM", "CYN": "CYP", "KOS": "OWID_KOS", "SAH": "ESH"}
country_codes = pd.Series(country_fields["ADM0_A3"]).replace(code_aliases)

pts = points(locations.calibrated_lon.to_numpy(), locations.calibrated_lat.to_numpy())
tree = STRtree(country_geometry)
point_ids, polygon_ids = tree.query(pts, predicate="within")
assigned = np.full(len(locations), -1, dtype=int)
assigned[point_ids] = polygon_ids

# Tiny islands can miss the generalized shoreline; assign them to the nearest polygon.
missing = np.flatnonzero(assigned < 0)
if len(missing):
    nearest = tree.query_nearest(pts[missing])
    assigned[missing[nearest[0]]] = nearest[1]

locations = locations.reset_index(drop=True)
locations["code"] = country_codes.iloc[assigned].to_numpy()
locations["country"] = pd.Series(country_fields["ADMIN"]).iloc[assigned].to_numpy()

duplicates = factor_table[factor_table.Code.notna() & factor_table.Code.duplicated(keep=False)].sort_values("Code")
if not duplicates.empty:
    print("Duplicate factor codes; keeping first:", duplicates[["Entity", "Code"]].to_dict("records"))
factor_by_code = factor_table.dropna(subset=["Code"]).drop_duplicates("Code").set_index("Code")
locations["start"] = locations.code.map(factor_by_code["1337"])
locations["end"] = locations.code.map(factor_by_code["1837"])

# Keep the map complete: units without an OWID factor are explicitly no-data, not silently zero.
valid = locations.start.notna() & locations.end.notna()

country_rows = []
country_index = {}
for code, group in locations.groupby("code", sort=True):
    row = factor_by_code.loc[code] if code in factor_by_code.index else None
    idx = len(country_rows)
    country_index[code] = idx
    country_rows.append([
        str(group.country.iloc[0]),
        str(code),
        None if row is None or pd.isna(row["1337"]) else round(float(row["1337"]), 4),
        None if row is None or pd.isna(row["1837"]) else round(float(row["1837"]), 4),
    ])

location_rows = [
    [round(float(lon), 3), round(float(lat), 3), country_index[code], tag]
    for lon, lat, code, tag in locations[["calibrated_lon", "calibrated_lat", "code", "location_tag"]].itertuples(index=False, name=None)
]

payload = {
    "countries": country_rows,
    "locations": location_rows,
    "land": {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "properties": {}, "geometry": mapping(geom)}
            for geom in simplify(country_geometry, 0.18, preserve_topology=True)
        ],
    },
    "coverage": {"total": int(len(locations)), "withFactor": int(valid.sum())},
}

template = (ROOT / "tmp/hyde_country_modifier/template.html").read_text(encoding="utf-8")
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(template.replace("__DATA__", json.dumps(payload, separators=(",", ":"))), encoding="utf-8")
print(json.dumps({
    "output": str(OUTPUT),
    "bytes": OUTPUT.stat().st_size,
    "locations": len(locations),
    "mapped_factors": int(valid.sum()),
    "no_factor_codes": sorted(locations.loc[~valid, "code"].unique().tolist()),
}, indent=2))
