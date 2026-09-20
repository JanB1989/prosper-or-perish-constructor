# Round 30: Paris management and conservative pressure retention

**Model not accepted.** The updated 25% pressure-offset candidate passes 38 of 44 regional horizon viability checks. Shuntian, Timbuktu and Acamama still fail at years 100 and 200. Global beneficiaries, historical plausibility and the other mandatory evidence groups remain to be verified.

The Parisis assignment uses [Higounet’s archival study](https://www.persee.fr/doc/crai_0065-0536_1956_num_100_4_10682) as evidence for maintained medieval open-field cultivation. Development 37.5–62.5 is an explicit game assessment range, not a historical measurement. No cultivated hectares, irrigation, food output or crop-calendar advantage were added. The world-start comparison verifies that neighbouring assignments, populations and building food remain unchanged.

| Paris-area candidate | Year | Minimum location population retention | Unmet location-months after startup | Viability |
|---|---:|---:|---:|---|
| unchanged | 100 | 80.356% | 65 | failed |
| unchanged | 200 | 81.240% | 65 | failed |
| low | 100 | 95.661% | 0 | passed |
| low | 200 | 95.962% | 0 | passed |
| central | 100 | 104.073% | 0 | passed |
| central | 200 | 104.297% | 0 | passed |
| high | 100 | 111.381% | 0 | passed |
| high | 200 | 111.791% | 0 | passed |

All three documented management positions pass both horizons. This addresses the previous potential-based classification of Paris as marginal dryland agriculture; it does not guarantee a reconstruction of historical war, plague, imports or investment.

The pressure experiment uses the canonical simulator, with a constant flat development addition cancelled in proportion to native free-land strength. It saturates at capacity. Fractions 0%, 25% and 50% of D50 decay correspond to 0, 0.0003125 and 0.000625 development/month. No starting capacity or food is added.

| Full-pressure compensation | Bali year 100 minimum retention | Bali year 200 minimum retention | Passed regional horizon checks |
|---|---:|---:|---:|
| pressure_offset_0 | 89.903% | 90.915% | 37/44 |
| pressure_offset_0.25 | 90.207% | 91.608% | 38/44 |
| pressure_offset_0.5 | 90.510% | 92.293% | 38/44 |

The smaller nonzero offset is sufficient for Bali in this candidate. It is not accepted yet: this regional comparison does not replace a global beneficiary check or uncertainty tests.

The new canonical budget split is:

`food balance = peasant subsistence surplus + (other net food supply − non-peasant consumption)`

Other net supply includes existing buildings, staffed agricultural jobs, RGO food, imports and production food inputs exactly once. It is not an invented cookery allowance. Cookeries/victuals markets remain the urban supply mechanism; geographical calibration must not disguise a missing supply contribution.

| Province | Peasant subsistence surplus | Other net supply after non-peasant demand | Total starting balance | Pressure-recoverable consumption |
|---|---:|---:|---:|---:|
| acamama_province | -580.610 | 139.170 | -441.440 | 594.363 |
| bali_province | -77.616 | 107.517 | 29.902 | 202.341 |
| pays_france_province | 84.709 | 83.429 | 168.139 | 94.272 |
| shuntian_province | -311.630 | 211.670 | -99.959 | 371.632 |
| timbuktu_province | -107.232 | 57.687 | -49.545 | 122.625 |

World province food accounts reconcile within 4.66e-10 food/month. Food and consumption coefficients are unchanged. The full budget is saved in `world_reconciled_food_budgets.csv`.

Validation: the recorded full-test result is stale for current code; rerun before acceptance.
Focused diagnosis, historical model, urban staffing and trajectory regressions: 21 passed. No game export or deployment.

Reproduce:

```sh
uv run python research/population_capacity/run_management_assessment.py --assignments research/population_capacity/historical_assignments_round_30.json --system parisis_maintained_open_fields --output artifacts/data/population_simulation/repair_round_30/parisis
uv run python research/population_capacity/run_acceptance_retention_comparisons.py --assignments research/population_capacity/historical_assignments_round_30.json --output artifacts/data/population_simulation/repair_round_30/pressure --no-frozen
uv run python research/population_capacity/summarize_management_acceptance.py
uv run ppc test -q
```

Next geographical work: water-dependent northern Niger fields, missing/uncertain Andean crop inputs and Shuntian land assignments. [The newly cached Cusco archaeological evidence](cusco_management_evidence.json) distinguishes early cultivation from later imperial terraces; it does not justify backdating the full later system.
