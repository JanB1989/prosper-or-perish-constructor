# Town-right plans

Branch `town-plans`, 2026-11-19, Jan: the one per-location decision of the Construction Plan is a **plan**, and a plan
is a town right. "This location is for lumber." Player-only; the AI never grants a plan right. **Tested in game
2026-11-20** in the Construction Plan test world as Castile, two years (section "Tested in game" below); the engine
behaviour further down that the test did not touch comes from a static reading of EU5 1.4.9.

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
  off, or the location is lost (below).
- A plan also shows in the game's own town rights card of the location, with its own icon (the good's; food and trade
  a map mode's) and name ("Plan: Lumber").

## The plan right

`pp_plan_<plan>` (`town_plans.py`, generated `town_rights/pp_plan_town_rights.txt`), one per plan: the 75 goods that
have a forced goods target (their producers) plus `food` and `trade`. Each right: `potential = { always = no }` (never
in the game's grant list, never granted by the AI, skipped by the Towns and Buildings rights rule), no `allow`, no
bonus, `kept_at_conquest = no`, `local_possible_town_rights = 1` (the right brings its own slot, so it never takes the
room of a real right), its own colour. Set and removed only by the mod: scripted GUI `pp_tplan_toggle` -> effect
`pp_tplan_flip = { g = <plan> }` (`grant_town_rights` / `revoke_town_rights_of_type`, every grant guarded by "not
held"). Script reads it with `has_town_rights` (trigger `pp_tplan_held`, value `pp_tplan_on_<plan>`).

## What the Construction Plan does with a plan

The rule group **Locations** (internal key `profiles`, construction code 105, its own purse and weight on the Global
Settings tab; it counts for the weights only while a location holds a plan) gives each location with a plan its turn
at its looks (months 3, 6, 9, 12; between looks only the location it saves for). The locations take turns from a
cursor (`pp_lprof_look`, `pp_lprof_turn`). In a location's turn every held plan runs its target, **forced**: no
payback limit, no market limit. Still needed: the can-build check, free workers, the construction goods in the market
(12 months of the draw), a free construction slot (one construction at a time in a location) and the group's purse.
Inside one location the plans whose next level has a profit to measure go first, best payback first, then the rest in
the plans' order; the first construction ends the location's turn (the others wait, state 9). Plans add: they switch
no global rule group off.

- **A good**: its producers (the buildings whose main good it is). Order: an older tier standing here whose successor
  (also a producer) the country has researched is upgraded first (the game's Upgrade, one level a turn); else a
  standing producer gets one more level, highest tier first; else the cheapest producer that can be built here starts.
- **Food**: the same over the producers of the staple foods and the Province Food buildings (Cookshop, Tavern, ...).
- **Trade**: the same over the trade buildings (building category `trade_category`).
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
  a month. Details: `docs/construction_plan_country.md` "Plans: charters and rights".

### States

Per plan and location after the last look, `pp_lplan_st_g_<plan>` (+ 100; texts `PP_LPROF_ST_<n>`): 1 started, 2
nothing to build (every producer at its highest level), 3 a construction under way here, 4 no free workers, 6 cannot be
built here, 7 gold (the purse cannot pay it, or the group saves for something before it), 8 the market lacks the
construction goods, 9 waiting for another plan's construction this turn, 11 needs a higher rank that cannot be raised
here now. 5 (payback) and 10 (market limit) never come up for a plan. The Locations pane of the Construction Plan
window counts the plans by state, names what the group saves for (a building or a town / city
upgrade) and lists what it built: "for its plan", or a higher rank with the location's people.

## Map mode

**Location Plan** (Economy menu, first row; `gfx/map/map_modes/pp_location_plan_map_mode.txt`, game concept
`pp_location_plan`): over each of the player's locations the icons of its town rights, plans among them, at most 8
(vanilla's raw goods marker, patched by `location_plan.py` in `gui/map_markers.gui`); each icon's tooltip names the
right. No legend: the map under the icons is the raw material map faded almost out. Engine facts of the marker (in game
2026-11-07): the engine makes raw goods markers only with `color_mode = raw_material`; with a color mode `map_color`
and `tooltip_key` are ignored; marker types load only from the three `map_markers*.gui`; a mod loaded after PP that
overrides `map_markers.gui` hides the icons; a map mode's `index` is its row in the category menu (economy shows rows
0-3).

## Engine behaviour relied on (static analysis of EU5 1.4.9, not tested in game)

- The script grant skips every check (potential, allow, slots, price) and can stack duplicates: every grant is guarded.
- Every held right counts against the location's slots; the plan's own +1 slot cancels that.
- A held right whose potential is false is never stripped.
- A rank change revokes the rights above the slot count, newest first (a plan holds its own slot, so only a real right
  can go that way; inferred).
- A hostile owner change destroys rights with `kept_at_conquest = no`: the conqueror does not inherit the plan.
- Every script grant and revoke sends the player the game's town rights message (a pop-up by the game's default; the
  mod switches the pop-up off, see "Known limits").
- The AI never grants plan rights (potential `always = no`).

## Known limits

- One charter per town: the charters' own "one specialization" condition stays, so a town with plans for two charter
  goods gets one charter.
- A tier two steps old upgrades only while the middle tier can still be built (the upgrade goes to the direct
  successor).
- Plans are lost on conquest (a hostile owner change), by design.
- The game's "town rights granted / revoked" messages go to the message log without a pop-up
  (`main_menu/gui/messagetypes/pp_messagetypes.txt` redefines the two message types; the default opened a pop-up for
  every plan click and every charter the plan grants). This holds for every town right, the player's own grants too.
- A plan right shows among the location's town rights in the game's own panels.
- Several plans in one location: the plan that pays back best is built first, a level a look, until it has nothing left
  or no workers; the others wait (state 9). In the test Oporto's Tools Guild got every level for six looks while Cloth
  and Trade waited. Open: take turns instead (Jan decides).
- While the Construction Plan is switched off, plans are kept and nothing is built; the Location Plan window says so
  and carries the switch.

## Code

- `town_plans.py`: the contract (names), the rights, their text and icons, `pp_tplan_held`, `pp_tplan_on_<plan>`, the
  rank raise.
- `location_plan.py`: the window's picker, the toggle and Clear, the tile texts with the state, the map marker patch.
- `town_plan_gui.py`: the Plans row.
- `location_profiles.py` + hand-written `scripted_effects/pp_location_profiles.txt`: the engine of the Locations group
  (targets, turns, measuring, states; `docs/location_profiles.md`).
- `construction_plan_country.py`: the charters and rights of planned locations; `pp_cplan_country_rank_up`.
- `construction_plan_detail.py`: the Locations pane.
- Tests: `tests/test_town_plans.py`, `tests/test_town_plan_gui.py`, `tests/test_location_plan.py`, `tests/test_location_profiles.py`,
  `tests/test_construction_plan_country.py`, `tests/test_construction_plan_detail.py`.

## Tested in game (2026-11-20)

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

Not tested: charter to rights (needs the Printing Press), a plan lost on conquest, the Food and Trade plans' builds
(the small rural location had no free workers, state 4; Trade waited behind the Tools Guild), the pane's "saving for
the upgrade" line for the Locations group, a tier upgrade.
