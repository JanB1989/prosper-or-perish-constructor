# Country finetunes

Hand-tuned changes for single countries, one entry each: what and why.

Note for judging finetunes in observer runs (found 2026-10-08): new games take the game rules of the preset
"LastAppliedRules", which holds `ai_personalities_random_per_age`; vanilla then re-rolls every AI personality at each age
(1342, 1437, ...). Run 40148576 had the Ottomans cautious, Castile cautious and Portugal and England isolationist from
1342 (vanilla setup: Ottomans aggressive, Castile/England/France/Muscovy expansionist, Portugal opportunistic), and new
ones again from 1437. Cautious, isolationist and friendly personalities need a casus belli and wait 18-24 months
between wars. Test runs should use `ai_personalities_historical`, or restore the historical personalities by console.

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
- **Ottomans: Mamluk Egypt and the Levant after Constantinople** (2026-10-08, branch expeditions,
  `ai_scripted_expansion_target/pp_ottoman_mamluks.txt`): from 1490, once TUR owns Constantinople and no rival rules
  from Anatolia, every country ruling from Egypt or the Fertile Crescent is a war target (+30, after 36 months of peace).
  Why: in run c4831a96 the Mamluks still held Egypt and Syria in 1836 (340 locations); the Ottoman conquest of 1516-17
  never came.
- **Portugal: the Strait coast of Morocco** (2026-10-08, branch expeditions,
  `ai_scripted_expansion_target/pp_portuguese_morocco.txt`): from 1410 the owners of Ceuta, Tangier, Asilah and Tetouan
  are Portugal war targets (+20, after 36 months of peace; never Castile/Spain). Why: Portugal sat at 67 Iberian
  locations from 1337 to 1497 in every run; Ceuta (1415) and the Moroccan forts were its first expansion.
- **Castile/Spain: the war for Granada** (2026-10-08, branch expeditions, `events/pp_reconquista_events.txt`
  pp_reconquista.2, `casus_belli/pp_reconquista.txt`, `ai_scripted_expansion_target/pp_reconquista.txt`): from 1475 a
  hidden event (once) gives CAS/SPA the Reconquista casus belli (conquer an Iberian province, 50 years) on every Muslim
  country that holds land in Iberia, Granada or a Maghreb power that took it; a second expansion target uses it (+60,
  ignores antagonism, 24 months of peace). Why: run c4831a96 still had Granada in 1497; run 40148576 had Castile at
  peace 1387-1402 beside a 16-location Granada without attacking it, and by 1452 Morocco had taken Granada (15 Iberian
  locations), which the capital-in-Iberia Reconquista target no longer saw.
