# Round 35 global collateral comparison

**Diagnostic results, not overall acceptance.** Every location is simulated with identical geographical inputs, starting composition, food supply, employment and consumption. These comparisons change the extra urban growth penalty and partial land-pressure development retention only. No new cookery or victuals-market food is assumed.

| Scenario | Year | World population (millions) | World capacity (millions) | Locations with more unmet food than native-rank control | Locations below 90% starting population | Locations at stock-growth ceiling ≥90% of months |
|---|---:|---:|---:|---:|---:|---:|
| native_rank_no_offset | 100 | 500.170 | 1914.431 | 0 | 5093 | 1098 |
| native_rank_no_offset | 200 | 544.888 | 1958.989 | 0 | 5066 | 179 |
| equal_rank_no_offset | 100 | 499.857 | 1913.433 | 611 | 5118 | 1098 |
| equal_rank_no_offset | 200 | 539.599 | 1956.275 | 632 | 5130 | 179 |
| equal_rank_quarter_offset | 100 | 500.332 | 1916.778 | 489 | 5111 | 1098 |
| equal_rank_quarter_offset | 200 | 541.006 | 1963.362 | 499 | 5109 | 179 |

World checkpoints reproduce the independently saved monthly provincial comparison within 0 absolute units across population, capacity, development, food stocks, production and consumption. Replay is checked at years 0, 25, 100 and 200.

Growth-ceiling duration measures the provincial food-stock bonus, not net growth of every population type. Tribesmen retain the authorized cancellation. Sparse settlements are not rejected solely for reaching the ceiling. Historical demographic applicability, initial denominators, annualized growth, local drawdowns and physically defensible accessible capacity must be evaluated together. The 36 initially empty locations remain empty; proportional retention and annualized growth are undefined there and excluded from those distributions, while their capacity and food remain in world accounts.

Additional unmet food identifies collateral risk requiring diagnosis; it is not hidden by a higher world total. Global population declines are likewise not all classified as failed healthy controls: this world includes genuine starting scarcity and unmodeled external supply. The complete per-location effects and scoped quantiles are saved alongside this report.

Artifacts: `world_comparison.csv`, `all_location_collateral.parquet`, `horizon_scope_distributions.csv`, `largest_capacity_outcomes.csv`, annual province/scope histories, all-location checkpoints and the fingerprinted manifest.

