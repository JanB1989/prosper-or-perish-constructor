# Wave 29: GAEZ agro-climatic constraint source audit

The official local copy of GAEZ Appendix 5.1 was inspected with `pypdf`.
It contains six pages and 7,202 extracted characters. Only the literal term
`wheat` was found among the 23 registered crop families; the other 22 families
have no text match in this source. The source is therefore not a complete
crop/LUT/thermal-zone constraint matrix for the registered EU5 labels.

This is a source-availability result, not permission to copy a constraint from
another crop. PDF text presence is insufficient for exact runtime use: a valid
mapping would still need table extraction, units, row identity, thermal-zone
semantics, water-mode compatibility, and PyAEZ regression tests. The audit
keeps `exact_runtime_mapping_ready=false` and leaves the exact challenger gate
closed.

Artifact: `research/population_capacity/model_reviews/gaez_constraint_source_audit_wave29.json`.
Source SHA-256: `f4f2c99c3434ed0f7080786c3e709511a16928d94d1686803bd6c0c4cb2041ac`.

