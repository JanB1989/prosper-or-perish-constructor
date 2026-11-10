# Construction Plan: Towns and Buildings (country rules)

Jan, 2026-11-10: "I also want the functionality to decide on global buildings to be built. We can say: we want
universities and stuff like that. Upgrading cities and applying town rights. We have to be very careful to keep the UI
tight."

Status: built on `location-profiles`; generator-level tests pass. The engine facts the rules stand on were tested in
game on 2026-11-10 (below), and the same day the tab and every rule ran in game in the test world ("In game: the
rules", at the end).

The third tab of the Construction Plan window. Everything is off until the player ticks it, nothing is kept between
passes. Module `src/prosper_or_perish_constructor/construction_plan_country.py` (run by `ppc build` right after
`construction_plan.apply`), config `[construction_plan_country]` in `constructor.toml`, tests
`tests/test_construction_plan_country.py`. The monthly pass, the budgets that save (the group pays from its purse and saves for the first thing it cannot pay
for, a building or a town or city upgrade; docs/player_construction_manager.md "Budgets that save"), the weights and
the ledger are
`construction_plan.py`'s and `pp_construction_plan.txt`'s (docs/player_construction_manager.md).

## Verified in game (2026-11-10, new game as England, EU5 1.4.7, console and run files)

**A. Town and city upgrades.** `construct_location_rank` charges the gold itself, at once: a town 482.14 (the price 500
less the market's price impact, the number the game's button shows), a city 1,928.58. It is a normal, visible
construction ("Founding a Town"), 365 days (a city 730), one progress a day, and it draws construction goods from the
market (`build_town_demand`: glass 1, masonry 2, lumber 1; `build_city_demand`: 2 / 4 / 2); without them it stalls (90
of 365 after a year in a market short of masonry). It holds the location's construction slot, first in first out: a
building started after it does not move until the town stands. Where the rank's `allow` fails (too few people, wrong
rank) the effect starts nothing and charges nothing. `can_become_rank` is **not** usable as a gate: it also reads the
market's stock in a way that is not understood and was false everywhere on day 3 while the game offered Found Town and
the effect worked.

**B. Urban rights.** The raw `grant_town_rights` ignores the right's `allow` and `potential` and the location's slot
maximum, and charges nothing. `pay_price = price:grant_town_rights` in country scope takes exactly the price (20).
`has_max_town_rights` is true once rights >= slots (and on rural settlements, which have none).
`modifier:can_grant_town_rights = yes` reads true. Granting `pp_cloth_rights` where `pp_cloth_charter` is held puts
the two side by side and both bonuses count: skipping a location that holds the charter is required.

**C. Building upgrades.** `construct_building = { building_type = <successor> }` where the older tier stands **is** the
game's Upgrade button: it pays the upgrade price the game shows (Spinners' Guild to Cloth Workshop: 196 shown, 196.43
paid), runs as a normal construction and on completion turns one level of the older tier into one of the successor.
`building_can_be_upgraded_by = <country>` (building scope) is true on every standing older tier once the successor is
researched; `building_type_is_obsolete` (country scope) flips with it. Dock to Dry Dock behaved the same. Only the
direct successor was tested.

## What it does

The gold rule group "Towns and Buildings" (`pp_cplan_group_country`, construction code 107) runs three rules in this
order; the monthly pass counts its weight only while `pp_cplan_country_active` is 1 (one of them is switched on).

**1. Upgrade buildings** (one switch, `pp_cplan_upgrade`; ledger step 3). Every owned location that passes
`pp_cplan_country_site` (not `integration_level = conquered`, no `pp_lprof_xc`, a free construction slot) and holds a
standing, open building with `building_can_be_upgraded_by`, highest maximum control first (no control line). There,
the first such building whose direct successor passes the country's part of `can_build_building`, where the market
holds the successor's construction goods: `pp_cplan_construct` with the successor (the group's purse, reserve, ledger as any
building). One upgrade a location a month. The location's part of the can-build check is not asked: the game's
upgrade does not need it, and it is what refuses a new building of an older tier. A closed older tier is left alone.
The successor map is generated from the building types (`obsolete = <older tier>`, the base game and the mod, DLC-only
keys left out): **155 pairs over 150 older tiers**; where several types name the same older tier (the mines' and the
lumber mill's variants), they are tried in the game's file order and the first the country can build wins. The plan's
cost estimate for the purse check is a new building's (the game charges the upgrade price, which is what is booked).

**2. Public buildings** (ledger step 1). One tile per building of `public_buildings`. A building with later tiers
(Dock, Dry Dock, Shipyard, Grand Shipyard, Naval Base; Early Council Hall, Council Hall, Modern Council Hall) is one
tile under its first tier's key. For every ticked tile in the config's order: the country's part of
`can_build_building` once per type, highest tier first, only the first tier that passes is tried; then one level in
every owned location that passes `pp_cplan_country_site`, has `max_control` at or above the player's line, has no tier
of the line standing, passes the location's part of `can_build_building` and whose market holds the construction
goods (`pp_cplan_goods_here_<demand>`), highest maximum control first. No worker check.

*Boosters only where their goods are made* (2026-11-10 evening, Jan, 2b053cff; not seen in game yet): a building of
the list whose modifier blocks (`modifier`, `raw_modifier`; every tier, the definition and what was injected) hold
nothing but `local_<good>_output_modifier` lines, at least one above 0, is a booster (`booster_goods`, read from the
building itself, nothing to configure). Today that is **Sawmill, Windmill, Local Smelters and Terraces**; the build
summary counts them ("N public buildings (M boosters)"). A booster is built only in locations that make one of its
goods: its raw material is the good, or a standing building there produces it (generated location trigger
`pp_cplan_pub_where_<key>`: `raw_material ?= goods:<good>` or `any_buildings_in_location` with `building_produced_goods`,
the Location Plan's "made here"); every other public building asks `pp_cplan_pub_anywhere` (always yes). The trigger is
passed as `where` to `pp_cplan_country_public` and sits in its location filter before `can_build_building`. The tile's
tooltip names the goods and says to mark the building in a location to have one anywhere else (a building mark is
forced, `docs/location_plan.md`). Before, a ticked Windmill went into every location that could have one, whether
anything there was milled or not.

**3. Towns and cities** (ledger step 2). Two switches. Every owned location that passes `pp_cplan_country_site`, has
the rank below, `modifier:cannot_upgrade_location = no`, the game's own population minimum of the rank (read at
generation from the rank's `allow` in `location_ranks`, mod over vanilla: town 5, city 30 thousand), for a town also
the player's population line, and whose market holds the upgrade's construction goods
(`pp_cplan_country_goods_<rank>`: the plan's months of the draw of every good of the rank's `construction_demand`; the
core writes its goods checks for building demands only, so these two are generated here by the same rule). Biggest
population first. Where the market lacks an upgrade's or a building's construction goods nothing starts and the
group's pane counts it (2026-11-10; the goods check sits in the rule's body, not in its location filter). The purse
check reads `pp_cplan_country_cost_<rank>`: the price of the price database x the
construction goods' price factor in the location's market (the formula the plan uses for buildings; it matches A).
`construct_location_rank` then charges by itself; the gold is measured before and after, and the upgrade is **booked
only when gold was paid** (started, spent, ledger, test-log lines), because the effect refuses silently.
`pp_cplan_rank_charge` stays the one place for the charging decision and charges nothing.

**Urban rights** (no gold; `pp_cplan_country_rights`, once a pass after the groups). One switch and a tile per right.
While the switch is on, the country has `can_grant_town_rights` and the political influence to keep plus one grant's
price: for every ticked right whose potential passes, in the rule's order, every owned location that is not only
conquered, has no `pp_lprof_xc`, has room for a right (`has_max_town_rights = no`), got none this month and holds
neither the right nor its upgrade partner, biggest population first: when the right's allow passes (location as
`scope:target`) and the influence still reaches, `grant_town_rights` and `pay_price = price:grant_town_rights`. Every
check the raw effect skips (B) is asked by the rule.

- Order: `rights_order` first, then the specialization rights, then the rest, each in database order. The game needs a
  right loaded before the charter that upgrades into it, so the stronger right always comes first and a location that
  qualifies for both gets it directly.
- **Charter upgrades are not part of this version.** A location that holds a charter is skipped for its stronger right
  (granted on top, both would stand and both bonuses count, B), and a charter is never granted on top of that right.
  The section's tooltip tells the player to upgrade those by hand.

## The rights database

Read at generation from every `in_game/common/town_rights/*.txt` of the base game, its DLC folders and the compiled mod
in load order: a later plain / `REPLACE:` / `TRY_REPLACE:` definition replaces the earlier one, `INJECT:` /
`TRY_INJECT:` adds its blocks (an injected `potential` or `allow` is one more block in the trigger, so both must pass).

| | count |
|---|---|
| rights in the database | 110 |
| switched off (`potential` or `allow` is exactly `always = no`: vanilla's bundled specialization rights) | 18 |
| only in a DLC folder (Across the Pillars), left out | 11 |
| tiles | 81 (35 of them the mod's `pp_<good>_charter` / `_rights` and `pp_iron_rights`) |

DLC-only rights are left out because the mod's script may not name a key only a DLC defines (AGENTS.md, DLC Content); a
player with Across the Pillars grants those eleven by hand. Per right three scripted triggers:
`pp_cplan_right_potential_<key>` (country), `pp_cplan_right_allow_<key>` (country, `scope:target` = the location) and
`pp_cplan_right_site_<key>` (location). The blocks are the database's text, re-indented; the one change is the spelling
of a `NOT` with several conditions as `NOR` (what the engine reads; the plan's scripts never hold such a `NOT`).

**Rights unlocked by advances.** The only unlock outside a right's own file is the advance key
`unlock_town_rights = <right>` (base game: 25 lines in `0_age_of_traditions`, `0_age_of_discovery`,
`culture_scandinavian`, `culture_netherlands`; the mod: 17 in the Printing Press advance; no reform, law or privilege
uses it). A right no advance lists is unlocked from the start; a listed one needs one of those advances. The potential
trigger therefore starts with `has_advance = <advance>` (an `OR` when several unlock it): 24 of the 81 rights, among
them Flemish Cloth Industries, the four Scandinavian privileges, the two Grand rights and the mod's 17 rights.

## Icons

- Buildings: `gfx/interface/icons/buildings/<key>.dds` (vanilla under `main_menu/gfx`, the mod's under `in_game/gfx`).
  All 39 configured buildings have one. A tile without a picture is not generated and `ppc build` names it.
- Rights: vanilla draws `TownRights.GetType.GetIcon`, which is `gfx/interface/icons/town_rights/<key>.dds` or the
  engine's `_default.dds`. The tab writes the same path: 74 rights have their own picture (all 35 of the mod's), 7 use
  `_default.dds` as in the game (Grand Market Rights, Grand Staple Port, Staple Port, Granary Town, Plantation Charter,
  Royal Free Cities, Novo Brdo Charter).

## Config `[construction_plan_country]`

```toml
public_buildings = ["early_council_hall", ...]   # the tiles, in order; a line under its first tier's key
control_pct = 50          # line: maximum control, % (0..100, control_step = 10)
town_population = 30      # line: thousand people (town_population_min .. _max = 5..100, _step = 5)
keep_influence = 50       # line: political influence kept (0..keep_influence_max = 100, _step = 5)
rights_order = []         # rights the rule tries first
tiles_per_row = 11
```

The numbers are placeholders for Jan to tune; none is written into a text.

## Names

Effects: `pp_cplan_group_country` (the gold group), `pp_cplan_country_rights`, `pp_cplan_country_declare` (flags, for
the never-run branch of `pp_cplan_run`); inside: `pp_cplan_country_upgrades`, `pp_cplan_country_upgrade_building`,
`pp_cplan_country_upgrade_to`, `pp_cplan_country_buildings`, `pp_cplan_country_public`, `pp_cplan_country_ranks`,
`pp_cplan_country_rank_up`, `pp_cplan_rank_charge`, `pp_cplan_country_grant`.
Triggers: `pp_cplan_country_site`, `pp_cplan_country_rights_site`, `pp_cplan_country_upgradable` (building scope),
`pp_cplan_country_goods_<rank>`, `pp_cplan_pub_line_<building>`, the three per right.
Script values: `pp_cplan_country_active`, `pp_cplan_country_control_pct` / `_control_line`, `_town_pop`,
`_keep_influence`, `_influence_need`, `pp_cplan_country_cost_<rank>`, `_rights_n`, `pp_cplan_pub_show_<building>`,
`pp_cplan_right_show_<right>`. Scripted GUIs: `pp_cplan_country_toggle`, `pp_cplan_country_step` (`scope:pp_key`,
`scope:pp_dir`). GUI type: `pp_cplan_country_tab`. Texts: `PP_CPLANC_*`.

| Variable (+ 100 where a number) | Scope | Meaning |
|---|---|---|
| `pp_cplan_upgrade` | country | the building upgrades are on |
| `pp_cplan_pub_<building>` | country | the tile is ticked |
| `pp_cplan_rank_town`, `pp_cplan_rank_city` | country | the town and city upgrades are on |
| `pp_cplan_rights_on`, `pp_cplan_right_<right>` | country | the rights rule is on; the right is ticked |
| `pp_cplan_ctl`, `pp_cplan_tpop`, `pp_cplan_infl` | country | the three lines |
| `pp_cplan_rights_n` | country | rights the last pass granted |
| `pp_cplan_up_try` | location | during the upgrade rule only: an upgrade was tried here this month |
| `pp_cplan_right_mark` | location | during the rights rule only: a right was granted here this month |

Ledger (`pp_cplan_log_step`): 1 a public building, 2 a town or city upgrade, 3 a building's upgrade. Buildings and
building upgrades go through `pp_cplan_construct_now` (the upgrade's building type in the list is the successor; its
reason value is the location's maximum control in %). A town or city upgrade writes its own entry (it has no building
type): lists `pp_cplan_log` and `pp_cplan_log_107`, the country's started / spent / `_107` numbers, and the location's
`pp_cplan_log_rank` (the window names the upgrade by it), `pp_cplan_log_cost_107` (added to the cost of a building the
group started there in the pass) and, unless such a building left its reason, `pp_cplan_log_step_107` 2 and
`pp_cplan_log_val_107` (population, thousand + 100); in a test run the lines `PP_CPLAN_TLOG_107` and the location.
Every rule group keeps its own entry of a location (docs/player_construction_manager.md, "The ledger is per rule
group and location").

## The tab

Three header rows (title, switches, a line with - and +), tiles under the first and the third; no paragraphs, tooltips
carry the words. The Upgrade switch sits in the public buildings' row. A tile is vanilla's toggle tile (pressed, gold
glow = ticked) with the building's or right's picture; its tooltip is the game's own name (`ShowBuildingTypeName`,
`ShowTownRightsName`) and one sentence. A tile shows while the country could use it (any tier's country can-build; the
right's potential) or while it is ticked. Rows of 11; a row takes no room while none of its tiles shows. The 26 rights
every country sees come first (full rows), the rest follow in the rule's order; the rights scroll.

## In game: the rules (2026-11-10, test world, new game as Castile, EU5 1.4.7)

Seven monthly passes over two sessions; gold, political influence, advances and market goods by console; the plan's
test lines (`pp_cplan_ai_test`) in debug.log. No plan line in error.log from a load or a pass.

- **Upgrades.** With `tools_workshop_advance` and `pottery_workshop_advance` researched the first pass started 16
  Tools Workshops over Tools Guilds, later passes Pottery Workshops; the ledger booked 181 to 502 gold each (what the
  game took).
- **Public buildings.** A ticked Library started in Valladolid once the market held the books its construction needs;
  before that the goods guard held it back in every location (24 books asked, none in the four markets).
- **Towns.** No rural settlement started until the market held glass (12 asked): then Sepulveda and Medina del Campo
  (50.6 and 49.3 thousand people, line 25) started "Founding a Town", 564 gold each booked.
- **Cities.** Salamanca and Leon (43.8 and 43.7 thousand people) started the city upgrade, 1,366 gold each booked,
  with the building upgrades and the Library switched off (a town with one slot gives it to those first).
- **Urban rights.** Market Charter went to Granada, then to Sevilla (the game's own message each time); political
  influence 100 -> 80 and 84.1 -> 64.1 (the price 20). At 82.7 with 65 kept nothing was granted (85 needed).
- **Two slots.** Nine locations have two; the first pass started two constructions in each. `finish_constructions
  <location>` (console) frees a location for the next pass.
- **The tab.** Ticks, the two rank switches, the upgrade and rights switches and the three lines change their
  variables; tooltips name buildings and rights. The rights' rows stood spread over the whole scroll area (a vbox
  there is stretched): they are flowcontainers in a vertical flowcontainer now. Cost: 0.07 ms of script a frame.

## The grids wrap (2026-11-10, second in-game round)

A hidden tile used to leave its fixed row: Castile saw building rows of 4, 3, 2 and 1 tiles and rights rows of
unequal length. Static rows cannot wrap, so the place of every tile among the tiles that show is computed by script
and kept on the country: `pp_cplan_tp_<tile>` = place + 100 (unset = hidden), `pp_cplan_tc_pub` / `pp_cplan_tc_right`
= the tiles that show + 100 (`pp_cplan_country_layout_do`, generated). It runs when the tab opens (scripted GUI
`pp_cplan_country_layout`: the tab's button, the window's opener, the button in the location window's header) and
after every tick of a tile (`pp_cplan_country_toggle`). Row r of a grid holds a copy of every tile from its first
place on (a tile's place is never past its own number: 90 building tiles in 4 rows, 340 right tiles in 8), each
shown while its place falls in that row; a row shows while the grid has tiles for it. The conditions read only
variables: no `pp_cplan_pub_show_*` / `pp_cplan_right_show_*` value a frame any more (they are read by the layout
alone). In game: Castile's ten buildings in one row, its 28 rights in rows of 11, 11 and 6. The always-shown rights'
place variables are removed before they are set: the removal is their one use in script, else the game's check at
load logs "set but never used" for each.

Fuero Real, ticked beside Market Charter in the first round and never granted: its conditions are the game's, copied
faithfully. The rule goes through the ticked rights in its order and the political influence reached one grant a
month; Market Charter stands before Fuero Real and always found another location. With Market Charter unticked Fuero
Real is granted (second round).

## Open

1. (Done in the second round, 2026-11-10: the grids wrap, "The grids wrap" below.)
2. An upgrade to a successor that is not the direct one, and `pp_cplan_country_cost_<rank>` against the game's price
   (the plan's check uses the price times the goods' price factor; booked is what the game took).
3. `root` in the Stapelrecht potential; rights other than Market Charter (Fuero Real was ticked and found no
   location).

## Script time (2026-11-10)

The group no longer looks every month: each rule looks in its own months (`[construction_plan] look_months`: upgrades of
buildings 4 and 10, ticked buildings 6 and 12, towns and cities 2 and 8, urban rights 5 and 11), one rule a look. While
the group saves for something it does not look at all; once its purse can pay it goes back to that one location
(`pp_cplan_group_target`, generated `pp_cplan_country_target`: the rule's gates again). Console, to time the group:
`effect c:TAG = { pp_cplan_test_country = yes }` and `pp_cplan_test_rights`. docs/player_construction_manager.md
"Script time".
