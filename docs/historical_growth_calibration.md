# Historical population growth calibration (2026-09-26)

Goal (Jan): roughly historical growth per super and macro region, for pops and economy, without putting the AI on
rails. The complaint was that "bumfuck nowhere" (sparse land) grows far too fast. Rule set by Jan during the work:
**positive growth only ever comes from food (storage) and offsets**, never from development or other stats.

## 1. Tribesmen growth was out of control

- England test campaign (1342-1482, autosaves every 5 years, new food chain): tribesmen on **unowned** land grew
  about **+1 %/yr** (47M -> 186M), owned tribesmen +0.1 to +0.27 %/yr.
- Cause: the -100 % tribesmen birth brake was `global_tribesmen_pop_growth`, a country modifier. Unowned land has no
  country. A first fix on the location ranks failed too: **unowned locations get no rank modifiers either** (Boror
  shows only the tribesmen share in its growth tooltip, no rank gate).
- Fix (commits 6c720513, e3af02ca): `local_tribesmen_pop_growth = -1.0` on **every topography** (the World Builder
  class generator writes it; topography modifiers do reach unowned land, their capacity rows show there). The
  free-land modifiers give back a share scaled by 1 - pop/capacity.
- Verified in game (fresh save 1337.5 -> 1338.5): unowned tribesmen 0 births, owned tribesmen +0.07 %/yr. The
  free-land modifiers do not reach unowned land either, so **unowned tribesmen do not grow at all** now; owned
  tribesmen at most ~0.15 %/yr (Jan's cap) on empty land, zero at capacity.
- The validator now simulates unowned land as its own pools and prints owned / unowned tribesmen in the build summary.

## 2. What the game did per region (old growth law)

England run, settled pops (tribesmen excluded), %/yr after the Black Death (1352 on):

| Macro region | Game | Historical, roughly |
| --- | --- | --- |
| Americas, West / Central / Southern Africa, North Asia | +0.7 to +1.5 | +0.1 to 0.2 |
| Middle East, North Africa, Central Asia | +0.4 to +0.6 | ~0 |
| Western / Eastern Europe | +0.3 to +0.7 | ~0 until 1450, then ~+0.4 |
| East Asia | 94M -> 67M, then flat | ~-25 % to 1400 (matches), then +0.4 |
| South Asia | slightly shrinking | ~+0.1 |

Mechanism: growth = rank gate -0.4 % + storage bonus 0.75 % per stored year (cap 2) + vanilla prosperity (up to
+0.2 %). Sparse provinces have huge food capacity in months (60-180 months median vs 13-35 in the cores, because
capacity is mostly flat amounts and tribesmen eat -1 each) and sit at the 24-month cap: +1.3 %/yr. Cores sit at
5-12 months stored with ~20 % of provinces starving at any time: about 0.

Victuals price over the same 130 years: stable (median 2.75 -> 3.05, per-market CV 0.19). Victuals trade between
markets is ~0 (Yards only feed their own market). Taverns 1.3k -> 11.2k levels, Yards 0.8k -> 8.1k; 3.5k Yard
levels were built in starving / < 3-month provinces; provinces holding both rise 79 -> 1,503 and swing the most.

## 3. Growth law changes (all food-side)

| Value | Before | Now |
| --- | --- | --- |
| rank gate `local_population_growth` (all ranks) | -0.004 | **-0.002** |
| storage bonus `positive_province_food_growth` per stored year | 0.0075 | **0.0015** |
| `province_starving` growth | -0.04 | **-0.02** |
| tribesmen `pop_percentage_impact` growth (offset of the gate) | 0.012 | **0.004** |
| tribesmen free-land give-back `local_tribesmen_pop_growth` | 1.0 | **0.75** |

Resulting law: ~+0.3 %/yr on full stores, ~0 at mid stores, -0.2 % at an empty (fed) store, -2 % starving.

Tried and dropped:
- A per-development growth term (separates cores from backwaters well) - forbidden by the food-only rule.
- Food capacity from development and granaries (Jan's suggestion): would cap backwater storage at ~8-10 months and
  so cut their growth, but the Victualling Yard only pays above 20 months stored, so it would switch off every Yard.
  Needs a joint redesign of the Yard band before it can be used.
- Iteration 1 (starving -0.04 kept): cores fell -0.4 to -0.7 %/yr, because the starving share then outweighs the
  smaller fed growth.

## 4. Results

In game, same save (1337.5) to 1346.4 (before the plague), settled pops, %/yr:

| Region | Old law | New law | Historical 1337-1346 |
| --- | --- | --- | --- |
| World | 0.00 | -0.16 | ~0 (famines in Europe and China in the 1340s) |
| Europe | -0.02 | -0.23 | ~0 / slightly falling |
| Asia (East Asia) | -0.06 (-0.38) | -0.16 (-0.11) | falling (late Yuan floods, famine) |
| Africa | +0.45 | -0.01 | +0.1 to 0.2 |
| Americas | +1.16 | +0.23 | +0.1 to 0.2 |
| West Africa / South America / Central Asia | +1.0 / +1.1 / +0.4 | +0.15 / +0.18 / +0.11 | ~+0.1 |

Simulator (validator re-fitted to the new law: matches the game run within ~0.2 %/yr per macro region), 1337-1600,
no plague, food production frozen at the start: world +78 % (old) -> **+19 %** (historical ~+25 % with the plague);
macro regions +0.04 (East / South Asia) to +0.26 %/yr (North Asia), sparse land +0.1 to 0.2.

## 5. Open

- **China and India grow too little in the long run** (historical +0.25 / +0.12 %/yr to 1600). With the food-only
  rule this has to come from food production growth (AI building farms and food chains, advances). The England run
  already showed East Asia flat after 1400. This is the economy half of the goal.
- The validator's "collapsing pools" count is ~0 now: at -2 % starving no pool loses 25 % in 8 years. Read
  "starving pools" instead.
- Unowned tribesmen do not grow at all (no land-aware modifier reaches unowned land).
- Tavern / Yard pairs in one province: consider an `allow` that forbids a Yard in a province with a Tavern and back.
- Only the pre-plague decade was run in game with the new law; the plague and recovery are simulator estimates.
- Test saves: `pp_tr0` (1337.5 base of this build), `pp_b1346` (old law), `pp_i2_1346` (new law). 114 old or
  incompatible saves (54.7 GB) were moved to the Recycle Bin; empty it to free the space.
