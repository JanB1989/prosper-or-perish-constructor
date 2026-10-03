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
  without a market good, gates on a store-following good (the Grange's Surplus Sales, the Tavern's and Cookshop's
  Province Food) and `strategic_goods` get none. Never gate on a method that
  buys the building's own main good (inverts the AI's price response), except a token amount:
- Crop farms (farm v3, 2026-10-02): Provision takes a token of the crop (`crop_provision_input_gold` in
  `[building_scaling]`) and makes a fixed Province Food amount per level, so it is the farm's gate (margin about 15 at
  base prices, open at any realistic crop price) and the farms have no Market leg. The AI's price response is the
  farm's `ai_construct_weight` (`[general.ai_construct_weight]` in `config/crop_farms.toml`: slope x ((1 + local crop
  output modifier) x market price / default price - 1) / (owner monthly income + offset); EU5 1.4 adds it raw at the
  end of the build score, after the gate). Fisheries, orchards and forest villages keep the buy-back Provision and
  their Market leg.
- A slot's first method is what new and game-start buildings run, so reordering can change defaults.

## Store Lever

- The province store moves goods output through two province modifiers (`stored_food.py`, `[stored_food]` in
  constructor.toml): **Low Stores** (size = years below 12 stored months) and **Full Stores** (size = years above).
  They carry the Province Food output (+ below, - above) and the Grange's Surplus Sales (+ above, steeply - below);
  the staple output line is 0 since farm v3 (the farms' price weight reads the crop output modifier as land quality).
  Stored Food keeps growth and prosperity.
  There are no country base values for the store: at 12 months every line is zero.
- Every maker of Province Food stops where its recipe stops paying, so the store rests there: the farms' Provisioning
  always runs (one method, no Sell the Surplus), the Cookshop follows its staple prices, the Tavern the victuals
  price (Serve Victuals is its only slot and its gate). Tavern and Cookshop must stay on the Province Food good: as
  flat food they would be pure price switches.
- The Grange is off since 2026-10-03 (`grange_max_level` 0: config/victuals_logistics.json `maximum` 0); its type,
  blueprint and Surplus Sales lines stay so `store_lever.load_design` and old saves keep working. Low Stores cuts
  victuals output (-1.0 per year short), so the harbour Victualling Yard stops packing below about 10 months and its
  Market gate closes there; `province_starving` zeroes victuals output.
- Farm Produce (`[stored_food.farm_produce]`): Cookshop and Public Kitchen locations get +Province Food output scaled by
  the province's worked farm levels (`local_pp_farm_levels`, script value `pp_province_farm_levels`); the store refresh
  renews it every January, so it adds no pulse. The start simulation counts placed farm levels for the Cookshop cap.
- `store_lever.load_design` reads the numbers from the config, the two blueprints and `province_starving`; the
  start-food validator (`worldbuilder/food_sim.py`), `tools/province_store_sim.py` (rest points and ripple on real
  provinces) and `tests/test_store_lever.py` (the properties the design rests on) all use it. After changing a value
  run the simulator and the tests.
- Production efficiency adds to the same pool as these output modifiers, so it moves every rest point (about 1.6
  months per +10 %). Smaller slopes make that worse; keep it in mind before flattening the lever.

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
  `uv run ppc logistics check` must report 0 off, 0 problems; `ppc build` prints it and `tests/test_logistics.py`
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
