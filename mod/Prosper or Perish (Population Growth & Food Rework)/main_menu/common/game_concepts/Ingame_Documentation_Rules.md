# In-game Documentation Rules

Instructions for Cursor when editing game concept definitions or the Europedia.
# Prosper or Perish (Population Growth & Food Rework)\in_game\gui\encyclopedia_lateralview.gui
# Localization is usually here main_menu/localization/english/pp_europedia_l_english.yml
## Localization guidance

- When a linked modifier or concept tooltip already displays food-storage modifier effects, do not restate those values in Europedia prose.
- Explain what the player should understand and where to inspect effects; let modifiers carry exact changing numbers.

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
