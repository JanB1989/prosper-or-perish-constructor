# Location Profiles (design contract, branch `location-profiles`, 2026-11-07)

Jan, 2026-11-07: the player defines **profiles** ("my furniture town": an icon, a colour, ordered build rules) and
assigns them to locations straight on the map. Global Construction Plan rules run everywhere **except** in a location
with a profile: there the profile's rules have priority (the global rules leave it alone, like v2's Own Rules mode).
The map shows each location's profile as a badge (its icon on its colour) beside the plan icons.

Branch `location-profiles` = `location-plan` + `player-construction-manager` (merge 91019fcb). Worktree
`../ProsperOrPerishConstructor-locplan`. Builds on: `location_plan.py` (plan items, map markers),
`construction_plan.py` + `pp_construction_plan*.txt` (monthly pass, budget, payback, producers per good).

UI name: **Location Profiles** (the v2 "Profiles" on the Plan tab are saved country settings; different thing).

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
| `pp_lprof_r<r>_st` | rule r state after the last pass (+100): 1 started, 2 nothing to build (all standing levels' payback too long / at max), 3 a level under construction, 5 payback too long, 6 cannot be built here, 7 budget, 8 market lacks the construction goods, 9 waiting for an earlier rule's construction this month |
| `pp_lprof_r<r>_est` | the shortest payback the rule found (years + 100; 1099 = no profit), shown beside state 5 |

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
| `pp_lprof_assign` | location (root) | `pp_slot` (`s<k>` or `none`) | set / remove the location's profile and its copy; keep `pp_lprof_locs`; a profile replaces the location's v2 own-rules mode (removes `pp_cplan_mode` and its `pp_cplan_own` entry); a location that has the slot already keeps it (and its states); `refresh_map_colors = yes` |
| `pp_lprof_new` | country (root = player) | `pp_slot` (`next`; `s<k>` works too) | switches the slot on: icon `goods:lumber`, colour k (wrapping at 8, script value `pp_lprof_new_color`), no rules; the editor shows it. The window's header has the "+" button while `pp_lprof_first_free` > 0 |
| `pp_lprof_select` | country | `pp_slot` (`s<k>`) | the editor shows slot k (its data into the edit buffer); its locations get its data again |
| `pp_lprof_set` | country | `pp_slot`, `pp_field`, `pp_key` | icon or rule target of the slot = item `pp_key` (goods → `_g`/`_ig`, category or symbol → `_c`/`_ic`, clears the other; a symbol only for the icon) |
| `pp_lprof_color` | country | `pp_slot`, `pp_col` | colour |
| `pp_lprof_payback` | country | `pp_slot`, `pp_field` (r1..r5), `pp_dir` | step the rule's payback limit through `payback_steps` (down from "any" = the last step) |
| `pp_lprof_rule_clear` | country | `pp_slot`, `pp_field` | empty rule r (and its states in the slot's locations) |
| `pp_lprof_rule_move` | country | `pp_slot`, `pp_field`, `pp_dir` | swap rule r with its neighbour (and their states) |
| `pp_lprof_delete` | country | `pp_slot` | clear the slot, unassign it from every location (their copies go), empty the edit buffer when it holds the slot |

Every button that changes a slot ends in `pp_lprof_commit` = `pp_lprof_write` (staged copy → slot) +
`pp_lprof_publish` (staged copy → edit buffer and → every location with the slot) + `refresh_map_colors = yes`.

## Monthly pass (in `pp_cplan_run`, first group, own share like the other groups)

Only when the Construction Plan is on (`pp_cplan_on`). `pp_cplan_location_ok` also requires `NOT = { has_variable =
pp_lprof }`, so every global rule (food, logistics, goods) leaves profile locations alone. For each location in
`pp_lprof_locs` still owned: rules 1..rules of its copy in order (`pp_lprof_location_rules` = `pp_lprof_rule = { r }`
per rule; no slot is looked at); the first rule that starts a construction ends that location for the month (later
rules get state 9). A rule with a goods target: expand a standing producer of the good whose next level pays back
within the limit (highest tier first, as v2's Expand), else, when no producer stands here, start the first buildable
producer (v2's try order; the first level has no profit to measure, so no payback check). `logistics` = v2's logistics
try for this location. A category target: the same over the buildings of that category (generated list per category:
player-buildable building types whose `category` is it). Guards as v2: `location_and_owner_can_build`, construction
goods in the market, never a second level under construction, budget (`pp_cplan_budget_left`). The monthly cleanup
takes the profile and its copy from locations that lost it (`pp_lprof_clear_location`).

## UI

- **Location Plan window**: a "Profile" row: the location's badge, None, "Edit profiles", the slot tiles (icon on
  colour, 8 per row, rows only while they hold a used slot) to assign. The location window's Infrastructure tab starts
  with the same row (`pp_lprof_location_row` = `pp_lprof_plan_row`).
- **Profile editor** (`gui/pp_location_profiles.gui`, scripted widget): the header's "+" (new profile in the first
  free slot), the profile list (used slots; a click selects one, `pp_lprof_select`), the edited profile (one body, the
  edit buffer): icon (click → picker mode `icon`), 8 colour swatches, rules 1..5 (target icon → picker mode `r<r>`,
  payback `< N years` / `any` with - / +, up / down, clear), Delete. One shared item picker (the plan's items + Market
  access, and the Symbols group for the icon only); clicking an item calls `pp_lprof_set` with the open picker mode.
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

## Not in v1

Profile names (typed text cannot be stored); profiles carried to a new game; level caps per rule; conditions per rule
(the v2 location rules keep those).

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
