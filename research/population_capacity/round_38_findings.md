# Round 38: allocation-independent annual crop support

**Working comparison, not accepted.** The opt-in `matched_annual_crop_v1` contract reads annual rainfed and irrigated nutrition directly. It no longer derives crop density from an optimized land allocation, a population fit or an exported allocation reused as an input cap.

## Calculation and bounds

Annual energy and protein are per hectare of the complete sampled footprint. Convert each to supported people using the existing source reference requirements (2,200 kcal/day, 50 g protein/day), take the limiting nutrient, then divide by the matching crop-mixture suitability fraction once. This gives people per square kilometre of fields. Source crop losses and fallow are already included; no inherited regional calendar multiplier is added or removed from this annual quantity. The existing source-reference development factor is removed once before applying assessed current development.

Climate rows are ordered by the mean of rainfed and irrigated support on a reference footprint. The same actual climate year supplies both modes at each selected probability rank. The reference is only an ordering statistic, never an allocation of real land. Per-location ranks are not a simultaneous world-year realization or a global confidence interval. Shared-year sensitivity still requires explicit complete-world-year scenarios.

Current cultivation continues to come from dated land use and historical assignments. Future opportunity remains separate. The maximum of the two matched crop-mixture fractions supplies the conditional physical land-access screen; it is **not a surveyed union of cultivable hectares**. This approximation, independently documented cultivated-area recovery and water-budget limits remain visible acceptance issues. Physical hectares stay additive; shared sublinear game conversion is unchanged.

## Verification

- 44 focused tests pass, covering annual nutrient/area units, matching climate years, incomplete-year rejection, zero-denominator rejection, independence from old allocations, no duplicate calendar/development effect, physical accounts and profile compatibility.
- Full-world independence probe: 20,929 locations, sixteen legacy allocation/crop-support columns zeroed, legacy scenario file deliberately absent. Current capacity, natural base, active infrastructure, development, physical component contributions and reported land opportunities are identical, with zero maximum residual. This proves removal of that legacy allocation dependency; it does not prove historical adequacy.
- First complete-province run: 36/44 survival checks pass at years 100/200. Bali, Trowulan, Cusco and Anahuac remain failed. Starting world capacity is 1,126.970m with unchanged round-36 balancing coefficients. The final-code rerun is saved under `annual_final`; its population, development and unmet-food horizon metrics reproduce the first run exactly.
- Full project tests: 852 passed, one existing environment-dependent setup-error-log skip in 600.59 seconds. The current code/configuration fingerprint is saved in `repair_round_38/full_test_result.json`. Earlier round-37 results cannot certify this changed code.

The native food equation, consumption rates, employment reservations and existing food-building supply are unchanged. Annual crop support is independent of urban allowances. No geographical dataset is accepted and no game export or live deployment occurred.

## Reproduce

Use `run_candidate_world_comparison.py` with:

```sh
uv run python research/population_capacity/run_candidate_world_comparison.py --assignments research/population_capacity/historical_assignments_round_38.json --output artifacts/data/population_simulation/repair_round_38/annual --scenario-file research/population_capacity/round_37_source_replay_scenario.json --regional-only --override mechanics.subsistence_output=1.3 --override 'paths.annual_crop_evidence="artifacts/data/population_capacity/repair_round_37/crop_risk_scenarios/crop_system_scenarios.parquet"'
uv run ppc test tests/test_annual_crop.py tests/test_historical_model.py tests/test_population_simulation_profile.py tests/test_physical_support.py -q
uv run ppc test -q
```

The full-world independence result is `artifacts/data/population_simulation/repair_round_38/allocation_independence/result.json`. Its modified candidate is diagnostic only. Continue with historical crop presence/field extent and the four failed provincial budgets, then the complete nine-group acceptance programme. Do not restore the old inflated crop source or change demand to conceal these failures.

## New dated American agricultural evidence

The [Xaltocan study](https://doi.org/10.1016/j.jaa.2009.10.005), PDF page 5, documents an integrated raised-field/canal system of at least approximately 1,000–1,500 ha and maize dates spanning AD 1200–1400. The numerical extent is a reported minimum system footprint, not a precise crop-bed area or total-location upper bound. [Source record](xaltocan_chinampa_evidence.json) pins the manuscript hash, limitations and chronology.

The game places Xaltocan in **tetzcoco_province**, not anahuac_province. The current model gives it 26.6 km² of fields, zero managed-water area and development 18.75. This identifies a missing historical system assessment but does not authorize transferring Xaltocan's hectares to the failing Anahuac province. Field-polygon overlap and crop-bed versus canal area need checking before assignment. No map values were changed from this source yet.
