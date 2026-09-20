# Round 42: broad acceptance, stable identities and measured recovery

Status: **not accepted**. This round combines the bounded central Lombok assessment with the corrected Malang rice source, then evaluates the broader stock/development programme. The underlying subsistence controls behave consistently; four geographical cases continue to fail.

## What was evaluated

The canonical candidate covers 20,929 starting locations, with monthly trajectories for 124 locations in 22 complete food-sharing provinces. Stocks of 0/3/12/24 months run with coupled and frozen development; paired temporary production losses and a year-25 physical clearing activation are separate scenarios. Both years 100 and 200 are evaluated.

| Evaluated evidence | Passed horizon checks | Failed horizon checks | Limit |
|---|---:|---:|---|
| Historical province viability across stocks/development | 288 | 64 | Every case of Bali, Trowulan, Cusco/Acamama and Anahuac fails: 16 checks each |
| Paired scenario food-control histories | 16 | 0 | Controlled perturbation checks, not complete historical economic coverage |
| Fixed-system equilibrium/recovery comparisons | 50 | 0 | Five development levels × five perturbations × two horizons; pure peasants |
| Experimental clearing progression | 2 | 0 | Physical activation experiment, not a historically dated investment programme |

The original mechanism controls also pass, including frozen controls. All nine acceptance groups are still represented explicitly. Geography is failed; the remaining groups retain unresolved coverage, rather than receiving a pass from these narrower results. The authoritative table is `acceptance_stable/evaluated_criteria_register.md`, with the individual horizon checks in `evaluated_horizon_criteria.csv`. The compatibility `criteria_register.md` contains the same current group table.

## Fingerprint correction and replay

Matching the recovery experiment exposed a cross-process identity defect. The model fingerprint used `repr(profile)`; unordered `frozenset` fields generated different text under different Python hash seeds. Cache hit/miss was only a coincident diagnostic difference, not the cause. Deterministic serialization now handles dataclasses and unordered sets, and the profile itself is hashed instead of its representation. Tests verify identity under seeds 1/2/3 and invalidation when population sets, coefficients or source bytes change.

The stable-identity rerun reproduces all 13 saved monthly histories exactly for population, development, capacity, stocks, production and consumption. `identity_fix_replay.json` records that comparison. The old `acceptance/` run is a superseded identity experiment; use `acceptance_stable/`. The recovery recipe reproduces the latter's model-input fingerprint. No gameplay parameter changed for this repair.

## Food pressure and growth behaviour

These are synthetic controls, not mapped historical population targets. The quarter-full pure-peasant control grows to 2.206× initial population at year 100 and 3.553× at year 200. Its instantaneous annualized growth falls from about 0.635% at year 100 to 0.334% at year 200 as fill rises. It never reaches the food-growth ceiling. The deliberately overpopulated, twice-capacity control falls to 53.0%/54.9% of its initial population, so genuine scarcity still permits decline.

The extremely sparse boundary control spends most months at the food-growth ceiling, with about 1% annualized growth and a 69-year doubling time. It starts at only about 0.5% fill; this is an intentionally extreme physical-system control, not proof that a particular frontier should have millions of starting capacity. Its population reaches 2.690×/7.308× at years 100/200. This distinguishes maximum growth in real spare capacity from a claim that the geographical map is correct.

The supplied-urban-food control reaches 2.425×/2.579× and slows considerably; the native self-provisioning tribal control remains at its starting population under the authorized offsets. Urban controls retain explicitly supplied food as a mechanism assumption; their numeric supply does not become free game output or a geographical capacity allowance.

Full growth/CAGR, fill, cap-duration and doubling-time summaries are in `mechanism_controls_growth_summary.csv` and `frozen_mechanism_controls_growth_summary.csv`.

## Equilibrium and recovery

Across development 0/25/50/75/100, pure-peasant food production equals consumption near fill **1.15**. The population-and-stock equilibrium is different: fill **1.053704**, with approximately **7.92 months** of stocks. It includes native stock decay.

Five unshocked controls remain stationary over 200 years; their maximum relative population drift is below 4.8×10⁻¹². Paired experiments perturb population by ±10% at unchanged absolute initial stocks, or halve/double stocks at unchanged population. Development and prosperity are explicitly frozen. At D50, log-population deviation halves sustainably after 241 months for the deficit and 196 months for the excess (about 20.1/16.3 years). Stock-only perturbations halve their stock deviation after 60 months. Absolute population deviation is also reported separately.

[The population-convergence extraction](population_convergence_extraction.json) now identifies Table 3 column 2 of Madsen et al. rather than borrowing a wage estimate. Its reported coefficient −0.028 and 30-year observation interval imply a log-population deviation factor of 0.16 and an approximately 11.35-year half-life. That regression covers nine mainly European countries in 1470–1870 with additional controls. It is a contextual population comparison, not an intrinsic growth rate, a universal local recovery deadline or an accepted range for medieval tropical/tribal cases. Historical applicability remains unresolved.

The attachment command verifies the recovery recipe/code identity, recomputes recovery measurements from saved monthly histories and binds the evaluated cases to the current acceptance fingerprint. It does not mark the historical comparison accepted.

## Tests and reproduction

The full `uv run ppc test -q` suite passes: **854 passed, one skipped**, in 614.08 seconds. The skip was independently checked with `-rs`: the current local `error.log` contains no setup-building errors, so that environment-dependent test has no cases. Fourteen focused fingerprint/profile/acceptance tests also passed. The result and source fingerprint are in `repair_round_42/full_test_result.json`.

```sh
uv run python research/population_capacity/run_acceptance_round_25.py --assignments research/population_capacity/historical_assignments_round_40.json --output artifacts/data/population_simulation/repair_round_42/acceptance_stable --scenario-file research/population_capacity/round_37_source_replay_scenario.json --scenario common_slower_quarter --include-frozen --override mechanics.subsistence_output=1.3 --override 'paths.annual_crop_evidence="artifacts/data/population_capacity/repair_round_41/crop_risk_scenarios/crop_system_scenarios.parquet"'
uv run python research/population_capacity/run_equilibrium_recovery.py --recipe research/population_capacity/round_42_candidate.json --output artifacts/data/population_simulation/repair_round_42/equilibrium_recovery
uv run python research/population_capacity/attach_recovery_evidence.py --output artifacts/data/population_simulation/repair_round_42/acceptance_stable --recovery artifacts/data/population_simulation/repair_round_42/equilibrium_recovery
uv run ppc test tests/test_simulation_fingerprints.py tests/test_population_simulation_profile.py tests/test_model_acceptance.py -q
uv run ppc test -q
```

The geography failures, historical ranges/holdouts, full physical water/maxima constraints, active-effect coverage, economic scenarios and sensitivity remain explicit work. No accepted-model manifest, game export or live deployment is claimed.
