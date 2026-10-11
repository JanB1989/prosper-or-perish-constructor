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
| India | 0.4 of a year's income | 1.25 x the cost | 600 |
| Far East | half a year's income | 1.25 x the cost | 900 |

On arrival the price of the land (a quarter of a year's income, at least 150) or the licence gifts (a tenth, at least
60) go to the host. In the 1612 save the colonial powers held 0.2-0.9 of a year's income in the treasury, so a voyage
empties most of it.

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

(filled in below as the tests run)
