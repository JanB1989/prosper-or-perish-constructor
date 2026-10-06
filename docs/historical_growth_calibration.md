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
| `NPop.FOOD_STORAGE_POP_GROWTH` | 0.001 | 0 (0.015 until the evening of 2026-10-01) | growth from storage rides the stored-food tiers since then (6.3); 0.015 = 0.0075 per stored year x the 2-year cap was the 1.3 law on the engine term |
| `NEconomy.GROWTH_FROM_FOOD_MULTIPLIER_MAX` | 2 | 2 | the 24-month cap of the 1.3 law (the stored-months value and the tiers stop there) |
| `NPop.FOOD_SURPLUS_POP_GROWTH` | 0.0015 | 0 | growth from storage only |
| `NEconomy.GROWTH_FROM_FOOD_SURPLUS_THRESHOLD` | 1.25 | 1 | surplus factor always 0 (the AI sees no surplus value either) |
| `NPop.GROWTH_DAMPING_START` | 0.6 | 1 | `approaching_capacity` never applies |
| `approaching_capacity`, `overpopulation_growth` | -0.5 % each | empty `TRY_REPLACE` | food-only growth |

Calibration of the engine term (in force until 6.3 moved growth onto the tiers) against the 1.3 law on a fresh
vanilla 1.4 start save (4,071 provinces): the engine term is the 1.3 law exactly (same stored-years input, same cap,
linear below it). What remained:

- Fixed-point rounding (1/100,000): the 1.4 term is never higher; it is lower by up to 0.001 %/yr (mean 0.0005
  %/yr, consumption-weighted mean storage growth 0.3153 %/yr under the 1.3 law vs 0.3148 %/yr).
- Starving months: 1.3 applied the storage bonus whenever food was left; 1.4 gives nothing in a month whose deficit
  empties the store. At most 0.0625 %/yr (Y below one month) and only in that month; 0 provinces at the start date.

The deleted modifier's other effects (the storage legs of the Tavern, `province_food_purchase` -8 per stored year, and
of Surplus Sales / the Victualling Yard, `province_food_sales` +8 per stored year, and per stored year +0.003
devastation recovery, +0.045 migration attraction and +0.0025 monthly prosperity) are back since 2026-10-01 on the
Stored Food modifier (6.2; whole-month tiers that evening, one scaled modifier since 6.4), and growth joined them the
same day (6.3). Displays read script values instead of the marker the modifier carried
(`in_game/common/script_values/pp_province_food_storage.txt`: months stored, local growth for the population growth
map mode; `pp_stored_food.txt`: the applied stored years and their growth).

### 6.1 Carrier search for the other stored-food effects (2026-10-01)

**Resolved the same day: the effects are back** on 24 stored-food tier modifiers refreshed by a staggered monthly
country pulse (option 1 below in whole months; section 6.2). The search and the error table below describe the state
before that.

Jan's decision: keep all of the 1.3 effects. The 1.3 modifier (`TRY_REPLACE:positive_province_food_growth`, category
province, scaled by min(stored years, 2)) carried per stored year:

| Effect | Per stored year | Purpose |
| --- | --- | --- |
| `local_population_growth` | +0.0075 | growth law; restored on the engine term above |
| `local_province_food_purchase_output_modifier` | -8.0 | Tavern *Scarcity Premium* leg: with the country constant +15 it pays 16x at an empty store and 0x at 24 months; break-even about 12 months at the mean victuals price |
| `local_province_food_sales_output_modifier` | +8.0 | *Sell the Surplus* leg of 43 farm and fishery buildings and the Grange (its AI gate): with the constant -1 it pays 0x at an empty store and 16x at 24 months; the Grange breaks even at about 20 months |
| `local_devastation_recovery` | +0.003 | |
| `local_migration_attraction` | +0.045 | |
| `local_monthly_prosperity` | +0.0025 | |

Result: EU5 1.4 offers no engine-applied mechanism that follows a province's stored food for these five, and the
mod adds no monthly script (Jan's rule). What was checked (engine behaviour in 1.4.0 beta):

- **Hardcoded static modifiers.** None of the province or location modifiers the engine applies by name reads the
  province store; the stored-food one is gone.
- **Province refresh.** In 1.3 the engine recomputed a province's modifiers each month its stored years (capped)
  changed. In 1.4 the monthly province update recomputes them only when the province starts or stops starving, so any
  province modifier that reads the store through a script would freeze between starving flips.
- **Auto modifiers** (`scales_with` takes a script value): the engine applies them to countries and international
  organisations only. A location- or province-typed auto modifier is never applied; a country one can only carry a
  country-wide average.
- **Scaled and triggered `province_modifier` / `location_modifier` blocks** of laws, privileges, reforms, cabinet
  actions, gods and avatars: no such object is held by every country, and they refresh only when the target's
  modifiers are recomputed for another reason (province: starving flips; location: prosperity, culture, religion or
  building changes), so they can go stale for years.
- **Production methods.** `potential` / `allow` are country scope; `location_allow` is location scope, but a running
  building is not moved off a method that stops being allowed (the method switcher moves one building per building
  type, market and slot a month, and new buildings take the slot's first method). Tiered leg methods would stick on
  stale tiers.
- **Building `allow` / `max_levels`**: construction checks only; levels that exist keep running.
- **Diseases and movements** scale a location modifier by their presence, which their spread model updates per
  location. Using one as a storage carrier would be a disguised per-location loop shown to the player as an
  epidemic; rejected.

Error today against the 1.3 law, both ways (stored years capped at 2, the 1.4 start date has a
consumption-weighted mean of 0.42 stored years):

| Effect | 1.4 now | Too high | Too low |
| --- | --- | --- | --- |
| Tavern leg output | 16x at every store (+8 starving, rank, droop unchanged) | +8x per stored year, up to +16x at 24 months; mean +3.4x | never |
| Sell the Surplus leg output | about 0x (rank only) | never | -8x per stored year, up to -16x; mean -3.4x. The Grange's gate (0.8 sales vs 11.2 offset) never passes, so the AI does not build Granges; farms gain nothing from the method |
| Devastation recovery | 0 | never | up to -0.006; mean -0.0013 |
| Migration attraction | 0 | never | up to -0.09; mean -0.019 (stored food no longer draws migrants) |
| Monthly prosperity | 0 | never | up to -0.005; mean -0.0011 |

Options for Jan:

1. **Monthly province pulse (exact 1.3 law).** One province static modifier with the five per-year values, added
   once, and each month `change_province_modifier_size` to min(stored years, 2) on every province with consumption
   above 0 (4,071 at the start date): about 49,000 cheap effect runs a year (each of the ~40 generic PP building
   types already costs about 17,500 `location_potential` checks a year) plus one modifier recompute per changed
   province, which is what the 1.3 engine did itself. Rounding the size to whole months cuts recomputes to provinces
   whose month count changed, at most 1/24 of each effect's cap below the law. Needs Jan's go-ahead (no pulse
   scripts otherwise).
2. **Construction-only gates for the legs** (`allow` on `pp_province_food_storage_months`: Tavern below 12 months,
   Grange / Yard above about 20): restores where the AI builds, not what running buildings earn or how they staff;
   Taverns keep paying and serving at a full store. Partial; not applied.
3. **Country-wide auto modifier** scaled by the country's average stored years: exact for one-province countries,
   wrong inside larger ones (and a uniform migration term moves nobody). Not applied.

### 6.2 Stored-food tiers (2026-10-01, replaced the same night by 6.4)

What the game applied (behaviour level):

- **24 province static modifiers** `pp_stored_food_tier_1` .. `_24`
  (`in_game/common/static_modifiers/pp_stored_food_tiers.txt`). Tier t stands for t whole months of the province's
  own consumption in store and carries the 1.3 payload per stored year x t / 12: sales leg +8, purchase leg -8,
  devastation recovery +0.003, migration attraction +0.045, monthly prosperity +0.0025 per stored year, and since
  6.3 population growth +0.0075 per stored year. Tier 24 = two stored years = the 1.3 cap. Below one month a province
  carries no tier. Values are rounded to five decimals (EU5 1.4 rejects six-decimal values as badly read).
  Configured in `[stored_food]` in `constructor.toml`; `stored_food.py` writes the modifiers, their localization
  ("Stored Food: N months"), the tier script value, the growth display value, the customizable localization that
  names the carried tier and the refresh effect in the finalize step of `ppc build` / `ppc sync`.
- **Months stored** (province scope, `pp_province_food_storage.txt`): consumption = the sum of the locations'
  `food_consumption` x -1 (the location value is negative, e.g. London -140.37), months = `province_food` /
  consumption, 0 to 24; tier = whole months (`pp_stored_food_tier_target`). The location-scope values the GUI, map
  mode and chips read (`pp_province_monthly_food_consumption`, `pp_province_food_storage_months`) delegate to the
  province ones; before this fix they guarded on consumption > 0 and read 0 everywhere in 1.4.
- **Refresh** (`pp_refresh_stored_food_tier`, province scope): the new tier goes into a province variable (+100 offset,
  as a variable at 0 counts as unset), the change is a difference + 100 matched by `<` / `>` ranges (`var:x = n` is a
  scope comparison in game); only a changed tier removes the old modifier, adds the new one and stores it.
- **Hook** (`in_game/common/on_action/pp_stored_food.txt`): the vanilla `monthly_country_pulse` runs
  `pp_stored_food_country_refresh` after a random 0-29 day delay, so the countries spread over the month; each
  refreshes `every_province` it owns (all 4,071 food provinces at the start date). `pp_stored_food_game_start`
  (`pp_game_start.txt`) sets every country's provinces on day one. Old saves: a province without the variable gets its
  tier at its owner's next pulse (within a month).
- **Exception to the no-pulse rule**, approved by Jan on 2026-10-01 after the in-game test over one game year:
  exact tier on 94 % of the provinces (the rest at most one month behind), total effect +0.1 % against the target,
  about 700 tier changes a month, cost 0.56 s per game year (about 12 µs per province and month, at most 5 ms for one
  country's call). In-game findings that shaped it: static-modifier amounts cannot use scope-dependent script values
  (they read 0), `add_*_modifier` has no scale, `food_consumption` is location-only and negative, and province scope
  has `province_food`, `province_food_percentage` and `province_max_food` but no consumption value.

Error against the 1.3 law: at most one month of stores below it (1/24 of each effect's cap), plus up to a month of
lag after the store crosses a whole month.

Tooling: `ppc province-food-sales-check` reads the sales leg per stored year from `[stored_food.per_year]`; the
migration model's stored-food attraction (`food_years`) is +0.045 per stored year again, in whole months; the food
simulation's prosperity fit (1.3 stored-years slope) applies again.

### 6.3 Growth on the stored-food tiers (2026-10-01, applied)

Growth from stored food moved from the engine term onto the tier modifiers, with the same numbers; the formula is
unchanged (Jan: "don't change the math yet"), no damping or hysteresis was added.

- `[stored_food.per_year]` carries `local_population_growth = 0.0075`, so tier t gives +0.0075 x t / 12 a year
  (tier 24 = +1.5 %, the old `FOOD_STORAGE_POP_GROWTH` 0.015 at the 2-year cap). `NPop.FOOD_STORAGE_POP_GROWTH` is 0
  (the engine term is off); `NPop.FOOD_SURPLUS_POP_GROWTH` stays 0.
- Behaviour (until 6.4 made it continuous): growth from stored food is part of the province's Stored Food modifier and
  of `modifier:local_population_growth` (the population growth map mode reads that alone again). It moved in whole-month
  steps, renewed by the monthly refresh, instead of continuously each month: up to one month of stores below the old
  term (at most 0.0625 %/yr), up to a month of lag after the store crosses a whole month, and a province whose store
  runs empty keeps its tier's growth until its next refresh (the engine term stopped in the starving month itself).
- Displays: the location view's Stored Food chip lists the carried tier's effects (location_status.py, the
  customizable localization `pp_stored_food_tier` names the carried modifier); `pp_province_food_storage_growth` is
  generated with the tiers and reads the carried tier from the province variable.
- **To watch in a run:** the AI no longer sees storage growth through the define. It valued stored food through
  `FOOD_STORAGE_POP_GROWTH` when it rated modifiers; with the define at 0 that part of its valuation is gone (the
  tier modifier's growth is applied by script, not something the AI anticipates). Check in a run whether the AI still
  builds food storage and storage-related buildings as before.
- Tooling: the food simulation counts stored years in whole months for growth (`migration.stored_food_tier_years`;
  its fitted slope 0.0086 is unchanged).

### 6.4 One Stored Food modifier scaled by stored years (2026-10-01, applied)

The tiers made every effect a staircase: inside each month nothing moved, and from 0 to 1 month the Sell the Surplus
legs and the Grange / Yard gate stayed at 0x and the Tavern leg at the full 16x, so poor provinces (which live in that
band) looked empty to their buildings. Replaced by the exact form option 1 of 6.1 described:

- **One province static modifier** `pp_stored_food` (`in_game/common/static_modifiers/pp_stored_food.txt`) carries the
  payload of one stored year (`[stored_food.per_year]`, unchanged). It is applied with `add_province_modifier = {
  modifier = pp_stored_food size = <stored years> }`, so 0.3 stored months give 0.3/12 of each effect. The payload is
  per year because per-month values (0.0075 / 12) would need six decimals, which 1.4 rejects.
- **Refresh** (`pp_refresh_stored_food`, `scripted_effects/pp_stored_food.txt`, same staggered monthly country pulse
  and game-start call): the consumption (the location loop) is worked out once into a local, months =
  `province_food` / consumption capped at 24, and the modifier is removed and re-added with the new size only when the
  months moved by more than `deadband_months` (0.05) since the last refresh, or the store emptied. The applied months
  sit in the province variable `pp_stored_food_size` (+100 offset). Remove + add, not `change_province_modifier_size`:
  vanilla uses that as a delta (`value = -1`, then checks the strength), and a set is drift-free.
- **Old saves**: the 24 tier names stay defined without effects so tier-version saves load; the first refresh removes
  a province's tier modifier and its three variables. The tier version's files are deleted by `ppc build`.
- **Displays**: `pp_stored_food_years` (location scope, the applied size) and `pp_province_food_storage_growth` (its
  growth); the location view's Stored Food chip lists each effect as `pp_stored_food_years` x its per-year value and
  shows the months with one decimal.
- **Verified in game** (2026-10-01, Jan's 1462 observer save made with the tiers, temporary probe = a marker type
  injected into `pp_stored_food`, read back as the engine's applied size): after one month 3,736 of 3,836 provinces
  carried exactly the size the script applied, 131 of 132 provinces under one stored month got their effects, legacy
  tiers left only on provinces whose owner had not pulsed yet; after one year 0 legacy modifiers or variables,
  3,840 of 3,919 exact. Every mismatch carried the modifier with the previous size (e.g. 1.918 instead of 1.888
  years): locations pick up a re-applied size within a few days. So `size` scales a permanent province modifier,
  including its location-level `local_*` effects.
- **Cost** (script profiler, one game year 1462-63, 3,912 provinces): 0.525 s per game year (11 µs per province and
  month; the tiers: 0.56 s in their test, 13.9 µs in the 1337-1412 profile); the consumption loop 0.25 s. About 2,600
  re-applies a month (tiers: ~700 changes); the engine's modifier recompute for them does not show in the script
  profile. `deadband_months` is the lever if a profile shows it.

### 6.5 Store lever: Low Stores and Full Stores (2026-10-02, branch `province-food-store-lever`)

Jan's design: the store no longer carries big output multipliers on dummy goods. It moves what Province Food is
worth, and everything that makes Province Food answers by itself.

- **Three province modifiers** (`stored_food.py`, `[stored_food]`): Stored Food (size = stored years) keeps growth,
  devastation recovery, migration attraction and prosperity. **Low Stores** is applied at size = the years the store
  is below 12 months (1 at an empty store), **Full Stores** at the years above (1 at 24 months). At 12 months neither
  exists, so there are no country base values for the store (the old -100 % Surplus Sales, +1500 % Scarcity Premium
  and +1900 % offset constants are gone).

  | Line | Low Stores (per year short) | Full Stores (per year above) |
  | --- | --- | --- |
  | Province Food output (`local_local_food_output_modifier`) | +0.75 | -0.75 |
  | staple output (one line per provisioned good) | none | +0.20 |
  | Surplus Sales output (the Grange) | -3.0 | +0.34 |

- **Farms** (every Provisioning building): one always-on Provision method, no Sell the Surplus. A wheat farm level
  on decent land yields 3.2 / 2.5 / 1.7 food and 0.23 / 0.23 / 0.28 wheat at 0 / 12 / 24 months; its profit stays
  positive and is highest at a low store. Staples are not cut below 12 months: the farms' Market gate leg sells the
  staple, and a cut would stop the AI from building new farms where the store is low.
- **Cookshop**: recipes unchanged; it serves while Province Food output x revenue covers its staples. At default
  prices (inputs 1.04 x revenue) it fills the store to 11.4 months, 13.6 with staples 15 % cheaper, 8.8 with 15 %
  dearer. New Cookshops pass the AI gate below about 10 months.
- **Tavern**: Serve Victuals is its only slot and its gate (0.8 victuals, 0.08 labour, 0.91 offset -> 24 Province
  Food). It fills the store to 10.7 / 7.0 / 2.7 months at victuals 2.0 / 2.7 / 3.5 and stops above 4.0;
  `province_starving` adds +100 % Province Food output, so a starving province still buys up to about 7.
- **Grange**: 0.6 victuals from 24 food, Surplus Sales 4.0 against 6.1 offset (4.46 on Surplus Sales, the gate method,
  1.64 on Haulage). It packs down to 20.6 / 16.9 / 12.7 / 11.5 / 10.6 months at victuals 2.0 / 2.7 / 3.5 / 4.5 / 6.0;
  the Surplus Sales end at 8 months, and without them packing pays only above victuals 10.3 (6.9 at +50 % production
  efficiency). The AI builds a new Grange from 18 months. A staffed Tavern takes 500 % of the Surplus Sales in its
  location per level, and `province_starving` sets victuals output to -200 %: a starving province packs nothing.
- **No droop and no dead legs**: the per-level droops of Tavern and Grange are gone; the Scarcity Premium good
  (`province_food_purchase`) stays defined for old saves but nothing produces it.

Simulation (`tools/province_store_sim.py`, 13 province cases built from the game-start pools, 60 years monthly, the
engine's staffing rule): stores rest at the break-even of the building that feeds or skims them (7 months behind
Taverns, 11.4 behind Cookshops, 17 under Granges with enough levels), ripple at most +-0.5 months without harvest
rolls, +-1.7 with the modifier seen three months late, about 6 months wide with harvest rolls, lag and the
prosperity appetite together. No sustained swing. What it does not do: a surplus province with too few Grange levels
still sits near its cap, and a deficit province without Cookshop or Tavern still starves.

Known limits:

- **Production efficiency** adds to the same pool as the lever, so it moves every rest point by about 1.6 months per
  +10 % (Taverns and Cookshops fill higher, Granges pack deeper). From about +25 % a Tavern and a Grange in the same
  province would both pay at one store; the Tavern's cut of the Surplus Sales bounds the food that cycles between
  them (9 % of consumption in the worst simulated case).
- **Growth**: the start-food validator (now on the lever's rules, `SimRules.from_project`) gives +4.93 % world
  population over 96 months (+5.37 % with the validator's old rules, which still carried the pre-2026-09-30 60-food
  Tavern and Grange), 2,673 pools pinned at the cap (3,262), 2 collapsing (3), 125 with a starving month. Cookshop
  provinces rest near 11 months instead of at the cap, so they grow more slowly; the growth law itself is unchanged.
- **Not verified in game.** The modifiers, the refresh and the buildings load without script errors (1.4.0); rest
  points, AI building and old-save behaviour are untested. Saves made before the change keep an empty Provisioning
  slot where a building ran Sell the Surplus: a new game is needed.

### 6.5a One Stored Food step modifier (2026-10-03, branch `province-food-store-lever`)

Jan: one food storage modifier that shows in the location view in its rightful place. The three size-scaled modifiers
(Stored Food, Low Stores, Full Stores) are replaced by 25 province modifiers `pp_food_store_0` .. `_24`, one per whole
stored month; a province carries exactly one, and the location view's province modifier list shows it with its true
values (the list no longer skips it; the Stored Food chip stays).

- Step s carries, worked out exactly and rounded once to five decimals: `[stored_food.per_year]` x s / 12, plus
  `[stored_food.low]` x (12 - s) / 12 below the pivot or `[stored_food.full]` x (s - 12) / 12 above it. Step 0 is the
  whole Low Stores year, step 12 carries no lever line, step 24 is two Stored Food years plus the whole Full Stores year;
  every line is within 0.000005 of the continuous value (tests/test_stored_food.py).
- Step choice: the stored months rounded to the nearest whole month, half up (`add = 0.5 floor = yes`); re-picked only
  when the store moved more than 0.55 months (half a month + `deadband_months`) away from the carried step, so a store
  on a boundary does not flip each month; an emptied store always lands on step 0; a province nobody eats in carries
  none. Against the continuous lever the effects sit at most about half a month off (Province Food output 3 %, Surplus
  Sales 1-12 %), the rest points of the buildings move in whole-month steps.
- `pp_stored_food_months` keeps the continuous stored months (deadband 0.05) for the AI weights
  (`pp_location_stored_months`); `pp_food_store_step` holds the carried step (+100). A step change removes only the
  carried step's modifier and finds both steps by halving the 25 (2026-10-06). No old-save support since
  2026-10-06 (Jan: the shipped mod is not save compatible across versions): the earlier carriers are gone.

### 6.6 Mini World growth calibration (2026-10-03, branch `province-food-store-lever`)

Jan's target: world growth about 0.3 %/yr, not uniform, set through food or minimal changes to growth from storage, no
financial or growth buffs. Test bed: PP + EU5 Mini World for PP, profile `europe` (5,543 land locations, 78.4M people at
start, the rest of the world empty and non-ownable), observer at top speed, five-yearly autosaves, 1337-1437 (100
years in about 25 minutes; runs 3 and 4 went on to 1522, 185 years in about 50 minutes). Saves are extracted to
`~/pp_ai_run/tables/miniN_*`; the scripts (session scratchpad) report growth per step, stores, starvation, food
buildings and a population-weighted fit of province growth on stored years. Run 4 starts from run 3's start save.

| Run | Rules | 1337-1347 | Black Death 1347-1352 | 1352-1437 | 1437-1522 | Store (mean) | Fit 1352-1437 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | food set 303946d8, Stored Food 0.0075 | -0.09 / +0.35 %/yr | -30 % | +0.48 %/yr | | 16.3 months | -0.26 + 0.54 x stored years |
| 2 | + flat Cookshop veto, Stored Food **0.006** | -0.22 / +0.50 %/yr | -30 % | **+0.28 %/yr** | | 15.9 months | -0.43 + 0.54 x stored years |
| 3 | + Daily Fare gate (384a743c) | +0.50 / -0.28 %/yr | -29 % | +0.28 %/yr | -0.00 %/yr | 16.0 / 13.6 months | -0.45 + 0.55 x stored years |
| 4 | + flat Tavern weight terms (b4b4c102) | +0.49 / -0.70 %/yr | -32 % | +0.30 %/yr | -0.04 %/yr | 15.8 / 13.8 months | -0.34 + 0.48 x stored years |
| 5 | new game: Grange price rule, grain-only Yard (d3091976), speed defines | | -29 % | +0.28 %/yr | -0.06 %/yr | | |

- The growth law is `local_population_growth` 0.006 per stored year since run 2 (0.0062 would give 0.30 exactly at the
  stores of run 1). The engine's surplus term (`FOOD_SURPLUS_POP_GROWTH`) stays 0: growth was already above target.
- Run 2: 0.4-1.9 % of provinces starving at a save (0.1-1.5 % of the people); of the provinces starving at a save half
  hold 3+ months five years later and 31 % still starve. The AI answers with Cookshops (29 levels per 100 starving
  province-steps), farms (14) and Taverns (10). The chronic cases are tiny collapsed pools (1-3k people: Ireland,
  steppes, Urals, North Atlantic isles) whose Cookshops find no staff.
- Two thirds of the peasants are jobless (subsistence) throughout; farm levels grow about 50 % in 100 years.
- **Plateau after about 1450 (runs 3 and 4).** The population stops growing (71.1M and 65.9M in 1522; 78.4M at start):
  the mean store falls from 16 to under 14 months, provinces under 3 months rise from about 6 % to 14 % (starving 2 % ->
  5 %), staples supply/demand falls from about 1.0 to 0.8-0.9 and victuals cost 3.5-3.7 (default 3.0). The hunger is
  structural (the starving provinces of 1512 make 61 % of what they eat) and has spread into big provinces of the core
  (Lombardy, Bohemia, Castile, the Low Countries). Europe as a whole still makes about 20 % more food than it eats, but
  the surplus sits in full inland provinces: with the Grange off it can only leave as crops (farms) or as victuals from
  harbour Yards. Cookshops are the main staple buyers (building demand 2.6k -> 6k a month, pops 1.8k -> 2.7k).
- **Taverns ratchet.** 68 -> 735 levels (run 3) and 815 (run 4) by 1522 at 240-263 town capitals. The AI adds them in
  famines, often 2-12 levels at once, never removes them, and about 60 % stand idle once the store refills. The flat
  Tavern weight terms of run 4 changed nothing measurable: the AI's score for a Tavern in a famine runs from thousands
  to billions (the engine's food term), far beyond any weight; only the gate (Serve Victuals) is a hard stop.
- AI answer to hunger (run 4, levels added per 100 province-steps): starving provinces get Taverns 20, Cookshops 14,
  farms 12 (42 % hold 3+ months five years later, 36 % still starve); provinces at 3-12 months get Cookshops 22, farms
  10, Taverns 4; full provinces farms 16, Cookshops 4. Farms follow crop prices, not the local store: the farm weight's
  store bonus lifts their AI score in hungry provinces (median 6.7 below 3 months vs 2.4 at 12-15) but stays far below
  what a Cookshop or Tavern scores there.
- Engine behaviour around the gates (run 3): a gated building (score 0) gets no close or subsidy decision, so subsidies
  granted in a famine are never withdrawn once the store refills (about 100 Cookshops subsidised at 18+ months by
  1500), while Cookshops in hungry provinces that cannot buy their inputs get closed (90-140 at 4 months or less).
  80 % of Cookshop levels stand in full provinces; their `local_monthly_food` (10 per staffed level) is not on the store
  lever.
- **Run 5** (Grange back with its price rule, grain-only harbour Yard; pp_mini5_base): the victuals market healed
  (supply/demand 0.86 in 1522, price 3.38; Granges 883 levels but only 13 % staffed), the plateau stayed (66.9M in
  1522). Why dear victuals did not reach the farms: farm and Cookshop levels were added where victuals were cheap and
  lost where they were dear (per million people and 5 years: farms +4 below 3.0, -13 above 4.0); the farm weight reads
  the crop price and the store (below 14 months) only, Yards stood only on harbours, and the dear markets' provinces sat
  at a median 14.8 months, between the farm store bonus and the Grange line (19.4 months at 3.5). Victuals demand
  1402 -> 1522: 399 -> 891, of it lumber mills 149 -> 235 (Extra Rations), Taverns 43 -> 185, pops 123 -> 202.
  Farm output per level fell about 9 % (no relief from advances). Answer (2026-10-03 evening): the steeper Grange line,
  Yards at every market centre (small inland caps), lumber mill victuals methods only in a glut.

### 6.7 Farm trade-off: one store curve for every staple good (2026-10-03)

Jan's design of 2026-10-02 (the farm feeds the province while the store is low and sells its crop while it is full),
never built until now: farm v3 had set the staple line to 0, so a hungry farm was strictly better than a full one.

- The store curve (`[stored_food.curve]`): Province Food output of every maker at Jan's shares 100 / 80 / 65 / 50 /
  40 % of an empty store's output at 0 / 6 / 12 / 18 / 24 months (+53.8 % / +23.1 % / 0 / -23.1 % / -38.5 %, linear
  between; was +-75 % linear); one crop line for the 8 crop farm goods = -0.40 x that (-21.5 % at an empty store,
  +15.4 % at 24 months). Output modifiers are per good, so every farm tier, every RGO and every other producer of these
  goods carries the same line; fish, fruit and game stay off it. Since 2026-10-04 (Jan: one staple food list, staple
  crops, animals and fruits) every staple food is on the curve, and every staple food building provisions: fish -0.20,
  fruit -0.21, wild_game -0.14, wool -0.23 by the same food-for-goods balance against the crop farms' 0.40
  (`staple_per_province_food_by_good`; `tests/test_staple_foods.py` recomputes it from the blueprints).
- 0.40: what a farm gains in food it gives up in crop at 12 food per unit of crop value; with the late tiers' changes
  below every farm's value (food + 12 x crop value) moves by at most 8 % between an empty and a full store.
- Late tiers: their crop is 4-15x tier 0's for about the same Province Food, so the crop line in a poor harvest at a
  low store cost them more than their Provision earned and they laid off workers (already at harvest -0.15..-0.35
  before). Tiers 2-3 now run their cultivation at half throughput, make 55 % of their food at 12 months as Province Food
  (Rotation Farm 3.78 Province Food + 3.09 flat, Model Farm 5.29 + 4.33; same total), and Rotational Farmsteads / Model
  Farms add +0.05 output of every crop farm good. Profit per level at 12 months: tier 2 0.59-0.66 (was 0.50-0.65),
  tier 3 0.87-1.08 (0.63-0.98); crop per level at 12 months: tier 2 1.16 (2.14), tier 3 1.81 (3.16).
- The promise (tests/test_crop_farms.py): at 0-12 stored months no crop farm loses money, so none lays off workers, on
  land 0 in a -0.5 harvest or on land -0.10 in a -0.4 harvest, with its cultivation held (default prices). Worst
  harvest survived on land 0 (0 / 12 / 24 months): tier 0 any / any / -0.90, tier 1 -0.59 / -0.67 / -0.72, tier 2
  -0.50 / -0.54 / -0.56, tier 3 -0.51 / -0.56 / -0.59.
- The Tavern's Serve Victuals went from 24 to 25.5 Province Food (the curve gives less at an empty store than +75 %):
  it fills the store to 11.6 / 5.9 / 1.0 months at victuals 2.0 / 2.7 / 3.5 (was 10.7 / 7.0 / 2.7).
- The crop farms' `ai_construct_weight` reads the land without the store's line (`pp_stored_food_staple_line`).
- Start validator (96 months): world +2.99 %, 11 of 2,883 food pools lose 25 % or more. Not tested in game.
