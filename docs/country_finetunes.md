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
