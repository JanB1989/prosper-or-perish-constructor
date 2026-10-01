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

## 6. EU5 1.4 port (2026-10-01)

The law in force at the port is the restored one (rank gate -0.004, storage +0.0075 per stored year up to two years,
`province_starving` -0.04); section 3's cut was rejected.

EU5 1.4 deleted the engine-scaled static modifier `positive_province_food_growth` that carried the storage bonus
(the mod's `TRY_REPLACE` of it is gone) and added two food growth terms of its own. Engine behaviour (1.4.0 beta):

- Each month a province gets two factors from 0 to 1. Storage: stored years Y = stored food / (12 x its monthly
  consumption), factor min(Y, `NEconomy.GROWTH_FROM_FOOD_MULTIPLIER_MAX`) / that cap. Surplus: the monthly food
  balance / monthly consumption, divided by (`NEconomy.GROWTH_FROM_FOOD_SURPLUS_THRESHOLD` - 1), clamped to 0..1
  (0 when the threshold is 1 or below).
- Every location of a province whose consumption is above 0 and that is not starving adds
  `NPop.FOOD_SURPLUS_POP_GROWTH` x surplus factor + `NPop.FOOD_STORAGE_POP_GROWTH` x storage factor to its yearly
  growth, on top of the summed `local_population_growth` and `global_population_growth` modifiers (it is not part of
  the `local_population_growth` modifier, so `modifier:local_population_growth` misses it). "Starving" is the same
  test that applies `province_starving`: the store is empty, or this month's deficit empties it.
- `cap_maximum_population_growth_at_zero` still caps the total at 0.
- New brakes near capacity: `approaching_capacity` (-0.5 % growth, scaled from `NPop.GROWTH_DAMPING_START` x
  capacity up to capacity) and `overpopulation_growth` (-0.5 %, applied with `overpopulation`, strength 1 + the
  share over capacity).
- The AI values stored food and food surplus through the same two defines when it rates modifiers.

PP settings (`pp_defines_adjustments.txt`, `pp_capacity_pressure_effects.txt`):

| Setting | Vanilla 1.4 | PP | Why |
| --- | --- | --- | --- |
| `NPop.FOOD_STORAGE_POP_GROWTH` | 0.001 | 0.015 | 0.0075 per stored year x the 2-year cap: the 1.3 law |
| `NEconomy.GROWTH_FROM_FOOD_MULTIPLIER_MAX` | 2 | 2 | the 24-month cap of the 1.3 law |
| `NPop.FOOD_SURPLUS_POP_GROWTH` | 0.0015 | 0 | growth from storage only |
| `NEconomy.GROWTH_FROM_FOOD_SURPLUS_THRESHOLD` | 1.25 | 1 | surplus factor always 0 (the AI sees no surplus value either) |
| `NPop.GROWTH_DAMPING_START` | 0.6 | 1 | `approaching_capacity` never applies |
| `approaching_capacity`, `overpopulation_growth` | -0.5 % each | empty `TRY_REPLACE` | food-only growth |

Calibration against the 1.3 law on a fresh vanilla 1.4 start save (4,071 provinces): the engine term is the 1.3
law exactly (same stored-years input, same cap, linear below it). What remains:

- Fixed-point rounding (1/100,000): the 1.4 term is never higher; it is lower by up to 0.001 %/yr (mean 0.0005
  %/yr, consumption-weighted mean storage growth 0.3153 %/yr under the 1.3 law vs 0.3148 %/yr).
- Starving months: 1.3 applied the storage bonus whenever food was left; 1.4 gives nothing in a month whose deficit
  empties the store. At most 0.0625 %/yr (Y below one month) and only in that month; 0 provinces at the start date.

Gone with the deleted modifier and not replaced (no modifier scales with stored food in 1.4): the storage legs of
the Tavern (`province_food_purchase` -8 per stored year) and of Surplus Sales / the Victualling Yard
(`province_food_sales` +8 per stored year), and per stored year +0.003 devastation recovery, +0.045 migration
attraction and +0.0025 monthly prosperity. Displays read script values instead of the marker the modifier carried
(`in_game/common/script_values/pp_province_food_storage.txt`: months stored, growth from storage, growth incl. the
storage term for the population growth map mode).
