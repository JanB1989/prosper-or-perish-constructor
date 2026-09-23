# RGO Startup Modifier Review

## 2026-09-23 distinctness pass

Every good keeps its `0.20` own-good output and, with one small exception (millet `-0.05` -> `-0.06`), its
peasant food consumption. The side effects were rewritten so each good has its own combination and every
line is large enough to notice, while staying at the low end of vanilla magnitudes: estate power
`0.05`-`0.25`, migration `0.03`-`0.10`, development `0.02`-`0.04`, unrest `0.03`-`0.05`, disease resistance
`0.02`-`0.05`, named-disease modifiers `0.05`-`0.15`, life expectancy `+1` / `-1` / `-2`.

New hooks used: estate power (crown, nobles, clergy, burghers, peasants, tribes), named diseases
(`local_malaria_impact_modifier` for rice, pepper and sugar; `local_bubonic_plague_resistance_modifier` for
wheat; `local_measles_resistance_modifier` for livestock), `local_sailors_modifier` (fish, fiber crops, pearls),
`local_levy_size_modifier` (horses, iron), `local_devastation_recovery` (potato +, olives -),
`local_institution_growth_modifier` (coffee), `local_pop_promotion_speed_modifier` (silk),
`local_monthly_prosperity` (fruit), `local_market_access` (olives, ivory), `local_life_expectancy`
(medicaments +, lead and mercury -), `local_fort_maintenance_efficiency` (stone), `local_cultural_influence`
(marble), `local_food_capacity_modifier` (millet), negative `local_max_rgo_size_modifier` (tobacco).

Removed: the leftover `local_population_capacity_modifier = 0` lines, the generic growth penalties on most
mines, and the tenfold medicaments growth value (`0.002` -> `0.0003`). Building-level modifiers are
deliberately not used.

The per-good sections below describe the earlier pass.

This review covers the startup-applied `pp_rgo_bonus_*` location modifiers.
Every raw material keeps an own-good local output bonus, raised from `0.15` to
`0.20`. The side effects were retuned to avoid weak or unsupported hooks and to
make each good read as a distinct local condition.

Removed everywhere:
- `local_trade_center_power`
- `local_ship_build_speed`
- `local_slave_pop_satisfaction`

Global guardrails:
- Mining goods may keep negative population growth, disease resistance, or unrest.
- `local_production_efficiency` is used only where the production logic is strong,
  and always with a downside.
- `local_max_control` is allowed, but no value is larger than `0.05` in magnitude.
- Construction speed and building cost reductions are reserved for direct material
  inputs such as clay, lumber, stone, marble, sand, iron, and saltpeter.

## Food And Staples

### Wheat
Current: `local_wheat_output_modifier = 0.15`; `local_peasants_food_consumption = -0.11`; `local_disease_resistance = -0.02`.
Proposed: `local_wheat_output_modifier = 0.20`; `local_peasants_food_consumption = -0.11`; `local_max_rgo_size_modifier = 0.03`; `local_disease_resistance = -0.01`.
Reason: Wheat should remain the strongest breadbasket food reducer, with larger field capacity and only a small disease drawback.

### Maize
Current: `local_maize_output_modifier = 0.15`; `local_peasants_food_consumption = -0.08`; `local_population_growth = 0.0002`; `local_disease_resistance = -0.02`.
Proposed: `local_maize_output_modifier = 0.20`; `local_peasants_food_consumption = -0.08`; `local_population_growth = 0.0002`; `local_disease_resistance = -0.01`.
Reason: Maize remains a growth food with a lighter resilience downside.

### Millet
Current: `local_millet_output_modifier = 0.15`; `local_peasants_food_consumption = -0.05`; `local_population_capacity_modifier = 0.02`.
Proposed: `local_millet_output_modifier = 0.20`; `local_peasants_food_consumption = -0.05`; `local_population_capacity_modifier = 0.02`; `local_supply_limit_modifier = 0.02`.
Reason: Millet should feel like a resilient dryland staple that also supports marching supplies.

### Legumes
Current: `local_legumes_output_modifier = 0.15`; `local_max_rgo_size_modifier = 0.05`; `local_peasants_food_consumption = -0.05`; `local_population_capacity_modifier = 0.03`.
Proposed: `local_legumes_output_modifier = 0.20`; `local_max_rgo_size_modifier = 0.05`; `local_peasants_food_consumption = -0.05`; `local_population_capacity_modifier = 0.03`.
Reason: Legumes were already coherent as soil-restoring mixed farming, so the pass only raises output.

### Potato
Current: `local_potato_output_modifier = 0.15`; `local_peasants_food_consumption = -0.08`; `local_food_capacity_modifier = 0.05`; `local_population_growth = 0.0002`.
Proposed: `local_potato_output_modifier = 0.20`; `local_peasants_food_consumption = -0.08`; `local_food_capacity_modifier = 0.05`; `local_population_growth = 0.0002`.
Reason: Potatoes already have a clear food-security identity and keep it.

### Rice
Current: `local_rice_output_modifier = 0.15`; `local_peasants_food_consumption = -0.10`; `local_population_growth = 0.0004`; `local_disease_resistance = -0.03`.
Proposed: `local_rice_output_modifier = 0.20`; `local_peasants_food_consumption = -0.10`; `local_population_growth = 0.0004`; `local_disease_resistance = -0.03`.
Reason: Wet rice remains the dense-population staple with a paddy disease cost.

### Fruit
Current: `local_fruit_output_modifier = 0.15`; `local_peasants_food_consumption = -0.03`; `local_population_capacity_modifier = 0.03`.
Proposed: `local_fruit_output_modifier = 0.20`; `local_peasants_food_consumption = -0.03`; `local_population_capacity_modifier = 0.03`; `local_monthly_development_modifier = 0.01`.
Reason: Orchards should add diet variety, capacity, and slow local improvement.

### Fish
Current: `local_fish_output_modifier = 0.15`; `local_peasants_food_consumption = -0.05`; `local_migration_attraction = 0.01`.
Proposed: `local_fish_output_modifier = 0.20`; `local_peasants_food_consumption = -0.05`; `local_migration_attraction = 0.01`; `local_supply_limit_modifier = 0.02`.
Reason: Fish improves protein supply and local provisioning without assuming coastal shipbuilding.

## Cash Crops

### Chili
Current: `local_chili_output_modifier = 0.15`; `local_population_growth = 0.0002`; `local_migration_attraction = 0.02`; `local_peasants_food_consumption = 0.02`.
Proposed: `local_chili_output_modifier = 0.20`; `local_population_growth = 0.0002`; `local_migration_attraction = 0.02`; `local_peasants_food_consumption = 0.02`.
Reason: Chili remains a useful but land-competing cash food.

### Cloves
Current: `local_cloves_output_modifier = 0.15`; `local_goods_gold_output_modifier = 0.03`; `local_disease_resistance = 0.02`; `local_population_growth = -0.0003`.
Proposed: `local_cloves_output_modifier = 0.20`; `local_monthly_development_modifier = 0.02`; `local_unrest = 0.02`; `local_max_control = -0.02`.
Reason: Cloves should model high-value plantation monopoly pressure, not gold output or generic population decline.

### Cocoa
Current: `local_cocoa_output_modifier = 0.15`; `local_trade_center_power = 0.02`; `local_peasants_food_consumption = 0.02`; `local_disease_resistance = -0.02`.
Proposed: `local_cocoa_output_modifier = 0.20`; `local_monthly_development_modifier = 0.01`; `local_peasants_food_consumption = 0.02`; `local_disease_resistance = -0.02`.
Reason: Cocoa becomes a development cash crop with land and health costs.

### Coffee
Current: `local_coffee_output_modifier = 0.15`; `local_migration_attraction = 0.01`; `local_disease_resistance = -0.05`.
Proposed: `local_coffee_output_modifier = 0.20`; `local_migration_attraction = 0.01`; `local_monthly_development_modifier = 0.01`; `local_disease_resistance = -0.03`.
Reason: Coffee keeps labor pull and unhealthy humid estates, but gains a modest development hook.

### Cotton
Current: `local_cotton_output_modifier = 0.15`; `local_migration_attraction = 0.01`; `local_slave_pop_satisfaction = -0.005`; `local_population_capacity_modifier = -0.03`.
Proposed: `local_cotton_output_modifier = 0.20`; `local_migration_attraction = 0.01`; `local_population_capacity_modifier = -0.03`; `local_unrest = 0.01`.
Reason: Cotton keeps settlement and land pressure while replacing the unsupported slave satisfaction hook.

### Dyes
Current: `local_dyes_output_modifier = 0.15`; `local_production_efficiency = 0.03`; `local_trade_center_power = 0.03`; `local_population_growth = -0.0002`.
Proposed: `local_dyes_output_modifier = 0.20`; `local_production_efficiency = 0.02`; `local_population_capacity_modifier = -0.02`; `local_unrest = 0.01`.
Reason: Dye processing can improve production, but it now has clear land and labor downsides.

### Olives
Current: `local_olives_output_modifier = 0.15`; `local_peasants_food_consumption = -0.03`; `local_supply_limit_modifier = -0.02`.
Proposed: `local_olives_output_modifier = 0.20`; `local_peasants_food_consumption = -0.02`; `local_monthly_development_modifier = 0.01`; `local_supply_limit_modifier = -0.01`.
Reason: Olives provide oil and cash value with a milder forage drawback.

### Pepper
Current: `local_pepper_output_modifier = 0.15`; `local_trade_center_power = 0.03`; `local_unrest = 0.01`; `local_disease_resistance = -0.02`.
Proposed: `local_pepper_output_modifier = 0.20`; `local_monthly_development_modifier = 0.02`; `local_unrest = 0.01`; `local_disease_resistance = -0.02`.
Reason: Pepper keeps high-value plantation pressure without the weak trade-center modifier.

### Saffron
Current: `local_saffron_output_modifier = 0.15`; `local_migration_attraction = 0.01`; `local_monthly_development_modifier = 0.03`; `local_peasants_food_consumption = 0.03`.
Proposed: `local_saffron_output_modifier = 0.20`; `local_migration_attraction = 0.01`; `local_monthly_development_modifier = 0.03`; `local_peasants_food_consumption = 0.03`.
Reason: Saffron already reads as a labor-heavy luxury crop that displaces staple food.

### Silk
Current: `local_silk_output_modifier = 0.15`; `local_trade_center_power = 0.02`; `local_migration_attraction = 0.02`; `local_peasants_food_consumption = 0.03`.
Proposed: `local_silk_output_modifier = 0.20`; `local_migration_attraction = 0.02`; `local_monthly_development_modifier = 0.02`; `local_peasants_food_consumption = 0.03`.
Reason: Silk becomes skilled-labor development rather than a trade-center boost.

### Sugar
Current: `local_sugar_output_modifier = 0.15`; `local_slave_pop_satisfaction = -0.005`; `local_disease_resistance = -0.05`; `local_peasants_food_consumption = 0.05`.
Proposed: `local_sugar_output_modifier = 0.20`; `local_disease_resistance = -0.05`; `local_peasants_food_consumption = 0.05`; `local_unrest = 0.02`.
Reason: Sugar keeps severe plantation health and food-displacement downsides, with unrest replacing the unsupported hook.

### Tea
Current: `local_tea_output_modifier = 0.15`; `local_trade_center_power = 0.02`; `local_peasants_food_consumption = 0.02`.
Proposed: `local_tea_output_modifier = 0.20`; `local_monthly_development_modifier = 0.01`; `local_peasants_food_consumption = 0.02`; `local_max_control = 0.02`.
Reason: Tea is now an ordered estate crop with modest development and control.

### Tobacco
Current: `local_tobacco_output_modifier = 0.15`; `local_migration_attraction = 0.01`; `local_slave_pop_satisfaction = -0.005`; `local_population_growth = -0.0002`.
Proposed: `local_tobacco_output_modifier = 0.20`; `local_migration_attraction = 0.01`; `local_population_capacity_modifier = -0.02`; `local_unrest = 0.01`.
Reason: Tobacco keeps cash-crop settlement pressure without a broad population-growth penalty.

### Wine
Current: `local_wine_output_modifier = 0.15`; `local_monthly_control = 0.001`; `local_peasants_food_consumption = 0.05`.
Proposed: `local_wine_output_modifier = 0.20`; `local_monthly_control = 0.001`; `local_peasants_food_consumption = 0.03`; `local_monthly_development_modifier = 0.01`.
Reason: Vineyards keep control and food displacement while adding estate development.

## Animal And Forest Goods

### Beeswax
Current: `local_beeswax_output_modifier = 0.15`; `local_peasants_food_consumption = -0.03`; `local_trade_center_power = 0.04`; `local_cultural_tradition = 0.03`; `local_unrest = 0.01`.
Proposed: `local_beeswax_output_modifier = 0.20`; `local_peasants_food_consumption = -0.03`; `local_cultural_tradition = 0.02`; `local_unrest = 0.005`.
Reason: Beeswax keeps pollination and craft value while losing the weak trade-center boost and softening unrest.

### Elephants
Current: `local_elephants_output_modifier = 0.15`; `local_migration_attraction = 0.01`; `local_manpower = 0.01`; `local_peasants_food_consumption = 0.05`.
Proposed: `local_elephants_output_modifier = 0.20`; `local_manpower = 0.01`; `local_supply_limit_modifier = 0.03`; `local_peasants_food_consumption = 0.03`.
Reason: Elephants now emphasize transport, war animals, and forage pressure.

### Fiber Crops
Current: `local_fiber_crops_output_modifier = 0.15`; `local_production_efficiency = 0.02`; `local_migration_attraction = -0.02`.
Proposed: `local_fiber_crops_output_modifier = 0.20`; `local_supply_limit_modifier = 0.02`; `local_peasants_food_consumption = 0.01`; `local_monthly_development_modifier = 0.01`.
Reason: Fiber crops become rope, linen, and supply value instead of a generic production boost.

### Horses
Current: `local_horses_output_modifier = 0.15`; `local_manpower = 0.01`; `local_supply_limit_modifier = 0.03`; `local_peasants_food_consumption = 0.02`.
Proposed: `local_horses_output_modifier = 0.20`; `local_manpower = 0.01`; `local_supply_limit_modifier = 0.04`; `local_peasants_food_consumption = 0.02`.
Reason: Horses already made sense and now lean slightly more into supply.

### Livestock
Current: `local_livestock_output_modifier = 0.15`; `local_peasants_food_consumption = -0.04`; `local_population_capacity_modifier = -0.03`; `local_migration_attraction = 0.01`.
Proposed: `local_livestock_output_modifier = 0.20`; `local_peasants_food_consumption = -0.04`; `local_supply_limit_modifier = 0.03`; `local_population_capacity_modifier = -0.02`.
Reason: Livestock should improve food and army supply while pasture still limits dense settlement.

### Wool
Current: `local_wool_output_modifier = 0.15`; `local_peasants_food_consumption = -0.03`; `local_population_growth = -0.0002`.
Proposed: `local_wool_output_modifier = 0.20`; `local_peasants_food_consumption = -0.03`; `local_monthly_development_modifier = 0.01`; `local_supply_limit_modifier = 0.02`.
Reason: Wool should represent pastoral food, textiles, and pack supply, not direct population decline.

### Lumber
Current: `local_lumber_output_modifier = 0.15`; `local_build_buildings_cost = -0.02`; `local_migration_attraction = 0.02`.
Proposed: `local_lumber_output_modifier = 0.20`; `local_build_buildings_cost = -0.02`; `local_construction_speed = 0.05`; `local_migration_attraction = 0.02`.
Reason: Lumber directly supports cheaper and faster local construction.

### Fur
Current: `local_fur_output_modifier = 0.15`; `local_peasants_food_consumption = -0.02`; `local_wild_game_output_modifier = -0.05`; `local_unrest = 0.01`.
Proposed: `local_fur_output_modifier = 0.20`; `local_peasants_food_consumption = -0.02`; `local_unrest = 0.01`; `local_max_control = -0.02`.
Reason: Fur should not suppress another good output; weak control better represents dispersed trapping.

### Ivory
Current: `local_ivory_output_modifier = 0.15`; `local_elephants_output_modifier = -0.10`; `local_peasants_food_consumption = 0.02`; `local_migration_attraction = -0.05`.
Proposed: `local_ivory_output_modifier = 0.20`; `local_peasants_food_consumption = 0.02`; `local_migration_attraction = -0.03`; `local_unrest = 0.02`.
Reason: Ivory keeps coercive extraction pressure without cross-good elephant penalties.

### Wild Game
Current: `local_wild_game_output_modifier = 0.15`; `local_peasants_food_consumption = -0.035`; `local_migration_attraction = -0.01`.
Proposed: `local_wild_game_output_modifier = 0.20`; `local_peasants_food_consumption = -0.035`; `local_migration_attraction = -0.01`; `local_supply_limit_modifier = 0.02`.
Reason: Wild game remains less settlement-oriented but useful for meat and field provisions.

## Construction Materials

### Clay
Current: `local_clay_output_modifier = 0.15`; `local_production_efficiency = 0.02`; `local_build_buildings_cost = -0.02`; `local_peasants_food_consumption = 0.02`.
Proposed: `local_clay_output_modifier = 0.20`; `local_build_buildings_cost = -0.02`; `local_construction_speed = 0.10`; `local_monthly_development_modifier = 0.01`.
Reason: Clay should strongly support brickmaking and construction speed, not broad production efficiency.

### Salt
Current: `local_salt_output_modifier = 0.15`; `local_food_decay_modifier = -0.00070`; `local_peasants_food_consumption = -0.02`; `local_trades_per_burgher = 0.10`; `local_max_control = -0.02`.
Proposed: `local_salt_output_modifier = 0.20`; `local_food_decay_modifier = -0.00070`; `local_peasants_food_consumption = -0.02`; `local_trades_per_burgher = 0.10`; `local_max_control = -0.02`.
Reason: Salt already has a strong preservation and trade identity, so only output changes.

### Sand
Current: `local_sand_output_modifier = 0.15`; `local_construction_speed = 0.03`; `local_monthly_development_modifier = 0.01`; `local_population_growth = -0.0001`.
Proposed: `local_sand_output_modifier = 0.20`; `local_construction_speed = 0.05`; `local_build_buildings_cost = -0.01`; `local_disease_resistance = -0.01`.
Reason: Sand helps glass and construction while dust is a clearer downside than population growth.

### Stone
Current: `local_stone_output_modifier = 0.15`; `local_build_buildings_cost = -0.03`; `local_construction_speed = 0.02`; `local_population_growth = -0.0001`.
Proposed: `local_stone_output_modifier = 0.20`; `local_build_buildings_cost = -0.03`; `local_construction_speed = 0.05`; `local_disease_resistance = -0.01`.
Reason: Stone should clearly speed and cheapen masonry, with quarry dust as the drawback.

### Marble
Current: `local_marble_output_modifier = 0.15`; `local_build_buildings_cost = -0.02`; `local_monthly_development_modifier = 0.02`; `local_migration_attraction = 0.01`; `local_disease_resistance = -0.02`.
Proposed: `local_marble_output_modifier = 0.20`; `local_build_buildings_cost = -0.02`; `local_construction_speed = 0.05`; `local_monthly_development_modifier = 0.02`; `local_disease_resistance = -0.02`.
Reason: Marble gains a direct construction-speed role and drops redundant migration attraction.

## Luxury And Special Goods

### Amber
Current: `local_amber_output_modifier = 0.15`; `local_migration_attraction = 0.01`; `local_trade_center_power = 0.01`.
Proposed: `local_amber_output_modifier = 0.20`; `local_migration_attraction = 0.01`; `local_monthly_development_modifier = 0.01`; `local_cultural_tradition = 0.02`.
Reason: Amber should feel like craft and prestige value, not a trade-center modifier.

### Incense
Current: `local_incense_output_modifier = 0.15`; `local_migration_attraction = 0.02`; `local_pop_conversion_speed_modifier = 0.05`; `local_monthly_development_modifier = -0.03`.
Proposed: `local_incense_output_modifier = 0.20`; `local_migration_attraction = 0.02`; `local_pop_conversion_speed_modifier = 0.05`; `local_max_control = 0.02`.
Reason: Incense should support religious and caravan authority rather than slowing development.

### Medicaments
Current: `local_medicaments_output_modifier = 0.15`; `local_disease_resistance = 0.05`; `local_life_expectancy = 1`.
Proposed: `local_medicaments_output_modifier = 0.20`; `local_disease_resistance = 0.05`; `local_population_growth = 0.002`; `local_monthly_development_modifier = 0.01`.
Reason: Medicaments now affect local population and development directly instead of character life expectancy.

### Pearls
Current: `local_pearls_output_modifier = 0.15`; `local_trade_center_power = 0.03`; `local_migration_attraction = 0.01`; `local_disease_resistance = -0.02`; `local_unrest = 0.01`.
Proposed: `local_pearls_output_modifier = 0.20`; `local_migration_attraction = 0.01`; `local_disease_resistance = -0.02`; `local_unrest = 0.01`.
Reason: Pearls keep risky extraction and labor pull without a trade-center bonus.

### Gems
Current: `local_gems_output_modifier = 0.15`; `local_migration_attraction = 0.02`; `local_trade_center_power = 0.02`; `local_unrest = 0.02`; `local_disease_resistance = -0.02`.
Proposed: `local_gems_output_modifier = 0.20`; `local_migration_attraction = 0.02`; `local_unrest = 0.02`; `local_disease_resistance = -0.02`.
Reason: Gem fields remain rush-labor extraction with disorder and health downsides.

## Mining

### Coal
Current: `local_coal_output_modifier = 0.15`; `local_migration_attraction = 0.02`; `local_population_growth = -0.0002`; `local_disease_resistance = -0.03`.
Proposed: `local_coal_output_modifier = 0.20`; `local_migration_attraction = 0.02`; `local_population_growth = -0.0002`; `local_disease_resistance = -0.03`.
Reason: Coal already had coherent mining labor and health costs.

### Iron
Current: `local_iron_output_modifier = 0.15`; `local_migration_attraction = 0.02`; `local_population_growth = -0.0002`; `local_build_buildings_cost = -0.02`.
Proposed: `local_iron_output_modifier = 0.20`; `local_migration_attraction = 0.02`; `local_population_growth = -0.0002`; `local_build_buildings_cost = -0.02`.
Reason: Iron supports construction and keeps a mining growth downside.

### Copper
Current: `local_copper_output_modifier = 0.15`; `local_migration_attraction = 0.02`; `local_population_capacity_modifier = -0.05`; `local_disease_resistance = -0.02`.
Proposed: `local_copper_output_modifier = 0.20`; `local_migration_attraction = 0.02`; `local_population_growth = -0.0002`; `local_disease_resistance = -0.02`.
Reason: Copper gets a clearer mining health and growth penalty instead of a large capacity hit.

### Gold
Current: `local_goods_gold_output_modifier = 0.15`; `local_migration_attraction = 0.03`; `local_unrest = 0.02`; `local_population_growth = -0.0003`; `local_disease_resistance = -0.03`.
Proposed: `local_goods_gold_output_modifier = 0.20`; `local_migration_attraction = 0.03`; `local_unrest = 0.02`; `local_population_growth = -0.0003`; `local_disease_resistance = -0.03`.
Reason: Gold already reads as a rush economy with strong disorder and health drawbacks.

### Silver
Current: `local_silver_output_modifier = 0.15`; `local_migration_attraction = 0.02`; `local_unrest = 0.01`; `local_population_growth = -0.0002`; `local_disease_resistance = -0.03`.
Proposed: `local_silver_output_modifier = 0.20`; `local_migration_attraction = 0.02`; `local_unrest = 0.01`; `local_population_growth = -0.0002`; `local_disease_resistance = -0.03`.
Reason: Silver keeps rush labor, unrest, and toxic processing downsides.

### Tin
Current: `local_tin_output_modifier = 0.15`; `local_migration_attraction = 0.01`; `local_production_efficiency = 0.02`; `local_population_growth = -0.0002`.
Proposed: `local_tin_output_modifier = 0.20`; `local_migration_attraction = 0.01`; `local_population_growth = -0.0002`; `local_disease_resistance = -0.02`.
Reason: Tin no longer gets rare production efficiency and instead uses a clearer mining health drawback.

### Lead
Current: `local_lead_output_modifier = 0.15`; `local_manpower_modifier = 0.01`; `local_disease_resistance = -0.05`; `local_population_growth = -0.0004`.
Proposed: `local_lead_output_modifier = 0.20`; `local_manpower_modifier = 0.01`; `local_disease_resistance = -0.05`; `local_population_growth = -0.0004`.
Reason: Lead remains one of the harshest health mining districts.

### Saltpeter
Current: `local_saltpeter_output_modifier = 0.15`; `local_manpower_modifier = 0.02`; `local_build_buildings_cost = -0.01`; `local_disease_resistance = -0.02`; `local_unrest = 0.01`.
Proposed: `local_saltpeter_output_modifier = 0.20`; `local_manpower_modifier = 0.02`; `local_build_buildings_cost = -0.01`; `local_disease_resistance = -0.02`; `local_unrest = 0.01`.
Reason: Saltpeter already matches gunpowder logistics and intrusive extraction.

### Alum
Current: `local_alum_output_modifier = 0.15`; `local_production_efficiency = 0.02`; `local_trade_center_power = 0.01`; `local_disease_resistance = -0.02`; `local_population_growth = -0.0002`.
Proposed: `local_alum_output_modifier = 0.20`; `local_production_efficiency = 0.02`; `local_disease_resistance = -0.02`; `local_population_growth = -0.0002`.
Reason: Alum keeps rare production efficiency because of chemical and dyeing uses, with mining health and growth downsides.

### Mercury
Current: `local_mercury_output_modifier = 0.15`; `local_goods_gold_output_modifier = 0.02`; `local_disease_resistance = -0.08`; `local_population_growth = -0.0005`.
Proposed: `local_mercury_output_modifier = 0.20`; `local_production_efficiency = 0.02`; `local_disease_resistance = -0.08`; `local_population_growth = -0.0005`; `local_unrest = 0.02`.
Reason: Mercury keeps severe toxicity and gains specialized processing value without boosting gold directly.
