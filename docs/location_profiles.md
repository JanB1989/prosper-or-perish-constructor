# Location Profiles (design contract, branch `location-profiles`, 2026-11-07)

Jan, 2026-11-07: the player defines **profiles** ("my furniture town": an icon, a colour, ordered build rules) and
assigns them to locations straight on the map. Global Construction Plan rules run everywhere **except** in a location
with a profile: there the profile's rules have priority (the global rules leave it alone, like v2's Own Rules mode).
The map shows each location's profile as a badge (its icon on its colour) beside the plan icons.

Branch `location-profiles` = `location-plan` + `player-construction-manager` (merge 91019fcb). Worktree
`../ProsperOrPerishConstructor-locplan`. Builds on: `location_plan.py` (plan items, map markers),
`construction_plan.py` + `pp_construction_plan*.txt` (monthly pass, budget, payback, producers per good).

UI name: **Location Profiles** (the v2 "Profiles" on the Plan tab are saved country settings; different thing).

## Why slots

Script cannot create named data while the game runs: every variable name and every GUI row exists in the files. A
profile is therefore a generated **slot** `k = 1..slots`. `slots` is one number in `[location_profiles]`; unused slots
are hidden. Raising it later changes only that number.

## Config `[location_profiles]` (constructor.toml)

```toml
[location_profiles]
slots = 12            # profiles per country
rules = 5             # ordered rules per profile
payback_steps = [1, 2, 3, 4, 5, 7, 10, 15, 20, 30, 40, 50]   # years a rule's limit steps through; past the last = any payback
colors = [[0.80, 0.25, 0.20], [0.90, 0.55, 0.15], [0.85, 0.80, 0.25], [0.30, 0.65, 0.30],
          [0.25, 0.60, 0.70], [0.25, 0.40, 0.80], [0.55, 0.35, 0.75], [0.75, 0.40, 0.60]]
```

## Items (icons and rule targets)

The plan items of `location_plan.plan_items` (goods by goods category, then the 8 building categories) plus the target
**market access** = the good `logistics` (its producers are the logistics buildings; hidden from the plan picker, shown
as "Market access" in profiles). Every item has a flag key: the good key (`furniture`, `logistics`) or the category key
(`trade_category`).

## Variables (all numbers carry +100; `var:x = n` compares scopes, so numbers use < / > ranges)

Country (the player's):
| Variable | Meaning |
|---|---|
| `pp_lprof_<k>_on` | slot k in use (yes) |
| `pp_lprof_<k>_ig` / `pp_lprof_<k>_ic` | icon: a goods scope (`goods:furniture`) **or** a category flag (`flag:trade_category`); one of the two |
| `pp_lprof_<k>_col` | colour 1..8 (+100) |
| `pp_lprof_<k>_r<r>_g` / `_r<r>_c` | rule r target: goods scope or category flag (unset both = empty rule) |
| `pp_lprof_<k>_r<r>_pb` | rule r payback limit in years (+100); unset = any payback |
| list `pp_lprof_locs` | locations with a profile (for the monthly pass) |

Location:
| Variable | Meaning |
|---|---|
| `pp_lprof` | assigned slot k (+100); unset = no profile |
| `pp_lprof_r<r>_st` | rule r state after the last pass (+100): 1 started, 2 nothing to build (all standing levels' payback too long / at max), 3 a level under construction, 5 payback too long, 6 cannot be built here, 7 budget, 8 market lacks the construction goods, 9 waiting for an earlier rule's construction this month |

GUI reads: `GetPlayer.MakeScope.Var('pp_lprof_3_ig').GetGoods.GetIcon` (texture), `.GetGoods.GetKey`,
`Var('pp_lprof_3_ic').GetFlagName` (category key; texture `gfx/interface/icons/building_categories/<key>.dds` through a
`Select_CString` chain over the 8 categories), `Var('x').IsSet`, `Var('x').GetValue` (CFixedPoint).

## Scripted GUIs (all in `in_game/common/scripted_guis/pp_location_profiles.txt`)

Parameters go in as flag scopes: `AddScope('pp_slot', MakeScopeFlag('s3'))`, `AddScope('pp_key', MakeScopeFlag('furniture'))`,
`AddScope('pp_field', MakeScopeFlag('icon'|'r1'..'r5'))`, `AddScope('pp_dir', MakeScopeFlag('up'|'down'))`,
`AddScope('pp_col', MakeScopeFlag('c1'..'c8'))`.

| Scripted GUI | Scope | Params | Effect |
|---|---|---|---|
| `pp_lprof_assign` | location (root) | `pp_slot` (`s<k>` or `none`) | set / remove the location's profile; keep `pp_lprof_locs`; a profile replaces the location's v2 own-rules mode (removes `pp_cplan_mode` and its `pp_cplan_own` entry); `refresh_map_colors = yes` |
| `pp_lprof_new` | country (root = player) | `pp_slot` | switches slot k on: icon `goods:lumber`, colour k (wrapping at 8), no rules. The GUI shows a "+" tile only at the first slot not on (generated per slot) and passes that slot; the same click sets the GUI variable `pp_lprof_edit` = `s<k>` |
| `pp_lprof_set` | country | `pp_slot`, `pp_field`, `pp_key` | icon or rule target of slot k = item `pp_key` (goods → `_g`, category → `_c`, clears the other) |
| `pp_lprof_color` | country | `pp_slot`, `pp_col` | colour |
| `pp_lprof_payback` | country | `pp_slot`, `pp_field` (r1..r5), `pp_dir` | step the rule's payback limit through `payback_steps` (down from "any" = the last step) |
| `pp_lprof_rule_clear` | country | `pp_slot`, `pp_field` | empty rule r |
| `pp_lprof_rule_move` | country | `pp_slot`, `pp_field`, `pp_dir` | swap rule r with its neighbour |
| `pp_lprof_delete` | country | `pp_slot` | clear the slot and unassign it from every location |

All edits end with `refresh_map_colors = yes` where a badge can change.

## Monthly pass (in `pp_cplan_run`, first group, own share like the other groups)

Only when the Construction Plan is on (`pp_cplan_on`). `pp_cplan_location_ok` also requires `NOT = { has_variable =
pp_lprof }`, so every global rule (food, logistics, goods) leaves profile locations alone. For each location in
`pp_lprof_locs` still owned: rules 1..rules in order; the first rule that starts a construction ends that location for
the month (later rules get state 9). A rule with a goods target: expand a standing producer of the good whose next level
pays back within the limit (highest tier first, as v2's Expand), else, when no producer stands here, start the first
buildable producer (v2's try order; the first level has no profit to measure, so no payback check). `logistics` =
v2's logistics try for this location. A category target: the same over the buildings of that category (generated list
per category: player-buildable building types whose `category` is it). Guards as v2: `location_and_owner_can_build`,
construction goods in the market, never a second level under construction, budget (`pp_cplan_budget_left`).

## UI

- **Location Plan window**: a "Profile" row: the location's badge, the slot tiles (icon on colour) to assign, "None",
  "Edit profiles".
- **Profile editor** (`gui/pp_location_profiles.gui`, scripted widget): slot list (+ New), the edited slot (GUI variable
  `pp_lprof_edit` = `s<k>`): icon (click → picker mode `icon`), 8 colour swatches, rules 1..5 (target icon → picker mode
  `r<r>`, payback `< N years` / `any` with - / +, up / down, clear), Delete. One shared item picker (the plan's items +
  Market access); clicking an item calls `pp_lprof_set` with the open picker mode.
- **Map right-click menu** (vanilla `LocationContextMenu` in `context_menu.gui`, patched at finalize like
  `map_markers.gui`: a copy of vanilla with one section added, a test checks the rest is vanilla): for player locations,
  a "Location Profile" section with the slot tiles, None, and "Open plan".
- **Paint mode** in the Location Plan map mode: a palette (scripted widget, visible only in that map mode) with the slot
  tiles and an eraser; the brush is the GUI variable `pp_lprof_brush` (`s<k>` / `none`). While a brush is set, every
  player location's marker shows a frame; a click on it calls `pp_lprof_assign` with the brush.
- **Map marker** (`location_plan.render_markers`): the badge (profile icon on its colour) first, then the plan icons.
  Badge tooltip: the profile's rules with this location's states.

## Not in v1

Profile names (typed text cannot be stored); profiles carried to a new game; level caps per rule; conditions per rule
(the v2 location rules keep those).

## Status (2026-11-07)

Built on `location-profiles`; all 1522 tests pass; synced live. **Tested in game 2026-11-07** (England save
`pp_lplan_icons_england` -> `pp_lprof_england`, 2 May 1337): editor (new profile, icon and rule pickers, colour, payback
steps), paint palette (frames on every English location, brush assigns, eraser removes), map right-click menu
(Location Profile section assigns), Location Plan window row, badge tooltip with rule states; one month with the global
groups off started two Lumber Mills from the profile (ledger "(location profile)"); furniture showed "cannot be built
here" in rural locations (the workshop needs a town), market access the same (logistics gate: 15 building levels). No
profile lines in error.log. A paint click right after another one was once lost (likely while the markers redrew).
Built as in the contract, with these choices:
- A new building for a goods or category rule is the **cheapest** one that can be built there (the plan's cost formula),
  not the first in a list; a standing producer grows highest tier first.
- Category rules start a building of the category only when none of it stands; afterwards they grow the standing one.
- Market access = the Construction Plan's logistics order (first that can be built), payback limit on a standing one.
- The editor, palette, right-click section and marker take about 530 KB of generated GUI (every slot x rule written out).
- Category icons come from `Concatenate(..., GetFlagName, '.dds')`; goods icons from `GetGoodsIcon(Var.GetGoods.Self)`.

Verified in game: `MakeScopeFlag(GetVariableSystem.Get(...))` (picker, paint frame), the badge tooltips' nested texts,
clicks on the marker frames, the `switch` on `goods:` keys in the rule dispatch. Not yet seen: a category icon or rule
(`GetFlagName`), a goods rule that expands a standing producer by payback, a long run.
Known gaps: no tier upgrades (a researched successor freezes the old tier: state "cannot be built"), fur has no
producer, profile names, profiles across games.
