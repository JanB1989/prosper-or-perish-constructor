# Location Profiles (history) and the Locations group's engine

**Gone since 2026-11-19** (Jan, branch `town-plans`): the Location Profiles (2026-11-07 to 2026-11-19: up to 100
player profiles, each an icon, a colour, five ordered build rules with payback limits and switches for the global rule
groups, assigned to locations on the map) and the Location Plan marks (goods marks and building marks, 2026-11-10 to
2026-11-19). The one per-location decision is now a **town-right plan**: `docs/location_plan.md`. The full design of
the profiles is in git history (this file before 2026-11-19).

What survived is the engine that builds for a location, under its old internal names (`pp_lprof_*`, `pp_lplan_*`; the
group's key `profiles`, construction code 105; module `location_profiles.py`, hand-written
`scripted_effects/pp_location_profiles.txt`).

## Targets

A target is what a plan builds: generated effect `pp_lprof_t_<target>` per target, its candidates highest tier first.

- a good: its producers (the buildings whose main good it is, as the Construction Plan's goods rules; `logistics` = the
  logistics buildings);
- `food`: the producers of the staple foods and the Province Food buildings;
- `trade_category`: the player-buildable building types of that category (no foreign, special, estate, organisation or
  event-only buildings).

In a target: an older tier standing here whose successor (one of the target's buildings) the country has researched is
upgraded first (`pp_lprof_upgrade`, the game's Upgrade, one level a turn; the direct successor only); else a standing
candidate grows (highest tier first); else the cheapest candidate that can be built here starts (a first level has no
profit to measure). Guards: `location_and_owner_can_build`, the room under the type's max level, the workers one level
needs (`pp_cplan_staff`), the construction goods in the market, one construction at a time in a location
(`pp_cplan_site_free`), never a level of a closed building, the group's purse (`pp_lprof_build_known` ->
`pp_cplan_construct_room`, the room by the type's own `pp_cplan_room_<type>` and the candidate's cost data; the
measured best plan, a type held at run time, through `pp_lprof_build` -> `pp_cplan_construct_scoped`). A plan's
target runs forced (`scope:pp_lprof_pb` = 1,000,000: no payback limit; `scope:pp_cplan_forced` = 1: not held by the
market limit). Why a candidate failed is ranked in `pp_lprof_fail` (+ 100): 101 at its highest level, 102 cannot be
built, 103 payback, 104 workers, 105 goods, 106 market limit, 107 gold, 108 a higher rank that cannot be raised now.

## States

`pp_lprof_finish` writes the state (+ 100) into the plan's `pp_lplan_st_g_<plan>` and the shortest payback found into
`pp_lplan_est_g_<plan>`: what the target set (1 started, 3 a construction under way, 9 waiting for this turn's
construction), else the best failure (108 -> 11, 107 -> 7, 106 -> 10, 105 -> 8, 104 -> 4, 103 -> 5, 102 -> 6, 101 ->
2), else 6. Texts `PP_LPROF_ST_<n>`; 5 and 10 never come up for a plan. At a look `pp_lprof_count_state` counts them
for the window's pane (`pp_cplan_ds_profiles_st<n>`, read as `pp_cplan_d_profiles_st<n>`).

## Turns

At its looks (months 3, 6, 9, 12) the group walks every owned location that holds a plan (`pp_lprof_look`), in turns:
a location gets a number when it first joins (`pp_lprof_seq`, country `pp_lprof_seq_n`), a look starts after the
country's place in that order (`pp_lprof_cursor`, script value `pp_lprof_turn`) and wraps around; afterwards the place
moves to just before the location the group saves for (`pp_cplan_save_loc_105`). Between looks only that location,
once the purse can pay (`pp_cplan_group_target` -> `pp_lprof_target_turn`). In a location (`pp_lplan_location_turn`)
the plans run in two goes (`scope:pp_lplan_mode`, trigger `pp_lplan_measuring`): first every plan whose next level has
a profit to measure offers its payback and the best is built (`pp_lplan_bt` / `_bp` / `_bn` / `_bo` / `_bq`); then
every plan in the plans' order (`pp_lplan_location_marks`, one `pp_lplan_mark` per plan) runs its target or, where
its producers need a higher rank, `pp_tplan_do_<plan>`. A construction started here ends the location's turn.
