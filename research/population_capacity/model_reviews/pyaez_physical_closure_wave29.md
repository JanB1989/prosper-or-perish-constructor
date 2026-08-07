# Wave 29: strict PyAEZ physical closure

This wave combines the exact-engine inventory, the source-backed GAEZ variant
uncertainty envelope, and the official GAEZ agro-climatic constraint source
audit. The result is a strict gate, not a relabeling pass.

## Result

- Same-geography GAEZ fallback coverage is complete: 962,734 location × crop ×
  water-mode rows across 20,929 locations, 23 crops, and two modes.
- Exact EU5 PyAEZ rows remain zero. The official runtime smoke is only the Laos
  maize tutorial (rain-fed and irrigated), and its 23 input files are hash
  recorded.
- The official Appendix 5.1 constraint PDF contains six pages and only one
  registered crop-family text match (`wheat`). Text presence is not a valid
  crop/LUT/thermal-zone runtime mapping, so no constraint row is promoted.
- The GAEZ variant envelope remains diagnostic uncertainty information; it is
  not an independent PyAEZ run and cannot unlock training.

The closure artifact therefore reports:

```text
same_geography_fallback_rows = 962734
exact_eu5_rows = 0
exact_pyaez_ready = false
training_challenger_eligible = false
state = blocked
```

## Artifacts and hashes

- `research/population_capacity/model_reviews/pyaez_physical_closure_wave29.json`
  - closure hash: `07887dbb9ddba16b68d28730cff48ef06019d357425a4f93d033e5298e37d8d7`
- `research/population_capacity/model_reviews/gaez_constraint_source_audit_wave29.json`
  - source SHA-256: `f4f2c99c3434ed0f7080786c3e709511a16928d94d1686803bd6c0c4cb2041ac`

The exact EU5 gate stays closed until every crop/mode has independently
validated water, constraint, soil, and terrain semantics at the same EU5
footprint. Approximate rows remain explicitly fallback/uncertainty states.
