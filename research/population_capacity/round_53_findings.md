# Round 53: exact Nile game geometry and river intersections

Status: spatial crosswalk machinery evaluated; historical allocation remains
open. Round49 is unchanged and no simulation result is recertified by this audit.

The new auditor reconstructs all24 locations in the four Upper Nile provinces
and Cairo province from the configured game's actual location raster. Every
location's pixel count matches the cached geometry. Both raster and canonical
coordinate-transform identities match the physical sampling contract. No local
coordinate shift or alternative historical-area denominator is introduced.

The resulting polygons are intersected with368 cached RiverATLAS main-Nile
reaches. The reach-level sums reconcile with the union of the channel geometry
to1.43e-14km. Polygon areas under a local equal-area projection differ from the
canonical area calculation by at most0.217%; the canonical areas remain the
model inputs. Projected polygon areas are diagnostic only.

## What changes the next allocation

The map confirms that the named game locations are not interchangeable slices
of an equally wide valley. Several northern locations primarily occupy one bank.
Under the existing transform, Cairo and Atfih have no intersection with the
selected modern trunk centerline, while Giza contains100.75km. That does not mean
Cairo or Atfih lack agricultural water: adjacent-bank fields and maintained
canals matter. Faiyum likewise has zero intersection with the main stem, as
expected for its distinct canal system.

Aswan contains61.87km of selected trunk, Edfu57.48km, Kom Ombo63.31km and
Esna102.51km. Assigning hectares in proportion to channel length would therefore
not reproduce the separately documented basin-chain areas. Uniform buffers at
0.5/1/2/5km per bank are saved as sensitivity diagnostics, never as historical
cultivated hectares. The geometry is ready for a bank/section-aware crosswalk;
the dated basin table cannot be joined to locations solely by town names.

Modern reach discharge is used only to select the major trunk within the cached
Nile basin. It is not a1337 water budget. Source distance-to-mouth values are
retained on the reach/location intersections; they are not equated with
Willcocks's distance from the Barrage.

The cached GFPLAIN data was considered as an additional spatial source. Its
[primary description](https://www.nature.com/articles/sdata2018309) limits
applicability in desert and ice-covered regions. Neither a positive sample nor
a zero in that global product, by itself, certifies medieval basin access.
No GFPLAIN-derived hectare limit is adopted here.

## Artifacts and reproduction

`artifacts/data/population_capacity/repair_round_53/nile_geometry/` contains:

- `game_location_polygons.geojson`: exact raster-derived geographical boundaries.
- `river_reach_location_intersections.csv`: reach IDs, downstream links, source
  distance and channel length in each location.
- `location_river_crosswalk.csv`: canonical fields/area and corridor diagnostics.
- `selected_river_reaches.csv`: the explicit modern-reference selection.
- `nile_geometry.png`: visually checked map with location labels and channel.
- `manifest.json`: source/code hashes, evaluated invariants and limitations.

```sh
uv run python research/population_capacity/audit_nile_game_geometry.py --ledger artifacts/data/population_simulation/repair_round_49/world/starting_ledger.parquet --locations-png '/mnt/c/Games/steamapps/common/Europa Universalis V/game/in_game/map_data/locations.png' --output artifacts/data/population_capacity/repair_round_53/nile_geometry
```

Resolve `--locations-png` from the game install in `constructor.load_order.toml`
on another machine. The auditor verifies its content hash against the canonical
samples rather than accepting a different installed raster silently.

The auditor executed successfully, including exact-pixel, transform and
intersection-accounting checks. The latest full suite remains round52's
878passed/1explained skip; only this research auditor and documentation changed
since then. No balance, game export or live deployment occurred. The source
section-to-game allocation and remaining acceptance groups are still open.
