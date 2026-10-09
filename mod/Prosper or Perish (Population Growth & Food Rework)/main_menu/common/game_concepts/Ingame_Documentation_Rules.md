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

1. `pp_eu_banner` - an edge-to-edge picture, 2900 x 500 DDS shown at 1450 x 250 (sharp at large UI scales).
   Vanilla has nothing that wide (its illustrations are 1080 x 440 and look soft stretched), so each banner is
   composed by `tools/build_europedia_banners.py` from the location view's 2654 px panorama layers, graded to the
   topic. Landscape only: a vanilla illustration laid over it never matched its horizon or style (Jan, 2026-10-09).
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
   - goods rows: `pp_eu_goods_row` with a two-line label (`#T name#!\nverdict`) and `pp_eu_goods` icons (tooltip = the
     goods key; alpha 0.55 for goods the mechanic leaves alone).
5. Section order that reads well: what happens (flow) -> how strong (scale) -> what it touches -> where to see it in
   game. Keep a card on its own mechanic; the neighbouring mechanics get a link in the text, not a section of their
   own (Jan dropped the harvest card's "Where It Leads" flow, 2026-10-09).

Use the mod's own visual language where one exists (harvest medallions = the location view's harvest chip frames).
`tests/test_europedia_style.py` checks textures, keys, links, data functions and that the text has no numbers; extend
it when a new card adopts the style.

## Concept display order

When editing the Europedia GUI or concept definitions, preserve this order:

1. All (done)
2. Getting Started
3. F.A.Q.
4. Update 0.9
5. Overview (done)
6. Food in EU5
7. Food Production (done)
8. Food Consumption
9. New Trade Goods (done)
10. New Buildings (done)
11. Building Limits
12. Building Capacity (done)
13. Building Output (done)
14. Variable Harvests (done)
15. Population Capacity
16. Population Growth
17. Population Distribution
18. Other Changes

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
| 6 | Food in EU5 | pp_food_in_eu5.txt |
| 7 | Food Production | pp_food_production.txt |
| 8 | Food Consumption | pp_food_consumption.txt |
| 9 | New Trade Goods | pp_new_trade_goods.txt |
| 10 | New Buildings | pp_new_buildings.txt |
| 11 | Building Limits | pp_building_limits.txt |
| 12 | Building Capacity | pp_farm_capacity.txt |
| 13 | Building Output | pp_farm_output.txt |
| 14 | Variable Harvests | pp_variable_harvests.txt |
| 15 | Population Capacity | pp_population_capacity.txt |
| 16 | Population Growth | pp_population_growth.txt |
| 17 | Population Distribution | pp_population_distribution.txt |
| 18 | Other Changes | other_changes_pp_buildings_in_location.txt, other_changes_pp_available_free_land.txt, other_changes_pp_abundant_free_land.txt, other_changes_pp_prosperity.txt, other_changes_pp_devastation.txt, other_changes_pp_cheap_food.txt, other_changes_pp_expensive_food.txt, other_changes_pp_province_current_food_storage.txt, other_changes_pp_starvation.txt |

Other Changes sub-cards use the `other_changes_` prefix so they group together when browsing the folder.

Linked support concepts without top-level Europedia cards:

| Concept | File |
|---|---|
| Fishing Capacity | pp_fish_capacity.txt |
| Forest Capacity | pp_forest_capacity.txt |
| Province Food Growth from Storage | pp_positive_province_food_growth.txt |
