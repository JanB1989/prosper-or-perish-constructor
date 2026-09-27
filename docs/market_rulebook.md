# EU5 market membership rulebook

Verified 2026-09-27 on EU5 1.3.11 with Prosper or Perish (Jan's playset: main mod, Community Mod Framework, Faster
Universalis), in a 36-month observer run from 1337.4.1: one save per `tick_day 15` (~29.4 days, `pp_mkt_m01..m36`),
the per-location dump `tools/markets/pp_mk.txt` from month 12 on and at the start, and the in-game market tooltip.
Code: `src/prosper_or_perish_constructor/worldbuilder/markets.py` (rules), `tools/markets/` (kit),
`food_sim.py` (`market_assignment = true`).

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
| market attraction of the centre | `local_trade_center_power` of the centre location | development x 0.001 (mod; vanilla 0.002), building levels x 0.0004 (mod; vanilla 0.0005), rank (city 0.025, megalopolis 0.05), market buildings 0.1 x level, walls 0.1, good natural harbour 0.01, Global Trade birthplace 0.1, uniques |
| attraction of the owner | `global_trade_center_power` of M's owner | prestige 0.05 x prestige/100, advances, privileges (the mod removed the trade_vs_tax line) |
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

## 7. Open

- Treaty flows (per country pair) and the Paris constant (+0.1) in the attraction.
- Access: river edges the tracer misses (12 % of lines touching an untraced river are charged) and the direction of
  rivers traced both ways; open-sea tiles on a few ocean crossings; the 0.4 in K.
- Monthly drift inside the food sim (market switches after the first tick, founded markets) is not modelled.
