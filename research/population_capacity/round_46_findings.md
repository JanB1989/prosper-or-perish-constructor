# Round 46: bounded management and shared subsistence sensitivity

**Not accepted. No new balance coefficient adopted.** This round tests the remaining geographical failures against the existing, frozen management ranges and compares shared subsistence output at fixed geography. Neither comparison resolves the failures. The central candidate remains round45 with output1.3.

## Management at corrected crop presence

Both experiments use the round45 annual crop source and unchanged neighbouring assignments. Current hectares, building food, population composition and consumption coefficients remain fixed. The `unchanged` case removes the named management system; it is not the current central candidate.

| System / assessment | Population retained, year100 | Year200 | Unmet location-months after startup |
|---|---:|---:|---:|
| Eastern Java, low |68.54%|69.19%|434|
| Eastern Java, central |77.07%|77.40%|175|
| Eastern Java, high |85.45%|85.51%|14|
| Lombok/Sasak, low |69.14%|70.15%|260|
| Lombok/Sasak, central |76.66%|77.18%|110|
| Lombok/Sasak, high |82.76%|83.01%|15|

All16 horizon checks, including the removed-system cases, fail. Eastern Java's D45–70 and water-service25–75% range leaves the central Trowulan assignment fixed. Lombok's D25–50 range grants no irrigation and leaves Bali-island assignments fixed. No range is widened or upper estimate selected merely to obtain a pass.

## Shared subsistence output

| Output | Food break-even fill | Population/stock equilibrium fill | Bali P100/P200 | Trowulan P100/P200 |
|---|---:|---:|---:|---:|
|1.3|1.1500|1.0537|76.66% /77.18%|77.07% /77.40%|
|1.4|1.2500|1.1463|80.20% /80.82%|79.90% /80.24%|
|1.5|1.3500|1.2389|83.61% /84.30%|82.82% /83.19%|

Equilibria use canonical native equations with fixed D50/prosperity and pure peasants. Equilibrium stocks remain7.92 months. Food break-even and demographic equilibrium remain separate. These are mechanism measurements, not empirical historical ranges.

Each regional output candidate passes40/44 screens and fails the same two provinces at both horizons. At1.5, Bali still has15 unmet location-months and Trowulan35. Sparse Arctic coastal growth remains near its native food-growth ceiling; output alone does not establish that the mapped capacity is historically correct.

The entire starting world is included in the collateral budget comparison:2,646 provinces receive more food under either output increase. Capacity, development, current fields, water, population composition and observed building food are exactly unchanged across all starting locations. Agricultural-job production follows the same subsistence baseline as before; slave consumption is unchanged. Full world trajectories were not run for these failing candidates. Positive starting food effects are not global acceptance.

Output1.3 remains the candidate. Higher shared output is not adopted to conceal unresolved geography. These experiments do not establish that no joint parameter set could work; they show that the tested changes alone are insufficient.

## Reproduction and evidence

Artifacts: `artifacts/data/population_simulation/repair_round_46`. Each management directory contains its resolved assignment files, monthly histories, budgets, horizon table and fingerprinted manifest. `shared_subsistence_horizon_criteria.csv` compares all22 provinces at both horizons. `shared_subsistence_all_province_starting_effects.csv` records every starting provincial effect. The comparison manifest records that no output change is recommended and no world trajectory acceptance occurred.

```sh
uv run python research/population_capacity/run_management_assessment.py --assignments research/population_capacity/historical_assignments_round_40.json --system eastern_java_established_rice_systems --output artifacts/data/population_simulation/repair_round_46/eastern_java --scenario-file research/population_capacity/round_37_source_replay_scenario.json --scenario common_slower_quarter --override mechanics.subsistence_output=1.3 --override 'paths.annual_crop_evidence="artifacts/data/population_capacity/repair_round_45/crop_risk_scenarios/crop_system_scenarios.parquet"'
# Repeat the preceding command with system lombok_recovering_maintained_fields and output .../lombok.
uv run python research/population_capacity/run_candidate_world_comparison.py --assignments research/population_capacity/historical_assignments_round_40.json --output artifacts/data/population_simulation/repair_round_46/subsistence_1_4 --regional-only --scenario-file research/population_capacity/round_37_source_replay_scenario.json --override mechanics.subsistence_output=1.4 --override 'paths.annual_crop_evidence="artifacts/data/population_capacity/repair_round_45/crop_risk_scenarios/crop_system_scenarios.parquet"'
# Repeat with output1.5 and output directory .../subsistence_1_5.
```

No simulator mechanics changed in this round. The last targeted tests remain23 passed and the last full suite remains854 passed with one documented environment-dependent skip; neither is represented as a fresh full-suite run. Building balance, game export and live deployment remain deferred. All broader acceptance requirements remain in scope.
