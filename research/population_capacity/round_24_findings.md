# Round 24: productive employment and historical management

The strongest result is an explicit staffed agricultural-employment target for slaves. Consumption is unchanged. Unemployed slaves still do not produce subsistence. The candidate adds jobs and their staffed food output; it adds neither capacity nor imports.

## Employment specification

Current agricultural capacity components, with their existing development factor, supply a shared job budget at one job per supported game-population unit. Existing employed peasants/slaves and initial subsistence peasants reserve that budget first. New jobs hire at most 75% of initially unemployed slaves and are bounded by the remainder. Food output is 1.25 per employed game-population unit per month, identical to the candidate peasant subsistence coefficient. This is a proposed conversion for building balancing, not a measured historical employment reconstruction. Fixed jobs do not grow automatically with population. Existing employment has priority when the workforce shrinks; unstaffed proposed jobs produce nothing. Food inputs, wages and construction costs remain for building balancing.

`proposed_agricultural_employment_targets.csv` records each location's jobs, land reservation and fully staffed food target. `all_province_075_comparison.csv` includes every province, including regions that were already prosperous. All files are under `artifacts/data/population_simulation/repair_round_24/`.

The 50% target was rejected for Patna's robust-control role: 24 months of initial stocks produced a brief overshoot and famine, even though its 100/200-year endpoints passed retention. The 75% target passes all four initial stocks (0, 3, 12 and 24 months): population is approximately 115% of initial at year 100 and 116% at year 200, development is retained, and no unmet food occurs after startup. Worst early population retention is 99.485%. A 12-month 50% crop-output loss starting at year 25 also avoids unmet food in these tests. This certifies the named experiment only, not every regional benchmark.

The same shared 75% rule raises South Asian population from 93.76 million initially to 101.61 million at year 100 and 104.93 million at year 200. World totals are 386.26 and 402.38 million. World retention is not the selection criterion. East/Southeast Asian geographical failures remain substantially separate from this mechanism.

## Bali historical management

[UNESCO's Bali assessment](https://whc.unesco.org/en/list/1194) supports medieval cooperative water control and maintained terraces. The round-24 candidate assigns inferred development 60–85 and water service on 50–90% of current cultivated fields in Julah, Samprangan and Melara. It does not increase cultivated hectares or reuse modern property area as medieval evidence. Lombok/Sasak are excluded from this historical assignment despite sharing the game province. Nominal comparisons hold their direct capacities unchanged; global uncertainty endpoints also vary their inferred management, as recorded in the manifest.

At the nominal assignment, the province retains 146,114 people at year 200 rather than 128,633, from 266,344 initially. Management correction alone fails the demographic case. Cultivated extent and crop-system interpretation are the next specific research targets; increasing development further to force retention is not justified.

The pure-subsistence geographic experiment is also saved. It replaces population composition and rank with rural peasants to test a mechanism. It is not a historical reconstruction, especially in tribal regions, and cannot be used as a world demographic target.

## Reproduce

Run from the repository:

- `uv run python research/population_capacity/run_agricultural_employment.py`
- `uv run python research/population_capacity/run_agricultural_employment.py --fractions 0.75 --output-name employment_075`
- `uv run python research/population_capacity/check_agricultural_employment_controls.py --fraction 0.75`
- `uv run python research/population_capacity/run_bali_management.py`
- `uv run python research/population_capacity/run_subsistence_geography.py`
- `uv run python research/population_capacity/summarize_round_24.py`

Root-level early employment artifacts in round_24 predate the conservative reservation of existing jobs and are superseded by `employment_reserved/` and `employment_075/`.

## Validation and limits

`uv run ppc test -q --tb=short`: 826 passed, 1 skipped. The existing skip concerns a local error log with no setup-building errors. Focused final employment, food-scenario and tick regressions: 53 passed. Employment tests verify worker competition, land budgets, unchanged consumption/capacity and lost output when workers disappear.

The geography dataset remains unaccepted. Additional historical regions, source holdouts, crop/land evidence and physically verified improvement opportunities remain outstanding. The employment targets are a demonstrated food-production mechanism for the later building pass, not an accepted complete world balance. No candidate game export or live deployment occurred.
