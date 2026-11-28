# Prosper or Perish Constructor

## Repository Workflow

- Use `uv run ppc --help` as the canonical command index before running project workflows.
- Prefer `uv run ppc test`, `uv run ppc inspect`, `uv run ppc analyze`, and `uv run ppc blueprint ...` over raw `eu5-orchestrator` commands unless debugging the wrapper itself.
- Use parser/evaluator commands for game-data and blueprint questions instead of text-searching generated mod files.
- Treat `uv run ppc sync --yes` as a live deploy action. Do not run it unless the user explicitly asks to mirror into the live Paradox mod folder.
- The constructor output mod root is `mod/pp` under this repo, shown from Windows as `\\wsl$\Ubuntu\home\jan\development\ProsperOrPerishConstructor\mod\pp`.
- The repo folder `mod/pp` is short on purpose: every tracked path stays inside the Windows path budget and plain ASCII (`tools/check_path_lengths.py`, `tools/check_repo_files.py`, pre-commit, and `.github/workflows/windows-paths.yml` on real Windows; no exceptions). The live Paradox folder keeps its full name through `[deploy] target`.
- `uv run ppc sync --yes` first makes sure that repo-local output mod root is built/current, then copies that output to the configured live Paradox mod folder. Work either edits files directly in this repo-local output root, or edits source/config/blueprints that compile into that output root before sync copies it onward.
- Do not look for or use a nested `Constructor/mod/...` path in this checkout; the repo-local compiled mod path is `mod/...`.
- The sync reruns the World Builder start setup (70-100 s) only when one of its inputs changed. Its mod inputs are the
  traced list `WORLDBUILDER_MOD_INPUTS` in `cli.py` (folders it lists, files it opens by name); edits elsewhere in the
  mod (advances, on_actions, area preferences, AI scripts, localization) skip it. When the stage starts reading another
  mod file, add it there; `uv run python tools/trace_worldbuilder_inputs.py` measures the reads and exits 1 on a miss.
- Machine-local paths and deploy targets belong in ignored `constructor.local.toml`.
- Keep game-install paths in tracked config/examples, not in conversation memory. `constructor.load_order.toml` accepts Windows paths such as `C:\Games\steamapps\common\Europa Universalis V`; parser tooling resolves those to `/mnt/c/...` under WSL/Linux.
- Keep constructor mod roots relative to the repo where possible so the checkout can live on another native WSL/Linux path.
- Do not run project tooling from an old Windows-mounted checkout. If a mounted checkout exists, treat it as quarantined; copy specific files only when recovering data. Targeted read-only checks against the configured EU5 install are allowed.

## Generated Outputs

- Generated parquet, graph, report, and blueprint outputs are reproducible artifacts.
- Commit reusable config, accepted blueprints, scripts, docs, tests, and repo skills.
- Avoid reverting existing dirty mod or generated files unless the user explicitly requests it.

## Production Gate

- The AI's "too low profit margin" check reads one margin per building: that of the last production method it looks at
  that has an output (slots in file order, methods in listed order; `docs/ai_building_rulebook.md` 2.4i).
- Every enabled blueprint with a producing unique method names that method with a top-level `gate_method:` key. Its slot
  is the last `unique_production_methods` block and the method is listed last. The rest is ordered by importance:
  base slots first, the slots that follow the province store last (Province Food: Provisioning, Serve; the Grange's
  Surplus Sales), other slots and methods by output value,
  output-less methods first in their slot.
- `uv run ppc gate apply` flags unflagged blueprints by that rule and rewrites the order (slot labels,
  `production_method_slots` and `# slot N` comments follow). `uv run ppc gate check` must report 0 unflagged, 0 out of
  order, 0 legs to write, 0 problems; `ppc build` prints it and `tests/test_production_gate.py` enforces it. The crop
  farm generator renders the same order. Methods never move between slots.
- Gate leg (2026-09-30): every building with a market main good (base method's good, else its most valuable output;
  never a floor-pinned dummy or storage-leg good) gets a last slot "Market" with one method `pp_<building>_market_sales`
  that makes a little of that good for `offset`, at margin 1.0 (`[production_gate.leg]`). A one-method slot is always
  read, so the gate follows the main good's price whatever is researched or in the market. `ppc gate apply` writes and
  updates the leg (body block, slot list, localization, evaluation allow rules); the labour pass skips it. Buildings
  without a market good, gates on a store-following good (the Grange's Surplus Sales, the Tavern's Common Table: 0.1 offset -> 0.852 Province Food, so it passes 1.05 up to ~6 stored
  months whatever victuals cost, 2026-10-04),
  buildings that sell only for `offset` (the Cookshop line) get none. No good carries `ai_rgo_expansion_priority` > 0
  (`pp_goods_adjustments.txt` sets vanilla's seven to 0: five on 2026-10-09, iron and lumber on 2026-10-31 after three
  days back at vanilla's 0.025; a test guards it): an output good with it skips the margin check, so masons and
  quarries were built against the price. Every producer, iron and lumber included, passes the profit-margin gate. Never gate on a method that
  buys the building's own main good (inverts the AI's price response), except a token amount:
- Crop farms (farm v3, 2026-10-02): Provision takes a token of the crop (`crop_provision_input_gold` in
  `[building_scaling]`) and makes a fixed Province Food amount per level, so it is the farm's gate (margin about 15 at
  base prices, open at any realistic crop price) and the farms have no Market leg. The AI's price response is the
  farm's `ai_construct_weight` (`[general.ai_construct_weight]` in `config/crop_farms.toml`: slope x ((1 + local crop
  output modifier - the store curve's crop line `pp_stored_food_staple_line`) x market price / default price - 1) /
  (owner monthly income + offset); EU5 1.4 adds it raw at the end of the build score, after the gate). Fisheries,
  orchards and forest villages keep the buy-back Provision and their Market leg.
- Farm trade-off (2026-10-03, Jan; see Store Lever): tiers 2-3 run their cultivation at half throughput
  (`tier_cultivation_throughput`, goods in and out, on top of [age_food]) and make 55 % of their food per level at 12
  stored months as Province Food (`tier_province_food_share`, `provisioning.crop_food_split`; the total stays the
  age's flat food + the plain Provision); Rotational Farmsteads and Model Farms give +0.05 `global_<good>_output_modifier`
  of every crop farm good (`crop_farm_output`). `tests/test_crop_farms.py` pins the promise: at 0-12 stored months no
  crop farm loses money (so none lays off workers) on land 0 in a -0.5 harvest or on land -0.10 in a -0.4 harvest.
  Workers are laid off whenever profit at full staffing is negative unless the AI subsidises; `can_close` /
  `ai_forbid_shutdown` do not stop that.
- New, upgraded and game-start buildings take in every slot the best allowed method whose inputs are in the market, else
  the allowed method with the largest output, else the slot's first method (EU5 1.4.9, tested in game 2026-11-22; an
  upgrade picks every slot again). The order still decides that fallback.
- Rural producers next to a town (`docs/ai_building_rulebook.md` 2.5b): a rural-capable building (`rural_settlement = yes`)
  that can make any good a town-only building also makes gets no AI levels at rural locations with a town in the province
  once the evaluating country has both (for most goods from day 1), whatever the weight or price. Every method counts, so
  check a new method's good first. `tests/test_rural_town_goods.py` fails on a pair not listed in
  `[rural_town_goods.allowed]` (`constructor.toml`) and on a listed pair that no longer holds.

## Legacy Methods

- An upgrade never takes a recipe away (2026-10-04, Jan). Vanilla's manufacturing lines (guild -> workshop ->
  manufactory -> mill/factory, `obsolete` chains) drop the older tiers' recipes, and once the next tier is researched
  the engine refuses new copies of the old one ("There is no need to build a X when we can build a Y"), so an economy
  built on the old inputs could not grow. Every tier of a line in `[legacy_methods.lines]` keeps the recipes of the
  tiers below it as `pp_<building>_legacy_<origin method>` (`legacy_methods.py`).
- Recipe = a method's goods set (labour aside). Walking up a line slot by slot (slots matched by shared goods), a
  recipe is carried unless the tier has an own method needing a subset of its goods and no other advance; same goods
  merge, a carried recipe dominated by a cheaper one (fewer goods, no other advance, share at least as high) is
  dropped. Share = origin value / the origin slot's best own method, x `decay` (0.75) per tier moved up. Output = share x
  the slot's best own method (the reference), inputs = the origin's goods and labour scaled to the reference's margin,
  category / debug_max_profit from the reference, icon from the origin, unlock advances carried
  (`TRY_INJECT:<advance>`), name = vanilla's name of the origin + "(Old Ways)".
- The labour pass skips legacy methods (their labour is the origin's); the gate pass lists them after the building's
  own methods (`method_key`), so no new building starts on an old recipe. `uv run ppc legacy apply|check` must report
  0 blueprints to write and 0 problems (`ppc build` prints it; `tests/test_legacy_methods.py` also checks that no
  upgrade loses a recipe). Order after editing recipes: `ppc labour apply`, `ppc legacy apply`, `ppc logistics apply`,
  `ppc gate apply`.
- The cannon foundry/factory, firearms manufactory/factory and fine cloth mill run their line's two slots (barrels and
  ammunition, weaving and dyeing; the combined vanilla method split by goods cost, tin and lead restored); the leather
  line keeps tar in every tier (`labour.keep_goods: [tar]`: goods the labour pass never drops).

## Location-Gated Methods (2026-11-22, Jan)

- A unique method may carry `location_allow = { <trigger> }` (location scope): it runs only where the trigger holds. The
  game applies it when a building is created (new, upgrade, game start: setup buildings in a gate location start on the
  gated method), when the AI values a building, when the player picks a method and when the AI's method switch moves
  one; a running building is never checked again. So gate only on what never changes: soil
  (`has_location_modifier = pp_wb_soil_<soil>`), climate, vegetation and topography (World Builder classes by their own
  keys, e.g. `ha1300_veg_mixed_forest`), `has_river`, `is_coastal`. The lumber mills' Forest Elephants gate on the
  market's elephants, which can change: a mill keeps the method after its market loses them.
- Pattern (`tests/test_location_gated_methods.py`): the gated method has a slot of its own, an ungated empty method (no
  goods, no output) first, the gated method second, nothing else, one gate per slot. Never the Market leg, never alone
  in a slot (a one-method slot runs without any check), never beside ungated producers (the AI's switch picks one
  favourite per country, building type, market and slot whatever the gate; in game a gated method in a shared slot
  froze every Clay Pit outside its gate). Every `obsolete` successor carries a method with the same gate.
- Add-on rule (2026-11-22, Jan: a special method must be a bit better than the empty choice, which stays selectable;
  `tests/test_location_gated_methods.py` enforces it at base prices, `production_gate.load_prices`):
  - Size: the gated method adds 8-16 % of the building's output value per level, the other slots on their most
    profitable ungated method (Market leg included); near the top where its good is short or tight in the runs, about
    10 % where it is balanced. That is the size of the +0.10 attribute output modifiers of the same day.
  - Always better: its own output / input is at least 1.2 with `manual_labor` at 1.8, so the building with it beats
    the empty choice at the labour price the game sees (buildings leave a losing method only slowly). Labour-only
    methods (`base` class, labour 20 % of output) return 2.78 there.
  - It is rated by this rule, not by the whole-building throughput, margin or base-output bands of `ppc blueprint
    evaluate`; its `evaluation` allow rules say so in one wording. Gates on the market (the lumber mills' Forest
    Elephants) are price switches, not add-ons, and stay outside the rule.
  - To give a method more or less: labour-only methods scale `output` (the labour pass sets labour); methods with
    goods scale every amount by one factor (margin and labour share stay; output alone would move the margin).
- Text: a single failed condition is named in the method's tooltip, an `OR` only says the requirements are not met, so
  the method's `_desc` says where it works (links, no numbers). Slot names are positional (`<building>_slot_<n>`):
  `ppc gate apply` renumbers the blueprint's labels with the slots; the test wants a name for every slot.
- `set_production_method` ignores the gate and the building stays on the method: the compiled mod calls it nowhere (the
  test keeps it so); a script that ever needs it tests the gate itself.
- Passes and calculators (`location_methods.py`): the gate pass never makes a gated slot a base slot, never gates on a
  gated method and leaves it out of the main good (the slot sorts among the ordinary slots by value, so a small add-on
  comes first); labour tags them like any method (labour-only ones take `base`); tier prices and the Old Ways pass leave
  them out; the start market stock counts them only where the gate holds (World Builder attributes, the start markets'
  goods); the Construction Plan's business estimate wraps the method's profit in its gate and its market limit leaves it
  out; `tests/test_upgrade_not_worse.py` compares an upgrade outside every gate and inside each gate.
- The methods (2026-11-22, not tested in game; per level, % = share of the building's output value): Peat Cutting
  (peat soil; Charcoal Clamp labour 0.04 -> coal 0.10, 16 %; Charcoal Retort 0.056 -> 0.14, 15 %; coal tight from
  1502), Sun Pans (Coastal Saltern, arid, hot semi-arid or mediterranean climate, labour 0.05 -> salt 0.05, 15 %; salt
  short from 1602), Fulling Mill (Rural Clothmaker, a river through hills, mountains or valleys, wool 0.021 + lumber
  0.003 + labour 0.017 -> cloth 0.036, 10-13 %, tagged `craft_medieval`: the wheel does the pounding), Forest Glass
  (Rural Glassmaker, forest, mixed forest or woods, sand 0.018 + lumber 0.006 + labour 0.01 -> glass 0.015, 10 %). Building
  gates on soil and vegetation never change, so they sit in `location_potential`: the Clay Pit and Clay Washmill also
  stand on clay soil, the three bog iron tiers also on peat soil and swamp.

## Manufacturing Tiers, Specialization Rights, Trade Buildings (2026-10-06, Jan)

- Goal: production centres of institution countries out-produce old workshops and export; countries without the
  institutions stay with small guilds and sell raw goods. Applied by hand-run one-off edits (no pass), tagged in every
  touched body as `manufacturing tiers 2026-10-06` / `trade buildings 2026-10-06`.
- The 16 refined end-good lines of `[legacy_methods.lines]` (all but dyes, paper, saltpeter, wine) plus the jewelry
  guild, the rural cloth and glass makers: tier by max-level script value (guild-type = 1, `workshop_max_level` = 2,
  `manufactory_max_level` = 3, `mills_max_level` = 4). Own methods (not legacy, not Market Sales) scaled goods in and
  out: tier 1 x0.7, tier 2 x1.3 with margin +0.05, tier 3 x1.7 +0.10, tier 4 x2.0 +0.12 (default prices, labour 1).
  Workers per level (after the employment cut): tier 2 x1.15 (0.287), tier 3 x1.3 (0.325 burghers, 1.04 laborers),
  tier 4 x1.45 (1.16); these sizes are written directly, so the cut skips them. Stack malus in the staffed `modifier`:
  `local_<good>_output_modifier` -0.005 (tier 1) / -0.0025 (tier 2) per level. The market village and the tatara
  craft methods: x0.7 only. The steel mill (a mill without a line) got the tier-4 numbers by hand on 2026-10-15
  (Jan: steel too weak): 4 -> 8.946 steel, iron/coal 3.44 -> 6.88, workers 1.16; no counter, malus or upgrade weight.
  Its Market leg runs at margin 1.06 (`[production_gate.leg] margin_by_good`): nothing demands steel until some exists, so
  the price sat at base and the 1.0 leg never opened (no steel mill in the 9 full runs since 2026-10-10).
- Every line building counts its standing levels in `raw_modifier local_pp_<good>_line_levels` (modifier types
  `pp_manufacturing_line_modifier_types.txt`). The paper line stays outside the tiers but has the counter for its
  right (2026-11-18). Tiers 2+ have `ai_construct_weight` 200 / (owner income + 10) where the
  predecessor stands (the engine scores a replacement with AI_UPGRADE_BUILDING_UTILITY 0.001).
- Specialization town rights (`town_rights/pp_specialization_town_rights.txt`): per good a charter (3 line levels, output
  +0.15, efficiency -0.05) that upgrades to the rights (unlocked by the Printing Press advance, 8 levels for
  cloth / leather / pottery / glass / jewelry / books / paper, 5 for the other lines; output +0.35, efficiency -0.05; a rights type needs an unlocking advance, else the engine never grants its charter); one
  specialization right per town (`pp_one_specialization_tt`). The AI values only the output line against the town's own
  production, so it takes a right where that line dominates. The 18 vanilla bundled royal rights and charters are
  `REPLACE`d with `potential = { always = no }`. Each rights block stands before its charter: `upgrades_to` reads only
  a right that is already loaded (a forward reference fails at load and the charter never upgrades; fixed 2026-10-15,
  `tests/test_town_rights_order.py`). Both tiers count WHOLE standing line levels (2026-11-11): `allow` compares the
  generated `pp_location_<good>_line_levels` (finalize pass `line_level_counts.py`, `location_building_level` of every
  building carrying the line's `local_pp_<good>_line_levels` counter) with the named thresholds in
  `script_values/pp_specialization_town_rights_values.txt` (tooltip `<right>_line_tt` shows them). The raw_modifier
  counter itself is scaled by input fulfilment (0 without inputs): gated on it, a quarter of the towns with 3+ line
  levels could take neither tier. `tests/test_town_rights_reachable.py` checks every town right: upgrade targets exist
  and have an unlocking advance, unlock keys resolve, conditions name only existing keys and never read a scaled counter.
- Iron right "Hammer Privileges" (`pp_iron_rights`, 2026-10-15, Jan; not tested in game): one right, no charter, no
  potential, no unlocking advance (nothing upgrades into it; an empty unlock list = unlocked from the start). Iron output
  +0.5, production efficiency -0.075. Only where the town works iron itself (`allow`: iron RGO, or a bog iron smelter of
  any tier with a level), because the line acts only on the town's own iron and the AI values it only against that. It
  is one of the specialization rights (in every `pp_one_specialization_tt` list; a test checks the lists name each
  other). Vanilla Bergslag Privileges (mining RGOs incl. iron) stays unchanged: a Bergslag town cannot take the iron
  right, but vanilla Bergslag does not check for it (one way, like every PP right); mining charter and the Bergregal
  rights may stack with it in a city with two slots. Icon: `assets/town_right_drawings/goods/iron.py` (blast
  furnace, pick and hammer; rights frame only, `LINES` in `render.py`).
- Plans are no town rights since 2026-11-21 (Jan; the plan rights `pp_plan_<plan>` of 2026-11-19..20, their file,
  text and icons are gone): a plan is a location marker, and a planned town gets its good's real charter and rights
  from the Construction Plan while the setting is on ("Location Plans" below). EU5 logs every pair of rights that share
  a colour: keep the rights' colours distinct.
- Trade buildings: no institution gates. Rule (Jan, 2026-10-19): a building an advance unlocks never needs an
  institution on top; once researched, it can be built (`tests/test_trade_building_gates.py` checks every loaded
  building type, vanilla and mod, scripted triggers included). The Printing Press / Global Trade gates of 2026-10-06 on
  merchants' quarters, trading hub, customs house, grand marketplace, stock exchange, commerce centre, clearing house
  and entrepot left researched buildings unbuildable for up to an age and are gone (2026-10-18/19). Merchant capacity per
  level: merchants' quarters 1.8 (+20 %), grand marketplace 3 (+50 %), commerce centre 7.2 (+80 %), added to vanilla's
  line; their AI weight is 200 where the predecessor stands + 100 at the market centre, / (owner income + 10).
- Also: `rural_building_cap` development term 0.15 -> 0.25 (mines, quarries, rural works); decentralization
  `global_production_efficiency` -0.05 -> -0.07. Not tested in game.

## Merchant Houses (2026-11-24, Jan)

- The Trade Office, Fondaco and Hanseatic Kontor are merchant houses: few, big, expensive steps instead of many small
  levels (Jan's Venice game: 500 Trade Office levels in 75 foreign towns, 16 towns in the Pest market). `REPLACE:` copies
  of vanilla in their blueprints (`blueprints/accepted/buildings/{trade_office,fondaco,hanseatic_kontor}.yml`, numbers
  in the body, vanilla's value in each comment); port them on game updates (vanilla pins).
- Sites (`allow`, never `location_potential`): `pp_merchant_house_site` (`scripted_triggers/pp_merchant_house_triggers.txt`,
  hand-written) = market centre, megalopolis, or a port with `natural_harbor_suitability` >= 0.75 (vanilla's deep-bay
  step: about 170 ports of the 1337 map outside market centres, 51 of them towns or cities); town rank or more. All three
  need `market = { in_trade_range_of = scope:actor }`; the Fondaco lost the `fondaco_rights` relation and its naval range
  (the AI never asks for the right). A house gives its owner a merchant in that market, which the engine counts as an
  origin of the trade range, so chains grow market by market.
- `need_good_relation = yes` (the engine refuses a foreign building without the flag, error.log 2026-11-24, so every
  step needs the host's opinion of 100; Jan's wish of a first step without good relations is open). Relations and steps in `allow`: no war, no
  rivalry either way; the first step needs the host's opinion of the builder >= 0, every further step >= 100. The
  builder's own levels (`location_building_level = { building_type owner = scope:actor value }`) gate step 2 on
  `trade_range_advance_age_3`, step 3 on `chartered_companies`, step 4 on a merchant republic (Fondaco: Italian).
  `max_levels = 4`.
- The Hansa grows by its own buildings (2026-11-25, Jan; not tested in game): the Kontor has no advance gates. Every
  Kontor step gives its owner 0.1 `pp_hanseatic_kontor_steps` (`foreign_country_modifier`, which the engine scales by
  level and goods access); two steps are always open, the third needs 1 (ten steps kept), the fourth 2 (twenty), in
  `allow`, so a network that shrinks never takes a standing step. The Hanseatic Shipwright Guild gives its owner 0.5
  `pp_merchant_houses` per level (1 until it got up to five levels, see "Hansa Military Buildings") and the Hanseatic
  Town Hall 2 (an INJECT blueprint), added to `pp_merchant_house_cap`. The Hansa's limit at the start is about 11
  houses (reach of a landless trade body about 8, two guild levels 1, the Town Hall 2) and it holds 4. Modifier types and icons: `pp_hansa_modifier_types.txt`, `pp_hansa_modifier_icons.txt`
  (hand-written); texts in `pp_merchant_houses_l_english.yml`. Members add nothing yet.
- Strength per step = 10 vanilla levels of power and 8 of capacity (capacity / power: Trade Office 4.8 / 2, Fondaco
  1.6 / 10, Kontor 2 / 10; capacity was 6 / 2 / 2.5 until 2026-11-25, Jan: the houses gave too much capacity; maritime
  presence x5; upkeep goods x3.5 in renamed unique methods `pp_<building>_...`, x10 until 2026-11-25: dear to build,
  cheap to keep, Jan; at x10 the Hansa's 16 start steps cost 27 gold a month on an income of 15 and it went bankrupt
  in 1358, run 5023bdba; since 2026-11-27 the Kontor alone keeps 2.5 levels of upkeep and 2.3 capacity, about 9 vanilla
  levels, see "Hansa Survival"), `market_center_modifier` +50 % capacity
  and power; employment = created pop 0.25 (the most a burgher building may employ after the cut,
  `tests/test_building_scaling.py`). Host gains in `modifier`: institution growth, max literacy,
  `local_merchant_capacity_modifier`, migration attraction (Fondaco literacy and institutions, Kontor merchant capacity and
  migration, Trade Office a small mix).
- Who builds (later on 2026-11-24, Jan: a nation that is not trade focused must not jump in with gold; in run 5023bdba
  countries with at most 3 locations held 449 of 682 houses in 1837, and nothing was built before 1450), all in the
  `scope:actor` block of `allow` (never `location_potential` or `country_potential`, so no standing house is removed):
  - never a landless bank or trading house (vanilla `country_type = building`, tooltip `pp_merchant_house_builder_tt`) for
    the Trade Office and Fondaco. The Kontor has no such line: its only builder, the Hanseatic merchant federation (HSA),
    is a building country in vanilla (setup `type = building`, the reform requires it).
  - a new house (no level of ours at the site yet): no other house of ours, any of the three types, in a location of
    the same market (`any_owned_foreign_building_location` with `market = root.market` and the scripted trigger
    `pp_merchant_house_of_actor`), and fewer houses than `pp_merchant_house_cap` = 1 + 7 x raw trade reach (see "Trade
    Reach": 1 house without any trade focus, 8 for a full trade nation; count `pp_merchant_houses_held` over
    `every_owned_foreign_building`). Houses above the cap stay; further steps of a standing house stay open.
- Price (later on 2026-11-24, Jan): own keys `pp_<building>_price` 820 (the blueprint) -> 1600 gold
  (`zz_pp_building_price_stockpile.txt`, x1.5 x1.30); `increase_per_level_cost` 2.0 after `[building_scaling]` x0.75 (the
  blueprint holds 2.6667), so steps cost 1600 / 4800 / 8000 / 11200 before the goods factor and efficiencies (first
  version: 3170 / 6340 / 9510 / 12680).
- AI: the engine values them by merchant capacity only; `ai_construct_weight` (root = location, `scope:builder` = builder,
  `scope:owner` = host) = (50 + 50 market centre + 100 no merchant of ours in the market + traded value x 0.1 up to 100 +
  100 merchant republic) / (builder income + 10), the merchant line's scale.
- Game start (`start_simulation.merchant_house_rows`, `[worldbuilder.start.merchant_houses]`, later on 2026-11-24): the
  config lists the whole start (`houses`, "TAG:building:location:step"); every vanilla house row is replaced. A listed
  house off its site (rank and allow as the setup audit reads them, without the World Builder river) fails the build;
  the test checks one house per owner and market (`config/start_markets.txt`), no building country except
  `landless_builders` (HSA), step 1 and step 2 only in a market centre. 33 houses, 39 steps (vanilla 85 rows / 122
  levels, first version 43 / 50): Venice 7 (Constantinople and Alexandria at 2), Genoa 6 (Caffa at 2), Aragon 5, Granada
  2, the Hansa 4 (London, Bruges, Novgorod at 2, Bergen; its member cities lost their vanilla Kontors), Hormuz 3 (Cambay,
  Calicut, Quanzhou), Pisa, Ragusa, the Mamluks (Karimi merchants in Aden), Rasulid Yemen (Calicut), Yuan China
  (Temasek), Kilwa (Sofala) 1 each. Every builder is within its cap estimated from run 5023bdba at 1342 except the
  landless Hansa (cap 1, 4 houses: history). `artifacts/data/worldbuilder/food_simulation/merchant_houses.csv`.
- Historic houses whose sites the rule refuses (left out; Jan decides): Tana (Venice, Genoa: a town in the Sarai market,
  harbour 0.5), Famagusta (rural in the setup, Damascus market, harbour 0.25), Laiazzo/Ayas (rural, harbour 0), Beirut
  (rural, harbour 0.25), Southampton (rural, harbour 0.75, London market), Theologos/Ayasuluk (rural, harbour 0), Chios
  (rural, harbour 0.25), Malaga (a city in the Sevilla market, harbour 0.25), Soldaia (a town in the Caffa market,
  harbour 0.25), Visby (Novgorod's Gotland court and the Hansa: a town in the Stockholm market, harbour 0.25), Pasai (a
  town in the Temasek market, harbour 0). Vanilla rows left out on purpose: Acre (destroyed 1291), Smyrna, Athens and
  Ismail (one per market beside Constantinople), Rome, Antioch, Mahdia, Genoa's Constantinople (Pera is Genoa's own),
  Aragon in Genoa (at war 1331-1336), Granada's other Saharan offices, the Hansa's member-city Kontors.
- `tests/test_merchant_houses.py`. Not tested in game.

## Store Lever

- All stored-food effects ride ONE province modifier per whole stored month, `pp_food_store_0` .. `_24` ("Stored Food:
  N months", `stored_food.py`, `[stored_food]` in constructor.toml; 2026-10-03, replaced the size-scaled Stored Food /
  Low Stores / Full Stores, which did not show their scaled values). Step s = Stored Food (`per_year`, growth and
  prosperity) x s/12 + the store lever: Low Stores (`low`) x the years below 12 months or Full Stores (`full`) x the
  years above (the Grange's Surplus Sales + above / steeply - below) + the store curve (`[stored_food.curve]`,
  2026-10-03, Jan's farm trade-off): Province Food output of every maker at Jan's shares 100 / 80 / 65 / 50 / 40 % of an
  empty store's output at 0 / 6 / 12 / 18 / 24 months (+53.8 % .. 0 .. -38.5 %, was +-75 % linear), and one line per
  staple food (every one since 2026-10-04, see Staple Foods) = its factor x that: -0.40 for the crop farm goods
  (-21.5 % .. +15.4 %; `staple_per_province_food`), own factors for the buy-back goods (fish -0.20, fruit -0.21,
  wild_game -0.14, wool -0.23, camels -0.16; `staple_per_province_food_by_good`, the same food-for-goods balance, recomputed from the
  blueprints by `tests/test_staple_foods.py`): food makers feed a lean province and sell from a full one. Output
  modifiers are per good, so the line is the same for every tier, every RGO and every other producer of that good.
  `pp_stored_food_staple_line` (location scope) is the carried step's crop farm line for the farm weights. Exact values rounded once to five decimals; the pivot step has no lever or curve line, so there are no
  country base values for the store. The refresh picks the nearest whole month (half up) and keeps the carried step
  while the store stays within 0.55 months of it; `pp_stored_food_months` keeps the continuous months for the AI
  weights. The step shows in the location view's province modifier list (no longer hidden).
- Every maker of Province Food stops where its recipe stops paying, so the store rests there: the farms' Provisioning
  always runs (one method, no Sell the Surplus), the Tavern follows the victuals price (Serve Victuals is its only
  slot and its gate). The Tavern must stay on the Province Food good: as flat food it would be a pure price switch.
  The Cookshop line is off the lever since 2026-10-03 (see Cookshop below).
- The Grange packs a full store and follows the victuals price (2026-11-27, Jan's "Grange fix", not tested in game):
  a working Grange breaks even at 38.8 - 8 x victuals price stored months (24 at 1.85, 22.8 at 2.0, 17.2 at 2.7, 14.8
  at 3.0, the pivot at 3.35, then just under it: 11.9 at 3.5, 11.6 at 4.0), about 11 months above the Tavern's fill
  point at every price. Full Stores gives Surplus Sales +0.225 per year, Surplus Sales offset 3.83 (gate opens at 12.3
  months), Haulage offset 2.1; packing alone pays only above victuals 10. Its `ai_construct_weight` vetoes (flat) a
  new Grange below that line + 1 month at today's price (39.8 - 8 x price, never below 13) and where the province does
  not gain food each month (`pp_location_province_food_balance`); `tests/test_store_lever.py` ties the weight's
  numbers to the design. Why: the line before (2026-10-03 evening, 63.53 - 13.85 x price, Full Stores +0.13, Haulage
  2.323) paid only above victuals 2.86; before 1600 only 9-25 % of markets were that dear, fewer than 7 % of people
  lived in a province with a staffed Grange before 1650, and the 14-18 month gap to the Tavern meant stores did not
  follow the price (study 2026-11-27, `f2_design.py` / `f2_sim.py`: staffed Grange levels in 1452 about 80 -> 300,
  the store / victuals price correlation right-signed from the start). Earlier still: 37.88 - 5.29 x price (d3091976),
  which left Mini World run 5's dear-victuals markets at 14-19 months. No Granges at game start
  (`grange_at_start = false`).
- The Victualling Yard takes no store food (2026-10-03): it turns 2.33 gold of market staples into 0.932 victuals and
  nothing else (food-neutral, denser for trade): grain, rice, millet, maize, pease, salt fish and, since 2026-10-04,
  salt beef (1.555 livestock; sheep walked to market and stay inland). Harbour sites (cap minimum 2) and, since the evening, every market centre:
  inland 2 levels with river or sea access (`is_coastal`), 1 without, + 0.025 x development, at most 4
  (`victuals_logistics.json` `inland_market_center`); the start planner places some there too. Low Stores no longer
  cuts victuals; `province_starving` still zeroes victuals output.
- Lumber mills feed crews victuals only in a glut (2026-10-03): Extra Rations 0.2 victuals -> 0.35 lumber and the two
  Provisioned Crews methods break even at victuals 2.4 at default prices (run 5: Extra Rations took 219 of the mills'
  235 victuals in 1522, a quarter of all victuals demand, mostly at a loss).
- Cookshop / Public Kitchen = farm reward (2026-10-03, Jan): `cookshop_max_level` = the province's standing farm,
  orchard, fishery and flock levels / 5 (`pp_location_province_farm_levels`; the counters `local_pp_farm_levels` /
  `local_pp_staple_levels` sit in `raw_modifier`, so staffing does not move the cap and the over-cap cull does not eat
  Cookshops; crop_farms.py renders them there, `start_simulation` reads both blocks) + half a level per standing
  Victualling Yard level in the province (2026-10-04, Jan: raw `local_pp_victualling_yard_levels`,
  `pp_location_province_victualling_yard_levels`; the start planner counts it, and Yard levels its river top-up adds at
  game start are re-checked like farm levels, written first in `pp_start_river_topup`); no base, development,
  population or rank levels. Since 2026-10-10 (Jan) the `allow` is the province capital only, and the cap is one
  budget per province: it subtracts the kitchen levels standing in the province's other locations
  (`pp_location_province_kitchen_levels` minus `pp_location_kitchen_levels`, building levels, not a raw counter, which
  input fulfilment would scale). The engine moves province capitals (highest rank, then most populous; about a quarter
  of provinces in a 500-year run), so kitchens left behind keep working and a new capital builds only what is left; no
  cull. Every owner of a split province has its own capital, store and budget. Small recipes (dish about 0.45 gold of staples + labour at margin
  1.08, drink about 0.23 at 1.2; Public Kitchen 0.55 / 0.28) sell their meals for `offset`, so profit is thin and
  store-independent; the food is the flat `local_monthly_food` (15 / 18 per staffed level, scaled by input
  fulfilment), plus `local_food_preservation_efficiency_modifier` +0.04 (Public Kitchen +0.05) and
  `local_peasants_food_consumption` -0.01.
- Food relief by age (`[age_food]` in constructor.toml, `age_food.py`, 2026-10-03, Jan: age 2 stays tough, age 3
  brings decent relief): per age the farming buildings' flat `local_monthly_food` and a throughput factor on their
  methods (Provision follows the scaled base output; the blueprint records the factor applied as
  `age_food_throughput`, so a new value rescales from it), and the age's food advance carries `global_food_decay`
  (base 0.015 a month; age 3 -0.003, ages 4/5 -0.002). Crop farm tiers take their tier advance's age (rendered by
  `crop_farms.py`); other farming buildings are listed in `[age_food.buildings]` and rewritten by
  `ppc age-food apply` (`check` must report 0 off; `ppc build` prints it; `tests/test_age_food.py`). Scaled tiers get
  throughput allow reasons in their evaluation block. Every farming upgrade has `upgrade_weight` (200 / (income + 10))
  where its predecessor stands: the engine scores a replacement with AI_UPGRADE_BUILDING_UTILITY 0.001, so without it
  the AI barely upgraded (farmsteads 19 % by 1550, run b033350e). Province decay = (local + global food decay) /
  max(1, 1 + summed preservation of the province's locations); the Granary carries preservation 0.03 (was 0.0002,
  a port slip). Order after editing: `ppc age-food apply`, `ppc crop-farms --write`, labour, logistics, gate.
  Well Water (labour -> offset) is the gate method, always available. AI weight: (20 + up to 40 by province farms)
  / (owner income + 10), no store terms. Daily Fare and Farm Produce are gone. The start simulation counts the
  province's placed farm levels for the cap (its caps are memoised on them) and the river top-up / setup audit count
  only the farms the setup files place.
- AI weights of the food buildings (`ai_construct_weight`: crop farm generator, cookshop/public_kitchen/tavern
  blueprints). The AI's own score for a building that adds Province Food to a short province runs from about 25 to
  1e9 (the engine's food term), so income-scaled terms are nudges only. Vetoes are flat (Tavern -10000 from 10 to 12 months, 2026-10-04, was 4 to 6, and -100 per standing level from 8 stored months, fading in from 6; below 6 months none, 2026-10-04) and still lose to the largest scores;
  the store-following gate is the only hard stop. The AI never removes a Tavern, so every famine it answers stays
  built (Mini World runs 3/4: 68 -> 735/815 levels by 1522; the flat Tavern terms of run 4 changed nothing measurable).
  Food urgency (2026-10-04, Jan: low food = under 12 stored months, critical under 8, a sliding scale): every
  Province Food maker (Provisioning slot, Tavern, Cookshop, Public Kitchen; not Grange/Yard) adds the script value
  `pp_food_urgency_weight` (`pp_food_building_values.txt`) = 7.5 x (12 - stored months), min 0, after its income
  divide. The engine's own Food Utility is 0 wherever the province makes more food than it eats, however low the
  store (Constantinople 1454: +16.3/month at 5.4 months, Tavern utility -13.29). Crop farms render it (crop_farms.py),
  upgrade weights too (age_food.py); `tests/test_capital_food_weight.py` checks every maker.
  Tavern (2026-10-04, Jan): allowed in every province capital whatever its rank (`tavern_max_level` 0 only outside
  province capitals); gate = the Common Table slot. Serve Victuals passed 1.05 only near an empty store at real victuals
  prices (save 1757: 4 % at 3 stored months), so hungry capitals never queued one.
- `store_lever.load_design` reads the numbers from the config, the two blueprints and `province_starving`; the
  start-food validator (`worldbuilder/food_sim.py`), `tools/province_store_sim.py` (rest points and ripple on real
  provinces) and `tests/test_store_lever.py` (the properties the design rests on) all use it. After changing a value
  run the simulator and the tests.
- Production efficiency adds to the same pool as these output modifiers, so it moves every rest point (about 1.6
  months per +10 %). Smaller slopes make that worse; keep it in mind before flattening the lever.

## Staple Foods

- One list (2026-10-04, Jan): staple crops (wheat, rice, millet, maize, potato, legumes), staple animals (livestock,
  fish, wild_game, wool; wool stands for sheep, which were eaten; camels since 2026-10-07, Jan: pastoralists lived on
  camel milk and meat) and staple fruits (fruit, olives). The source is the
  `staple_group` column of `config/goods_categories.csv` (`crops` / `animals` / `fruits`, empty otherwise), read by
  `staple_foods.py`; category and subcategory stay as they are (production and RGO expansion cost). Nothing keeps a
  list of its own.
- Readers: the store curve (every staple food), `[logistics] bulky_staples` (one share per staple food; `ppc logistics
  check` reports a missing one), the crop allocation's staple crops (`grains` is gone), the Cookshop cap counters and
  the employment tag `pp_staple_food_priority`, Seasonal Harvests (`[exempt] staple_groups = ["animals"]` in
  variable_harvests.toml: the harvests leave the staple animals alone; the generator runs again without its old input file, the
  reviewed tier overrides name every tier; strength since 2026-10-07: max_abs_output_modifier 0.33, a third of 1.00;
  peasant food consumption unchanged), the Colonial Nation output bonus (every raw good but the staple foods).
- Every building that makes a staple food runs Provisioning (`provisioning.py`): the flocks since 2026-10-04 (Provision
  with Mutton, buying their wool back at 2.5), Camel Herders and Camel Stud since 2026-10-07 (Provision with Camel,
  at 3; store curve factor -0.16, bulk share 0.2; the Cookshop and Public Kitchen serve Camel Stew, camels + a pinch
  of salt; colonial nations lose their camel bonus) and the Maghreb palm groves and the English royal forest at
  reference size (one-level specials without a base slot). `tests/test_staple_foods.py` pins the list, the makers (Provision,
  tag, counters), the curve factors, the bulk shares, the Yard's salt beef and the Cookshop cap's Yard term.
- Every staple food maker's description ends with one sentence, `provisioning.STORE_DESC` (2026-10-28, Jan: a high
  store means more goods for the market, a low one more Province Food): crop_farms.py appends it to the tiers, the
  other makers carry it in their blueprints, `tests/test_staple_foods.py` checks all of them.
- The crop farm tier advances' `crop_farm_output` (was `staple_output`) stays on the crop farm goods: farming advances.

## Logistics

- The logistics buildings (River Boatmen's Yard, Coastal Shipping Office, Transport Office, Carrier Inn and its regional
  variants Caravanserai, Oasis Caravan Station, Yam Station, Banjara Tanda, Llama Caravan Post) produce the pinned dummy
  good `logistics` (1 gold at its floor, like offset) and add `local_market_access` per level (`raw_modifier`).
- Each carries `logistics: { class: <river|coastal|overland|urban>, bulky_scale: x }`; `[logistics]` in constructor.toml
  holds the numbers. `uv run ppc logistics apply` rewrites the tagged blueprints (every method costs `input_cost`, output
  = cost x class output, the last method + `improved_method_bonus`, bulky-goods cut and flavour in `modifier`, the
  market-access and building-level gates in `allow`, `increase_per_level_cost`, laborers, employment 1).
  Class outputs (2026-10-01): river 1.40, coastal 1.35, overland 1.30, urban 1.25 x the input cost.
  Pack animals (EU5 1.4): the Caravanserai and the Oasis Caravan Station run on `camels` (their zones hold 59 of the
  69 vanilla camel RGOs and lie almost wholly in vanilla's camel-demand lands); the Yam Station keeps horses, the
  Banjara Tanda its bullocks (`livestock`), the Carrier Inn horses and livestock.
- Network slot (2026-10-01): the engine scales `raw_modifier` by level x input fulfilment, the average over the
  building's slots, and at 0 market access a building buys no inputs, so the market-access bonus fell to 0 and the
  location never recovered. Every logistics building therefore has a slot 0 with one method
  `pp_<building>_logistics_network` that has no goods inputs at all (no manual_labor) and makes `network_output`
  logistics; a slot without inputs counts as fully supplied, so half the bonus always stands. `ppc logistics apply`
  writes it (body, `production_method_slots`, slot labels and names from `[logistics.network]`, evaluation allow rule);
  the labour pass skips it; the gate stays on the main slot's last method (the network slot is a base slot, so the gate
  rule puts it first; an input-less gate would read a margin of output / 0.001 and never close).
- AI urgency (2026-10-05, Jan): the engine's build score does not see market access, so a heavily built location at low
  access ranked its logistics buildings like any small earner and could stall. `ppc logistics apply` writes
  `pp_logistics_urgency_weight` (`in_game/common/script_values/pp_logistics_urgency.txt`, generated) from `[logistics]`
  `urgency_per_level` x building levels (steps of `urgency_level_step`, at most `urgency_levels_cap`) x the access gap
  below `urgency_max_market_access` (0.85) as a share of it, and makes it every logistics building's flat
  `ai_construct_weight` (no income divide, like the food urgency; 70 levels at 0.20 -> 92, max 120). Since 2026-10-23
  (Jan) the build gate `gate_max_market_access` is 0.99, so a location may build logistics as soon as it drops below full
  access, while the urgency still pushes the AI only below 0.85. One level at a time (same day, `one_level_at_a_time`):
  every logistics building's `max_levels` is `pp_<building>_logistics_max_level` (generated
  `pp_logistics_level_caps.txt`) = levels built + 1 while no other logistics construction runs in the location, clamped
  by `level_caps` (river size, harbour); the engine counts levels under construction against `max_levels`, so the next
  level waits for the last to finish and passes the allow gate again (the AI had started up to 3 levels at once).
  Edits to logistics.py rerun the start
  setup (it is a World Builder input); the weight numbers do too, since constructor.toml is hashed whole.
  `uv run ppc logistics check` must report 0 off, a current urgency value and 0 problems; `ppc build` prints it and `tests/test_logistics.py`
  enforces it. Order after editing recipes: `ppc labour apply`, `ppc logistics apply`, `ppc gate apply`.
- Logistics buildings (custom tag `pp_logistics`) are staffed before every other building in every employment system
  (`pp_employment_priority.txt`, river > coastal > city > rural, above food security and education). Overbuilt
  locations (`unsupported_building_levels`) also get `local_logistics_output_modifier` per level. The vanilla foreign
  buildings (trade office, embassy, ...) carry `raw_modifier free_building_levels = 1`: each level supports itself.
- The overland variants are gated by the geography-only scripted triggers `pp_logistics_zone_*`
  (`in_game/common/scripted_triggers/pp_logistics_zone_triggers.txt`); the Carrier Inn uses
  `NOT = { pp_logistics_zone_any = yes }`. The zones must never overlap (the test evaluates them over every location).
  Never put market access, owner or culture conditions in `location_potential`: the game re-checks it on owner change
  and deletes buildings that fail it.

## Job Room (2026-11-27, Jan)

- Jan: closed and laid-off buildings must not raise the equilibrium ("I want surplus to demote. That's the main reason
  we are doing this"). The engine counts a building's jobs (employment_size x level) in its pop type's equilibrium
  whether anyone works there or not; run b18a10d6, 1837: 1.5 M burghers and 15.9 M laborers unemployed next to unfilled
  jobs in open buildings.
- The rule (`job_room.py`, `[job_room] room_per_head` in constructor.toml; burghers and laborers at 4): **the people
  of a class take its room, their workplaces give it back.** The lines below name burghers; laborers have the same.
  - Pop type (hand-written in `pop_types/pp_pop_adjustments.txt`, checked at every build):
    `pop_percentage_impact = { local_burghers_desired_pop_scaled = -4 }`. That block is applied at the class's share
    of the location's people and the `_scaled` room modifier is multiplied by the location's people, so it is -4 room
    per burgher, always.
  - Building (written at finalize, after the employment cut; marker `# job_room`): per level
    `modifier = { local_burghers_desired_pop = 4 x employment_size }`, scaled by staffing, so a filled job gives the 4
    back. A line of the same key the building's own block already has is folded into ours (`# job_room base <value>`:
    the Trade School's 0.5 of spare room shows as 0.7).
  - With the engine's own count of every job once: **idle burghers allowed = (flat room + unfilled jobs) / 5.** People
    at work are always covered. An unfilled job, in an empty building as in a short-staffed one, counts a fifth of a
    place, and so does every flat source of room (ranks, schools, laws).
- Who carries the building line: every blueprint building that employs a listed class, production building or not
  (324: 167 for burghers, guilds, marketplaces, trade houses, vanilla's council halls and theatres; 157 for
  laborers). A person at work in a building without it would take room and get none back. Four worker-less
  improvements that name laborers (bund, khmer_baray, polders, qanats) have no jobs and no line. A vanilla building the mod only injects into gets the line in
  its INJECT (modifier blocks add up). `not_buildings` takes single buildings out. The size follows the building's
  final `employment_size` at every build.
- Laborers and RGOs (2026-11-27, Jan: "RGO workers can give their stuff back by RGO level"; read in the 1.4.9 code,
  private `headcount_laborers_149.md`; live since 2026-11-28 with the pops setup below, withdrawn for a day in
  between): an RGO is no building and the engine counts no jobs for it.
  Its room is the `rgo_level` static modifier, applied at the RGO's size (1.0 = 1,000 workers) whether anyone works
  there or not. Only laborers work in an RGO (slaves first where the owner allows slave demand), the RGO hires before
  any building and lays nobody off. The line is 7.5 a level (1.5 before): 1 for the workers, 4 they take, and the old
  spare half place x 5. Idle laborers allowed = (flat room + 2.5 x RGO levels + unfilled building jobs) / 5 + unfilled
  RGO jobs. In the saves an unfilled RGO job never stands next to an idle laborer, except where slaves do the work
  (2,239 locations in 1347, 1,041 in 1837): there the RGO's laborer room is spare, as it was before.
- **Flat room x 5.** Every flat source counts a fifth, so the flat room numbers the mod sets for burghers and laborers
  are their old ones x 5 and the same idle people fit as before: location ranks (megalopolis 20, city 2.5, town 1.0;
  vanilla's line plus the inject in `pp_location_rank_adjustments.txt`), schooling buildings (Trade School burghers
  2.5; Library burghers 1.25; University burghers 3), the RGO level above, and
  devastation's cut of the laborers (2.0 and 0.05 scaled). Not raised: vanilla's small lines on buildings (burghers
  0.05, laborers 0.1) and on laws and reforms (`global_burghers_city_desired_pop`). For scale: the RGO's spare half
  place is by far the largest flat room in the game, 11.7 M idle laborers allowed in 1347.
  `tests/test_job_room.py::test_flat_room_of_a_listed_class_is_its_old_number_times_one_plus_k`.
- **Devastation and the upper-class multiplier.** The multiplier (nobles, clergy, burghers) scales flat room, jobs and
  the give-back, not the 4 each burgher takes, so a negative value pushes people at work over the cap: jobs that can
  stay filled = (1 - x) / (1 + 4x). Devastation's value is 0.1 (0.5 before): the same cut at light devastation, 64 %
  of the jobs at full devastation (50 % before; 17 % had it stayed 0.5). Nobles and clergy get the smaller number on
  their flat room and jobs; their own cuts are devastation's scaled lines. No other source of the multiplier is in
  use (vanilla's `province_starving` -0.5 is commented out in PP).
- **Slower demotion (2026-11-27, Jan).** A location demotes 10 people a month plus 1 per 1,000 inhabitants
  (`location_base_values` -0.09 on vanilla's 0.10; `total_population` `local_pop_demotion_speed = 0.001`), vanilla a
  flat 100: median location 18-27 a month, a tenth of them 10, a tenth above 58-173, the largest about 1,000. One
  speed per location and month for every class. Engine: speed = (local + global flat) x max(0, 1 + percentages), x
  1,000 people per class, at most the largest pop; no per-person term exists.
- Why the minus sits on the people: nothing on a building can take room away. Every block of a building is scaled by
  its input fulfilment, which is 0 while nobody works there. The first version of that day (`raw_modifier` -jobs and
  `modifier` +jobs on every producer of a capped class) lost its negative line exactly in the empty building; measured
  in game from each location's summed `local_burghers_desired_pop`: -0.93 per unfilled job in a building with workers,
  -0.02 per job in a building without, and in run defb89f2 85-88 % of unfilled burgher jobs stood in buildings without
  any worker. That pair is gone from every building. Only `always_add_demands = yes` keeps a block alive in an empty
  building, and then it buys its full inputs every month (private `input_fulfilment_149.md`).
- Checked in game the same night (two new games as observer, three years, each location's summed
  `local_burghers_desired_pop` and `local_burghers_desired_pop_scaled` written into location variables by a console
  run file at six dates and compared with the save's people and buildings):
  - the per-person line is -4.000 x the location's burghers (fit 1.0000), the buildings give back 4.00 per burgher at
    work (fit 0.998-0.9999; 3.6-3.9 in the first game, where only production buildings carried the line);
  - burghers world-wide, second game: month 1 2.99 M (2.21 M at work, 0.78 M idle), year 1 2.35 M (1.94 / 0.41),
    year 2 2.14 M (1.91 / 0.23), year 3 1.97 M (1.70 / 0.28). The pair of the first version stood at 2.82 M
    (1.87 / 0.96) at the same date, runs before it at 3.65 M (2.05 / 1.61) in 1347;
  - no script error from it.
- Known costs, from the 1.4.9 code (private `headcount_room_149.md`) and the test:
  - **Swing.** The engine sizes a promotion or demotion for a fixed cap, but every person who moves shifts the room
    by 5, so the class never settles: it swings by about min(4 x promotion, promotion + demotion speed) people a
    month (simulated from the engine's rules, private note). People at work are lost only where that swing is larger
    than the idle allowance, i.e. in a fully staffed location with little flat room. That is the likely reason for
    0.17 M fewer burghers at work than under the pair in the second test game (town flat room 0.2 then, 40 idle
    allowed); flat room x 5 and the slower demotion came after that game and have not been run.
  - **Input shortage.** The give-back is scaled by input fulfilment: a building short of inputs gives less back and
    its workers demote. In the 1837 save 99 % of staffed slots had full inputs.
- Game start. When a new game starts the engine sizes every class to its room in one pass, while no building has
  workers, so nothing is given back yet and burghers are cut to (flat room + jobs) / 5: day 0 has 1.83-1.93 M burghers
  against 3.88 M in a game without any of this, and without help a million at work after three years (first test
  game). `pp_job_room_start` (`job_room.py` writes it; on_game_start with a delay of a day, once, never a pulse,
  nothing on the buildings) does the fill: (1) where the setup gives the class several groups in a location
  (Stockholm's Swedish, Holsatian and Lower Saxon burghers), each is brought back to its setup size from the peasants,
  the largest first (`pp_job_room_group`, one generated line per group, read from the mod's pops setup at every
  build); (2) `pp_job_room_restore` in every owned location fills the jobs of its open buildings that nobody fills
  (`pp_job_room_open_<pop>`, read from the live buildings) from the peasants, into the class's largest pop there (the
  engine's own rule), else the owner's culture and religion for an upper class. With it: 2.21 M burghers at work after
  a month.
- **Game start for laborers: the pops setup holds them (2026-11-28, Jan: "Why can't we handle it like the burghers?
  ... Can't you solve this?"; tested in three new games against the month-1 save of run bd7d9616).** The game's start
  fills a class once, up to its room as the room reads with the setup's people. The setup held 2 M laborers, so with
  the RGO level at 7.5 the start saw room for about 180 M and made 142 M (11-27, withdrawn that evening). Now the
  World Builder stage writes the laborers that work in no building into `06_pops.txt`
  (`job_room.start_laborer_plan`, `start_placement.with_setup_laborers`, called where the start simulation writes
  the pops; the planner's own conversions for its start buildings are replaced, the game promotes the building
  workers itself): per owned location 1.5 x the RGO level + the rank's flat room (megalopolis 4, city 0.5, town 0.2),
  taken from the peasants' own groups, the largest first, at most 98 % of a group. Then the start's room is the old
  one: 7.5 R + J + 5 f - 4 x (1.5 R + f) = 1.5 R + J + f. 28.8 M of the 45 M laborers of a new game sit in the setup.
  - Reference: `config/start_laborers.csv` (`tools/start_laborers.py --save <save a month into a new game without the
    rule>`; today from Jan's `SP_Observer_1337_05_02_bd7d9616...`): per owned location the RGO's size, the laborers
    outside buildings and the slaves. Where a location has slaves (0.5k+) the setup's laborers are capped by the
    laborers it had outside buildings in that game: slaves do the RGO's work first and the start leaves the laborers
    out. Without slaves no cap (322 locations had no idle laborers in the reference and came out 2-10k too high with
    one).
  - **The RGO's own starting size follows the setup**: one level per 10,000 peasants, slaves and tribesmen of the
    setup, 1 to 5 (fitted on two games: where the candidates differ, total minus laborers was right once, this count
    100-114 times; about 1,700 RGOs are smaller than it gives, 20 larger; between games of one setup about 80 RGOs
    differ by a level). Laborers do not count: the first test setup moved peasants into laborers and 1,132 RGOs came
    out a level smaller, each with 4-8k laborers cut. So the setup never takes a location's lower pops below its RGO
    level x 10,000. Where that leaves the setup d laborers short (1,167 locations, the ones just above a 10k step)
    the start promotes 4 d too many: 9 M for one day (54.5 M laborers on day 0).
  - `pp_job_room_trim` (generated row per such location in `pp_job_room_start`, a day in, once): `size` laborers
    back to the peasants, never more than the laborers idle then, never below `keep` laborers outside the buildings
    (where the peasants ran out the start promoted fewer; `pp_job_room_at_work_laborers`). Every laborer pop gives
    the same share and keeps its culture.
  - Laborers get no start fill (`SETUP_SIZED`): the start adds the building workers itself.
  - In game, a month in, against the reference game without the rule: laborers 45.38 M (45.44 M), idle 15.00 M
    (15.11 M), at work in buildings 10.84 M (10.84 M), in RGOs 22.30 M (22.25 M), peasants 234.3 M (234.2 M),
    burghers 3.41 M (3.43 M); 99.4 % of locations within 500 laborers, 13 above by 2k+, 1 below; RGO sizes as in the
    reference (23 of 13,588 one level up); no script error from it. After a year (first test game, the locations with
    the right RGO size): 38.2 M laborers, idle 12.0 M against 11.4 M allowed by the rule (the RGOs' spare half places
    11.1 M of that): the idle laborers settle at the rule's number.
  - Culture: the game puts the laborers its start promotes into the location's largest laborer group whatever the
    peasants' culture (99.4 % of the laborers of mixed locations are of the majority culture in the reference game
    too), so the setup's one-culture groups and the trim add no new distortion.
  - When the start setup changes the RGO sizes (pops per location) or a game update changes the rule: run the tool on
    a new month-1 save with `--levels-only`, then a new game, and compare laborers per location a month in.
- Spare room for new buildings comes from the location ranks and from the schooling buildings, each for the classes
  it teaches, in `modifier`, per level (burghers x 5, see above; in idle burghers allowed: Trade School 0.5, Library
  0.25, University 0.6); clergy and nobles as plain room: Library clergy 0.1, nobles 0.05; University clergy 0.3,
  nobles 0.2 (Jan: "these things should probably cover at least like a building"). Hand-written in
  `building_types/pp_school_buildings.txt` and `pp_culture_building_adjustments.txt`. **Village School: 0.2 idle
  laborers per level since 2026-11-28** (the line is 1, flat room counts a fifth; Jan: "it's fine if it gives some
  laborers"), no soldier room, no laborer room on the University: 0.8 laborers and 0.1 soldiers per level and the
  University's 1.2 parked 11.9 M idle laborers and 1.5 M soldiers by 1837 (run bd7d9616: 14,875 Village School
  levels, built for literacy; laborers beyond building jobs + RGO places 11.5 M against 0.3 M in the run before).
  At 0.2 that is about 3 M. The laborers' main spare room is the RGO's spare half place, which every location has.
- How fast room fills (run defb89f2, people promoting into the class per month where any promote; 1402-1802):
  burghers about 1 a month in a typical town (top tenth 2-4) and 1-2 in a typical city (top tenth 3-11); laborers 7-9
  and 8-11; nobles and clergy 0.6-0.8; soldiers 4-5. Small countries are faster.
- AI: the engine values class room at zero and ignores the `_scaled` line. The burgher schooling buildings'
  `ai_construct_weight` adds `pp_spare_room_weight_burghers` (Trade School, University, half of it on the Library)
  before the income divide (`script_values/pp_school_values.txt`): 100 while the location has an open burgher
  building that is not fully staffed and fewer than 0.25 idle burghers. The laborer term went with the schools'
  laborer room (2026-11-28).
- Not listed: soldiers, clergy, nobles (the engine's plain count). Measured on run defb89f2 (1347 / 1592 / 1837):
  nobles' jobs are 76-109k for 1.4-6.0 M nobles, 5-13k unfilled; clergy's 0.39-3.1 M for 2.6-14.4 M, 83k / 528k /
  1.27 M unfilled; soldiers' 0.9-11.3 M for 1.1-11.8 M, 0.18-1.8 M unfilled. For nobles and clergy the room is flat
  and scaled lines (vanilla: 0.25 % and 0.5 % of a location's people, ranks, laws), which would all need x (1 + k).
- The Construction Plan's booster test ignores a building's room for its own workers' class
  (`construction_plan_country.booster_goods`): it is no effect of the building.
- The burgher rule is tested in game (above). Laborers, flat room x 5, devastation's numbers and the slower demotion
  are read from the code and checked on saves only: no game since.
- `tests/test_job_room.py`; the build prints the counts. No full run yet.

## Building Shutdown (2026-10-05, Jan)

- Buildings without goods output may not be closed unless they are military. `[building_shutdown.classes]` in
  constructor.toml maps every footprint class to `never` or `keep` (keep: barracks, fortification, military_grounds,
  farm_land, technical); a blueprint overrides with a top-level `shutdown: never | keep` (the Kurultai is `never`).
- The finalize step of `ppc build`/`sync` (`building_shutdown.py`, after the footprint) writes `can_close = no` (the
  player) and `ai_forbid_shutdown = yes` (the AI's maintenance-budget and profit closing) into the block that owns each
  `never` building, marked `# building_shutdown`; a building switched to `keep` loses them again. An INJECT never
  repeats a flag vanilla already sets. `uv run ppc shutdown apply|check` (0 problems;
  `tests/test_building_shutdown.py`). 310 buildings locked.
- Buildings WITH a goods output (2026-11-27, Jan; until then skipped, "a losing producer must stay closable"): nobody
  closes a production building. The same step writes `can_close = no` and nothing else into every one (241), whatever
  its class says; an explicit `can_close = yes` of the definition is replaced. `can_close` is the last check of the
  player's button and of the AI's close alike, so both are gone; without `ai_forbid_shutdown` the building stays in the
  AI's close / subsidy pass, so the AI still subsidises it (score above 0) and a negative score does nothing (read in
  the 1.4.9 code, private `notes/close_destroy_149.md`; the run confirms only that `ai_forbid_shutdown` removes both;
  seen in game 2026-11-27: after three years no producer closed, seven subsidised). A producer that loses money lays
  workers off, and their room goes with them for the classes of "Job Room" above. A
  blueprint's `shutdown: keep` leaves a producer closable (none today). Why: a closed building keeps all its jobs in
  its class's equilibrium and applies none of its own lines. The Construction Plan's closer lists no production
  building any more (`plan_closer.never_types`), so its setting "close other businesses for a plan's workers" finds
  nothing to close among them; what replaces it is not decided.
- Why: the AI's maintenance budget (docs/ai_building_rulebook.md, "Maintenance budget") closed and reopened temples,
  libraries, marketplaces and docks 5-13 times a game; universities and grand palaces of small countries stayed closed.
  Their maintenance now always counts, so an over-budget AI closes its military buildings first and builds fewer new
  ones. Estimated extra cost on run 4f95382e: ~3.4 % of world income, worst for small countries holding a university
  or grand palace (open question: cheaper upkeep for those two and the library).
- Library and University AI weight (2026-10-05, Jan): `ai_construct_weight` = 200 (University 150) x
  `pp_promotion_signal` / (owner monthly income + 10). The signal is the open laborer jobs of the location, 0..1, read
  from `modifier:local_pp_surplus_laborer_jobs`, one line in the engine's `surplus_jobs` static modifier (no script
  keeps it), where at least 2k peasants stand idle (`unemployed_pops_of_pop_type_in_location`), else 0. Evaluated only
  when the AI scores the candidate. Run 4f95382e: on in 230-680 locations, 86-91 % without a Library; 87-93 % of
  locations have more laborers than laborer jobs and get nothing (more promotion would only add unemployed laborers).

## Production Method Icons (EU5 1.4)

- EU5 1.4 gives every production method an `icon_type` (`building_type`, `goods`, ...) and an `icon`. The finalize step of
  `ppc build` / `ppc sync` (`method_icons.py`) writes them on every mod method that has none: a renamed vanilla method
  (`pp_<building>_<vanilla method>`, `pp_<vanilla global method>`) keeps vanilla's icon, the Market gate leg shows the
  good it sells, Provision the good it buys back, other unique methods their building, other global methods their good.
  A blueprint may set its own pair (the method keeps it); copies of vanilla files are left alone.

## Interface DDS Format

- Every DDS under `<layer>/gfx/interface/` is in vanilla's format: DXT5 (or DXT1) with a full mip chain, icons at most
  128 px (building icons 128, from the 512 px blueprint PNGs), advance icons at most 256. Write them with
  `eu5_building_pipeline.dds.write_game_dds` / `encode_dds`, never `Image.save(format="DDS")` (raw RGBA, no mips;
  Pillow's own DXT5 alpha is lossy). Pictures (anything below an `illustrations` folder: Europedia banners, situation
  and goods pictures) are BC7 in ONE level at their size, written from their source with `interface_dds.encode_bc7`
  (etcpak): they are stored at twice the shown size, so a mip chain made the game draw a blurred half-size level
  (2026-10-24, Jan: "low res" banners; BC7 one level 40 dB vs DXT5 with mips 31 dB at the shown size). The last
  finalize pass of `ppc build` / `ppc sync` (`interface_dds.py`) converts anything else in place and leaves compliant
  files byte-identical; `tests/test_interface_dds.py` enforces it. Map mode picker icons live only in
  `main_menu/gfx/interface/icons/map_modes`.

## Script Value Overrides (EU5 1.4)

- A scalar `REPLACE:name = 0` in `common/script_values` does nothing: the game reads the key as the scope link
  `replace:name` (error.log: "Feeding data into an event target link that doesn't require data. Link replace") and
  vanilla's value stays. That is why the first 1.4 food-productivity nil left vanilla food percentages in game.
- The block form `REPLACE:name = { ... }` replaces (the building caps in `pp_building_cap_adjustments.txt`; a 1.3 run
  had guilds far above vanilla's cap). It must load after the definition (file names sort; mod and vanilla files share
  one sorted order).
- A plain redefinition is rejected at load ("Duplicated key ... will not be created"): the first definition wins;
  a hot reload re-creates the entries in file order, so there the last one wins. Never rely on either.
- A mod file with the same relative path replaces vanilla's file whatever the rule. The mod's food-productivity nil
  is a same-name copy of `main_menu/common/script_values/default_values.txt`, written byte for byte from the game
  files with every `monthly_food_productivity_*` set to 0 by the finalize step of `ppc build`/`sync`
  (`vanilla_food_productivity.py`). After a game update, rebuild: `tests/test_vanilla_food_productivity.py` fails
  while the copy differs from vanilla apart from those values, and also pins the net food productivity of every
  vanilla object (and of the mod's own objects) to 0 under this rule.

## Blank Effects (2026-11-02, Jan)

- What would show nothing in game never builds, deploys or passes the tests (`blank_effects.py`, fatal in `ppc build` and
  `ppc sync`, `tests/test_blank_effects.py`). It reads the merged objects with the mod's script values: a key's copies add
  up, a net 0 is not a line. There is no exception list. `empty_advances`: an advance with nothing on its card (an unlock
  must reach something too). `dead_modifier_blocks`: in every other database folder, a modifier block where lines are
  written and all of them come to 0; a block left empty on purpose (a REPLACE without lines) is not dead. Buildings:
  `tests/test_building_effects.py`, which reads the script values as well.
- A line the mod zeroes gets a live one in the folder's `pp_empty_effects.txt` (advances: `pp_empty_advance_effects.txt`):
  vanilla's food tier number as output of the goods the object is about, every crop farm good when it is about farming in
  general. An advance that only gates something says so with a `pure_tooltip_entry` (the canals, the four gated crops from
  `crop_farms.py`).
- `in_game/common/gods/hellenism.txt` is a same-path copy of vanilla's file plus `ZEUS_OMEN_LINES`: the omen sits inside
  the god, so an inject or REPLACE of it could register the omen twice. A test fails when vanilla's file changes; copy
  it again.

## Max-Level Tooltips (EU5 1.4)

- The game draws a building's max level as one row per script-value operation: every step after the first `value =`
  inside a described row is a sub-row ("missing key" without a desc, its own change with one). A script value read
  through a scope link (`value = this.<helper>`) is ONE number. Probed in game 2026-10-03.
- `cap_tooltips.py` runs in the finalize step of `ppc build`/`sync`: every described row with steps keeps its label
  and reads `this.<cap>_<desc>`, the helper (the same steps) written right after its cap; caps defined only in
  vanilla get fixed `REPLACE:` copies in `script_values/zz_pp_cap_tooltips_vanilla.txt`. Numbers never change.
  `tests/test_cap_tooltips.py` fails on any max-level row with sub-steps or without a desc (vanilla buildings too).
  A labelled `floor = { ... }` breaks the cap to 0; keep floors inside helpers. The start planner's evaluator
  (`start_rules.py`) reads `this.`/`root.` as the same location.
- Farm max levels speak in levels of that farm (`scripts/generate_rural_capacity_values.py`): "Free Arable Land"
  (floor((flat - townsfolk capacity - reserve) / land)) plus "This farm and the lower tiers it replaces" (their level
  counters `raw_modifier pp_levels_<farm> = 1`, scaled like the land they take, so the cap is exact). A farm shows its
  land once, as Arable Land (`local_population_capacity = -land`); no second land record (2026-10-23, Jan:
  `local_pp_farmland_used` and the old "Farming Capacity from X" counters are gone, a test blocks them).
- Shared land (2026-10-28, Jan, branch `improvement-room-farm-caps`, tested in game): the engine counts a building's own
  levels under construction against its max level, but not another farm's, so two farms could start levels on the same
  free land (Sanlorenzo 1554: Cattle Farm 21/25 and Horse Breeders 13/17 on land for 4 levels). Every farm max has the
  row "Farm Land Usage of other farms under construction": the land of the farm levels under construction in the location outside the
  farm's own upgrade line (`pp_farm_land_queued_outside_<line>`, `building_levels_under_construction` stepped to 5 per
  building, land classes as scripted triggers `pp_farm_land_class_<land>`), only where land is free (a construction
  never lowers a cap below the standing levels). The townsfolk capacity reads `pp_subsistence_land` at its applied
  size (marker `pp_subsistence_land_size`): the modifier refreshes once a year, so today's subsistence count took a
  hiring farm's peasants' land twice until the refresh. The location view's bars read the same land. Cost (script
  profiler, Jan's 1554 observer save, 27 game months at speed): the new farm cap parts ~1.1 s of 89 s script time
  (~1.2 %); the bars with possible improvements ~2.8 ms script time per frame while a location view is open (were ~8 ms
  before one candidate per upgrade line, `arable_land_bar.candidate_groups`).
- `script_eval.py` evaluates the generated location script values offline (farm caps, improvement caps, the bars);
  `tests/test_land_script_values.py` checks them by what they compute, anchored on numbers read in game.

## Deleted Vanilla Objects and Start Exceptions (2026-10-23, Jan)

- The mod deletes vanilla objects it has no use for instead of keeping inert stubs: `[worldbuilder.compat]
  removed_objects` leaves them out of the file's generated copy (written even without a widened test, else the vanilla
  definition comes back), `[[worldbuilder.compat.replacements]]` rewrites vanilla references to them (exact text, fails
  when vanilla changes). `farming_village` is deleted this way (its English event option and the town graphics now
  follow the crop farms); `compat.removed_vanilla_buildings` gives the deleted buildings to the footprint check and the production coverage.
- No start exceptions: no building rule names start locations or start flags. The start setup removes every vanilla
  setup row that fails its building's rank, `location_potential` or `allow` (`start_simulation.drop_invalid`; the setup
  audit checks the same), so the game start holds only what could be built there. `tests/test_setup_building_keepers.py`.
- By the book (2026-10-24, Jan): no building starts above its cap, the 1337 improvement works included (the World
  Builder clamps its starting levels, `clamp_start_to_cap`; the constructor clamps every building; the old above-cap
  exception also made the planner skip every placement in ~1,500 locations). Vanilla's `<rank> = setup_only` counts only
  for setup- and event-only buildings (`allow = { always = no }`): cathedrals and city walls below their rank go. The
  start check reads every rule (`start_rules`: cultures, capitals, integration, province, pops, borders, market goods =
  the mod map's RGOs in the start save's markets `config/start_markets.txt` plus base_production goods); conditions on
  the building country (`BUILDER_TRIGGERS`, scope:actor) hold for the setup's owner. A rule it cannot read fails the
  build. No game-start culls: the random estate cull, its vanilla location lists and the invalid-building culls are
  deleted. `tests/test_building_effects.py`: every building the game loads has an effect.

## DLC Content (2026-10-28)

- The game mounts every `game/dlc/<folder>/` like `game/` (after it, before mods). The parser's vanilla layer reads them
  the same way (eu5-game-parser `dlc_roots`: one file list sorted by name, a DLC file replacing vanilla's same-name
  file); `building_footprint.vanilla_files` does it for the footprint, shutdown, ship upkeep and blockade passes (Across
  the Pillars adds 5 ships). Other direct readers of `game/in_game` (cap tooltips, the start simulation's setup rows)
  still see the base game only.
- Buildings only a DLC folder defines (Across the Pillars: 9) have footprint blueprints like every vanilla building, in
  a skip-if-missing mode only (`TRY_INJECT`/`TRY_REPLACE`, never CREATE or plain INJECT/REPLACE), and no DLC-only key
  may appear outside their own block. `ppc footprint check` fails otherwise; `tests/test_dlc_buildings.py`,
  `test_inject_targets_exist_in_constructor_load_order` and `tests/test_building_type_references.py` guard it.

## Stockpile Prices (branch stockpile-prices, 2026-10-31, Jan)

- Exploration branch, never merged unasked. Prices follow the market stockpile: `NMarket.STOCKPILE_TRADE_IMPACT_ON_SUPPLY_SCALE`
  6.7 with the stock bleed from the first unit (`MARKET_MIN_STOCKPILE_TO_ALLOW_EXTRA_TRADE` 0,
  `MARKET_STOCKPILE_FULL_EXTRA_TRADE_THRESHOLD` 0.01), every default price x1.55 (x1.6 until 2026-11-02) except the floor-pinned
  dummy goods (`in_game/common/goods/zz_pp_goods_stockpile_prices.txt`, written by `ppc stockpile apply` from `[stockpile_prices]`;
  `check` must report it in step, a test enforces it), stockpile cap x10 (development 100, market centre 250). A market
  with supply = demand sits at the default price when empty and at the old price at 2.9 months of stock. Price / default
  depends only on supply, demand and stock, never on the raise: the raise moves the price level and nominal incomes.
- `production_labour.load_prices` divides the raise back out, so every pass that turns gold into goods amounts (labour,
  gate legs, logistics, Old Ways, crop farms, ship upkeep) keeps its amounts; `profit_margins.goods_prices` reads what the
  engine reads. After changing the raise: `ppc stockpile apply`, `ppc crop-farms --write`, labour, legacy, logistics, gate.
  The Market legs run at margin 1.06 (steel 1.12): they open at 0.64x the default price / the good's factor, about 2.9 months
  of stock (5.0 with +20 % output), and that gate is where stocks settle, whatever the demand. Iron and lumber lost
  `ai_rgo_expansion_priority` (0 here, 0.025 on 0.10).
- Price brake (2026-11-03, Jan, not tested in game): `NMarket.DEMAND_ELASTICITY_COEFFICIENT` 1.0 (vanilla 0.40). The exe fixes its start at
  1x default; a good below default has stock or surplus, so the brake acts only in real shortage (it reduces strain on goods already too
  much in demand). Static estimate from run ebdb631e: 2-4 % of pop demand value, three quarters of it tea, fur, cocoa and amber (at 1652
  amber -26 %, cocoa -24 %, coffee -22 %, tea -7 %, wheat -2 %). Watch: less unmet demand also means a weaker missing-goods term in the AI's
  building utility. `demand_multiply` is a load-time number, it cannot follow price. Tea's and coffee's `demanded_Temporary` is vanilla event
  demand (`prices.7`, `coffee_boom_happened`), which the brake never touches.
- RGO output (2026-11-03, Jan, not tested in game): country base value `global_raw_material_output` -0.65 (was -0.5). Additive: serfdom nets +0.1 (vanilla +0.2, ours
  -0.1) and traditional economy 0, so the real multiplier at the start goes about 0.55 -> 0.40, RGOs -27 %. A change of it also moves the colonial nation's own value (now +0.7,
  3x a normal RGO) and the start planner's `rgo_output_per_location` for lumber (now 0.42); `raw_goods_per_rgo_k` stays. Run 16fe282a: RGOs 62 % of raw goods output at 1342, 14 % at 1837;
  used / made 0.53 at 1342, about 1 from 1500. Watch: prices near the floor rise faster than output falls, so RGO income and Location Wealth rise, and raw producers' gates open earlier.
- Burgher trade capacity (2026-11-03, Jan, not tested in game): `local_trades_per_burgher` per level Marketplace 0.7 (was 1), Merchants' Quarters 0.8 (1.5), Grand Marketplace 0.9 (2), Commerce Center 1 (4): each upgrade adds 0.1, an upgrade never loses capacity (Jan);
  `global_trades_per_burgher` in `societal_values/pp_societal_value_adjustments.txt`: plutocracy +1 / aristocracy -0.4, capital economy +1 / traditional -0.3, free subjects +0.5 / serfdom -0.1. Keep the three
  cuts summing below the base of 1 (-0.5, -0.5, -0.25 left 1.4-1.7 % of burghers with no capacity). Run 16fe282a used 13-36 % of the old capacity, trade buildings 58-86 % of it. Replay of its saves: capacity per
  1,000 burghers 13.8 -> 7.6 in 1837, 2.9 -> 1.9 in 1347; used 23-57 %; units -0.4 to -3.1 %; republic / monarchy capacity 0.55 -> 0.70 in 1837, 1.37 -> 2.00 in 1347. Tightest: the median market is full in 1407 (57 %
  used before), unmet need 1.53 -> 1.88 % of demand. Capacity does not limit burgher trade, so republic-majority markets' share of units barely moves. `docs/market_rulebook.md` 8d.
- Demand (2026-11-01, Jan; from run 67859be2, where demand / production sat at 1.1-1.15 from 1550 on, not tested in game):
  `[stockpile_prices.pop_demand]` is a `demand_multiply` on every pop type per good (the engine's price brake has no setting
  per good or pop type and only acts above the default price); `NPop.DEVELOPMENT_SCALE_ON_DEMAND` 0.04;
  `NEconomy.INFLATION_MINTING_GOLD_DEMANDS_FACTOR` 0.45 (minted metal follows income); `[production_labour] extra_share`
  0.09 on every share class except `extra_share_skip` and food buildings (a method producing a staple food or a good in
  `extra_share_spare_goods`, or `extra_share_spare_buildings`): the cost stays, the goods scale down about 10 %.
- `[stockpile_prices.price_factor]` (0.85-1.15 per good, from run 06aedac2's relative prices, five moved one step on 2026-11-02
  from run ebdb631e; staple foods never cut) multiplies the raise; the passes and the crop farm weight divide it back out too (`stockpile_price_raise`), so only
  the engine's market price moves. Crop farm `ai_construct_weight` multiplies price / default by the raise (a weight
  that read the raised default made farms look half as profitable in run 06aedac2).
- Building prices x1.5 in gold (`in_game/common/prices/zz_pp_building_price_stockpile.txt`, written by hand, old value in
  each comment): the 12 age prices every building without its own price uses, the estate, HRE army, aqueduct and
  hippodrome prices and the mod's 55 own building prices. Why: with prices x2 nominal incomes rose (x1.3 at the start, x2
  by 1542) while gold prices stayed, and the AI built faster than population grew (run 06aedac2). A new blueprint price
  needs a line there too. Since 2026-11-06 (Jan) the file's gold = old value x 1.5 x 1.30, rounded to 5: every location
  rank had `local_build_buildings_efficiency` -0.3 (a flat cost raise the cost tooltip showed as the rank; the engine divides
  a level's price by max(0.5, 1 + summed efficiency)). The ranks carry none now (sheet `free_building_levels_sheet.csv`,
  rank rows); the prices carry it. 1.30 = gold spent in run 77768726 at the old vs the new rule (per 50 years 1.32 early,
  1.29 late). Bonuses (rivers, ports, ruler, advances) are worth their vanilla weight again, penalties are milder, and the
  0.5 floor no longer binds on mountains. Religious-influence prices (monasteries, preachers, merchant guild chapel) untouched.
  `tests/test_tier_lines.py` ties this file to `[tier_lines] price_factor`.
- Building cost tooltip (2026-11-06, Jan): one shared vanilla template (`price_tooltip`, economy_tooltips.gui) shows the
  engine text `PriceTooltipWrap.GetTooltip` for every price. Only `BUILDING_LEVEL_COST_MOD` (in
  `replace/english/pp_vanilla_overrides_l_english.yml`) is building-only: red when it raises the cost, with the bucket rows
  "Level, multiplies the cost" above and "Construction Efficiency, divides the cost" below. The engine writes it only when
  the level term is not 0 (a first level shows the efficiency rows under the plain header); an upgrade row comes after it.
  `SCALE_IMPACT_ON_PRICE`, `PRICE_FURTHER_MODIFIED` and `MARKET_PRICE_IMPACT_HEADER` stay vanilla: war costs pass their own
  scale text (`tests/test_building_cost_tooltip.py`).
- Tier lines (`tier_lines.py`, `[tier_lines]`, finalize pass, `ppc tier-lines` lists them; 2026-11-01, Jan, from run 6ee05b7e):
  upgrade lines whose lowest tier needs a raw material, + the extras. A researched successor freezes the old tier, and upper
  tiers cost 4-24x the base for 1.0-1.5x its profit. Each tier's price = profit per level at base prices x 180 months, lowest
  tier 75-100 gold, higher tier 1.5-2x the tier below, then x `price_factor` 1.30 rounded to 5 (the rank efficiency, see
  above; `pp_<tag>_price` in `prices/pp_tier_line_prices.txt`, final gold, NOT in the x1.5 file); own-good level bonus x0.75; tiers on `rural_building_cap` go deeper (second x1.25, third x1.5,
  `script_values/pp_tier_line_caps.txt`); every tier also names all older tiers as `obsolete`, so a site two tiers behind
  can upgrade (blueprints keep the direct predecessor only, the pass adds the rest). `increase_per_level_cost` stays. A new
  line in scope needs no config; a test pins the list of lines. `[tier_lines.price_overrides]` prices four crafts.
- Silver (2026-11-02, Jan; not tested in game): `saiger_process_discovery` had the same research hole as the adit's advance, so it
  also requires `pike_and_shot_advance`, with weight +200 for silver producers.
- Copper and amber (2026-11-02, Jan; not tested in game): the AI skipped `new_currency_demands` (the adit's unlock; owners of 27 % of
  copper sites in 1642, 40 % in 1807), so it now requires `pike_and_shot_advance` with weight +200 for copper and tin producers;
  a third tier, Deep Copper Works (`copper_mine_deep`, advance `pp_reverberatory_copper`, age 5). The copper price factor stays 0.9:
  1.0 opens only 2-13 more sites past workers and gold. Amber Diggings (`amber_diggings`, advance `pp_amber_diggings`, age 4 under
  `global_trade_advance`): about twice the amber per level. An advance's `requires` must be in its own age, and a building unlocked
  after age 1 needs an institution-gated ancestor (`tests/test_focus_restricted_unlocks.py`).
- Merchant line salt (2026-11-02, Jan): `marketplace`, `merchants_quarters`, `grand_marketplace` and `commerce_center` are REPLACE copies
  of vanilla because their upkeep sits inside the building (the line took 26-32 % of world salt, whatever the price); salt 0.05 / 0.06 /
  0.08 / 0.08, was 0.06 / 0.075 / 0.1 / 0.1. Port them on game updates.
- Elephants (2026-11-02, Jan: find uses; run ebdb631e: about 230 a month made, 25 wanted, all at the floor; not tested in game): the
  nobles' demand opens at wealth 1 at half vanilla's rate, only in markets that breed them (`pp_goods_adjustments.txt`); the three
  lumber mill tiers have a two-method slot "Forest Elephants" whose method loses money at default prices and pays with elephants
  near the floor and lumber from about 1.4 (`location_allow`: the market breeds elephants; safe in a two-method slot).
- Not changed: marketplace building caps (vanilla 20-100), tariffs. Engine costs that scale by market / default price
  (unit upkeep and the like) run about 35-50 % lower at normal stocks. Simulation: `~/pp_ai_run/tradesim` (private).

## Upgrades Never Worse (2026-11-06, Jan)

- Rule: a building that names another as `obsolete` never earns or makes less per level than the producing building it
  replaces (once researched, the old one cannot be built). `tests/test_upgrade_not_worse.py` reads the compiled mod, at base
  prices (`production_gate.load_prices`), in every age from the upgrade's unlock with the methods each knows by then: profit
  per level with each slot's most profitable method, and output value with each slot's most valuable method. No exceptions.
- Why: the Clay Washmill made 1.07 clay per level against the Clay Pit's 1.48 and earned a third of its profit since the June
  move to one worker per level (its outputs were divided by 4, the pit's were not). Nothing checked it.
- Fixed the same day (blueprint comment `upgrade not worse 2026-11-06`): one output factor on the upgrade's own methods, inputs
  kept, the smallest step of 0.05 at which it earns at least 1.25x what it replaces at its unlock and never less later (the
  mod's 131 upgrade pairs: lower quartile 1.27x, median 1.9x). Clay Washmill x1.4, Salt Mine (improved) x1.25, Sand Washery,
  Fiber Dressing Yard, Coke Blast Furnace, Planned Saw Works, Pomological Orchard x1.1, Blast Furnace and Gun Smith x1.05,
  Offshore Fishery x1.3. Food buildings and the saw works keep their slot-0 base method (Provision follows it; the saw
  works' base is a requested low baseline). Planned Saw Works also got the Water Sawmill's Extra Rations (an upgrade never
  takes a recipe away). Evaluation bands crossed by the fix carry an allow rule naming it; the offshore output band is x1.3.
- Not changed: tier-line prices (every fixed tier still takes the 1.5x step), employment, the predecessors.

## Start Market Stock (2026-11-04, Jan)

- A new game slid for about a decade because market stocks fill from 2 to 45+ months of supply and the target price falls with them. No script can set a price or a default price, so `start_market_stock.py` (finalize pass of `ppc build` / `ppc sync`) writes `in_game/common/on_action/pp_start_market_stock.txt`: one `add_goods_supply` per market and good, once, 5 days into a new game (`DELAY_DAYS`: on day 0 location modifiers and the stock ceilings they set may not be in place; prices first step on 1 May, so nothing is lost). The price then only has to step down to its target at `MONTHLY_PRICE_CHANGE`.
- Per market and good, with flow = max(use, make): `min(months(x) x flow, 0.85 x ceiling) - existing_months x flow`, the ceiling being the market's stock ceiling (275 + 100 x the centre's development), because at 90 % of it the AI stops building producers of the good there; with `months(x) = ((1 - 0.2 x) / (x - 0.2) - 1) / 0.335` (the price law solved at supply = demand for the settled price x). use and make come out of game from what the build places: pops x the goods files, setup levels x inputs and outputs (each slot averaged), RGO workers by rank, World Builder land rows, `config/start_markets.csv`.
- `start_market_stock.csv`: per good the settled price and one engine factor each for pop demand, building inputs, RGO and building outputs (the engine's wealth rules and method choice are not modelled). Demand, recipes, levels and pops move the result at every build without a save. Only a moved settled price or a new good at game start needs `uv run ppc start-stock calibrate --save <day-0 save>` (settled prices from the newest five full runs in `graphs/dataset`). `ppc start-stock check [--save <day-0 save>]` says whether the file is current and how far the targets sit from the settled prices.
- Only goods a market has (2026-11-08, Jan: chili in Paris, elephants in Venice, lacquerware in Mexico had start stock, so the goods came into those markets): a vanilla good gets stock only where the market produces it at game start (vanilla's `is_produced_in_market`); PP's own goods (victuals) go anywhere. `start_market_goods.csv` (repo root) lists per market the goods it produces in a new game, union of a day-0 save and one a month in (locations change market on the first monthly tick); a save decides because the model's own production misses about a tenth both ways. Rerun `uv run ppc start-stock presence --save <day 0> --save <month 1>` when the start setup changes which goods a market makes; the test fails on a planned market without a row. 4,077 rows, 3.45 M gold (was 6,550, 3.81 M); 2,473 rows dropped.
- Checked on a day-0 save of the same build: target against settled price, typical miss 31 %, mean +9 % (no added stock 151 %, +132 %; true flows of the save 22 %). Factors from a save of 2026-09-20 still give 31 %, so the table does not go stale with balance edits. Details: `docs/market_rulebook.md` 8e.
- Victuals (2026-11-27, Jan): the common good cut 0.003 -> 0.001 per 1,000 idle peasants (`pp_goods_victuals.txt`; it was 67 % of world victuals in 1342, 99 % in India, 86 % in China, and kept 24+ months of stock at a third of the default price until about 1450). Settled price 0.396 -> 0.54 (the simulator's victuals price at 1362 against the old value) and the output factor 4.337 -> 2.397 (x 0.553: the common good was two thirds of the day-0 make the factor carries), both by hand until a day-0 save of the new build calibrates them; injection 18,336 -> 5,092 victuals. The start planner and the start validator count the common good in each market's victuals supply (`start_simulation.victuals_v2`, `food_sim`), and `NLocation.SUBSISTENCE_AGRICULTURE` 1.20 -> 1.21 covers part of the Tavern food the cut takes. Simulated (scratch sim on run b18a10d6): world stock 21.6 -> 14.2 months in 1343, about 10 from 1347 on; victuals price +46 % from 1352 to 1830 (was +86 %); world people in 1836 -5 %, India -4 %, China -2 to -5 %. Not tested in game.
- In game, first version (no ceiling cap, median settled prices), 13 months against the same build without: no errors; stock 27 -> 39 months of supply at once (without 2 -> 6); world price / default 0.67 at month 6, 0.52 at 10, 0.46 at 13 (without 0.87, 0.74); monthly moves 8.9 % falling to 3.8 % (without 4.9 to 3.8); unmet pop demand 7.1 vs 9.5 % at month 10; tax paid -27 %, wanted (Jan: people were making money on inflated prices); food, people and constructions unchanged. Not measured past 13 months: the AI's first-decade building.

## Ship Upkeep (2026-10-11, Jan)

- A ship's monthly upkeep is the value of its maintenance goods at default market prices. Vanilla charges the category
  price (prices/02_units.txt: heavy 1, light, galley and transport 0.5) doubled every age of the ship type
  (`NUnit.BASE_SCALE_SHIP_DOUBLE_PER_AGE`, an integer multiplier: 0 makes ships free, no other growth rate exists), so an
  age-6 three-decker cost 32 for goods worth ~11.5 and an age-1 ship less than its goods; the goods only moved it by
  their market price deviation.
- `uv run ppc ship-upkeep apply` writes `in_game/common/prices/pp_ship_upkeep.txt`: one `<unit_type>_maintenance` add
  per navy unit type (vanilla unit-specific prices add to the category price before the age doubling), so that
  (category gold + add) x 2^(age index) = the basket value; units vanilla already prices get `TRY_REPLACE:` with their
  sailors kept. The define stays 1. For the new prices it also writes their `<price>_cost_modifier` types, icons (the
  category's vanilla maintenance icon) and names (`pp_ship_upkeep_modifier_types.txt`, `..._modifier_icons.txt`,
  `pp_ship_upkeep_l_english.yml`; the game logs "Missing modifier type for price" without them). `ppc ship-upkeep
  check` must report the files current (`tests/test_ship_upkeep.py`); rerun apply after a game update or a goods price
  change.
- The goods market percentage and maintenance efficiency still apply on top. The AI spends a fixed share of income on
  its navy, so cheaper late ships mean larger AI navies. Not tested in game.

## Starting Technology Ladder (2026-11-25, Jan)

- What: every country of the 1337 setup starts in a group 1..9 and gets the general first-age advances whose level is
  at most its group; group 9 = what a vanilla level-3 country held. Design: `config/starting_technology.toml` (levels,
  `[requires]`, `[research_cost]`, `[ai_weight]`, `[specific_remap]`, `[floors]`, `[caps]`: societies of pops are written at level 1 and hold nothing, as in vanilla). Groups:
  `config/starting_technology_countries.csv` (`tag,group,confidence,basis,note`, one row per country block of
  `10_countries.txt`; a placeholder from the vanilla level until the researched table arrives,
  `tools/start_technology_placeholder.py`). Plain-language rules and the ladder table: `docs/starting_technology.md`.
- Code: `start_technology.py`; `uv run ppc start-tech apply|check [--verbose]`; finalize step of `ppc build` / `ppc
  sync` (after every step that writes advances). Outputs: `in_game/common/advances/zz_pp_start_technology.txt`
  (INJECT of the level; REPLACE with the effective block where the ladder changes requires, research cost or AI
  weight, and where another mod file already replaced the advance: the engine ignores an inject into a replaced block),
  `main_menu/setup/1337/28_pp_start_technology.txt` (partial country blocks, no BOM), `config/starting_technology_buildings.csv`
  (building -> ladder advance -> level) and the reports in `artifacts/data/start_technology/` (countries, removed start
  buildings, setup requirements, `withheld_specific_advances.csv`: tag-gated first-age advances a country on the map
  held with vanilla levels and loses under the ladder, with the blocking ancestor and what it unlocks; culture,
  religion and government gates are not evaluated). `[requires]` (only that section) may also name a specific
  first-age advance: REPLACE with the new parents, no level unless it had one (then remapped); Mali's
  `kouroukan_fouga_advance` under Subject Nations keeps its start reform (load log 2026-11-25).
- Start buildings: the World Builder start stage (`start_simulation.drop_locked`, and `add` for the placement) drops
  and never places a building whose unlocking ladder advance is above the owner's group; it reads the building table,
  not the advance files, so advance edits do not rerun the start setup (`ppc build` / `ppc sync` refresh the table
  before the stage; a table the finalize step changes is applied on the next build). Raising a group and rebuilding
  brings the buildings back (the CSV is in `config`, a World Builder input).
- Engine facts (in game 2026-11-25): an Age of Traditions advance is granted at start when its level <= the country's
  level (none = 0), `allow` / `potential` pass and one parent is granted; a withheld advance withholds its subtree;
  levels are a plain integer compare (5, 6, 8, 9 tested). `INJECT:<advance> = { starting_technology_level = N }` raises
  a vanilla level (2 -> 9 tested; a lower value is untested); `REPLACE:` works. In a country block the LAST level in
  reading order wins (includes expanded in place); a later setup file's partial `countries = { countries = { TAG = {
  starting_technology_level = N } } }` merges and wins. Setup files are UTF-8 without BOM, advance files with BOM. A
  start subject relation is invalid when the overlord lacks Subject Nations (vassal checked; other subject types, laws,
  reforms, privileges and parliament types untested; `setup_requirements.csv` lists what the start countries use).
  First-age cost once that age is past = 17 x (1 + `research_cost`); `ai_weight = { add = N }` adds to the AI score.
- Change a country's group: edit its CSV row and rebuild. The pass fails, naming the tags, on a setup country without a
  row, a row without a setup country, a duplicate or a group outside 1..9.
- After a game update: `uv run ppc start-tech check` and `tests/test_start_technology.py` (new or renamed countries need
  rows, a new general first-age advance needs a level, a changed replaced advance is carried by `apply`), then `uv run
  ppc vanilla-pins record` for the pass's REPLACE blocks.

- Research speed on the writing branch (2026-11-25, Jan: "we disperse this research speed on them ... the AI
  researches these first and our other nations have a head start"; a new game loads clean and the numbers show in
  game, no full run): vanilla's flat 1 research a month becomes base 0.4 plus Written Alphabet 0.2, Scriptorium 0.1,
  Chancery 0.1, Library 0.1, Paper Guild 0.1 (`[research_speed]`, base and shares must add up to 1: groups 8 and 9
  research as before, nobody gains; start research 0.4 for groups 1-5, 0.7 group 6, 0.8 group 7). The pass writes the
  shares as `research_speed` lines into the advances' REPLACE blocks and the base into
  `in_game/common/auto_modifiers/pp_research_base.txt` (a REPLACE of every vanilla auto modifier with
  `research_speed = 1`, copied from vanilla on every build; pops keep 0.1; pinned in `tests/vanilla_replace_pins.csv`).
  The AI puts no value on flat research, so the five advances carry the ladder's highest AI weights (300-200,
  Codified Laws 150 because the Chancery hangs under it; a test keeps them above every gate). The four big gates went
  from research cost 5.0 to 3.0 the same day (Jan: the worst nations should need about 100 years, not 150). Simulated
  catch-up to every institution-free first-age advance, researching nothing else: group 2 99 years, 3 80, 4 72, 5 66,
  6 37, 7 24, 8 10 (`pp_workspace/techstart/speed/`). A bonus per advance researched (`num_of_advances_researched`
  works in an auto modifier's `scales_with`) was considered and left out: a growing global buff that widens gaps.

## Schools (literacy rework, 2026-11-25, Jan)

- Literacy is earned in the location; the country-wide sources are cut by `literacy_sources.py` (`ppc literacy`).
  Hand-written like the Library (disabled footprint blueprints `pp_village_school.yml`, `pp_trade_school.yml`):
  `building_types/pp_school_buildings.txt`, levels and AI weights `script_values/pp_school_values.txt`, triggers
  `scripted_triggers/pp_school_triggers.txt`, upkeep `production_methods/pp_culture_maintenance_adjustments.txt` (the one
  place for the provisional amounts), advances `advances/pp_school_advances.txt`, texts `pp_schools_l_english.yml`.
- Village School (clergy, every rank): peasant, laborer and soldier literacy caps, monthly literacy, the promotion speed
  the Library had. Levels: 1 (Village Schools, Renaissance tree) + Printing Press + Common Schooling (Confessionalism
  tree, country modifier `pp_village_school_levels`) + an Education of the Masses policy that teaches the common people
  (`pp_educates_the_masses`). Trade School (burghers, towns and up): burgher cap, monthly literacy, the Library's burgher
  room. Levels: 1 (Reckoning Schools, Banking tree) + a specialization town right (`pp_has_specialization_town_rights`,
  every PP charter and rights by name; `tests/test_schools.py` keeps the list whole). Both open to estates (clergy,
  burghers pay for their own pop type's buildings); AI weights 30 + 2 per 1,000 people / + 10 per 1,000 burghers, max
  150, / (owner income + 10). Library: upper-class caps only, no promotion or room; its weight follows nobles, burghers
  and clergy (`pp_library_ai_weight`).
- Clergy, laborers and peasants are full `REPLACE:` copies in `pop_types/pp_pop_adjustments.txt` (pinned): whether an
  injected `literacy_impact` replaces vanilla's block or adds to it is not established, and the laborers' vanilla
  production efficiency line could only go in a replace. Clergy literacy teaches (`local_monthly_literacy`), peasant
  literacy brings peasant estate power. Not tested in game; icons are vanilla placeholders.

### Education pyramid and institution spread on estate literacy (2026-11-27, Jan; not tested in game)

- Pyramid: the Trade School needs a Village School in the town (`allow`). The Library has levels by rank
  (`pp_library_max_level`: 1, town 2, city and megalopolis 3); a University needs two Library levels in its location
  (`pp_library_levels >= 2` in `allow`, read only when it is built). The **Academy of Sciences**
  (`pp_academy_of_sciences`, `building_types/pp_school_buildings.txt`) stands in the capital: one level per three
  Universities of the country, at most ten (`pp_academy_university_levels`, a walk over the owner's locations that runs
  for the capital only), research speed per staffed level through `capital_country_modifier` and, since 2026-11-28
  (Jan: a small country-wide bonus, never the country's main source), half a point of maximum literacy for every
  class per staffed level (`global_<class>_max_literacy = 0.5` for the six classes; five points at ten levels; run
  bd7d9616: nine countries built it from 1692, six levels at most, 18 in 1837), gone when the capital
  moves (`remove_if`), unlocked by `pp_academy_of_sciences_advance` (Scientific Revolution tree). It uses
  `location_potential = { counts_as_capital = yes }` like vanilla's Chancery (a capital building should go with the
  capital). The University's AI weight (`pp_university_ai_weight`) gets a push once the owner holds that advance; the
  engine values the Academy itself. Icons are vanilla placeholders.
- Game start: `[worldbuilder.start.foundations]` (constructor.toml, `start_simulation.lay_foundations`) gives every
  location with a start University two Library levels before the invalid rows are dropped, and the advance lock leaves
  those rows alone (Gladzor). All 23 historic Universities stay.
- Spread: `script_values/pp_institution_spread.txt` replaces vanilla's channel values. They read
  `pp_institution_literacy` = (0.8 x literacy of nobles, clergy and burghers by size + 0.2 x literacy of all people;
  all people where the estate numbers read nothing) x the rank factor (rural 0.1, town 0.6, city and megalopolis 1.5);
  the trade value (market centres) reads it without the rank factor. Vanilla's coefficients are kept. The estate
  numbers are hidden location modifiers `local_pp_<estate>_literacy` (pop type `literacy_impact`) and
  `local_pp_<estate>_share` (`pop_percentage_impact`); nobles and burghers are full `REPLACE:` copies for it now.
  After the owner embraced, every institution reads `pp_institution_control_spread` (reading x 0.006, at most 0.3 a
  month x control; vanilla flat 2): `in_game/common/institution/*.txt` are same-path copies of vanilla with that one
  line changed (`tests/test_institution_spread.py` fails when a game update changes them; copy them anew then).
- Numbers from a forward simulation on run b18a10d6 (`pp_workspace/literacy/rank_spread_sim`, set R5): market centres
  and towns and cities about twice as fast as before, rural land as slow or slower; years to half a region's people
  W Europe about 73 (92 before), China about 207 (338). Risks: Asia catches up faster (its upper classes read as well as
  Europe's), small rural realms without a town may never reach the embrace threshold, and if the estate modifiers read
  nothing in game the rule falls back to all people x the rank factor (rural then far slower than before). Check a
  location's modifiers ("Literacy of the Nobles") in game.

### Literacy speed x0.4, Library against University, Trade School levels (2026-11-27, Jan; not tested in game)

- Measured on run b18a10d6 (`pp_workspace/literacy/rise_speed`): a raised cap was nine tenths reached 15-20 years
  after a Village School level, about 10 after a Library; a schooled place gained 0.55-0.65 points a year (England and
  France 0.15-0.2 as countries, the fastest campaigns about 1). Sources there: Village School a third, teaching clergy
  a quarter, Library a sixth, country-wide a sixth. So every speed x0.4: `[speed]` in `config/literacy_sources.toml`
  (factor 0.08 from vanilla, the small ones x0.4, base rate 0.002), Village and Trade School 0.004, Library 0.008,
  clergy `literacy_impact` 0.008, print shop 0.002, gymnasium 0.008. Expected: ten points in about 35-40 years.
  NOT reached by the cut (still vanilla's size, `artifacts/data/literacy_sources/left_out.csv`, 121 speed lines):
  religious order callings, the peasant cabinet action, two character traits, the writer artist, four parliament
  issues, two town rights, Jesuit college and about 30 unique or event buildings, about 40 timed event modifiers. Each
  is rare or local, but one of them is worth ten to thirty Village School levels now; Jan has not decided on them.
- Library = how high (estate caps per level, institution growth); University = how fast (`local_monthly_literacy`
  0.03, about four Library levels; no literacy cap and no institution growth any more), plus what it had (migration,
  promotion, room for the classes) and its place under the Society of Sciences.
- Trade School: +2 levels with a specialization town right (3 at most; was +1).
- Two tiers of speed (Jan, later the same night): passive country-wide sources (advances, religions) keep the hard cut
  (x0.08 of vanilla); what a country chooses (societal values, laws and policies, reforms, estate privileges, religious
  aspects and schools: `[speed] active_folders`) x0.4 of vanilla (0.1 -> 0.04, one such choice is worth ten Village
  School levels everywhere). Flavour (unique and event buildings, timed modifiers, traits, gods) is never touched; the
  few chosen sources in left-out folders (parliament issues, peasant cabinet action, religious order callings, two town
  rights) keep vanilla's numbers. The University gives burghers and nobles 5 maximum literacy again (was 10, then 0).

### Literacy sources (the cut, same day)

- Jan: literacy is earned by local buildings, so the country-wide sources are cut. `config/literacy_sources.toml` +
  `literacy_sources.py`, `uv run ppc literacy apply|check` (a finalize step of `ppc build` right after the ladder).
- Rule of 2026-11-26 (Jan: research follows the country's average literacy, which tracks the learned estates only if
  commoners read as little as in history): a positive all-class cap `global_max_literacy = X` becomes
  `global_{nobles,clergy,burghers}_max_literacy = X` at vanilla's value (`[split]`; added to an estate line the same
  block already has); zero and negative caps stay for everyone. Exception, the commoners' base (`[split_exceptions]`):
  Written Alphabet keeps 2 for everyone and gives each estate 3 (vanilla 5). The estate keys are country modifiers
  (`category=country` in vanilla's modifier types, like `global_max_literacy`). The estates' start
  (`[estate_start]`): Guilds burghers 5 -> 20, Improved Religious Organization clergy 5 -> 20 (both written by the
  ladder). Lower-class caps country-wide (`global_<peasants|laborers|soldiers>_max_literacy`): x0.4 to whole numbers
  (10 -> 4, 5 -> 2, at least 1). Every `local_*` cap is not touched. Speed (`global_/local_monthly_literacy`) on the
  same sources: to a fifth (0.1 -> 0.02, 0.05 -> 0.01), and the base rate is halved (`[base_rate]`: Written Alphabet
  and Educated Bureaucrats 0.01 -> 0.005). All literacy speed is flat points a month; the game has no base rate and
  no percentage modifier for it.
- Scope: generic advances, the Innovative societal value, laws and their policies, non-country reforms, estate
  privileges, religions, religious aspects and schools. Each changed object is written whole as a `REPLACE` into
  `<folder>/zz_pp_literacy_sources.txt` (pins in `tests/vanilla_replace_pins.csv`); objects another generator already
  replaces (`written_alphabet`, `educated_bureaucrats`, `guilds`, `organized_religion` by the ladder, `legal_code_law`
  by the RGO redirects, `printing_press_advance` by hand) carry the rule at their own source and the pass checks them
  (`rgo_cost_redirects.py`'s text copy cannot move an all-class cap to the estates and fails if one appears).
- Left out on purpose (`artifacts/data/literacy_sources/left_out.csv`): country, culture, religion and region
  advances, country-specific reforms, unique and event buildings, gods, timed event modifiers.
- Not tested in game (2026-11-25): the mod never replaced religions, religious schools or the societal value before.

## Hansa Members (2026-11-25, Jan)

- The AI Hansa (HSA, a landless building country) never gained a member in any run: the AI's only peacetime routine
  for offering a subject relation skips every subject type that cannot be annexed, and vanilla's `hanseatic_member`
  has `can_be_annexed = no` (as have tributary, march, trade company and others; the AI gets those only by peace deal
  or script). `subject_types/pp_hanseatic_member.txt` is a `REPLACE:` copy with `can_be_annexed = yes` and annexation
  blocked for good (`annexation_min_opinion` and `annexation_stall_opinion` 1000, opinion stops at 200;
  `annexation_min_years_before` 1000), no `annexation_speed` line. Port it on game updates (vanilla pin).
- Side effects: a player Hansa sees an Annex action that always refuses; an AI Hansa that wins a war may demand
  membership in the peace deal; the Hansa's rivals see the option to guarantee a member's independence.
- Not tested in game. Open: the routine takes candidates from the AI's conquest wishes, which are scaled by military
  strength against the target, so a Hansa without ships and soldiers may still find none. Who may join is vanilla's
  rule in the same file (a town or city, fewer than five locations with subjects, opinion of the Hansa 100): 92
  independent countries at 1342 in run 5023bdba, 34 of them in the two German regions.

## Hansa Military Buildings (2026-11-25, Jan)

- Jan: the Hansa's two military buildings work like its merchant houses: levels from the town's development and from
  the League's advances, dear to build, cheap to keep, and the town gains too ("not a parasitic relationship").
  Not tested in game. Both are `REPLACE` blueprints (`hanseatic_shipwright_guild.yml`, `hsa_burgtor.yml`).
- Where: only the League builds them (`country_potential`, `allows_hanseatic_federation_buildings`), only in a town,
  city or megalopolis whose owner is its member (`allow`, `owner = { is_subject_of = scope:actor }`, tooltip
  `pp_hansa_member_town_tt`; the guild also needs a port). Membership sits in `allow`, never in `location_potential`
  (vanilla's guild had it there, and the engine removes a building whose potential fails after an owner change): a
  building that stands stays, `remove_if` takes it only when the location has no owner or its owner is at war with
  the League. Vanilla's Burgtor needed a city, the advance `hsa_hanseatic_fortifications` (age 2) and an owner of the
  League's culture group; it stands from the start now, in member towns of any culture.
- Levels (`script_values/pp_hansa_building_values.txt`): Shipwright Guild 1 + development / 20 + the owner's
  `hanseatic_shipwright_guild_max_level` (vanilla's `hsa_hanseatic_shipwrights`, age 2, and `hsa_mastery_of_the_sea`,
  age 3), 5 at most; Burgtor 1 + development / 25 + the owner's `pp_hsa_burgtor_levels`
  (`hsa_hanseatic_fortifications`, age 2, a `TRY_REPLACE` copy without its `unlock_building`, and
  `hsa_regularized_contributions`, age 5), 4 at most (`advances/pp_hansa_advances.txt`; vanilla 1 to 2 and 2).
  Lübeck, Hamburg and Bremen (development 32, 27, 24) allow two levels of each at the start.
- Price: own keys, 513 in the blueprint -> 1,000 gold (`zz_pp_building_price_stockpile.txt`), `increase_per_level_cost`
  1.0 after `[building_scaling]` x0.75, so levels cost 1,000 / 2,000 / 3,000 / ... before the goods and efficiencies
  (the merchant republic reform's foreign build efficiency about halves it for the League).
- Upkeep: a quarter of vanilla's per level since 2026-11-27 (a third before; see "Hansa Survival") in the unique methods `pp_<building>_maintenance` (one vanilla guild level
  cost the League 0.5 to 1.4 gold a month in run 5d232536, a Burgtor level about 1, on an income of 13 to 20). Staff
  250 a level (vanilla 1,000 laborers, 500 soldiers): five guild levels would have taken half of Lübeck's laborers,
  and a `modifier` block gives nothing without workers (the guilds of run 5d232536 stood empty from about 1500, when
  Lübeck had no laborers left). The Burgtor has `shutdown: never`.
- Per staffed level, the League gets: guild 10 sailors a month, one ship slot (both vanilla) and
  `gold_to_building_owner` 0.5 (the dues on shipped goods; the League paid its wars from such a levy); Burgtor 10 men a
  month (vanilla 5). The town gets: guild harbour suitability and repair (vanilla), `local_sailors` 0.005 and
  `local_monthly_development` 0.002; Burgtor garrison and defence (vanilla) and `local_manpower` 0.005. Both carry
  `raw_modifier free_building_levels = 1` and `ai_construct_weight` 100 / (builder income + 10).
- Start, three towns at two levels each: about 60 sailors and 60 men a month (pools of five years) and 3 gold; vanilla
  gave 20 sailors and no men before the age 2 advance.
- Open: whether `gold_to_building_owner` pays a landless owner as written (vanilla uses it on two buildings); whether
  the AI League builds the levels (500 gold for it is three years of income) and raises ships and regiments (it planned
  a navy of zero in every run); the guilds' workers in towns that run out of laborers.
- `tests/test_merchant_houses.py` (`test_hansa_buildings_in_member_towns`, `test_hansa_advances_give_levels`).

## Hansa Survival (2026-11-27, Jan)

- Jan: "buff the Hansa a little bit more ... they shouldn't always die ... their trade a bit more profitable ... reduce
  their special building maintenance by a bit". In observer run defb89f2 the AI League died as in every run: its
  Kontors went in peace deals (vanilla `disband_kontor` lets any winner close every Kontor of the loser, also those in
  neutral third countries; three of four start Kontors gone by 1347, Bruges about 1500), all its merchant capacity
  came from them, and the Town Hall (2.3 to 3.4 gold a month, no capacity) drained 1,760 gold into the bankruptcies of
  1547 and 1552. Not tested in game, no run yet.
- Peace deals: `peace_treaties/pp_disband_kontor.txt` is a `REPLACE:` copy of vanilla (vanilla pin) whose
  cost depends on where the Kontor stands. The demand is one per Kontor (vanilla: 0.75 x the peace cost of its town,
  any Kontor of the loser). Jan, same day: closing Kontors in other countries must stay possible, raise the war cost
  instead. So every Kontor can still be picked; in a town of the winner (`scope:winner`) or of one of its subjects the
  cost stays 0.75 x, in any other town it is 2 x the town's peace cost (`if` / `else` inside the cost's `add`).
  Select trigger, antagonism, potential, effect, AI desire and the player text stay vanilla. A first version that
  hid Kontors in third countries (f6cc9d2b) was replaced.
- Members' opinion: `subject_opinions = 50` in the `overlord_modifier` of `pp_hanseatic_member.txt` (the opinion an
  overlord's subjects have of it; vanilla's Livonian reform gives 25), so a member can reach the opinion of 100 that
  the guild and the Burgtor need (`need_good_relation`). No pulse or event. The members' opinion of the League was
  never measured (not in the save tables); whether the modifier counts once or per member is not known.
- Upkeep: Kontor 2.5 vanilla levels per step (was 3.5 like the Trade Office and Fondaco, which keep it); Shipwright
  Guild and Burgtor a quarter of vanilla per level (was a third); Town Hall a third of vanilla
  (`production_methods/pp_hansa_maintenance.txt`, hand-written `TRY_REPLACE:hanseatic_town_hall_maintenance`, vanilla
  pin; the Town Hall blueprint is an INJECT and keeps vanilla's method).
- Tax base share (2026-11-27, Jan, same day, later: "another little buff to the Hansa"): the Kontor's `modifier` block
  carries `scaled_gold_to_building_owner = 0.01`: each staffed step pays the League 1 % of the host town's tax base
  (after control) a month, so it earns where its host towns prosper without running a market itself. The engine
  creates this gold (the host keeps its tax; checked on run b18a10d6), pays it only from `modifier`, and the AI counts
  it as plain gold, so the AI League wants Kontors in rich towns more. At the start Kontors of run defb89f2 (London,
  Bruges, Novgorod, Bergen; 7 steps) it is about 1.3 gold a month; a four-step Kontor in a town with a tax base of 100
  pays 4. Vanilla's banking office takes 2.5 % per office. Not tested in game.
  (`test_kontor_earns_a_share_of_its_host_towns_tax_base`.)
- Trade: Kontor merchant capacity per step 2 -> 2.3 (+15 %; market centre 1 -> 1.15), most of the fifth cut on
  2026-11-25 back for the Kontor only.
- `tests/test_merchant_houses.py` (`test_kontor_cheaper_to_keep_and_more_capacity_than_the_other_houses`,
  `test_town_hall_upkeep_a_third_of_vanilla`, `test_members_think_well_of_the_league`,
  `test_kontors_demanded_only_in_the_winners_towns`).

## Long Disasters: Growing Pain (2026-11-27, Jan; not tested in game)

- Why: a vanilla disaster has no timer, it ends only when `can_end` holds, and while it runs the AI declares no war and
  (`has_any_active_disaster = no` in nearly every `can_start`) no other disaster starts. Three observer runs: of 14
  `religious_turmoil` cases stuck 50+ years, 13 met every condition except stability (Ottomans from year 29: stability
  about 4, bar 30). Jan: "I want there to be a period of pain. If it's resolved with whatever conditions the game wants
  to have, then it's fine. If it's not resolved, there's a period of growing bigger pain, but at the end, you can
  resolve it with lower stability if you survived until then"; "I kind of don't even want something like a hard end";
  the pain must not lower what the end asks for ("circular"), it should weaken the state "until breakaway factions or
  other nations feel strong enough to come in", and "it shouldn't always just cause bankruptcy". Replaces the breaking
  point of the same morning (8424df7b, 9e5e9d24: bands with stability hits, a forced end at 40 years with a breakaway,
  civil war or collapse, reward withheld), which is gone.
- Scope (`COVERED` / `VANILLA` / `EXEMPT` in `disaster_growing_pain.py`, every vanilla disaster in exactly one):
  covered, general (any country of a broad kind): `religious_turmoil` (Christian, not Orthodox / Miaphysite / France,
  age of reformation), `horde_civil_war` (steppe hordes), `succession_crisis` (monarchies), `crisis_of_faith`
  (theocracies but the Papacy), `oligarchic_capture` (republics), `decline_of_empire` (empires from age 3),
  `peasants_war` (monarchies and theocracies, ages 3-4), `revolution_disaster` (age 6 with the Enlightenment). Pure
  vanilla, no copy (one tag, culture or national story): ambrosian_republic_disaster, byzantine_succession_crisis,
  castilian_civil_war, ciompi_revolt, crisis_of_the_chinese_dynasty, crisis_of_the_sayfawa_dynasty,
  curse_of_stefan_uros_iii, death_of_hayan_wuruk, decline_of_majapahit, decline_of_mali, dissolution_of_delhi,
  fate_of_the_phoenix, hook_and_cod_wars, muscovite_succession_war, reform_society, rise_of_the_szlachta,
  savonarola_disaster, sinicization_disaster (China's neighbours against China, ends by its own event counters),
  struggle_for_royal_power, turmoil_in_brandenburg, twilight_of_the_tsardom, war_of_the_aragonese_union_disaster,
  war_of_the_roses. Exempt (vanilla ends them within 25 years): aspiration_for_liberty, coup_attempt,
  court_and_country, english_civil_war, french_wars_religion, revolutionary_chaos, time_of_troubles.
- Years 0-25: vanilla. 25-50: one country modifier per five years (`pp_disaster_pain_<disaster>_1..5` at
  25/30/35/40/45), swapped by `pp_disaster_pain_effect` from the disaster's own `on_monthly`; notice events
  `pp_disaster.1` (first step) and `.2` (each later step). The last step stays for as long as the disaster runs: no
  hard end. Lines at the last step (the core, even steps; `CORE`): estate target satisfaction -0.2 (vanilla's great
  permanent penalty; small / medium / large / larger / great by step), crown power -0.2 (succession_crisis,
  horde_civil_war, crisis_of_faith), government power lines -0.3 a month (decline_of_empire's legitimacy -0.3), rebel
  growth of the disaster's kind 0.015 (vanilla 0.003-0.02), separatism +0.1, subject loyalty -20, levy size -0.3
  (decline_of_empire's manpower -0.3), land morale and discipline -0.1 each (decline_of_empire), tax efficiency -0.15
  (between vanilla's large -0.1 and huge -0.2); plus one story line each (`COVERED[...].extra`). Rebels: religious
  (religious_turmoil), pretender (horde_civil_war, succession_crisis: a rising pretender ends the succession crisis,
  `in_civil_war = yes` is one of its exits), clergy estate (crisis_of_faith), nobles + burghers estate half each
  (oligarchic_capture), nationalist (decline_of_empire), peasants estate (peasants_war), burghers estate (the
  revolution's rebels, revolution_disaster).
- Nothing the end asks for: `EXIT_NUMBERS` lists every number each covered disaster's vanilla end trigger compares and
  the modifiers that would push it; those and every stability modifier (`STABILITY`) are never written (so no
  legitimacy for succession_crisis, no devotion for crisis_of_faith, no republican tradition for oligarchic_capture, no
  horde unity for horde_civil_war, per-estate satisfaction without the clergy for religious_turmoil and without the
  peasants for peasants_war, no separatism for decline_of_empire). A test reads every comparison in the end triggers.
- From 50 years: `can_end` = `OR = { AND = { <vanilla> } AND = { pp_disaster_relief_due_trigger
  pp_disaster_relief_<disaster>_trigger } }`; the relief trigger is vanilla's end trigger with only the stability bar
  lowered (generated into `scripted_triggers/pp_disaster_relief_triggers.txt` from vanilla's `disaster_triggers.txt`,
  `RELIEF` per disaster): `stability > 30` (religious_turmoil), `> 25` (succession_crisis, crisis_of_faith,
  oligarchic_capture), `> HORDE_CIVIL_WAR_END_STABILITY` = 25 (horde_civil_war), `> 10` (peasants_war) become
  `stability >= 0`; decline_of_empire's bar is already 0 and goes 25 lower (`>= -25`); revolution_disaster has no
  stability bar and so no relief (its revolutionaries win or are beaten). Notice `pp_disaster.3` once the relief is
  open (`pp_disaster_relief_notice_effect`). Vanilla's `on_end` runs unchanged either way (the reward stays); before it,
  when vanilla's own condition does not hold (the relaxed branch ended it), `block_disaster_temporarily_effect` 25
  years (`pp_disaster_restart_allowed_trigger` at the top of the copy's `can_start`); after it the step modifiers go
  (`pp_disaster_pain_clear_effect`). No pulse: nothing on an on_action, the events have no timer or effect.
- Form: same-path copies `in_game/common/disasters/<vanilla file name>` of the covered disasters only (marked `# PP:
  growing pain`). `ppc disasters apply|check|pin` (`disaster_growing_pain.py`, also run by the finalize step of
  `ppc build`/`sync`) writes them byte for byte from vanilla plus the inserted lines, the relief triggers, the step
  modifiers (`main_menu/common/static_modifiers/pp_disaster_modifiers.txt`) and their text
  (`pp_disaster_pain_l_english.yml`); stale copies go. Hand-written: `scripted_triggers/pp_disaster_triggers.txt`,
  `scripted_effects/pp_disaster_effects.txt`, `events/pp_disaster_events.txt`, `pp_disasters_l_english.yml`; the rule
  is also in the vanilla Disaster concept's description (`localization/replace`).
- Game update: `tests/test_disaster_growing_pain.py` fails when a vanilla file this pass reads changes
  (`tests/disaster_vanilla_pins.csv`: the covered disasters and `disaster_triggers.txt`), when a disaster is added
  without a class, when a copy is not vanilla plus the rule, when an end trigger compares a number `EXIT_NUMBERS` does
  not list, or when a stability clause in `RELIEF` is not found exactly once. Review, then `uv run ppc disasters apply`
  and `uv run ppc disasters pin`.
- Not known: the step sizes' effect on AI wars against a weakened country and on bankruptcy (no run yet); whether a
  rebel kind's growth reaches the disaster's own rebels (e.g. crisis_of_faith's schismatic clergy, created as clergy
  estate rebels); whether separatism lowers control (left out of decline_of_empire for that reason). A save loaded
  mid-disaster gets the step it is in at once; old saves carry the removed `pp_disaster_coming_to_head_*` modifiers
  and band variables (no save compat).

## Maghreb Control Gifts (2026-11-27, Jan; not tested in game)

- Morocco, Tlemcen and Tunis held 0.85-0.91 population-weighted control by 1837 in four runs, inland included. Jan: their
  cities may have decent control, inland should be hard. The country and region control gifts of the base game and
  Across the Pillars are cut, each object kept with its other lines: flat monthly control to a fifth, maximum rural
  control and Atlas Strongholds' proximity relief halved, separatism and rebel growth reliefs by a third; Tlemcen's
  tribes reform keeps vanilla strength below half tribes satisfaction (two modifiers, `scale` with `min`/`max = 0`).
  Copies: `bureaucracies/pp_bureaucracy_adjustments.txt` (new folder), `pp_government_reform_adjustments.txt`,
  `pp_law_adjustments.txt`, `pp_country_advances_adjustments.txt`, `pp_estate_privilege_adjustments.txt` (vanilla pins);
  the list and the left-out objects are in `docs/country_finetunes.md`. `tests/test_maghreb_control.py` checks every
  value as a ratio of today's vanilla (a game update that changes one fails) and that every tribes privilege, DLC ones
  included, carries the -0.075 research row exactly once.

## Great Pestilence (2026-11-27, Jan; seen in Jan's observer run bd7d9616, which still had the broken leak)

- Jan: "make it so that the Great Pestilence can spread better. Make it more deadly, make it spread easier ... we want
  it to be harder." Runs: the Americas lost about a third (run 5d232536 by 1567, from the saves' resistance: Mesoamerica
  about half, the Andes a tenth; rough rural Andes untouched), history 80-90 % over a century and a half.
- `diseases/pp_great_pestilence.txt`, TRY_REPLACE of vanilla `great_pestilence` (pinned): for locations with no road and
  mountains, desert or jungle R0 x0.25 -> x0.5, spread threshold 0.85 -> 0.60 (the flat value), stagnation chance x3 ->
  x2; `mortality_rate` {0.75 0.9} -> {0.85 0.92} (milder since 2026-11-28, Jan: "a little bit mild"; x0.75, x1.5 and
  {0.9 0.95} on 11-27 took the Americas from 37 M to 12 M in the 1450s and to 56 M by 1837 in run bd7d9616, earlier
  runs 24-30 M at the low point and 70-108 M; the new numbers are not modelled or run); no `monthly_resistance_reduction`, as in vanilla (the first version
  had 0.001 in the Americas only; the game reads that value without a location, so the continent check wrote a script
  error on every read, 10,551 in one observer run, and read 0; removed the same day). The migration line of `zz_pp_disease_migration_adjustments.txt` sits in the copy
  (an inject misses a replaced block); that file no longer injects into great_pestilence.
- Engine facts (EU5 1.4.9 saves): resistance is stored per location (setup `add_disease_resistance`, with a date) and
  per pop in affected locations (with `stagnated_counter`, 3600 days = `STAGNATION_LENGTH_DAYS`); the leak is linear
  (vanilla bubonic plague's own comment: 0.0001 a month "took 833 years"). The setup gives Europe, Asia and Africa
  great_pestilence resistance 1.0 from 1337; a leak in the Old World would have it gone before contact, and
  `monthly_resistance_reduction` has no location in scope (seen in game: "Event target link 'continent' returned an
  unset scope"), so there is no leak at all. R0 x0 and stagnation 1.0 outside the Americas stay, so the Old World never grows an outbreak. The pestilence
  has no `specific_pop_type_effect`: colonists in America are hit as natives are, in vanilla too.
- Calculation (scratchpad model `b1_sim.py`: per location the script's R0, stagnation, 10 % fate per calc, spread at the
  threshold to neighbours on a lattice with the regions' rough shares; assumes a stagnated location grows no more, which
  reproduces the saves: vanilla Andes 7-10 %, rough rural 2 %, Mesoamerica 37 %). Deaths in one wave, per location
  class (rough rural / flat rural / town / city): vanilla 2-10 / 15-56 / 15-63 / 69 %, new 55-62 / 68-75 / 78-86 /
  91-93 %; a fully reached location loses about the mortality (vanilla 80 %, new 90-92 %). Over the situation (it lasted
  11, 88 and 130 years in the runs): Andes / Mesoamerica 68 / 73 % throughout, since nothing leaks (a 0.001 leak in the
  Americas would have given 75 / 86 % at 90 years and 84 / 88 % at 130, measles' 0.002 88 / 91 % and 91 / 93 %; it
  would need another way than this value). Observer run bd7d9616 without a working leak: the Americas at 18 M people in
  1562, 27-36 M in the runs before the change.
- Ending: the situation ends only in a month with no active outbreak; without a leak a location that was hit stays
  closed, so there are no later waves in the same place.
- `tests/test_great_pestilence.py` pins every changed number against vanilla's (fails when vanilla's file changes),
  checks the other lines are vanilla's and the Old World shield.

## Russia and Lithuania (2026-11-27, Jan; not tested in game)

- Forming Russia and the tsardom decision count Novgorod, Tver and Vladimir held by a subject or union partner
  (`formable_countries/pp_formable_adjustments.txt`, `decisions/pp_russia_decisions.txt`); Muscovy annexes its union
  partner Vladimir by decision (`pp_mos_vladimir_patrimony_decision`, AI at once, players choose); only Muscovy and
  Russia keep vanilla's `russia_conquer_region`; Lithuania's Ruthenia and Smolensk aim; Hungary's Ruthenia aim retired.
  Details and why: `docs/country_finetunes.md`; `tests/test_russia_lithuania.py`. The repo's clausewitz parser reads
  `a ?= {` as an item plus a `?` entry, so tests compare such blocks as text.

## Vanilla Replace Pins (2026-11-02, Jan)

- A `REPLACE:` or `TRY_REPLACE:` block is a frozen copy of vanilla, and `ppc update-audit` compares vanilla with vanilla
  only. `agricultural_cultivation` kept `monthly_towards_serfdom` where vanilla has `monthly_towards_land`; the game
  tracker starts on 2026-05-17 with land already in place, so no audit could show it.
- `tests/vanilla_replace_pins.csv` holds the hash of the vanilla block (the audit's `new_hash`, joined with `+` per DLC
  inject) for every replaced block. `tests/test_vanilla_replace_pins.py` fails when one differs, so after a game update
  `ppc test` lists these blocks too. Port the change into the mod's copy, then run `uv run ppc vanilla-pins record`.
  `ppc vanilla-pins check` lists the same blocks without the suite. A new `REPLACE:` needs a record as well. The file
  stays out of `config`, a World Builder input: a record there would rerun the start setup on the next sync.
- The same test compares the mod's copies with vanilla today for societal value moves (`monthly_towards_*`): a replaced
  block may differ only if it is listed in `DELIBERATE_SOCIETAL_VALUE_MOVES`. Other lines are not compared with vanilla
  today, because the mod changes them on purpose; the pins catch their vanilla changes from 2026-11-02 on.

## AI Roads (2026-10-15, Jan)

- Roads should not be good everywhere, upgrades rarely: gravel 50, paved 265, modern 495, railroad 2000 per unit
  (`pp_road_gold_adjustments.txt`; 2026-11-02, Jan: too many late roads, 1,504 railroads by 1837 in run ebdb631e; +10 %, railroad +54 %. A cost
  limits them, no tax base line and no bonus). The engine credits a candidate road with the full land - road saving at its
  far end even where that end already has a cheaper path (river leg 12 < road 20) or no proximity; 42 % of the AI's new
  roads in run 4b90876a raised nothing.
- No AI road weight (removed 2026-11-27, Jan: "the AI should just understand this naturally ... fully remove it"; an
  AI-only veto or weight on roads changes only the AI's decisions and leaves the player free, which he never wants
  except as the very last resort). From 2026-10-15 until then `road_types/pp_road_ai_weights.txt` vetoed roads whose
  two ends had nearly the same proximity. Roads carry vanilla's valuation again; price and benefit, the same for
  player and AI, are the levers.

## Colonial Range (Maritime Reach, 2026-11-19, Jan)

- Rule (one for every country, AI and player): the base colonial range (`country_base_values`, 1000) stays; the flat
  colonial range of the researched advances (`pp_advance_colonial_range`: merchants and trade 250, New World 600, open
  sea exploration 1500, Exploration 500, chartered companies 1000, superior ship design 1000) counts only by the
  country's maritime reach `pp_maritime_reach` (0..1). The auto modifier `pp_limited_maritime_reach` takes the rest off
  (`colonial_range = -1` scaled by `pp_maritime_reach_shortfall`); `colonial_range_modifier` percentages still multiply
  the total. Files: `script_values/pp_maritime_reach_values.txt`, `scripted_triggers/pp_maritime_reach_triggers.txt`,
  `auto_modifiers/pp_maritime_reach.txt`; `tests/test_maritime_reach.py` keeps the advance list equal to every advance
  with a `colonial_range` line and pins the points.
- Maritime reach: points over every owned port that faces the open sea (`pp_open_sea_port`: a water neighbour of
  ocean, deep ocean, coastal ocean, narrows or inland sea topography outside the Black Sea and Caspian areas; river
  channels, lakes and the two enclosed seas do not count; ports in colonies count): 1 per port, 3 in a town or city,
  +2 per shipbuilding slot there (`max_ships_built_at_same_time`: dock 1, dry dock and better 2+; at most 2 slots).
  Reach = (points - 6) / 18, clamped: none at 6 or less, full from 24.
- It replaced the AI charter cap cut `pp_colonial_charter_gate` (2026-10-09: -6 parallel charters unless colonial
  subject, 150+ locations or 8+ open-sea ports at home). That gate blocked about nine in ten native countries next to
  unowned land (Cahokia, Chimu, Kanem, Songhai, Great Zimbabwe and Kongo in every save, the Tarascans in most; Discord
  report 2026-11) and let countries with at most 3 open-sea ports through by size: 14 overseas jumps in the 9 runs (Bohemia 7,
  Hungary 3, Kyiv, Austria, Guelders, Muscovy). No charter cap is cut now.
- Engine behaviour (checked against the runs, details in the private notes): land next to our own or a subject's land
  (also across wasteland) can be chartered whatever the range, so frontier colonisation (Siberia, the natives'
  backyard) never depends on range. Any other target must be a port location within naval distance: the shortest sea
  path from one of our own ports (port, its sea zone, sea zones, the target's sea zone, the target), each step the
  distance between the bounding-box centres of the two tiles in map pixels, against colonial range x (1 +
  colonial_range_modifier). Without ports nothing overseas is in range. In 9 runs 96 % of 6,179 non-adjacent port
  colonies lay inside the colonizer's range (own and subjects' ports); first entries into a new subcontinent sat at a
  median 0.65 of it, three quarters below 0.91; the rest are chains or range gained inside one five-year save interval.
- Fit (2026-11-19): nine full observer runs (stockpile-prices dataset: 77768726, 16fe282a, ebdb631e, cf884236,
  97f9d39a, 6ee05b7e, 67859be2, 060ad1de, af7dce96); per country and save: ports by class, shipyards, colonial range and
  the naval distance to the nearest unowned port per target area; every first overseas colony replayed under the new
  range (blocked jumps wait until a home port reaches a target). First year in range, median over the runs (old range
  / new range / first colony observed; history):

  | | Atlantic islands | West Africa | Brazil | Caribbean | North America | history |
  |---|---|---|---|---|---|---|
  | Portugal | 1342 / 1342 / 1387 | 1432 / 1432 / 1642 | 1447 / 1447 / 1462 | 1442 / 1442 / - | 1442 / 1442 / 1749 | islands 1420-50, Brazil 1500-40 |
  | Castile | 1342 / 1342 / 1372 | 1417 / 1417 / - | 1447 / 1447 / 1667 | 1447 / 1447 / 1457 | 1417 / 1417 / 1728 | Canaries ~1490, Caribbean 1492 |
  | England | 1527 / 1527 / 1527 | 1527 / 1527 / 1552 | 1552 / 1552 / 1667 | 1542 / 1542 / 1672 | 1527 / 1527 / 1557 | 1600-40 |
  | France | 1417 / 1417 / 1526 | 1507 / 1507 / 1654 | 1522 / 1522 / 1597 | 1527 / 1527 / 1559 | 1512 / 1512 / 1537 | 1600-40 |
  | Holland | 1557 / - / - | 1551 / 1582 / - | 1562 / - / - | 1609 / 1662 / - | 1551 / 1582 / 1657 | 1600-30 |
  | Denmark | 1619 / 1619 / - | 1572 / 1574 / 1672 | 1602 / 1602 / - | 1622 / 1622 / 1717 | 1572 / 1574 / 1652 | 1620-70 |
  | Sweden | 1677 / 1677 / - | 1577 / 1577 / - | - | 1657 / 1657 / - | 1577 / 1577 / 1681 | 1638 |

  The big colonizers keep every observed jump (their reach is full from game start); their early dates are the
  advances', not the gate's. Distinct overseas colonizers per half century, old gate observed / replayed: 1600 9 / 9,
  1650 12 / 11, 1700 14 / 12, 1750 14 / 13, 1800 14 / 12. Without any gate, 44-55 European countries with at most 3
  open-sea ports could reach an unowned overseas port in 1552-1702 (the pre-gate flood of Basel, Kleve, Cologne ...);
  under the rule none. Small coastal countries (at most 40 locations) that could reach one: 8-13 -> 3.5-7; larger
  coasts 8-12 -> 8-11.
- Both error sides: Holland (about 8-10 open-sea ports, 4-5 of them towns) is at 0.56-0.72 reach until about 1600 and
  full from about 1650 with its shipyards; its North America reach comes 31 years later than with the old range, its
  observed jumps (1652, 1662) are kept. Rump states lose their reach (France cut to 1-6 ports, a 7-location Sweden).
  Frisia's rural coast (10 ports, 2 towns): 1 of 6 jumps kept, 3 delayed 5 years, 2 never. Still through: coastal
  states with port towns and yards (Genoa 6 of 6 jumps, Pomerania-Wolgast, Brittany, Normandy, Aquileia once it holds
  the Venetian coast) and land realms that hold a real coast (Hungary with Dalmatia 3 of 4, Lithuania, Muscovy). Inland
  countries, the Hanse cities (reach at most 0.06), Black Sea and Caspian powers: no overseas reach.
- AI: it does not value colonial range when it builds, so its coast does nearly all the work: shipyards lift 2-4 % of
  the countries with advance range to full reach (mean reach +0.015 to +0.04); Holland is where they count. The auto
  modifier is evaluated with the country modifiers; one pass over the country's ports (two with partial reach); the old
  gate's trigger cost 0.146 s over 82k evaluations in the 2026-11-10 profile. Not tested in game.
- Watch in the next run: who colonizes overseas by half century, Holland's first colony, native backyard charters
  (Inca, Chimu, Kongo, Kilwa, Mali, Benin), running charters of a country that loses its ports.

## Colonial Plantations and Cash-Crop Trade (2026-11-27, Jan; not tested in game)

- Sites: the sugar, cotton and tobacco plantations stand where `pp_<crop>_plantation_site` holds
  (`scripted_triggers/pp_plantation_site_triggers.txt`, hand-written): the location's raw material is the crop, or a
  static climate gate (World Builder classes, fertility modifiers, river, coast; never ownership). Sugar: tropical,
  tropical monsoon or savanna on low ground by the sea or a river, rainforest only on the sea coast; subtropical only on
  floodplains, deltas and wetlands. Cotton: subtropical, savanna, tropical monsoon, hot semi-arid or mediterranean on
  flat land or plateau; arid only along a river. Tobacco: tropical to mediterranean on flat land or hills with
  moderate or better fertility. The owner rule (overseas for the owner, or a colonial subject's land) is
  `pp_plantation_owner_allowed` in `allow`, so a conquered or released plantation stays. The free-labour farms keep the
  RGO-only rule.
- Colonial sites, b18a10d6 1737 (owner rule applied; RGO only / old placement trigger / this gate): sugar 39 / 983 /
  481, cotton 68 / 402 / 541, tobacco 29 / 653 / 610. The gate admits the historical zones (Caribbean, Brazil's coast,
  Guianas, Gulf coast, Louisiana and Florida for sugar; Brazil's north-east, Mexico, the US South for cotton; the
  Chesapeake, Bahia, Cuba for tobacco). Too much: cotton in the Chesapeake (62 sites) and the Mediterranean; too little:
  the Atlantic islands (1 colonial sugar site; Madeira and the Canaries are hills).
- Colonial nations focus the three crops: `global_<crop>_output_modifier` 0.5 (was 0.1) in `pp_colonial_nation.txt`.
- Colonial nations set no trade policy: `max_tariff = -2`, `max_trade_subventions = -2` in the same subject_modifier.
  A rate is held between minus the subvention cap and the tariff cap, each clamped to 0..1, so the cap is 0 for the AI
  and the player alike. The overlord was already exempt from its colonial nation's tariffs
  (`overlord_exempt_from_subject_import_tariffs`, export rates too); the cut frees every other buyer. Only colonial
  nations that own a market centre had rates (7 of 55 in 1737, 20 of 115 in 1837).
- Transport cost 0.5 for sugar, cotton and tobacco (`pp_goods_adjustments.txt`; vanilla default 1): half the merchant
  capacity and maintenance per unit on every route, Old World ones included. Cocoa and coffee 0.5 too (same day, Jan:
  coffee 1.3-1.8x default in Europe with about half its demand unmet while American markets hold 50-150 months of
  cocoa and coffee stock); dyes keep 1.
- Pop demand (`[stockpile_prices.pop_demand]`, `ppc stockpile apply`): tobacco 0.5 -> 0.65, sugar 0.7 -> 0.8 (Jan: fit
  history). The 2026-11-01 cut came from a run where demand exceeded supply; now both sit in world balance at 0.5-0.6
  of default and tobacco carried 38 months of stock after its demand opened around 1640. Tea 0.65, cocoa and coffee 0.4
  stay. History points the same way: both became goods of ordinary people in Europe after 1650 (English tobacco about a
  pound a head a year by 1700, sugar about 4 lb in 1700 and 20 lb by 1800), so a half cut on estate demand was low.
  Start market stock unchanged (rebuilt, same rows): these goods get stock only in their producing markets, where the
  start make outweighs the pop use, so flow = max(use, make) does not move; settled prices left until a run shows them.
- Why (run b18a10d6, measured): Europe is not short of these goods (no unmet pop or building demand; sugar 0.58-0.82,
  cotton 0.62-0.73, tobacco 0.36-0.49 of default; coffee is the one short plantation good). 70-85 % of American output
  comes from colonial nations' land, but most of it sits in markets whose centre a native country owns (Mayapan,
  Azcapotzalco, Canajoharie, Cahokia, Kuskatan), which tax exports at 20-30 %. European importers carry 85-95 % of the
  exports on their home capacity; sugar and tobacco earn 0.2-0.3 gold per capacity there, below most of their other
  trades, so 100-160 units a month of exportable sugar and tobacco stay in American stock (4,000-5,700 units each).
- Tests: `test_building_upgrade_chains.py` (site trigger, owner in allow), `test_project_config.py` (transport costs,
  colonial nation caps and focus), `test_stockpile_prices.py` (tobacco and sugar demand).

## Slave Trade (2026-11-27, Jan; not tested in game)

- How the game moves people (behaviour, checked against three runs' saves): a traded unit of `slaves_goods` moves people
  only when the market that sold it has slaves standing at its own slave market or slave centre sites. People per unit
  = 1,000 x `TRADE_SLAVE_FACTOR` (0.2, vanilla, unchanged) x min(1, slaves at the seller's sites in thousands / units the
  seller ships that month), shared equally over the buyer market's locations with open slave jobs; with no such
  location the goods are delivered and nobody moves. Producing the good removes nobody. Old World slave markets hold
  almost no slaves (their towns' people mostly share the owner's religion), so their goods are empty; the West African
  slave centres hold 0.3-3.4 M slaves. In the runs the Americas bought most of their slaves goods from the Maghreb and
  Western Europe: 2-300 people landed a month for most of the game, 5,456 in the one save where West Africa sold to
  Brazil directly (history: about 3,000 a month on average, 6-7,000 at the 1780s peak).
- Rule (Jan: what things cost or give, for player and AI alike; no AI weights): the empty supply shrinks, the supply
  that carries people grows, the plantations ask what that supply can meet.

  | | vanilla | PP before | PP now |
  |---|---|---|---|
  | slave market slaves goods per level | 2.0 | 2.0 | 0.5 (every input x0.25, margin kept) |
  | slave centre slaves goods per level | 1.0 | 1.0 | 2.0 (inputs kept) |
  | slave centre `building_enslavement_power` | 0.20 | 0.20 | 0.30 |
  | slave market `building_enslavement_power` | 0.10 | 0.10 | 0.10 |
  | sugar / cotton / tobacco plantation worked method slaves goods | 0.25 (maintenance) | 0.3 | 0.1 (the other goods x1.73-1.76, input cost and margin kept) |
  | `TRADE_SLAVE_FACTOR` | 0.2 | 0.2 | 0.2 |

- Arithmetic: a West African unit carries 200 people as long as its sites hold more slaves (in thousands) than it
  ships units, which every save shows by a wide margin (hundreds of thousands against tens of units), so 25-35 units a
  month from West Africa land 5-7,000 people where plantations have open jobs. A centre at full staffing now makes 2
  units (break-even at about 0.47 of the default price; West African prices sat at 0.49-0.63, where the old 1-unit
  recipe lost money and the centres ran at 10-77 % staffing) and refills its site with up to 300 people a month (the
  engine takes at most 1 % of the largest eligible pop a month). With 20 / 30 / 45 centres (17-43 stood in 1837 in the
  runs): about 32 / 48 / 72 units and 4.8 / 7.2 / 10.8 thousand enslaved a month at 80 % staffing. American demand at
  0.1 per worked level, about 80 % of levels worked: 300 levels 24 units, 600 levels 48, 1,000 levels 80. People landed
  a month at most, while plantations open jobs (filled plantations need only their turnover), with the West African
  refill in brackets (above it the stock at the sites, 0.3-3.4 M, drains slowly):

  | plantation levels | demand (units) | 20 centres (refill 4.8 k) | 30 centres (7.2 k) | 45 centres (10.8 k) |
  |---|---|---|---|---|
  | 300 | 24 | 4.8 k | 4.8 k | 4.8 k |
  | 600 | 48 | 6.4 k, 16 units from elsewhere | 9.6 k | 9.6 k |
  | 1,000 | 80 | 6.4 k, 48 units from elsewhere | 9.6 k, 32 from elsewhere | 14.4 k, 8 from elsewhere |

  At the old 0.3 per level the same plantations asked 72 / 144 / 240 units, up to seven times what West Africa can
  ship, and the rest came from empty Old World goods.
- Old World: the slave markets (1,077-1,335 levels in 1837, about 10 % staffed, prices 0.5-0.7 of default with
  2,000-4,000 units in stock world-wide) keep their margin; their capacity at full staffing falls from about 2,670 to
  670 units a month against 300-450 units of Old World demand (janissary barracks 190-330, slave labour yards 60-190,
  mamluk, galley and ghilman barracks about 30). Expected: the stock drains for some years, then prices rise towards
  the slave market's break-even (about 0.92 of default) and more of the standing levels staff up. Janissary barracks
  maintenance about +7 % at that price (slaves goods are a fifth of it), slave labour yards pay about 1.6 gold more per
  level. People moved by Old World trades are bounded by the few slaves at their sites (East Africa 0.1-2.2 thousand,
  Eastern Europe 1-8), not by units, so the Indian Ocean, Black Sea and steppe trades (50-500 people a month in the
  runs) keep about what they move; Central Asia's slave-market slaves were never exported. American native slave markets
  (64-166 levels) also make a quarter, which takes the local empty supply out of the American markets.
- Not changed: `TRADE_SLAVE_FACTOR` (it would scale every slave trade alike, the Old World ones included), slave centre
  `max_levels` 1 and its sites, slave goods price and transport cost, raids and enslavement rules.
- Unverified in game: whether American importers switch to West Africa (the AI picks by route profit and does not see
  which goods carry people), how many centres the AI builds once they pay, how fast the empty stocks drain.
  Cheapest check: A/B from a 1650-1700 save of run b18a10d6, a few observer years: plantation entries in AI queues and
  plantation constructions, slaves goods bought by American markets per seller region, `SlaveTrade` arrivals in the
  Americas per source market, slave centre count and staffing, Old World slaves goods price and janissary staffing.
- Tests: `tests/test_slave_trade.py` (new values against vanilla, margins and input costs kept, the define untouched).
  Docs: `docs/market_rulebook.md` 8g.

## Trade Reach (2026-11-24, Jan)

- Rule (Jan: nations that invest in trade and are built for it get better at it over time; a nation that is not trade
  focused must not jump in with gold; the mellow variant, "so we don't fuck over some countries"): the base trade range
  (1000) and every percentage trade range modifier stay; the flat trade range of the researched advances
  (`pp_advance_trade_range`: merchants and trade, the age 2 and age 3 range advances 250 each, chartered companies and
  joint stock companies 200 each, and the seven country and culture advances with a `trade_range` line, 150-200) counts
  by `pp_trade_reach` (0.5..1). The auto modifier `pp_limited_trade_reach` takes the rest off (`trade_range = -1` scaled
  by `pp_trade_reach_shortfall`), like the maritime reach. `NCountry.MERCHANT_DISTANCE_COST_DIVISOR` 200 -> 300 the same
  day (800 vanilla).
- Points (all numbers in `script_values/pp_trade_reach_values.txt`; fit in `pp_workspace/trade_range_study/sim2`,
  `r3_best_weights.json`): burghers 10 per percent of the population above 1.5 %, at most 45
  (`percentage_pop_type_in_country:burghers`); seafaring 40 x `pp_maritime_reach`; capital economy up to 30 (its half of
  the slider), plutocracy up to 15 (linear over the whole slider), naval and free subjects up to 15 (their halves); people
  in towns and cities 0.5 per percent, at most 15; trade buildings at home up to 15 at 4 levels per 100,000 people
  (`total_effective_building_levels` of the marketplace line, port authority, stock exchange, trading hub, entrepot,
  market warehouse, funduq, caravan stop, caravanserai; not the merchant houses or banking offices). Raw reach = points /
  150, clamped 0..1 (the simulation's 100 saturated the trade nations by 1450; Jan wants them to keep improving); reach =
  max(0.5, raw); a country without locations has no points (the floor). The raw reach also sets the merchant house cap
  ("Merchant Houses").
- The town share is the one input that walks the country's locations: `pp_refresh_trade_reach`
  (`scripted_effects/pp_trade_reach_effects.txt`) stores it in the country variable `pp_trade_reach_urban_share` once a
  year from the Subsistence Land pulse (`on_action/pp_subsistence_land.txt`, the cost switch stops only Subsistence Land)
  and at game start; a country created later has 0 town points until its first pulse. Everything else is read live.
- Text: the modifier's description names the inputs and shows the viewing player's points per input
  (`GetPlayer.MakeScope.ScriptValue`); the points total carries one described row per input (`PP_TRADE_REACH_*`).
- Estimated reach at 1342 (run 5023bdba, points / raw / house cap): Venice 143 / 0.95 / 8, Ragusa 122 / 0.81 / 7, Hormuz
  88 / 0.59 / 6, Genoa 87 / 0.58 / 6, Aragon 82 / 0.54 / 5, Pisa 81 / 0.54 / 5, Granada 63 / 0.42 / 4, Yuan 61 / 0.41 / 4,
  the Mamluks 56 / 0.38 / 4, Novgorod 42 / 0.28 / 3; landless countries (the Hansa, the banks) 0 / 0 / 1.
- `tests/test_trade_reach.py`. Not tested in game.

## Location Plans (town-right plans until 2026-11-21)

Branch note (2026-11-20, Jan): `town-plans` became the working branch `0.11` (in development, not released; the mod's
version field stays 0.10.0 until a release). `town-plans` and `location-profiles` no longer exist; where this file
names them, read `0.11`.

- The Construction Plan's one per-location decision is a plan (77: 75 goods + `food` + `trade`; `town_plans.py`, its
  module docstring is the contract), set and removed only by the mod's button (Location Plan window, the location
  window's Plans row), any owned location incl. rural, several per location. Location Profiles and the Location Plan
  marks (goods and building marks) are gone.
- Plans as markers (2026-11-21, Jan: "why did we add the level 0 rights? ... We just use our plans, and the plans
  apply the relevant town rights if the setting is turned on"; tested in game the same day, `docs/location_plan.md`
  "Tested in game (2026-11-21, plans as markers)"): location variable `pp_tplan_p_<plan>`, `pp_tplan_any` while one is
  held (trigger `pp_tplan_held`; `pp_tplan_held_scan` asks every marker), country list `pp_tplan_locs` (kept by
  `pp_tplan_flip`; the Locations look `pp_lprof_gather` and the charter look walk it, script has no iterator over
  locations with a variable; the gather sweeps off what the country no longer owns or holds no plan). An owner change
  strips them: `on_location_changed_owner` -> `pp_tplan_owner_changed` -> `pp_tplan_owner_changed_effect` (off
  `scope:loser`'s list, its Locations saving released, generated `pp_tplan_strip`). The closer's location list
  `pp_pclose_for` became variables `pp_pclose_for_<plan>` (`pp_pclose_for_held`, `pp_pclose_for_clear`). GUI test
  `Location.MakeScope.Var('pp_tplan_p_<plan>').IsSet`; the map mode draws the plans' icons, then the real rights. Until
  then each plan was a town right `pp_plan_<plan>` (`potential = { always = no }`, no bonus, `kept_at_conquest = no`,
  its own slot and colour); file, text and the 77 icons removed (`town_plans.stale_paths`). Old saves keep each former
  plan right as a typeless town right and lose their plans; the mod ships no cleanup, a one-off console file
  (`pp_plans_restore.txt`, kit `pp_testing\townplan_test_20261120\gen_restore.py`) restores a running game.
- The Locations rule group (key `profiles`, code 105) builds for every held plan, forced (no payback limit, no market
  limit): the good's producers level after level, the newer tier as it unlocks (upgrade first), food = staple food
  producers + Province Food buildings, trade = trade buildings; for the 15 plans whose producers need a town or city it
  raises the rank first (`pp_tplan_raise` -> `pp_cplan_country_rank_up = { rank n why = 105 }`, state 11 where it
  cannot). While the setting "Grant a plan's charter and rights" is on, Towns and Buildings grants a planned town the
  good's real specialization charter (18 goods; iron its rights) and swaps charter for rights by revoke + grant
  (`pp_cplan_country_plan_rights`), at the normal influence prices.
- Engine (static analysis of 1.4.9; behaviour only, internals stay private; for the real charters): a script grant
  skips every check and can stack duplicates (every grant is guarded); every held right counts against the slots; a
  rank change revokes the newest rights above the slot count; every script grant / revoke sends the game's town rights
  message. For the plans (in game 2026-11-21): `on_location_changed_owner` fires for `create_country_from_location`
  and `change_location_owner` with `scope:loser`; a saved right whose type is gone loads typeless, only
  `revoke_town_rights = this` inside `every_town_rights_in_Location` removes it.
- Limits: one charter per town; a two-steps-old tier upgrades only while the middle tier can still be built; plans are
  lost on every owner change (peace deal and annexation not tested); several plans in one location take turns by
  default (setting "best payback first").
  `docs/location_plan.md` (the feature), `docs/location_profiles.md` (the engine's internal names),
  `docs/construction_plan_country.md` "Plans: charters and rights".
- Tested in game 2026-11-20, plans still town rights (plan test world, Castile, two years; `docs/location_plan.md`
  "Tested in game (2026-11-20)"): grants on rural locations, the button and the Plans row, builds, the rank raise with the plans surviving it, a charter granted
  to a planned new town. Charter to rights, an owner change and a tier upgrade: tested in the third round (below). The game's town rights messages
  (`TOWN_RIGHTS_GRANTED` / `_REVOKED`) are redefined without the pop-up in `main_menu/gui/messagetypes/pp_messagetypes.txt`
  (a mod file may redefine a vanilla message type; verified in game). While the Construction Plan is off, the Location
  Plan window says so and carries the switch.
- Plans free their workers (2026-11-20, Jan; plan setting, default on, `pp_tplan_free_off` = off; not tested in game as
  a rule): where a plan's next level waits for workers and nothing else in a look, the location's turn closes ONE other
  business of the player's there (open, producing, staffed, unsubsidised, no plan of the location wants it, no
  logistics / improvement / public building, its workers peasants or the level's pop type, food makers only while the
  province's store is not short, never a type the player reopened by hand), least profit per worker first, then waits
  a look; the plan's state is 14. Script cannot close a building: the building goes on a country list and the hidden
  scripted widget `gui/pp_plan_closer.gui` closes it with the game's own GUI function, a scripted GUI handshake takes it
  off (mechanism proven in game 2026-11-20). Taking the plan off or the setting off reopens them; the lists are emptied
  every month. `plan_closer.py` (generated lists), `pp_plan_closer.txt` (hand-written), `docs/location_plan.md` "Plans
  free their workers", `tests/test_plan_closer.py`. Closed buildings no longer count as open jobs in the free-worker
  count (`pp_cplan_free_peasants_here`).
- Third round (2026-11-20 morning, Jan: test the untested paths, think the cases through; 8bd92898 + results commit,
  all tested in game, `docs/location_plan.md` "Third round" and "Cases thought through"):
  - Tested and working: charter to rights (the script revoke in the swap is free), a tier upgrade, an owner change
    (plans gone, the rule's closings reopened by the game, a real charter kept), a building opened again by hand.
  - Food plan: farms first (the staple farm with the best return here, `pp_cplan_farm_roi_<type>`), kitchens only
    where the farms have nothing to do, a Tavern only while the province's store is short (`pp_tplan_do_food`). Trade
    plan: `[construction_plan] trade_plan` (Marketplace line, Port Authority, market centre buildings), in start order.
    A plan whose standing buildings are full starts another of its buildings. "Never at a loss" only for buildings
    that make a good.
  - A town's specialization follows its plans (another specialization makes way once the planned line is the bigger
    one and that good has no plan there; revoke and grant in one step; `pp_tplan_cwait` = why a charter waits, shown in
    the plan's tooltip). Taking a plan off keeps its charter.
  - Plans come first for their location's workers: the Businesses rule builds nothing where a plan waits for workers
    (`pp_lplan_wk`) or a closing is under way (`pp_pclose_wait`); both checks sit in `pp_cplan_business_site` and the
    Businesses look's limit.
  - Two more plan settings: "Other businesses in planned locations" (`pp_tplan_alone`), "Grant a plan's charter and
    rights" (`pp_tplan_rights_off`). Taking the last plan off a location drops the group's saving for it; switching
    the Construction Plan off opens every building the plans closed.
- Fourth round (2026-11-20 afternoon, Jan: how does it scale, feedback for the money sliders; tested in game,
  `docs/player_construction_manager.md` "Feedback for the money sliders" and "The look runs in daily slices"):
  - The Locations look runs in daily slices (`[construction_plan] look_slice_min` 60, `look_slice_days` 24; hidden
    event `pp_construction_plan.1`): every planned location is walked within the look's month, so the group counts
    again what all its plans are missing. A turn that begins while the group already saves only sets states and counts
    gold (no start, no closing, no worker mark).
  - Forecast numbers per rule group (`construction_plan_forecast.py`: gold coming in, what the group lacks, its years,
    the weight it would need, one step up and down, its situation by look). The window reads them as kept country
    variables (`pp_cplan_forecast_store`); never put a formula that walks or re-derives the weights behind a value the
    window shows every frame (it cost 4 s of script time in 12 s, measured).
  - The window (`construction_plan_status.py`): a white bar under each gold weight bar (what the group asks for), a
    status line under each row, step tooltips on - and +, one line for the whole plan, and in each cog pane the
    status, a second chart (the situation over the last twelve looks) and a pane that scrolls as a whole.
  - Test pitfall: a console `tick_day` over a look and the next month's start gives the hidden widget no frame, so
    the closings of that look never happen and their types land on the keep list. Stop a tick right after a look.
- Fifth round (2026-11-20 evening, Jan: no scrolling, more plan options, a real budget; NOT tested in game;
  `docs/player_construction_manager.md` "Wide window and monthly budget", `docs/location_plan.md` "Plan options"):
  - The window is 1360 x 820 and nothing scrolls except the two lists of what was built: Global Settings in two
    columns (settings left, pane right), Towns and Buildings in two columns, Plans with all icons at once. Each tab
    module has a test that sums its fixed heights against the body: keep it true when adding rows.
  - Monthly budget under the gold reserve (`pp_cplan_budget`, `pp_cplan_purse_share`): at most that much new gold is
    shared out a pass; 0 = no limit.
  - Plan options are data: add one to `town_plan_options.OPTIONS` (the window renders it by its kind and `where`),
    implement its value and scripted GUI in `town_plans.py`, default = no variable set = no cost in the look. Plan
    states 15 (production efficiency below the line) and 16 (held back by the plan's options).

## Release Checklist

- Treat an explicit request to create or publish a release as authorization for the one final guarded live sync required by this checklist. Confirm the exact `constructor.local.toml` deploy target before running it.
- Do not publish or finalize a GitHub release until every step below is complete:
  1. Confirm the release scope, mod version, supported EU5 version, target branch, and tag. Preserve unrelated or intentionally unpublished working-tree changes.
  2. Run the normal pre-release validation, including `uv run ppc blueprint parity`, constructor validation, and the full `uv run ppc test` suite. Resolve every unexpected failure before continuing.
  3. Merge and push the exact release commit, confirm `main` is clean, then run `uv run ppc sync --yes` against the confirmed live target.
  4. Verify release-critical deployed files match the repository output byte-for-byte and run the final relevant tests after sync when the sync/build path could have changed tracked output.
  5. Inspect recent GitHub releases with `gh release list` and `gh release view <previous-tag>` before drafting notes, so the title and writing style remain consistent.
  6. Write short patch notes about player-facing mod changes only. Exclude constructor, parser, test, CI, and other tooling changes unless the user explicitly asks to mention them. The release zip's top folder is the live name `Prosper or Perish (Population Growth & Food Rework)`, not the repo's `mod/pp`: the release text tells players to copy that folder.
  7. Create or update the release, then verify its tag, target commit, title, body, publication state, and URL. If a release was published before its final sync, complete the sync and explicitly re-verify or adjust the release before reporting completion.

## Localization

- Localization is player-facing in-game text, not implementation notes or a restatement of user instructions.
- Do not hardcode balance values in localization when a modifier, scripted value, building tooltip, or generated modifier effect can display the current value.
- Explain what the player should understand and where to inspect effects; let modifiers carry exact changing numbers.
- When a linked modifier or concept tooltip already displays food-storage modifier effects, do not restate those values in Europedia prose.
- Player-facing names of the population capacity (Jan, 2026-10-10): **Arable Land** (the total: what a location's land
  can feed, in people; farms take from it, improvements add to it); its states **Abundant Arable Land**
  (`abundant_free_land`), **Available Arable Land** (`available_free_land`), **Overused Arable Land** (`overpopulation`);
  the location's own land (World Builder baseline, the land panel's tooltip row) is **Natural Arable Land**, one concept
  (`pp_location_potential`, hand-kept; "Location's Land" merged into it 2026-10-28). Engine and script keys stay. Link
  Arable Land in text with `[population_capacity|e]` (vanilla concept, no prefix; its description, in
  `localization/replace`, is also the Arable Land card's lead). "Farmland" (as a capacity term), "Free Land",
  "Overpopulation" and "Settled Land" are retired; `tests/test_europedia_style.py` fails if they come back. State icons:
  `tools/build_arable_land_icons.py`.
- The location view's land panel (`arable_land_bar.py`, names 2026-10-28, Jan): the top bar is the **Land Usage**
  (`[Concept('population', 'Land Usage')|E]`) = **Urban Land** (`pp_townsfolk`: everyone but the subsistence
  peasants; brings its own capacity) + **Subsistence Land** (the static modifier `pp_subsistence_land`, no concept:
  its name and `STATIC_MODIFIER_DESC_` are the text, links are `[ShowModifier('pp_subsistence_land')]`); the bottom bar
  the **Land Capacity** (`[Concept('population_capacity', 'Land Capacity')|E]`)
  = Urban Land + **Free Arable Land**, then past its end **Farm Land Usage** (`pp_farm_land`) and **Unimproved Land**
  (links Land Improvements). The land states' one-line definitions (`PP_LAND_CHIP_*`, chip and tooltip) read Land Usage
  against Land Capacity. The legend is one unwrapped line: keep it within the panel's 546 px (game font, 12 px).
- One thing, one entry, one text (Jan, 2026-10-28): the text sits on the game object (a good's or building's `_desc`,
  `STATIC_MODIFIER_DESC_`, a situation's `_desc`, a vanilla concept's desc in `localization/replace`) and links open
  the object; never a "P&P:" concept beside it. A Europedia card shows its object's own name and text
  (`docs/mod_authoring_rules.md`, "Concept files and entries").
- Europedia cards use the card style in `in_game/gui/shared/pp_europedia_style.gui` (banner, lead, sections with flows,
  scales and goods rows; rules in `docs/mod_authoring_rules.md`, first card Variable
  Harvests, 2026-10-09). Their text has no numbers at all: values sit behind concept, modifier and goods links.
- Use plain text in situation panes and generated static-modifier descriptions unless that target UI is verified to support inline concept links; unsupported formatter tags spam `error.log`.
- Situation panels: the game opens `gui/panels/situation/<situation key>.gui` when a situation is clicked. The Variable
  Harvests panel (`in_game/gui/panels/situation/harvest_situation.gui`, 2026-10-10, not yet seen in game) is vanilla's
  `situation_panel` with `situation_card_common` sections; its texts (`PP_HARVEST_SIT_*`, pp_situations_l_english.yml)
  sit in its own `text_multi` widgets like the Europedia cards and carry links. The situation's tooltip texts
  (`harvest_situation_desc` / `_monthly`), its map tooltip and its legend stay plain. Picture and icon:
  `tools/build_harvest_situation_art.py`; tests: `tests/test_variable_harvest_situation_panel.py`.
  The welcome panel (`pp_mod_welcome_situation.gui`, 2026-10-10, not yet seen in game) is an introduction
  (`PP_WELCOME_SIT_*`) and one button that opens the Europedia on its Prosper or Perish section
  (`OpenLateralView('encyclopedia')` + the variables `pp_encyclopedia_active` = yes, `pp_filter` = all); the situation
  never ends, the player closes it. Picture from the same tool; tests: `tests/test_welcome_situation_panel.py`.
- Internal goods (2026-10-14, Jan): `offset`, `logistics`, `local_food` (Province Food) and `province_food_sales` are
  hidden from the market's goods lists, the goods ledger, the markets ledger's surplus/demand icons, the market
  tooltip's Greatest Local Surplus/Deficits and the trade-order goods picker (view only; goods tooltips, building
  panels and methods still show them). The list is `INTERNAL_GOODS` in `tools/port_vanilla_gui.py`, which writes the
  template `pp_hide_internal_goods` and the tooltip table column `pp_GoodsMarketTableColumn` (`in_game/gui/shared/
  pp_internal_goods.gui`, the column built from vanilla's `TooltipTableColumn`) and the five vanilla files (goods rows
  as `vbox`, icon rows as `dynamicgridbox` with `ignoreinvisible`, tables five rows high in a scroll box over the first
  nine, so hidden goods leave no gap and top-five lists keep five); a new internal good goes into that tuple, then
  rerun the tool.
  Tests: `tests/test_internal_goods_gui.py`.
- Research time in the advance tree (2026-11-25, Jan: "you should see straight when you look at it how long each
  research takes ... in years ... maybe with colours"; "in the space of the advancement thing ... not dangling around
  ... write years out ... classy as it did before"; "somewhere at the top, where it can't be hidden" by a card whose
  effect rows scroll; tested in game as Scotland, new game): every advance a country has not researched carries a
  small badge in its card's upper right corner, beside the medallion: the years it takes at the country's present
  research (cost / (12 x `research_speed` x (1 + `research_speed_modifier`))) over the word "years", in the titles'
  lettering (header font, italic) on a faint dark plate; the number is green under 3 years, gold to 6, red from 6
  (`ADVANCE_TIME_FAST_YEARS` / `_SLOW_YEARS`, size and place `ADVANCE_TIME_BADGE*` in `tools/port_vanilla_gui.py`; the
  text formats `pp_advance_time_*` and the templates are `shared/pp_advance_time.gui`). `port_technology_view` adds
  `using` lines (marker `### PP: research time`) to vanilla `technology_lateralview.gui`: for the card as the last
  child of the card's button (`# button not in progress`) and of each of its six `#unlock` artwork widgets, for the
  round icon (far zoom, not seen in game) as the last child of its button. Port again after a game update (`--check`
  must report none). Draw order found in game: the card's own container is at the bottom, its button (the effect
  rows) above it, the unlock artwork above the button, and a widget added to the node itself ends up behind all of
  them; so the badge rides in the button and in every artwork widget, at the same spot. The cost comes from two
  global variable maps keyed by the advance (`pp_advance_cost`, `pp_advance_cost_past`), written at game start by
  `advance_research_cost.py` (`ppc advance-cost apply|check`, finalize step after the ladder) from the advances and the
  four research cost defines; the GUI picks the past-age cost by `Advance.HasResearchCostDiscount` (not seen in game
  past 1342 yet). Engine facts: the GUI's `Advance.GetResearchCost` is the cost factor cut to a whole number (1 for
  25 points), there is no number for the real cost; one global variable per advance made the game log "set but never
  used" with four suggestions each (36,000 lines at load), a map the on_action reads itself does not. Card size: the
  tree lays its nodes on a fixed grid, so a card that grew with its unlocks would cover the lines and the row below
  (not done). A save older than the pass has no maps and shows no badge. Tests: `tests/test_advance_time_gui.py`.
- Construction Plan tab (2026-11-20, Jan: the opener docked under the top-left tab row stuck out): the mod carries
  vanilla `panels/left_panel/left_panel.gui` plus one `button_panel_tab_alt` at the end of the `tabs_buttons` row
  (marker `### PP: Construction Plan tab`, game icon `flat_icons/mass_construct.dds`) that toggles `pp_cplan_open`
  and places the Towns and Buildings tiles; hidden for observers. Last in the row because vanilla's hbox has no
  `ignoreinvisible`, so a hidden tab keeps its room at the row's end. `port_left_panel` in `tools/port_vanilla_gui.py`
  inserts it after the decisions tab; port it again after a game update (`--check` must report none). A broken copy
  breaks the whole top-left HUD. Tests: `tests/test_plan_opener.py`.
- Build panel (2026-10-17, Jan; panel 990 wide, rows a fixed 930): the vanilla location row (slot circles and every method's efficiency,
  two per column) plus one value per column: build cost (sorts by the engine's `cost` key, which vanilla never
  shows), payback (build cost / monthly profit per level, in years, Construction Manager's ROI by profit; the tooltip
  also gives it by tax income), profit and tax income (template `pp_build_location_values`). The engine sorts only by
  its own keys, so the header's payback button (GUI variable `pp_build_payback_order`) draws the same vanilla rows
  once per payback band (`BUILD_PAYBACK_BANDS`), each built only in its band (`DataModelRepeatedItem` of 1 or 0);
  inside a band the last sort holds, and every sort button switches the payback order off. Never a vbox in the list
  area: it stretched to the panel and spread the spare height between the rows, and with an `expand` its layout did
  not converge and the panel lagged (error.log, in game 2026-10-17); the selected sort is vanilla's fixedgridbox, the
  bands vertical flowcontainers (size to content). **`GetBuildOrExpandBuildingCost` is slow** (measured in game
  2026-10-17 with `measure_frame_time` and hot-swapped GUI variants: band tests calling it every frame took the panel
  from 33 to 65 ms per frame on a ~40-location list; the profit call and the band widgets cost nothing): never call it
  per band per frame. Each location records its band once into the GUI variable `pp_pb_<building name><location key>`
  (a recorder created hidden, `visible_at_creation = no`, whose `_show` state runs when the payback order opens or the
  location's construction count changes); the bands only read the variables (33 ms = the frame cap). Bands: one per
  whole year below 10, then 10+ and no profit, then "not recorded yet".
  The location view ("Production in <location>", 2026-10-17, not yet seen in game) has the same layout, value columns
  and payback order: its rows are pp_ copies of vanilla's `location_filtered_header_with_candidate` /
  `_no_candidate` (production_lateralview.gui, re-declared by CMF) in `shared/pp_location_building_rows.gui`
  (`port_location_rows`), built rows fed by the candidate's LocationToBuildItem, unbuilt rows by template
  `pp_location_values_unbuilt`; each row records its own band (same variable as the build panel); no `cost` sort key
  assumed there (a header label instead). The building window's header row (`building_view.gui`, `port_building_view`)
  also shows slots and efficiencies two per column, window 760 wide: vanilla's 50-high row squeezed a three-slot
  building's checkbox column so auto expand could not be clicked (Jan, 2026-10-17). All in `port_build_location` (`tools/port_vanilla_gui.py`); tests:
  `tests/test_build_location_gui.py`.
- Situation map legends should use mod-owned plain localization keys, not inherited or generic `LEGEND_KEY_*` keys, because legend UI is sensitive to formatter syntax.
- In GUI files, do not put `#` formatter markers in `default_format` style names; use the raw style key such as `yellow_titles`.
  Exception found 2026-10-10: EU5 1.4 vanilla writes `default_format = "#yellow_titles"` (382 times, never bare), and the
  Europedia style types' bare `yellow_titles` titles drew magenta in game, so `pp_europedia_style.gui` uses the `#` form.
  The card headers in `encyclopedia_lateralview.gui` still use the bare form (enforced by a test); check them in game
  before changing that.

## Workers per level and estates (2026-10-03, Jan)

- `[building_scaling.employment_cut]` in constructor.toml: at finalize (after the footprint) every mod-defined
  building of a listed pop type whose `employment_size` is the reference gets the new size (laborers 1.0 -> 0.8,
  burghers 0.3 -> 0.25; peasants untouched). The line records `# [building_scaling.employment_cut] reference X`, which
  `building_footprint._employment` reads back, so population capacity stays at the reference and a second finalize
  changes nothing. Blueprints, the blueprint evaluation and the labour/gate tools keep the reference; output and profit
  per level are unchanged. In towns the AI's per-capita factor is 0.3 / employment_size, so cut buildings score higher.
- Crop farms are open to estates (`forbidden_for_estates = no` in config/crop_farms.toml); Cookshops and Public
  Kitchens already were. `ESTATE_MAX_PRICE_MULTIPLIER` = 2.0 (a plain multiplier on what an estate pays for its own
  builds, not a cap; was 1.2). Tests: tests/test_employment_cut.py.

## Slower Economy and Growth Set (2026-11-28, Jan, after run bd7d9616; not tested in game)

- Jan: growth after the Black Death is still too fast and the AI catches up too quickly. Three existing numbers:
  - **Building prices +15 %**: `[tier_lines] price_factor` 1.30 -> 1.50. Every gold price follows: the tier lines
    (`prices/pp_tier_line_prices.txt`) and `prices/zz_pp_building_price_stockpile.txt` (old value x 1.5 x 1.50, in
    steps of 5; rewritten by hand from its comments, `tests/test_tier_lines.py` checks every row). First-age price
    115 (100), merchant house steps 1,845 / 5,535 / 9,225 / 12,915 (1,600 / ...), Hansa buildings 1,155 (1,000).
  - **RGO output**: `country_base_values` `global_raw_material_output` -0.65 -> -0.75. Additive: with serfdom's net
    +0.1 the start's RGOs yield about 0.30 of full (0.40 before, a quarter less). Colonial nations +0.7 -> +0.5 (3x
    a normal RGO stays), start planner lumber per RGO 0.42 -> 0.32, `start_market_stock.csv` `rgo_factor` x 0.75 by
    hand until `ppc start-stock calibrate` runs on a new day-0 save. Run bd7d9616 used 63 % of the raw goods it made
    in 1342 and 86 % in 1402, with 84 and 74 months of stock.
  - **Subsistence**: back at 1.21 since the evening of 2026-11-28 (Jan, after run 2ae8dd7a: at 1.10 South Asia grew
    0.23 %/yr after the plague instead of 0.39 and East Asia 0.19 instead of 0.29, while Western Europe was back at its
    1342 level in 1417 instead of 1412; the world ended at 931 M instead of 1,148 M). What follows is the 1.10 state the
    run had: `NLocation.SUBSISTENCE_AGRICULTURE` 1.21 -> 1.10. Start model: world food supply +8.3 % ->
    +4.7 % over demand; provinces short before the start buildings 1,692 -> 1,801 (shortfall 26.5k -> 32.6k a month);
    validator over 96 months: world +2.5 % -> +2.0 %, 13 food pools collapse (14), 2,408 pinned at the storage cap
    (2,496), 867 starve at some point.
- Risks told to Jan before he decided: the subsistence cut is uniform, so Delhi, Gujarat and North China (pools that
  starve at times already) feel it first while half the people live on full stores; fur (15-22 % unmet), tea, horses,
  fruit and wine are short already; the early tax base was already 6-17 % below earlier runs until 1650.
- Next run: starving pools by region in the first century, years to regain the pre-plague level (world 1397, Europe
  1412 in bd7d9616), tax base and building investment by 1500, fur and tea.
