# Round 35: central provincial survival screen

**All 44 central-candidate provincial survival checks pass with the 25% D50-decay offset. The model is not yet accepted.** The low Cusco crop/management estimate still fails. Dated benchmarks, independent holdouts, global collateral, complete scenario coverage and water/opportunity maxima remain separate gates.

This comparison retains all 22 complete provinces and both mandatory horizons. It uses the same starting state, active effects, employment reservations, food production and consumption across pressure-offset candidates. Cookeries and victuals markets remain urban supply; there is no additional food-building allowance or higher-pop consumption cut.

## The concrete crop-input repair

Pisaq had reconstructed current dry fields but zero conditional crop support. That drove its central round-34 peasant consumption above 400 food/month and exhausted the shared provincial food budget. Increasing management alone did not fix it.

The new explicit analogue fills only zero support on current dry fields within the documented Cusco system. Its range is the full positive-density envelope of six same-province, same-native-climate donors: 122.545–401.197 people per cultivated km² at source reference development 25. The inherited calendar is removed before constructing the range, and reference development is removed once before applying recipient effectiveness. No population enters donor selection, no positive yield is raised, and no land or irrigation is added.

This is an inferred comparison, not a measured Pisaq yield. The native climate class is coarse; cultivar, fallow and source-history uncertainty remain. [The evidence record](cusco_missing_crop_evidence.json) freezes donors, source hash, units and exclusions. [FAO’s Andean-system account](https://www.fao.org/giahs/giahs-around-the-world/peru-andean-agriculture/en) supports altitude-adapted crops and maintained systems, not the numerical transfer itself.

| Cusco assignment | Year 100 minimum local population retention | Year 200 | Unmet location-months through year 200 | Result |
|---|---:|---:|---:|---|
| unchanged | 45.37% | 43.19% | 2448 | failed |
| low | 81.78% | 82.26% | 513 | failed |
| central | 100.00% | 100.00% | 0 | passed |
| high | 100.00% | 100.00% | 0 | passed |

## Both required horizons, central candidate

| Province | Population retained at 100 | At 200 | Minimum development retained across horizons | Unmet location-months through 200 | Result |
|---|---:|---:|---:|---:|---|
| acamama_province | 100.00% | 100.00% | 101.34% | 0 | passed |
| alexandria_province | 121.01% | 122.84% | 100.29% | 0 | passed |
| anahuac_province | 101.12% | 101.48% | 107.89% | 0 | passed |
| angkor_province | 112.61% | 113.46% | 100.52% | 0 | passed |
| bali_province | 90.21% | 91.61% | 99.59% | 0 | passed |
| cairo_province | 153.57% | 156.65% | 100.72% | 0 | passed |
| central_doab_province | 205.40% | 224.56% | 113.89% | 0 | passed |
| delhi_province | 186.78% | 196.19% | 112.96% | 0 | passed |
| jiaxing_province | 136.27% | 142.31% | 100.21% | 0 | passed |
| kano_province | 137.09% | 140.53% | 113.78% | 0 | passed |
| la_plata_province | 100.00% | 100.00% | 103.79% | 0 | passed |
| liaoyang_province | 106.96% | 107.29% | 109.47% | 0 | passed |
| obdorsk_province | 100.00% | 100.00% | 100.50% | 0 | passed |
| ogan_province | 109.55% | 110.06% | 100.57% | 0 | passed |
| patna_province | 156.41% | 156.41% | 101.14% | 0 | passed |
| pays_france_province | 104.25% | 104.73% | 100.88% | 0 | passed |
| qikiqtaaluk_province | 299.45% | 899.16% | 106.35% | 0 | passed |
| shuntian_province | 146.72% | 151.18% | 101.99% | 0 | passed |
| songjiang_province | 164.47% | 186.11% | 100.48% | 0 | passed |
| suzhou_province | 138.80% | 152.80% | 100.07% | 0 | passed |
| timbuktu_province | 112.19% | 112.57% | 102.94% | 0 | passed |
| trowulan_province | 97.71% | 98.07% | 99.61% | 0 | passed |

These are per-location peaceful survival predicates, not provincial averages or historical population targets. Without the retention offset, 43/44 pass: Bali reaches 89.903% at year 100. Both 25% and 50% offsets pass 44/44; the smaller offset remains the conservative candidate.

The new coverage diagnostic identifies 659 locations with current dry fields but zero source crop density; one is explicitly inferred and 658 remain unresolved. These can include misclassified water-dependent fields as well as missing crop evidence. The diagnostic is not authorization to give every flagged location a yield. The complete list is in `crop_density_coverage_conflicts.csv`.

The new source-gap, inferred and unresolved ledger flags are independent. A numerical fill does not relabel the original source as observed. Existing tests cover evidence requirements, applicability dates, reference units, unchanged positive yields and hectare conservation.

## Remaining acceptance actions

- Resolve whether the low Andean range represents plausible starting support or a genuine scarcity case; do not discard it because it fails.
- Evaluate every global beneficiary of the rank/pressure candidate, including low-fill growth and already prosperous regions. The world comparison keeps food buildings unchanged and checks annual checkpoints against monthly provincial histories.
- Complete the nine-group criteria register on this exact candidate: numerical historical/holdout criteria, stocks/compositions/shocks, actual-composition equilibria, demographic applicability, dated investment, physically bounded maxima and joint sensitivity. Earlier artifacts cannot certify changed inputs.
- Preserve model/export separation. No game export, live deployment, building-level balance or accepted manifest has been produced.

Reproduce:

```sh
uv run python research/population_capacity/run_management_assessment.py --assignments research/population_capacity/historical_assignments_round_35.json --system cusco_preimperial_maintained_fields --output artifacts/data/population_simulation/repair_round_35/cusco_crop
uv run python research/population_capacity/run_acceptance_retention_comparisons.py --assignments research/population_capacity/historical_assignments_round_35.json --output artifacts/data/population_simulation/repair_round_35/pressure --no-frozen
uv run python research/population_capacity/run_candidate_world_comparison.py --assignments research/population_capacity/historical_assignments_round_35.json --output artifacts/data/population_simulation/repair_round_35/world --monthly-reference artifacts/data/population_simulation/repair_round_35/pressure/pressure_offset_0.25.parquet
uv run python research/population_capacity/summarize_candidate_round_35.py
uv run ppc test -q
```


Full validation: 846 passed, 1 skipped in 626.7 seconds. Recorded code/test inputs match current files. Existing environment-dependent setup-building-error-log fixture; local game log contains no matching setup errors.
The focused historical/food/land regressions passed 27 tests. [Global collateral results](round_35_world_findings.md) remain separate from this regional survival gate.

