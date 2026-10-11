# Trade expeditions (branch `trade-expeditions`, 2026-10-11)

Three expensive, gated expeditions that any colonial power (AI and player alike) can send for a station on the coasts
of Africa, India and the Far East. Unlike the parked `expeditions` branch (eight tag-flavoured chain voyages), these
are generic: each voyage picks the best free historical site when it sails, and the host on arrival decides whether
the station is bought, licensed, fought for or refused. They use EU5 1.4's expedition system (`common/expedition_types`,
the `start_expedition` generic action), so the AI launches them on its own.

## Files

| File | What |
| --- | --- |
| `in_game/common/expedition_types/pp_trade_expeditions.txt` | the three types: gates, start, arrival, AI weights |
| `in_game/common/scripted_effects/pp_trade_expedition_effects.txt` | site choice, arrival decision, settle/buy/war/licence, castle and garrison, owner-change hook, traces |
| `in_game/common/on_action/pp_trade_expedition_on_actions.txt` | `on_location_changed_owner`: castle for a town won in a landing war, station change log |
| `main_menu/common/static_modifiers/pp_trade_expedition_modifiers.txt` | bastion / star-fort / fortress works of a castle by age |
| `in_game/common/scripted_triggers/pp_trade_expedition_triggers.txt` | colonial power, free site, hosts, the site lists |
| `in_game/common/script_values/pp_trade_expedition_values.txt` | costs (scaled by yearly income), prices, chances, site score |
| `in_game/common/subject_types/pp_te_company.txt` | Chartered Company: land-holding company subject that holds castle towns in India and the Far East |
| `in_game/common/building_types/pp_trade_expedition_buildings.txt` | Castle and Factory (own harbour), Factory (licence in a host's port) |
| `in_game/common/area_preferences/pp_trade_expedition_preferences.txt` | conquest preference per region after a landing war |
| `in_game/events/pp_trade_expedition_events.txt` | outcome events (`pp_trade_expedition.1`-`.5`, `.20` lost at sea) |
| `main_menu/localization/english/pp_trade_expeditions_l_english.yml` | all text |
| `tests/test_trade_expeditions.py` | every reference exists, site lists agree, costs scale with income, no numbers in text |

## The three expeditions

| Type | Opens | Sites (historical) | Outcomes |
| --- | --- | --- | --- |
| Castle on the African Coast (`pp_te_africa`) | Age of Discovery; East Africa once the Cape route is known (Cape of Good Hope discovered or Age of Reformation) | Arguin, the Gambia, Cacheu, Bissau, Axim, Accra, Ughoton, the Calabars, Sao Tome, Soyo, Loango, Cabinda, Luanda; Sofala, Kilwa, Mozambique, Mombasa, Malindi, Zanzibar, Quelimane, Inhambane, Lamu, Pate | settle / buy / war / licence / refusal |
| Factory in the Indies (`pp_te_india`) | Age of Discovery with the Cape route known and an own African station, or the Age of Reformation; tax base 200+ | Goa, Cochin, Calicut, Cannanore, Cranganore, Quilon, Mangalore, Bhatkal, Bombay, Bassein, Daman, Diu, Surat, Madras, Pondicherry, Karaikal, Negapatam, Masulipatnam, Galle, Colombo (Kotte), Jaffna, Balasore, Hooghly (Satgaon), Chittagong | buy / war / licence / refusal |
| Embassy to the Far East (`pp_te_far_east`) | an own Indian station, or the Age of Reformation with an African one, or the Age of Absolutism; Cape route; tax base 300+ | Macau (Xiangshan), Canton, Quanzhou, Amoy (Tong'an), Ningbo (Yin), Liampo (Dinghai), Zeelandia (Siraya), Keelung (Ketagalan), Nagasaki (Nishisonogi), Hirado (Minamimatsuura), Manila, Malacca, Banten, Sunda Kelapa | settle (Taiwan) / lease (rare) / war (rare) / licence / refusal |

All three: `unique = yes`, `repeatable = yes`, at most three African, three Indian and two Far Eastern stations per
country, 15/20/25 years between voyages of one kind (counted from the arrival), never while a great power is at war
with the country. A fleet that finds no free site at departure sails for the Cape and looks again on arrival.

### Who may send them (`pp_te_colonial_power`)

A sovereign country with a capital in Europe, the `colonies` advance and an ocean-going advance (open-sea exploration,
explorer commissions, Portugal's pursuing the waves, colonial charters), a harbour on the Atlantic, North Sea or
Baltic coasts of the west (Iberia, France, the British Isles, the Low Countries and North Germany, Scandinavia, the
Atlantic islands), a sea-going realm (150+ locations or 8+ ports on its capital's continent facing open sea, the test of
the AI colonial charter gate) and a tax base of 75+. In the 1612 save of run cf982ee6 this admits Portugal, England,
France (Bourbon), Brittany, Ulster, Mecklenburg and Pomerania-Wolgast; Castile and Denmark fail on the treasury that
year. The first draft without the Europe and ocean test let the Ottomans, Ming, Korea, Vijayanagara, Orissa and the
Papacy launch African voyages within a year.

### Cost

Costs follow the country's own yearly income (`yearly_gold`), so they stay as heavy when the colonial powers grow rich
(run cf982ee6: Portugal 113 gold a month in 1452, 254 in 1602, 670 in 1837; England 222 in 1577, 2,537 in 1802):

| | Fitting out (paid at departure) | Treasury needed | Floor |
| --- | --- | --- | --- |
| Africa | a quarter of a year's income | 1.25 x the cost | 300 |
| India | a quarter of a year's income | 1.25 x the cost | 600 |
| Far East | 0.3 of a year's income | 1.25 x the cost | 900 |

On arrival the price of the land (a quarter of a year's income, at least 150) or the licence gifts (a tenth, at least
60) go to the host. The AI treasuries of run cf982ee6 hold about 0.2-0.5 of a year's income (1612: Portugal 0.42, England
0.49, France 0.36; 1712: Portugal 0.35, France 0.37, Great Britain 0.21), so the treasury gate (0.31 of a year for Africa
and India, 0.375 for the Far East) opens only when a treasury runs high, and a voyage takes most of it. At 0.4 and 0.5
of a year for India and the Far East (first draft) no Far East voyage sailed in 25 years from 1612.

## Arrival: the host decides (`pp_te_arrive_effect`)

If another country took the harbour while the fleet was at sea, the fleet sails on to the best free site of the same
expedition. Then:

1. **No owner** (Arguin 1445, Zeelandia 1624): the country takes the location, raises the Castle and Factory and
   lands the garrison.
2. **The host sells** (Christiansborg 1661, Madras 1639, Pondicherry 1674): chance `pp_te_cede_chance` x the
   expedition's factor (Africa 1, India 0.8, Far East 0.4): base 30, +30 if the host is weak (not a great power, under
   half our tax base), +15 if it is at war, x0.3 if it is a great power or richer than us, never its capital or one of
   its last two towns. The price goes to the host, both sign a 20-year truce, and the castle and garrison go up.
3. **A weak host refuses** (Goa 1510, Kilwa 1505): with Africa 25 %, India 35 %, Far East 15 % the fleet lands twice the
   garrison, declares war with `cb_conquer_province` for the town's province and the country gets a conquest
   preference for the region (`pp_te_hold_<region>`, needed by `peace_treaties/pp_cede_preferred_location.txt` to let
   the AI take a town away from its own land).
4. **The host licenses trade** (Surat 1612, Hirado 1609, Canton): Africa 60 %, India 75 %, Far East 55 % (+15 for a
   host that is not strong): gifts, `trade_access` and a Factory (foreign building of the crown) in the port. The
   Factory stands while the host grants trade access (`own_or_overlord_relation_needed = trade_access`); a war between
   them closes it.
5. **Refused** (Tuen Mun 1521): the cost is lost, the cooldown runs.

## Holding the station

- **Castle and Factory** (`pp_te_factory`): fort level 3 (between castle and bastion; + bastion, star-fort or fortress
  works when founded in the Ages of Reformation, Absolutism or Revolutions: fort level 4, 6, 8), `local_garrison_size`,
  `local_defensive`, zone of control, `is_indestructible` (the AI demolishes forts to save money; this one stays), plus
  merchant capacity, merchant power, maritime presence, market access and development growth.
- **Garrison**: two regiments (three from the Age of Reformation, four from Absolutism) of heavy infantry and shot,
  landed at full strength. A town won by a landing war gets the castle and garrison when it changes owner
  (`on_location_changed_owner`).
- **Treaty**: a bought site comes with a 20-year mutual truce with the seller.
- **Chartered companies** (`subject_types/pp_te_company.txt`): a castle town in India or the Far East (bought, settled
  or won) goes to the country's Chartered Company for that region, a land-holding subject with its own governor
  (the English company at Madras, the Dutch at Batavia); later towns in the region join it, and the company holds the
  garrison. Its overlord joins its defensive wars; it cannot declare wars, be annexed or be offered in diplomacy.
  African castles stay with the crown. Vanilla's `trade_company` (a building subject, as `create_building_subject`)
  was tried first: script-made ones died within three months in Indian regions in every test and took their Factory
  with them (runs 3 and 5), so licences keep their Factory under the crown.
- **Peace deals**: PP's AI peace deals only take land connected to the winner (`AI_CONQUER_TREATY_DESIRE_ADJECENT`), so a
  European rival at war in Europe does not take a station overseas unless it holds land next to it; the threat is the
  station's neighbours.

## AI

- Launch: once a month per AI country with at least 99 political influence; each type is looked at every third month
  with `ai_chance_to_check` 0.15 (about once in two years once the gates are open); leader from the whole court
  (`ai_leader_source_list`, any adult who is not the ruler and holds no other expedition or exploration); utility 30.
  Gold, debt and saving mode do not enter the engine's choice, so the treasury gate in `can_start` is the money gate
  (decode: private `notes/expedition_ai_140.md`).
- Site choice (`pp_te_site_score`): an unclaimed coast first (+2,000), then a weak host (+600), then the most populous
  port; x2 next to an own location, x1.5 in a region where the country already holds land.

## Testing trace

Country variables `pp_te_year_<stage>_<kind>` (stage start, end, gain, refused, fail) and global lists
`pp_te_log_<stage>_<kind>`; every station in the global list `pp_te_all_footholds` with location variables
`pp_te_foothold_of` (founder) and `pp_te_foothold_year`. Console run files (in `Documents/.../run/`, not in the repo):
`pp_te_dbg.txt` (gates per colonial power, `PPTEDBG` lines), `pp_te_trace.txt` (`PPTETL`/`PPTETF`/`PPTETO` per station:
name, founder and year, held, castle standing, current owner; `PPTETC` per country: years of each stage),
`pp_te_force.txt` (force starts). `[THIS.GetCountry.GetTag]` prints a tag in a country scope; scope-name loc
(`SCOPE.sCountry(...)`) prints nothing in run files.

## Results

All runs: observer, PP Main Test playset (PP + Observer Auto Pause), loaded from copies of run cf982ee6's autosaves
with autosave switched off; the AI alone launches (no forced starts unless noted).

### Run 2: 1612-1637 (base autosave _47, Age of Reformation)

Gates open at the start: Africa Portugal, Pomerania-Wolgast, Mecklenburg, France, Brittany, Ulster, England; India
Mecklenburg. AI check chance 0.5, India and Far East still at 0.4/0.5 of a year (so no Far East voyage).

| Year | Station | Founder | How | 1637 |
| --- | --- | --- | --- | --- |
| 1612 | Ughoton (Benin) | France | licence (Factory) | held |
| 1613 | Lamu | Brittany | bought (castle) | held |
| 1613 | Mombasa | Pomerania-Wolgast | licence | held |
| 1613 | Zanzibar | Portugal | landing war, won the same year (castle on capture) | held |
| 1614 | Cacheu | Mecklenburg | bought (castle) | held: 1637 Mecklenburg's new colonial subject (capital Cacheu) |
| 1615 | Bissau | Frisia | bought (castle) | held |
| 1618 | Madras | France | bought (castle) | held |
| 1618 | Diu | Mecklenburg | licence + trade company (Saurashtra) | lost by 1624: the company and its Factory were gone |
| 1621 | Galle | Castile | licence + trade company (Sailan) | lost 1636 when the town changed hands |
| 1627 | Jaffna | Novgorod | bought (castle) | held |
| 1628 | Malindi | Portugal | licence | held |
| 1629 | Pate | England | bought (castle) | held |
| 1631 | Inhambane | Mecklenburg | licence | held |
| 1632 | Quelimane | Aragon | licence | held |

- 11 countries sent 15 voyages (11 African, 4 Indian); 14 stations, 12 held after up to 25 years; every castle stayed in
  its founder's realm. Refused: Ulster 1616, Ireland 1631. Landing wars: Portugal 1613 (won), Novgorod 1629, Castile and
  Frisia 1632 (all three ended without the town).
- No local power attacked a station in 25 years.
- Trade: each founder trades out of its station's market (1636: England 10 routes of size 22 through Pate's market,
  Aragon 4.2, Portugal 2.4, Mecklenburg 1.3, Brittany 1.0); founder merchant capacity in station markets 0.6-1.6.
- The hosts keep building in station towns (Madras 59 -> 71 building levels, Bissau 7 -> 18, Cacheu 10 -> 24 from 1620
  to 1636); castle towns stay at very low control (0.0-0.13) as far exclaves.

### Run 3: 1712-1732 (base autosave _27, Age of Absolutism), with a forced attack in 1720

Gates at the start: Africa Portugal, Novgorod, Mecklenburg, France, Frisia, Castile, Ireland; India Portugal,
Mecklenburg, France (after the India cost went down to a quarter of a year; at 0.3 none passed). Great Britain held
only 0.21 of a year in the treasury.

- 12 countries sent 23 voyages (12 African, 9 Indian, 2 Far Eastern); 21 stations by 1732. Far East: France refused
  1716; Mecklenburg\x27s 1719 fleet vanished without arriving (it had found no free site and its fallback waypoint was the
  inland capital; fixed: it now sails for the Cape and looks again there).
- New castles: Lamu, Ughoton, Madras, Satgaon (Hooghly, Portugal), Pate, Kozhikode (Great Britain), Kotte (Colombo,
  Brandenburg), Bissau, Kilwa, Quelimane, Cacheu. Licences: Zanzibar, Mombasa, Malindi, Mozambique, Inhambane, Sofala,
  the Gambia, and in India Galle, Jaffna, Daman.
- **Forced attack 1720** (console : each castle\x27s non-European neighbour declares war on its
  owner with a casus belli on the station\x27s province): Ajuran on Mecklenburg\x27s Lamu - war over by 1723, castle kept;
  Benin on France\x27s Ughoton - war over, castle kept (in 1726 the town passed to France\x27s own new subject); SMV on
  France\x27s Madras (fort level 3, three regiments) - occupied by 1723, ceded in 1726. So 2 of 3 held a full war against
  a neighbour with no help from home. Since then the castle is built to the standard of its age (bastion works from the
  Age of Reformation, star-fort works from Absolutism, a fortress in the Age of Revolutions) and the Absolutism garrison
  is four regiments.
- **All three Indian licences died with their trade company** (Galle and Jaffna within a year, Daman), while all seven
  African licences (no company) stood. Side-by-side test in the same session: three companies made by console at
  Zanzibar, Mombasa and Malindi - the one given the overlord\x27s ruler lived, the two created without a ruler died within
  150 days and took their Factories with them; a company with a newly created governor (Mozambique) and one whose
  shared ruler was killed (Inhambane) both lived 300+ days. The effect passed the overlord\x27s ruler with , which
  is empty in a regency or for some republics. Fixed: every company gets its own governor, and only a country with an
  advance that unlocks the type founds one (Pomerania-Wolgast\x27s test company lost its type after a year without it).
- Natural attacks by locals: none in 20 years (45 run-years so far over runs 2 and 3).

### Run 4: 1487 (base autosave _72, early Age of Discovery)

Gate check before the ocean-advance test: Denmark, Norway, Novgorod, Holland, Castile, Aragon, Brittany, England and
the Teutonic Order could all send African voyages in 1487, Portugal not (no gold). Only Portugal, Castile and Aragon
had an ocean-going advance (open-sea exploration, explorer commissions, colonial charters); with that test added only
Castile and Aragon pass in 1487 (Portugal again short of gold).

Run 4, 1487-1517 (AI alone, all fixes up to the ocean-advance gate):

| Year | Station | Founder | How | 1517 |
| --- | --- | --- | --- | --- |
| 1490 | Cacheu | Aragon | licence (Factory) | held (town passed to Mali 1494, the Factory stayed) |
| 1494 | Ughoton | Portugal | bought (castle) | held |
| 1509 | Mombasa | Portugal | licence | held |
| 1511 | Bissau | Aragon | licence | held |

- Only the Iberian crowns acted in 30 years: Portugal, Aragon (as in run cf982ee6 itself, where Aragon became the West
  African colonizer), Castile (refused 1505). Portugal reached India in 1496 and was refused (da Gama 1498), and sailed
  again in 1516.
- All 4 stations held for up to 27 years; no local attacked them.

### Run 5: 1712-1733 again (company governor, castles of their age), forced attack in 1721

- 10 countries, 21 voyages (9 African, 7 Indian, 3 Far Eastern); Far East voyages now land: France licensed at Manila
  1716, Mecklenburg at Hirado 1720, Pomerania-Wolgast at Nagasaki 1725.
- **Forced attack 1721:** Bhopal on Portugal\x27s Satgaon (Hooghly; castle with star-fort works, four regiments). Held for
  the 12 years of the run.
- Ireland\x27s Mombasa castle (1714) went in 1729 to an Irish revolt country: a rebellion at home took the overseas
  station with it.
- **Every Asian licence still died with its trade company** (Chittagong, Galle, Kotte, Madras, Manila, Hirado, Nagasaki),
  even with the governor fix, while the African Factories held. Side-by-side test in the same session: a company with a
  new governor at Surat and one made 30 days after its Factory at Goa both died within 90 days with their Factories;
  crown Factories (no company) at Kochi and Mangalore and a company at Sofala lived on. The engine\x27s own test
  \x60subject_can_be_created_by\x60 said yes for France in the Deccan. Cause not found; the licence now keeps the Factory
  under the crown everywhere (no company).

### Run 6: 1712-1737 (crown Factories, no companies; with the later reverted treasury check on purchases)

- 11 countries, 21 voyages (11 African, 8 Indian, 2 Far Eastern); **19 stations, all 19 held in 1737** (Zanzibar\x27s town
  changed hands in 1735, the Factory stayed). The Asian crown Factories that used to die with their companies all
  stood: Chittagong, Madras, Galle, Satgaon, Kotte, Daman, and France\x27s Far East licence at Dinghai (Liampo, 1721);
  Mecklenburg was refused in the Far East (1722).
- Trade (1732 save): founders run trade routes out of their station markets - Castile 9 routes (size 18.2), England 11
  (15.3), Portugal 11 (12.0), France 4 (8.5), Sweden 3 (4.1), Brittany 3 (2.7), Mecklenburg 2 (2.0); founder merchant
  capacity there 0.6-1.6 per station. The hosts keep building in licensed towns (Satgaon 246 building levels, Malindi
  217, Chittagong 178).
- Only 2 of 18 stations were castles: a purchase also had to find its price in the treasury on arrival, and the
  fitting out had already taken most of it. That check was reverted (purchases may take the buyer into debt, as in
  runs 2-5, where 8 of 14 and 11 of 21 stations were castles).

### Run 7: 1612-1632, final code (confirmation)

| Year | Station | Founder | How |
| --- | --- | --- | --- |
| 1613 | Diu | Brittany | castle |
| 1613 | Galle | Portugal | Factory |
| 1614 | Lamu | Portugal | castle |
| 1616 | Satgaon (Hooghly) | Mecklenburg | Factory |
| 1616 | Ughoton | Mecklenburg | castle |
| 1617 | Mombasa | Ulster | Factory |
| 1619 | Dinghai (Liampo, Zhoushan) | Mecklenburg | castle |
| 1619 | Zanzibar | Brittany | Factory |
| 1620 | Cacheu | Castile | Factory (town passed to Mali 1622, Factory stayed) |
| 1623 | Yin (Ningbo) | Portugal | Factory |
| 1624 | Jaffna | Castile | castle |
| 1625 | Madras | France | castle |
| 1625 | Malindi | Denmark | Factory |
| 1629 | Pate | Portugal | castle |
| 1629 | Bissau | England | castle |

- 9 countries, 17 voyages (9 African, 5 Indian, 3 Far Eastern); refusals: Pomerania-Wolgast (Africa 1613), Brittany (Far
  East 1618), France (Africa 1622). **15 stations, 8 castles and 7 Factories, all 15 held in 1632.**
- Trade out of station markets in 1632: England 7 routes (size 11.9), Castile 6 (6.4), Brittany 3 (2.5), Portugal 3
  (2.4), Ireland 2 (2.3), Mecklenburg 2 (1.3).

### Chartered companies and a European war (1632 save of run 7, console set-up, 8 years)

- Four land-holding chartered companies made by console at the castle towns Diu (Brittany), Dinghai (Mecklenburg),
  Jaffna (Castile) and Madras (France): all four were still companies of their crowns in 1640. Jaffna was taken by
  rebels in 1638 and was back with its company by 1640.
- Forced war Castile on Portugal (`cb_war_from_event`): over within two years; neither side's overseas stations
  changed hands (Portugal kept Lamu and Pate). This is PP's peace rule at work (`AI_CONQUER_TREATY_DESIRE_ADJECENT`,
  already in 0.10): a winner takes only land connected to its own.
- Player side: `tag POR` and the outcome event fired for the player; the console showed "Portugal gets the Event
  'A Harbour Bought'" (title localized). The event window itself did not show in that debug session, so the
  event and panel texts are still unseen in game.

### Runs 8 and 9: 1712 with chartered companies (AI alone)

- Run 8 (stopped at 1722): France's company at Madras formed in 1719 and held. Portugal's castle at Hooghly (Satgaon)
  went to its new company in 1716, and Orissa attacked the company in February 1717 and took the town the same year:
  the one-town company is the war target and makes its own peace, while crown-held castles survived such wars (run 5).
- Since then `ai_scripted_expansion_score/pp_te_company_protection.txt` makes every AI attacker count a chartered
  company at a quarter (attacking it means war with its crown).
- Run 9 (1712-1727, with that weight): 11 countries, 22 voyages (11 African, 8 Indian, 3 Far Eastern); 19 stations,
  18 held. Chartered companies: France at Madras (1717, held ten years), Mecklenburg at Chittagong (1723), Sweden at
  Colombo (1726) held; Brittany's at Hooghly (1721) fell to Orissa again in 1722. Orissa (tax base about 2,500)
  next to Hooghly is the one place where a company does not last.

### Run 10: run 9 continued 1727-1767 - do the colonizers station or ferry forces?

The yearly trace now counts, per station, the founder's (and its subjects') regiments in the town, in the
neighbouring land and sea locations, and anywhere on land in the station's region, and its ships next to the station
(`pp_te_trace_forces_effect`, `PPTETU` lines).

| Year | Stations (held) | Castles | Regiments at stations | Stations with troops | Regiments in the regions | Ships next to stations |
| --- | --- | --- | --- | --- | --- | --- |
| 1728 | 20 (19) | 9 | 25 | 5 | 25 | 0 |
| 1730 | 22 (21) | 11 | 36 | 7 | 44 | 16 |
| 1735 | 22 (20) | 11 | 15 | 5 | 15 | 0 |
| 1739 | 23 (21) | 12 | 41 | 6 | 41 | 0 |
| 1745 | 28 (26) | 12 | 5 | 4 | 5 | 0 |
| 1755 | 32 (30) | 13 | 10 | 4 | 13 | 1 |
| 1760 | 32 (30) | 13 | 8 | 3 | 8 | 16 |
| 1767 | 34 (32) | 13 | 3 | 2 | 3 | 1 |

- **No.** The AI neither keeps the landed garrisons nor sends troops. Regiments appear only when a new expedition lands
  (1730, 1738) and are gone within one to three years (disbanded or withdrawn); the chartered companies own no regiments
  at all within a few years (1727 save: none). Regiments in the station regions equal those in the station towns: no
  field army is ever moved into a region with a station. A founder fleet lay off a station twice for two years (1730-1732,
  1760-1761); otherwise no ships.
- The stations still hold (32 of 34 in 1767, 13 castles) because nobody attacks them: the castle, the truce, PP's
  connected-land peace rule and their small value make them poor targets, not their defence.
- Possible fix (not built): defenders that do not depend on an AI decision, e.g. a much larger fort garrison on the
  Castle and Factory (`local_garrison_size`, regenerating), or locally raised soldiers (the castle employing soldier
  pops).

## Conclusions

- **Used by the AI, several but not too many.** 1480s: only the Iberian crowns (the ocean-advance gate). 1610s-1730s:
  9-12 countries per 20-25 years, i.e. every Atlantic and Baltic power of this world with an ocean advance, a tax base
  of 75+ (200 for India, 300 for the Far East) and a full treasury, about one voyage per country every five years. In
  this world that includes the mid-sized northern states (Mecklenburg, Pomerania-Wolgast, Frisia, Brittany), the
  analogues of Brandenburg, Courland and the Ostend Company. If that is too many, raise the African tax base or lower
  the per-country caps (3/3/2).
- **Costs follow wealth.** A quarter of a year\x27s income for Africa and India, 0.3 for the Far East, plus the land
  price (a quarter) on a purchase: Portugal\x27s African voyage costs about 430 gold in 1487, 810 in 1612, 1,410 in 1712;
  France\x27s about 4,300 in 1712. The treasury gate (1.25 x the cost) opens only at a treasury peak.
- **Staying power without define changes.** Across all runs (roughly a thousand station-years), no station fell to a
  local power except in the forced wars; the saves checked (1632, 1636, 1732) show no war between a founder and a local
  host. Castles were lost only to a home rebellion (Ireland\x27s Mombasa) or a forced war before the age works
  (Madras, fort level 3); under forced wars Lamu, Ughoton and the star-fort Satgaon held. Licensed Factories stand while
  the host grants trade access. What protects them: the castle of its age and the landed garrison, the 20-year truce
  with the seller, and PP\x27s existing peace define \x60AI_CONQUER_TREATY_DESIRE_ADJECENT\x60 (0.10), which keeps a far-away
  European winner from taking a station in a peace deal. No new define was needed.
- **Trade builds up.** Every founder trades out of its station\x27s market within a few years (up to 11 routes for
  England), and the host towns of licensed Factories keep growing (Satgaon, Malindi, Chittagong 170-250 building
  levels).
- **Trade companies:** castle towns in India and the Far East go to a land-holding Chartered Company of the crown
  (one per region). 3 of 4 AI companies held in run 9 and all 4 console-made ones in the 1632 test; a very strong
  neighbour (Orissa at Hooghly) takes a fresh company within a year. If that is too weak, the alternative is to keep
  castles under the crown, as in runs 2-7, where they held better.
- **Open:** script-made vanilla trade companies (building subjects) die in Asian regions (cause unknown); licences keep
  their Factory under the crown. Landing wars rarely take the town (2 of 7 won: Portugal at Zanzibar, Ireland at Mombasa). Far East: a strong Chinese owner mostly refuses or
  licenses, as intended. No player-side check of the events and panel texts in game yet.
