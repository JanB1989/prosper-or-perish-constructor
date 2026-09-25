# Starting buildings, food and victuals logistics

The constructor generates starting buildings and population conversions during
`uv run ppc worldbuilder apply` and `uv run ppc build`. No monthly placement
script or savegame correction is required. Start a new campaign after rebuilding.

## Inputs and order

`worldbuilder/start_simulation.py` reads merged building definitions, accepted
blueprints, script values, ranks, native river modifiers, World Builder attributes
and navigation states. It uses the development that the constructor actually
writes, not the separate World Builder fitting target. Food transfer, employment,
food consumption, footprints and the subsistence define come from game data.

The engine changes the world between the setup files and the first tick, and the
budget models that state rather than the files:

- **Setup promotion.** The vanilla pops file is almost all peasants; at tick 0
  the game promotes millions of them into nobles, clergy, burghers, laborers and
  soldiers (nobles eat 25 food per 1,000, peasants 1). Per location the promoted
  amount is `const + per 1,000 pops x pop + per development point x development`
  (`[worldbuilder.start.engine_promotion_linear]`, fitted on the day-0 save
  `nb.eu5`); the per-1,000 shares in `[worldbuilder.start.engine_promotion]` are
  the fallback (megalopolis). The laborers follow the RGO's desired workers, not
  the population: the old per-1,000 share (107 per 1,000) gave a 300k Chinese
  location 32k laborers where the engine makes about 10k, i.e. ~200k too many
  non-farming mouths in the dense provinces. `ppc worldbuilder food-check`
  refits both. Worker conversions the planner writes into `06_pops.txt` count
  only where they exceed the promotion.
- **RGO hiring.** The location's RGO employs `[worldbuilder.start.rgo_workers_k]`
  thousand peasants who leave subsistence agriculture.
- **Province pools are per province and owner** in the engine, which is what
  the budget groups.

1. Expand vanilla town presets and include explicit setup buildings, including
   foreign-owned religious buildings. Preserve their ownership and other setup
   metadata. Add the World Builder's initial improvement buildings.
2. Reduce existing levels until every evaluated location cap is satisfied.
   Re-evaluate shared capacity after each placement. Unknown cap or gate syntax
   stops generation instead of silently granting space.
3. Reserve available workers for existing buildings. Place configured resource
   processors, appropriate farms, fishing villages and forest villages where
   their live gates, caps, available workers and land permit them. Fruit and
   wool RGOs get an orchard or sheep farm; every other farmable location
   (farmable RGO or farmland) spreads its farm levels over the crop farms
   (see *Crop farms at game start*).
4. Per market (the nearest starting market centre within the region), run the
   food chain v2 (see *Placement v2*): Cookshops where the market's raw goods
   allow, Taverns sized to each deficit pool's remaining need at its province
   capital, Victualling Yards in surplus pools (well-connected first) until the
   market's victuals cover the Taverns, and further Cookshops where the market
   cannot. Every city and megalopolis additionally receives at least one Tavern
   (not in a province with a Victualling Yard). Only the permitted share of local
   peasants becomes laborers, preserving culture, religion and total population.
   Nobles are never fabricated for Taverns or Yards: the engine's setup promotion
   supplies them.
5. Per market, place lumber, masonry and tools producers where the market's
   supply falls short of the construction it will need (see *Construction
   materials*).
6. Audit all placed building levels, export the budget, run the validator
   (see *Validator*) and write the reports.

## Crop farms at game start

The farming village is split into eight crop farms (`wheat_farm`, `rice_farm`,
`millet_farm`, `maize_farm`, `legume_farm`, `potato_farm`, `olive_farm`,
`cattle_farm`). A crop location keeps the farm-level budget the single farming
village had (`max_farm_levels_per_location`, 6). `Simulation` spreads it with
`worldbuilder/crop_allocation.py` (`[worldbuilder.start.crops]`):

- only goods **available** there count: rice, maize, potato and olives only in
  their native sub-continents or regions (the same gates as the crop-farm
  advances), and only goods whose tier-0 farm passes its live cap
  (rank, `location_potential`, `allow`, `max_levels`) right now;
- livestock takes `round(g x levels)`, `g` the location's grazing share,
  clipped to `livestock_share_min..max`; the crops share the rest by their World
  Builder output rows, the RGO crop with a bonus;
- the levels are then placed farm by farm (most planned levels first), one level
  at a time through the ordinary checks (cap, workers, shared land, pops within
  capacity). Levels a farm refuses go to the RGO crop's farm, else to the
  heaviest other candidate, livestock last and at most one level beyond its
  planned share (a herd level takes 2 land against 5, so it would otherwise soak
  up every refused level); what no farm takes is not placed (rejection
  `crop farms: no room`). Placing stops once no peasant is left to staff a
  level. A location never gets more than the budget.

`start_placement.json` reports `crop_levels_total`, `crop_levels_by_good` and a
`crops` block (planned and placed levels, levels per farm, livestock share);
`start_placement.csv` has the planned/placed levels and one `<farm>_levels`
column per farm; `artifacts/data/worldbuilder/crop_allocation.csv` lists per
crop location and good the availability, weight, planned and placed levels.

## Food model v2

`worldbuilder/start_food_model_v2.py`, `[worldbuilder.start.food_model]`. Fitted
on the day-0 save of a fresh campaign (`nb.eu5`, 1337.4.1, 4,018 province/owner
pools; production = `base_food_consumption + cached_structural_food_change`):

- **Subsistence** = define `NLocation.SUBSISTENCE_AGRICULTURE` (1.5) x (1 + the
  location's static `local_monthly_food_modifier` stack) x `yield_rank` x
  `yield_climate`, per 1,000 jobless **peasants and slaves**. The stack is read
  from the files the game uses (rank, climate/vegetation/topography classes,
  the setup's fertility/soil/coast/lake/river modifiers); in the mod it nets to
  zero almost everywhere, because the World Builder class rows cancel the vanilla
  values and the rank injects cancel vanilla's. Jobless **laborers produce
  nothing** (fitted coefficient -0.03): the ~40 M setup laborers eat without
  farming. Pops in jobs (buildings, the RGO) do not farm.
- **Overpopulation** (the mod's `overpopulation` modifier, scaled by
  pop / capacity - 1) adds `local_peasants_food_consumption +0.5` per unit
  (fitted -0.47..-0.51). `base_food_consumption` leaves it out; the structural
  change carries it. This, not the land, is what made deserts and very-low-
  fertility land look barren in the pre-plague analysis (desert 0.24 food per
  jobless worker before the term, 1.39 after).
- **Building food** per staffed level: `local_monthly_food` (scaled by the
  stack) plus the Province Food good of the Provisioning method (farms, fishing
  and forest villages, orchards). Cookshops (and Public Kitchens) serve every
  dish as Province Food since 2026-09-25 (`cookshop_serve_share` 1, no Preserve
  recipes) plus `cookshop_drink_food` (12, an estimate: about 0.4 of the 0.67
  victuals the old drink and packing slots made per level on `nb.eu5`, x30) from
  the drink slot, on top of their flat `local_monthly_food`. Taverns add +60,
  Victualling Yards -60 per staffed level.
- **Day 0**: no farm runs Provisioning and no cookshop Serve yet (see *Day-0
  stores*), so `day0_production` leaves the Province Food out.

Per pool the budget reports `demand` (pops' food plus overpopulation), `R` =
(subsistence + building food) / demand without trade, `structural_balance`,
`food_capacity` and `capacity_months`.

| Fit on `nb.eu5` | R² per pool | aggregate |
| --- | ---: | ---: |
| v2 formula on the save's own pops, jobs and running methods (configured yields) | 0.989 | +0.9 % (437.0k vs 433.2k) |
| same, plain define 1.5 and overpopulation only | 0.985 | -1.7 % |
| the plan that produced `nb.eu5`, day-0 methods, linear promotion | 0.971 | +1.5 % (439.6k) |
| the same plan, per-1,000 promotion | 0.982 | -1.9 % |
| old model (v1) on that plan | 0.936 | +28.6 % (556.9k) |

Demand of the plan against the engine: R² 0.995 (linear promotion; 0.987
before). The model now finds 2,847 pools short on day 0 against the engine's
2,687 (v1: 680).

Yield factors (food per 1,000 jobless worker = 1.5 x rank x climate): rural
1.56, town 1.53, city 1.46, megalopolis 1.39; climates with at least 500k
jobless workers range from arctic 0.43, highland monsoon 0.64, cold steppe 0.84,
continental monsoon 0.89 to subtropical monsoon 1.08 (the cold ones carry the
April winter consumption of the reference save). The province food capacity is
fitted as 32 per development point + 3.65 per 1,000 pops + 100 per location +
rank (town 521, city 815, megalopolis 1,241), R² 0.968; buildings add their
`local_food_capacity` (a Victualling Yard level 1,200).

## Placement v2

`start_simulation.place_food_chain`, per market:

1. **Cookshops** in pools that fall short of `demand x food_target_ratio`, as
   far as the market's raw food goods allow: `serve_raw_goods_share` (0.2) of its
   RGOs' output of the Serve inputs (1.5 goods per 1,000 RGO workers) divided by
   the goods one level uses (2.07). A Cookshop feeds only its own province, so the
   levels go one at a time to the pool whose remaining need is the largest share
   of its demand (the market's crops are spread over its short provinces instead
   of filling the largest one).
2. **Taverns** sized to each pool's remaining need / 60, at the province capital
   (the pool's highest-ranked location, a market centre first, then the most
   populous; the engine's province capital is not in the setup files), then at its
   other locations; caps (`tavern_max_level`), nobles and the no-Yard rule apply.
3. **Victuals balance.** Every Tavern must be backed by the market's victuals:
   configured producers and **Victualling Yards** in surplus pools (own food above
   +25 % of demand, a store that can reach the Yard's 20-month band, no Tavern in
   the province; a level once the spare food beyond the reserve fills
   `yard_min_level_share` (0.3) of its 60 food, since the engine staffs levels
   partly; cap `victualling_yard_max_level`), until supply >= demand x
   `victuals_target` (1.1). Well-connected pools come first: surplus x the pool's
   best Yard cap, which rewards rivers, coasts, harbours and market centres. A Yard
   packs its pool's surplus / 40 food per victual, at most 1.5 per level (loose
   stores). Demand is the pops' victuals and what the Taverns will actually buy: a
   Tavern only runs while its pool is short (its storage leg stops paying above 12
   months), so it buys its pool's gap / 30 food per victual, at most 2 per level.
   Cookshops make no victuals.
4. Pools that would otherwise collapse (fed below `import_priority_coverage`,
   0.85) get the market's victuals first, cheapest first; the rest by coverage.
5. What the victuals cannot cover goes to further Cookshops
   (`serve_fallback_raw_goods_share`, 0.5 of the raw goods); steps 2-5 repeat
   until nothing more can be placed.

`start_placement.json` has per market (`victuals.catchments`) the deficit, raw
goods, Cookshops, wanted/placed Taverns and Yards, the unmet food and the
victuals supply, demand and cover.

## Day-0 stores

The setup files have no province food or stockpile field. The engine fills every
province store to its capacity when the setup loads, then the mod's
`on_game_start` action `pp_set_starting_province_food` lowers it to the game
rule's share (default `pp_starting_province_food_010`: 10 % of capacity, 1.5 to
12.9 months of consumption, median ~3.7). The farms' methods are chosen against
the full store first, so **every farm starts on Sell for the first month**; they
switch once the store reads low.
A months-based start (for example 6 months) is not possible in script: there is
no trigger or value for a province's food consumption (only `province_food`,
`province_max_food` and `province_monthly_food_production`). The validator shows
what a 6-month start would change: collapsing food pools unchanged (99 on the
third iteration's placement), world +1.0 point; 12 months: 64 pools, +2.0 points.

## Construction materials

Every build the AI queues early stalls in a market without lumber, masonry or
tools (233 of 1,567 AI-queued Victuallers, now Taverns, in the pre-plague run never finished;
`victuals_trade_construction`: lumber 0.25, masonry 0.1, tools 0.1 for 365
days). `start_simulation.place_construction_materials`,
`[worldbuilder.start.construction_materials]`:

- supply per market = its producers' levels x output per level as `nb.eu5`'s
  markets show it (lumber mill 0.70, mason 0.49, tools guild 0.18, market
  village 0.144) plus, for lumber, its lumber RGOs (1.16 each);
- expected construction demand = `margin` (2) x the construction demand per
  million pops the same campaign had in 1341 (lumber 0.61, masonry 0.77, tools
  0.18; `nb.eu5` itself has none on day 0) + the construction of the Taverns
  the placement still wanted but could not place;
- short markets (those with no supply first) get lumber mills, masons, tools
  guilds (then market villages) through the ordinary checks; a market that makes
  none of a good's inputs (masonry: stone or clay; tools: iron, stone or copper)
  gets none and is reported under `no_inputs`.

`start_placement.json` -> `construction_materials` reports per good the markets
short or without supply before and after, the levels added and the supply.

## Validator

`worldbuilder/food_sim.py`: `ppc worldbuilder food-sim [--months N]` reruns it on
the last apply's `artifacts/data/worldbuilder/food_sim/input.csv`; `ppc build`
prints its summary (a report, never a failure). It runs the population loop of
`tools/province_food_sim.py --depop`, calibrated on the pre-plague saves
(1337.4 / 1341.3 / 1345.3), for every pool at once for 96 months from the planned
start: jobs = jobs0 x (N/N0)^0.5, jobless peasants and slaves x yield,
consumption falls 0.4 x the lost share (upper classes leave first) plus the
overpopulation term, farms on Provisioning from month 6 while the store is below
~11 months, Cookshops serving from month 1, Taverns and Victualling Yards staffing
by the sign of their profit per level at a victuals price of 2.7 (the Tavern pays
below 12 stored months, the Yard above 20; each moves 60 food), Taverns limited by
their market's victuals (the Yards' 1.5 per staffed level and other producers), a
starving pool losing its Tavern's noble at 0.09 a year, a yearly
seeded harvest roll (peasant consumption +0.30..-0.30), growth -0.0048 + 0.0086
x stored years (starving: -0.056). Tribesmen (engine rules verified 2026-09-25):
the food of their pop type (-1 per 1k: they feed the province) enters the
province consumption, every pop gets +0.012 x the tribal share, tribesmen are
born at the positive location growth x the free-land factor 1 - 0.75 x pop /
capacity and lose negative growth unscaled like everyone; a province with zero
or negative consumption gets no storage growth bonus. It reports the
pools that lose >= 25 % (food pools: tribesmen < 50 %), the pools pinned at the
storage cap (24 months or full) for more than 48 months, the world population
change, and one CSV row per pool (`pools.csv`).

Checked on the plan that produced `nb.eu5` against the same pools observed in
1345: food pools' population -1.7 % (observed -2.1 %), 164 of the matched food
pools lose >= 25 % (observed 216), per-pool correlation 0.15 (the observed
losses also depend on wars, AI builds and harvests the loop does not know).
It is a validator for placement rules, not a forecast.

## Report and current result

Open `artifacts/data/worldbuilder/food_simulation/index.html` after a build.
It contains a searchable province map/table, market levels and caps, CSV audits,
and a subsistence selector. `start_placement.csv` also records safe startup caps
and initialized gameplay caps for every planned location.
`artifacts/data/worldbuilder/food_sim/` holds the validator's input, per-pool
results and summary.

The 25 September 2026 pass (food model v2, placement v2, construction
materials), with the validator after each placement iteration:

| Iteration | Rule change | Food pools losing >= 25 % | World population 1337-1345 |
| --- | --- | ---: | ---: |
| v1 plan (as in `nb.eu5`) | - | 164-175 | -1.7 % |
| 1 | placement v2 as specified (per-market victuals at 3 per import level) | 306 | -4.0 % |
| 2 | imports and cookeries alternate until the victuals are used | 142 | -2.5 % |
| - | model fix: linear engine promotion (same rules) | 438 | -2.3 % |
| 3 | an import costs its market the victuals its pool's gap needs | 99 | +0.6 % |
| 4 | collapse-risk pools first for scarce victuals; construction materials | 84 | +0.8 % |
| 5 | food niches (2026-09-25): Cookshops serve only, victuals from Victualling Yards, Taverns at 60 food; Cookshops spread by coverage, partial Yard levels, drink food counted | **37** | **+2.5 %** |

Iteration 5 (the food niches) replaced the victuals chain; before it the placement had 2,974 cookshop levels,
2,492 import levels (2,400 by the food chain, 151 city minimums), 17 export levels, 13,265 crop farm levels, 304
masons, 94 lumber mills, 56 tools guilds and 140 market villages for
construction; 1,123 worker conversions. 2,550 pools feed less than their demand
without trade; 538 remain short after it (7.5k of 424.8k food a month). 115 of
130 markets meet the victuals target. The remaining collapses sit in dense
markets whose victuals and raw goods cannot feed them (Genoa, Venice, Naples,
Bruges): the market cannot buy enough victuals for them and cookeries have no
raw goods left. The validator assumes a victuals price of 2.7; with this many
Victuallers the market price would rise on day 0, when every import is staffed.

Construction materials (markets short of their expected demand, before -> after;
without any supply in brackets): lumber 41 (29) -> 22 (15); masonry 62 (11) ->
13 (10), 11 without stone or clay; tools 54 (12) -> 25 (11), 9 without iron,
stone or copper.

## Taverns and Victualling Yards

Both move **60 food per fully staffed level** (one noble each). They are
**two-legged**:

- The **Tavern** serves bought-in victuals: *Serving* buys 2 victuals and earns a
  steady 3.34 gold from 0.167 `offset` at 20x; its *Scarcity Premium* leg (0.533
  `province_food_purchase`, constant +15, -8 per stored year, +8 while starving)
  pays while the store is below 12 months at the mean victuals price. It keeps the
  former Victualler's behaviour at two thirds of its throughput.
- The **Victualling Yard** packs the lasting part of a full store: *Pack
  Provisions* is a real victuals output (1.5 per level, production efficiency
  scales it; no negative input, no pulse script), *Sell the Surplus* is its
  storage leg (2.0 `province_food_sales`, the farms' Surplus Sales good, constant
  -1, +8 per stored year, offset 30.52), paying above 20 months. Its *Packing*
  slot (pottery jars, coopered barrels, tin cans; each breaks even at default
  prices) adds victuals up to 1:30. Loose stores pack at 1:40, so food that goes
  out through a Yard and back through a Tavern always loses; the 12-20 month dead
  band between the two only closes at about +125 % production efficiency.

Each staffed level lowers its own leg by 0.2 so staffing settles.

`config/victuals_logistics.json` generates distinct live script values:

- Taverns favour development, population, town/city rank and market centres (1.5x
  the former Victualler's coefficients, maximum 36).
- Victualling Yards favour water transport and market centres: harbour, coast,
  river level, navigable neighbours; no crop or population terms (they pack the
  province store, not the location's own output).
- Both include mountain/hill penalties and adjacent navigation state.
- Open and maintained waterways grant more capacity than difficult waterways.
  Navigation works can increase the cap during play. A barrier grants no
  navigability bonus, although its native coastline may still supply coast credit.
- Caps are floored, bounded from zero to the configured maximum, and are
  logistical potential, not a promise that demand or workers exist.

The startup planner uses the lower cap from before/after navigation variables
are initialized, so it cannot spend an `on_game_start` bonus prematurely.
Forest capacity also has a geography fallback before its cache is initialized.

Every city gets one Tavern; additional levels depend on deficits, logistics and
staffing. A self-sufficient city's minimum Tavern can remain idle. Placement policy
limits and staffing shares live in `[worldbuilder.start]` in `constructor.toml`.

## Limits of the estimate

This is a start-state food budget plus a calibrated population loop, not the
running game's economic engine. It uses the nearest starting market centre
within each game region as a market proxy. That does not recreate actual market
borders, access, prices, shipping bottlenecks or trade between markets (victuals
trade between markets is almost nil on day 0). It does not simulate armies,
AI builds or engine-only country modifiers. Engine RGO size and market access use
zero lower bounds in cap evaluation, which can deliberately underplace buildings.
A fresh-campaign check is still needed for actual staffing, market clearing and
engine-calculated caps.

## Checks

Run `uv run ppc test`, `uv run ppc blueprint parity` and
`uv run ppc worldbuilder check`. The last command reports population-capacity fit
against World Builder targets, not the food budget. The food audit and the
validator are produced by the build itself.

`uv run ppc worldbuilder food-check [--save <file.eu5>]` compares the model with
a saved campaign (with `--save` it exports the save first; otherwise it uses the
existing `artifacts/data/savegame` export). It reports the engine's consumption
and production per province-owner group, the v1 formula and the food model v2
on the save's own pops, jobs and running methods (`model_v2.configured`), the
refitted rank and climate yields (`model_v2.refit`), the last build's day-0
budget against the engine (`model_v2.last_build_day0`, needs the build that
made the save), and the refitted setup promotion (per 1,000 pops and linear) and
RGO shares to paste into `constructor.toml`. A save on the first day of a fresh
campaign is the right reference.
