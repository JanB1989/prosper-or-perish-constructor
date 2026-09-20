# Round 28: Trowulan's historical management assignment

**Model remains unaccepted.** The isolated correction passes its accounting checks but fails peaceful population/food viability at both required horizons.

Indonesia's [Trowulan archaeological submission](https://whc.unesco.org/en/tentativelists/5466/) documents canals, reservoirs, flood control and agricultural water management. The earlier candidate nevertheless assigned Trowulan development 18.75 through a generic farming analogue. This experiment assigns the same maintained-field assessment used for Bali: development 60–85 and managed-water service on 50–90% of existing fields, selecting the central values 72.5 and 70%. These ranges are inferred game mappings, not archaeological measurements.

The approximately 99 km² archaeological city footprint includes several land uses. It is not treated as cultivated area. Cultivated extent, crop calendar, population, food buildings and all neighbouring assignments remain unchanged. The source's seasonal drought also does not justify an automatic second harvest.

| Measure | Baseline | Dated management |
|---|---:|---:|
| Provincial starting capacity, people | 71,584 | 89,466 |
| Starting monthly food balance | −3,279.90 | −2,948.14 |
| Provincial population retention, year 100 | 22.50% | 23.87% |
| Provincial population retention, year 200 | 23.18% | 24.19% |
| Post-startup unmet location-months | 2,527 | 2,387 |

At negligible pressure the unchanged population and food composition has a positive monthly balance of 526.61. The starting deficit is therefore pressure-recoverable; reducing higher-pop consumption or inventing urban food imports is not the geographical repair needed here.

The complete province spans seven locations. The six neighbouring assignments still have development 18.75, while their currently reconstructed cultivated fractions are roughly 1–4%. The next geographical diagnosis must cover those systems and their reconstructed land use. A capital-only development correction cannot substitute for that work.

The source interpretation and extraction hash are in [the evidence ledger](trowulan_water_management_evidence.json). The direct origin fetch returned a challenge page; the separate cached search-tool extraction is identified explicitly and is not represented as original HTML bytes.

Reproduce:

```sh
uv run python research/population_capacity/run_trowulan_management_comparison.py
```

Artifacts are under `artifacts/data/population_simulation/repair_round_28/trowulan_management/`: paired starting ledgers, monthly histories, reconciled provincial budgets and a fingerprinted manifest. The runner verifies that neighbouring assignments and cultivated hectares did not change.

Validation after the urban-food/profile additions: `uv run ppc test` — **842 passed, 1 skipped**. The existing setup-building test skips because the local error log contains no setup building errors. No new gameplay parameter or historical candidate has been exported or marked accepted.
