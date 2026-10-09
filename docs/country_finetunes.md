# Country finetunes

Hand-tuned changes for single countries, one entry each: what and why.

- **France** (2026-10-05, `pp_estate_privilege_adjustments.txt`): Great Offices of the Crown +10 points noble max tax.
  Why: its powerful nobles were taxable at only 4-5 %, so the crown went bankrupt and France fell apart in observer runs.
- **France +500, Ottomans +1,500, Byzantium -1,000 starting gold** (2026-10-05, `on_action/pp_country_finetunes.txt`).
  Why: France and the Ottomans went bankrupt early in observer runs; Byzantium took the Ottoman land.
- **Castile/Spain aimed at the Reconquista, then the Maghreb; no Castile-Portugal wars meanwhile** (2026-10-07;
  replaces the +200 Iberian Concord opinion of 2026-10-06, which the AI's war-target choice ignores).
  `ai_scripted_expansion_score/pp_reconquista.txt`: CAS/SPA and POR `never_attack` each other while a Muslim country
  has its capital in Iberia or the Maghreb; CAS/SPA +30 target score on Muslim Iberia (and the Maghreb, see below).
  `ai_scripted_expansion_target/pp_reconquista.txt`: those countries become CAS/SPA war targets across the strait
  (after 36 months of peace). `events/pp_reconquista_events.txt`: once no Muslim capital is left in Iberia, CAS/SPA get
  the conquest preference `pp_castile_conquer_maghreb` (x10). At start CAS gets vanilla's `castile_no_portugal_conquest`
  (vanilla: only after Rio Salado) and POR the mirror `pp_portugal_no_castile_conquest` (`on_action/pp_country_finetunes.txt`).
  Why: Castile conquered Portugal in every game; +100 opinion for 150 years and +200 for 100 years did not stop it.
- **France +3 diplomatic reputation** (2026-10-06, `pp_estate_privilege_adjustments.txt`, Great Offices of the Crown).
  Why: Jan's call, on the same privilege as the noble tax; vanilla privileges give at most +2.
- **Colonizers daisy-chain down Africa** (2026-10-07, `area_preferences/pp_colonizer_preferences.txt`,
  `on_action/pp_country_finetunes.txt`, `scripted_effects/pp_area_preference_effects.txt`). For AI POR, CAS/SPA,
  ENG/GBR, FRA, HOL/NED, one day after vanilla's setup at game start and every new age: vanilla's
  `avoid_african_colonization` (all of continent Africa, which also holds the sea lanes along it) becomes
  `pp_colonizer_avoid_africa` (-0.9 on the African land areas without the stations), plus +5 preferences by age:
  POR route west + Madeira/Azores (age 2), route round the Cape + Cape Verde + St Helena (age 3); CAS/SPA Canaries
  (age 2); ENG/FRA/HOL route west + round the Cape (age 4); ENG St Helena (age 4), the Cape (age 6); FRA Mascarenes
  (age 5); HOL the Cape + Mascarenes (age 5). Why: no colonizer ever explored down Africa (in 1458 Portugal and Castile
  had the exploration advances and idle explorers but explored nothing); the India and Asia events need the route
  discovered. No events, only AI desire. Not tested in game.
  Added the same day: `pp_colonizer_avoid_europe` (-0.9 on continent Europe) for the same colonizers until the Age of
  Revolutions (removed at its start). Why: in run c4831a96 Castile ran two colonial charters in Arkhangelsk by 1497;
  Europe's empty land (Lapland, Finland, the Russian north, the Urals, North Atlantic islands) is for its neighbours.
- **Ottomans recover from defeat; Anatolia before the Balkans** (2026-10-07, not tested in game).
  `advances/pp_country_advances_adjustments.txt`: Seljuk Heritage (age 1) +war exhaustion -0.05/month, stability cost
  efficiency +20 %, rebel growth -0.1 %/month; Timariots (age 2) and Ottoman Bureaucracy (age 3) +5 % max control each.
  `ai_scripted_expansion_score/target pp_ottoman_anatolia.txt`: +30 target score on every country ruling from Anatolia
  (no named country; war targets even if not neighbours, after 36 months of peace); while one is left, Balkan and
  Carpathian targets score x0.25, except whoever holds Constantinople. Why: run d3c30c7a, the Ottomans reached 262
  locations by 1432 but Karaman was still standing; they lost the war against it (39 locations occupied), the Bursa
  province broke away (62 locations), bankrupt 1442, nobles' civil war 1447, stability -14 .. -46 until 1512 (62-76
  locations).
- **Muscovy: Gathering of the Russian Lands, more control** (2026-10-07, not tested in game).
  `ai_scripted_expansion_score/target pp_gathering_russian_lands.txt`: MOS/RUS +30 target score on every country ruling
  from the Russian region (war targets even if not neighbours, after 36 months of peace); at start the conquest
  preference `pp_muscovy_gather_russian_lands` (x2, Russian region; `on_action/pp_country_finetunes.txt`);
  `events/pp_gathering_russian_lands_events.txt` gives vanilla's `russia_conquer_ruthenia_baltic` from 1450 (vanilla
  1600). Skilled Tax Collectors (age 1) +5 % max control, +5 % max rural control. Why: run d3c30c7a, Muscovy grew
  steadily (26 -> 199 locations) but in 1512 Novgorod still held 128 and Smolensk 137, Kiev took Ruthenia, and Muscovy's
  control sat at 0.26-0.30 (159 of 496 possible tax).
- **Japan: the imperial courts keep their palaces for the first four years of the Nanbokucho** (2026-10-09,
  `in_game/common/peace_treaties/expand_clan_influence.txt`, vanilla copy plus one block, guarded by
  `tests/test_peace_treaty_overrides.py`): the clan-influence peace term cannot target a country with the
  japanese_imperial_family reform while the situation is in its first four years. Why: with connected-land peace deals
  (`docs/peace_deal_rulebook.md`) clans took the Southern Court's palace sooner, it left the shogunate, lost the
  emperor status and the Nanbokucho ended around 1340 instead of 1344 (43 instead of ~140 civil-war wars). With the
  gate: ends 1345.3 or later (156 / 192 wars in two runs).
