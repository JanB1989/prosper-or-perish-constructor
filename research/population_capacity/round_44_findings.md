# Round 44: regional rice presence without additional land

**Not accepted.** The source correction improves Trowulan but the regional result remains 38 passed and six failed horizon checks. Bali/Lombok, Trowulan and Cusco/Acamama still fail. Broader historical, holdout, economic and physical acceptance remains required.

Christie's *Water and rice in early Java and Bali*, printed pp.237–241 (PDF246–250), describes established dry and wet rice before1337, including central/eastern Java and Bali. The previous input corrected only Malang while retaining uncertain-presence discounts in neighbouring documented systems. The new source-pinned crosswalk contains 31 explicit mainland/island tags, excludes Madura/Kangean/Bawean and Lombok, and changes rice availability in 26 tags. It assigns no additional land, water, management advantage or second harvest. See `java_bali_rice_presence_evidence.json` for the frozen interpretation and source hash.

The paired annual rebuild changes exactly 2,626 rows in26 locations out of2,113,829 rows. No other location changes. Canonical preparation likewise changes capacity only in26 locations, with **zero changes in cultivated hectares, managed-water hectares, development, population composition or building food**. All affected provincial starting totals are in `source_audit/changed_province_totals.csv`.

| Province | Previous P100/P200 | Corrected P100/P200 | Previous → corrected unmet location-months |
|---|---:|---:|---:|
| Trowulan | 69.96% /70.31% | 77.07% /77.40% | 385 →175 |
| Bali, including Lombok/Sasak | 76.23% /76.76% | 76.66% /77.18% | 125 →110 |
| Cusco/Acamama | 91.91% /92.18% | unchanged | 216 →216 |

These population percentages are provincial totals. Acceptance also checks every location; Cusco includes locations below90%, so its provincial total is not a pass. All rows use12 months of starting stocks and the existing coupled native scenario. Neither endpoints nor reduced starvation duration conceal the remaining unmet-food failures.

Trowulan's initial monthly food balance improves from−319.915 to−137.199 through pressure-sensitive consumption; Bali's from−57.490 to−48.996. Building food and consumption coefficients remain unchanged. The archived `failed_province_land_diagnosis.csv` compares current fields with dated related LUH2/HYDE estimates; those estimates are not independent validation or permission to select whichever hectares produce a pass.

Six new source-attribution regressions check legitimate crop-screen changes, out-of-scope capacity changes, unrelated development/food/population changes, and population-composition changes at constant total population. The combined targeted run passes **23 tests**. The last full-suite result remains round42, not a new full-suite claim.

## Reproduction

```sh
uv run python research/population_capacity/build_named_crop_history.py --evidence research/population_capacity/java_bali_rice_presence_evidence.json --baseline-registry artifacts/data/population_capacity/repair_round_43/crop_history/crop_history_registry.toml --baseline-labels artifacts/data/population_capacity/repair_round_43/crop_history/crop_mode_labels.parquet --output artifacts/data/population_capacity/repair_round_44/crop_history --config-output population_capacity.round44.local.toml --annual-output artifacts/data/population_capacity/repair_round_44/crop_risk_scenarios
uv run ppc population-capacity build-risk-scenarios --config population_capacity.round44.local.toml
uv run python research/population_capacity/compare_crop_history_scenarios.py --before artifacts/data/population_capacity/repair_round_43/crop_risk_scenarios/crop_system_scenarios.parquet --after artifacts/data/population_capacity/repair_round_44/crop_risk_scenarios/crop_system_scenarios.parquet --output artifacts/data/population_capacity/repair_round_44 --name java_bali_rice_presence
uv run python research/population_capacity/run_candidate_world_comparison.py --assignments research/population_capacity/historical_assignments_round_40.json --output artifacts/data/population_simulation/repair_round_44/source_only --regional-only --scenario-file research/population_capacity/round_37_source_replay_scenario.json --override mechanics.subsistence_output=1.3 --override 'paths.annual_crop_evidence="artifacts/data/population_capacity/repair_round_44/crop_risk_scenarios/crop_system_scenarios.parquet"'
uv run python research/population_capacity/audit_source_starting_state.py --before artifacts/data/population_simulation/repair_round_43/source_only/starting_ledger.parquet --after artifacts/data/population_simulation/repair_round_44/source_only/starting_ledger.parquet --changes artifacts/data/population_capacity/repair_round_44/crop_history/availability_changes.csv --output artifacts/data/population_simulation/repair_round_44/source_audit
uv run ppc test tests/test_crop_source_attribution.py tests/test_annual_crop.py ../ProsperOrPerishPopulationCapacityPipeline/tests/test_crop_history.py -q
```

Building balancing, game export and live deployment remain deferred. Current geographical evidence and starting assignments must still be repaired before a full-world acceptance run can certify a candidate.
