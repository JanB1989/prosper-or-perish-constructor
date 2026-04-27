# In-game Documentation Rules

Instructions for Cursor when editing game concept definitions or the Europedia.
# Prosper or Perish (Population Growth & Food Rework)\in_game\gui\encyclopedia_lateralview.gui
# Localization is usually here main_menu/localization/english/pp_europedia_l_english.yml
## Concept display order

When editing the Europedia GUI or concept definitions, preserve this order:

1. All (done)
2. F.A.Q.
3. Overview (done)
4. Urbanisation (done)
5. Food Production (done)
6. Food Consumption
7. New Buildings (done)
8. New Trade Goods (done)
9. Farm Capacity (done)
10. Farm Output (done)
11. Variable Harvests (done)
12. Population Growth
13. Population Distribution
14. Other Changes

More concepts may be added later.

## File naming

Each Europedia card has exactly one game concept file. Filename = card name (snake_case, pp_ prefix):

| # | Card | File |
|---|------|------|
| 1 | All | (filter only) |
| 2 | F.A.Q. | pp_faq.txt |
| 3 | Overview | pp_overview.txt |
| 4 | Urbanisation | pp_urbanisation.txt |
| 5 | Food Production | pp_food_production.txt |
| 6 | Food Consumption | pp_food_consumption.txt |
| 7 | New Buildings | pp_new_buildings.txt |
| 8 | New Trade Goods | pp_new_trade_goods.txt |
| 9 | Farm Capacity | pp_farm_capacity.txt |
| 10 | Farm Output | pp_farm_output.txt |
| 11 | Variable Harvests | pp_variable_harvests.txt |
| 12 | Population Growth | pp_population_growth.txt |
| 13 | Population Distribution | pp_population_distribution.txt |
| 14 | Other Changes | other_changes_pp_buildings_in_location.txt, other_changes_pp_prosperity.txt, other_changes_pp_devastation.txt, other_changes_pp_cheap_food.txt, other_changes_pp_expensive_food.txt, other_changes_pp_province_current_food_storage.txt, other_changes_pp_starvation.txt |

Other Changes sub-cards use the `other_changes_` prefix so they group together when browsing the folder.
