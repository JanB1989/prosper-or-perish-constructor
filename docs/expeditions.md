# Colonial expeditions (branch `expeditions`, 2026-10-08)

Eight expensive, gated expeditions that give the colonial powers footholds, trade companies and wars for market centres
on the road to the Indies and China. They use EU5 1.4's expedition system (`common/expedition_types`, the
`start_expedition` generic action), so the AI launches them on its own and the player sees them in the expedition
panel when the country meets the gates.

## Files

| File | What |
| --- | --- |
| `in_game/common/expedition_types/pp_colonial_expeditions.txt` | the eight types: gates, cost, route, AI utility |
| `in_game/events/pp_expedition_events.txt` | outcome events (`pp_expedition.1`-`.11`, `.20` lost at sea) |
| `in_game/common/scripted_effects/pp_expedition_effects.txt` | foothold, trade company, market claim, landing, log |
| `in_game/common/scripted_triggers/pp_expedition_triggers.txt` | seafarer/Atlantic gates, cape route, war and company sites |
| `in_game/common/script_values/pp_expedition_values.txt` | cost (scaled gold units), reserve, AI utility, check chance |
| `in_game/common/building_types/pp_expedition_buildings.txt` | Fortaleza (foreign), Castle-Factory (own harbour) |
| `in_game/common/casus_belli/pp_market_center.txt`, `wargoals/pp_wargoals.txt` | Seize the Market Centre |
| `in_game/common/ai_scripted_expansion_target/pp_market_center_wars.txt` | claimed market owners and company rivals are AI war targets |
| `main_menu/common/static_modifiers/pp_expedition_modifiers.txt` | permanent country modifiers |
| `main_menu/localization/english/pp_expeditions_l_english.yml` | all text |

## The eight expeditions

| # | Type | Gate (besides gold, navy, peace) | Target | Outcome |
| --- | --- | --- | --- | --- |
| 1 | Gold Coast Factory | Atlantic power, Age of Discovery, naval-minded | unclaimed harbour in the Axim area, else Axim | harbour + Castle-Factory + market, or Fortaleza; Gold of Mina |
| 2 | Armada to India | European seafarer, Age of Discovery, cape route known (Gold Coast done, cape route discovered or Cape of Good Hope known), exploration advance | Kochi, Kannur, Goa or Kozhikode (unclaimed or weakest owner) | Fortaleza + trade access + trade company, or Fortaleza + claim on the market centre; Carreira da India; marks the cape route discovered |
| 3 | Armada of Conquest | Armada to India done; an Indian coastal market centre held by a fair target | that market centre (Goa, Kozhikode, Kochi, Diu or Surat market) | war with Seize the Market Centre, six regiments land there |
| 4 | Armada to Malacca | foothold in the Indies; Malacca's market centre held by a fair target | Malacca's market centre | war + landing, Lord of the Straits; or factory + company |
| 5 | Voyage to the Spice Islands | foothold in the Indies; Malacca done or Age of Reformation | Ternate, Tidore or Banda | Fortaleza/Castle-Factory + company, or + claim; Spice Islands Trade |
| 6 | Embassy to the Celestial Court | foothold in the Indies; Malacca or Spice Islands done, or Age of Reformation; 10-year cooldown | Xiangshan (Macau) | the owner decides: Macau port + trade access + company + Licence to Trade with China, or refusal |
| 7 | The Manila Galleon | Age of Reformation; 5 American locations or Spice Islands done | Maynila | harbour + Castle-Factory + market, or Fortaleza + claim; Manila Galleon |
| 8 | Company Voyage to the Indies | trade companies or chartered companies advance, cape route known; repeatable, 15-year cooldown | richest South/South East Asian market centre where the country has no foothold | Fortaleza + company; optional trade war on a European rival already there; Chartered Company |

A fair target (`pp_exp_weak_market_owner`) is any other country that is not a great power, not our subject and not our
overlord. Costs are in vanilla scaled gold units (`pp_exp_gold_unit` = 1 + 0.2 capital wealth + 0.05 economic base, as
`change_gold_effect`): light 4, armada 8, company 10; the treasury must hold 1.5 times the cost.

## AI

- The AI launches expeditions through `start_expedition` (vanilla generic action, monthly tick every 6 months): it
  scores each type it can start with the type's `utility` (here 40, +20-30 for the countries that led the venture
  historically) and checks a type with `ai_chance_to_check` (here 0.5). Vanilla needs 99 political influence
  (`AI_PI_START_EXPEDITION_THRESHOLD`); AI countries sat at 100 in the test run, so gold, navy and peace are the
  real gates.
- Outcome events pick options by `ai_chance` (factory and company first; claims and landings where they apply).
- Claimed market centres: the owner goes into the country's `pp_market_war_targets` list;
  `ai_scripted_expansion_target/pp_market_center_wars.txt` makes it a war target with `cb_pp_market_center` (24 months
  of peace), ignoring antagonism. Company rivals: `pp_trade_war_targets` with vanilla `cb_trade_war_triggered`.

## Testing trace

Every start, end and failure writes `PPEXP;<stage>;<type>;<tag>;<date>` to error.log and sets the country variable
`pp_exp_year_<stage>_<type>` = the year (save table `country_variables`). Console checks:
`run pp_exp_dbg.txt` (gates per colonizer, `PPEXPDBG` lines), `run pp_exp_force.txt` (force-starts all eight).

## Pacing

The chain follows the historical gaps, counted from when the country itself finished the previous step
(`pp_exp_years_since_*`, from the `pp_exp_year_end_<type>` variables): Armada to India 15 years after its Gold Coast
castle (Mina 1482, Calicut 1498) unless the cape route is already known (another country reached India, or the Cape of
Good Hope is discovered); Armada of Conquest 8 years after India (Goa 1510); Armada to Malacca 10 years after India
(1511) or after a company voyage; Spice Islands and the China embassy 5 years after Malacca (Ternate 1522, Canton
1517), or from the Age of Reformation.

## Where the AI colonizes (colonial charters)

Charters are an engine decision (EU5 1.4 removed the scripted `ai_country_should_colonize`). What the defines and the
mod say:

- Who: a country with a tax base of at least `AI_COLONIZE_TAX_BASE_THRESHOLD` (PP 60, vanilla 100; `AI_EAGER_COLONIZER_TAGS`
  SWE/POR/KUR skip it) and 5 population, evaluated every `AI_COLONIAL_CHARTER_TICK_MONTHS` (6). Under the default game
  rule only capitals in Europe colonize (not the Papacy, not AI preference tag `warfare`).
- Where: each candidate province scores `AI_BASE_COLONY_UTILITY` (3) plus goods price x population
  (`COLONY_GOODS_PRICE_UTILITY_MODIFIER`), small-population bonus / large-population penalty, +10 next to own land
  (`COLONY_NEIGHBORING_UTILITY_BONUS`), +5 next to an own charter, a multiplier for the share of the region already held
  (`COLONY_REGION_COMPLETION_UTILITY_BONUS`), -50 for disease-endemic land unless migration is high, and the area
  preferences (`colonize_bias`; PP's colonizer preferences in `area_preferences/pp_colonizer_preferences.txt` push the
  African stations, the route round the Cape and keep them out of Africa's interior and Europe). Colonial range limits
  the reach; `AI_COLONIAL_RANGE_UTILITY` makes the AI value range modifiers.
- Expeditions feed this: footholds extend presence and range (Castle-Factories, colonial range modifiers), so charters
  follow the stations the expeditions open.
