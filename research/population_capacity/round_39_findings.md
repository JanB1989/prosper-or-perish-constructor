# Round 39: separate Bali management from the shared Lombok deficit

Status: **not accepted**. All eight isolated Bali-management horizon checks fail. The completed comparison changes neither food consumption nor building food; no capacity values are selected from its survival results.

## Evaluated management range

The existing source-bounded assessment varies only Julah, Samprangan and Melara: development 60–85 and water service on 50–90% of their current fields. These numerical ranges remain explicitly inferred, not measured medieval yields or hectares. Lombok and Sasak and every other neighbouring assignment stay fixed. The native candidate uses subsistence output 1.3, common rank growth −0.005 and pressure compensation of 25% of D50 decay.

| Assessment | Population retained, year 100 | Year 200 | Unmet location-months after startup |
|---|---:|---:|---:|
| Named system removed | 56.61% | 58.15% | 590 |
| Low | 63.69% | 65.00% | 400 |
| Central | 64.58% | 65.89% | 365 |
| High | 65.28% | 66.60% | 350 |

The last column is a sum of location-months, not elapsed province starvation duration. Neither increasing management within these ranges nor endpoint recovery resolves the failure.

## Reconciled starting cause

The game province includes five locations on two islands. Its label must not be mistaken for the extent of the Balinese historical system.

| Location | Population, thousands | Capacity, thousands | Starting food balance |
|---|---:|---:|---:|
| Julah | 73.590 | 59.253 | −9.449 |
| Samprangan | 75.030 | 72.055 | +164.823 |
| Melara | 47.047 | 39.759 | −9.988 |
| Lombok | 40.628 | 4.832 | −263.635 |
| Sasak | 30.049 | 8.596 | −64.222 |

Bali-island contributions sum to +145.387 food; Lombok/Sasak sum to −327.857, giving −182.470 for the unchanged complete sharing province. This is a decomposition of canonical local production and consumption, **not an isolated-island simulation or acceptance pass**. All three Bali-island locations have positive peasant subsistence surplus at the starting snapshot. Lombok/Sasak have substantial pressure-dependent peasant deficits. Existing food buildings cover aggregate non-peasant demand; automatic demand reductions or invented cookery production would conceal this geographical discrepancy.

The new reusable audit reproduces the entire saved starting ledger and provincial budget before emitting local accounts. Its fingerprint binds the saved experiment, preparation, source ledger and simulator. The final run passes both replay checks; no simulator code or balance coefficients changed.

## Land and historical follow-up

The audit compares LUH2 and HYDE at the same date, 1300, retaining the separate 1337 HYDE column. Current fields include the separately identified small baseline open-land allowance. The sources differ in spatial allocation and version; their differences are diagnostic, not permission to select whichever gives more support. LUH2's historical land inputs derive from HYDE, so these are related evidence, not independent validation ([Hurtt et al.](https://doi.org/10.5194/gmd-13-5425-2020)).

[The Lombok recovery source](lombok_samalas_recovery_evidence.json) identifies a specific historical mechanism to investigate after the 1257 eruption. Its repository abstract reports agricultural rebuilding and potentially century-long recovery. Full-text/spatial corroboration and dated field-system evidence remain needed. This does not supply quantitative hectares, development, a growth coefficient, or an exception to the mandatory peaceful-control requirements. Next geographical work targets Lombok/Sasak rather than increasing Bali management again.

## Reproduce and inspect

```sh
uv run python research/population_capacity/run_management_assessment.py --assignments research/population_capacity/historical_assignments_round_38.json --system bali_subak_managed_fields --output artifacts/data/population_simulation/repair_round_39/bali --scenario-file research/population_capacity/round_37_source_replay_scenario.json --scenario common_slower_quarter --override mechanics.subsistence_output=1.3 --override 'paths.annual_crop_evidence="artifacts/data/population_capacity/repair_round_37/crop_risk_scenarios/crop_system_scenarios.parquet"'
uv run python research/population_capacity/audit_management_food_accounts.py --experiment artifacts/data/population_simulation/repair_round_39/bali
```

Evidence is under `artifacts/data/population_simulation/repair_round_39/bali`: `viability_criteria.csv`, four monthly histories, `manifest.json`, and `central_food_audit/{local_food_accounts.csv,dated_land_comparison.csv,reconciled_provincial_budgets.csv,manifest.json}`. The full core suite remains the round-38 result (852 passed, one existing skip); this round exercised research-runner changes against the real cached candidate. All remaining geographical and nine-group acceptance gates remain open. No export or deployment.
