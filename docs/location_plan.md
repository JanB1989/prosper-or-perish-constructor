# Location Plan

Branch `location-plan` (off `stockpile-prices`, 2026-11-07, Jan): a player marks what a location should produce or have,
and sees on the map which locations have it. Player-only.

**The marks are build picks (Jan, 2026-11-10, branch `location-profiles`):** "When I'm in a location, I can apply a
profile, and the global settings stick as well, but I would like to be able to also click: in this location, also
expand wheat. Pretty similar to how the auto-expand feature of vanilla works, but with our own logic and thresholds."
A mark on a location means: the Construction Plan builds it here. One concept, one storage; the map icons show the
picks. Until then the marks were only visual.

## In game

- **Location window, Infrastructure tab:** under the Profile row the row **Also build here** (one block with it, the
  same card): toggle tiles, pressed with a gold glow = marked. First the marked items, then, unmarked, the goods that
  buildings standing in the location make (what a mark would expand, like vanilla's auto expand on a standing
  building), then one round button that opens the Location Plan window for everything else. One click on a tile marks
  or unmarks. Tile tooltip: the item's name, what the mark does, and while marked its state after the last monthly pass.
- **Plan button** in the header of the location window (player-owned locations, not observers), left of the go-to arrow.
  It opens the **Location Plan** window on that location.
- **Window:** the location's marked items (green once the location makes or has it, red while it does not, "N of M
  here already"; each tooltip with the mark's state), and a picker: every good (grouped Farming, Forestry, Gathering,
  Hunting, Manufactured, Mining) and eight building categories (Trade, Government, Military, Defensive, Religious,
  Cultural, Naval, Infrastructure). Click an icon to mark or unmark it; marked icons carry a gold frame. Clear removes
  every mark.
- **Map mode Location Plan** (Economy menu, first row; or "Show on map" in the window): each marked item as an icon over the
  location, on a green tile once done, red while still to do; hover an icon for its name and state. The map underneath
  is the raw material map faded almost out.

A marked good is done (green) once the location produces it: its raw material is that good, or a standing building
there produces it (`building_produced_goods`). A building category is done once a building of it stands there. Done is
only the colour: the plan keeps expanding a marked item while it pays back.

## What a mark builds

Each monthly pass of the Construction Plan (only while it is on), in the rule group **Location profiles** (reason code
105, that group's purse; weight 0 = nothing), per location after the rules of its profile (a
location with marks and no profile gets its turn too): every marked item in the picker's order, **exactly as a profile
rule with that target** (`docs/location_profiles.md`, Monthly pass): a standing producer of the good gets one more
level while the next level pays back within the limit (highest tier first), else the cheapest buildable producer
starts; a building category the same over its buildings. Same guards (workers, construction goods, the market limit, the group's purse, one
construction at a time in a location). The limit is the player's global **Businesses line** ("payback within N
years", country script value `pp_cplan_business_years`, variable `pp_cplan_biz`). One construction per location per
month, whether a rule of the profile or a mark starts it; later ones wait (state 9).

Marks add. They switch nothing off in the global rule groups and do not depend on the profile's "Global rules here"
checkboxes; a good that is both a profile rule's target and marked is tried twice (the rule with its limit, then the
mark with the Businesses line).

Each mark keeps its state after the last pass, the profile rule states with their texts (`PP_LPROF_ST_<n>`): 1 started,
2 nothing to build, 3 a construction is under way here, 4 no free workers, 5 payback too long (with the payback found),
6 cannot be built here, 7 gold (the Locations group's purse cannot pay it, or the group saves for something before it), 8 the market lacks the construction goods, 9 waiting for an earlier one this month, 10 the market limit (enough of the good is on the way in its market; 2026-11-10).
Fur has no building that makes it: its mark always shows state 6.

## Code

- `location_plan.py` (finalize; `[location_plan]` in `constructor.toml`: categories, hidden goods, icons per row):
  done values and counts, the toggle switch, clearing, the picker grid and the strip, the item texts (tile and icon
  tooltips with the mark's state) and the patched `gui/map_markers.gui` (see Map icons). It also patches the plan
  button into the location window (`location_view.build_window`).
- `location_profiles.py`: the pass. Generated `pp_lplan_location_marks` (one line per item: `pp_lplan_mark = { v =
  g_wheat do = pp_lprof_t_wheat }`, the target effect a profile rule's dispatch calls; `pp_lplan_mark_none` for an
  item without buildings) and the row's script values (`pp_lplan_quick_<good>`, `pp_lplan_quick_room_<n>`).
  Hand-written in `scripted_effects/pp_location_profiles.txt`: `pp_lprof_run` (walks the locations with a profile or
  marks, `pp_lprof_gather`), `pp_lplan_mark`, `pp_lplan_cleanup`, and the start and end a rule and a mark share
  (`pp_lprof_open`, `pp_lprof_finish = { st = <state variable> est = <payback variable> }`).
- `location_profiles_gui.py`: the row `pp_lplan_location_row` (`_also_row`), placed by `add_location_row`.
- Hand-written: `scripted_effects/pp_location_plan.txt` (`pp_lplan_flip = { v = g_<good> | c_<category> }` with count
  and list, `pp_lplan_keep_list`, `pp_lplan_clear_do`, select), `scripted_guis/pp_location_plan.txt`,
  `gui/pp_location_plan.gui` (window, scripted widget), `gfx/map/map_modes/pp_location_plan_map_mode.txt`, the game
  concept and icon (copy of vanilla `building_based`), `pp_location_plan_l_english.yml`.
- Variables. Location: `pp_lplan_g_<good>` / `pp_lplan_c_<category>` (present = marked), `pp_lplan_n` (marks + 100),
  `pp_lplan_st_g_<good>` / `pp_lplan_st_c_<category>` (state + 100) and `pp_lplan_est_g_<good>` / `_c_<category>` (the
  shortest payback found, years + 100; 1099 = no profit). Country: `pp_lplan_sel` (the location the window shows), the
  list `pp_lplan_locs` (the locations the country marked; kept by every toggle and Clear). The monthly cleanup drops
  list entries without marks and takes the marks from own locations that are not on the list (an earlier owner's); a
  location lost and won back keeps its marks. A save from before 2026-11-10 has marks without list entries: the first
  pass removes them.
- Row width: the line holds `QUICK_ROW` = 11 tiles (37 px each, as the Profile row). The quick candidates come in
  chunks of `QUICK_CHUNK` = 4 goods in the picker's order; a chunk shows while marks + candidates before it <= 7, so
  candidates never push the line past 11 tiles and a cut line still shows at least 8 (the rest is in the Location Plan
  window). An exact cut would count the candidates before every tile each frame. Marked tiles are never hidden by a
  count: the line is a widget of 11 tiles' width with `scissor = yes` (vanilla's mission view), so a twelfth mark is
  cut and the title then reads "N marked, more in the Location Plan" (`PP_LPLAN_ALSO_COUNT`; in game 2026-11-10
  thirteen marks made the card wider than the window and pushed the round buttons out). Both rows' tiles start at
  the left, under their titles (an hbox with an expand). Cost while the tab is open, measured in game 2026-11-10
  (script profiler, self times, Burgos): 0.7 ms a frame for the two rows (7,300 script calls) on top of the location
  window's 4.3 ms; frame time stays at the 30 frames cap. Fewer, larger chunks would be cheaper.
- The window's detail pane counts the marks' states with the profile rules' (`pp_cplan_ds_profiles_st<n>`); a mark's
  construction is in the ledger as the profile group's with step 0 (`pp_cplan_log_step`; a profile rule's step is its
  number).
- Tests: `tests/test_location_plan.py` (marks, state texts, no "only visual" text), `tests/test_location_profiles.py`
  (the pass: same targets as the rules, the Businesses line, the lists, the row's values and cap),
  `tests/test_location_profiles_gui.py` (the row).

Tested in game 2026-11-10 (test world, Burgos): a click on a quick candidate marks it and moves it to the marked
tiles, a second click unmarks; the round button opens the Location Plan window; thirteen marks; after a pass the
tooltips read "Waiting: a construction is under way here" (a business had taken the location's slot) and, once the
slot was free, "Started a construction here last month" (a Dye Maker for the dyes mark; the Locations pane and the
"Last month" list name it).

## Map icons

The icons are vanilla's raw goods marker. `location_plan.py` copies vanilla `gui/map_markers.gui` into the mod and
splits only the `raw_goods_marker` widget (a test checks the rest is vanilla): outside the plan map mode it shows
vanilla's raw goods icon, in it a row of the marked icons, for player-owned
locations with a mark only (`pp_lplan_n` set; locations without one never look at the 84 items). The marker carries
nothing per item for the picks; the mark's state is in the icon's tooltip text.

Engine facts (in game 2026-11-07):
- The engine creates raw goods markers only with `color_mode = raw_material`. `map_markers = { raw_goods_marker = yes }`
  alone shows none (vanilla's market_food_balance neither), raw_material map names do not create them.
- With a `color_mode`, `map_color` and `tooltip_key` are ignored (error.log says so). So no map coloring and no
  location hover text in this mode; the icons carry their own tooltips. Gradient alpha 0.12 fades the raw colors.
- Map marker types are fixed by the engine and loaded only from `map_markers.gui`, `map_markers_city.gui`,
  `map_markers_construction.gui`; map name text cannot draw icons.
- The marker hides at the farthest zoom (vanilla's zoom range) and covers the location name. Icon size scales with zoom,
  capped at 60.
- Mods that override `map_markers.gui` win if they load after PP: in Jan's playset Faster Universalis (3662193478),
  3601047146 and 3735059838 do. PP must load after them for the icons.
- `refresh_map_colors = yes` after a toggle redraws the markers at once.
- A map mode's `index` is its row in the category menu, not a sort order: hud_bot.gui shows economy rows 0-3 only
  (`GetMapModeGroupFromCategory`). At index 40 the mode existed but never showed in the menu (test guards it).
- GUI and map mode files hot-reload in a running game; loc and script files do not.

Tested 2026-11-07 in a new game as England (saves `pp_lplan_england`, `pp_lplan_icons_england`), with the marks only
visual then: window, picker, strip, counts; map icons (Woking and Guildford lumber + furniture, Shoreham lumber on green
from its lumber RGO, the rest red), icon tooltips, vanilla Raw Materials map mode unchanged; no plan lines in error.log.
