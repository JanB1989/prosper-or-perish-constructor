# Wave 28: source-backed PyAEZ uncertainty envelope

This wave investigated whether the official PyAEZ source could be expanded
beyond its bundled Laos tutorial and, failing that, built the strongest
defensible physical challenger artifact without inventing crop parameters.

## What was verified

- The complete registered matrix is present: 23 crops × 2 water modes = 46
  rows, covering 20,929 EU5 locations per key (962,734 location labels).
- The sampled GAEZ v5 footprint matrix is complete: 46 × 1,339,456 sample
  rows = 61,614,976 rows. File hashes and source hashes are recorded in the
  JSON audit and Parquet matrix.
- The official GAEZ v5 biomass workbook provides every registered crop's LUT
  family. For each crop, the artifact reports min/median/max envelopes for
  reference cycle, harvest index, LAI, thermal limits, and related parameters.
- Structural zero is preserved: GAEZ's zero/NULL selected-LUT sentinel is not
  counted as a crop variant, while finite zero yields remain zero-yield sample
  outcomes.
- No row is promoted to `exact_pyaez`; every current location label remains the
  GAEZ v5 same-geography physical fallback.

## Why this does not unlock exact PyAEZ

The official PyAEZ 2.2 repository contains runnable maize/sugarcane tutorial
inputs, not complete same-footprint EU5 crop/mode workbooks. The GAEZ water
parameter rows are source-backed but have not been mapped to each biomass LUT,
and crop/mode constraint tables are not published in the runtime contract.
Banana, cassava, and taro also have no annual-crop water row in the cited GAEZ
water appendix. The matrix therefore reports
`blocked_water_parameter_mapping_and_crop_mode_constraints` (or the equivalent
crop-specific blocker) and keeps `exact_pyaez_ready=false` and
`training_challenger_eligible=false`.

The official source receipt is independently hash-verified at commit
`b314640710a3ec398482b0065f4f26f45494eefa` and contains 23 data-input files,
all Laos/maize tutorial inputs; it reports zero exact EU5 rows. Their paths,
byte sizes, and SHA-256 values are carried into the wave28 audit.

The variant envelope is valid for sensitivity analysis and uncertainty
diagnostics, but it is not an independent PyAEZ simulation and must not be
silently averaged into the production labels.

## Artifacts

- `artifacts/data/population_capacity/pyaez_1337/exact_engine_wave28/gaez_parameter_uncertainty_coverage.parquet`
- `research/population_capacity/model_reviews/pyaez_parameter_uncertainty_wave28.json`

The audit records registry, biomass/water source, label, sample-file, and
combined source-manifest SHA-256 values. The build intentionally exits non-zero
because this is a diagnostic artifact and the exact/challenger gate remains
closed.
