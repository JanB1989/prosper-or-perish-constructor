# Player Construction Manager: design brainstorm

Status 2026-11-09: **two tabs** (Jan: "global settings that are very easy to set, and then our profiles, and that's
it"), branch `location-profiles`; since 2026-11-10 a third tab and a sixth rule group, **Towns and Buildings**; see the
next section. The sections below it are the history (v1, v2, the first
2026-11-09 pass); what they describe and the next section no longer lists is gone. Player-only: the AI keeps its own
logic and is never touched (a console-only test switch lets it run for an AI country in the test world).

## Script time (2026-11-10, Jan: "The monthly pass takes 0.4 seconds. That is substantially too long")

Jan: "We don't have to have this on a monthly pass, could be yearly as well, but you have to fix the performance
issues. It needs to be built so that it doesn't use unnecessary script time ... some kind of sampling or clever use of
saving information." Measured in the plan test world (Castile owns Iberia: about 330 locations, 4 markets) with the
script profiler: 0.32-0.39 s a pass, 0.20 s of it the business pick. Not profiled since the rework: the numbers below
are counts of what the script evaluates, taken from the generators (`tests/test_construction_plan_cost.py`).

**Where the time went** (L owned locations, P provinces, T = 224 business types, B ticked public buildings, every
month):

| part | evaluations a pass, before | at L = 330 |
| --- | --- | --- |
| business pick | L sites x T types: the country's mark, then workers and `can_build_building` for every type the country can build; plus one market count (a walk over the market's locations and their buildings) per market and good a pick asked for | 73,920 type checks |
| business order | L locations ordered by a value | 330 |
| logistics, improvements | 2 walks over L, each with an order | 660 |
| Towns and Buildings | B walks over L (one per ticked building), 1 walk over every building of every location (upgrades), 2 over L (towns, cities); the rights on top | up to 42 walks |
| food | P provinces x the store a year from now TWICE (the order and the rule; each walks the province's locations several times); every farm site's best line twice | |
| Locations | every location with a profile or marks | |

**Options looked at** (web: Paradox's own modding advice is general: cheap triggers first in a limit, on_actions and
rare pulses instead of polling, variable lists to keep a target list and `ordered_` to score it; nothing specific to
caching. The rest is from the structure above.)

- *a. Businesses top-down, per market.* Rank the types at the market's prices, then look for sites only for the best
  few goods. Cost M x T + a few x L per market. Not chosen: a location's output modifier (World Builder attribute
  rows) moves a good's profit by tens of percent, so a market-level rank picks the wrong goods for many locations,
  script has no way to sort 224 named values but K rounds of 224 comparisons, and it needs a second copy of every
  recipe estimate at market scope. The same saving comes from c + b with the existing exact per-location estimate.
- *b. Remember what rarely changes.* Chosen in this form: a site's best business (type, return, cost) stays on the
  location; what a group saves for stays on the country until its next look; the market limit's counts stay on the
  market centres between two counts; the country's part of the business can-build check is asked twice a year. Not a
  per-location list of candidate types: `can_build_building` cannot be split into its static part, so the list would
  be as stale as the pick it feeds.
- *c. Slices.* Chosen for the one walk that scores (the business pick): a fixed few sites a pass, in a fixed order.
- *d. Cheap exits.* Chosen: between its looks a group walks nothing; when it saves for something and its purse can pay,
  it goes back to that one place. The "how much is missing" count is taken at looks only, and for the businesses from
  the stored picks it tries.
- *e. Rhythm per group.* Chosen: every group looks in its own months.
- *f. Order of checks, nothing twice.* Chosen where it was wrong: the store a year from now once a province, the farm
  lines' returns once a site; the limits already ran cheap checks first.
- *g. The upgrades rule.* Its walk over every building stays, but twice a year instead of every month; remembering
  researched successors was not needed for that.

**What was built.** The pass still runs every month, but it is cheap:

- *Every pass:* the purses fill (arithmetic, no walk); the business group works out the best business of the next few
  sites (`pp_cplan_business_refresh`: every owned location has a number in the order the plan first saw it,
  `pp_cplan_seq`; a pass takes the numbers after the country's place, `pp_cplan_cursor`, a window's worth,
  `pp_cplan_bz_window` = `[construction_plan] business_sites` (16), or as many as it takes to see every location
  within `business_cycle_months` (24); the pick stays on the location). One walk over the owned locations with two
  comparisons each finds the few.
- *A group looks only in its months* (`look_months`, trigger `pp_cplan_looks_<name>`): food 1, 4, 7, 10; logistics 2,
  5, 8, 11; improvements 3, 9; Locations 3, 6, 9, 12; Towns and Buildings one rule a look: upgrades of buildings 4,
  10, ticked buildings 6, 12, towns and cities 2, 8; urban rights 5, 11. At a look a group does what the monthly pass
  did: walks what it wants, best first, builds what its purse pays, saves for the first thing it cannot pay
  (`pp_cplan_look_<group>`).
- *The business group's look* (`pp_cplan_look_business`): the stored picks ranked by payback including the time to
  save; the best `business_tries` (6) are tried, each site working its pick out afresh first
  (`pp_cplan_business_here`), so nothing is built on a stale estimate. While the group does not save it looks every
  month, while it saves only in its look months (1, 7).
- *Between looks* (`pp_cplan_group_target`): a group that saves for something does nothing until its purse can pay;
  then it goes back to that one place and runs its rule there again (the province's food rule, the location's
  logistics or improvement rule if it still holds, the site's business pick, the location's profile rules and marks,
  the town or city upgrade or the building for Towns and Buildings), with every guard of a look. Towns and Buildings
  does not look at all while it saves.
- *The market limit* counts what is under construction afresh in its months only (1, 4, 7, 10); between them the
  counts stand on the market centres, raised by what the plan itself starts.
- *The window:* a group's numbers, its list and what it saves for are its LAST LOOK's and stay until its next look
  (`pp_cplan_stats_reset_<why>` in `pp_cplan_group_start`; `pp_cplan_now_<why>` marks who looked in this pass, for the
  hand-on and the chart, whose months without a look show nothing). "Built at the last looks" lists every group's.

**Counts after, at L = 330:**

| part | evaluations a pass, after | change |
| --- | --- | --- |
| business pick | 16 sites x T = 3,584 type checks every pass; a look adds at most 6 sites (1,344) | 73,920 -> 3,584 to 4,928: 15 to 20 times fewer |
| walks over the owned locations | every pass 1 (the business turn: two comparisons a location); a look adds its own: business 2 (has a pick?), logistics 1, improvements 1, a ticked building 1 each, upgrades 1, towns and cities 2 | a year: about 540 -> about 126 with every public building ticked, about 70 -> about 50 with none |
| food | P provinces x the store a year from now once, 4 times a year | 24 P -> 4 P a year |
| market counts | a market and good once a quarter | was once a pass |
| between looks | a group that saves: 3 comparisons; when its purse can pay: one place | was the whole walk |

A pass without a look is the purses, one cheap walk and 16 site picks: by the measured 0.20 s for 330 sites about
0.01 s. The worst passes are the look months (month 4: food and the upgrades of buildings; month 6 / 12: the Locations
group and every ticked public building); with every public building ticked that walk alone is 39 x L cheap limits.
The cost of a pass no longer grows with L x T: the sites scored a pass are max(16, L / 24).

**What changes for the player:** each rule group looks at the country a few times a year instead of every month, and
the best business of a location is worked out once every L / 16 months (about 21 months in a 330-location country,
at most 24); what a group saves for is built in the month its purse can pay. The window's numbers are those of each
group's last look. Said in the plan's tooltip (`PP_CPLAN_MASTER_TT`) and the budget note of every rule tooltip.

**For the profiler** (console; each runs a pass with only that look, whatever the month):
`effect c:CAS = { pp_cplan_test_empty = yes }` (purses and bookkeeping alone), `pp_cplan_test_business_refresh`,
`pp_cplan_test_business_look`, `pp_cplan_test_food`, `pp_cplan_test_logistics`, `pp_cplan_test_improve`,
`pp_cplan_test_profiles`, `pp_cplan_test_country` (its three rules at once), `pp_cplan_test_rights`; the whole pass:
`effect c:CAS = { pp_cplan_run = yes }`. The test mode (`pp_cplan_ai_test`) is unchanged.

Not tested in game. Open: the business group's first cover of a country takes the cycle (21 months at 330
locations); a ticked-everything Towns and Buildings look is the dearest single walk left.

## Budgets that save (2026-11-10, Jan, after he watched the plan run in game)

(Since the script time rework above a group "looks" a few times a year; where this section says "each pass" for a
group's walk, read "each look". What a group saves for stays until its next look, and a group hands on only in a
pass in which it looked.)

Jan's three problems: (1) "it is disproportionately favoring cheap buildings: the part of the budget that is left
sometimes cannot even build expensive buildings, so it just builds cheap ones"; (2) "if it detects that some building
is profitable, like horses, it spams 500 buildings of that type, which will likely crash the market ... the user would
not expect that it suddenly builds 500 buildings for horses just because some random influx of money came in"; (3)
"maybe we can allocate a construction budget for each of the branches, and the budget cannot go below the floor we
already set. It needs to be clean and easy to understand, I don't want to overwhelm them with settings; all of this
needs to happen under the hood in a sensible manner." No new setting in the window.

**Causes.** Every pass offered all the gold above the reserve anew (`pp_cplan_pot` / `pp_cplan_cap`), nothing was saved
from month to month, and a group walked past what it could not pay for and built whatever cheaper thing fitted. The
business group scored every site at today's price and built all of them while gold lasted; it never counted what was
already under construction.

**A. A budget per rule group that saves (its purse).** Country variable `pp_cplan_purse_<why>` (+ 100), readout
`pp_cplan_purse_n_<why>`. At the start of each pass (`pp_cplan_purses_fill`): free = max(0, gold - reserve); a group
that does not count this pass (weight 0, the Locations group without a profile or mark, Towns and Buildings with
nothing ticked) loses its purse; when the purses together exceed free (the player or a war spent the gold) they all
shrink by free / total; then the gold in no purse yet is shared among the counting groups by their weights.
`pp_cplan_pot`, `pp_cplan_cap`, `pp_cplan_share_<group>` and `pp_cplan_budget_left` are gone; a group "had" its purse
(`pp_cplan_dhad_<why>`). A construction is affordable only when its cost fits in the purse of the group that builds
it (`pp_cplan_affordable = { why }`; also in the gold above the reserve, whatever happened since the pass began);
after it starts the purse falls by what was really paid, never below 0 (`pp_cplan_purse_pay`). The town and city
upgrades of Towns and Buildings pay from the same purse by the same rules. The arithmetic sits in generated script
values of the state as it stands (`pp_cplan_purse_kept_` / `_new_` / `_next_<why>`, `pp_cplan_purse_held` / `_rest`);
the effect reads every new amount first and writes afterwards, so one group's change never reaches another's sum.
`tests/test_construction_plan_budget.py` evaluates them offline (`script_eval.py`).

**B. Best pick first.** Each group goes through what it wants in its own order of importance: food the hungriest
province first (`ordered_province` over the country's provinces by `pp_cplan_food_order` = minus the store a year from
now; the engine has that ordered iterator, so no workaround was needed; it costs one more reading of the store a year
from now per province), logistics the most urgent location, improvements the fullest, Towns and Buildings its own
order (upgrades of buildings, the ticked buildings in the tab's order, towns, cities), the Locations group as before
(its location order, each location's rules then its marks). The first thing a group wants and cannot pay for becomes
what it saves for (`pp_cplan_note_wait`: `pp_cplan_save_cost_<why>` + 100, `pp_cplan_save_loc_<why>`,
`pp_cplan_save_type_<why>`; for a town or city upgrade `pp_cplan_save_rank_107` = 101 / 102 instead of a type), and
from then on the group builds nothing more in this pass, even things that would fit (`pp_cplan_saving`); they are
still counted as wanted, so the pane's "how much investment is missing" stays. Things stopped for another reason
(cannot be built, no workers, construction goods missing, the market limit) are skipped and are not what it saves
for. What a group saves for is found afresh every pass (the fill clears it); only the gold is kept.

**C. Businesses rank by payback including the time to save.** `pp_cplan_bz_order` (location scope, a site with a
pick): the pick's payback in years (100 / its yearly return) plus max(0, cost - purse) / (12 x the gold the group
received for this pass); with nothing coming in, a pick the purse cannot pay ranks behind every pick it can. "Received
for this pass" (`pp_cplan_in_<why>`) = the group's part of the gold in no purse plus what was handed on to it at the
end of the last pass (E), since that is how fast it really saves. The picks are built in that order while they fit;
the first that does not fit is what the group saves for. The player's line ("pays back within N years") still reads
the plain payback. The group does not look at all while it has neither gold saved nor gold coming in.

**D. A market limit against spam, in one place.** A level of a building whose main good G is a market good starts
only while, in the location's market, the output of G under construction (every level under construction there of
the buildings whose main good is G, whoever started them, at that building's recipe output a level:
`pp_cplan_uc_here_<good>`, `pp_cplan_uc_market_<good>`) plus this level's output stays within `[construction_plan]
business_market_share` % (10, Jan's placeholder) of the market's monthly demand for G (`goods_demand_in_market`);
with nothing of G under construction one level is always allowed (`pp_cplan_market_room = { g out }`,
`pp_cplan_mroom_<good>`). The ONE place: `pp_cplan_construct_scoped` asks through the generated dispatch
`pp_cplan_market_do = { do = gate }` for the rule groups of `MARKET_LIMITED` (`pp_cplan_limits_market_<why>`: the
Businesses group, and the Locations group = profile rules and marks; decided: not the food rule, which builds for
hunger, nor Towns and Buildings, whose ticked buildings the player asked for everywhere). The business pick asks the
same trigger (`pp_cplan_business_take`), so a site moves on to its next best good. "Under construction" is counted
once per market and good per pass, only when a pick needs it (`pp_cplan_market_load`), kept on the market's centre
location (`market.location`; `pp_cplan_uc_<good>`, + 100), raised when the plan starts a level (`pp_cplan_market_do =
{ do = add }` in `pp_cplan_construct_now`, for every group) and cleared at the pass's end (the country's list
`pp_cplan_markets` of those centres, `pp_cplan_markets_clear`). Not on the market itself: **a market scope holds no
variables** (in game 2026-11-10: "This scope doesn't support variables. Scope: Market Burgos Market", about 2,000
error lines a pass, the limit never held and 81 Stud Farms started in one pass, 39 of them in the Burgos market,
which asks for 11 horses a month). With the count on the centre location the same influx of 50,000 gold started 4
Stud Farms, one or two a market; `every_location_in_market` in a script value and the macro in the effect name
(`pp_cplan_market_$do$_good`) both work. A pick stopped by the limit is not waiting for gold: it is counted apart
(`pp_cplan_dml_<why>`, the Businesses pane: "passed over because their market already has enough of that good on the
way"); a profile rule or mark stopped by it gets the new state 10 (`PP_LPROF_ST_10`; fail code 106, the gold code
moved to 107).

**E. Handing on.** At the end of the pass (`pp_cplan_purses_hand_on`) every group that ran and saves for nothing gives
what is left in its purse to the groups that do save, by their weights (next month's money; `pp_cplan_hand_<why>`
keeps what each got, for C). While no group saves, the purses stay as they are.

**In game (2026-11-10, second round; test world, Castile, about 25 passes).** The pane's "saving for Hospital in
Sevilla: it has 108 of 175" names building and location; with 108 gold the group started no Windmill (59) until the
Hospitals were paid. Purses add up to gold minus reserve to the gold piece, shrink in proportion when gold is taken
away, and a group at weight 0 holds none. Food went through its provinces by the store a year from now (2.6, 3.6,
4.7 months). An influx of 50,000 gold: 111 constructions the first month (Cookshop 45 and Granary 26 by the food rule,
one a province; 30 businesses of 14 types, at most 4 of one), 35 and 11 the next two; before the market limit's fix
(D) the same influx started 81 Stud Farms. Twelve months at about 280 gold a month with all six groups counting: 60
constructions, Locations 23, Businesses 19, Food 16, Logistics 2; Businesses does not take everything. A group
that got gold handed on after it chose what to save for shows "it has 86 of 47" until the next pass. The pass costs
0.32 to 0.39 s in the script profiler there (the business pick over 330 sites 0.20 s of it; the 0.036 s of
2026-11-09 was before the Businesses group existed).

**F. The window.** Each rule group's row shows what the group has saved beside its share (the weight bar's last
number; the window is 68 px wider for it); its tooltip and every rule tooltip end with the same two sentences on the
budget (`PP_CPLAN_BUDGET_NOTE`); the cog pane says what the group saves for and how far it is ("it has N of M gold").
The texts of the old "this month's gold" are reworded. The month rotation of the group order stays: it now only
decides who gets a free construction slot of a location first.

**G. Construction goods.** A thing the market lacks the construction goods for is counted per group
(`pp_cplan_note_goods`, `pp_cplan_dgo_<why>`) and shown in its pane ("N were held back because their market lacks the
construction goods"): the food rule's capital buildings and Victualling Yard, logistics, improvements, the business
pick (a site that passed a better business over), and Towns and Buildings (ticked buildings, upgrades of buildings,
town and city upgrades: the goods check moved out of the location filters into the body, the same locations are
walked). The "first that can be built" pickers still pass a building over that lacks its goods (a Carrier Inn where
the River Boatmen's Yard lacks naval supplies) and count only when nothing was built. The Locations group shows them
as its rule state 8, as before. Not counted, because it would take another walk: the food rule's farm step (a farm
line the market lacks the goods for has no return and is never picked).

Not tested in game. To check there first: the pane's "saving for" line (`Var(...).GetBuildingType.GetName` /
`.GetLocation.GetName` on a country variable), `every_location_in_market` inside a script value and the cost of the
market count, `ordered_province`'s order (hungriest first), the purse arithmetic over a few months (the saved gold
beside the bars), and the pass's cost now that the business group looks whenever it has gold saved or coming in.

## Two tabs (Jan 2026-11-09, evening), three since 2026-11-10

- **The window** (`in_game/gui/pp_construction_plan.gui`, vanilla main tabs): **Global Settings**, **Location
  Profiles** (the profile editor, type `pp_lprof_editor_tab` in `pp_location_profiles.gui`; every opener of the old
  editor window opens this tab: `docs/location_profiles.md`) and **Towns and Buildings** (GUI variable `pp_cplan_tab` =
  `country`; the settings of the rule group of that name, type `pp_cplan_country_tab`, hosted the same way; the type,
  the group's effect `pp_cplan_group_country` and `pp_cplan_country_rights` are `construction_plan_country.py`'s).
  Nothing else.
- **In-game test 2026-11-10** (test world, new game as Castile, seven monthly passes over two sessions; the engine
  facts and what each rule did are in `docs/construction_plan_country.md` and `docs/location_plan.md`): the three tabs,
  the six panes and every rule ran; no plan line in `error.log` from a load or a pass. Fixed from it: the ledger per
  rule group (below), the rights' rows in the scroll area, the cut tile line of "Also build here", the - / + buttons
  of the three lines without a tooltip, and the panes' "did not run" texts (they said "its bar is empty" for a plan
  that was off and for Towns and Buildings with nothing switched on). Script time, profiler self times at 30 frames
  a second: the location window 4.3 ms a frame, its Infrastructure tab 1.3 ms more, 0.7 of them the Profile and
  "Also build here" rows (7,300 script calls a frame); the Towns and Buildings tab 0.07 ms, Global Settings 0.10 ms.
  Frame time 33.4 ms (the 30 frames cap) in every state, paused and running.
- **Maintenance 2026-11-10**:
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
    `pp_cplan_log` / `pp_cplan_log_107`, the location's `pp_cplan_log_rank`, `pp_cplan_log_cost_107`, `_step_107` 2,
    no building type) and the lists name it (type `pp_cplan_rank_upgrade`, "Upgrade to a higher Location Rank");
    nothing shows blank.
  - *The ledger is per rule group and location* (in-game test 2026-11-10). A location with two construction slots
    gets two constructions in one pass, from two groups (Valladolid: a business and a building upgrade) or from one
    (an upgrade and a Library). With one line per location the window named both buildings under both groups, with
    the later group's cost and reason, and a Tools Workshop upgrade next to a Cookshop read "Upgrade to a higher
    Location Rank". So each group keeps its own entry of a location: the list `pp_cplan_log_types_<why>`,
    `pp_cplan_log_cost_<why>` (its gold there, two constructions added up), `pp_cplan_log_val_<why>`,
    `pp_cplan_log_step_<why>` (`pp_cplan_construct_now`; cleared by `pp_cplan_log_clear = { why }` at the next pass;
    read through `pp_cplan_log_<name>_<why>_n`). The "Last month" list is generated (`pp_cplan_last_list`,
    construction_plan_detail.py): a line per rule group and location, the groups in the window's order. Two
    constructions of one group in one location stay one line: both names, the gold of both, the later one's reason.
  - *One place says when a site is free:* the scripted trigger `pp_cplan_site_free` (`num_civil_constructions <
    pp_cplan_site_slots`, the location's `max_constructions_at_same_time`). The construction itself, the business
    sites, the food rule's farm sites and the logistics and improvement groups ask it; no other plan script reads the
    count (a test checks). In game 2026-11-10 (test world): nine locations have two slots, and the first pass started
    two constructions in each of the nine. The farm step now takes its sites only among free locations: a busy one among the four
    best used up a try and built nothing, and the province went on to a Tavern although it could farm.
  - *Worker check* (`pp_cplan_staff`): the idle pops of a building's own class are read through one generated value
    per pop type (`pp_cplan_idle_<pop type>`, the type written out as vanilla writes the call). With the pop type
    passed into the quoted call (`"unemployed_pops_of_pop_type_in_location(pop_type:$type$)"`) the trigger logged
    "Script system error! ... trigger [ pop_type ]" about 2,000 times a session (Jan's game, 2026-11-10); no vanilla
    file puts an argument inside quotes.
  - *A pass without gold is cheap for the business group* (since the budgets that save: while it has neither gold
    saved nor gold coming in)*:* its pick (every free site against every business type)
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
- **The gold:** no limit on the number of constructions. Until 2026-11-10 a pass could spend all the gold above the
  reserve anew each month, a part per group that passed on to the next group; since then every group has a budget
  that saves ("Budgets that save" above). No construction takes the treasury below the reserve:
  `pp_cplan_construct_scoped` prices the level with the engine's formula (`pp_cplan_btype_data`, `pp_cplan_est_cost`)
  and starts it only when it fits in its group's purse and in the gold above the reserve (`pp_cplan_affordable`).
  The groups' order still turns with the month (six groups since 2026-11-10: every group goes first twice a year);
  it now only decides who gets a free construction slot first.
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
  history `pp_cplan_hn_` / `_hs_<why>_<k>`, generated `pp_cplan_stats_reset_<why>` (at the group's look since 2026-11-10) / `pp_cplan_history_push`); switching the
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
