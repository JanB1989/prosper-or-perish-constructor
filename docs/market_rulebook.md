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
- `unsupported_building_levels` (static modifier, scaled by the building levels above the supported ones) carries only
  `local_market_access = -0.01` per level.
- The logistics buildings add `local_market_access = +0.10` per level through `raw_modifier` (not scaled by staffing), can
  be built only while `market_access < 0.85` and `total_building_levels >= 15` (`allow`), and produce the floor-pinned
  `logistics` good for their wage. Blueprint rule: `ppc logistics apply|check`, `[logistics]` in `constructor.toml`,
  `src/prosper_or_perish_constructor/logistics.py`. Regional variants of the Carrier Inn follow the geography-only
  zones in `pp_logistics_zone_triggers.txt`.

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

## 7. Open

- Treaty flows (per country pair) and the Paris constant (+0.1) in the attraction.
- Access: river edges the tracer misses (12 % of lines touching an untraced river are charged) and the direction of
  rivers traced both ways; open-sea tiles on a few ocean crossings; the 0.4 in K.
- Monthly drift inside the food sim (market switches after the first tick, founded markets) is not modelled.
