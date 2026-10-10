# In-game Documentation Rules

Instructions for Cursor when editing game concept definitions or the Europedia.
# Prosper or Perish (Population Growth & Food Rework)\in_game\gui\encyclopedia_lateralview.gui
# Localization is usually here main_menu/localization/english/pp_europedia_l_english.yml
## Localization guidance

- When a linked modifier or concept tooltip already displays food-storage modifier effects, do not restate those values in Europedia prose.
- Explain what the player should understand and where to inspect effects; let modifiers carry exact changing numbers.
- No numbers in the text at all (Jan, 2026-10-09). A number the player needs sits behind a blue link: a concept
  (`[concept|e]`), a modifier (`[ShowModifier('key')]`, its tooltip lists the live effects), a good, building or pop
  type (`[ShowGoodsName('x')|e]`, `[ShowPopTypeName('x')]`). Dates and structure ("each September") are fine.

## Card style (2026-10-09; first card: Variable Harvests)

The types live in `in_game/gui/shared/pp_europedia_style.gui`; a card is the usual header tab, then:

1. `pp_eu_banner` - an edge-to-edge picture, 2900 x 500 DDS shown at 1450 x 250. Every banner is a painting of the
   page's topic in the style of the game's loading screens: people doing the thing the page explains, each card its
   own culture and scene (Jan, 2026-10-10: no stitched landscapes; a landscape says nothing about labor). The
   paintings are in the constructor's `assets/europedia_paintings/` (its README has the brief they were painted from,
   by Codex's image generation with the loading screens as style references); `tools/build_europedia_banners.py`
   cuts each card's strip (the start row is set per painting so faces stay in frame) and writes the DDS.
   Override `blockoverride "banner_texture"` with the card's banner.
2. `pp_eu_lead` - one short paragraph in the flavour type: what the mechanic is, in plain words. It is also the
   concept's own tooltip text, so it must read well alone. It is the first text of the card (the web export starts there).
3. Optional live line (`visible = "[GetPlayer.IsValid]"`): the mechanic in the player's own game, e.g. the capital's
   harvest medallion. The web export leaves texts that read `GetPlayer` out.
4. Sections: `pp_eu_section` heading (icon + gold title + fading rule), then any of
   - `pp_eu_text` body text;
   - a flow: an hbox (`margin = { 40 0 } spacing = 8`) of up to four `pp_eu_step` with `pp_eu_arrow` between;
   - a scale: an hbox (`spacing = 10`) of up to seven `pp_eu_scale_step`, worst to best, each a medallion and a
     concept link whose tooltip holds the details;
   - goods rows: `pp_eu_goods_row` with a two-line label (`#T name#!\nverdict`) and `pp_eu_item`s (ten to a line; a
     longer row wraps into a vbox of hbox lines; alpha 0.55 on the icon for goods the mechanic leaves alone);
   - a comparison: an hbox (`margin = { 40 0 }`) of two `pp_eu_panel` (items, title, text) with a `pp_eu_sign`
     ("or", "+") or a two-way arrow between them, e.g. store running low vs store full;
   - an equation: `pp_eu_step`s with `pp_eu_sign` "–" and "=" between, e.g. grows – eats = surplus;
   - a list: a vbox (`margin = { 40 0 } spacing = 8`) of `pp_eu_entry` (up to three items) or `pp_eu_entry_wide`
     (four), each a fixed icon column (a small input -> building -> output flow of `pp_eu_item` and
     `pp_eu_item_arrow`, or a row of buildings) next to a title and text.
   **Every icon carries a hoverable game link** (Jan, 2026-10-10: the blue or golden text players know they can
   hover, not an icon with a plain tooltip): a `pp_eu_item` shows its link under the icon (`item_link`), a
   `pp_eu_step` under its icon (`step_link` with a `pp_eu_link`), a scale step in its label. Link the real thing:
   `[ShowGoodsName('x')|e]`, `[ShowBuildingTypeName('x')|e]`, `[ShowPopTypeName('x')]`, the terrain names
   (`ShowTopographyName`, `ShowVegetationName`, `ShowClimateName`), `[ShowModifier('x')]` for a state the game
   applies as a modifier (its tooltip lists the live effects), else a concept. Only the header, banner, section
   headings, arrows and the live line stand without one; the test enforces it.
5. Section order that reads well: what happens (flow) -> how strong (scale) -> what it touches -> where to see it in
   game. Keep a card on its own mechanic; the neighbouring mechanics get a link in the text, not a section of their
   own (Jan dropped the harvest card's "Where It Leads" flow, 2026-10-09).
6. Cards need not look alike (Jan, 2026-10-10): banner, lead and section headings stay, the rest is whatever explains
   the mechanic best (Food: comparisons; Food Production: an equation and a building list). Concise wins.

Use the mod's own visual language where one exists (harvest medallions = the location view's harvest chip frames).
`tests/test_europedia_style.py` checks textures, keys, links, data functions, that every icon carries a link, that
banners differ and that the text has no numbers; add a new card to its CARDS when it adopts the style.

## Concept display order

When editing the Europedia GUI or concept definitions, preserve this order:

1. All (done)
2. Getting Started
3. F.A.Q.
4. Update 0.9
5. Overview (done)
6. Food (was Food in EU5; card style)
7. Food Production (card style)
8. Food Consumption (card style)
9. New Trade Goods (card style)
10. Logistics (Market Access) (was Building Limits; card style)
11. Rural Capacities (was Building Capacity; card style)
12. Labor (card style)
13. Variable Harvests (done)
14. Arable Land (was Population Capacity)
15. Population Growth (card style)
16. Other Changes

More concepts may be added later.

## File naming

Each Europedia card has exactly one game concept file. Filename = card name (snake_case, pp_ prefix):

| # | Card | File |
|---|------|------|
| 1 | All | (filter only) |
| 2 | Getting Started | pp_getting_started.txt |
| 3 | F.A.Q. | pp_faq.txt |
| 4 | Update 0.9 | pp_update_0_9.txt |
| 5 | Overview | pp_overview.txt |
| 6 | Food | pp_food_in_eu5.txt |
| 7 | Food Production | pp_food_production.txt |
| 8 | Food Consumption | pp_food_consumption.txt |
| 9 | New Trade Goods | pp_new_trade_goods.txt |
| 10 | Logistics (Market Access) | pp_building_limits.txt |
| 11 | Rural Capacities | pp_farm_capacity.txt (farms on Arable Land; fishing and forest capacity) |
| 12 | Labor | pp_labor.txt |
| 13 | Variable Harvests | pp_variable_harvests.txt |
| 14 | Arable Land | pp_population_capacity.txt (card concept, also the map mode icon; plus Overused Arable Land) |
| 15 | Population Growth | pp_population_growth.txt |
| 16 | Other Changes | other_changes_pp_buildings_in_location.txt, other_changes_pp_available_free_land.txt, other_changes_pp_abundant_free_land.txt, other_changes_pp_prosperity.txt, other_changes_pp_devastation.txt, other_changes_pp_cheap_food.txt, other_changes_pp_expensive_food.txt, other_changes_pp_province_current_food_storage.txt, other_changes_pp_starvation.txt |

Other Changes sub-cards use the `other_changes_` prefix so they group together when browsing the folder.

Linked support concepts without top-level Europedia cards:

| Concept | File |
|---|---|
| Fishing Capacity | pp_fish_capacity.txt |
| Forest Capacity | pp_forest_capacity.txt |
| Province Food Growth from Storage | pp_positive_province_food_growth.txt |
| Staple Foods (the goods list follows `config/goods_categories.csv` staple_group; a test keeps them equal) | pp_staple_foods.txt |
