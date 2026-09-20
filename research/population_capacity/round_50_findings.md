# Round 50: source dating and the Upper Nile raster discrepancy

Status: **provenance correction and source diagnosis; no new balance candidate**.
Round49's numerical state is unchanged and overall acceptance remains open.

## Source dates are no longer inferred from filenames

The five cached HYDE files named `*_1337.tif` declare `requested_year=1337` but
`hyde_year=1300` and source band24. Preparation now records the actual source
year, requested year, dataset, band, units and date-match status. Missing metadata
is explicitly unknown; malformed dates fail rather than silently becoming1337.
The management food auditor no longer hardcodes the starting HYDE evidence as1337.

This is a provenance correction, not a change to raster values or an instruction
to interpolate a new date. A canonical re-preparation reproduces all412 columns
of round49's20,929-location starting ledger exactly, including food stocks,
population composition, development and capacity. `provenance_replay.json`
records that verification and current input identity. Historical artifacts keep
their original identities; this does not automatically recertify acceptance.

## The low area exists before game-location aggregation

The new source audit sums complete native HYDE cells in a coarse geographic
rectangle from23.5–30.1°N and29–34°E, covering the Aswan-to-Cairo corridor and
Fayyum. Outward cell rounding extends the northern edge to30.16667°N. It uses
per-cell km² values directly, with no population, centroid sampling or game-area
multiplier:

| Source component, actual year1300 | Area in the rectangle |
|---|---:|
| Cropland | 1,448.58355 km² |
| Irrigated land | 1,448.58355 km² |
| Rainfed land | 0 km² |
| Pasture | 0 km² |

There are4,699 valid and101 masked cells in each window. The equality of crop
and irrigation totals is evidence of water dependence **within this source**;
it does not independently date irrigation in1337 or establish the absence of
pastoral livelihoods.

The rectangle is not a historical basin polygon and is not identical to the
round49 game-province brackets. Nevertheless, the low total is already present
in the raw raster: correcting game sampling alone cannot explain the difference
from Borsch's rough8,400 km² estimate for1315 Upper Egyptian basins. The fifteen-year
source-date difference is now explicit; it is not a measured explanation for
the magnitude of the discrepancy.

The cached NetCDF metadata additionally declares `HYDE3.4`, with description
`HYDE3.4 test netCDF`, input date4Apr2025 and CC-BY-3.0, despite the output folder
being named `hyde_3_5`. Both declarations are recorded. Directory naming is not
proof of a scientific source version. The source audit hashes both GeoTIFFs and
NetCDF files; no cached dataset is overwritten or silently relabelled.

## Consequence for calibration

The Nile extent discrepancy needs a dated regional land reconstruction and
explicit spatial uncertainty. It must not be patched with a population floor,
a higher global capacity scale, or an automatic maximum of disagreeing sources.
Future regional hectare assignments must preserve the distinction between
seasonal Nile basins and Fayyum canals, allocate by land evidence rather than
population, and reconcile displaced livelihoods and physical opportunity.

No source extent, management assignment, subsistence coefficient, urban supply or
consumption rate was changed in this round. Food buildings remain the urban
supply mechanism. The broader historical, demographic, physical-maxima and
acceptance requirements remain open.

## Reproduction and verification

```sh
uv run python research/population_capacity/audit_nile_source_rasters.py --output artifacts/data/population_simulation/repair_round_50/nile_source_audit
uv run ppc test tests/test_simulation_source_provenance.py tests/test_population_simulation_profile.py tests/test_simulation_fingerprints.py -q
```

Focused regressions: **13 passed**, including four new provenance tests. The
last full suite remains round49's867passed/1explained skip; this round does not
claim a fresh full-suite result after the provenance changes. No export or live
deployment occurred.
