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
- **Kiev west, Hungary east; Muscovy into the steppe** (2026-10-09, Jan, not tested in game).
  `ai_scripted_expansion_score/target pp_kiev_hungary.txt`: KIE +30 target score on every country ruling from the
  Carpathians (Hungary, Wallachia, Moldavia), and targets ruling from the steppe, the Volga or Russia count x0.25; HUN
  +30 on every country ruling from Ruthenia (Kiev, Halych); MOS/RUS +30 on every country ruling from the steppe or the
  Volga (the Golden Horde and its heirs); all of them war targets even if not neighbours (after 36 months of peace).
  At start the conquest preferences `pp_kiev_go_west` (Carpathians), `pp_hungary_go_east` (Ruthenia) and
  `pp_muscovy_conquer_steppe` (steppe + Volga), x2 each, and Muscovy +500 starting gold
  (`on_action/pp_country_finetunes.txt`). Why: Kiev grew to 250-1,260 locations in most runs by eating the Golden
  Horde's steppe while Muscovy stayed small; Jan: Kiev and Hungary should fight each other, and Muscovy needs a push.
- **Ottomans +5 culture capacity** (2026-10-09, Jan, `advances/pp_country_advances_adjustments.txt`): all on
  Seljuk Heritage, researched at game start. Why: in run
  a3e3bb2a the Greek majority (353 k Greeks vs 220 k Turks at start) sat at satisfaction 0.02 and broke away in 1347.
- **Ottomans crush the Mamluks once their power base stands** (2026-10-10, Jan, not tested in game). Power base =
  owns Constantinople and no other country (Ottoman subjects aside) rules from Anatolia
  (`scripted_triggers/pp_ottoman_triggers.txt`). Then `ai_scripted_expansion_score/pp_ottoman_anatolia.txt` gives
  +60 and x2 on every country ruling from the Levant or Egypt, `ai_scripted_expansion_target/pp_ottoman_anatolia.txt`
  makes them war targets after 24 months of peace, and `events/pp_ottoman_events.txt` adds the conquest preference
  `pp_ottoman_crush_mamluks` (Egypt + Levant, x5). Why: run ac0ccc76, the Ottomans grew to 32 M people but left the
  Mamluks' 143 locations untouched until 1612 and then only took them as a tributary (Egypt frozen to 1837); vanilla's
  Egypt preference comes only 1475-1525 at x1, the same as Persia and the Caucasus.
  `casus_belli/pp_make_tributary_cb.txt` (REPLACE of vanilla `cb_make_tributary`, re-check after game updates): TUR
  never gets the make-tributary CB against MAM (the only way to a tributary is its `force_tributary` peace), so Egypt is
  conquered, not frozen as a tributary.
- **Serbia and Bulgaria look north to Hungary** (2026-10-09, Jan, not tested in game).
  `ai_scripted_expansion_score/target pp_balkans_north.txt`: SER/BUL +30 target score on every country ruling from the
  Carpathians (Hungary, Wallachia, Moldavia; war targets even if not neighbours, after 36 months of peace); the
  Ottomans and every country ruling from Anatolia count x0.25. At start the conquest preference `pp_balkans_go_north`
  (Carpathians, x2; `on_action/pp_country_finetunes.txt`). Why: Jan, tired of the Ottomans dying; Hungary gets a
  second front while it pushes east into Kiev.
- **Lucky nations: expansion aims for the first century** (2026-10-10, Jan, branch `lucky-nations-expansion`, tested in
  observer runs, see below). England, France, Muscovy, Brandenburg, the Ottomans, Portugal, Castile (and successors).
  `ai_scripted_expansion_score/target pp_lucky_nations.txt`:
  - all seven: a target whose army, or whose overlord's army, is over 1.25x their own counts x0.25; while at war every
    new target counts x0.25 (one war at a time);
  - France and the Papacy never plan a war on each other (run 3610b1ce: France lost 31 locations to the Papacy);
    France and Castile, and Castile and Portugal, not before 1450; Muscovy and Smolensk not before 1400 (3610b1ce:
    Muscovy lost 24 of 40 locations to Smolensk by 1357);
  - France +30 on every independent country ruling from the France region (Bourbon, Armagnac, Brittany, Foix ...;
    conquest preference `pp_france_consolidate_realm` x5); Brandenburg +30 on every country ruling from the
    Brandenburg, Pomerania and Mecklenburg areas (`pp_brandenburg_marches` x3); Portugal +20 on countries ruling from
    the Maghreb from 1400 (`pp_portugal_morocco` x3 on the Moroccan core, events/pp_lucky_nations_events.txt);
  - England: vanilla's `england_conquer_france` (x15 on all of France) is removed at start for `pp_england_french_claims`
    (x4 on Gascony, Guyenne, Poitou, Normandy, Picardy, only where England or its subjects still hold land) and vanilla's
    `england_conquer_ireland` from the start (vanilla 1450);
  - Castile: `pp_castile_no_france_conquest` and, until 1450, `pp_castile_spare_portugal` at -1 (zero desire: the peace
    AI keeps every location scoring above zero, so vanilla's -0.9 `castile_no_portugal_conquest` still let Castile take
    Portuguese land, run 5e45c44e: Portugal 67 -> 11 by 1437); France likewise `pp_france_spare_iberia` (-1 on Iberia)
    until 1450 (run 5f9f0232: France took 48 Castilian locations in an alliance war despite the planning peace). The
    1450 removals are in events/pp_lucky_nations_events.txt.
  Never-attack rules only stop planned wars; alliance and event wars still happen, so the land a winner may take is
  steered by the -1 preferences.
  Observer runs 1337-1437 (historical personalities, normal aggression), locations at 1387/1437 (start ENG 138,
  FRA 163, MOS 26, BRA 27, TUR 23, POR 67, CAS 244):
  baseline 3610b1ce ENG 245/229, FRA 158/228, MOS 28/125, BRA 44/28, TUR 134/185, POR 67/68, CAS 318/337;
  v1 d2733167 206/246, 177/336, 153/267, 35/47, 149/294, 67/64, 277/277;
  v2 5e45c44e 248/243, 141/249, 166/233, 27/51, 88/114, 48/11, 314/344;
  v3 cacbb6a6 192/302, 187/158, 164/286, 38/55, 159/230, 67/68, 309/349;
  v4 5f9f0232 211/236, 209/299, 99/255, 38/94, 110/262, 67/68, 322/228;
  v6 d6dc966a (final: v5 England x4 + Ireland, v6 France spares Iberia) 251/274, 169/240, 159/239, 28/54, 3/39,
  67/73, 330/348.
  Thriving at 1437 (grown, never below 80 % of start): baseline 4 of 7, v1 5, v2 5, v3-v6 6 each. The misses that aims
  cannot fix: Ottoman revolts (v2 rebels took 55 locations in 1397; v6 the Akhis rose from 1 to 52 locations in 1357,
  Ottoman stability -12), France's dips from England's 1350s invasions (it recovers by 1437 in every run but v3).
  Second sample of the final version, cf982ee6 (stopped at 1392 for the deadline): ENG 235, FRA 105, MOS 136, BRA 27,
  TUR 172, POR 1, CAS 329: Castile took Portugal despite the -1 preference, so -1 does not reliably zero the peace
  desire (the war likely came from vanilla's Portuguese succession events); France fell from 163 to 105. Open.
  v7 (2026-10-10 after the deadline, NOT tested in game, not deployed): Castile's vanilla -0.9 on Portugal is removed
  while the -1 is active (if the engine keeps the stronger preference, the -0.9 left x0.1) and restored in 1450;
  Castile plans no war on a country ruling from France before 1450 (the war target's province is taken regardless of
  the -1); France's realm aim softened to +10 / x2 (runs 5e45c44e, cacbb6a6, cf982ee6: France lost land to Brittany,
  Bourbon, Foix in those wars).
