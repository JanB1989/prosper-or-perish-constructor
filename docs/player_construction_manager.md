# Player Construction Manager: design brainstorm

Status 2026-11-06: brainstorm only, nothing built. Player-only: the AI keeps its own logic and is never touched.
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
