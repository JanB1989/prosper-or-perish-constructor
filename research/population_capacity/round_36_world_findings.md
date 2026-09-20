# Global collateral comparison

**Diagnostic results, not overall acceptance.** Every location is simulated with identical geographical inputs, starting composition, food supply, employment and consumption. These comparisons use the growth and development settings recorded in each manifest scenario. Subsistence output and other shared inputs are recorded in the preparation manifest. No new cookery or victuals-market food is assumed.

| Scenario | Year | World population (millions) | World capacity (millions) | Locations with more unmet food than native-rank control | Locations below 90% starting population | Locations at stock-growth ceiling ≥90% of months |
|---|---:|---:|---:|---:|---:|---:|
| native_rank_no_offset | 100 | 514.315 | 1916.026 | 0 | 4997 | 1158 |
| native_rank_no_offset | 200 | 566.663 | 1961.360 | 0 | 4985 | 179 |
| equal_rank_quarter_offset | 100 | 514.496 | 1918.420 | 443 | 4991 | 1158 |
| equal_rank_quarter_offset | 200 | 562.584 | 1965.880 | 453 | 4987 | 179 |
| common_middle_quarter | 100 | 505.083 | 1919.687 | 75 | 5062 | 1321 |
| common_middle_quarter | 200 | 551.424 | 1969.549 | 82 | 5063 | 179 |
| common_slower_quarter | 100 | 495.736 | 1920.922 | 23 | 5119 | 1539 |
| common_slower_quarter | 200 | 540.601 | 1973.273 | 23 | 5126 | 189 |
| common_slower_half | 100 | 496.191 | 1924.232 | 20 | 5115 | 1542 |
| common_slower_half | 200 | 541.984 | 1980.295 | 20 | 5104 | 189 |

World checkpoints reproduce the independently saved monthly provincial comparison within 0 absolute units across population, capacity, development, food stocks, production and consumption. Replay is checked at years 0, 25, 100 and 200.

Growth-ceiling duration measures the provincial food-stock bonus, not net growth of every population type. Tribesmen retain the authorized cancellation. Sparse settlements are not rejected solely for reaching the ceiling. Historical demographic applicability, initial denominators, annualized growth, local drawdowns and physically defensible accessible capacity must be evaluated together. The 36 initially empty locations remain empty; proportional retention and annualized growth are undefined there and excluded from those distributions, while their capacity and food remain in world accounts.

Additional unmet food identifies collateral risk requiring diagnosis; it is not hidden by a higher world total. Global population declines are likewise not all classified as failed healthy controls: this world includes genuine starting scarcity and unmodeled external supply. The complete per-location effects and scoped quantiles are saved alongside this report.

Artifacts: `world_comparison.csv`, `all_location_collateral.parquet`, `horizon_scope_distributions.csv`, `largest_capacity_outcomes.csv`, annual province/scope histories, all-location checkpoints and the fingerprinted manifest.

