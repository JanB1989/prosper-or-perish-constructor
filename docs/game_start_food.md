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

1. Expand vanilla town presets and include explicit setup buildings, including
   foreign-owned religious buildings. Preserve their ownership and other setup
   metadata. Add the World Builder's initial improvement buildings.
2. Reduce existing levels until every evaluated location cap is satisfied.
   Re-evaluate shared capacity after each placement. Unknown cap or gate syntax
   stops generation instead of silently granting space.
3. Reserve available workers for existing buildings. Place configured resource
   processors, appropriate farms, fishing villages and forest villages where
   their live gates, caps, available workers and land permit them.
4. Group food budgets by province **and owner**. Fund imports from exports in
   the same estimated trade catchment, retaining the configured food reserve
   in donor provinces. Do not place opposing transfers in one province.
5. Add cookeries to remaining deficits where staffing and caps permit. Convert
   only the permitted share of local peasants to laborers, preserving culture,
   religion and total population. Nobles are never fabricated for markets.
6. Audit all placed building levels and export the budget and sensitivity report.

Existing special buildings may remain understaffed; their food is counted only
for staffed levels. All newly placed food buildings must have available workers.
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

Balance coefficients are intentionally modest and adjustable. No particular
city is forced to import: the game's initial population and its owned provincial
hinterland may already feed it. Placement policy limits and staffing shares live
in `[worldbuilder.start]` in `constructor.toml`.

## Report and current result

Open `artifacts/data/worldbuilder/food_simulation/index.html` after a build.
It contains a searchable province map/table, market levels and caps, CSV audits,
and a subsistence selector. `start_placement.csv` also records safe startup caps
and initialized gameplay caps for every planned location.

The September 2026 pass audits 56,460 positive location/building records across
13,690 owned locations. It removes 8,275 excess starting levels and leaves zero
entries above the evaluated cap, with no unresolved cap rules. New placements
include 16,119 farming village levels, 11,724 fishing village levels, 6,445 forest
village levels, 1,265 orchard levels, 636 cookery levels, 44 import-market levels
and 60 export-market levels. The difference in trade levels is export capacity
left unmatched after local import staffing/cap restrictions; imports never
exceed funded exports in their catchment.

| Subsistence | Province/owner groups short | Food missing per month |
| --- | ---: | ---: |
| 1.0 | 2,004 | 15,849.27 |
| 1.25 | 840 | 3,366.71 |
| **1.5** | **563** | **1,870.95** |
| 1.75 | 461 | 1,547.20 |
| 2.0 | 405 | 1,331.84 |

These scenarios hold placements fixed. At 1.5, projected unmet demand is about
0.57% of 328,670.96 monthly food demand. Keeping 1.5 is a provisional balance
choice: increasing it mainly expands surplus rather than solving isolated
shortages. The report identifies remaining short provinces for later tuning.

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
