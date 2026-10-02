# EU5 market membership rulebook

Verified 2026-09-27 on EU5 1.3.11 with Prosper or Perish (Jan's playset: main mod, Community Mod Framework, Faster
Universalis), in a 36-month observer run from 1337.4.1: one save per `tick_day 15` (~29.4 days, `pp_mkt_m01..m36`),
the per-location dump `tools/markets/pp_mk.txt` from month 12 on and at the start, and the in-game market tooltip.
Code: `src/prosper_or_perish_constructor/worldbuilder/markets.py` (rules), `tools/markets/` (kit),
`food_sim.py` (`market_assignment = true`).

Toy sheet: [EU5 market attraction toy (mod values)](https://docs.google.com/spreadsheets/d/1d9oY7BfSLBmzzmUjzW9q446aRhj1T-lbK_5ap16swKs/edit)
(Google Sheet): three markets and eight locations with editable inputs, the attraction terms of section 2, the access
steps of section 3 as summed route legs, the market each location joins this tick and next month (drifting prestige,
control, development, building levels), the rules and the factor table. Two near ties show the monthly flipping of
section 4; the proposal levers (prestige weight, protection per control, flat protection) test jitter fixes.

## 1. The rule

**A location belongs to the market with the highest market attraction.** The engine recomputes it for every location
at the monthly tick and switches immediately; there is no hysteresis, no threshold and no range limit (distance only
works through access).

- The first tick after the game start moved 1,086 locations at once: the setup assignment is not the engine's argmax.
- The saved `market_attraction` is the value of the last tick; the live tooltip ("Highest Market Attraction") shows the
  current values (thisted, 1338.3.19: tooltip Lübeck 88.94 %, Oslo 88.14 %; the model gives 0.8895 and 0.8814).
- Of 3,017 locations whose best-access market is not their market, 8 would score higher there (lakes, treaty cases).

## 2. Attraction of location L toward market M

| Term | Value | Source |
|---|---|---|
| market access of L to M | 0..1 | section 3 |
| market attraction of the centre | `local_trade_center_power` of the centre location | mod since 2026-09-27: development x 0.002, market buildings (entrepot, trading hub, customs house, stock exchange, clearing house) 0.05 x staffed level, Global Trade birthplace 0.1, uniques. The measured runs had the older values: development x 0.001, building levels x 0.0004, rank (city 0.025, megalopolis 0.05), market buildings 0.1, walls 0.1, good natural harbour 0.01 (vanilla: development 0.002, building levels 0.0005). Building values are `market_center_modifier`, scaled by staffing like every building modifier (walls at 50 % staff gave 0.05) |
| attraction of the owner | `global_trade_center_power` of M's owner | prestige 0.05 x prestige/100 (vanilla auto modifier `prestige`; the mod doubles it to 0.10 since 2026-09-27, `auto_modifiers/pp_prestige_trade_power.txt`), advances, privileges (the mod removed the trade_vs_tax line) |
| language power | 0.1 x power of M's market language | `MARKET_LANGUAGE_POWER_ATTRACTION`; power 0..1 relative to the top language (`language_manager`) |
| geography | +0.2 same province as the centre, else +0.1 same area | smallest shared unit only; region, subcontinent and continent 0 |
| owner's language | +0.05 if M's language is the common language of L's owner (language of its primary culture), else +0.01 same language family | owned locations only |
| location's language | +0.05 if M's language is L's dominant language, else +0.01 same family | |
| treaties | small per country pair (+0.005 .. +0.011 seen) | `trade_to_first/second` relations; not modelled |
| protection | −(`local_trade_protection_factor` + `global_trade_protection_factor`) of L | only if L is owned and its owner is neither M's owner nor a subject of M's owner |

- Local protection is the static modifier `control`: 0.5 x control (within ±0.003), plus buildings (port authority 0.1,
  toll castle 0.05) and town rights. Country protection: mercantilism up to +0.5, reforms 0.1; 11 locations in 1339.
- The market language is the majority burgher language at the centre (save `markets.language`); dialects count as
  their language (`in_game/common/languages`: a culture may carry `english_dialect`, the market `english_language`).
- Fit, model vs saved attraction toward the current market (saved access): months 13-36 91-99 % within 0.005,
  median error 0.0002; 99.4 % within 0.001 in the save taken right after a tick (m28). Remaining: treaty flows,
  Paris (+0.1 constant, unexplained), 116 lake and sea tiles (−0.1/−0.2).

## 3. Market access

Access = 1 − transport cost from the market centre to L + `local_market_access` of L, clamped to 0..1 (tooltip:
"Base 100 %, Transportation distance to market −x %"). The cost is the cheapest path over the location graph
(`worldbuilder/market_access.py`), step by step, with K = 0.0024 per pixel (= `MARKET_BASE_DISTANCE_FACTOR` 0.006 x
0.4, the 0.4 is measured, not found in a file) and d = distance between the bounding-box centres of the two locations
in locations.png:

| Step | Cost |
|---|---|
| land → land | K d favg min(road, river); f = 1 + (topography movement_cost − 1)/2 + (vegetation movement_cost − 1)/2, favg the mean of both ends; road = 1 + the road's `market_access` if negative (gravel 0.9, navigable river 0.4, improved 0.2; positive values ignored); river 0.5 downstream / 0.8 upstream (seen from the centre), else 1 — see the river test below |
| water → water | K d favg S road; S = 0.2 (`MARKET_SEA_DISTANCE_FACTOR`), 0.4 if either tile is open sea (no passable land neighbour) or the step joins a lake and a sea tile |
| land ↔ water | (K d 0.15 + P) road; P = 0.02 x (1 − harbour suitability) if the land location is owned, has a port and the water tile is its port sea zone or a lake, else 0.1 (`MARKET_NO_PORT_EXTRA_DISTANCE`) |

- **River test** (found 2026-09-27 on 10,304 measured land edges): a land step gets the river factor when the river
  of rivers.png runs from one location into the other (traced from the sources, direction = flow) AND the straight
  line between the two bounding-box centres, the same line the distance is measured on, touches a river pixel.
  Traced and touching: 97 % charged; traced but the line misses the river: 2–6 %; line touches a river that does not
  run between them: 12 %; neither: 0.07 %. Together 97.6 % of edges right. A river along the shared border, or
  one that clips a corner, gives no factor unless the centre line crosses it. The game uses the mod's rivers.png
  (vanilla's lines fit worse), so the navigation sea-zone strips do not change it; being split by the river only
  correlates (a river through a location tends to cross its centre line).
- `local_market_access` counts only at the end location; impassable locations are no nodes.
- A location with access 0 to every market keeps the market it had (Lapland, remote lakes; the save omits its access).
- The save keeps access to the current market and to `second_best_market` (the market with the highest access,
  mostly) and `market_parent`, the previous location on the path to the current market; `road_network` holds every
  road. The saved access lags the live value by the `local_market_access` changes since the last tick.
- Fit against the saved access (1338.3.19): rules only 80 % within 0.005, 98 % within 0.05 (65 % / 94 % before
  the river test). Calibrated on the save's path tree (river class of each edge on it, effective harbour of each
  port): 99.1 % within 0.005. The thisted
  tooltip (Oslo 0.833, Lübeck 0.777, Bruges 0.677, Köln 0.669, London 0.634) is reproduced within 0.003.
- Remaining misses: long open-ocean crossings (Greenland–Labrador, Galápagos, Madeira, Palau, Tuvalu: 0.07–0.2 per
  region; the game's open-sea set differs for a few tiles), locations whose live access is capped at 1.

### 3a. Market access in Prosper or Perish (logistics, 2026-09-30)

- The base is `NMarket.MARKET_BASE_ACCESS` (vanilla 1.0, the mod 1.3): access = 1.3 − transport cost +
  `local_market_access`, clamped to 0..1. The measurements and the calibration above (and `worldbuilder/market_access.py`,
  `config/start_markets.csv`) come from saves with base 1.0; re-run `tools/markets/save_inputs.py` on a save made with the
  new base before trusting `food-sim --markets` for high-access locations.
- `unsupported_building_levels` (static modifier, scaled by the building levels above the supported ones) carries
  `local_market_access = -0.01` per level and, since 2026-10-01, `local_logistics_output_modifier = 0.001` per level (a
  nudge for the AI to build logistics where the location is overbuilt). The vanilla foreign buildings (trade office,
  embassy, missionary building, slave center, overseas trading post, colonial administration, merchant guild chapel,
  viceroyalty) carry `raw_modifier free_building_levels = 1`: foreign countries open them with 1 + 0.1 x development +
  0.05 x population levels each (Mantova: 267 foreign levels of 437), and each level now supports itself.
- The logistics buildings add `local_market_access = +0.10` per level through `raw_modifier`, can be built only while
  `market_access < 0.85` and `total_building_levels >= 15` (`allow`), and produce the floor-pinned `logistics` good for
  their wage. Blueprint rule: `ppc logistics apply|check`, `[logistics]` in `constructor.toml`,
  `src/prosper_or_perish_constructor/logistics.py`. Regional variants of the Carrier Inn follow the geography-only
  zones in `pp_logistics_zone_triggers.txt`.
- `raw_modifier` is not scaled by staffing but by input fulfilment: the engine applies it x level x the average over the
  building's production-method slots of each slot's input fulfilment (decompiled FUN_144612a10 / FUN_1443c9470; the save
  stores it per method as `building_manager.database.*.<method>.input`, eu5q table `building_method_inputs`; not stored =
  full). Inputs are bought in proportion to market access, so at access 0 a building demands nothing and its fulfilment
  is 0; `manual_labor` is an input like any other. In run pp_lr_1830, 393 of 1544 logistics buildings (1078 levels) had
  input 0 while fully staffed, so their locations could never recover. A method without goods inputs counts as fully
  supplied. Since 2026-10-01 every logistics building has a network slot (slot 0, one method
  `pp_<building>_logistics_network`, no inputs, 0.30 logistics per level) beside its main slot: at least half the bonus
  (+0.05 per level) always stands.
- Main-slot output (input cost 3.0 per level per method): river 1.40, coastal 1.35, overland 1.30, urban 1.25 x the
  cost, the improved (last, gate) method +0.05. Profit per level at base prices, main slot + network slot: river
  1.20 + 0.30 (improved 1.35 + 0.30), coastal 1.05 + 0.30 (1.20 + 0.30), overland 0.90 + 0.30 (1.05 + 0.30), urban
  0.75 + 0.30 (0.90 + 0.30). The AI's margin gate stays on the main slot's last method (an input-less gate reads a
  margin of output / 0.001 and would never close).
- Employment: logistics buildings are staffed before every other building in every employment system
  (`pp_employment_priority.txt`: river 80M > coastal 70M > city 60M > rural 50M, above education 20M plus the largest
  category bonus 10M).

## 3b. Predicting the market

Access for every location and market + the attraction of section 2 + argmax:

| Test | Locations right | Owned | People |
|---|---|---|---|
| 1338.3.19, calibrated access | 98.6 % | 98.7 % | 98.7 % |
| 1338.3.19, access from the rules only | 98.0 % | 98.1 % | 98.1 % |
| forecast: start save 1337.4.1 -> markets after the first tick (1,030 switches) | 98.7 % | 98.8 % | 99.0 % |
| forecast, rules only | 98.3 % | 98.3 % | 98.9 % |
| forecast one month ahead, 1339.3 -> 1339.4 (52 switches) | 99.4 % | 99.6 % | 99.6 % |

Most misses are near-ties (the runner-up is the true market, often within 0.01): the dump is taken days before the
tick and the drifting terms (development, prestige, control) decide them. Owner/province pools (the food sim's
unit): 3,960 of 4,070 pools right (98 % of the people) after the first tick, against 2,680 (67 %) for the placement's
nearest-centre proxy.

## 4. When locations switch (36 months from 1337.4)

| Cause | Switches |
|---|---|
| attraction shifts (first tick 1,086, then 50-150 a month, 10-50 in year 3) | 3,947 |
| into the 7 markets the AI founded (months 7-8; creation takes 3 months) | 839 |
| conquest (owner change: protection and the owner's language flip) | 7 |
| markets destroyed | 0 |

- 427 locations flip three or more times between two near-equal markets (thisted Lübeck/Oslo 0.889 vs 0.881, Taiwan
  and the Ryukyus, river tiles): a 0.001 edge decides, so small monthly drifts in development, prestige, control and
  language power move them back and forth.
- Protection makes foreign markets lose: 0.5 x control is subtracted from every foreign market, so a location with
  full control needs a foreign market 0.5 more attractive than its own. Low-control border land flips first.

## 5. Where it is in a save

- Location: `market`, `market_access`, `market_attraction`, `second_best_market`, `second_best_market_access`,
  `language`, `control`. Market: `center`, `language`, `members`. `language_manager.power`, `culture_manager`.
- eu5save tables: `locations` (the fields above), `markets.language`, `languages`, `cultures`, `location_variables`
  (the `pp_mk_*` dump: `ltcp`/`gtcp` centre and owner attraction, `ltpf`/`gtpf` protection, `lma` local market
  access, `acc` access).
- eu5save tables also: `roads` (`road_network`), `locations.market_parent`.
- Kit: copy `tools/markets/pp_mk.txt` to `Documents/.../run/`, `run pp_mk.txt` in the console, then `save <name>`.
  `uv run python tools/markets/save_inputs.py SAVE [--pure] [--truth LATER_SAVE] [--csv OUT]` reports the attraction
  fit, the access fit and the predicted market of every location (against SAVE or a later save);
  `--build-cache` rebuilds the map graph (`artifacts/data/markets/`: adjacency, bounding-box centres, traced rivers)
  after a map change.

## 6. In the start-food simulator

`market_assignment = true` in `[worldbuilder.start.food_sim]` (or `ppc worldbuilder food-sim --markets`) puts every
owned province pool into the market the engine picks at the first tick, from `config/start_markets.csv`
(`save_inputs.py START_SAVE --pool-markets config/start_markets.csv`, predicted from `pp_mkt_0d`, 1337.4.1 with the
dump: population majority of the pool's locations). Pools without market access keep the proxy; the placement
(Taverns and Granges per catchment) is not changed. The assignment stays fixed for the run: the sim does not move
the terms that make markets drift (development, prestige, control) and founds no markets.

Effect on the 96-month run (2026-09-27 input, start_markets.csv with the river test): starving pools 262 → 280,
collapsing pools 113 → 124, world population +1.16 % → +1.09 %; the victuals trade now couples the pools the engine
couples.

Centre power rework (2026-09-27; the table in section 2): `start_markets.csv` is re-predicted from `pp_mkt_0d` with
each centre's dumped power rebuilt from its parts (fit: median residual −0.0008; negative residuals are overcounted
building levels and are dropped with that term). First tick: 1,014 locations (15.6M of 380M people) join a different
market than under the old weights, 222 of 4,015 pools change market; near ties within 0.01 of the runner-up fall
from 829 locations (15.2M people) to 525 (8.2M), within 0.001 from 84 to 42. Megalopolis and walled centres lose
(Dadu −3.1M people, Genoa −2.0M, Constantinople −1.6M), unwalled high-development centres gain (Shangyuan +2.7M,
Venice +1.5M, Pest +0.8M). 96-month food sim: starving pools 280 → 287, collapsing 124 → 126, world population
+1.09 % → +1.07 %. Monthly jitter is not measured yet: the monthly saves of the observer run were deleted; the terms
that drove it (building levels, staffing of walls, rank changes) are gone, development now moves twice as much.

## 6b. When markets are founded and dissolved (2026-09-29, confirmed in the engine and in 4 runs)

**The AI founds a market by a fixed rule, not by utility.** Each AI tick for a country (the trade AI), it founds a
market in its capital when all of these hold:

1. The country is not at war.
2. Its rank is kingdom or empire (rank level above 2), or it owns at least 100 locations.
3. The capital's market access is below 0.55. For a subject it must also be below 0.25.
4. The capital passes the normal checks of the `create_market` action:
   - the country owns it;
   - it is not a market centre already;
   - no market construction is under way there;
   - a capital that is not a city (rural settlement) needs market access below 0.25.

Then the country issues `create_market` on its capital. Gold is not checked: one country founded a market with 1.15
gold. The market appears after `MARKET_CREATION_MONTHS` (3). The AI never founds a market anywhere except its
capital.

- **Defines that matter:** only `MARKET_CREATION_MONTHS`. The thresholds 0.55, 0.25 and 100 are hardcoded, not
  defines.
- **Defines that do not steer founding:** the AI market-value defines `MARKET_ACCESS_IMPORTANCE` (0.15),
  `MARKET_TAX_BASE_REFERENCE` (100) and `MARKET_OWNING_IMPORTANCE` (0.0005). The engine uses them only in the script
  values `create_market_utility` / `relocate_market_utility`, which the rule above does not call. Those values show
  in the create-market tooltip under `ai_debug` and in the actions' `ai_will_do`. `MARKET_FLIPPING_IMPORTANCE` is
  not used here either.
- **The value those script values compute:**
  - Formula: (U(assignment after) − U(now)) × d^`MARKET_CREATION_MONTHS`, where d is the country's monthly AI
    discount factor.
  - U sums over all markets: IncomeUtility × [OurTaxBase×Access_m × `MARKET_ACCESS_IMPORTANCE` × Total_m/(Total_m +
    `MARKET_TAX_BASE_REFERENCE`) + (Total_m × `MARKET_OWNING_IMPORTANCE` if the country owns market m's centre)].
  - OurTaxBase×Access_m is the country's raw tax base in market m, weighted by each location's access (clamped to
    0..1). Total_m is market m's raw tax base from all owners.
  - IncomeUtility is the country's value of one more ducat per month.
- **Measured in game (2026-09-29, main mod, observer, 1337.4.1 → 1337.8.1):**
  - Call counters sat on the value calculation and on the founding rule.
  - The founding rule ran once per country per month: 8,613 calls. Countries passed rules 1–3 29 times, and markets
    were founded (Ankober, Soba).
  - The value calculation ran 0 times.
  - One console evaluation of `create_market_utility` ran it at once (control).
  - So in play these three defines have no effect. They only change the number a script or tooltip reads.
- **`destroy_market_utility` is always 0.** It compares the current assignment with an unchanged copy of it.

**Nothing in the AI code dissolves or relocates markets.** `destroy_market`, `relocate_market` and `create_market` all
have `ai_tick = never`. Only script removes markets:

- **Withering, checked monthly by the engine.** A market is withering when:
  - it has at most `MARKET_WITHERING_LOCATION_THRESHOLD` (5) locations;
  - it has stayed at or below that for at least `MARKET_WITHERING_GRACE_MONTHS` (24) months in a row (the counter
    resets as soon as it has more);
  - at least `MARKET_WITHERING_OUTCLASSED_FRACTION` (0.5) of its locations have a second-best market. Any other
    market in reach counts; it does not have to be more attractive.
- **The "AI destroy bias" in the define comment is only the event `market_decline.1`.** It fires from the yearly
  country pulse (0–36 months jitter) once the withering market has been at or below the threshold for more than 36
  months. AI choices:
  - dissolve 70;
  - accept 10;
  - subsidize 30, but only for its capital's market and with at least 1000 gold.
- **Nothing else in the engine reads the withering flag.**
- Colonial new towns found an instant market (`cc_setup_new_town`, when the town's market access ≤ 0). That is the
  source of most non-capital markets in long runs.

**Runs checked:**

| Run | Markets founded | Of which capitals | Destroyed |
|---|---|---|---|
| Lab 1337.5–1340.1, monthly | 7 | 7 | 0 |
| Observer 1340–1437, yearly | 1 | — | 0 |
| 1342–1443, 5-yearly | 5 | — | 0 |
| England 1342–1838, 5-yearly | 70 | 26 (the rest mostly colonial towns and unowned new land) | 0 |

- Every lab founder was a kingdom or empire at start, with capital access 0–0.50. The subjects all had access below
  0.25.
- The observer run's countries that met rules 1–3 but never founded (BNL, HSL, CHI, cholistan) all have rural
  capitals with access 0.26–0.52, which rule 4 blocks.
- War status is not in the dataset, so rule 1 is checked only in the engine.

**Levers for the mod:**
- The founding rule cannot be tuned by defines.
- It reacts to capital market access (roads, harbours, `local_market_access`), to whether the capital is a city,
  and to country rank.
- Destruction reacts only to the withering defines and the event's `ai_chance`.

## 8. Trade between markets and the reaction to shortages (2026-10-01, measured in saves and test runs)

How the AI trades goods between markets, how trade feeds back into prices, and what the raw-material balance of
2026-10-01 changed. Rule for this balance: no global output or capacity buff; the AI has to answer a shortage by
building supply and by trading from producers that can export.

**Capacity.** A country trades from a market with the merchant capacity it has in that market (market centres, market and
trade buildings, `global_merchant_capacity_modifier`). One traded unit of any good uses one unit of capacity, whatever the
good's value, transport cost or the distance (the save's `merchant.used` equals the sum of the trade sizes). The world has
~2,800-3,000 capacity, 98 % of it in use, against ~50,000 units of raw output a month; capacity does not grow with the
economy. Burghers trade on their own besides (burgher trading: the burghers of a town buy what their market lacks); in 1387
they moved more raw goods than the countries (1,934 against 1,366 units a month).

**Profit per unit** = destination price x (1 + the trader's selling efficiency) - source price (divided by the market
owner's modifier when the trader is not the owner, never below half) - a distance cost - `NCountry.MERCHANT_MAINTENANCE_COST`
per unit (flat, 0.25). Trades below `AI_PERFORMANCE_TRADE_PROFIT_PER_WEIGHT_CUTOFF` profit per transport weight are skipped,
except imports that cover a pop shortage or a building input: they score a bonus per unit (`AI_IMPORT_POP_NEED_SCORE_BONUS`,
`AI_IMPORT_INPUT_GOODS_SCORE_BONUS`) and may run at a loss of up to `AI_WELFARE_IMPORT_PROFIT_CUTOFF` (-1 gold) per unit.
Exporting what local pops lack is penalised (`AI_EXPORT_POP_SHORTAGE_PENALTY`).

**What a market can export** = its surplus (supply - demand) plus a share of its stockpile: a stockpile fuller than half of
its cap releases up to 5 % of its stock a month (full rate at 75 % fill). In PP stockpiles sit at their cap (10 per
development point).

**Price.** Target price = base price x (D + c S) / (S + c D), clamped to 0.2-3x, with c = 0.2 (fitted on 6,867 market-goods
of a 1387 save) and S, D the supply and demand plus `SUPPLY_AND_DEMAND_STABILITY_OFFSET_CONSTANT`; the price moves
`MONTHLY_PRICE_CHANGE` of the way to the target each month. Trade enters S and D only in part: imports count
`TRADE_IMPACT_ON_SUPPLY_SCALE` (0.75) of country trades and `BURGHER_TRADE_IMPACT_ON_SUPPLY_SCALE` (0.1) of burgher trades;
exports count `TRADE_IMPACT_ON_DEMAND_SCALE` and `BURGHER_TRADE_IMPACT_ON_DEMAND_SCALE` (vanilla 0.75 and 0.25; a country
modifier `export_impact_on_demand` scales them, capped at 1). A stockpile drawn down for export does not count as supply
(`STOCKPILE_TRADE_IMPACT_ON_SUPPLY_SCALE` 0). At vanilla values an exporter's price saw a quarter of its burgher exports, so a
neighbour's shortage barely reached its producers: their price stayed near the local balance and their buildings
(production gate at 1.05) were not built for export.

**The AI's building utility** has its own shortage terms besides the price inside the profit: "Missing pop need" (pops'
missing amount of the good, at most the building's output, x `POP_MISSING_GOODS_UTILITY_FACTOR`), "Producing input goods
shortage" (`INPUT_GOODS_SHORTAGE_UTILITY_FACTOR`) and "Export profit" (goods the country exports at a profit from that
market with no surplus left, x profit per unit x `PROFITABLE_EXPORT_GOODS_UTILITY_FACTOR`; with surplus it falls to
`PROFITABLE_EXPORT_GOODS_REDUCE_PRICE_UTILITY_FACTOR` over `AI_EXPORT_GOODS_SURPLUS_GRADIENT_CAP`). All need profitability
above `AI_PROFITABILITY_THRESHOLD_FOR_MISSING_GOODS_UTIL` (PP 1.01). At vanilla factors they were 0.03-0.06 % of all utility
terms in a logged month (cost 35 %, modifiers 40 %, profit 20 %).

**RGOs** hardly grow (most raw goods have `block_rgo_upgrade`): the supply answer to a shortage is buildings, steered by the
production gate leg (section 2.4i of the AI building rulebook), profit and the shortage terms above.

**Balance 2026-10-01** (`pp_defines_adjustments.txt`, `pp_goods_adjustments.txt`):

- `TRADE_IMPACT_ON_DEMAND_SCALE` 0.75 -> 1.0, `BURGHER_TRADE_IMPACT_ON_DEMAND_SCALE` 0.25 -> 1.0: exports count fully in the
  exporter's price.
- `POP_MISSING_GOODS_UTILITY_FACTOR` 0.02 -> 0.1, `INPUT_GOODS_SHORTAGE_UTILITY_FACTOR` 0.02 -> 0.1,
  `PROFITABLE_EXPORT_GOODS_UTILITY_FACTOR` 0.5 -> 1.0.
- `AI_IMPORT_POP_NEED_SCORE_BONUS` 5 -> 10; transport cost of fruit, legumes and horses 2 -> 1.5.
- Long run (8b): `TRADE_IMPACT_ON_SUPPLY_SCALE` 0.75 -> 1.0 and `BURGHER_TRADE_IMPACT_ON_SUPPLY_SCALE` 0.1 -> 1.0
  (imports count fully in the importer's price); `POP_MISSING_GOODS_UTILITY_FACTOR` 0.1 -> 0.25.
- Tested and dropped: +150 % merchant capacity for every country, RGO bonus 0.30 / 0.10 for deficit / glut goods (global
  output and capacity buffs), `MERCHANT_MAINTENANCE_COST` 0.10 and profit/weight cutoff 0.15 (the vanilla values did better
  with the shortage terms: cheap trade let low-margin arbitrage keep the capacity). Never put `local_merchant_capacity` into
  the development static modifier: the AI's valuation of development then crashes the game.
- EU5 1.4 (not yet tested in a run): imports that only cover a pop shortage got their own loss limit
  (`AI_POP_NEED_IMPORT_PROFIT_CUTOFF`, vanilla -0.1); PP keeps -1.0, the 1.3 limit the runs above were measured with.
  The new food trade rules (trade orders' food mode, burgher food trade) read the market food stock as a share of
  market food capacity; PP markets hold none, so the share is 0 everywhere and the thresholds are set so it never holds
  food trade back (`TRADE_ORDER_FOOD_GROWTH/MAINTAIN_STOCKPILE_FRACTION` 1.0, `TRADE_ORDER_FOOD_EXPORT_SELF_STOP/CANCEL_FRACTION`
  and `MARKET_MIN_FOOD_STOCKPILE_RATIO_FOR_BURGHER_TRADE` 0). Those rules only apply to goods with a food value, and PP
  gives every good food = 0. The rest of the trade-order system, trade policies, tariffs and subsidies stay vanilla.

Test runs (fresh game to 1387, then 10 years from the same save; v8 = the list above, continued to 1407; b0 = no change):

| | b0 1397 | v6 1397 (export impact only) | v8 1397 | b0 1407 | v8 1407 |
|---|---|---|---|---|---|
| raw output (units/month) | 53,868 | 54,732 | 56,186 | 57,626 | 57,307 |
| RGO workers vs b0 | | | +0.1 % | | |
| merchant capacity | 2,875 | 2,933 | 2,968 | 2,946 | 2,930 |
| raw goods traded (units/month) | 2,091 | 2,228 | 2,346 | 2,303 | 2,309 |
| raw market-goods at >= 1.5x | 178 | 173 | 144 | 171 | 168 |
| raw market-goods at >= 2x | 63 | 51 | 50 | 45 | 51 |
| pops' unmet raw demand (gold) | 3,032 | 3,009 | 2,141 | 3,047 | 2,465 |
| producer levels built where the good was >= 1.5x (from 1387) | 199 | 169 | 313 | 414 | 601 |
| producer levels built where it was 1.05-1.5x | 898 | 961 | 1,152 | 1,987 | 2,319 |
| producer levels built where it was 0.8-1.05x | 983 | 884 | 732 | 1,860 | 1,641 |
| exporting market-goods: median price | 0.85x | 0.95x | 0.96x | 0.85x | 0.96x |
| starving provinces | 531 | 542 | 520 | 599 | 619 |
| population (k) | 341,354 | 337,352 | 341,359 | 353,721 | 351,619 |
| countries' gold (k) | 519 | 518 | 504 | 523 | 481 |

Unmet pop demand 1407 (b0 -> v8): millet 204 -> 68, wheat 280 -> 142, fruit 167 -> 108, horses 168 -> 132, wine 38 -> 26;
tea 90 -> 102 and saffron 23 -> 28 did not improve. RGO output swings by good between branches (rice +30 %, wine -22 % in
v8 1397) come from Seasonal Harvest rolls, not from the balance: RGO workers are the same.

Case studies. Lumber around Stockholm: lumber is a world glut (production 1.65x local demand, every market below 1x), so
Sweden has no short neighbour to export to and exports nothing; that is right. Tea: a world deficit (production 0.74-0.84x
local demand); the Chinese and Japanese tea markets export to their short neighbours and their price rose from 0.75-1.04x
to 1.0-1.19x, but tea gardens (and saffron crofts, amber collectors) can only be built on locations whose RGO is that good
and share farmland with every other farm, so tea supply stayed capped (71 garden levels against 76 in b0). India's tea
shortage (2.3-3x) is out of reach of the producers' trade.

## 8b. Long run 1407-1830: do specialist raw-material markets form? (2026-10-01)

One observer game from the 1407 save of section 8, checked every 20 years with two yearly saves (Seasonal Harvests move
farmed RGO output by +-15 % between runs and years, so a single snapshot misleads), until 1830.

**Measures** (raw goods, values at base price): trade share = exports (country + burgher trades) / production; the
production/consumption gap of a market = half the sum over goods of |share of its production - share of its own
demand|, weighted by production (0 = every market makes what it uses); exporting market-goods = exporting >= 2 units and
>= 10 % of production; specialist markets = exporting >= 10 % of their raw production value; neighbour pairs = a market
>= 1.5x short of a good next to a market <= 0.9x with a surplus of it.

**Why markets were alike.** From 1337 to 1407 raw trade fell from 18.7 % to 9.8 % of output and the gap from 0.40 to
0.24. An importer's price counted 75 % of country-trade and 10 % of burgher-trade imports: burghers
covered the shortage, the price still showed it, and the importer built its own copy of the supply.

**Changes.**
- 1407: imports count fully in the importer's price (`TRADE_IMPACT_ON_SUPPLY_SCALE`, `BURGHER_TRADE_IMPACT_ON_SUPPLY_SCALE`
  1.0). A/B over 20 years (1428, matched harvest): trade share 10.3 -> 13.2 %, exporting market-goods 420 -> 566,
  short market-goods 173 -> 83, starving provinces 623 -> 535, population 361M -> 374M, pops' unmet demand +13 %.
  Control from 1688 with the vanilla scales: by 1708 trade share 14.8-15.7 % against 19.9-20.2 %, gap 0.24 against
  0.27, short market-goods 552-563 against 360-408, starving provinces and population the same.
- 1528: `POP_MISSING_GOODS_UTILITY_FACTOR` 0.25: staples were short world-wide while RGOs stay fixed; the AI built more
  staple farms (wheat +221, millet +137, rice +61 levels against the control by 1548), trade unchanged.

| year | trade share | gap | exporting mg | specialist markets | short mg | merchant capacity | population | starving |
|---|---|---|---|---|---|---|---|---|
| 1337 | 18.7 % | 0.40 | 442 | 88 | 469 | 3,146 | 355M | 594 |
| 1407 | 9.8 % | 0.24 | 383 | 60 | 168 | 2,930 | 352M | 619 |
| 1428 | 13.2 % | 0.24 | 566 | 75 | 83 | 2,984 | 374M | 535 |
| 1508 | 15.3 % | 0.23 | 650 | 90 | 120 | 3,591 | 451M | 714 |
| 1588 | 17.4 % | 0.24 | 795 | 97 | 187 | 4,549 | 464M | 749 |
| 1668 | 18.7 % | 0.27 | 898 | 106 | 370 | 6,001 | 540M | 1,263 |
| 1708 | 19.9 % | 0.27 | 1,025 | 110 | 360 | 6,894 | 519M | 1,131 |
| 1748 | 20.6 % | 0.26 | 1,205 | 118 | 357 | 8,016 | 583M | 943 |
| 1788 | 22.0 % | 0.26 | 1,290 | 130 | 432 | 9,632 | 662M | 1,023 |
| 1830 | 22.1 % | 0.25 | 1,399 | 134 | 434 | 11,518 | 702M | 853 |

Merchant capacity grew by itself (market and trade buildings, burghers) from ~3,000 to ~11,500. Specialists that formed:
Riga, Krakow, Stockholm and Venice lumber; Lubeck herring; London wool; Paris wheat, wine and horses; Krakow wine and
salt; Prague, Pest, Tarnovo, Sofala and Niani gold; Malabar (Kozhikode, Pazhaverkadu, Vijayanagar) pepper; Khambat and
Kataka iron; Delhi and Kataka cotton; Shangyuan wheat, rice and livestock; Kyoto, Chittagong, Thang Long and Hangzhou tea;
Ternate, Trowulan and Berune cloves; Jinjiang and Alexandria sugar; Benin cocoa; Varanasi ivory. Short market-goods with a cheap
neighbour holding a surplus: 10 in the control at 1428, 0-4 from 1428 to 1628, 9 at 1830.

**What stays short is supply, not trade.** At every check-in 60-90 % of the short market-goods were goods short
world-wide; goods in world surplus that failed to arrive were 20-64 market-goods. World-short in turn: staples 1528-1668
(wheat 0.69-0.88 of demand in bad years; RGOs fixed by `block_rgo_upgrade`, wheat farm levels grew 6 %, 2 % and 3 % in the
40-year steps after 1528 while building demand for wheat rose 48 % 1528-1608 (cookshops, horse breeders); Europe's
staple farms fell from 13,072 to 10,503 levels 1528-1667, mostly bankruptcy cuts and sacks); then the goods that can
only be grown on their own RGO locations or spread late: tea 0.57-0.84, cocoa 0.50-0.74, amber 0.31-0.53, potato
0.53-0.98. Starving provinces ran 21 % / 23 % / 27 % in markets importing < 10 % / 10-20 % / >= 20 % of their raw demand
(1687), and the vanilla control had the same count.

## 8c. Tariffs and subventions (EU5 1.4 beta, 2026-10-01, engine-confirmed and checked in a 1.4 PP run)

**What a rate is.** A market owner sets one import rate and one export rate per good for all its markets; > 0 is a
tariff, < 0 a subvention. Every use clamps the rate to `max_tariff` and `max_trade_subventions`, both capped at 100 %.
Base values are 20 % each (auto modifier `country_base_values`), raised by advances, laws, reforms, parliament issues,
societal values, estate privileges and subject types.

**What a rate does.**
- Trade profit: a trade pays the destination owner's import rate x amount x destination price and the source owner's
  export rate x amount x source price.
  - This applies only to foreign merchants trading with a foreign market.
  - A tariff exemption (the `tariff_exemption` relation, subject keys) removes tariffs but keeps subventions.
  - The owner gets the same amount as income, and pays it when the rate is negative.
- Price: only the import rate moves the price. The target multiplier gets + import rate x `NMarket.TARIFF_PRICE_IMPACT`
  (0.25) x (1 + `tariff_impact_on_price`).
  - This is added after the 0.2-3x clamp.
  - A 20 % import tariff raises the target by 5 % of the base price.
  - Export rates have no price effect.
- Income: `tariff_income` (base 10 %, plus the crown's power share) goes to the treasury; the rest is split among the
  estates like trade income. `NEconomy.ECONOMICAL_BASE_FROM_TARIFF` adds 0.2 x tariff income to the economic base.
- Opinion: `opinion_import_tariff` -250, `opinion_export_tariff` -150 and the subvention bonuses towards the countries
  whose merchants are hit.

**When the AI sets them.** The country AI recomputes the policy for every good on each run of its economy tick, for
every country that owns at least one market. It sets **export rates only**: no AI ever sets an import tariff or any
subvention.
1. Ratio = 12 x domestic demand of its markets (demand minus exports) / the smallest exportable amount among its
   markets. The ratio is 0 when any of its markets has nothing of the good to export.
2. Plus `TRADE_POLICY_AUTO_WARTIME_FOOD_EXPORT_TARIFF` (0.40) for a food good while at war.
3. Otherwise, plus `TRADE_POLICY_SUBSIDY_LIGHT` (-0.10) when its export value (export volume x base price) is at least
   `TRADE_POLICY_AUTO_EXPORT_VALUE_THRESHOLD` (15).
4. Times the strategy factor: Mercantilist 1.25, Balanced 1.0, Free Trade 0.5. Every AI country is Balanced.
5. Floored at 0, then capped by `max_tariff`.
6. The rate changes only when the new value differs from the current one by at least `TRADE_POLICY_AUTO_HYSTERESIS`
   (0.05).

So a country taxes the exports of the goods it uses itself, at the cap. A big exporter of a good gets 0.10 off.

**Defines the 1.4 beta does not read.** `TRADE_POLICY_TARIFF_LIGHT/MODERATE/HEAVY`, `TRADE_POLICY_SUBSIDY_MODERATE`,
`TRADE_POLICY_AUTO_IMPORT_VALUE_THRESHOLD`, `TRADE_POLICY_AUTO_WARTIME_FOOD_SUBSIDY`, `TRADE_POLICY_AUTO_MARGIN_SAFETY`
and `TRADE_POLICY_EMBARGO_LIMIT_BASE`. `TRADE_POLICY_SUBSIDY_HEAVY` is not even a known define. The import side of the
automation (and the player's "Tariffs" automation) is apparently not wired up yet in this build.

**In PP (Jan's 1.4 run, save 1387.4.1):**
- 155 market owners had 7,063 export tariffs, no import tariffs and no negative rate.
- 62 % sat exactly at the 20 % base cap, 7 % above it (up to 45 %), and the rest below.
- Tariff income was 79 gold a month world-wide.
- The most taxed goods were lumber, `manual_labor`, clay, pottery, fish, `offset` and tools; the dummy goods are taxed
  like any other.
- For the raw-material trade of section 8 this is a cost on every foreign merchant's export. At 20 % of the source
  price it is more than the median profit per unit of wheat (0.08) or fruit (0.02) trades measured in 1.3.

**Levers (not applied).**
- `TRADE_POLICY_SUBSIDY_LIGHT` very negative together with `TRADE_POLICY_AUTO_EXPORT_VALUE_THRESHOLD` 0 turns the AI's
  export tariffs off. Set `TRADE_POLICY_AUTO_WARTIME_FOOD_EXPORT_TARIFF` to 0 as well; it is moot in PP because its food
  goods have food 0.
- Lowering `max_tariff` in `country_base_values` caps them, but advances and laws add their own `max_tariff`.
- The price effect matters only for player-set import rates.

## 7. Open

- Treaty flows (per country pair) and the Paris constant (+0.1) in the attraction.
- Access: river edges the tracer misses (12 % of lines touching an untraced river are charged) and the direction of
  rivers traced both ways; open-sea tiles on a few ocean crossings; the 0.4 in K.
- Monthly drift inside the food sim (market switches after the first tick, founded markets) is not modelled.
