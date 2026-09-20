# Round 36: common growth, stock resilience and source audit

**Not accepted.** This round extends the canonical scenario configuration to shared rank growth and bounded land-pressure retention, including the native additive tribal cancellation. Urban food supply remains the responsibility of cookeries, victuals markets and external supply. Consumption rates are unchanged. No new building food, capacity export or deployment is assumed.

The common-slower-quarter comparison uses subsistence output 1.30, common annual rank growth −0.005 and a monthly pressure offset equal to 25% of decay at development 50. Geography is round 35, shared physical scale 3, area exponent 0.75, development capacity coefficient 0.05, urban accommodation 3 per observed worker, and the unchanged 75% staffed agricultural-employment experiment. These are candidate settings, not accepted balance.

## Evaluated behavior

- Coupled development, actual composition, stocks 0/3/12/24 months: all 22 complete provinces pass the peaceful survival screens at both years 100 and 200 (176 horizon checks).
- Frozen development, the same four stock levels: 168 of 176 horizon checks pass. Bali fails all eight population-retention checks, retaining 89.02–89.14% at year 100 and 88.765–88.768% at year 200. Development remains constant and no unmet food is recorded. This is a population-growth equilibrium failure, not starvation or proof that capacity needs inflation.
- Pure-peasant development-50 food break-even is fill 1.15; growth/stock equilibrium is fill 1.053704 with 7.92 months of food. These are distinct measurements.
- Saved monthly population components, finite/nonnegative state, checkpoints and historical land allocation pass their current checks. Full food/storage/land reconciliation and all nine-group coverage are not thereby established.
- The global monthly/checkpoint replay residual is zero. The slower-quarter world reaches 495.736 million and 540.601 million at years 100/200. Relative to the same-output native-rank control, 23 locations have increased unmet-food duration at each horizon. This is a collateral diagnosis list, not an accepted exception. See [global results](round_36_world_findings.md).

The report `evaluated_horizon_criteria.csv` derives each horizon's status from its actual checks. The older `province_horizon_results.csv` contains diagnostic evaluations of non-nominated controls and its `behavior_status` must not be mistaken for a survival-gate result. The new evidence summary preserves failed, passed and unresolved group states and rejects mismatched candidate fingerprints.

## Source defect before further balance selection

The cached crop labels give wheat, barley and rye physical-fallback availability 0.5 in Pisaq, Tenochtitlan and La Plata. FAO's 1994 historical agricultural synthesis describes these as colonial introductions, and rice as an introduced crop accompanying colonial land transformation. The existing numerical crop-history closure does not establish historical eligibility. [Pinned source interpretation](crop_availability_repair_evidence.json) records the source hash, pages, scope and exclusions. Exact exclusion geometry and annual crop-system recomputation remain to be implemented. Do not silently replace the joint rainfed contract with static sampled yields. Andean missing indigenous crops and round-35 donor availability must be reconsidered together; current central Cusco passes do not certify the donor envelope.

The nine acceptance groups remain open: historical numerical criteria and source correction; independent holdouts; full composition/shock matrix; actual-composition equilibria; frozen applicable demographic ranges; dated typed investment; simultaneous physical maxima and urban worker competition; joint sensitivity; active modifier and food-account coverage. Existing group missing-action text predates some newly evaluated frozen runs and must be interpreted alongside the actual evidence, not as proof those runs were absent.

## Reproduction and validation

```sh
uv run python research/population_capacity/run_candidate_world_comparison.py --assignments research/population_capacity/historical_assignments_round_35.json --output artifacts/data/population_simulation/repair_round_36/world --scenario-file research/population_capacity/common_growth_scenarios.json --override mechanics.subsistence_output=1.3
uv run python research/population_capacity/run_acceptance_round_25.py --assignments research/population_capacity/historical_assignments_round_35.json --output artifacts/data/population_simulation/repair_round_36/acceptance --scenario-file research/population_capacity/common_growth_scenarios.json --scenario common_slower_quarter --override mechanics.subsistence_output=1.3 --include-frozen
uv run python research/population_capacity/summarize_candidate_world.py --output artifacts/data/population_simulation/repair_round_36/world --report research/population_capacity/round_36_world_findings.md --selected-scenario common_slower_quarter
uv run python research/population_capacity/summarize_acceptance_evidence.py --output artifacts/data/population_simulation/repair_round_36/acceptance
uv run ppc test -q
```

Full core validation: 848 passed, one existing environment-dependent skip in 671.53 seconds. The skipped setup-error-log fixture has no matching local game errors. The full-test input fingerprint is saved in `repair_round_36/full_test_result.json`. Subsequent changes in this turn are research reporting and source interpretation, not gameplay/core changes. Building implementation, export and live deployment remain deferred.
