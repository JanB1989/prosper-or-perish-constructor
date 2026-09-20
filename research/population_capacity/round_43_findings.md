# Round 43: Mesoamerican crop presence and southern lake management

**Not accepted.** The source-only run passes 38 of 44 provincial survival checks at years 100 and 200. Anahuac now passes; Bali/Lombok, Trowulan and Cusco/Acamama still fail. This is one coupled scenario with 12 months of starting stocks, not the complete acceptance programme.

## Source correction before management

The pinned FAO crop-history source excludes pre-contact wheat, barley, rye and rice in Mexico and Central America. A separate named-system record establishes maize presence in the five Anahuac locations. It does not grant northern Mexican hunter-gatherer landscapes blanket maize cultivation. See `mesoamerican_crop_presence_evidence.json` for dates, source hash, geographic scope and exclusions.

The annual rebuild changes 22,321 of 2,113,829 rows in 221 locations, with zero changed rows outside the corrected crop scope. Canonical preparation changes capacity in 181 locations. Development, starting population and building food remain fixed. Five cultivated-area assignments decrease by a combined 0.1014 km² through the crop-mixture feasibility screen; water-managed hectares do not change. Thus unchanged physical source labels do **not** imply invariant final cultivated hectares. The builder's reporting contract now makes this distinction explicit.

`source_audit/changed_starting_locations.csv` and `changed_province_totals.csv` cover all affected starting locations, not only Anahuac. These are attribution checks, not global behavioural acceptance.

## Southern lake-field comparison

The INAH regional synthesis describes early Postclassic lake-margin drainage and cultivation in Chalco–Xochimilco before later Mexica expansion. Only those two location assignments change. The D37.5–62.5 and water-service 0–50% ranges are explicitly inferred management uncertainty, frozen before the experiment; they are not measured medieval hectares or fitted population targets. Modern archaeological-site areas, Xaltocan hectares and later imperial expansion are excluded. Current cultivated hectares remain unchanged in this comparison.

| Assignment | Population retained, year 100 | Year 200 | Unmet location-months after startup | Both horizons |
|---|---:|---:|---:|---|
| Corrected source, previous management | 95.78% | 96.20% | 0 | passed |
| Low management | 99.06% | 99.31% | 0 | passed |
| Central management | 100.83% | 101.04% | 0 | passed |
| High management | 102.08% | 102.28% | 0 | passed |

All cases also pass the per-location development and early-drawdown checks. Neighbouring assignments are exactly invariant across the four management cases. The central audit independently reproduces the saved starting ledger and provincial food budget.

Starting monthly food production remains 518.785 throughout: 86.873 peasant subsistence and 431.913 existing building food. Other-pop consumption remains 288.370. Management changes pressure-sensitive peasant consumption from 181.371 to 121.127 in the central case; total balance increases from +49.044 to +109.288. This is an improvement in peasant land pressure, with existing urban food supply explicitly retained. No extra cookery output, food imports or consumption reductions are invented.

## Evidence and reproduction

Artifacts are under `artifacts/data/population_capacity/repair_round_43` and `artifacts/data/population_simulation/repair_round_43`. `round_summary.json`, both run manifests and the source/food audits bind their results to inputs. The old crop-label manifest preserves the builder version that created it; the new canonical audit supersedes its overly broad unchanged-hectares wording.

```sh
uv run ppc population-capacity build-risk-scenarios --config population_capacity.round43.local.toml
uv run python research/population_capacity/compare_crop_history_scenarios.py --before artifacts/data/population_capacity/repair_round_41/crop_risk_scenarios/crop_system_scenarios.parquet --after artifacts/data/population_capacity/repair_round_43/crop_risk_scenarios/crop_system_scenarios.parquet --output artifacts/data/population_capacity/repair_round_43 --name mesoamerican_crop_presence
uv run python research/population_capacity/run_candidate_world_comparison.py --assignments research/population_capacity/historical_assignments_round_40.json --output artifacts/data/population_simulation/repair_round_43/source_only --regional-only --scenario-file research/population_capacity/round_37_source_replay_scenario.json --override mechanics.subsistence_output=1.3 --override 'paths.annual_crop_evidence="artifacts/data/population_capacity/repair_round_43/crop_risk_scenarios/crop_system_scenarios.parquet"'
uv run python research/population_capacity/run_management_assessment.py --assignments research/population_capacity/historical_assignments_round_43.json --system southern_mexico_lakes_managed_fields --output artifacts/data/population_simulation/repair_round_43/southern_lakes_management --scenario-file research/population_capacity/round_37_source_replay_scenario.json --scenario common_slower_quarter --override mechanics.subsistence_output=1.3 --override 'paths.annual_crop_evidence="artifacts/data/population_capacity/repair_round_43/crop_risk_scenarios/crop_system_scenarios.parquet"'
uv run python research/population_capacity/audit_management_food_accounts.py --experiment artifacts/data/population_simulation/repair_round_43/southern_lakes_management --candidate central
```

The broader stock/development, geographical/source holdout, demographic, progression, resource-maxima, sensitivity and global-beneficiary gates remain unresolved. No accepted manifest or game export is produced. Building balance and live deployment remain deferred.

Relevant annual-crop, crop-history and fallback regressions pass: **21 passed** using the ppc test wrapper. The last full suite remains round 42: 854 passed, one documented environment-dependent skip.

The next Cusco investigation has a pinned primary source in marcacocha_crop_history_evidence.json: the AD1100–1400 core interpretation supports pre-imperial agricultural activity, but does not supply province-wide hectares or a 1337 yield. No assignment has yet been changed from this source.
