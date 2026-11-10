# Location Plan

Branch `location-plan` (off `stockpile-prices`, 2026-11-07, Jan): a player marks what a location should produce or have,
and sees on the map which locations have it. Player-only.

**The marks are build picks (Jan, 2026-11-10, branch `location-profiles`):** "When I'm in a location, I can apply a
profile, and the global settings stick as well, but I would like to be able to also click: in this location, also
expand wheat. Pretty similar to how the auto-expand feature of vanilla works, but with our own logic and thresholds."
A mark on a location means: the Construction Plan builds it here. One concept, one storage; the map icons show the
picks. Until then the marks were only visual.

**A mark forces what was clicked (Jan, 2026-11-10 evening, playing Venice; 2b053cff, not seen in game yet):** "this
location-specific upgrading should just force the upgrades ... sometimes I might want to invest in stuff that's zero
profit or buildings that don't even have a profit gate, for example a marketplace", otherwise "why wouldn't I just use
the global setting". Since then a mark has no payback limit and the market limit does not hold it back. A mark is a
**good** (the picker's icons: its producers) or **one building** (marked on the building's own entry), and no longer a
building category ("trade buildings" did not say what is in it). The categories stay rule targets of the profiles.

## In game

- **Location window, Infrastructure tab:** under the Profile row the row **Also build here** (one block with it, the
  same card): toggle tiles, pressed with a gold glow = marked. First the marked goods, then the marked buildings (the
  building's own icon; a click takes the mark off), then, unmarked, the goods that buildings standing in the location
  make (what a mark would expand, like vanilla's auto expand on a standing building), then one round button that opens
  the Location Plan window for every good. One click on a tile marks or unmarks. Tile tooltip: the item's name, what
  the mark does, and for a marked good its state after the last pass (a marked building has no state).
- **A building's mark** (2026-11-10 evening, Jan: "I want to force it to become a trading hub, or I want to force an
  iron mine here"): **Ctrl + click** on a building tile of the location window (beside vanilla's Alt + click for auto
  expand; a small Location Plan badge on the tile while it is marked), or the **checkbox** on a row of the build panel
  (only on rows of the player's locations where no own building of that type stands: a standing building is marked on
  its tile). Both call the scripted GUI `pp_lplan_bmark`; the GUI cannot look into a variable list, so it asks
  `pp_lplan_bmarked` (`is_shown`) whether a building is marked. Player-owned locations only, not observers.
- **Plan button** in the header of the location window (player-owned locations, not observers), left of the go-to arrow.
  It opens the **Location Plan** window on that location.
- **Window:** the location's marked goods (green once the location makes it, red while it does not, "N of M here
  already", counting goods only: `pp_lplan_goods_n`, `pp_lplan_done_n`; each tooltip with the mark's state), the strip
  of marked buildings (`pp_lplan_bstrip`, a click takes a mark off), and a picker: every good (grouped Farming,
  Forestry, Gathering, Hunting, Manufactured, Mining). The eight building categories left the picker on 2026-11-10.
  Click an icon to mark or unmark it; marked icons carry a gold frame. Clear removes every mark, the marked buildings
  too.
- **Map mode Location Plan** (Economy menu, first row; or "Show on map" in the window): each marked good as an icon over
  the location, on a green tile once done, red while still to do; hover an icon for its name and state. The map
  underneath is the raw material map faded almost out. Marked buildings have no map icon.

A marked good is done (green) once the location produces it: its raw material is that good, or a standing building
there produces it (`building_produced_goods`). Done is only the colour: the plan keeps building a marked good, level
after level, as long as the mark stands.

## What a mark builds

At each look of the rule group **Locations** (reason code 105, that group's purse; weight 0 = nothing; looks in months
3, 6, 9, 12, between looks only the location it saves for, `docs/location_profiles.md` Script time), per location
after the rules of its profile (a location with marks and no profile gets its turn too; the locations take turns,
`docs/location_profiles.md` Monthly pass): the location's marks, **forced** (2026-11-10 evening, 2b053cff;
hand-written `pp_lplan_location_turn`). Until then a mark ran as a profile rule with the player's Businesses line
(`pp_cplan_business_years`) as its payback limit, and the market limit held it; both are gone for marks:

- **No payback limit** (`scope:pp_lprof_pb` = 1,000,000) and **no market limit** (`scope:pp_cplan_forced` = 1 while
  the marks run; `pp_cplan_construct_scoped` skips `pp_cplan_market_do` then). Still needed: the can-build check, the
  workers, the construction goods in the market, a free construction slot (one construction at a time in a location)
  and the group's purse. Profile rules keep their own payback limit and the market limit.
- **Order inside one location: best measurable payback first, then mark order.** Two goes over the marks
  (`scope:pp_lplan_mode`; trigger `pp_lplan_measuring` = mode 1):
  1. *Measure* (only while a construction can start here: no construction this turn, `pp_cplan_site_free`): every mark
     whose next level could be built (can-build, not at its highest level, workers, construction goods) and that has a
     profit to measure (a standing building that earns: `pp_lprof_payback100` below 1098) offers its payback; nothing
     is built, first levels are not offered. The best is kept on the location (`pp_lplan_bt` its building type,
     `pp_lplan_bp` its payback + 100, `pp_lplan_bn` the mark's number: 100 + its place in the picker for a good, 1000
     for a building mark; `pp_lplan_bq` the best before a mark measured) and built at once (`pp_lplan_bo` what came of
     it: 101 started, 107 gold, 102 it could not be built after all).
  2. *Build* in mark order (the goods in the picker's order, then the marked buildings in the list's order): the
     measured mark takes `pp_lplan_bo` as its state, every other mark runs its target without a payback limit, so a
     first level (a Marketplace, nothing to measure) or a level without profit is built too. After a construction
     started here they wait (state 9).
  `pp_lplan_measure_clear` removes the measuring variables before and after.
- **A goods mark** runs the good's generated target `pp_lprof_t_<good>`, what a profile rule with that target runs
  (`pp_lplan_mark = { v = g_<good> do = pp_lprof_t_<good> n lo hi }`): a standing producer gets one more level, highest
  tier first, else the cheapest buildable producer starts.
- **A building mark** (`pp_lplan_building_mark`, one per entry of the list `pp_lplan_b`) builds a level of that
  building; where the country has researched a later tier, that tier (generated `pp_lplan_b_newest`: up to 4 steps of
  `pp_lplan_b_step`, the 155 upgrade pairs; a building the country has made obsolete is not built any more); where an
  older tier of it stands here and the country can upgrade it, the upgrade (generated trigger `pp_lplan_b_upgrade_here`:
  a construction of the successor is the game's Upgrade button). It needs no level of it under construction, not its
  highest level, the country's and the location's part of the can-build check (an upgrade does not ask the
  location's), the workers (generated `pp_lplan_b_staff`, `scope:pp_lplan_sok`; not for an upgrade) and the
  construction goods (`pp_cplan_btype_data`, `scope:pp_cplan_gok`; missing goods are counted, `pp_cplan_note_goods`).
  A building mark keeps no state (script cannot make a variable name per building type).

One construction per location per turn, whether a rule of the profile or a mark starts it; later ones wait (state 9).
Marks add. They switch nothing off in the global rule groups and do not depend on the profile's "Global rules here"
checkboxes; a good that is both a profile rule's target and marked is tried twice (the rule with its limit, then the
mark without one).

Each goods mark keeps its state after the last look, the profile rule states with their texts (`PP_LPROF_ST_<n>`): 1
started, 2 nothing to build, 3 a construction is under way here, 4 no free workers, 6 cannot be built here, 7 gold (the
Locations group's purse cannot pay it, or the group saves for something before it), 8 the market lacks the
construction goods, 9 waiting for an earlier one this turn. A forced mark never gets 5 (payback too long) or 10 (the
market limit); its tooltip no longer shows the payback found (`MARK_STATES` in `location_plan.py`; the variable
`pp_lplan_est_g_<good>` is still written). Fur has no building that makes it: its mark always shows state 6.

**Old saves** (2b053cff is save-compatible): a save's category marks (`pp_lplan_c_<category>` with
`pp_lplan_st_c_...` / `pp_lplan_est_c_...`) are taken off quietly at the Locations group's first look
(`pp_lplan_drop_categories`, from `pp_lplan_cleanup`; each off the count `pp_lplan_n`); the player loses them and marks
the buildings anew. Clear removes them too. A goods mark's old state 5 or 10 stays until the next look.

## Code

- `location_plan.py` (finalize; `[location_plan]` in `constructor.toml`: categories, hidden goods, icons per row):
  done values and counts (`pp_lplan_planned_n` goods and buildings, `pp_lplan_goods_n`, `pp_lplan_open_n`,
  `pp_lplan_done_n` goods only), the toggle switch, clearing (`pp_lplan_clear_all`, also the marked buildings and an
  old save's category marks), `pp_lplan_drop_categories` (`legacy_marks`), the picker grid (goods only, `mark_items`)
  and the strips, the item texts (tile and icon tooltips with the mark's state, `PP_LPLAN_BMARK_TILE` for a marked
  building) and the patched `gui/map_markers.gui` (see Map icons). It also patches the plan button and the building
  marks into the location window (`add_location_button`, `add_building_marks`: a Ctrl + click `action_tooltip` beside
  each of vanilla's two Alt + click auto-expand actions and a badge beside vanilla's auto-expand badge, nothing of
  vanilla changed; `location_view.build_window`) and writes the build panel's checkbox (`build_panel_mark`), which
  `tools/port_vanilla_gui.py` inserts into `build_location_lateralview.gui` and keeps when the panel is re-ported
  (71c29c6c).
- `location_profiles.py`: the generated parts of the pass. `pp_lplan_location_marks` (one line per good: `pp_lplan_mark
  = { v = g_wheat do = pp_lprof_t_wheat n = 122 lo = 121.5 hi = 122.5 }`, the target effect a profile rule's dispatch
  calls and the mark's number; `pp_lplan_mark_none` for a good without buildings), the building mark's helpers
  (`render_building_marks`: `pp_lplan_b_step`, `pp_lplan_b_newest`, `pp_lplan_b_staff`; `render_building_mark_triggers`:
  `pp_lplan_b_upgrade_here`; data from `building_mark_data`: the Towns and Buildings rule's upgrade pairs and the
  workers a level) and the row's script values (`pp_lplan_quick_<good>`, `pp_lplan_quick_room_<n>`). Hand-written in
  `scripted_effects/pp_location_profiles.txt`: `pp_lprof_run` (walks the locations with a profile or marks,
  `pp_lprof_gather`, in turns), `pp_lprof_location_turn`, `pp_lplan_location_turn`, `pp_lplan_mark`,
  `pp_lplan_building_marks` / `pp_lplan_building_mark`, `pp_lplan_measure` / `_before` / `_after` / `_clear`,
  `pp_lplan_cleanup`, and the start and end a rule and a goods mark share (`pp_lprof_open`, `pp_lprof_finish = { st =
  <state variable> est = <payback variable> }`); trigger `pp_lplan_measuring` in `scripted_triggers/pp_construction_plan.txt`.
- `location_profiles_gui.py`: the row `pp_lplan_location_row` (`_also_row`, the marked buildings `_building_mark_tiles`),
  placed by `add_location_row`.
- Hand-written: `scripted_effects/pp_location_plan.txt` (`pp_lplan_flip = { v = g_<good> }` and `pp_lplan_bflip`
  (scope:pp_bt) with count and list, `pp_lplan_keep_list`, `pp_lplan_clear_do`, select), `scripted_guis/pp_location_plan.txt`
  (`pp_lplan_toggle`, `pp_lplan_bmark`, `pp_lplan_bmarked`, ...), `gui/pp_location_plan.gui` (window, scripted widget),
  `gfx/map/map_modes/pp_location_plan_map_mode.txt`, the game concept and icon (copy of vanilla `building_based`),
  `pp_location_plan_l_english.yml`.
- Variables. Location: `pp_lplan_g_<good>` (present = marked), the list `pp_lplan_b` (marked building types, since
  2026-11-10 evening), `pp_lplan_n` (goods and buildings marked + 100), `pp_lplan_st_g_<good>` (state + 100) and
  `pp_lplan_est_g_<good>` (the shortest payback found, years + 100; 1099 = no profit; no longer shown), during a turn
  `pp_lplan_bt` / `_bp` / `_bn` / `_bo` / `_bq` (the measuring, removed at its end). `pp_lplan_c_<category>` and its
  state and payback exist only in older saves. Country: `pp_lplan_sel` (the location the window shows), the list
  `pp_lplan_locs` (the locations the country marked; kept by every toggle, building mark and Clear). The cleanup at
  each look drops list entries without marks and takes the marks from own locations that are not on the list (an
  earlier owner's); a location lost and won back keeps its marks. A save from before 2026-11-10 has marks without list
  entries: the first look removes them.
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
- Tests: `tests/test_location_plan.py` (marks, state texts, no "only visual" text, building marks, the location
  window's Ctrl + click), `tests/test_location_profiles.py` (the pass: same targets as the rules, forced marks, the
  measuring, the building marks' helpers, the turns, the lists, the row's values and cap),
  `tests/test_location_profiles_gui.py` (the row, the category lists), `tests/test_build_location_gui.py` (the build
  panel's checkbox).

Tested in game 2026-11-10 (test world, Burgos): a click on a quick candidate marks it and moves it to the marked
tiles, a second click unmarks; the round button opens the Location Plan window; thirteen marks; after a pass the
tooltips read "Waiting: a construction is under way here" (a business had taken the location's slot) and, once the
slot was free, "Started a construction here last month" (a Dye Maker for the dyes mark; the Locations pane and the
"Last month" list name it). That was before 2b053cff: forced marks, the measuring, building marks (Ctrl + click,
the build panel's checkbox, the strip and the row's tiles), the turns and the clearing of category marks are not seen
in game yet. To check there first: `pp_lplan_bmarked` as `IsShown` on the tiles and checkboxes, a Ctrl + click beside
vanilla's Alt + click, an upgrade by a building mark (Upgrade button price), a Marketplace mark without profit, and an
old save's category marks going at the first look.

## Map icons

The icons are vanilla's raw goods marker. `location_plan.py` copies vanilla `gui/map_markers.gui` into the mod and
splits only the `raw_goods_marker` widget (a test checks the rest is vanilla): outside the plan map mode it shows
vanilla's raw goods icon, in it a row of the marked icons, for player-owned
locations with a mark only (`pp_lplan_n` set; locations without one never look at the 76 goods; 84 items with the
categories until 2026-11-10). The marker carries
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
