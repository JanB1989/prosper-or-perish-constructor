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
