# Round 29: regional management and shared scaling

**Model not accepted.** The strongest tested combination passes 35 of 44 province/horizon peaceful-viability screens, compared with 22 for the baseline. These screens are not substitutes for historical, demographic, holdout, sensitivity or full-scenario acceptance.

Eastern Java now has a shared maintained-rice-system assessment on its existing fields. Direct evidence is strongest for Malang and the Brantas basin; other eastern locations are explicit regional analogues. The assignment range is development 45–70 with 25–75% water service, below the core Trowulan/Bali range. No extra cultivated hectares or second rice harvest are assumed. See [the frozen evidence interpretation](eastern_java_rice_management_evidence.json).

The comparisons then vary the shared physical/game scale from 1.5 to 3 and the area exponent from 0.5 to 0.75. These modify game capacity, not physical hectares. The subdivision bias for two equal locations falls from 41.42% at exponent 0.5 to 18.92% at 0.75. It is still present and explicit.

Joint comparisons add the previously tested urban accommodation coefficient of 3, then remove the extra urban rank growth penalty while preserving tribal cancellation. Subsistence production, population-type consumption and existing food-building output are unchanged. Neither joint change is accepted or exported.

| Candidate | Passed horizon screens | Failed horizon screens |
|---|---:|---:|
| baseline | 22 | 22 |
| regional_management | 22 | 22 |
| area_exponent | 24 | 20 |
| shared_scale | 33 | 11 |
| joint_urban | 33 | 11 |
| joint_rank | 35 | 9 |

| Province | Year | Minimum location population retention | Post-startup unmet location-months | Viability |
|---|---:|---:|---:|---|
| acamama_province | 100 | 45.367% | 2448 | failed |
| acamama_province | 200 | 43.188% | 2448 | failed |
| alexandria_province | 100 | 120.723% | 0 | passed |
| alexandria_province | 200 | 122.207% | 0 | passed |
| anahuac_province | 100 | 101.052% | 0 | passed |
| anahuac_province | 200 | 101.341% | 0 | passed |
| angkor_province | 100 | 112.590% | 0 | passed |
| angkor_province | 200 | 113.398% | 0 | passed |
| bali_province | 100 | 89.903% | 0 | failed |
| bali_province | 200 | 90.915% | 0 | passed |
| cairo_province | 100 | 153.400% | 0 | passed |
| cairo_province | 200 | 156.202% | 0 | passed |
| central_doab_province | 100 | 205.357% | 0 | passed |
| central_doab_province | 200 | 224.388% | 0 | passed |
| delhi_province | 100 | 186.312% | 0 | passed |
| delhi_province | 200 | 194.967% | 0 | passed |
| jiaxing_province | 100 | 136.170% | 0 | passed |
| jiaxing_province | 200 | 141.777% | 0 | passed |
| kano_province | 100 | 137.090% | 0 | passed |
| kano_province | 200 | 140.528% | 0 | passed |
| la_plata_province | 100 | 100.000% | 0 | passed |
| la_plata_province | 200 | 100.000% | 0 | passed |
| liaoyang_province | 100 | 106.934% | 0 | passed |
| liaoyang_province | 200 | 107.237% | 0 | passed |
| obdorsk_province | 100 | 100.000% | 0 | passed |
| obdorsk_province | 200 | 100.000% | 0 | passed |
| ogan_province | 100 | 109.520% | 0 | passed |
| ogan_province | 200 | 109.997% | 0 | passed |
| patna_province | 100 | 156.412% | 0 | passed |
| patna_province | 200 | 156.409% | 0 | passed |
| pays_france_province | 100 | 80.356% | 65 | failed |
| pays_france_province | 200 | 81.240% | 65 | failed |
| qikiqtaaluk_province | 100 | 299.454% | 0 | passed |
| qikiqtaaluk_province | 200 | 899.157% | 0 | passed |
| shuntian_province | 100 | 74.663% | 312 | failed |
| shuntian_province | 200 | 75.563% | 312 | failed |
| songjiang_province | 100 | 164.420% | 0 | passed |
| songjiang_province | 200 | 185.897% | 0 | passed |
| suzhou_province | 100 | 138.765% | 0 | passed |
| suzhou_province | 200 | 152.662% | 0 | passed |
| timbuktu_province | 100 | 74.915% | 230 | failed |
| timbuktu_province | 200 | 75.746% | 230 | failed |
| trowulan_province | 100 | 97.495% | 0 | passed |
| trowulan_province | 200 | 97.566% | 0 | passed |

Bali remains failed at year 100: 89.903% retention is below 90%, despite passing year 200. It is not rounded into a pass. The other remaining failures are Acamama, Pays de France, Shuntian and Timbuktu at both horizons. Trowulan passes both horizons only in the joint rank comparison.

The Arctic snapshot includes only six people in the Qikiqtaaluk case; its roughly ninefold growth is about 54 people at year 200. A viability pass is not independent validation of either Arctic carrying capacity or demographic rates.

Land accounting passes for all candidates and cultivated hectares remain identical. Starting cropland comes from the LUH2-derived land-cover fractions; the separately sampled HYDE series supplies related comparison/progression evidence. They are related evidence, not independent validation, and their local area estimates differ. No source series was swapped simply because it increased support.

Next diagnoses: maintained agriculture around Paris, water/crop assignments in Shuntian, Andean managed fields and Niger floodplain support. Regional uncertainty, demographic plausibility, full physical opportunities and all nine acceptance groups still need evaluation for the eventual candidate. World starting food budgets are saved, but world trajectories for these changed parameters are deferred until the focused failures are repaired.

Reproduce:

```sh
uv run python research/population_capacity/run_geographical_candidates.py
uv run python research/population_capacity/summarize_geographical_candidates.py
```

Evidence fingerprint: `407a60053c51a327ce84bf5dc7ead2985efab8279be61e255ef2c640bcc55151`.

Artifacts: `artifacts/data/population_simulation/repair_round_29/geography/` contains full starting ledgers and world food budgets, monthly histories for 22 complete provinces, the horizon-specific criteria register, and physical-accounting checks. The previous full project suite remains 842 passed with one existing environment-dependent skip; this round changes research assignments and comparison runners, not game output.
