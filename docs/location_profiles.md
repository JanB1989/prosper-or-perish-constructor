# Location Profiles (design contract, branch `location-profiles`, 2026-11-07)

Jan, 2026-11-07: the player defines **profiles** ("my furniture town": an icon, a colour, ordered build rules) and
assigns them to locations straight on the map. The map shows each location's profile as a badge (its icon on its
colour) beside the plan icons.

**Profiles and the global rules (Jan, 2026-11-09):** the local setting overrides the global one, but only for what it
sets; whatever a profile does not set, the global Construction Plan rules still do in its locations (no need to repeat
"logistics where needed" in every profile). In detail:

- The profile's rules run as their own rule group of the monthly pass, with its own budget that saves (its purse, 2026-11-10) like every
  group: the Location profiles weight bar on the Global Settings tab (its weight over the sum of the weights; 0 = the
  profiles build nothing).
- A rule's target takes that target from the global rules there: a good takes the Businesses rule's buildings that
  make it and, for a staple food, the food rule's farm step (the profile decides which food is made here); a building
  category takes the Businesses rule's buildings of that category; victuals take the Grange and Victualling Yard steps;
  market access takes the logistics rule.
- A profile can switch whole global groups off in its locations: Food, Logistics, Improvements, Businesses, Towns and
  Buildings (checkboxes "Global rules here" in the editor; unticked = off; the fifth since 2026-11-10: `xc`, field
  `global_country`, location variable `pp_lprof_xc`, read by that group's own triggers,
  `construction_plan_country.py`). An empty profile with all five off keeps the plan out.
- Beside its profile a location carries its **marks** (Jan, 2026-11-10: "in this location, also expand wheat"): the
  Location Plan's items, which the same pass builds after the profile's rules, each as a profile rule with that target
  and the player's Businesses line as its limit. Marks add; they switch nothing off and do not depend on the
  checkboxes above. `docs/location_plan.md` has the feature; the Monthly pass section below the mechanics.
- Example: global logistics on, a profile "iron mines" (rule: iron). When the location's market access drops, the
  logistics rule builds there, because the profile names no market access. With a market-access rule in the profile,
  that rule decides (its own payback limit) and the global logistics rule stays out.

Branch `location-profiles` = `location-plan` + `player-construction-manager` (merge 91019fcb). Worktree
`../ProsperOrPerishConstructor-locplan`. Builds on: `location_plan.py` (plan items, map markers),
`construction_plan.py` + `pp_construction_plan*.txt` (monthly pass, the budgets that save, payback, producers per good).

UI name: **Location Profiles**; the editor is the Construction Plan window's second tab, "Location profiles" (the
first is "Global settings", 2026-11-09, Jan).

## Why slots, and what grows with them

Script cannot create named data while the game runs: every variable name and every GUI row exists in the files. A
profile is therefore a generated **slot** `k = 1..slots`. `slots` is one number in `[location_profiles]`; unused slots
are hidden, only used ones show, and a "+" makes a new one. Raising it later changes only that number.

Up to 100 profiles (Jan, 2026-11-07: "people will want many") cost little because nothing that is drawn or run often
looks at the slots (redesign 2026-11-07):

- **Every location with a profile carries a copy of it** (icon, colour, each rule's target and payback limit),
  written on assign and whenever its slot is edited. The monthly pass and the map marker's badge and tooltip read only
  that copy: one badge per marker for any slot count, no per-slot dispatch in the pass.
- **The editor shows one edit buffer** (country variables `pp_lprof_e_*`, a copy of the slot it shows); its buttons
  pass the slot flag `e` (the buffer's slot). One editor body for any slot count.
- **Buttons work on a staged copy.** A button reads its slot into the staged copy (`pp_lprof_s_*`), edits that with
  effects on fixed names, writes it back and passes it on (edit buffer, every location with the slot). Parametrized
  scripted effects expand where they are called, so the only per-slot script is a flag's slot number (`pp_lprof_resolve`,
  `pp_lprof_resolve_free`) and the read and write of a slot (`pp_lprof_read`, `pp_lprof_write`), each written once.
- **Per slot** stay only the small tiles (a button with the slot's face: one colour frame, one icon) in the editor's
  list, the paint palette, the Profile rows and the right-click menu, and their tooltips. Rows of tiles show only while
  they hold a used slot.

Sizes (bytes; 12 slots before the redesign, 100 slots after):

| Part | 12 slots, before | 100 slots, now |
|---|---|---|
| `gui/pp_location_profiles_generated.gui` | 544,934 | 365,205 |
| profile cell in every location's map marker | 32,556 | 2,531 (any slot count) |
| right-click menu section (`context_menu.gui`) | 14,306 | 69,606 |
| `pp_location_profiles_gui_l_english.yml` | 200,956 | 436,443 |
| `scripted_effects/pp_location_profiles_generated.txt` | 166,729 | 203,505 |
| `scripted_effects/pp_location_profiles.txt` (hand) | 15,770 | 24,691 |
| `script_values/pp_location_profiles_generated.txt` | 22,081 | 19,194 |
| profile script lines with every parametrized call expanded | 68,776 | 104,124 |
| textures (flag strip, symbol pictures, colours) | 0 | 664,736 |

## Config `[location_profiles]` (constructor.toml)

```toml
[location_profiles]
slots = 100           # profiles per country
rules = 5             # ordered rules per profile
payback_steps = [1, 2, 3, 4, 5, 7, 10, 15, 20, 30, 40, 50]   # years a rule's limit steps through; past the last = any payback
colors = [[0.80, 0.25, 0.20], [0.90, 0.55, 0.15], [0.85, 0.80, 0.25], [0.30, 0.65, 0.30],
          [0.25, 0.60, 0.70], [0.25, 0.40, 0.80], [0.55, 0.35, 0.75], [0.75, 0.40, 0.60]]

[location_profiles.symbols]   # name = { name = player-facing name, texture = source below gfx/interface/icons }
city = { name = "City", texture = "map_modes/cities.dds" }
# ... 21 symbols, picker order
```

## Items (icons and rule targets)

The plan items of `location_plan.plan_items` (goods by goods category, then the 8 building categories) plus the target
**market access** = the good `logistics` (its producers are the logistics buildings; hidden from the plan picker, shown
as "Market access" in profiles). Every item has a flag key: the good key (`furniture`, `logistics`) or the category key
(`trade_category`).

**Symbols** (Jan, 2026-11-07: "a city, rural, food, ... so you are not forced to use the iron icon for a metal town"):
generic pictures a profile can carry as its **icon only** (they build nothing, so the picker shows them only for the
icon and the script refuses them as a rule target). Flag `pp_sym_<name>`, which is also the loc key of its name.

A profile's icon is a good (a goods scope) or a flag (a building category or a symbol). The GUI draws a good with
`GetGoodsIcon` and a flag **only as a frame of one strip**, `main_menu/gfx/interface/component_tiles/pp_profile_symbols.dds`
(`lpf.frame_flags`: the 8 building categories in `[location_plan]` order, then the symbols in config order; 64 px frames,
pictures inside a 2 px transparent edge; outside `icons/`, which `interface_dds` cuts to 128 px). Beside every flag that
is drawn sits its frame number (+ 100): the icon's `_in`, a category rule target's `_r<r>_cn` (set together with the flag
from the script value `pp_lprof_key_frame`). In game 2026-11-07 (Cyprus save): a texture built with `Concatenate` draws
nothing, even from literals, and `GetFlagName` returns the flag's **localized name** ("City"), not its key; so no
texture path is built from a flag, and `GetFlagName` only shows a name (`[Var.GetFlagName]`; a symbol's loc key is its
flag, a category's is vanilla's). The 8 colours are the frames of `.../component_tiles/pp_profile_colors.dds` (64 px,
2 px transparent edge): a tile's colour is one icon with `frame = colour variable - 100`, proven in game. Each symbol
also has its own picture `main_menu/gfx/interface/icons/pp_profile_symbols/pp_sym_<name>.dds` for the picker's static
buttons (categories use vanilla's `building_categories` icons there).

| Symbol | Name | Source (vanilla `gfx/interface/icons/`) |
|---|---|---|
| `pp_sym_city` | City | `map_modes/cities.dds` |
| `pp_sym_town` | Town | `buildings/council_hall.dds` |
| `pp_sym_village` | Village | `buildings/free_village.dds` |
| `pp_sym_capital` | Capital | `location_icons/capital.dds` |
| `pp_sym_food` | Food | `map_modes/province_food.dds` |
| `pp_sym_farming` | Farming | `buildings/farming_village.dds` |
| `pp_sym_herding` | Herding | `buildings/sheep_farms.dds` |
| `pp_sym_fishing` | Fishing | `buildings/fishing_village.dds` |
| `pp_sym_forest` | Forest | `map_modes/vegetation.dds` |
| `pp_sym_mining` | Mining | `map_modes/raw_material.dds` |
| `pp_sym_industry` | Industry | `location_icons/employment.dds` |
| `pp_sym_luxury` | Luxury | `resources/political_influence.dds` |
| `pp_sym_market` | Market | `map_modes/market.dds` |
| `pp_sym_treasury` | Treasury | `map_modes/economical_base.dds` |
| `pp_sym_harbour` | Harbour | `map_modes/maritime.dds` |
| `pp_sym_military` | Military | `map_modes/military.dds` |
| `pp_sym_stronghold` | Stronghold | `map_modes/fort.dds` |
| `pp_sym_religion` | Religion | `buildings/cathedral.dds` |
| `pp_sym_learning` | Learning | `map_modes/literacy.dds` |
| `pp_sym_administration` | Administration | `map_modes/government.dds` |
| `pp_sym_population` | Population | `map_modes/population.dds` |

## Variables (all numbers carry +100; `var:x = n` compares scopes, so numbers use < / > ranges)

Country (the player's):
| Variable | Meaning |
|---|---|
| `pp_lprof_<k>_on` | slot k in use (yes) |
| `pp_lprof_<k>_ig` / `pp_lprof_<k>_ic` | icon: a goods scope (`goods:furniture`) **or** a flag (`flag:trade_category`, `flag:pp_sym_city`); one of the two |
| `pp_lprof_<k>_in` | the icon flag's frame in the flag strip (+100), set with `_ic` (what the GUI draws) |
| `pp_lprof_<k>_col` | colour 1..8 (+100) |
| `pp_lprof_<k>_r<r>_g` / `_r<r>_c` | rule r target: goods scope or category flag (unset both = empty rule) |
| `pp_lprof_<k>_r<r>_cn` | the category target's frame in the flag strip (+100), set with `_r<r>_c` |
| `pp_lprof_<k>_r<r>_pb` | rule r payback limit in years (+100); unset = any payback |
| list `pp_lprof_locs` | locations with a profile (for the monthly pass) |
| `pp_lprof_e_k` | the slot in the edit buffer (+100) |
| `pp_lprof_e_ig` / `_ic` / `_in` / `_col` / `_r<r>_g` / `_r<r>_c` / `_r<r>_cn` / `_r<r>_pb` | the edit buffer: a copy of slot `pp_lprof_e_k` (what the editor shows) |
| `pp_lprof_k`, `pp_lprof_s_on` / `_ig` / ... | during a button only: the slot it works on and its staged copy (removed at the end) |

Location:
| Variable | Meaning |
|---|---|
| `pp_lprof` | assigned slot k (+100); unset = no profile |
| `pp_lprof_ig` / `_ic` / `_in` / `_col` / `_r<r>_g` / `_r<r>_c` / `_r<r>_pb` | the location's copy of its profile (the pass and the badge read only this; no rule frames, the badge draws no rule icon) |
| `pp_lprof_r<r>_st` | rule r state after the last pass (+100): 1 started, 2 nothing to build (all standing levels' payback too long / at max), 3 a construction is under way here (a location builds one at a time), 4 no free workers here, 5 payback too long, 6 cannot be built here, 7 budget, 8 market lacks the construction goods, 9 waiting for an earlier rule's or mark's construction this month |
| `pp_lprof_r<r>_est` | the shortest payback the rule found (years + 100; 1099 = no profit), shown beside state 5 |
| `pp_lprof_xf` / `_xl` / `_xi` / `_xg` / `_xc` | the profile's copy of its switches: set = that global group stays out here (food, logistics, improvements, businesses, towns and buildings) |
| `pp_lplan_g_<good>` / `pp_lplan_c_<category>`, `pp_lplan_n` | the location's marks (present = marked) and their count + 100 (`location_plan.py`) |
| `pp_lplan_st_g_<good>` / `pp_lplan_st_c_<category>`, `pp_lplan_est_...` | a mark's state and payback found, as a rule's `_st` / `_est` |

Country, for the marks: the list `pp_lplan_locs` (locations the country marked) and, during a pass, `pp_lprof_turns`
(this pass's locations: with a profile, with marks, or both) and `pp_lplan_gone`.

Flags are copied by a switch (`pp_lprof_pull_icon`, `pp_lprof_pull_cat`: compared, then set), never as a variable's value;
their frame numbers are plain numbers (`pp_lprof_copy_profile` carries `_in`, `pp_lprof_copy_frames` the rules' `_cn`).

GUI reads: `GetPlayer.MakeScope.Var('pp_lprof_3_ig').GetGoods` (`GetGoodsIcon(... .GetGoods.Self)`, `.GetKey`,
`.GetName`), `Var('pp_lprof_3_ic').GetFlagName` (the flag's localized name; shown only, never compared or used in a
path), `frame = "[FixedPointToInt(Subtract_CFixedPoint(Var('pp_lprof_3_in').GetValue, '(CFixedPoint)100'))]"` (the
flag's or colour's frame), `Var('x').IsSet`, `Var('x').GetValue` (CFixedPoint), `ScriptValue('pp_lprof_n')` / `('pp_lprof_e_n')` /
`('pp_lprof_first_free')` / `('pp_lprof_used_n')`.

## Scripted GUIs (all in `in_game/common/scripted_guis/pp_location_profiles.txt`)

Parameters go in as flag scopes: `AddScope('pp_slot', MakeScopeFlag('s3'))`, `AddScope('pp_key', MakeScopeFlag('furniture'))`,
`AddScope('pp_field', MakeScopeFlag('icon'|'r1'..'r5'))`, `AddScope('pp_dir', MakeScopeFlag('up'|'down'))`,
`AddScope('pp_col', MakeScopeFlag('c1'..'c8'))`. `pp_slot` is `s<k>`, `e` (the slot in the edit buffer: the editor's
buttons pass this), `none` (assign) or `next` (new: the first free slot).

| Scripted GUI | Scope | Params | Effect |
|---|---|---|---|
| `pp_lprof_assign` | location (root) | `pp_slot` (`s<k>` or `none`) | set / remove the location's profile and its copy; keep `pp_lprof_locs`; a location that has the slot already keeps it (and its states); `refresh_map_colors = yes` |
| `pp_lprof_new` | country (root = player) | `pp_slot` (`next`; `s<k>` works too) | switches the slot on: icon `goods:lumber`, colour k (wrapping at 8, script value `pp_lprof_new_color`), no rules; the editor shows it. The editor's "Your profiles" row has the "+" button while `pp_lprof_first_free` > 0 |
| `pp_lprof_select` | country | `pp_slot` (`s<k>`) | the editor shows slot k (its data into the edit buffer); its locations get its data again |
| `pp_lprof_set` | country | `pp_slot`, `pp_field`, `pp_key` | icon or rule target of the slot = item `pp_key` (goods → `_g`/`_ig`, category or symbol → `_c`/`_ic`, clears the other; a symbol only for the icon) |
| `pp_lprof_color` | country | `pp_slot`, `pp_col` | colour |
| `pp_lprof_payback` | country | `pp_slot`, `pp_field` (r1..r5), `pp_dir` | step the rule's payback limit through `payback_steps` (down from "any" = the last step) |
| `pp_lprof_rule_clear` | country | `pp_slot`, `pp_field` | empty rule r (and its states in the slot's locations) |
| `pp_lprof_rule_move` | country | `pp_slot`, `pp_field`, `pp_dir` | swap rule r with its neighbour (and their states) |
| `pp_lprof_delete` | country | `pp_slot` | clear the slot, unassign it from every location (their copies go), empty the edit buffer when it holds the slot |
| `pp_lprof_global` | country | `pp_slot`, `pp_field` (`global_food` / `global_logistics` / `global_improve` / `global_business` / `global_country`) | switch a global rule group off in the slot's locations, or on again (`pp_lprof_<k>_xf` / `_xl` / `_xi` / `_xg` / `_xc`, copied to the locations as `pp_lprof_xf` ...; `_xg` = Businesses, `_xc` = Towns and Buildings) |
| `pp_lprof_examples` | country | none | the example profiles (`[[location_profiles.examples]]`) in the next free slots, made with the buttons' own effects (`pp_lprof_examples_do`); the editor offers it while the country has no profile |

Every button that changes a slot ends in `pp_lprof_commit` = `pp_lprof_write` (staged copy → slot) +
`pp_lprof_publish` (staged copy → edit buffer and → every location with the slot) + `refresh_map_colors = yes`.

## Monthly pass (in `pp_cplan_run`, a rule group with its own purse like the others)

Only when the Construction Plan is on (`pp_cplan_on`). The global groups ask per group whether they may build in a
location (`scripted_triggers/pp_construction_plan.txt`: the owner's location, then the profile's side, read from the
location's copy): food not where `pp_lprof_xf` is set, its farm step not where a rule names a staple food
(`pp_lprof_food_target`), its victuals makers not where a rule names victuals; logistics not where `pp_lprof_xl` is set
or a rule names market access; improvements not where `pp_lprof_xi` is set; businesses not where `pp_lprof_xg` is set,
and no building whose good (`pp_lprof_has_good = { g = <good> }`) or category (`pp_lprof_has_category = { c =
<category key> }`, e.g. `trade_category`) a rule names (generated `scripted_triggers/pp_location_profiles_generated.txt`).
One construction at a time in a location (2026-11-09): the engine builds a location's
constructions one after another (test world: a Cookshop moved 344 days in a year while the Granary, Grange and Carrier
Inn the plan had started beside it moved 0), so `pp_cplan_construct_scoped` starts nothing where
`num_civil_constructions` > 0, whoever started it, and a profile rule then shows state 3.

For each owned location with a profile (`pp_lprof_locs`) or with marks (`pp_lplan_locs`), each once (`pp_lprof_gather`
builds the pass's list `pp_lprof_turns`; fewest building levels first): rules 1..rules of its copy in order
(`pp_lprof_location_rules` = `pp_lprof_rule = { r }` per rule; no slot is looked at), then its marks in the picker's
order (`pp_lplan_location_marks` = `pp_lplan_mark = { v = g_<good> do = pp_lprof_t_<good> }` per item). The first rule
or mark that starts a construction ends that location for the month (later ones get state 9; `pp_cplan_hit` is cleared
once a location by `pp_lprof_run`). A rule and a mark share their start and end: `pp_lprof_open` (waits: 9 after this
month's construction here, 3 while one is under way, the plan's trigger `pp_cplan_site_free`) and `pp_lprof_finish =
{ st = <state variable> est = <payback variable> }`; between them a rule dispatches its stored target
(`pp_lprof_goods_target` / `pp_lprof_category_target`) and a mark calls its target's effect directly, the same
generated `pp_lprof_t_<target>`. A mark's payback limit is the player's Businesses line (`pp_cplan_business_years` of
the country, saved as `scope:pp_lprof_pb` + 100 like a rule's). The profile group runs, and counts for the weights,
while a location has a profile or a mark (`pp_lprof_has_locations`). A rule with a goods target: expand a standing
producer of the good whose next level pays back within the limit (highest tier first, as v2 Expand), else, when no
producer stands here, start the cheapest buildable producer (the first level has no profit to measure, so no payback
check). `logistics` = the logistics try for this location. A category target: the same over the buildings of that
category (generated list per category: player-buildable building types whose `category` is it). Guards:
`location_and_owner_can_build`, the workers one level needs (`pp_cplan_staff`, Jan 2026-11-09: idle peasants left
after the open jobs of the location's buildings, or idle pops of the building's own class; candidates carry `pt` /
`sz`, state 4 when none finds them), construction goods in the market (12 months of the draw), one construction at a
time in the location, never a level for a closed building, the market limit (state 10 since 2026-11-10: enough of the good is on the way in its market), the group's purse (state 7: the purse cannot pay it, or the group already saves for something that comes before it; checked by `pp_cplan_construct_scoped`; a level the
gold does not reach is state 7 and counts once a location as waiting for gold in the Location profiles detail pane,
which also counts the rules and marks by state, `pp_lprof_count_state`). The monthly cleanup takes the
profile and its copy from locations that lost it (`pp_lprof_clear_location`), and the marks from own locations the
country did not mark (`pp_lplan_cleanup`, the same rule for the list `pp_lplan_locs`).

## UI

- **Location window, Infrastructure tab** (2026-11-09, Jan: "the same style as the other buttons there"): its own
  type `pp_lprof_location_row`, styled like the tab's rows (vanilla `location_conditions_item`): a paper card in a
  wooden frame (`bg_paper_card`, `bg_cabinet_card_frame`), the badge in a dark header strip (`bg_card_header_01`),
  plain white text, the profiles as vanilla toggle tiles (road builder style, pressed + gold glow = this location's),
  and two round icon buttons at the right (Edit profiles, No profile). The header buttons are vanilla's
  `button_round_shortcut` (Location Plan) and `button_automation_shortcut` (the plan's cog), 30 px apart.
  Right under it, in the same wrapper and the same card style, the row **Also build here** (2026-11-10,
  `pp_lplan_location_row`): the location's marks as the same toggle tiles (marked first, then the goods standing
  buildings make) and one round button to the Location Plan window; `docs/location_plan.md`. Both rows' tiles start
  at the left, under their titles (in game 2026-11-10: one block).
- **Location Plan window**: a "Profile" row: the location's badge, None, "Edit profiles", the slot tiles (icon on
  colour, 8 per row, rows only while they hold a used slot) to assign. The location window's Infrastructure tab starts
  with the same row (`pp_lprof_location_row` = `pp_lprof_plan_row`).
- **Profile editor** (2026-11-09, Jan: the plan window has two tabs): the Construction Plan window's second tab,
  "Location profiles" (GUI variable `pp_cplan_tab` = `profiles`; `pp_cplan_open` opens the window). Its body is the
  type `pp_lprof_editor_tab` (`gui/pp_location_profiles.gui`, a vbox expanding both ways, made for the tab's inner area
  of about 650 x 700 px), which `pp_construction_plan.gui` places in the tab; the plan window's close button clears
  `pp_lprof_pick`. Every "Edit profiles" (the palette, the Location Plan window's and the location window's Profile
  rows, the right-click menu; `location_profiles_gui.OPEN_EDITOR`) sets `pp_cplan_open` = `yes` and `pp_cplan_tab` =
  `profiles`. The body: the note; "Your profiles" with "+" (new profile in the first free slot), "Start with the
  examples" (while the country has none) and "Paint on map"; the profile list (used slots; a click selects one,
  `pp_lprof_select`); the edited profile (one body, the edit buffer): icon (click → picker mode `icon`), 8 colour
  swatches, Delete, rules 1..5 (target icon → picker mode `r<r>`, payback `< N years` / `any` with - / +, up / down,
  clear), the five "Global rules here" checkboxes; one shared item picker (the plan's items + Market access, and the
  Symbols group for the icon only); clicking an item calls `pp_lprof_set` with the open picker mode.
- **Map right-click menu** (vanilla `LocationContextMenu` in `context_menu.gui`, patched at finalize like
  `map_markers.gui`: a copy of vanilla with one section added, a test checks the rest is vanilla): for player locations,
  a "Location Profile" section with the badge, the slot tiles (7 per row, rows only while used), None, "Location Plan",
  "Edit profiles".
- **Paint mode** in the Location Plan map mode: a palette (scripted widget, visible only in that map mode) with the slot
  tiles and an eraser; the brush is the GUI variable `pp_lprof_brush` (`s<k>` / `none`). While a brush is set, every
  player location's marker shows a frame; a click on it calls `pp_lprof_assign` with the brush.
- **Map marker** (`location_plan.render_markers`): the badge (the location's copy: icon on its colour) first, then the
  plan icons. Badge tooltip (`PP_LPROF_UI_BADGE`, one text for every slot): "Location Profile: <icon name>", the rules
  with targets, limits, this location's states and the payback found.
- Tile tooltips (per slot): "Location Profile: <icon name>" and the rule targets, then what a click does.

## Example profiles (2026-11-09, Jan: "baseline settings I could take a look at")

`[[location_profiles.examples]]` in constructor.toml: breadbasket (wheat, legumes, livestock < 20 years), mining town
(iron, copper, lead, tin < 30), lumber camp (lumber < 50, market access), market town (market access, trade buildings
and tools < 20), harbour (fish < 30, naval buildings < 30, market access), hands off (no rules, all five global groups
off). "Start with the examples" in the editor (while the country has no profile) makes them; the test world's setup
(`run pp_plan_ai_setup.txt`) uses the same effect and assigns them by raw material and location kind.

## Not in v1

Profile names (typed text cannot be stored); profiles carried to a new game; level caps per rule; conditions per rule.

## Status (2026-11-07)

Built on `location-profiles`; synced live before the redesign. **Tested in game 2026-11-07** (England save
`pp_lplan_icons_england` -> `pp_lprof_england`, 2 May 1337), on the 12-slot design: editor (new profile, icon and
rule pickers, colour, payback steps), paint palette (frames on every English location, brush assigns, eraser
removes), map right-click menu (Location Profile section assigns), Location Plan window row, badge tooltip with rule
states; one month with the global groups off started two Lumber Mills from the profile (ledger "(location profile)");
furniture showed "cannot be built here" in rural locations (the workshop needs a town), market access the same
(logistics gate: 15 building levels). No profile lines in error.log. A paint click right after another one was once
lost (likely while the markers redrew).
Built as in the contract, with these choices:
- A new building for a goods or category rule is the **cheapest** one that can be built there (the plan's cost formula),
  not the first in a list; a standing producer grows highest tier first.
- Category rules start a building of the category only when none of it stands; afterwards they grow the standing one.
- Market access = the Construction Plan's logistics order (first that can be built), payback limit on a standing one.

**Redesign 2026-11-07 (100 slots, location copies, edit buffer, symbols): tested in game the same day (Cyprus save,
synced build)**: goods icons, colour tiles (`framesize` + `frame = "[FixedPointToInt(...)]"`), the edit buffer, the
re-copy on select, the "+" new profile and the picker's Symbols group (static paths) work. Broken there and fixed since
(not yet seen in game): every icon drawn from a flag (symbols and categories) drew nothing, because a texture built with
`Concatenate` draws nothing and `GetFlagName` returns the localized name. Flags are now drawn as frames of the flag
strip from a frame number stored beside the flag (`_in`, `_r<r>_cn`), the same mechanism as the colours; a test fails
on any texture or frame that uses `Concatenate` or `GetFlagName`. Still to check in game: a flag icon from the strip
(slot tiles, badge, editor, rule targets in the editor), names via `[Var.GetFlagName]`, the `$KEY$`-nested tile
tooltips, `Select_CString` inside `SelectLocalization`, a profile's copy reaching its locations after each kind of edit,
the `pp_lprof_new_color` script value (`modulo`), and the load time (about 104,100 expanded script lines for the
profiles, 68,800 before at 12 slots). A save from before the redesign has profile locations without copies, and slots
with a flag icon or category rule set before the frame numbers have no frame: select each profile once in the editor
(that copies it to its locations again) and pick such icons and category rules anew, or assign the profiles anew.
Verified in game before: `MakeScopeFlag(GetVariableSystem.Get(...))` (picker, paint frame), the badge tooltips' nested
texts, clicks on the marker frames, the `switch` on `goods:` keys in the rule dispatch.
Known gaps: no tier upgrades (a researched successor freezes the old tier: state "cannot be built"), fur has no
producer, profile names, profiles across games.

In game 2026-11-07 (Cyprus save `pp_cyprus_check`, after the 100-slot rework): re-copy by selecting each old profile
restores the badges; "+" makes a new profile; a symbol icon (City) draws from the frame strip in the editor, the tiles,
the palette and the map badge; a category rule (Trade Buildings) started a Marketplace in Nicosia in the next monthly
pass. Found and fixed: `Concatenate` cannot feed a texture and `GetFlagName` returns the localized name, so flag icons
use the numbered strip; clearing a location copy no longer removes the rule frame numbers (never set on a location,
the engine logged "used but never set"). Error log clean of profile lines.
