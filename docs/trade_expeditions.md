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
| `in_game/common/scripted_effects/pp_trade_expedition_effects.txt` | site choice, arrival decision, settle/buy/war/licence, castle and garrison, trade company, traces |
| `in_game/common/scripted_triggers/pp_trade_expedition_triggers.txt` | colonial power, free site, hosts, the site lists |
| `in_game/common/script_values/pp_trade_expedition_values.txt` | costs (scaled by yearly income), prices, chances, site score |
| `in_game/common/building_types/pp_trade_expedition_buildings.txt` | Castle and Factory (own harbour), Factory (licence in a host's port) |
| `in_game/common/area_preferences/pp_trade_expedition_preferences.txt` | conquest preference per region after a landing war |
| `in_game/common/advances/pp_trade_expedition_advances_adjustments.txt` | Age of Discovery ocean advances also unlock the trade company subject type |
| `in_game/events/pp_trade_expedition_events.txt` | outcome events (`pp_trade_expedition.1`-`.5`, `.20` lost at sea) |
| `main_menu/localization/english/pp_trade_expeditions_l_english.yml` | all text |
| `tests/test_trade_expeditions.py` | every reference exists, site lists agree, costs scale with income, no numbers in text |

## The three expeditions

| Type | Opens | Sites (historical) | Outcomes |
| --- | --- | --- | --- |
| Castle on the African Coast (`pp_te_africa`) | Age of Discovery; East Africa once the Cape route is known (Cape of Good Hope discovered or Age of Reformation) | Arguin, the Gambia, Cacheu, Bissau, Axim, Accra, Ughoton, the Calabars, Sao Tome, Soyo, Loango, Cabinda, Luanda; Sofala, Kilwa, Mozambique, Mombasa, Malindi, Zanzibar, Quelimane, Inhambane, Lamu, Pate | settle / buy / war / licence (no company) / refusal |
| Factory in the Indies (`pp_te_india`) | Age of Discovery with the Cape route known and an own African station, or the Age of Reformation; tax base 200+ | Goa, Cochin, Calicut, Cannanore, Cranganore, Quilon, Mangalore, Bhatkal, Bombay, Bassein, Daman, Diu, Surat, Madras, Pondicherry, Karaikal, Negapatam, Masulipatnam, Galle, Colombo (Kotte), Jaffna, Balasore, Hooghly (Satgaon), Chittagong | buy / war / licence + trade company / refusal |
| Embassy to the Far East (`pp_te_far_east`) | an own Indian station, or the Age of Reformation with an African one, or the Age of Absolutism; Cape route; tax base 300+ | Macau (Xiangshan), Canton, Quanzhou, Amoy (Tong'an), Ningbo (Yin), Liampo (Dinghai), Zeelandia (Siraya), Keelung (Ketagalan), Nagasaki (Nishisonogi), Hirado (Minamimatsuura), Manila, Malacca, Banten, Sunda Kelapa | settle (Taiwan) / lease (rare) / war (rare) / licence + trade company / refusal |

All three: `unique = yes`, `repeatable = yes`, at most three African, three Indian and two Far Eastern stations per
country, 15/20/25 years between voyages of one kind (counted from the arrival), never while a great power is at war
with the country.

### Who may send them (`pp_te_colonial_power`)

A sovereign country with a capital in Europe and the `colonies` advance, a harbour on the Atlantic, North Sea or
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
   host that is not strong): gifts, `trade_access`, a Factory (foreign building) in the port and, in India and the Far
   East, a trade company for the region (as vanilla `create_building_subject`; it runs the country's foreign
   buildings there).
5. **Refused** (Tuen Mun 1521): the cost is lost, the cooldown runs.

## Holding the station

- **Castle and Factory** (`pp_te_factory`): fort level 3 (between castle and bastion), `local_garrison_size`,
  `local_defensive`, zone of control, `is_indestructible` (the AI demolishes forts to save money; this one stays), plus
  merchant capacity, merchant power, maritime presence, market access and development growth.
- **Garrison**: two regiments (three from the Age of Reformation) of heavy infantry and shot, landed at full strength.
- **Treaty**: a bought site comes with a 20-year mutual truce with the seller.
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
