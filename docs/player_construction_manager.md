# Player Construction Manager: design brainstorm

Status 2026-11-09: **two tabs** (Jan: "global settings that are very easy to set, and then our profiles, and that's
it"), branch `location-profiles`; since 2026-11-10 a third tab and a sixth rule group, **Towns and Buildings**; see the
next section. The sections below it are the history (v1, v2, the first
2026-11-09 pass); what they describe and the next section no longer lists is gone. Player-only: the AI keeps its own
logic and is never touched (a console-only test switch lets it run for an AI country in the test world).

## Two tabs (Jan 2026-11-09, evening), three since 2026-11-10

- **The window** (`in_game/gui/pp_construction_plan.gui`, vanilla main tabs): **Global Settings**, **Location
  Profiles** (the profile editor, type `pp_lprof_editor_tab` in `pp_location_profiles.gui`; every opener of the old
  editor window opens this tab: `docs/location_profiles.md`) and **Towns and Buildings** (GUI variable `pp_cplan_tab` =
  `country`; the settings of the rule group of that name, type `pp_cplan_country_tab`, hosted the same way; the type,
  the group's effect `pp_cplan_group_country` and `pp_cplan_country_rights` are `construction_plan_country.py`'s).
  Nothing else.
- **Maintenance 2026-11-10** (not tested in game):
  - *Six rule groups.* `GROUPS` = profiles, food, logistics, improve, business, country (code 107). The player's names
    of two differ from their keys: profiles = **Locations** (what the player set for single locations: their
    profiles' rules, then their marks, the Location Plan's "Also build here", `docs/location_plan.md`; the tab keeps
    its name Location Profiles), country = **Towns and Buildings** (its row has no line: its settings are on its
    tab). Both count in the sum of the weights only while they have something to do (`pp_cplan_profiles_cw`: a
    location has a profile or a mark; `pp_cplan_country_cw`: `pp_cplan_country_active`, a public building ticked or an
    upgrade switched on), so an idle group holds no gold back; the % beside the bar follows. In the lists a mark's
    construction reads "marked there: Also build here" (code 105, step 0; a profile rule's step is its number), a
    public building shows the location's maximum control, an upgrade its people (what that group leaves in
    `pp_cplan_log_val`). The order turns with the month as before, now every group first exactly twice a
    year; the group's urban rights cost no gold, so `pp_cplan_country_rights` runs once after all groups, without a
    part of the gold. A town or city upgrade is no building: that group writes the ledger entry itself (the lists
    `pp_cplan_log` / `pp_cplan_log_107`, location `pp_cplan_log_why` 107, `_cost`, `_step` 2, no building type) and
    the lists name it (type `pp_cplan_rank_upgrade`, "Upgrade to a higher Location Rank"); nothing shows blank. Where
    another group built in the same location in that pass the upgrade leaves the location's line to it; the group's
    own pane then still shows the upgrade (without the other group's building, cost and reason).
  - *One place says when a site is free:* the scripted trigger `pp_cplan_site_free` (`num_civil_constructions < 1`).
    The construction itself, the business sites, the food rule's farm sites and the logistics and improvement groups
    ask it; no other plan script reads the count (a test checks). The engine's `max_constructions_at_same_time`
    (vanilla: 1, a megalopolis 2, one town building + 1) would allow more in some locations; not verified in game, so
    the rule is unchanged. The farm step now takes its sites only among free locations: a busy one among the four
    best used up a try and built nothing, and the province went on to a Tavern although it could farm.
  - *Worker check* (`pp_cplan_staff`): the idle pops of a building's own class are read through one generated value
    per pop type (`pp_cplan_idle_<pop type>`, the type written out as vanilla writes the call). With the pop type
    passed into the quoted call (`"unemployed_pops_of_pop_type_in_location(pop_type:$type$)"`) the trigger logged
    "Script system error! ... trigger [ pop_type ]" about 2,000 times a session (Jan's game, 2026-11-10); no vanilla
    file puts an argument inside quotes.
  - *A pass without gold is cheap for the business group:* its pick (every free site against every business type)
    is the pass's dear part, so the group does not look at all when it starts without gold to spend
    (`pp_cplan_budget_left` right after it got its part). Its pane then says "It had no gold to spend, so it did not
    look for businesses" instead of "Nothing waited for gold", and the chart's tooltip says that such a month shows
    nothing: what the businesses would have cost is not counted then. The other groups still go through all they
    want (they are cheap); the logistics and improvement groups no longer look for a building in a location with a
    construction under way (it could not start one; it still counts for their situation).
  - *"Last month" list:* its reasons that do not apply take no room any more (`ignoreinvisible`: an improvement's
    reason stood behind the gaps of the four hidden ones).
- **Global Settings:** run the plan every month (on/off); the gold reserve in gold (default 1,000; - and + move it 100,
  a right-click 1,000; a script cannot read typed text, the game's typed fields such as the loan amount are wired into
  the engine); the rule groups, each with a weight bar (see below) and the last three with one line: Food per province (no line; its numbers stay at the
  `[construction_plan]` defaults), Logistics per location (market access below the line, default 97 %, steps of 1),
  Improvements per location (population over capacity from the line, default 90 %, steps of 10 from 50 to 300 %:
  `location_population_percentage`, Jan's "old school" population / population capacity), Businesses (payback within
  the line, default 10 years, steps of 1 from 1 to 50); "Last month": what the last pass built where and by which rule.
- **The month's gold:** no limit on the number of constructions any more. A pass may spend the gold above the reserve
  (`pp_cplan_pot`); each rule group that runs adds an equal part to `pp_cplan_cap`, so a part one group leaves passes
  on; a group may go past its part with its last construction. No construction takes the treasury below the reserve:
  `pp_cplan_construct_scoped` prices the level with the engine's formula (`pp_cplan_btype_data`, `pp_cplan_est_cost`)
  and starts it only when it fits in the gold above the reserve (`pp_cplan_affordable`). The groups' order still turns
  with the month (six groups since 2026-11-10: every group goes first twice a year).
- **Businesses (new rule group):** every building whose main good is a market good (the producers of
  `market_short_weight.main_good`, 224 types; not the food rule's Taverns, kitchens, Granaries, Granges and Yards, not
  logistics or improvements, not the hidden goods) wherever a level pays back within the line, the best yearly return
  first across the country. Each pass: the country's part of the can-build check once per type
  (`pp_cplan_business_types`, `can_build_building` in country scope, marks cleared after the group); then every free
  site (the player's location, held by the player, with a market, no construction under way, no profile there that
  keeps businesses out) picks its best candidate (`pp_cplan_business_pick`: the location can build it, max level and
  allow included, the market holds its construction goods, no level of it here is closed, a profile here does not name
  its good or its building category); then the picks are built in the order of their return while the gold lasts.
  **Profit**, the same for a new building and one more level so the two compare: each slot's best method at the
  market's prices and the location's output modifier of the good it makes, inputs at market prices, with **this year's
  Variable Harvest taken out** (the `local_<good>_output_modifier` of the location's `pp_harvest_*` modifier, read per
  sub-continent and severity into `scope:pp_cplan_hv_<good>`). Return = profit x 12 over the level's cost (the engine's
  formula), in %; the line in years is 100 / return. Left out like the farm estimate: production efficiency, staffing,
  market access, method unlocks (a method not researched yet still counts). Farms are businesses too: the food rule
  builds them where a province is short, the business rule where they pay.
- **Weights instead of on/off** (Jan 2026-11-09, later the same day: "allocate percentages, maybe slider-based; every
  slider on full divides it"): each of the rule groups (Locations = the location profiles, Food, Logistics,
  Improvements, Businesses, and since 2026-11-10 Towns and Buildings) has a weight 0..10 (default 5;
  `[construction_plan] weights`); its part of the gold above the reserve =
  its weight over the sum of the weights that count (`pp_cplan_share_<group>`; the profiles count only while a location
  has a profile or, since 2026-11-10, a mark; Towns and Buildings only while something is ticked on its tab), shown in % beside the bar (`pp_cplan_part_<group>`). 0 = the group is off. A part one group leaves
  passes on, as before. The bar (generated, `gui/pp_construction_plan_weights.gui`): vanilla's slider - and + buttons
  and a gold progress bar whose ten steps set the weight when clicked. A real slider is not possible: vanilla's
  sliders report their value only to engine functions (`onvaluechanged = "[AutomatedSystemsItem.OnChangedGoldSlider]"`),
  a scripted GUI cannot receive it.
- **Workers** (Jan 2026-11-09: "we don't want to build endless businesses in a location that doesn't have the
  peasants"): a business or a profile rule's building gets a level only where it finds the workers one level needs
  (`employment_size` of the building, a number or a script value such as `manpower_employment`, in thousands like the
  pops): the idle peasants left after the open jobs of the buildings there (`pp_cplan_free_peasants_here`: idle
  peasants minus each building's `building_employment_size_amount - building_employed_amount`; peasants are promoted
  into the other classes), or idle pops of the building's own class (`pp_cplan_staff`, which reads them as the
  generated `pp_cplan_idle_<pop type>`). A profile rule that finds no
  workers shows "No free workers here" (state 4). The food, logistics and improvement rules do not check workers.
- **Detail panes** (Jan 2026-11-09, night: "we can see that a building is being built, but not how much investment
  is missing given the current settings, or why it was built; a little cog per setting where you can see what's
  happening under the hood"): each rule group's row ends in vanilla's cog (`button_automation_shortcut`); it opens that
  group's pane in place of the "Last month" list (GUI variable `pp_cplan_detail` = the group; generated
  `gui/pp_construction_plan_detail.gui` + `pp_construction_plan_detail_l_english.yml`, construction_plan_detail.py).
  The pane shows the last pass: the gold the group could spend (its part plus what the groups before it left), what it
  spent on how many constructions, how many it wanted that waited for gold and the gold that would have started them
  all, the group's situation (food: provinces close to empty or short a year from now, due a Granary or a Grange;
  logistics: locations below the line and the lowest access; improvements: locations over the line and the fullest;
  businesses: sites with a business within the line and the quickest payback; profiles: locations and their rules by
  state), a chart of the last 12 passes (grey = wanted, gold = spent, as % of the largest month), and the list of what
  it built, each with its cost and its reason (the food step and the store a year from now, the access %, the % of
  capacity, the payback years, the profile's rule). How "wanted" is counted: every group now goes through all it wants
  even after the gold is used up; the construction itself checks the budget (`pp_cplan_construct_scoped`) and counts a
  level the gold does not reach at the engine's cost (`pp_cplan_note_wait`), once per decision (a province for the food
  rule, its one construction a month; a location otherwise). Locations with a construction under way are not counted
  (they cannot start one). The numbers live on the country until the next pass (`pp_cplan_d*` / `pp_cplan_ds_*`, the
  history `pp_cplan_hn_` / `_hs_<why>_<k>`, generated `pp_cplan_stats_reset` / `pp_cplan_history_push`); switching the
  plan on clears the chart. The rules never read any of it (a test checks), so the plan stays stateless as Jan wants.
  Cost: a pass with no gold left checks everything instead of stopping, except the business group since 2026-11-10
  (its pick over every free site was the dear part: it does not look when it starts without gold, see Maintenance
  above); the food steps of every province still run; not profiled yet. Not tested in game.
- **Gone** (Jan: "the rest for now can go"): the Food, Goods, Logistics, Locations and Here tabs; the monthly
  construction limit; the presets; the line about the game's own automation (the guards stay: no level for a closed
  building, nothing where a construction is under way); the goods modes (Off / Keep / Expand / Never); the per-location
  own rules and modes (Own Rules / Hands Off) and the location window's cog (the Location Plan button took its place);
  the logistics overrides per location; the province focus and the food rule's state per province (the hunger line is
  `hungry_months`, 6). A hands-off location is a profile with no rules and every global group switched off (the example
  "hands off").

## Built (v2, Jan 2026-11-06: payback instead of cost/profit, a location layer, profiles)

History: the location layer, the Here and Locations tabs, the cog, the presets and the goods modes below were removed
on 2026-11-09 (two tabs). Payback and the guards stay.

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
  the Locations tab lists every province and location with its mode and an Edit button. The Here tab lists the
  buildings standing there and the ones that could be built there, each with its payback, and an Add button.
- Templates removed 2026-11-09: Location Profiles do this (reusable, assigned on the map).
- **Presets** (2026-11-09, Jan: "baseline settings I could take a look at"; replace the 3 saved "Profiles", whose
  name clashed with Location Profiles): Balanced, Food and growth, Builder, Cautious (`[construction_plan.presets]`).
  A preset sets every setting (unnamed ones back to the default), which rule groups run and every good's mode, so
  loading one never leaves a mix. Province focuses, location profiles and location rules stay.
- **Guards found in the in-game tests:** the construction goods must be in the location's market (one unit's need of each;
  the engine stalls a construction whose market lacks them: 3 Cookshops in Northumberland stalled on Edinburgh masonry);
  never a second level of the same building in a location while one is under construction (a Granary had +5 queued in
  Plymouth); the food rule waits in a province while one of its food buildings is under construction there.
- Engine facts (memory `player-construction-manager`): `NOT = { a b }` means neither a nor b; `construct_building` checks no
  `allow` (it queued Cookshops outside province capitals until the guard was fixed); `can_build_building` does check
  `allow` and max levels; building conditions of foreign and jewelry buildings read `scope:actor` (the plan sets it);
  `num_pop_type:peasants` (colon form); a GUI reads a scope variable with `Scope.Var('x')`, `.IsSet`.
- Not built yet: Upgrades rule group; filter by the game's own search filters inside our lists (the conditions mirror their
  numbers instead); "Expand" and "Never" for farms bought by the food rule are untested at scale; a
  long run (cost not profiled).

## Built 2026-11-09 (Jan: test it, make it clean, let it work with the game's own automation)

- **Global and local together.** A location profile takes from the global rules only what it sets: its rules' targets
  (a good, market access; a staple food also takes the farm step, victuals the Grange and Yard steps) and the global
  groups it switches off (Food, Logistics, Improvements, Goods; checkboxes in the profile editor). Everything else the
  global rules still build in profile locations, after the profile's own rules (`pp_cplan_*_ok` triggers). Before,
  every global rule left a profile location alone, which also kept Cookshops and Granaries out of province capitals
  with a profile. Details: `docs/location_profiles.md`.
- **The game's own automation** (Automation panel): the Plan tab shows whether Buildings, Auto-Expand, Close and Open
  and Destroy are on (`is_system_automated = buildings / expandbuildings / closebuildings / destroybuildings`, read in
  game). They work together: the plan only starts constructions (never closes, destroys or switches methods); neither
  queues a second level of a building in a location while one is under construction; the plan never adds a level to
  a closed building (`is_opened`); with Buildings on, the game also builds by its own judgement everywhere, from the
  same treasury (the plan keeps its reserve). The AI's own destroy paths are forts, proximity sources and late "swap"
  pairs only (private notes `queue_logic.md`), so no destroy-rebuild loop with the plan's buildings.
- **One construction at a time per location.** The engine builds a location's constructions one after another (test
  world: a Cookshop moved 344 days in a year while the Granary, Grange and Carrier Inn the plan had started beside it
  moved 0). The plan starts nothing where `num_civil_constructions` > 0, whoever started it (gold paid for a waiting
  construction is gold lost to everything else).
- **Location window style.** The Profile row on top of the Infrastructure tab and the two header buttons use vanilla's
  types (card, header strip, toggle tiles, `button_round_shortcut`, `button_automation_shortcut`): see
  `docs/location_profiles.md`, UI.
- **Templates removed** (Location Profiles do the same, on the map).
- **Test mode for an AI country:** `pp_cplan_ai_test` (console only) lets the monthly pass run for an AI country (the
  test world as observer: no event pop-ups; the AI's own building plays the game's Buildings automation) and writes
  per construction a marker and two `debug_log_scopes` lines to debug.log, and one line per pass. `debug_log` has no
  data context in this build (ROOT and saved scopes are null in its text) and `debug_log_date` writes nothing.
  `uv run ppc plan-report --save ... --baseline ...` (`plan_test_report.py`) turns saves and logs into
  `artifacts/plan_test/<date>/report/index.html`. Runbook in `pp_testing\README.md`, setup `run\pp_plan_ai_setup.txt`.
- **AI test runs 2026-11-09** (test world, Castile as AI, 1337-1352, the Balanced preset with 10 constructions a month,
  the six example profiles on 258 of 424 locations, +20,000 gold; control run with the same gold and no plan;
  `artifacts/plan_test/2026-11-09/report_ai/`): no plan error in error.log over the 15 years (every plan line there came
  from the console's description pass of the setup file); about 2 s a game year either way; the monthly pass 0.43 s a
  game year in the script profiler (profiles 0.38 of it). Found and fixed on the way: profiles took all the gold when
  money was tight (order now turns with the month), one construction at a time per location, the Granary before the
  kitchen (no Granary in 15 years before). Last run: +141 levels over the control (Cookshops 59, wheat farms 45,
  Drainage Ditches 34, Granaries 24, Spinners' Guilds 21 for cloth on Expand), 43 provinces at 24+ months of food against
  34. The global rules built in profile locations only what the profile does not set (Cookshops and improvements yes;
  logistics never where the profile has a market access rule; nothing in hands-off locations). Mines (payback 100-240
  years at the start) and naval buildings stayed unbuilt under their payback limits, as intended.

## Built (v1)

History: the Food, Goods and Logistics tabs, the monthly limit, the reserve in months of income, the province focus and
the logistics overrides below were removed on 2026-11-09 (two tabs). The food and logistics rules themselves stay.

- **Construction Plan** panel (scripted widgets `pp_construction_plan` = opener button, `pp_construction_plan_window`;
  `in_game/gui/pp_construction_plan.gui`), tabs Plan / Food / Goods / Logistics. Off by default per country.
- **Plan:** on/off, gold reserve (months of total income), most new constructions a month, rule groups on/off, "Last
  month" list (building, location, which rule). Each running group gets an equal share of the monthly limit; a share left
  unused passes on to the next group (food, logistics, goods). Constructions are `construct_building` = normal, paid,
  in the construction queue (verified: gold drops, queue shows them).
- **Food (per province):** focus Standard 6, Breadbasket 8, Market Town 6, Workshop 4 months (the low end of the old
  bands; the upper end is unused since 2026-11-08), Hands Off, Custom (arrows set your own line).
  **Baseline rules (2026-11-08, Jan), stateless:** nothing is kept from pass to pass (Jan: no stored history, so the
  pass can run at any rhythm, monthly, cascading or market by market). Short-lived effects are taken out instead (a
  blacklist): this year's Variable Harvest (its `local_peasants_food_consumption`, +0.11/+0.20/+0.30 bad, the same
  negative good, read from `pp_variable_harvest_modifiers.txt` per sub-continent and severity, x peasants x their food
  per head) and spoilage (`local_food_decay` + the owner's `global_food_decay` over max(1, 1 + the province's summed
  preservation)). The food rules read **the store a year from now in a normal year** = province food / normal
  consumption + 12 x (food made - food eaten + the harvest's extra - spoilage) / normal consumption
  (`pp_cplan_food_in_a_year`). The harvest's crop output part is not taken out of the farm estimates (all staple crops
  get about the same shock). One construction per province a month, the first that builds:
  1. famine (a year from now below the famine line, setting, default 3 months): a Tavern, where the market holds
     victuals (`tavern_victuals`, 10);
  2. hungry (a year from now below the focus line): a staple food maker, one bucket: the 8 crop farm lines plus every
     other building that counts toward the Cookshop budget (orchards, fisheries, herds, forest villages, palm groves:
     `food_level_counts`), chained into lines by `obsolete`. Locations where one pays, ordered by
     `pp_cplan_farm_best_roi` (the land is the buildings' own max levels); there the line that pays back fastest, at its
     highest tier that can be built (in game: only Famagusta of the 7 Cyprus locations allows crop farms; a standing
     older tier is replaced once its successor is researched: the old tier cannot be built then). Payback estimate per
     tier: each slot's best method at the market's prices and the location's output modifier of the good it makes,
     inputs at market prices (production efficiency, staffing and market access left out: the same for every line
     there), yearly return in % of the tier's base price. No farm where no line makes a profit (it would lay off its
     workers and make no food);
  3. a Granary while the store can hold less than N months (`province_max_food` / normal consumption, setting 24), is
     at least X % full (setting 85) and a normal month still adds food: room helps only a store that fills, in run
     057c295e half of all provinces had room but sat at ~13 months; before the kitchen since 2026-11-09 (food a kitchen
     adds to a full, capped store spoils; with the kitchen first the AI test run built no Granary in 15 years);
  4. a kitchen whenever the Cookshop budget allows, Public Kitchen first;
  5. hungry and nothing above built: a Tavern (provinces that cannot farm), where the market holds victuals;
  6. a Grange where the store holds 24 months and a normal month still adds S % of consumption (setting 5): a working
     Grange packs the store below 24 months, so the next level waits until it is full again;
  7. a Victualling Yard at Yard sites and market centres: the next level of a standing Yard while it pays back within Y
     years (setting 10, the plan's own payback), a first one where victuals cost at least their default price.
  Farm and Tavern steps wait while a farm or Tavern of the province is under construction (not for kitchens: a
  Cookshop takes a year and held farms back in game). A province with
  the budget used up is skipped at once (status "held back"). The Food tab shows the store now, a year from now (the
  normal month's gain and this year's harvest in the tooltip), room and fill, and the five settings. A location profile
  on the province capital blocks the capital's food buildings (the profile has priority there).
  First version the same day used counts of passes in a row (Granary 3, Grange 12, logistics 3 + 12 months without a
  market switch; tested in game on the Cyprus save: Cookshop, then Granary); Jan rejected stored history, replaced.
- **Improvements (per location, 2026-11-08, Jan):** its own rule group (on/off, share of the monthly limit). Where the
  people fill at least X % of a location's capacity (`location_population_percentage`, setting on the Plan tab, default
  90, steps of 5, 50-150), the fullest locations first: one level of the improvement that adds the most capacity per
  gold (raw_modifier capacity per level over base price x (1 + increase_per_level_cost x standing levels); 15
  improvements read by `arable_land_bar.model`), among those that can be built (a standing older tier is replaced
  once its successor is researched). Test world, new game 1337: no Castile location at 90 %, 8 at 70 %; at 70 % the
  second month built Drainage Ditches in Granada.
- **Test world (2026-11-08, Jan):** `eu5-mini-world` profile `plan_iberia` on stack `pp_plan` = mod "PP Construction
  Test" (load after PP; playset "PP Plan Test", `pp_testing\eu5_playset.ps1 -Mode plan`): Iberia only (451 land
  locations, 4 markets: Burgos, Sevilla, Lisbon, Barcelona), all of it Castile's (`owner = "CAS"`: the other countries
  go off the map, their buildings in Iberia go to Castile), the rest of the world empty. Built from the live PP folder:
  rebuild (`uv run eu5mini build -p plan_iberia -s pp_plan`, then `deploy -s pp_plan --yes`) after a PP sync that
  changes the map or the start setup. New game as Castile: save `pp_plan_base` (1 April 1337). Speed: the plan's
  monthly pass took about 4 ms (script profiler) for 451 locations, 3 constructions a month.
  Stress test 2026-11-08 (`artifacts/plan_test/2026-11-08/README.md`, console `run pp_plan_setup.txt`: 10
  constructions a month, 4 profiles on 168 locations, goods rules): 10 years by `tick_day` take 18-20 s with the
  plan off and 21 s with it on; profiler at 1347: 0.53 s a year for the pass (profiles 0.23, food 0.22). +396
  levels over 10 years. Fixed from it (3accd8fe): construction goods must cover 12 months of the draw
  (`construction_goods_months`; four River Boatmen's Yards had stood still a year on 0.65 naval supplies), and the
  profile pass goes fewest building levels first (the profile assigned last had built nothing). The test world
  falls apart after ~25 years (Catalan independence, rebels, Black Death): use 10-15 year runs.
- **Goods (per good):** Off / Keep / Expand / Never, months of stock in the capital's market, a Keep line (months).
  Keep built a Stud Farm in Woking for horses (0 months) in the test.
- **Logistics (per location):** a market access line (default 97 % since 2026-11-08, steps of 1), per location Follow
  Plan / Always / Never and Plan builds / Hands Off. The buildings' own gates still apply (15 building levels: no English
  location qualified in 1337). Stateless (Jan): market access without the event modifiers of `access_blacklist`
  (`staple_port_commercial_stagnation_modifier` -0.25, the only negative event one in vanilla) below the line while the
  owner controls the location (`controller ?= owner`). No market-switch wait: in run af7dce96 (1342-1837, 5-year
  saves) 98 % of the drops below 97 % came with a market switch, but 98.7 % of the owned locations below 97 % at a save
  were below it five years earlier too, so short dips are rare among the candidates.
- Generated parts (`construction_plan.py`, finalize): farm/kitchen/tavern/granary/logistics pickers, 226 producers of 75
  goods, per-good values, the Goods tab rows. Tests: `tests/test_construction_plan.py`.

## Not built yet (from the mock-up and this doc)

- Lines for the food rule in the window (Jan 2026-11-09: "I'll take a look at that later"); its numbers are the
  `[construction_plan]` defaults.
- "Next from the plan / blocked by" per location; pins per building.
- Upgrades rule group.
- Not exercised in game: multiplayer, a long run of the business rule in a full world (cost not profiled there).
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
