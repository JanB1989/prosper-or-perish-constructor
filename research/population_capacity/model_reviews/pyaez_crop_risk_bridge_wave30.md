# Wave 30: crop-specific GAEZ interannual-risk bridge

The remaining crop-risk blocker was narrowed using the official GAEZ Appendix
4.2 water-limited-yield parameters already present in the repository. The
parser resolves 28 published rows across 20 of the 23 registered food-crop
families. Each resolved family now has a same-geography GAEZ baseline, source
water coefficients, and explicit rain-fed/irrigated response semantics in the
coverage matrix.

## Coverage

```text
crop/mode matrix: 46 rows
same-geography labels: 962,734
family-level water bridge rows: 40/46
blocked rows: 6 (banana, cassava, taro; both modes)
exact PyAEZ rows: 0
```

The 20 resolved families are usable for a source-backed interannual fallback
using the published GAEZ `Ky`, stage, and crop-coefficient rows. This closes a
real gap in the former broad family-constant response, but the artifact does
not claim that family rows are mapped to every cultivar/LUT. LUT-specific
agro-climatic, soil, terrain, and perennial constraints remain unresolved.
Banana, cassava, and taro remain blocked because the cited annual-crop water
appendix has no corresponding published rows.

## Strict acceptance state

The bridge is diagnostic only and cannot unlock the exact challenger:

```text
exact_pyaez_ready = false
independent_risk_validation_complete = false
physical_uncertainty_gate_eligible = false
training_challenger_eligible = false
```

No values are copied from another crop, region, or global median. Missing
families remain blocked rather than receiving a proxy coefficient.

## Artifacts

- `artifacts/data/population_capacity/pyaez_1337/exact_engine_wave30/crop_risk_bridge_coverage.parquet`
- `research/population_capacity/model_reviews/pyaez_crop_risk_bridge_wave30.json`

The audit SHA-256 is
`145b825fe90836e75ce31e75f80ebc87c0ef4bf4fe5103eed0ef255d77e3adf9`.
The source Appendix 4.2 hash is
`8e26477f8b033e17171282c0cb14e7edce2230d44237f7097e46dae0691d30fb`.

