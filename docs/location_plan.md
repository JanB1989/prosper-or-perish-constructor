# Location plans

Branch `town-plans` (now `0.11`), 2026-11-19, Jan: the one per-location decision of the Construction Plan is a
**plan**. "This location is for lumber." Player-only; the AI never sets a plan. Since 2026-11-21 a plan is a plain
marker on the location and no town right (Jan: "We just use our plans, and the plans apply the relevant town rights if
the setting is turned on"; from 2026-11-19 to 2026-11-20 every plan was a town right `pp_plan_<plan>` without
conditions or bonus). What a plan does did not change. **Tested in game** 2026-11-20 as town rights (sections "Tested
in game (2026-11-20)" and after, three rounds) and 2026-11-21 as markers ("Tested in game (2026-11-21, plans as
markers)"), in the Construction Plan test world as Castile; the engine behaviour further down that the tests did not
touch comes from a static reading of EU5 1.4.9.

It replaces the Location Profiles (slots with ordered rules) and the Location Plan marks (goods marks and building
marks), which are gone (history: `docs/location_profiles.md`, and this file's history in git before 2026-11-19).

## What the player does

- **Location Plan window** (`gui/pp_location_plan.gui`): opened by the plan button in the location window's header
  (player-owned locations, not observers) or the round button of the Plans row. A picker of every plan, grouped
  (Farming, Forestry, Gathering, Hunting, Manufactured goods, Mining, then "Food and trade"); one click sets a plan, a
  second click takes it off. Planned tiles are pressed. Clear takes every plan off the location; "Show on map" switches
  to the map mode. A good no building makes (fur) is shown dimmed and cannot be planned.
- **Plans row** on top of the location window's Infrastructure tab (`town_plan_gui.py`): the plans the location holds
  as pressed tiles (a click takes one off), each tooltip with what the plan does and how its last check went; past 11
  tiles the title gives the count. The round button opens the Location Plan window.
- Any owned location, rural settlements included; several plans per location. A plan stays until the player takes it
  off, or the location changes owner (below).
- A plan is not a town right: it does not show in the game's town rights list of the location, takes no rights slot,
  has no colour in the town-rights map mode and sends no town rights message. The charter and rights a plan grants
  are real town rights and show as such.

## How a plan is kept

77 plans (`town_plans.py`): the 75 goods that have a forced goods target (their producers) plus `food` and `trade`.
Since 2026-11-21:

- **The marker**: location variable `pp_tplan_p_<plan>` = the location holds the plan. Set and removed only by the
  mod: scripted GUI `pp_tplan_toggle` -> effect `pp_tplan_flip = { g = <plan> }`
  (`scripted_effects/pp_location_plan.txt`). A plan taken off takes its state and payback along. The GUI tests a
  held plan with `Location.MakeScope.Var('pp_tplan_p_<plan>').IsSet`.
- **`pp_tplan_any`** (location variable): set while the location holds at least one plan; trigger `pp_tplan_held`
  reads it. `pp_tplan_flip` asks the generated `pp_tplan_held_scan` (every marker) after it took a plan off and drops
  `pp_tplan_any` when none is left.
- **The country list `pp_tplan_locs`**: the country's planned locations, each once, kept by `pp_tplan_flip` (added
  with the first plan, removed with the last). The Locations look (`pp_lprof_gather`) and the charter look
  (`pp_cplan_country_plan_grant` / `_upgrade`) walk this list. Why a list: script has no iterator over the locations
  that carry a variable (before, `every_locations_with_town_rights_in_country` found them through the plan right).
  `pp_lprof_gather` first sweeps the list: entries the country no longer owns or that hold no plan come off.
- **Owner change**: a location that changes owner loses its plans. On_action `on_location_changed_owner`
  (`on_action/pp_construction_plan.txt`) -> `pp_tplan_owner_changed` -> `pp_tplan_owner_changed_effect`: the location
  comes off `scope:loser`'s list, what that owner's Locations group saved for it is released, and the generated
  `pp_tplan_strip` removes every marker, state, payback, `pp_tplan_any`, `pp_lplan_wk`, `pp_lplan_last` and
  `pp_tplan_cwait`. Until 2026-11-21 the engine did this through the right's `kept_at_conquest = no`. The sweep of
  `pp_lprof_gather` strips a lost location's plans that are still there only where the new owner is no player (a
  location another player owns keeps that player's plans).
- **What went with the rights**: the rights file, their text and the 77 icons (`town_plans.apply` deletes leftovers,
  `stale_paths`). No entry in the town rights list, no slot, no colour, no message.

## What the Construction Plan does with a plan

The rule group **Locations** (internal key `profiles`, construction code 105, its own purse and weight on the Global
Settings tab; it counts for the weights only while a location holds a plan) gives each location with a plan its turn
at its looks (months 3, 6, 9, 12; between looks only the location it saves for). The locations take turns from a
cursor (`pp_lprof_look`, `pp_lprof_turn`). In a location's turn every held plan runs its target, **forced** by
default: no payback limit, no market limit. Still needed: the can-build check, free workers, the construction goods in
the market (12 months of the draw), a free construction slot (one construction at a time in a location) and the
group's purse; by default also no level for a standing building that loses money (see "Plan settings"). Inside one
location the plans take turns by default; the first construction ends the location's turn (the others wait, state 9).
Plans add: they switch no global rule group off.

- **A good**: its producers (the buildings whose main good it is). Order: an older tier standing here whose successor
  (also a producer) the country has researched is upgraded first (the game's Upgrade, one level a turn); else a
  standing producer gets one more level, highest tier first; where none stands, the cheapest producer that can be
  built here starts. Since 2026-11-20: once every standing building of the plan is at its highest level and nothing
  else holds it back (the best reason is exactly "at its highest level"), the plan starts another of its buildings,
  never one standing here or an older tier of one (`pp_lprof_more`, `successors()`); the plan then shows why that
  start waits, and reads "nothing to build" where nothing can start.
- **Food** (2026-11-20, `pp_tplan_do_food`, `town_plans.py` `render_food_turn`): farms first: the staple food
  producers (`pp_lprof_t_food_farms`), a new one being the farm with the best return here by the food rule's own
  measure (`pp_cplan_farm_roi_<type>`, `pp_lprof_start ... how = roi`). Only where the farms have nothing to do (all
  at their highest level, or none can be built) the kitchens (Cookshop, Public Kitchen; their cap follows the
  province's farms), and a Tavern only while the province's store is short by the food rule's line
  (`NOT pp_pclose_store_ok`: `pp_lprof_t_food_kitchens_taverns`, else `pp_lprof_t_food_kitchens`). Never a Grange,
  Victualling Yard or Granary. Before, one flat list: a standing Tavern kept farms from starting and got levels
  whatever the store held. The plan's building list for the closer, the settings card and the picker is unchanged.
- **Trade** (2026-11-20): the buildings that carry trade, `[construction_plan] trade_plan` in `constructor.toml`, in
  start order: the Marketplace line, the Port Authority, then the market centre's buildings. Where none stands, the
  first in that order that can be built starts. No Hired Labor Yard, Smuggler's Cove or unique building (before: every
  building of the category, the cheapest first).
- **Rank raise**: for the 15 plans whose producers all need a town or a city, where none of them stands and the rank is
  too low, the turn raises the rank one step instead (`pp_tplan_do_<plan>` -> `pp_tplan_raise` ->
  `pp_cplan_country_rank_up = { rank n why = 105 }`, the Towns and Buildings upgrade, paid from the Locations purse).
  The game charges the upgrade itself; it is booked only when gold was paid. Where the raise cannot start (only
  conquered, a modifier forbids it, too few people for the rank, the game refused) the plan's state is 11; where the
  purse cannot pay, the group saves for the raise (`pp_cplan_save_rank_105`).
- **Charter and rights** (`construction_plan_country.py` `pp_cplan_country_plan_rights`, in every rights look of
  Towns and Buildings, whether its rights switch is on or not): for the 18 goods with a specialization charter, a
  planned town (never a rural settlement) gets the charter when its conditions hold and a slot is free; once the rights
  it upgrades into are allowed, charter is swapped for rights (revoke + grant). Iron has rights and no charter and gets
  them directly. Normal influence prices (grant, upgrade), the influence reserve is kept; one grant or swap a location
  a look (the rights look runs twice a year, in May and November). Details: `docs/construction_plan_country.md`
  "Plans: charters and rights". Since 2026-11-20:
  - The plan setting "Grant a plan's charter and rights" (`pp_tplan_rights_off`) stops every grant and swap of plans.
  - **A town's specialization follows its plans.** Where a plan's charter waits only because the town holds another
    specialization, that one makes way if its good has no plan here and its line has fewer levels here than the
    planned good's: it is revoked and the plan's charter granted in the same step, at the normal price, the reserve
    kept, never a revoke without the grant (`pp_cplan_plan_yield_<right>`, `pp_cplan_country_plan_make_way`). The
    game's regional rights and iron's rights never make way, and an iron plan replaces nothing.
  - **Why a charter waits** (`pp_tplan_cwait` on the location, written by the rights look where the line levels are
    reached: 101 political influence, 102 the other specialization stays, 103 no free rights slot, 104 the swap to
    rights waits for influence): the plan's tooltip in the picker and the Plans row says so, or names the charter or
    rights the location holds.
  - Taking a plan off keeps the charter it granted; that leftover makes way for a later plan by the rule above.

### States

Per plan and location after the last look, `pp_lplan_st_g_<plan>` (+ 100; texts `PP_LPROF_ST_<n>`): 1 started, 2
nothing to build (every producer at its highest level), 3 a construction under way here, 4 no free workers, 6 cannot be
built here, 7 gold (the purse cannot pay it, or the group saves for something before it), 8 the market lacks the
construction goods, 9 waiting for another plan's construction this turn, 11 needs a higher rank that cannot be raised
here now, 5 the next level pays back too slowly for the plan's payback limit, 12 the standing building loses money at
full staffing (no level), 13 the standing building is closed (no level; until 2026-11-20 this showed as 6), 14
another business here is being closed to free workers for it ("Plans free their workers" below). 10 (market
limit) never comes up for a plan. The Locations pane of the Construction Plan
window counts the plans by state, names what the group saves for (a building or a town / city
upgrade) and lists what it built: "for its plan", or a higher rank with the location's people.

**The look runs in daily slices** (2026-11-20, evening; tested in game, see the end of this section). It replaced "a look stops when the purse
is spent" (same day, morning; measured before that: the look of 615 plans on 418 locations took 0.197 s, 331 plans
ended in state 7), which kept the pass short but left the group without the gold its plans were missing, and a look
over thousands of plans in one day still froze the game (about 0.47 ms a location). Now:

- The look fixes its turn order once: every location of the look goes onto the country list `pp_lprof_todo` with its
  place (`pp_lprof_pos`). It walks K of them a day, K = max(`look_slice_min`, ceil(locations / `look_slice_days`))
  (`[construction_plan]`, 60 and 24; script value `pp_lprof_slice_k`): the first K on the look's day inside the pass,
  every further slice through the hidden country event `pp_construction_plan.1` a day later
  (`events/pp_construction_plan_events.txt` -> `pp_lprof_slice_event`). Up to 60 planned locations the whole look
  runs on the pass day, as before. The event does nothing but drop the list when the plan is off, the country no
  longer runs it or the group's weight is 0; it sets up what a turn reads outside a pass and fills no purse.
- The purse rule is unchanged: turn order, each location builds while the purse pays, the first thing it cannot pay
  is what the group saves for, after that nothing starts. But the walk goes on: a turn that begins while the group
  already saves is a *costing turn* (`scope:pp_lprof_costing`). Its plans run, so their states are set and the gold
  they want is counted (`pp_cplan_note_wait`), and nothing else happens there: nothing starts, no business is closed,
  the closer's wait does not count down, the location's mark `pp_lplan_wk` is neither set nor removed. A plan whose
  closing is already under way still reads 14.
- Nothing is "not reached" any more: every location of a look is walked within `look_slice_days`. A location the
  running look has not walked yet keeps the state of its last turn. The pane's counter `pp_cplan_ds_profiles_unr` now
  counts the look's locations still to be checked (0 once the look is done).
- The place in the turn order moves at the end of the last slice (`pp_lprof_look_end`), to just before the location
  the group saves for; a look that could pay for everything leaves it where it was.
- The Locations group hands its purse on (it saved for nothing) only after its last slice: at the pass's end while
  slices are pending it waits (`pp_cplan_gives_105` reads `pp_lprof_pend`), and the event's last slice hands on
  (`pp_cplan_purses_hand_on_105`). After every event slice the chart's month 1 takes the look's totals again.
- The console's `pp_cplan_test_profiles` still runs the whole look in one go (`pp_lprof_whole`: one slice, no event).

Inside a location the plans' two goes are split as the turn begins (`scope:pp_lplan_from`); the second go runs only
where a plan started the location's last construction. Details: `docs/player_construction_manager.md` "Script time".
Measured with the stop (in game 2026-11-20, 615 plans on 418 locations, first look on 1 June): the whole monthly pass
0.062 s (before 0.238 s), 62 constructions started, 4,769 gold spent, no script error in ten years.
Tested in game (2026-11-20, plan test world, Castile, 615 plans on 418 locations, 1337-1340): the first slice took 60
locations (418 / 24 is below the minimum); the June look walked 60 locations a day over seven days (still to be
checked 358, 298, 238, ..., 0), started 88 constructions while the purse lasted, then only counted (208 plans held
back for gold); `limit` inside `ordered_in_list` and the hidden event chain work; the forecast values evaluate as
specified: after three years with little gold coming in the window read Locations "short of gold, 8.3 years" (lacking
27,174 gold at 272 a month), Food 1.2 years, Logistics and Improvements "has the gold for all it asks for",
Businesses "keeping up"; no mod script error in the three years. Not tested: a look that overlaps a save and load, a
country with more than 1,440 planned locations (a slice above 60), multiplayer.

### In-game results of the night (2026-11-20, plan test world, Castile)

Plans were town rights `pp_plan_<plan>` then.

- **Impact, ten years, 615 plans on 418 locations** (every location its raw material, towns a manufactured good and
  Trade, province capitals Food; all rule groups at their defaults, +20,000 gold) against a control run without plans:
  the same total building levels (5,297 -> about 5,620) and population at the end; the country's gold is the limit in
  both, the plans decide where it goes and spend it sooner. 3 charters granted. No mod script error in any run.
  (The test country runs a deficit by itself and sits below the plan's gold reserve after the first years, so both
  runs stop building early: the comparison says "no harm", not "how much better".)
- **A bug the test found**: for one build every plan target did nothing, because the game compiles a scripted effect
  call that passes an argument the body never uses into a silent no-op (the message is only in debug.log and the load
  part of the rotated error logs). Fixed; `tests/test_script_call_arguments.py` scans the whole mod for it.
- **Plan settings** (same world, year ten, one look each): defaults: 466 plans held back for gold, 40 add no level
  because the building loses money (state 12), 69 wait for goods, 10 for workers; payback limit one year: 521 plans
  "pays back too slowly" (state 5); losses allowed: state 12 gone.
- **Plans take turns**: with the default, the first look started 62 constructions and the plans of one location
  alternate.
- **Plans free their workers** (plans on every town and village, only the Locations group funded, 60,000 gold): first
  look 421 constructions and 18 locations with one business closed each (Fishing Villages and Market Villages in
  villages with livestock and lumber plans; 23 plans in state 14); the next look closed nothing more (the wait), the
  one after 3 more. Switching the setting off reopened all of them within two days; taking the plans off eight
  locations reopened their eight buildings at once. The keep list after a reopen by hand: tested in the third round.

### Plan settings (2026-11-20, Jan; tested in game the same night, see above)

Baseline settings the player sees and may change (the settings tab of the Construction Plan window, agent G's
`town_plan_settings_gui.py`); the defaults are meant to be left alone. Country variables (0 counts as unset, never
stored), names and steps in `town_plans.py` ("Plan settings"):

- **Payback limit, all plans** (`pp_tplan_pb_all`: a step 1..12 of `PAYBACK_STEPS` = 1, 2, 3, 4, 5, 7, 10, 15, 20, 30,
  40, 50 years; unset = any payback, the default) and **per plan** (`pp_tplan_pb_<plan>`: a step, or 13 = any payback;
  unset = same as all plans). A held plan runs with its own limit, else the all-plans one, else none
  (`pp_tplan_set_pb` -> `scope:pp_lprof_pb`). A further level compares the standing building's payback (its current
  profit per level; no profit = too long). A first level and a tier upgrade compare the Businesses rule's estimate of
  one level of the new building (`pp_cplan_bz_est_<type>`, market prices, this year's harvest taken out) where it has
  one; buildings without one (Marketplace and the other trade buildings, Cookshop, Tavern, Grange, Victualling Yard)
  are not checked. Too long: state 5. While any limit is set (`pp_tplan_pb_some`) the location's turn takes the harvest
  first (`pp_cplan_business_harvest`).
- **Never at a loss** (default on; `pp_tplan_loss_ok` set = off): no level for a standing building with production
  methods whose profit at full workers and full goods is below zero (`building_potential_profit < 0`, building scope:
  the game lays off the workers of such a building every month, subsidised or not). State 12. Tier upgrades are not
  held back (the upgrade replaces the building). Only buildings with a production method that makes a good are
  checked (`makes_goods()`, since 2026-11-20): a Marketplace or a market centre's building only pays upkeep, so it
  always shows a loss and would never have got a second level.
- **Wait for free workers** (default on; `pp_tplan_staff_off` set = off): further and first levels need workers here
  (`pp_cplan_staff`). Tier upgrades never asked for workers.
- **Several plans in one location** (default: take turns; `pp_tplan_order_best` set = best payback first, the old
  rule): the plans after the one that started the location's last construction (`pp_lplan_last`, location) go first,
  then the rest; no measuring go (`pp_lplan_location_marks_turns`).
- **Close other businesses for a plan's workers** (default on; `pp_tplan_free_off` set = off): see "Plans free their
  workers" below. Switched off, every building the rule closed opens again at once (`pp_pclose_undo_all`).
- **The game closes losing buildings**: switches the game's own automation `closebuildings` for the country
  (`set_automated_system`, read by `is_system_automated`). Default: as the player set it in the game. A plan never
  adds to a closed building (state 13).
- **Other businesses in planned locations** (2026-11-20; default on; `pp_tplan_alone` set = off, value
  `pp_tplan_alone_n`, GUI `pp_tplan_toggle_alone`): off, the Businesses rule builds nothing in a location that holds
  a plan; only the plan's buildings and the other rule groups' food, logistics, improvement and public buildings are
  built there. The gate sits in `pp_cplan_business_site` and in the Businesses look's limit.
- **Plans come first for their workers** (always, no setting): the Businesses rule builds nothing in a location while
  the rule frees workers there (`pp_pclose_wait`) or one of its plans waits for workers after its last look
  (`pp_lplan_wk`, set by `pp_lprof_finish` for state 4 or 14, removed at the location's next turn and with its last
  plan). Same two places, so a blocked pick takes none of the look's tries.
- **Grant a plan's charter and rights** (2026-11-20; default on; `pp_tplan_rights_off` set = off, value
  `pp_tplan_rights_n`, GUI `pp_tplan_toggle_rights`): off, plans grant no charter and no rights and spend no
  political influence; they only build.
- **Taking the last plan off a location** (`pp_tplan_flip`): `pp_lplan_wk` goes, and if the Locations group was
  saving for that location (`pp_cplan_save_loc_105`, a rank raise `pp_cplan_save_rank_105`) the saving is dropped at
  once (before: it stayed until the purse covered it or the next look).

Script values for the window (country scope): `pp_tplan_pb_years_all`, `pp_tplan_pb_years_<plan>` (0 = any),
`pp_tplan_pb_own_<plan>`, `pp_tplan_loss_n`, `pp_tplan_staff_n`, `pp_tplan_order_n`, `pp_tplan_free_n` (1 = the
default), `pp_tplan_close_n` (1 = automation on). Scripted GUIs (`scripted_guis/pp_town_plan_settings.txt`, player
only): `pp_tplan_pb_up` / `_down` (`scope:pp_key` = `flag:all` or `flag:<plan>`), `pp_tplan_pb_reset`,
`pp_tplan_toggle_loss` / `_staff` / `_order` / `_close` / `_free`.

### Plan options (2026-11-20 evening, Jan: "food and trade need other options ... for the goods some additional options, let us not go overboard"; NOT tested in game)

Ten options beyond the eight settings above. `town_plan_options.py` is the contract (`OPTIONS`: key, where it
shows, kind switch / cycle / stepper, the script value the window reads, the scripted GUIs, the player texts); the
script side is `town_plans.py`, the window side renders the list generically (`town_plan_settings_gui.py`). Every
default (no variable set) is the behaviour before the options existed, and each check sits behind a `has_variable`
guard, so the look costs nothing more at the defaults.

- **Lowest production efficiency** (all plans + each goods plan's own, like the payback limit; `pp_tplan_effv_all` /
  `pp_tplan_effv_<plan>` = a step of `EFF_STEPS`, -10 .. 75 %; a plan's own "none" = 14; guard `pp_tplan_effv_some`).
  A goods plan starts nothing (first level, further level, tier upgrade, rank raise) where the location's lasting
  efficiency is below the line: `modifier:local_production_efficiency` + the owner's
  `modifier:global_production_efficiency`, minus the short-lived ones (`EFF_SHORT_LIVED`: every efficiency event
  modifier the game adds for at most five years, and `raised_levies`; amounts read from the files at finalize). What
  belongs to one building alone (establishment, raw-material share, bonus per level) is not in it. State 15.
- **Raise a settlement for its plan** (default on; `pp_tplan_raise_off`): off, a plan whose producers need a higher
  rank shows state 11 and never starts or saves for the raise.
- **Food plan** (its card): staple food makers on / off (`pp_tplan_food_farms_off`), kitchens on / off
  (`pp_tplan_food_kitchens_off`), Taverns never / while the store is short (default, the rule before) / always
  (`pp_tplan_food_taverns` 1 / unset / 3), and "build only while the store lasts less than" (`pp_tplan_food_store`, a
  step of `FOOD_STORE_STEPS` 3 .. 24 months against `pp_location_stored_months`; default always).
- **Trade plan** (its card): Marketplaces, Port Authority and market centre buildings on / off
  (`pp_tplan_trade_market_off` / `_port_off` / `_centre_off`; with one off the turn runs the groups one after the
  other, `pp_tplan_trade_split`), and "build only while our trade capacity is used" (`pp_tplan_trade_use`, a step of
  `TRADE_USE_STEPS` 10 .. 90 %): market scope `used_merchant_capacity(country)` / `merchant_capacity(country)`, the
  syntax vanilla's market actions use; no capacity in that market counts as fully used. It holds the whole Trade plan,
  because every building of `trade_plan` adds merchant capacity (a test checks that).
- **States**: 15 "lasting production efficiency below the line" (fail 103.25), 16 "held back by this plan's options"
  (fail 102.75: the food store limit, the trade share, or every part switched off).
- Not verified without the game: that `has_location_modifier = raised_levies` sees the engine's static modifier, that
  the location's efficiency modifier includes province modifiers, the merchant capacity functions through
  `market ?=`, the script time with lines set. The five-year cut for "short-lived" is a choice.

### Plans free their workers (2026-11-20, Jan; tested in game the same night, see "In-game results")

Jan: "You conquer or get a city with a bunch of businesses the AI built, and you want to specialize it ... at some
point there is a worker shortage. Then, step by step, the other businesses that are not part of the location's plans
should be turned off in that location, so they release the workers ... automatically, probably by profitability."

**The rule** (`plan_closer.py`, hand-written `scripted_effects/pp_plan_closer.txt`, `scripted_triggers/pp_plan_closer.txt`,
`script_values/pp_plan_closer.txt`; called by the plan engine `pp_location_profiles.txt`):

- **When**: in a look of the Locations group, a plan's next level (a further level or a first level) waits for workers
  and for nothing else: its worker test fails (`pp_cplan_staff`) while a level fits under the max level, the market
  holds its construction goods, the group does not save for something and its purse can pay the level, and the plans
  are not being measured (`pp_pclose_may`). The candidate's reason is then 104.25 instead of 104 and the pop type its
  level needs is kept (`pp_pclose_worker_fail`, `_new` for a first level, which sets the cost temporaries only on this
  path). It counts only when it is the plan's best reason (no construction, no candidate stopped at goods, gold, rank):
  `pp_lplan_mark` then calls `pp_pclose_plan`. Player countries only, setting on, the Construction Plan on (the pass
  runs only then). Tier upgrades ask no workers and never close anything.
- **What**: ONE building per location per look (`pp_pclose_pick`: one ordered walk over the location's buildings), put
  on the country list `pp_pclose_now`, which the widget closes. Then the location waits (`pp_pclose_wait`, + 100): no
  closing in the next look, the second look after it may close again (the freed people need time to show as idle and
  to promote or demote; looks are every three months, so at most one closing per location every six months). A walk
  that finds nothing is not repeated in that turn (`pp_pclose_none`).
- **Which** (`pp_pclose_candidate`, building scope): the player's own, standing (level > 0), open, nothing under
  construction, with workers, not subsidised, producing (non-producers are public, military or capacity buildings);
  not a logistics building, an improvement or a public building of the Towns and Buildings group (every tier;
  generated `pp_pclose_never_type`); not a candidate of any plan the location holds, older tiers included (generated
  `pp_pclose_planned`); its workers peasants or the pop type the plan's level needs (the people the worker test counts:
  free peasants, or idle pops of the level's own type; generated `pp_pclose_pt_match`); a Province Food maker or staple
  food producer (the Food plan's buildings and the food rule's kitchens, taverns, granaries, granges, yards; generated
  `pp_pclose_food_type`) only while the province's store is not short by the food rule's own line (a normal year leaves
  at least `pp_cplan_hungry_months` a year from now, `pp_pclose_store_ok`; no store = short); never a type the player
  opened again by hand after the rule closed it there (`pp_pclose_keep`).
- **Order** (`pp_pclose_rank`): the walk takes the highest value first (the game's ordered lists do; the mod's turn
  order relies on it). Least current profit per worker first: `building_profit` (gold a month, now) over
  `building_employed_amount` (thousands), turned round and counted in hundredths; equal steps: more workers first. A
  building losing money goes before every earning one. Current profit, not potential: what loses money now is the
  cheapest to give up.
- **State 14** ("Closing another building here to free its workers for this plan"): every plan whose level waits only
  for workers while a closing here is under way (this look's or the wait after it). Where nothing can be closed the
  state stays 4. Counted for the Locations pane like every state (`pp_cplan_ds_profiles_st14`).
- **Memory**: the location keeps the building types the rule closed (`pp_pclose_types`, by type: a building cannot hold
  variables), the plans they are for (location variables `pp_pclose_for_<plan>`, read by the generated trigger
  `pp_pclose_for_held` and cleared by the generated effect `pp_pclose_for_clear`; until 2026-11-21 a location list
  `pp_pclose_for` of the plan rights) and the types the player opened again (`pp_pclose_keep`); the country keeps the
  locations (`pp_pclose_locs`).
- **Undo**: when no plan the closings are for is held any more (the plan button and Clear: `pp_tplan_flip` ->
  `pp_pclose_plan_off`, at once; or the monthly check), or the setting is switched off, every closed building of those
  types goes on the country list `pp_popen_now`, which the widget opens; the location forgets its closings (the keep
  list only once it holds no plan at all).
- **Monthly check** (`pp_pclose_month`, first thing of `pp_lprof_run`): both widget lists are emptied (no entry
  outlives a month: a destroyed or lost building just drops out, nothing stale after a load), then each location with
  closings: lost (owner change; the game opens every closed building of a location that changes owner) -> forgotten;
  setting off -> undo; a closed type whose building is open again (the player, or the game refused the close) -> keep
  list, not while the game's own close-buildings automation runs (it may have reopened it, a 25 % roll per pass); no
  plan left it is for -> undo.

**The mechanism** (script cannot close or open a building): a building scope can sit in a country variable list.
The hidden scripted widget `pp_plan_closer` (`gui/pp_plan_closer.gui`, registered in
`gui/scripted_widgets/pp_plan_closer.txt`), always present for a player who plays a country and never for observers,
has a datamodel over each list; each listed building gets a hidden item widget whose `_show` state runs when it turns
visible (open and closable / closed and openable) and calls the game's own `CloseBuilding` / `OpenBuilding`, then the
scripted GUI `pp_pclose_ack` takes the building off both lists. Without that handshake a building the player opens by
hand while it is still listed would be closed again at once. The GUI passes `scope:pp_b`; a never-run block of
`pp_lprof_run` declares it (`pp_pclose_declare`).

**Free workers**: `pp_cplan_free_peasants_here` (the idle peasants minus the open jobs of the location's buildings)
counts only open buildings since 2026-11-20: a closed building hires nobody but keeps its employment size, so closing
one LOWERED the free count before. This is the correct count for both rule groups that read it: the Locations plans
and the Businesses rule now find more free peasants where a building is closed (by the player, the game's automation
or this rule); the Businesses rule still adds no level to a closed type.

**Proven in game on 2026-11-20** (prototype, console runs, no rule): a building scope goes into a country variable
list; the widget closed it at once, also while paused; the handshake took it off the list; `OpenBuilding` from the
second list opened it; a closed building reports `building_employed_amount` 0 and keeps its
`building_employment_size_amount`; `ordered_buildings_in_location` with `order_by`, `max = 1`,
`check_range_bounds = no` works on buildings; `is_opened`, `building_level`, `building_employed_amount` work in
building scope. The rule itself, the undo paths and the keep list were tested afterwards ("In-game results of the
night", "Third round"). **Not tested**: a building scope in a list across a save and load (the lists are emptied
monthly, so at most a month's entries), the freed people being hired by the plan's next level, multiplayer.

Side effect to know: while one building of a type is closed in a market, the game's AI (and the player's Buildings
automation) adds no new building or level of that type in that market.

## Cases thought through (2026-11-20, Jan: "what happens if I turn off a plan ... other cases")

- **A plan is taken off** (its tile, the picker, Clear): the location goes back to the global rules. At once: the
  buildings the rule closed for that plan open again (only those; a building the player or the game's own automation
  closed stays closed), the group stops saving for the location, the "waits for workers" mark goes, so the Businesses
  rule builds there again. What the plan built stays, a town it founded stays, and the charter or rights it granted
  stay: they are real rights the player paid influence for, the game's own revoke is the player's tool. Such a
  leftover makes way for a later plan's charter (below).
- **The whole Construction Plan is switched off**: plans are kept, nothing is built, and every building the plans
  closed opens again (`pp_cplan_toggle_on` -> `pp_pclose_undo_all`; the monthly check that would do it no longer runs).
- **Other rule groups in a planned location**: they keep building there (plans add). The Businesses rule builds its
  own buildings in a planned location when they pay, unless the setting "Other businesses in planned locations" is
  off. Always: a plan comes first for its location's workers. While a plan waits for workers there (state 4 or 14,
  location mark `pp_lplan_wk`) or a closing is under way (`pp_pclose_wait`), the Businesses rule builds nothing in
  that location, so it neither takes the people a closing freed nor builds what the plan would close next. Food,
  logistics, improvements and public buildings are not held back (a hungry province still gets its farm).
- **Budget**: plans are paid from the Locations group's purse (its weight on the Global Settings tab; it counts only
  while a plan exists) and nothing else: buildings, tier upgrades, rank raises. The country's gold reserve holds for
  it like for every group. One thing at a time is saved for; once the purse is spent the look only counts what the
  rest would cost (costing turns, "The look runs in daily slices" above). Closing and opening buildings costs nothing.
- **Political influence**: only the charter (the game's grant price) and the swap to rights (its upgrade price) cost
  influence, twice a year, plans before the global rights rule, never below the influence kept back on the Towns and
  Buildings tab. The setting "Grant a plan's charter and rights" stops plans spending any. A plan's tile says when its
  charter waits and why.
- **A town already specialized** (a conquered city keeps its charter, tested; a leftover of an earlier plan): the
  town's specialization follows its plans. The other specialization makes way for the planned good's charter once
  that good's line has more levels in the town than the other's and the other good has no plan there.
- **The location is lost**: every owner change tested takes the plans off (since 2026-11-21 the mod's on_action
  `on_location_changed_owner`, before the plan right's `kept_at_conquest = no`) and the game reopens what the rule
  closed; the rule's memory of the location is dropped at the next monthly check. Won back, it has no plans.
- **A building the player opens again** stays open (keep list, tested).
- **Several plans, too few workers**: plans never close each other's buildings; they take turns.
- **A plan whose good cannot be made here**: state 6, nothing is built, nothing is closed.
- Known and left: a tier upgrade goes one level a look (four a year); a plan may close a local producer of its own
  inputs (the order is profit per worker, so a paying supplier goes last); the game's own close-buildings automation
  may reopen or close buildings independently of the plans.

## Map mode

**Location Plan** (Economy menu, first row; `gfx/map/map_modes/pp_location_plan_map_mode.txt`, game concept
`pp_location_plan`): over each of the player's locations first one icon per held plan (77 icon widgets behind the test
of `pp_tplan_any`, each shown by its marker, tooltip `PP_TPLAN_MAP_<PLAN>`), then the location's real town rights from
the game's datamodel, at most 8, on a tile of another colour (vanilla's raw goods marker, patched by
`location_plan.py` in `gui/map_markers.gui`); a right's tooltip names the right. Until 2026-11-21 the plans were among
those at most 8 town rights. No legend: the map under the icons is the raw material map faded almost out. Engine
facts of the marker (in game 2026-11-07): the engine makes raw goods markers only with `color_mode = raw_material`;
with a color mode `map_color` and `tooltip_key` are ignored; marker types load only from the three
`map_markers*.gui`; a mod loaded after PP that overrides `map_markers.gui` hides the icons; a map mode's `index` is its
row in the category menu (economy shows rows 0-3).

## Engine behaviour relied on (static analysis of EU5 1.4.9; the owner change, the free script revoke and the old
saves' typeless rights were confirmed in game on 2026-11-20 and 2026-11-21)

These now matter only for the real charters and rights a plan grants:

- The script grant skips every check (potential, allow, slots, price) and can stack duplicates: every grant is guarded.
- Every held right counts against the location's slots (a plan holds none since 2026-11-21).
- A rank change revokes the rights above the slot count, newest first (inferred).
- An owner change keeps a real charter (in game: both script owner changes and making a country from the location).
- Every script grant and revoke sends the player the game's town rights message (a pop-up by the game's default; the
  mod switches the pop-up off, see "Known limits").

For the plans themselves:

- `on_location_changed_owner` fires for both `create_country_from_location` and `change_location_owner`, with the
  previous owner as `scope:loser` (in game 2026-11-21).
- A save's town right whose type no longer exists loads as a right WITHOUT a type: the game logs "Failed to read key
  reference: pp_plan_<plan>", the right stays on its location, counts in the rights counter and in
  `every_town_rights_in_Location`; `revoke_town_rights_of_type` cannot remove it ("unknown Type"), `revoke_town_rights =
  this` inside `every_town_rights_in_Location = { limit = { NOT = { exists = town_rights_type } } ... }` can (in game
  2026-11-21).

## Known limits

- One charter per town: the charters' own "one specialization" condition stays. Two charter plans in one town: the
  first granted stays; the location carries one wait reason, so the other plan's tooltip may show it too.
- A tier two steps old upgrades only while the middle tier can still be built (the upgrade goes to the direct
  successor).
- Plans are lost on every owner change, by design. Tested: `create_country_from_location` and `change_location_owner`;
  not tested: a peace deal, a country annexed.
- The game's "town rights granted / revoked" messages go to the message log without a pop-up
  (`main_menu/gui/messagetypes/pp_messagetypes.txt` redefines the two message types; the default opened a pop-up for
  every plan click while plans were town rights, and still for every charter a plan grants). This holds for every town
  right, the player's own grants too.
- Saves made before 2026-11-21 keep each former plan right as a typeless town right (it still counts in the rights
  counter) and lose their plans. The mod ships no cleanup (no old-save compatibility). For a running game a one-off
  console file outside the mod, `run pp_plans_restore.txt` (written by the kit's
  `pp_testing\townplan_test_20261120\gen_restore.py`), revokes the typeless rights in every location of every player
  country and sets the plans again from the plan states left on the location (`pp_lplan_st_g_<plan>`; a plan never
  looked at is not found). Tested on the old test save: rights 5 -> 0 and 4 -> 1, plans back.
- Several plans in one location: until 2026-11-20 the plan that paid back best was built first, a level a look (in the
  test Oporto's Tools Guild got every level for six looks while Cloth and Trade waited); now they take turns by default
  ("Plan settings"), the old rule is the setting "best payback first".
- While the Construction Plan is switched off, plans are kept and nothing is built; the Location Plan window says so
  and carries the switch.

## Code

- `town_plans.py`: the contract (names, the module docstring), `pp_tplan_held`, `pp_tplan_held_scan`,
  `pp_tplan_strip`, the rank raise, the plan settings; `stale_paths` (what the plan rights left in the mod folder).
- Hand-written `scripted_effects/pp_location_plan.txt`: `pp_tplan_flip` (marker, `pp_tplan_any`, the country list),
  `pp_tplan_owner_changed_effect`; `on_action/pp_construction_plan.txt`: `pp_tplan_owner_changed` on
  `on_location_changed_owner`.
- `location_plan.py`: the window's picker, the toggle and Clear, the tile texts with the state, the map marker patch.
- `town_plan_gui.py`: the Plans row.
- `location_profiles.py` + hand-written `scripted_effects/pp_location_profiles.txt`: the engine of the Locations group
  (targets, turns, measuring, states; `docs/location_profiles.md`).
- `construction_plan_country.py`: the charters and rights of planned locations; `pp_cplan_country_rank_up`.
- `construction_plan_detail.py`: the Locations pane.
- `plan_closer.py` (generated `pp_pclose_for_held`, `pp_pclose_for_clear` in
  `scripted_effects/pp_plan_closer_generated.txt`, the type lists) + hand-written `pp_plan_closer.txt` (effects,
  triggers, values, scripted GUI) and `gui/pp_plan_closer.gui`: plans free their workers.
- Tests: `tests/test_plan_closer.py`, `tests/test_town_plans.py`, `tests/test_town_plan_gui.py`, `tests/test_location_plan.py`, `tests/test_location_profiles.py`,
  `tests/test_construction_plan_country.py`, `tests/test_construction_plan_detail.py`.

## Tested in game (2026-11-21, plans as markers)

Plan test world, Castile, EU5 1.4.9; kit `pp_testing\townplan_test_20261120\gen_mk.py` -> `run\pp_mk_*.txt`, dump
lines `PPM;`.

- Setting plans through the button's effect on six locations: markers set, `pp_tplan_n` counts them, the country list
  holds each location once (also after set, off, set of one plan).
- A Locations look and a rights look: states written, constructions started; a plain charter grant (tools), a town's
  other specialization making way (Granada: Cloth Charter without a cloth plan replaced by the Tools Charter), and the
  other specialization staying where it has a plan (Avila: wait reason 2); political influence paid per grant.
- Owner change by `create_country_from_location` and by `change_location_owner`: the plans, their states and the list
  entry are gone at once (the on_action fires for both); coming back by `change_location_owner` brings no plan back.
  Not tested: a peace deal, a country annexed.
- Clear in the window: plans, states and the list entry gone.
- Plans free their workers with 423 planned locations: one look closed 14 buildings in 14 locations (state 14 on 18
  plans); they stayed closed over a monthly pass; taking the plans off those locations reopened all 14 at once.
- 105 days over a sliced Locations look and a rights look: no script error from the plan files.
- Map mode, the location window's Plans row and the Location Plan window (click a tile on / off) checked on
  screenshots.
- Old saves: a save made while plans were town rights loads; each former plan right stays as a typeless town right
  ("Engine behaviour relied on"); the one-off `run pp_plans_restore.txt` ("Known limits") took the test save's rights
  5 -> 0 and 4 -> 1 and set the plans again.

## Tested in game (2026-11-20)

Plans were town rights `pp_plan_<plan>` in this and the following test sections.

Construction Plan test world (playset "PP Plan Test"), new game as Castile, 1 April 1337 to March 1339, run files
`run\pp_tp_setup.txt` (gold, influence, the plan on, plans through `pp_tplan_flip` on a small rural location, the
biggest rural location and the biggest town) and `run\pp_tp_dump.txt` (`PPTP;` lines in error.log, numbers + 1000).

- Plans are granted on rural locations and on a town; `every_locations_with_town_rights_in_country` finds a rural
  location whose only rights are plans. The location's rights counter reads n/n: the plan's own slot cancels its use.
- The button: a click in the Location Plan window sets the plan (gold frame, a tile in the Plans row, the tooltip's
  state), the map mode shows the plans as icons. No script error named a plan file in two years.
- The look builds: a Lumbermill in the rural location, a Tools Guild in the town.
- Rank raise: the plans for pottery and beer on the rural location first reported the missing construction goods
  (state 8), then started "Founding a Town" from the Locations purse; **the plans survived the rank change**. Beer
  producers followed in the new town, and the next rights look granted the **Beer Charter** for the normal price.
- The pop-up of the game's town rights messages is off (ten grants, none opened).

### Third round (2026-11-20 morning, same world, the closer setup `run\pp_tp3_setup.txt`, run files `run\pp_r3_*`)

- **Charter to rights**: Granada (a city without rights) with the tools plan and Tools Guild levels added by script
  got the Tools Charter at the May look (20 influence) and, with the Printing Press spawned, embraced and researched by
  console, the Tools Rights at the November look; a second town the same. Influence over the November look: 100 -> 64 =
  two swaps (8 each) and one new charter (20): the script revoke inside the swap costs nothing.
- **Tier upgrade**: with `tools_workshop_advance` researched by console, the June look turned one Tools Guild level of
  Granada into a Tools Workshop level (12 + 1; the line count stays), state 1.
- **Owner change**: both script owner changes (`change_location_owner`, `change_location_owner_forcefully`) to a
  second country, and making a country out of a planned location, take every plan off (the plan rights are gone, the
  location keeps none); the game opens the buildings the rule had closed there; the monthly check then forgets the
  rule's memory of the location. A real charter survives: Granada kept its Tools Charter both ways and lost only the
  plan. Taken back, the plans stay gone (by design). Not tested with a peace deal; the console's `conquer` did nothing.
- **A building opened again by hand** (through the game's open function, the call the building's own button makes): the
  monthly check put its type on the location's keep list, and over the next three looks the rule left it open while
  the location's plans went on building.
- Test pitfall: the hidden widget needs a frame to close a building. A `tick_day` that runs over a look and the next
  month's start in one go never gives it one, so the monthly check finds the building open and puts it on the keep
  list (3 of 3 later closings in this run). In play there are frames between days. Stop a tick right after a look.

**The third round's changes, tested in game the same morning** (new games, build 8bd92898; no compile failure and
no plan script error in the load logs or in the runs):

- **Food and Trade plans** (`run\pp_r4_setup.txt`: Food on every province capital and rural location, 419 locations,
  Trade on the 51 towns and cities, only the Locations group funded, 60,000 gold; four looks; `PPF;` lines), old
  build against new. No province's store was short in either run. First look, old -> new: constructions started
  367 -> 381; Taverns started 1 -> 0 (3 -> 0 after four looks); Cookshop and Public Kitchen levels 24 -> 10 (farms
  come first); plans with "nothing to build" 47 -> 41; "loses money" 9 -> 1. The Food plan's constructions were Legume,
  Cattle and Millet Farms, Fruit Orchards and Fishing Villages, Cookshops only in capitals.
- **Trade**: in both runs no trade building started in the first year: the towns were building for their Food plan,
  and the Marketplace's construction goods (masonry, glass) were missing in all four markets (state 8). With the
  Food plan taken off the towns, ten constructions finished by console and masonry and glass stocked by console, one
  look started 33 Marketplace levels (state 1) and no Hired Labor Yard or Smuggler's Cove.
- **Charters follow plans** (`run\pp_r5_ch_setup.txt`, the rights look run by console, `PPH;` lines): Granada with a
  tools plan, eight Tools Guild levels and a script-granted Cloth Charter without a cloth plan; Avila the same with a
  cloth plan. Influence at zero: Granada's wait reason 1 (influence), Avila's 2 (the other specialization stays).
  Influence at the cap: Granada's Cloth Charter was revoked and the Tools Charter granted in the same look for 20
  influence (100 -> 80: the revoke is free); Avila kept its Cloth Charter, reason 2. The tooltip of Avila's tools
  tile shows the line ("Tools Charter: waits, this town holds another specialization ..."). With the setting "Grant
  a plan's charter and rights" off, the look granted nothing and cleared the wait reasons.
- **The Plans tab** shows the eight settings above the plan icons.
- **Plans first for their workers** (second new game, `run\pp_r6_setup.txt`: tools plan on every town, lumber plan on
  every village, only the Locations and the Businesses group funded; `PPB;` lines): the first look closed one building
  in each of 14 locations; all 14 carried both marks. The next monthly pass started one Businesses construction, none
  in a marked location (the Businesses rule was nearly idle in this game, so the run alone proves little). The rule's
  own gate (`pp_cplan_business_site`, `run\pp_r6_gate.txt`) evaluated on those 14 locations: all 14 pass without a
  mark, none with `pp_lplan_wk`, none with `pp_pclose_wait`. With the setting "Other businesses in planned locations"
  off, none of the 155 planned locations that pass otherwise does.
- **The saving is released**: with the treasury emptied the group saved for a location; taking that location's plans
  off (the Clear button's effect) dropped the saving at once.
- **Switching the Construction Plan off** by its switch in the window reopened all 14 closed buildings.

Not tested: a plan lost in a peace deal, the pane's "saving for the upgrade" line for the Locations group, the
make-way rule against a specialization at rights level.
