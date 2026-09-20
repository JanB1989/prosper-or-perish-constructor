# Round 40: bounded Lombok management comparison

Status: **not accepted**. The candidate changes only Lombok and Sasak management, retaining the full five-location Bali province and all existing food-building supply. No cultivated hectares, irrigation, crop yields, consumption rates or native equations change.

## Frozen interpretation and result

The [source record](lombok_samalas_recovery_evidence.json) distinguishes observed agricultural rebuilding after Samalas from inferred game management. The trial scores maintained fields and cultivation/coordination at two each, with no water-management score: nominal development 37.5, uncertainty 25–50 on the existing shared scale. This is a comparable-system inference, not a measured medieval development value. The ANU abstract is available; ANU and HAL records did not expose a downloadable full manuscript. No later Lombok royal irrigation system is transferred to 1337.

| Case | Year 100 population retention | Year 200 | Starting food balance | Unmet location-months after startup |
|---|---:|---:|---:|---:|
| Previous generic management | 64.58% | 65.89% | −182.470 | 365 |
| Low, D25 | 68.82% | 69.82% | −129.238 | 270 |
| Central, D37.5 | 76.23% | 76.76% | −57.490 | 125 |
| High, D50 | 82.26% | 82.52% | −11.367 | 20 |

All eight mandatory horizon checks fail. Development retention stays above 99% in these comparisons, so management decay is not the main failure. Management correction improves the food account but does not resolve the shortage within the frozen range. Do not extrapolate a higher development value to meet the population target.

The central case retains 20.936 km² of fields in Lombok and 38.187 km² in Sasak, with no water-managed area. Their capacities are 7.170k and 12.755k respectively. Every neighbouring starting assignment is exactly unchanged. The reusable food audit reproduces the complete saved world state and provincial starting budget; the saved monthly histories provide both acceptance horizons. No world comparison is warranted yet because the focused candidate fails.

## Next specific checks

Complete the crop-availability review before changing global scale or demand. The cached Christie chapter explicitly documents Malang rice cultivation and early Brantas irrigation (PDF pages 249–258, printed pages 240–249), while annual crop labels still assign uncertain rice availability to Malang. PDF page 252 explicitly rules out assuming documented double rice cropping before the fifteenth century. Correcting a crop-presence label must rebuild the annual source and its fingerprint; it cannot be implemented as an extra harvest, arbitrary yield bonus or additional hectares. Lombok's recovery abstract by itself does not establish rice adoption or irrigated extent.

The source evidence and old uncertainty range remain visible. The unresolved geography, full nine-group acceptance programme, holdouts, maxima, sensitivity and final evidence package remain mandatory. The latest full core test result remains 852 passed and one existing skip from round 38; this round changed candidate data and exercised the existing simulation and audit runners. No game export or deployment.

## Reproduction

```sh
uv run python research/population_capacity/run_management_assessment.py --assignments research/population_capacity/historical_assignments_round_40.json --system lombok_recovering_maintained_fields --output artifacts/data/population_simulation/repair_round_40/lombok --scenario-file research/population_capacity/round_37_source_replay_scenario.json --scenario common_slower_quarter --override mechanics.subsistence_output=1.3 --override 'paths.annual_crop_evidence="artifacts/data/population_capacity/repair_round_37/crop_risk_scenarios/crop_system_scenarios.parquet"'
uv run python research/population_capacity/audit_management_food_accounts.py --experiment artifacts/data/population_simulation/repair_round_40/lombok
```

Artifacts: `artifacts/data/population_simulation/repair_round_40/lombok/{manifest.json,viability_criteria.csv,provincial_budgets.csv}`, four monthly histories and starting ledgers, and `central_food_audit/manifest.json` with its reconciled local and provincial food accounts.
