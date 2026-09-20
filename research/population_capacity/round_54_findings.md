# Round 54: grouped Nile allocation fails before simulation

Status: **rejected spatial analogue; no candidate adopted**. Round49 remains
unchanged. The rejection identifies an input-accounting problem that survival
tests would not resolve.

## Frozen comparison

The seven-group contract was written before calculating allocations. It uses
Willcocks's1889 seasonal-basin province shares as an explicitly later spatial
analogue for the rough1315 regional total of8,400km². Summer-irrigation tracts
are excluded. Named game locations are partitioned into approximate historical
province groups. Population, food deficits, development and consumption are
absent from the allocation inputs.

This is deliberately weaker than a digitized historical basin crosswalk. It
tests whether that coarser source constraint is at least internally feasible;
passing would not establish medieval local acreage.

## Physical result

| Inferred group | Proposed fields km² | Current fields km² | Current conversion ceiling km² | Result |
|---|---:|---:|---:|---|
| Esna |400.58|147.73|2,526.79|Feasible|
| Kena |1,316.57|482.41|1,411.52|Feasible|
| Girga |1,642.56|443.41|694.44|Above ceiling|
| Assiut |1,936.41|630.12|1,346.21|Above ceiling|
| Minia |1,204.60|455.71|1,713.71|Feasible|
| Beni Suef |1,066.74|656.56|1,666.12|Feasible|
| Guza |832.52|1,092.73|1,743.90|Below current fields|

The reusable builder saves the conflicts and writes no assignments. It does
not cap the first two failures, erase existing Guza fields, or move the excess
to unrelated locations. Changing HYDE to LUH2 within-group weights cannot fix
these group totals, so a second simulation would not test a different physical
case. No population simulation was run for the rejected input.

## Diagnosis

The ceiling in all seven groups equals the annual crop-mixture suitability
area, within4.55e-13km². That quantity is already documented as a conditional
crop denominator, not a surveyed union of possible fields. Thus these failures
do not prove that the historical basin estimate was physically impossible.

For context, the related HYDE2025 cultivated estimates are1,210.57km² in the
Girga group and1,702.01km² in Assiut, both above their current model ceilings.
Those modern reconstructions do not supply1337 fields or independent validation;
they flag that the ceiling cannot be treated as a proven timeless land limit.
Conversely, Guza's starting fields exceed both the grouped proposal and that
later HYDE diagnostic. Source dates, categories and geographical coverage differ.

Whole-location province partitioning is another unresolved approximation:
historical basin/province boundaries need not coincide with game boundaries.
The next correction must distinguish that mismatch from the agronomic-mask
problem. Replacing the ceiling with total location area or promoting modern
fields directly to starting infrastructure would not resolve either.

## Framework changes and checks

`build_upper_nile_allocation.py --group-contract` now evaluates all group
constraints before writing an assignment. It verifies source transcription
hashes, exact disjoint coverage, common regional totals and source-province
uniqueness. Grouped attempts require a fresh output directory so a rejected run
cannot leave an earlier assignment masquerading as its result. Successful
fixture assignments carry the grouped source contract in their provenance.

Four new regressions cover source/partition checks, rejection without clamping,
neighbour preservation/provenance and stale-output protection. Together with
the canonical area allocator: **11passed**. The ungrouped path reproduces all
columns of round51's21-location allocation exactly. The latest full suite
remains round52's878passed/1explained skip; no new full-suite claim.

## Reproduction

The first command intentionally exits nonzero after writing the physical
rejection and feasibility table. Use a fresh grouped output directory.

```sh
uv run python research/population_capacity/build_upper_nile_allocation.py --ledger artifacts/data/population_simulation/repair_round_49/world/starting_ledger.parquet --base-assignments research/population_capacity/historical_assignments_round_49.json --output artifacts/data/population_simulation/repair_round_54/grouped_hyde/input --boundary with_cairo --weights hyde --group-contract research/population_capacity/upper_nile_grouped_allocation_experiment.json
uv run python research/population_capacity/audit_grouped_nile_failure.py --ledger artifacts/data/population_simulation/repair_round_49/world/starting_ledger.parquet --groups research/population_capacity/upper_nile_grouped_allocation_experiment.json --output artifacts/data/population_simulation/repair_round_54/grouped_hyde/input
uv run ppc test tests/test_grouped_nile_allocation.py tests/test_regional_field_extent.py -q
```

No higher-pop/slave consumption change, urban food replacement, game export or
live deployment. The dated-geography gate and overall acceptance remain open.
