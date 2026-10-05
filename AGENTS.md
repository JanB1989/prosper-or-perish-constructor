# Prosper or Perish Constructor

## Repository Workflow

- Use `uv run ppc --help` as the canonical command index before running project workflows.
- Prefer `uv run ppc test`, `uv run ppc inspect`, `uv run ppc analyze`, and `uv run ppc blueprint ...` over raw `eu5-orchestrator` commands unless debugging the wrapper itself.
- Use parser/evaluator commands for game-data and blueprint questions instead of text-searching generated mod files.
- Treat `uv run ppc sync --yes` as a live deploy action. Do not run it unless the user explicitly asks to mirror into the live Paradox mod folder.
- The constructor output mod root is `mod/Prosper or Perish (Population Growth & Food Rework)` under this repo, shown from Windows as `\\wsl$\Ubuntu\home\jan\development\ProsperOrPerishConstructor\mod\Prosper or Perish (Population Growth & Food Rework)`.
- `uv run ppc sync --yes` first makes sure that repo-local output mod root is built/current, then copies that output to the configured live Paradox mod folder. Work either edits files directly in this repo-local output root, or edits source/config/blueprints that compile into that output root before sync copies it onward.
- Do not look for or use a nested `Constructor/mod/...` path in this checkout; the repo-local compiled mod path is `mod/...`.
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
  buildings that sell only for `offset` (the Cookshop line) and `strategic_goods` get none. Never gate on a method that
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
- A slot's first method is what new and game-start buildings run, so reordering can change defaults.

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
  wild_game -0.14, wool -0.23; `staple_per_province_food_by_good`, the same food-for-goods balance, recomputed from the
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
- The Grange packs a full store and answers the victuals price steeply (2026-10-03 evening; d3091976 had
  37.88 - 5.29 x price): a working Grange breaks even at 63.53 - 13.85 x victuals price stored months (22 at 3.0,
  because Full Stores stops growing at 24; 15 at 3.5; about 12 from 3.75 up, the pivot; never below 2.86). Full Stores
  gives Surplus Sales +0.13 per year (was 0.34), Surplus Sales offset 3.83 (gate opens at 12.5 months), Haulage offset
  2.323. Its `ai_construct_weight` vetoes (flat) a new Grange below that line + 1 month at today's price (never below
  13) and where the province does not gain food each month (`pp_location_province_food_balance`);
  `tests/test_store_lever.py` ties the weight's numbers to the design. Why: in Mini World run 5 the dear-victuals
  markets sat at 14-19 stored months, above the farms' store bonus (below 14) and below the old Grange line, so no
  building answered the price. No Granges at game start (`grange_at_start = false`).
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
  population or rank levels; the `allow` town-or-province-capital rule stays. Small recipes (dish about 0.45 gold of staples + labour at margin
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
  fish, wild_game, wool; wool stands for sheep, which were eaten) and staple fruits (fruit, olives). The source is the
  `staple_group` column of `config/goods_categories.csv` (`crops` / `animals` / `fruits`, empty otherwise), read by
  `staple_foods.py`; category and subcategory stay as they are (production and RGO expansion cost). Nothing keeps a
  list of its own.
- Readers: the store curve (every staple food), `[logistics] bulky_staples` (one share per staple food; `ppc logistics
  check` reports a missing one), the crop allocation's staple crops (`grains` is gone), the Cookshop cap counters and
  the employment tag `pp_staple_food_priority`, Seasonal Harvests (`[exempt] staple_groups = ["animals"]` in
  variable_harvests.toml: the harvests leave the staple animals alone; the generator's input file is gone, so the
  generated modifiers were trimmed by hand), the Colonial Nation output bonus (every raw good but the staple foods).
- Every building that makes a staple food runs Provisioning (`provisioning.py`): the flocks since 2026-10-04 (Provision
  with Mutton, buying their wool back at 2.5) and the Maghreb palm groves and the English royal forest at reference
  size (one-level specials without a base slot). `tests/test_staple_foods.py` pins the list, the makers (Provision,
  tag, counters), the curve factors, the bulk shares, the Yard's salt beef and the Cookshop cap's Yard term.
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
  below `gate_max_market_access` as a share of it, and makes it every logistics building's flat `ai_construct_weight`
  (no income divide, like the food urgency; 70 levels at 0.20 -> 92, max 120). Edits to logistics.py rerun the start
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

## Building Shutdown (2026-10-05, Jan)

- Buildings without goods output may not be closed unless they are military. `[building_shutdown.classes]` in
  constructor.toml maps every footprint class to `never` or `keep` (keep: barracks, fortification, military_grounds,
  farm_land, technical); a blueprint overrides with a top-level `shutdown: never | keep` (the Kurultai is `never`).
- The finalize step of `ppc build`/`sync` (`building_shutdown.py`, after the footprint) writes `can_close = no` (the
  player) and `ai_forbid_shutdown = yes` (the AI's maintenance-budget and profit closing) into the block that owns each
  `never` building, marked `# building_shutdown`; a building switched to `keep` loses them again. Buildings with a goods
  output are skipped (a losing producer must stay closable). An INJECT never repeats a flag vanilla already sets.
  `uv run ppc shutdown apply|check` (0 problems; `tests/test_building_shutdown.py`). 306 buildings locked.
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
- Farm max levels speak in levels of that farm (`scripts/generate_rural_capacity_values.py`): "[Farmland] for this
  farm" (free farmland, floored as before, plus the land all farms here use) minus "Used by other farms" (that land
  less this farm's own and replaceable lower-tier levels); the difference is the old cap exactly. Every land farm
  records its land per level as `raw_modifier local_pp_farmland_used` (`crop_farms.py` and worldbuilder
  `patch_farm_blueprints`), shown as "Farmland Used"; the Farmland concept (`pp_farmland`) explains it on hover.

## Release Checklist

- Treat an explicit request to create or publish a release as authorization for the one final guarded live sync required by this checklist. Confirm the exact `constructor.local.toml` deploy target before running it.
- Do not publish or finalize a GitHub release until every step below is complete:
  1. Confirm the release scope, mod version, supported EU5 version, target branch, and tag. Preserve unrelated or intentionally unpublished working-tree changes.
  2. Run the normal pre-release validation, including `uv run ppc blueprint parity`, constructor validation, and the full `uv run ppc test` suite. Resolve every unexpected failure before continuing.
  3. Merge and push the exact release commit, confirm `main` is clean, then run `uv run ppc sync --yes` against the confirmed live target.
  4. Verify release-critical deployed files match the repository output byte-for-byte and run the final relevant tests after sync when the sync/build path could have changed tracked output.
  5. Inspect recent GitHub releases with `gh release list` and `gh release view <previous-tag>` before drafting notes, so the title and writing style remain consistent.
  6. Write short patch notes about player-facing mod changes only. Exclude constructor, parser, test, CI, and other tooling changes unless the user explicitly asks to mention them.
  7. Create or update the release, then verify its tag, target commit, title, body, publication state, and URL. If a release was published before its final sync, complete the sync and explicitly re-verify or adjust the release before reporting completion.

## Localization

- Localization is player-facing in-game text, not implementation notes or a restatement of user instructions.
- Do not hardcode balance values in localization when a modifier, scripted value, building tooltip, or generated modifier effect can display the current value.
- Explain what the player should understand and where to inspect effects; let modifiers carry exact changing numbers.
- When a linked modifier or concept tooltip already displays food-storage modifier effects, do not restate those values in Europedia prose.
- Use plain text in situation panes and generated static-modifier descriptions unless that target UI is verified to support inline concept links; unsupported formatter tags spam `error.log`.
- Situation map legends should use mod-owned plain localization keys, not inherited or generic `LEGEND_KEY_*` keys, because legend UI is sensitive to formatter syntax.
- In GUI files, do not put `#` formatter markers in `default_format` style names; use the raw style key such as `yellow_titles`.

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
