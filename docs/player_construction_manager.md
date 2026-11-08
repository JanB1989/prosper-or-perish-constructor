# Player Construction Manager: design brainstorm

Status 2026-11-06: **v2 built** on branch `player-construction-manager` (architecture B; v1 and v2 tested in new games as
England, error.log clean of plan lines). Player-only: the AI keeps its own logic and is never touched.

## Built (v2, Jan 2026-11-06: payback instead of cost/profit, a location layer, templates, profiles)

- **Payback is the one money number.** Payback = the gold the next level costs here over the profit one level makes
  here each month, in years. The cost is the engine's own formula, fitted in game on 158 real constructions (all within
  1 %): base price (`building_base_cost_in_gold`) x (1 + increase_per_level_cost x standing levels) / max(0.5, 1 + build
  efficiency: location + owner global + one category term, urban or rural by `is_city`, forts/ports/foreign their own,
  mills none, + the new-building term) x the construction goods' price factor (each good's price / default clamped to
  1 + MIN/MAX_PRICE_IMPACT, 0.5..2.5 in PP, averaged by the demand's amounts; `default_construct_building` when a building
  names none). In game the plan's cost matched the GUI's `GetBuildOrExpandBuildingCost` to the cent (Woking Cookshop
  30.01). Profit: a standing building's `building_profit / building_level` (what PP's build panel also uses); a building
  that does not stand yet shows the engine's estimate (`GetBuildingTypeProfitInLocation`) and its first level needs no
  payback check.
- **Goods "Expand"** = one more level of a standing producer whose next level pays back within the country's payback line
  (default 10 years, Goods tab). Keep stocked stays a stock rule.
- **Two layers.** Each location has a mode: the plan's rules (default), **Own Rules** (the global food, logistics and goods
  rules leave it alone; only its own list builds there) or Hands Off. Own rules run first each month, as their own rule
  group with an equal share of the monthly limit.
- **Location rules** (Here tab; up to 4 per location): build a building up to a level, one level at a time, when a
  condition holds (Always or one of 18 numbers: the game's location filter numbers - population, peasants, idle peasants
  and laborers, employment, market access, control, proximity, development, prosperity, building levels, tax base, RGO
  profit, literacy, coast, river - plus PP's stored food and arable land; at least / below a threshold that starts at the
  value here) and the next level pays back within its limit. Each rule shows its state after the last pass (started,
  waiting for the condition, done, a level under construction, payback above the limit, cannot be built now, budget,
  market lacks the construction goods).
- **Getting there:** a cog in the location window header (player-owned locations) opens the Here tab on that location;
  the Locations tab lists every province and location with its mode, Edit, and template buttons. The Here tab lists the
  buildings standing there and the ones that could be built there, each with its payback, and an Add button.
- **Templates** (4 per country): save a location's mode and rules, apply them to one location (Here or Locations tab) or to
  every location of a province (province row in Locations, or the Province button in Here). A location shows "template
  N" until edited.
- **Profiles** (3 per country, Plan tab): save and load the country settings (reserve, limit, logistics line, stock
  line, payback line, which rule groups run, every good's mode). Province focuses and location rules are not in them.
- **Guards found in the in-game tests:** the construction goods must be in the location's market (one unit's need of each;
  the engine stalls a construction whose market lacks them: 3 Cookshops in Northumberland stalled on Edinburgh masonry);
  never a second level of the same building in a location while one is under construction (a Granary had +5 queued in
  Plymouth); the food rule waits in a province while one of its food buildings is under construction there.
- Engine facts (memory `player-construction-manager`): `NOT = { a b }` means neither a nor b; `construct_building` checks no
  `allow` (it queued Cookshops outside province capitals until the guard was fixed); `can_build_building` does check
  `allow` and max levels; building conditions of foreign and jewelry buildings read `scope:actor` (the plan sets it);
  `num_pop_type:peasants` (colon form); a GUI reads a scope variable with `Scope.Var('x')`, `.IsSet`.
- Not built yet: Upgrades rule group; filter by the game's own search filters inside our lists (the conditions mirror their
  numbers instead); per-template names; "Expand" and "Never" for farms bought by the food rule are untested at scale; a
  long run (cost not profiled).

## Built (v1)

- **Construction Plan** panel (scripted widgets `pp_construction_plan` = opener button, `pp_construction_plan_window`;
  `in_game/gui/pp_construction_plan.gui`), tabs Plan / Food / Goods / Logistics. Off by default per country.
- **Plan:** on/off, gold reserve (months of total income), most new constructions a month, rule groups on/off, "Last
  month" list (building, location, which rule). Each running group gets an equal share of the monthly limit; a share left
  unused passes on to the next group (food, logistics, goods). Constructions are `construct_building` = normal, paid,
  in the construction queue (verified: gold drops, queue shows them).
- **Food (per province):** focus Standard 6/18, Breadbasket 8/20, Market Town 6/14, Workshop 4/12, Hands Off, Custom
  (arrows set your own band); status per province (building X / blocked / in band / above / held back / Granary due).
  Baseline rules since 2026-11-08 (Jan), one construction per province a month, the first that builds: (1) below the
  band a crop farm (standing line first, else the line with the best local output); (2) a kitchen whenever the Cookshop
  budget allows, Public Kitchen first (an old tier cannot be built once its successor is researched); (3) below the
  band a Tavern; (4) a Granary while the store can hold less than N months of consumption (`province_max_food` /
  consumption, setting, default 24) and is at least X % full (setting, default 85), both in 3 passes in a row: room
  helps only a store that fills, in run 057c295e half of all provinces had room but sat at ~13 months; (5) a Grange
  after the store held 24 months for M passes in a row (setting, default 12), the count starts again after each level.
  The hunger steps wait while a farm, kitchen or Tavern of the province is under construction. Counters
  `pp_cplan_gw` / `pp_cplan_fw` (province) move every pass, also with the budget used up; switching the plan or a group
  clears them. Food tab: the three settings, room and fill per province. Tested in game 2026-11-08 (Cyprus save,
  1339, 5 months): Cyprus room 22 months, 100 % full; the Granary came due after 3 passes; with a location profile on
  the province capital it stayed "due, cannot be built" (the profile has priority there); without it the kitchen step
  started a Cookshop, the next month the Granary; the market count rose 112 -> 116 (same-market compare works,
  `province_max_food` works as a value); error.log has no plan lines. Not exercised: a location below the logistics
  line, a market switch, an occupation, a Grange, the Public Kitchen upgrade. Farm, Tavern and Victualling Yard rules: open
  (Jan's direction: farms by stored months + arable land, highest payback first, robust to Seasonal Harvests; Taverns
  where farms do badly or food is very low; Yards by payback).
- **Goods (per good):** Off / Keep / Expand / Never, months of stock in the capital's market, a Keep line (months).
  Keep built a Stud Farm in Woking for horses (0 months) in the test.
- **Logistics (per location):** a market access line (default 97 % since 2026-11-08, steps of 1), per location Follow
  Plan / Always / Never and Plan builds / Hands Off. The buildings' own gates still apply (15 building levels: no English
  location qualified in 1337). Short dips do not count (Jan): below the line in 3 passes in a row while the owner
  controls the location (`controller ?= owner`), and 12 months without a market switch (`pp_cplan_mm`, market in
  `pp_cplan_mkt`; a market first seen counts as settled). Run af7dce96 (1342-1837, 5-year saves): 98 % of drops below
  97 % came with a market switch, a third were back above 5 years later; occupation 1.4 % (1 % otherwise); dips shorter
  than 5 years are not in those saves. The Logistics tab marks a location "waiting" with both counts in the tooltip.
  Always skips the wait.
- Generated parts (`construction_plan.py`, finalize): farm/kitchen/tavern/granary/logistics pickers, 226 producers of 75
  goods, per-good values, the Goods tab rows. Tests: `tests/test_construction_plan.py`.

## Not built yet (from the mock-up and this doc)

- Controls in PP's own windows (food panel rows, market goods list, location window); all controls sit in the panel.
- "Next from the plan / blocked by" per location; pins per building (only per-location Hands Off).
- Upgrades rule group; province focus preset from geography (every province starts on Standard).
- The Logistics tab lists every location below full access, also those under the 15-level gate.
- Not exercised in game: Expand while profitable, Never, multiplayer, a long run (cost not profiled; one country).
Goal (Jan): a player sets rules once, coarse or fine, and buildings get queued when the conditions hold. It has to
understand PP's own systems (Province Food and stores, logistics, farm land, the Cookshop budget), which Construction
Manager does not.

## 1. What Construction Manager does (workshop 3736668860, v2.2.14, EU5 1.4.7)

- **How it builds.** A monthly human-country pulse (from Community Mod Framework, CMF) only *stages* candidates into
  variable lists. An always-present hidden widget, added through `gui/scripted_widgets` (no vanilla file overridden),
  drains the lists over the next frames with animation states and fires the player's own GUI action
  `BuildOrExpandBuildingDefault` / `UpgradeBuildingDefault`. Why the detour: cost, tax income and profit per level of a
  building not yet built, and the next tier, are GUI-only bindings (`GetBuildOrExpandBuildingCost`,
  `GetBuildingTypeProfitInLocation`, `GetBuildingTypeIncomeToOwnerInLocation`, `CanBuildOrExpandBuilding`,
  `GetNextReplacementBuilding`). A second hidden widget classifies every building type once per load for the same reason.
- **Features**, run in a player-ordered priority list: expand existing buildings, expand RGOs, upgrade obsolete
  buildings, auto-build listed building types, auto-food, auto-urbanize (via fake "Found Town/City" buildings), capital
  buildings, auto-grant town rights.
- **Conditions** it offers: min tax income or min profit per level or max ROI years (one metric chosen), min
  construction discount (price of the construction goods in the market), gold reserve, overbuild limit (supported
  building levels), min control, enough pops of the building's type now or within a year, building open, fully
  staffed, no missing goods, not already constructing, the market not short of construction goods (seven goods,
  written by hand).
- **Controls:** per-location toggles in the location and building views, shift-click mass toggles by filter, map
  modes, a requirements tooltip ("will not expand: ... not met"), settings in CMF menus.
- **Why it breaks with PP:** it ships `location_window.gui` and `building_view.gui` (PP ships both too: one wins by
  load order) plus re-declared vanilla types in its production, build-location, food and automation views. Its food
  logic is vanilla food (highest food output per RGO good), blind to Province Food, stores, the Cookshop budget,
  Tavern and Granary rules, and farm land.

What to keep from it: the priority list, the gold reserve, "blocked by" tooltips, mass toggles, the hidden
`scripted_widgets` trick if we ever need GUI-only numbers. What not to copy: overriding vanilla windows, one hand-made
list per good.

## 2. What the engine gives us

| Need | Available | Note |
| --- | --- | --- |
| Start a construction from script | `construct_building = { building_type owner payer instant cost_multiplier cost_multiplier_reason }` (location scope; vanilla uses it ~400 times: parliament agendas, fort sponsorship) | **Verify in a test mod:** a non-instant one charges normal gold and goods, joins the owner's queue, respects can-build and max_levels, adds a level to a standing building |
| Can it be built here | `can_build_building` (location and country scope) | |
| Already building | `building_levels_under_construction` | |
| Profit of a standing building | `building_profit` | |
| Profit or cost of a level not yet built | GUI only | We precompute static scores in the constructor instead (section 4.3) |
| Engine automation for players | Automation panel (1.4): "Buildings" (the game builds for you), "Auto-Expand Buildings" (marked buildings, if profitable, staffed, no missing goods, slots left), "Auto-Expand R.G.O.", close/open, subsidize, destroy. Toggled from script with `set_automated_system`; a building opts out with `automation_build_allowed = no` | **Verify:** does "Buildings" for a player read `ai_construct_weight` and the AI's gold gates? |
| Player-automated actions | generic actions with `player_automated_category` + `automation_tick` | Categories are fixed (religion, estates, colonies, ...); none for construction |
| Settings UI | scripted GUIs (work for players, dead for observers), `gui/scripted_widgets` for new windows | |

## 3. Three ways to build it

**A. Steer the vanilla automation.** The player turns on "Buildings"; PP adds player-only terms to its
`ai_construct_weight` scores (x0 vetoes, flat boosts) that read the player's settings (country variables), behind
`owner = { is_ai = no }`. The engine handles gold, goods, queue and pacing.
- For: no pulse, no executor, immune to UI changes; our existing terms (food urgency, short markets, logistics urgency,
  Granary weight, farm store bonus) come for free.
- Against: unproven for players; the engine's own food term scores thousands to billions, so only a hard veto beats it;
  "exactly this building here" cannot be said; the player sees fuzzy behaviour.

**B. Own rule engine in script + `construct_building`.** A monthly player-only pass, spread over the month by
province, reads PP script values and starts constructions directly.
- For: exact and readable; our own conditions; no GUI tricks, so it works under any UI mod.
- Against: a pulse (one country only, but still one); no hypothetical profit (static scores instead); the effect's
  cost semantics are unverified.

**C. Construction Manager's GUI executor.** Exact player click, all GUI-only numbers.
- Against: timing tricks at speed 5, breaks when GUIs change. That is what broke for us.

Suggestion: **B as the core**, A as an optional "let the game handle the rest" switch for players who want it, C only
if a rule truly needs profit per level of a building not yet built.

## 4. The rule model

### 4.1 What a rule is

Target (what) x Scope (where) x Condition (when) x Limit (how much) x Priority/budget.

### 4.2 Scope: each domain has its own natural scope

Asking "province or country?" once for everything gives a bad answer for half the domains. Each module takes the
scope where its numbers live:

| Module | Natural scope | Why |
| --- | --- | --- |
| Food | province | Province Food, the store, the Cookshop budget, Tavern and Granary at the province capital |
| Logistics | location | market access is per location; one logistics level at a time per location |
| Goods | market | price and stock are market numbers |
| Upgrades | country | a tier is researched country-wide |

On top, a cascade lets the player go finer where wanted: **country default -> province override -> location pin**.
Unset means "inherit", so one country-level setting covers everything until the player cares about one place.

### 4.3 Target: goods, families, buildings

- **Per good** ("keep iron stocked"): the manager picks the building. Candidates = producers of that good the player
  can build there; score = a static output value per gold of cost (constructor-generated per building, like
  `market_short_weight.py` already lists 224 producers of 75 goods) x the location's output modifier for that good x
  raw-material fit; legacy-only producers skipped. Generated, so it follows every rebalance.
- **Per family** (crop farms, kitchens, logistics, granaries): for PP systems where no traded good is the point
  (Province Food is never traded, logistics is a dummy good).
- **Per building** (pins): the escape hatch. "Never build X here", "always keep X at max here".

Suggestion: goods for the market layer, families for food and logistics, pins for fine control. A player with 300
building types never has to touch a building list.

### 4.4 Condition vocabulary (keep it small)

- **Food:** stored months (a band: build below, stop above), province food gain or loss per month, store fill vs
  capacity.
- **Market:** months of stock of the good, price vs default, unmet demand.
- **Location:** market access, building levels over the supported ones, idle workers of the building's pop type,
  arable land left, control, already constructing here.
- **Money:** reserve in months of income (scales with the game, unlike CM's flat gold), max spend per month.

### 4.5 Set-and-forget in four layers

1. **Master:** on/off, reserve (months of income), monthly spend share.
2. **Province focus**, one choice per province, preset from geography: *Breadbasket* (food band high, farms first),
   *Market town* (logistics, kitchens, trade buildings), *Workshop* (goods rules apply here first), *Hands off*,
   *Custom*. A focus is just a bundle of module settings.
3. **Module settings:** food band, access threshold, goods modes.
4. **Pins** on single locations.

Most players stop at layer 1 or 2.

### 4.6 Modules

**Food (per province).** A stored-months band. Below the low end, answer in the food chain's own order:
1. farm levels where arable land is left (crop by local output fit; the farm caps already count other farms'
   constructions),
2. the next farm tier where researched,
3. Cookshop / Public Kitchen within the province budget (farm levels / 5 + Victualling Yard levels / 2),
4. a Tavern level in the province capital when the market has victuals,
5. a Granary when the store is full but holds less than 24 months (a capacity problem, not a food problem).

Above the high end: nothing. Optional "export" switch: Victualling Yard / Grange where victuals are dear. The store
lever already cuts Province Food output as the store fills, so the band limits itself. Options: crops by staple only,
by price, or by fit.

**Logistics (per location).** Build when market access is below the player's threshold (default: the building's own
gate) and the location has enough building levels. The variant comes from the zone triggers (`pp_logistics_zone_*`);
order river > coastal > city > rural like staffing. One level at a time is already enforced by max_levels. Options:
province capitals only / everywhere, skip low control. Probably just on/off plus one threshold.

**Goods (per market, or country-wide over the player's markets).** Per good one mode: *Off / Keep stocked / Expand
while profitable / Never*. Default: off, except construction goods (lumber, masonry, stone, tools) on *Keep stocked*.
*Keep stocked* reads the same stock measure as `pp_market_short_<good>`, so player and AI see one number.

**Upgrades (country).** Replace an obsolete tier when the successor is researched (farms, mines, manufacturing lines);
legacy methods mean no recipe is lost. Options: where profitable / everywhere.

**Later or never:** RGO expansion (PP RGOs do not expand), town rights (PP has per-good rights; CM's auto-grant could
come back), urbanization.

### 4.7 Budget and priority

- Spend only above the reserve.
- Modules in a player-ordered list (default food > logistics > upgrades > goods), or fixed shares of the monthly spend.
- At most one new construction per province per pass; cap parallel constructions (each one charges upkeep while built).

### 4.8 Feedback

- One message per pass, or a short ledger: what was started where and which rule did it.
- A chip in the food panel row per province: rule on / blocked (gold, workers, budget, land).
- A map mode for province focus.
- A tooltip per location: "would build X; blocked by Y" (CM's best feature).
- No numbers in player text; values behind hover links.

## 5. Where the controls live

- **(a)** one new panel (scripted widget) with a tab per module;
- **(b)** controls next to the data they act on: the food rule on each province row of PP's food panel, the goods mode
  on each good in the market goods list (beside the months-stored bar), the logistics toggle in the location window;
- **(c)** CMF settings menus (a dependency; Jan plays with CMF).

Suggestion: (b) for the toggles plus a small master panel (a). PP already owns the windows (b) needs:
`location_window`, `food_production_lateralview`, `goods_overview`, `markets_overview`, `selected_market_view`. Nothing
new overrides vanilla.

## 6. PP rules the manager must respect

- Owner and capital gates sit in `allow`; the manager calls `can_build_building` and never re-implements them.
- Province-capital-only buildings: Tavern, Granary, Cookshop / Public Kitchen (one budget per province).
- Farm land caps count farms of other types under construction.
- Logistics: one level at a time, zone variants, gate on market access and building levels.
- Building levels over the supported ones cost market access.
- Workers per level after the employment cut; idle workers of the right pop type.
- The store lever, food urgency, the Grange price rule and the Victualling Yard sites.
- Tier lines, legacy methods, the mine tier freeze.
- Player-only: every term behind `is_ai = no`; AI scores never change.

## 7. Performance

One country, monthly, spread over the days of the month by province (like the yearly country pulse). Early exits:
module off, gold under the reserve, province already constructing. Measure with the script profiler before shipping.
(Standing rule: pulses only when Jan asks; this feature is that ask.)

## 8. Open questions

1. Architecture: B (own rules + `construct_building`), A (steer the vanilla automation), or both?
2. Inside PP, or a separate sub-mod that loads after PP?
3. Natural scope per module plus the cascade, or one scope for everything?
4. Goods rules per market or country-wide?
5. Province focus presets: yes or no, and which?
6. Controls in place (b), one panel (a), or CMF (c)?
7. Name.

## 9. First steps if we go

1. Test mod (one launch, all variants): non-instant `construct_building` (cost, queue, max_levels, adding a level,
   payer); `set_automated_system`; whether the vanilla "Buildings" automation for a player reads `ai_construct_weight`.
2. Logistics module first (smallest, clear condition), then food, then goods, then upgrades.
