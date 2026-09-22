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
  the game promotes roughly 50 million of them into nobles, clergy, burghers,
  laborers and soldiers (nobles eat 25 food per 1,000, peasants 1). The shares
  per 1,000 pops by rank live in `[worldbuilder.start.engine_promotion]`; they
  were fitted to a one-month reference save and are refitted by
  `uv run ppc worldbuilder food-check --save <file>`. Worker conversions the
  planner writes into `06_pops.txt` count only where they exceed that share.
- **RGO hiring.** The location's RGO employs `[worldbuilder.start.rgo_workers_k]`
  thousand peasants who leave subsistence agriculture.
- **Local food modifiers.** Subsistence and building food are scaled by the
  rank's and the classes' `local_monthly_food_modifier` (rural −10 %; the World
  Builder class rows cancel the vanilla class values exactly).
- **Province pools are per province and owner** in the engine, which is what
  the budget groups.

Subsistence is 1.5 food per 1,000 unemployed peasants, laborers and slaves; the
engine's own production matches this formula with R² 0.98 on the reference save.
Food decay is deliberately ignored: the starting stock is generous by design.

1. Expand vanilla town presets and include explicit setup buildings, including
   foreign-owned religious buildings. Preserve their ownership and other setup
   metadata. Add the World Builder's initial improvement buildings.
2. Reduce existing levels until every evaluated location cap is satisfied.
   Re-evaluate shared capacity after each placement. Unknown cap or gate syntax
   stops generation instead of silently granting space.
3. Reserve available workers for existing buildings. Place configured resource
   processors, appropriate farms, fishing villages and forest villages where
   their live gates, caps, available workers and land permit them.
4. Group food budgets by province **and owner**. Place export markets where a
   province has food beyond its reserve and the catchment has deficits.
5. Per trade catchment, cover the food deficit with cookeries and import
   markets together so that the imports buy `absorb_share` of the victuals the
   catchment makes (see below). Cookeries go to rural deficits first; imports
   go to urban deficits first, then to the remaining deficits, then the towns
   and cities take the leftover victuals as importers beyond their own need.
   Deficits the imports cannot reach fall back to cookeries, whose victuals are
   again bought by urban import levels. Every city and megalopolis additionally
   receives at least one import market. Only the permitted share of local
   peasants becomes laborers, preserving culture, religion and total
   population. Nobles are never fabricated for markets: the engine's setup
   promotion supplies them.
6. Audit all placed building levels and export the budget and sensitivity report.

## Victuals balance

Victuals are the mod's food in the goods market. Cookeries make them (about
0.65 per level as the market sees it), the villages' worker provisions add a
baseline (about 0.05 per level), export markets turn province food into them,
and pops, lumber mills and above all **import victuals markets** (about 1.2
per level) buy them. Import markets are the only buildings that turn victuals
back into province food. If far more victuals are made than bought, their
price collapses, the cookeries become unprofitable and lay off their laborers,
and the province food they gave disappears months into the campaign.

`[worldbuilder.start.victuals]` in `constructor.toml` holds the per-level
rates, the pop demand scale (the goods file's `demand_add x demand_multiply`
against what the market shows) and `absorb_share`, the share of a catchment's
victuals the imports should buy. The planner solves per catchment

    food:     cookeries x 18 + imports x 60 >= deficit
    victuals: imports x 1.2 = absorb_share x (existing surplus + cookeries x 0.65)

and reports supply, demand and the absorbed share per catchment in
`report.json`. `ppc worldbuilder food-check` refits the per-level rates from a
save.

Existing special buildings may remain understaffed; their food is counted only
for staffed levels. Ordinary new food buildings must have available workers; the mandatory city
import market is an infrastructure minimum and may initially be unstaffed.
Staffing removes workers from subsistence, so moving a peasant into a farm does
not count their food twice. Historical buildings are not deleted simply because
workers are scarce.

## Victuals markets

Both variants transfer **60 food per fully staffed level**. Import production
uses two victuals; export production supplies two. Export market employment now
matches the import variant (one noble per level), allowing rural surplus sites
with small noble populations to participate.

`config/victuals_logistics.json` generates distinct live script values:

- Imports favour development, population, town/city rank and market centres.
- Exports favour rural food resources, farmland and water transport.
- Both include native river level, coastal access, natural harbour suitability,
  mountain/hill penalties and adjacent navigation state.
- Open and maintained waterways grant more capacity than difficult waterways.
  Navigation works can increase the cap during play. A barrier grants no
  navigability bonus, although its native coastline may still supply coast credit.
- Caps are floored, bounded from zero to the configured maximum (currently 24),
  and are logistical potential, not a promise that demand or workers exist.

The startup planner uses the lower cap from before/after navigation variables
are initialized, so it cannot spend an `on_game_start` bonus prematurely.
Forest capacity also has a geography fallback before its cache is initialized.

Balance coefficients are intentionally modest and adjustable. Every city gets
one import market; additional levels depend on deficits, logistics and staffing.
A self-sufficient city's minimum market can remain idle. Placement policy limits and staffing shares live
in `[worldbuilder.start]` in `constructor.toml`.

## Report and current result

Open `artifacts/data/worldbuilder/food_simulation/index.html` after a build.
It contains a searchable province map/table, market levels and caps, CSV audits,
and a subsistence selector. `start_placement.csv` also records safe startup caps
and initialized gameplay caps for every planned location.

The 22 September 2026 pass (engine start state modelled, victuals balanced)
plans 13,690 owned locations, removes 8,275 excess starting levels and leaves
zero entries above the evaluated cap. New placements include 2,632 cookery
levels, 1,794 import-market levels, 113 export-market levels, 13,872 farming
village levels, 10,244 fishing village levels, 5,618 forest village levels and
1,069 orchard levels. Monthly food demand is 412,875 (peasants 241k, laborers
54k, burghers 42k, nobles 31k, clergy 24k, slaves 15k, soldiers 6k), which
matches the engine's 420,025 in the one-month reference save. The victuals the
catchments make (3,519 per month) meet a demand of 2,837, an absorbed share of
81 % (median 82 % per catchment). The earlier passes had modelled 328,671 food
demand from the raw pops file and placed 636 cookery levels (73 % of the
province-owner groups then ran a structural deficit), or 4,224 cookery levels
against 306 import levels, which flooded the markets with victuals and idled
the cookeries (32 % staffed, 42 % losing money five years in).

| Subsistence | Province/owner groups short | Food missing per month |
| --- | ---: | ---: |
| 1.0 | 1,963 | 48,454 |
| 1.25 | 1,196 | 9,215 |
| **1.5** | **791** | **2,313** |
| 1.75 | 794 | 2,382 |
| 2.0 | 786 | 2,189 |

At 1.5, projected unmet demand is 0.6 % of monthly demand. The remaining short
groups are small provinces whose demand comes from nobles and burghers while
the working pops are slaves or tribesmen: the cookeries cannot convert those
into laborers, which the game shares. Rural provinces are roughly
self-sufficient; towns and cities cover only about half of their demand from
subsistence, so the import markets and cookeries carry them.

## Limits of the estimate

This is a **steady-state food budget**, not the running game's economic engine.
It uses the nearest starting market centre within each game region as a trade
catchment proxy. That does not recreate actual market borders, access, prices,
shipping bottlenecks or competition for victuals. It does not simulate seasonal
harvests, armies, engine-only country modifiers, RGO hiring or RGO food production.
Unemployed peasants, laborers and slaves contribute subsistence; actual RGO hiring
can materially change this estimate. Engine RGO size and market access use zero
lower bounds in cap evaluation. This can deliberately underplace buildings.

Consequently, a clean offline cap audit is not a claim of an in-game validation
of every country's modifiers. A fresh-campaign check is still needed for actual
staffing, market clearing and engine-calculated caps. Retain the 1.5 setting until
those observations justify changing it.

## Checks

Run `uv run ppc test`, `uv run ppc blueprint parity` and
`uv run ppc worldbuilder check`. The last command reports population-capacity fit
against World Builder targets, not the food budget. The food audit is produced
by the build itself. Tests cover live cap arithmetic and initialization timing,
shared capacity, staffing and population conservation, food conservation,
export reserves, isolated catchments and preservation of foreign-owned buildings.

`uv run ppc worldbuilder food-check [--save <file.eu5>]` compares the model with
a saved campaign (with `--save` it exports the save first; otherwise it uses the
existing `artifacts/data/savegame` export). It reports the engine's consumption
and production per province-owner group next to the model formula evaluated on
the save's own pops and buildings, the last build's budget for the same groups,
and the refitted setup-promotion and RGO shares by rank to paste into
`constructor.toml` when the game's setup changes. A save one month into a fresh
campaign is the right reference; decay is excluded by construction.
