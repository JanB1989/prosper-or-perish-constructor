# Round 23: required-horizon repair

The model remains unaccepted. Building balance, candidate game export and live deployment are deferred.

Implemented: 100/200-year acceptance instead of a compulsory 500-year endpoint; per-horizon control checks; growth-cap exposure, net growth, doubling time, drawdown and unmet-food diagnostics; aligned saved advance/policy activation; country development and population-type consumption adapters; historical land-mask correction; reconciled provincial pressure budgets; input-bound evidence validation.

The irrigated suitable fraction in the upstream carrying-capacity calculation is a selected staple/legume mixture weighted by crop shares and sample weights. It is not the union of cultivable hectares. Historical requested extent now displaces known land uses beyond that fraction when necessary. It does not consume unknown land or grant future potential. All nine previous assignment conflicts disappear under this accounting; chronology, inferred historical extent and basin boundaries still require validation. Tests cover over-area requests and unknown cover.

56 canonical controls passed at 100 and 200 years. The sparse 5%-fill example spends 481 months at the generic food bonus ceiling, then slows as pressure increases. This is a mechanics result, not historical demographic acceptance.

Observed policy/advance activation supplies 10,425 relevant numeric effect rows. The currently supported country adapters apply 400 rows. Other effects are explicitly listed as unapplied; output modifiers need reconciliation with observed building/RGO output. Eligibility never activates a future advance. Missing ownership and activation remain coverage gaps.

After the area correction, world population is 360.74 million at year 100 and 375.92 million at year 200 from 394.50 million initially. East Asia remains at about 74.5% of its initial population at year 200; Southeast Asia at 63.6%. These fail to establish geographical acceptance. Alexandria retains about 66.9% at year 200. Global retention cannot excuse these cases.

All six initial heartland provinces have a nonnegative food balance in the artificial negligible-pressure diagnostic. That does not authorize increasing their capacity; it establishes that current starting deficits alone do not demonstrate a need for global higher-pop consumption reductions. Across the world, 489 provinces still have a deficit at that limit. Complete per-type budgets distinguish those cases. The provisional 90% retention screen flags 1,297 provinces at year 100 and 1,289 at year 200; this is a diagnosis queue, not a population-fitting objective or a claim that all were initially well provisioned.

## Reproduction

Run from the repository with `uv run python`:

- `research/population_capacity/export_active_modifiers.py`
- `research/population_capacity/run_required_horizons.py --output-name historical_extent_correction`
- `research/population_capacity/diagnose_required_horizons.py`
- `research/population_capacity/summarize_required_horizons.py`

Research artifacts are under `artifacts/data/population_simulation/repair_round_23/`. The pre-correction world run is retained in `world/`; corrected trajectories are in `historical_extent_correction/`. Input changes invalidate prior acceptance evidence. Reproduction with newer code has a new fingerprint even if its numerical results are unchanged.

## Work still required for acceptance

Complete historical management and infrastructure coverage beyond the initial systems, including controls with inappropriate potential-derived classifications. Audit the Upper Egyptian basin estimate against historical and game boundaries. Reconcile remaining active modifiers and observed food supply. Freeze scenario-specific demographic criteria and independent holdouts, then evaluate uncertainty, food/growth equilibria, typed investment and water-limited maxima. Resolve regional failures through those mechanisms before selecting shared coefficients or downstream demand interventions.

## Validation

`uv run ppc test -q --tb=short`: **824 passed, 1 skipped**. The skip is `tests/test_setup_building_corrections.py:221`: the local error log contains no setup-building errors. `git diff --check` passes. No live sync or candidate game export was performed.

## Slave-demand follow-up

The provincial diagnosis exposed substantial slave-only populations with zero subsistence production, especially in parts of India. The user confirmed slaves probably cannot produce subsistence and suggested testing zero consumption. The new `compare_slave_consumption.py` runner compares unchanged, half and zero slave demand globally at identical starting population, infrastructure, employment and absolute stocks. This is an explicitly authorized downstream diagnostic; no slave coefficient has been accepted or changed in game configuration.

The raw save records literal `type=slaves` for Patna/Rajgir populations and already records starvation. This is not an inferred population-type mapping. The audit is saved as `indian_population_raw_audit.json`.

At year 200, unchanged/half/zero slave demand produces world populations of 375.917 / 381.224 / 391.317 million. Zero demand therefore adds 15.400 million globally, but East Asia gains only about 33,546 people. Patna still collapses: zero slave consumption leaves a starting monthly deficit of 76.2634 food units from other types with no recorded production; provincial starvation still affects its slaves. The change cannot be accepted as a fix for missing food supply or the Asian geographical failures. No slave-demand reduction is adopted.

Historical-demography follow-up is cached with hashes in the source manifest: Owen (1987), DOI 10.1017/S0022463400001247, gives later-period natural-increase comparisons; Geloso and Kufenko (2015), DOI 10.1007/s12546-015-9153-9, tests frontier price/mortality responses. Their regional and temporal restrictions are recorded in `demographic_adjustment_benchmarks.json`. They do not establish a universal medieval growth envelope.
