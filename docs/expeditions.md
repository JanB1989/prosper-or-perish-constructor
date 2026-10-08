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

| # | Type | Gate (besides the gold reserve; see War below) | Target | Outcome |
| --- | --- | --- | --- | --- |
| 1 | Gold Coast Factory | colonial power, Age of Discovery, naval-minded, a free harbour left on the Guinea coast | the best free Guinea harbour (unclaimed first, then the most populous) | unclaimed: the harbour + Castle-Factory + a market if none in the region; native: Fortaleza + trade access; Gold of Mina |
| 2 | Armada to India | colonial power, exploration advance, 15 years after the own Gold Coast castle (or Age of Reformation once the cape route is known), a free harbour among Kochi, Kannur, Goa, Kozhikode, Diu | that harbour (unclaimed or weakest owner) | Fortaleza + trade access + trade company, or Fortaleza + claim on the market centre; Carreira da India; marks the cape route discovered |
| 3 | Armada of Conquest | India done 8 years ago; an Indian coastal market centre held by a fair target | that market centre (Goa, Kozhikode, Kochi, Diu or Surat market) | war with Seize the Market Centre, six regiments land there |
| 4 | Armada to Malacca | foothold in the Indies, India 10 years ago (or a company voyage); Malacca's market centre held by a fair target | Malacca's market centre | war + landing, Lord of the Straits; or factory + company |
| 5 | Voyage to the Spice Islands | foothold in the Indies; Malacca 5 years ago or Age of Reformation; a free harbour among Ternate, Tidore, Banda | that island | Fortaleza/Castle-Factory + company, or + claim; Spice Islands Trade |
| 6 | Embassy to the Celestial Court | foothold in the Indies; Malacca 5 years ago, Spice Islands done or Age of Reformation; no foothold at Macau yet; 10-year cooldown | Xiangshan (Macau) | the owner decides (accepts 30 % before the Age of Reformation, 70 % after): Macau port + trade access + company + Licence to Trade with China, or refusal |
| 7 | The Manila Galleon | Age of Reformation; 5 American locations or Spice Islands done; Maynila free | Maynila | unclaimed: harbour + Castle-Factory + market; native: Fortaleza + claim; Manila Galleon |
| 8 | Company Voyage to the Indies | trade companies or chartered companies advance, cape route known, 15+ locations; repeatable, 15-year cooldown | the most populous South/South East Asian market centre where the country has no foothold | Fortaleza + company; optional trade war on a European rival already there; Chartered Company |

A colonial power (`pp_exp_colonial_power`) owns a harbour on Europe's ocean coasts (Iberia, France, the British Isles,
the Low Countries and North Germany, Scandinavia), at least 25 locations and 10 ships, and an ocean-going advance. A
free site (`pp_exp_free_site`) is a harbour no European country owns and where no country has a foothold yet. A fair
target (`pp_exp_weak_market_owner`) is any other country that is not a great power, not our subject and not our
overlord. Costs are in vanilla scaled gold units (`pp_exp_gold_unit` = 1 + 0.2 capital wealth + 0.05 economic base, as
`change_gold_effect`; Portugal 31, Castile 62, England 44 in 1452): light 4 (at least 150 gold), armada 8 (at least
400), company 10 (at least 600); the treasury must hold 1.5 times the cost.

War: the commercial and diplomatic voyages (1, 2, 5, 6, 7, 8) only wait while the country is at war with a European
great power; the two war armadas (3, 4) need full peace. (In the first proof run Portugal fought Morocco for the
Strait coast from 1472 to 1482 and could not send its India armada while any war ran.)

Trade companies are created like vanilla's `create_building_subject` action: `create_building_country_in_location` with
`subject_type:trade_company`, the overlord's ruler and the target's region; the new company takes over the country's
Fortalezas in that region (1452 test: England's Moluccas company owns the Ternate and Tidore Fortalezas).

EU5 1.4 keeps a subject type only while the overlord has an advance that unlocks it (vanilla: `trade_companies_advance`,
Age of Reformation, only); without it the engine turns the company into a plain vassal at its next validity check (on
province owner changes, abandoned locations, revolts), and a vassal with no land disappeared within a few years
(Castile's Malabar company, 1478-1487). So `advances/pp_expedition_advances_adjustments.txt` lets
`open_sea_exploration`, `explorer_commisions_advance` and `por_carreira_da_india` unlock `trade_company` too (tested:
Portugal's Konkan company kept its type through a province transfer and six months). Vanilla's Trade Company
Headquarters `on_built` made the same vassals for the same reason.

Landings put six regiments (halberdiers in the Age of Discovery, pikemen later) ashore at the market centre right after
the war declaration.

## AI

- How the AI launches an expedition (decoded from the 1.4 engine, 2026-10-08): once a month per AI country, if it
  holds at least `AI_PI_START_EXPEDITION_THRESHOLD` (99) political influence and can pay the 25 of the
  `start_expedition` price. Each type is looked at every third month and then only with its `ai_chance_to_check`
  (here 0.5; vanilla default 0.05, about one try in five years). A type must pass ai/potential/unique/repeatable and
  `can_start`, and needs a leader with `leader_utility` above 0 (here at least 1); `ai_leader_source_list` (every
  character passing `pp_exp_leader`) makes the AI look at the whole court instead of a fifth of it per try. The
  type's `utility` (here 40, +20-30 for the countries that led the venture historically) only ranks the types that
  passed in the same month; anything above 0 can launch. Gold, debt, saving mode and war do not enter the AI's
  choice, so the gold reserve in `can_start` is the only money gate. AI countries sat at 100 political influence in
  the test run.
- Outcome events pick options by `ai_chance` (factory and company first; claims and landings where they apply).
- Claimed market centres: the owner goes into the country's `pp_market_war_targets` list;
  `ai_scripted_expansion_target/pp_market_center_wars.txt` makes it a war target with `cb_pp_market_center` (24 months
  of peace), ignoring antagonism. Company rivals: `pp_trade_war_targets` with vanilla `cb_trade_war_triggered`.

## Testing trace

Every start, end and failure sets the country variable `pp_exp_year_<stage>_<type>` = the year (save table
`country_variables`) and adds the country to the global list `pp_exp_log_<stage>` (error.log keeps only one line per
script location, so it cannot trace repeated starts). Console checks (run files in `Documents/.../run/`, not in the
repo): `pp_exp_dbg.txt` (gates per colonizer, `PPEXPDBG` lines in error.log), `pp_exp_chain.txt` (sets the earlier
stages and force-starts India, Malabar war, Malacca, Spice Islands, China; `start_expedition` refuses a type whose
potential or can_start fails), `pp_hist_personalities.txt` (restores vanilla's historical AI personalities).

## Pacing

The chain follows the historical gaps, counted from when the country itself finished the previous step
(`pp_exp_years_since_*`, from the `pp_exp_year_end_<type>` variables): Armada to India 15 years after its Gold Coast
castle (Mina 1482, Calicut 1498); a country without its own Gold Coast castle goes from the Age of Reformation once the
cape route is known (another country reached India, or the Cape of Good Hope is discovered; EIC 1600, VOC 1602);
Armada of Conquest 8 years after India (Goa 1510); Armada to Malacca 10 years after India
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
- How strong an area preference is in the colony score (decoded, partly inferred): the score adds score x the area's
  preference value; the `colonize_bias` trigger read Castile's "avoid Europe" value in Arkhangelsk at 0.05 or below,
  yet at -0.9 Castile kept chartering Kuloy, Mezen and Zavolochye through 1498. `pp_colonizer_avoid_europe` is now
  -2.0, which makes the score negative there whichever way the value is stored. The other exploration preferences
  (routes, stations: +5) multiply the score of their areas several times.
- Expeditions feed this: footholds extend presence and range (Castle-Factories, colonial range modifiers), so charters
  follow the stations the expeditions open.

## Results (2026-10-08)

Test setup: run 40148576 (`pp_exp1_*`, 1337-1452, observer, colonizers all alive in 1452: Castile 250 Iberian
locations, Portugal 67, England 147, France 210, Holland 16), then from its 1452 save with this branch, historical AI
personalities restored by console (the preset that new games inherit re-rolls them each age, see
`country_finetunes.md`) and the Iberian truce applied by console. Expeditions were launched by the AI alone.

Run pp_exp4 (1452-1582), year each expedition arrived:

| Expedition | AI countries (year) | What they got |
| --- | --- | --- |
| Gold Coast Factory | Portugal 1458, Aragon 1460, Castile 1464, Brittany 1541, Holland 1565, England 1566, France 1571 | Fortalezas on the Benin and Senegambia coasts (Ughoton, Ikorundu, Cacheu, Tankular, Ikosi, Bintang, Bafata) |
| Armada to India | Portugal 1474, Aragon 1490, Castile 1491, Brittany 1565, Holland 1573 (one Dutch armada lost 1570), England 1575 | Fortalezas at Kannur, Goa, Diu; Castile's Konkan trade company |
| Armada to Malacca | Portugal 1490, Aragon 1503, Castile 1568, Brittany 1580 | Portugal's war on Temasek (SNG) and its allies, 1490 |
| Armada of Conquest | Portugal 1495, Castile 1501, Aragon 1574, Brittany 1577 | wars for the Malabar/Gujarat market centres |
| Voyage to the Spice Islands | Portugal 1501, Aragon 1532 | Ternate Fortaleza under Portugal's Moluccas trade company (still a trade company in 1582) |
| Embassy to the Celestial Court | Portugal 1507 | Macau port granted, Portugal's Guangdong trade company (lost by 1547 when the Chinese owner changed) |
| The Manila Galleon | Castile 1548 | Fortaleza at Maynila |
| Company Voyage | none by 1582 (no AI had trade_companies_advance or chartered_companies yet) | |

The armadas' wars in pp_exp4 won no market centre: the landed regiments spawned empty (fixed: full strength) and the
first target was the biggest market (fixed: weakest owner). Landing tests from the 1487 save: against Jhalawad (Khambat,
68 locations, six allies) the war ended without gain; with the weakest-owner target and the surrender rule
(owner below half our tax base) Portugal took Kozhikode, the Malabar market centre, in 1487 and kept it.

Colonization in pp_exp4: Castile chartered Hispaniola, Venezuela and the Guianas, Portugal Brazil (Paraiba to the
Amazon), Portugal's Cape Verde and Guinea colonial nations chartered the Guinea coast; no colonizer charter in Europe
after the avoid-Europe change (Castile had chartered Kuloy, Mezen and Zavolochye until then).

Run pp_exp5 (same 1452 start, all fixes; AI alone): Portugal Gold Coast 1458, India 1474, Armada to Malacca 1490 ->
Temasek, the market centre of the straits, surrendered (Portugal's Castle-Factory there), Armada of Conquest 1492 ->
Kozhikode, the Malabar market centre, surrendered (Castle-Factory); Aragon's Armada of Conquest 1499; Castile India
1491. The market centres stay Portuguese (checked 1502).
By 1532 in pp_exp5: Portugal's Spice Islands 1508 (Moluccas trade company at Ternate, a `trade_company` in 1512) and
China embassy 1510; Castile's Malacca 1503, Malabar war 1505, Spice Islands 1509 and China embassy 1509; both China
embassies were refused (30 % before the Age of Reformation). Castile took Granada (Reconquista casus belli). Portugal
kept Kozhikode; Temasek fell to a Johor splinter in a 1528 war.

## Open points

- Portugal's Moluccas company dissolved between 1512 and 1517 in pp_exp5 (reproduced within 30 days of loading the 1512
  save); a second, Castilian Fortaleza stood in the same harbour then. Fixed since: one foothold per harbour, fleets
  re-target, companies only on their own Fortaleza. The dissolution itself is not explained (a war with the host
  breaking trade access is the likeliest cause; check with a save where the company's overlord goes to war with the
  harbour's owner).
- The Macau port depends on the host: in pp_exp4 the Guangdong company and the port were gone by 1547 after the Chinese
  owner of Xiangshan changed.
- No AI made a Company Voyage by 1582 (no AI had `trade_companies_advance` or `chartered_companies`); test from a later
  save or with the advances given by console.
- Landing wars against large owners end in white peace; only the surrender rule (owner below half our tax base) takes
  market centres so far.
