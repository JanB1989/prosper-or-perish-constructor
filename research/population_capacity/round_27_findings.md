# Round 27: urban food and accommodation

**Model remains unaccepted.** This round separates urban food buildings from accommodation. Current victuals-market output is retained in every comparison. No food consumption coefficient, imports, building count or cultivated area is changed.

The aligned snapshot contains 2,345 cookery records, 335 without recorded employment. The baseline gives those records no staffed output. The staffing scenario fills existing vacancies only from available labourers after reserving their existing employment. Across the world it hires 6,601 additional people in six locations and adds 132.0244 monthly food units. Recipe inputs and wages are assumed supplied; autonomous promotion, hiring and market supply are not simulated.

Accommodation is tested separately at zero, one and three flat game population units per observed non-agricultural worker unit, before native relative capacity modifiers. These are shared experimental coefficients, not historical household-size estimates or accepted building bonuses. Agricultural opportunity and agricultural job reservations remain unchanged.

Every location is simulated through 200 years. Monthly histories for 22 complete provinces reproduce the world checkpoints within numerical tolerance. The companion accounting artifact checks that accommodation creates no crop support or agricultural jobs.

| Candidate | Year | World population difference | Locations with more unmet food |
|---|---:|---:|---:|
| unchanged | 100 | 0 | 0 |
| unchanged | 200 | 0 | 0 |
| cookery_staffing | 100 | 45,425 | 0 |
| cookery_staffing | 200 | 48,056 | 0 |
| accommodation | 100 | 11,524,185 | 0 |
| accommodation | 200 | 11,767,597 | 0 |
| both | 100 | 11,572,940 | 0 |
| both | 200 | 11,819,603 | 0 |
| accommodation_three | 100 | 21,017,396 | 0 |
| accommodation_three | 200 | 21,778,603 | 0 |

| Candidate | Province | Year | Population retention | Post-startup unmet location-months | Viability |
|---|---|---:|---:|---:|---|
| accommodation | bali_province | 100 | 54.0% | 685 | failed |
| accommodation | bali_province | 200 | 54.6% | 685 | failed |
| accommodation_three | bali_province | 100 | 54.0% | 685 | failed |
| accommodation_three | bali_province | 200 | 54.6% | 685 | failed |
| both | bali_province | 100 | 54.0% | 685 | failed |
| both | bali_province | 200 | 54.6% | 685 | failed |
| cookery_staffing | bali_province | 100 | 54.0% | 685 | failed |
| cookery_staffing | bali_province | 200 | 54.6% | 685 | failed |
| unchanged | bali_province | 100 | 54.0% | 685 | failed |
| unchanged | bali_province | 200 | 54.6% | 685 | failed |
| accommodation | jiaxing_province | 100 | 86.0% | 6 | failed |
| accommodation | jiaxing_province | 200 | 87.1% | 6 | failed |
| accommodation_three | jiaxing_province | 100 | 91.3% | 0 | failed |
| accommodation_three | jiaxing_province | 200 | 92.1% | 0 | failed |
| both | jiaxing_province | 100 | 86.0% | 6 | failed |
| both | jiaxing_province | 200 | 87.1% | 6 | failed |
| cookery_staffing | jiaxing_province | 100 | 83.1% | 12 | failed |
| cookery_staffing | jiaxing_province | 200 | 84.2% | 12 | failed |
| unchanged | jiaxing_province | 100 | 83.1% | 12 | failed |
| unchanged | jiaxing_province | 200 | 84.2% | 12 | failed |
| accommodation | pays_france_province | 100 | 56.8% | 600 | failed |
| accommodation | pays_france_province | 200 | 59.7% | 600 | failed |
| accommodation_three | pays_france_province | 100 | 72.0% | 235 | failed |
| accommodation_three | pays_france_province | 200 | 75.3% | 235 | failed |
| both | pays_france_province | 100 | 56.8% | 600 | failed |
| both | pays_france_province | 200 | 59.7% | 600 | failed |
| cookery_staffing | pays_france_province | 100 | 46.7% | 885 | failed |
| cookery_staffing | pays_france_province | 200 | 49.2% | 885 | failed |
| unchanged | pays_france_province | 100 | 46.7% | 885 | failed |
| unchanged | pays_france_province | 200 | 49.2% | 885 | failed |
| accommodation | timbuktu_province | 100 | 56.9% | 770 | failed |
| accommodation | timbuktu_province | 200 | 56.3% | 770 | failed |
| accommodation_three | timbuktu_province | 100 | 57.8% | 740 | failed |
| accommodation_three | timbuktu_province | 200 | 57.0% | 740 | failed |
| both | timbuktu_province | 100 | 56.9% | 770 | failed |
| both | timbuktu_province | 200 | 56.3% | 770 | failed |
| cookery_staffing | timbuktu_province | 100 | 4.3% | 5940 | failed |
| cookery_staffing | timbuktu_province | 200 | 2.0% | 7825 | failed |
| unchanged | timbuktu_province | 100 | 4.3% | 5940 | failed |
| unchanged | timbuktu_province | 200 | 2.0% | 7825 | failed |
| accommodation | trowulan_province | 100 | 25.2% | 2289 | failed |
| accommodation | trowulan_province | 200 | 25.5% | 2289 | failed |
| accommodation_three | trowulan_province | 100 | 27.2% | 2142 | failed |
| accommodation_three | trowulan_province | 200 | 27.6% | 2142 | failed |
| both | trowulan_province | 100 | 25.2% | 2289 | failed |
| both | trowulan_province | 200 | 25.5% | 2289 | failed |
| cookery_staffing | trowulan_province | 100 | 22.5% | 2527 | failed |
| cookery_staffing | trowulan_province | 200 | 23.2% | 2527 | failed |
| unchanged | trowulan_province | 100 | 22.5% | 2527 | failed |
| unchanged | trowulan_province | 200 | 23.2% | 2527 | failed |

Viability uses per-location population and development checks, not the province total printed above. Neither a larger world total nor an urban accommodation improvement certifies unresolved geographical, water, holdout or demographic gates.

Food-budget diagnosis: the major Bali/Java deficits remain pressure-recoverable peasant consumption. Additional urban cookery staffing cannot repair those land-support assignments. Urban food shortages are downstream requirements for cookeries and victuals markets; they must not be converted into agricultural capacity boosts.

Reproduce:

```sh
uv run python research/population_capacity/run_urban_food_comparison.py
uv run python research/population_capacity/summarize_urban_food_comparison.py
uv run ppc test
```

All source/preparation parameters, monthly histories, annual world aggregates, reconciled provincial budgets, per-location global effects and horizon-specific viability checks are in `artifacts/data/population_simulation/repair_round_27/urban_food/`. Both new profile options remain disabled by default. No game export or live deployment occurred.
