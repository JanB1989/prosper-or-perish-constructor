# Regional assessment results: rounds 31–34

**Model not accepted.** These isolated comparisons test historical assignments at unchanged neighbouring assignments. They do not replace a joint candidate run, dated numerical benchmarks, holdouts or the complete acceptance suite.

All comparisons retain slave and higher-pop consumption, existing food-building supply, and population composition. Cookeries and victuals markets are the intended urban food supply; no urban food deficit is converted into extra land capacity.

## Timbuktu: water-dependent existing fields

| Assignment | Minimum local population, year 100 | Year 200 | Unmet location-months through year 200 | Both survival screens |
|---|---:|---:|---:|---|
| unchanged | 74.92% | 75.75% | 230 | failed |
| low | 109.53% | 109.90% | 0 | passed |
| central | 112.16% | 112.50% | 0 | passed |
| high | 113.76% | 114.13% | 0 | passed |

| Assignment | Peasant subsistence surplus | Other net supply after other-pop consumption | Total monthly balance |
|---|---:|---:|---:|
| unchanged | -107.232 | 57.687 | -49.545 |
| low | 1.556 | 57.687 | 59.243 |
| central | 6.377 | 57.687 | 64.064 |
| high | 8.550 | 57.687 | 66.237 |

Evidence: [niger criteria](../../artifacts/data/population_simulation/repair_round_31/niger/viability_criteria.csv). Recorded candidate/source/simulator identity: `66fbe8977cfe8ab190bddb376f84d901dcbfb5459b461299315e5bea3fcbb547`.

## Shuntian: management alone

| Assignment | Minimum local population, year 100 | Year 200 | Unmet location-months through year 200 | Both survival screens |
|---|---:|---:|---:|---|
| unchanged | 74.66% | 75.56% | 312 | failed |
| low | 86.86% | 87.00% | 16 | failed |
| central | 93.49% | 93.42% | 0 | passed |
| high | 99.18% | 99.04% | 0 | passed |

| Assignment | Peasant subsistence surplus | Other net supply after other-pop consumption | Total monthly balance |
|---|---:|---:|---:|
| unchanged | -311.630 | 211.670 | -99.959 |
| low | -184.666 | 211.670 | 27.004 |
| central | -136.228 | 211.670 | 75.442 |
| high | -102.617 | 211.670 | 109.053 |

Evidence: [shuntian criteria](../../artifacts/data/population_simulation/repair_round_32/shuntian/viability_criteria.csv). Recorded candidate/source/simulator identity: `1ef9f74d64892dc674bce00270cb3721793faabc1b744c21f6c363aeac4617ac`.

## Shuntian: management and restored current fields

| Assignment | Minimum local population, year 100 | Year 200 | Unmet location-months through year 200 | Both survival screens |
|---|---:|---:|---:|---|
| unchanged | 74.66% | 75.56% | 312 | failed |
| low | 145.54% | 149.77% | 0 | passed |
| central | 146.71% | 151.16% | 0 | passed |
| high | 147.55% | 152.18% | 0 | passed |

| Assignment | Peasant subsistence surplus | Other net supply after other-pop consumption | Total monthly balance |
|---|---:|---:|---:|
| unchanged | -311.630 | 211.670 | -99.959 |
| low | 48.502 | 211.670 | 260.173 |
| central | 50.556 | 211.670 | 262.226 |
| high | 51.987 | 211.670 | 263.657 |

Evidence: [shuntian_fields criteria](../../artifacts/data/population_simulation/repair_round_33/shuntian_fields/viability_criteria.csv). Recorded candidate/source/simulator identity: `036588249655a04b6ed11076fb7ba9dffef9b4e08a60d3910d5eeeb0c181b7b5`.

## Cusco: management and restored current fields

| Assignment | Minimum local population, year 100 | Year 200 | Unmet location-months through year 200 | Both survival screens |
|---|---:|---:|---:|---|
| unchanged | 45.37% | 43.19% | 2448 | failed |
| low | 48.56% | 46.15% | 2178 | failed |
| central | 60.08% | 58.54% | 1494 | failed |
| high | 66.67% | 66.72% | 1242 | failed |

| Assignment | Peasant subsistence surplus | Other net supply after other-pop consumption | Total monthly balance |
|---|---:|---:|---:|
| unchanged | -580.610 | 139.170 | -441.440 |
| low | -540.776 | 139.170 | -401.606 |
| central | -436.839 | 139.170 | -297.669 |
| high | -364.734 | 139.170 | -225.564 |

Evidence: [cusco_fields criteria](../../artifacts/data/population_simulation/repair_round_34/cusco_fields/viability_criteria.csv). Recorded candidate/source/simulator identity: `f11da1851c1119e0c33fb8c5d33a5758eabc30e53f63018f4e1d15b6a9d65d02`.

## Interpretation and remaining work

- Niger: the new assignment changes the treatment of existing fields, not their hectares. Its water-served fraction is an explicitly inferred northern-delta analogue. Flood-recession farming is not proof of modern controlled-irrigation reliability; this source interpretation still needs a physical yield/water check.
- Shuntian: management alone fails at the low estimate. Restoring the dated current dry-field footprint resolves that comparison. This recovery consumes known land and displaces livelihoods; it grants no irrigation. The crop-mixture mask is not a historical measurement of abandoned farmland. Yield transfer to restored hectares remains uncertain.
- Cusco: management and restoration of dated fields do not resolve the failure, even at the high estimate. Pisaq still has zero crop-density support. This is a missing crop-system input, not evidence of zero Andean agricultural potential. Later imperial terraces and yields remain excluded from the starting assignment.
- Shared scale 3, area exponent 0.75, development coefficient 0.05, subsistence output 1.25, urban allowance 3 per observed worker and removal of the extra urban rank penalty are experimental joint settings. Their geographical and global growth consequences still need joint verification.
- The previous 25% land-pressure offset helped Bali but is absent from these isolated runs. No combined pass total is inferred by stitching these separate comparisons together.
- World starting capacity exceeds 1.85 billion under these experimental parameters. This is a diagnostic total, not a ceiling or an accepted result. High-density and low-fill outliers require physical and 100/200-year plausibility checks.

Reproduce each row with the same canonical runner, for example:

```sh
uv run python research/population_capacity/run_management_assessment.py --assignments research/population_capacity/historical_assignments_round_33.json --system shuntian_maintained_dryland_cultivation --output artifacts/data/population_simulation/repair_round_33/shuntian_fields
uv run python research/population_capacity/run_management_assessment.py --assignments research/population_capacity/historical_assignments_round_34.json --system cusco_preimperial_maintained_fields --output artifacts/data/population_simulation/repair_round_34/cusco_fields
uv run python research/population_capacity/summarize_regional_assessments.py
```

Each directory retains all four resolved assignments, complete-world starting ledgers, monthly complete-province histories, budgets and original fingerprints. These are reproducible experiments; none is an accepted parameter manifest or game export.
