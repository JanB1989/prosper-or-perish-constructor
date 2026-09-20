# Round 37: crop availability and annual-source replay

The isolated candidate excludes wheat, barley, rye and Oryza rice in South America before 1492, using the pinned FAO 1994 interpretation. Original domains and point evidence remain intact. Greenland and North America are outside this staged correction. The builder validates the source and boundary hashes and loads the result through the existing registry validator.

Rebuilding the original crop-history registry reproduces every cached location/crop availability value. The corrected registry changes 6,675 crop/location pairs across 1,335 locations, all from availability 0.5 to 0. Physical crop yields are retained, with availability applied separately. The corrected labels are isolated in `artifacts/data/population_capacity/repair_round_37/crop_history`; the working simulation candidate has not been changed.

The annual crop builder completed 2,113,829 rows covering 20,929 locations and 101 shared climate years. Comparison against the old annual cache found large changes outside South America, including exact halving of rainfed energy. This rejects the old cache as a clean unchanged control. A paired annual rebuild with the original labels is required to distinguish stale-cache effects from the historical exclusion. No capacity or acceptance result may be inferred before this comparison.

The annual builder's method/run input hash currently omits the crop-availability label hash. This is a concrete provenance defect to fix before using rebuilt evidence for acceptance, even though the output artifact itself has a content checksum. The existing annual cache and current crop labels cannot be presumed aligned.

```sh
uv run python research/population_capacity/build_crop_history_repair.py --output artifacts/data/population_capacity/repair_round_37/crop_history
uv run ppc population-capacity build-risk-scenarios --config population_capacity.round37.local.toml
uv run ppc population-capacity build-risk-scenarios --config population_capacity.round37.baseline.local.toml
uv run python research/population_capacity/compare_crop_history_scenarios.py
```

The two local configurations preserve the original settings, redirect scenario output to round 37, and point the corrected run at the isolated labels. The corrected label directory links to the unchanged physical crop sample directory. Remaining work: paired replay, availability-bound input identity, canonical current/opportunity recalculation, North American scope, indigenous crop gaps, then affected geography and acceptance reruns. No game export or live deployment.

Paired rebuild completed: replaying the unchanged labels differs from the old cache in 19,460 locations. Comparing the historical exclusion against that fresh baseline changes 557 locations (56,257 annual rows), with **zero changes outside the exclusion domain**. This separates the localized historical correction from the much broader stale annual-source defect. Both comparisons retain the complete 2,113,829-row universe. Results and fingerprints are in `cached_annual_replay.json` and `paired_historical_exclusion.json`.

## Propagation fixes and first food rerun

The sibling population-capacity pipeline now includes the availability-label SHA-256 in annual method identity and fails when labels are missing. The quantile replacement function also replaces rainfed and irrigation component quantiles and allocation fields instead of retaining stale values and appending `_right` columns. The constructor's canonical joint land-evidence verification rejects such stale candidates; both new candidate datasets now pass it.

An initial rebuild falsely reported zero crop changes because of that duplicate-column defect. Its fresh-baseline artifact has been replaced with the corrected rebuild; do not use the initial console result as evidence. After the fix, the largest per-location median rainfed-component change is approximately 8.29 million physical-support people, before the direct model's accessible-land, area, management and scaling interpretation.

Both the freshly aligned original labels and the South American exclusion candidate pass 36/44 provincial survival checks under unchanged round-36 coefficients. Bali and Trowulan retain roughly 65–69% of their lowest-retention locations at years 100/200, Cusco roughly 89%, and Anahuac exceeds 90% retention but has unmet-food episodes after startup. The South American exclusion slightly worsens Cusco; other listed cases have identical outcomes in the pair. `paired_province_horizons.csv` preserves both complete comparisons.

All four starting provincial budgets have positive non-subsistence food after non-peasant demand and negative peasant subsistence surplus. The hypothetical negligible-pressure probe removes their aggregate deficits, but is not a capacity assignment. These results identify pressure-driven peasant consumption as a key mechanism; they do not justify reducing urban demand or inventing cookery supply. Full budgets remain in each run; `failed_province_budget_diagnosis.csv` collects the decomposition.

The pipeline test file exposed six old CSV-render compatibility failures. Minimal capacity CSVs can now be rendered without an optional density column; existing density diagnostics still require explicit density evidence and cannot silently remain stale. This preserves the accepted capacity interface without inventing density. No game files were rendered. Pipeline focused regressions: 42 passed, including stale quantile replacement, missing availability and stale-density refusal. The constructor full suite passed: 848 tests, one existing environment-dependent skip in 605.36 seconds. The recorded fingerprint includes the changed sibling pipeline source and test files.

Rebuild commands after annual runs:

```sh
uv run python research/population_capacity/rebuild_crop_capacity.py --case fresh_baseline
uv run python research/population_capacity/rebuild_crop_capacity.py --case historical_exclusion
uv run ppc test ../ProsperOrPerishPopulationCapacityPipeline/tests/test_carrying_capacity.py ../ProsperOrPerishPopulationCapacityPipeline/tests/test_pyaez_trace_fallback.py -q
uv run ppc test -q
```

The regional runner uses `round_37_source_replay_scenario.json`, the round-35 assignments, subsistence output 1.3, and `paths.location_candidates` / `paths.capacity_scenarios` redirected to the corresponding round-37 rebuilt source folder. Shared scale, development, employment, consumption and starting stocks remain fixed.

Starting-world accounting with identical population (394.497m): cached round-36 capacity 1,854.289m; freshly aligned annual baseline 1,109.203m; South American exclusion 1,109.017m. These are current game capacity totals, not historical population targets or full-improvement maxima. The large shift comes from annual-source alignment; the targeted crop exclusion contributes a much smaller additional change.

The next geographical diagnosis must distinguish known availability from missing crop evidence: rice is already known available in Julah and Samprangan, while Melara, Trowulan and Malang still carry the 0.5 fallback. It would be incorrect to explain all of Bali's loss as missing rice availability. The cached Christie chapter documents historical rice cultivation but supplies no new hectare measurement; it can support crop-presence review, not a fitted area increase.

## Additional replay limitation

After fixing replacement, the full-world cached-source replay does **not** reproduce every old candidate crop quantile (p10 maximum discrepancy 226,932.766 physical-support people). The earlier four-location smoke test was insufficient, and the earlier full zero-residual report used the stale-column path. The fresh/exclusion pair uses identical inputs and passes internal joint accounting, but it must not certify faithful reconstruction of the original optimizer inputs. In particular, exported optimized crop/fallow allocations are reused as technology caps in the legacy builder; these are not guaranteed to be the original pre-optimization caps. This dependency must be resolved before acceptance. Prefer a documented direct annual crop-density contract independent of optimized allocations, consistent with the plan's shared-parameter physical model, rather than compensating with food coefficients.
