# Country finetunes

Hand-tuned changes for single countries, one entry each: what and why.

- **France** (2026-10-05, `pp_estate_privilege_adjustments.txt`): Great Offices of the Crown +10 points noble max tax.
  Why: its powerful nobles were taxable at only 4-5 %, so the crown went bankrupt and France fell apart in observer runs.
- **France +500, Ottomans +1,500, Byzantium -1,000 starting gold** (2026-10-05, `on_action/pp_country_finetunes.txt`).
  Why: France and the Ottomans went bankrupt early in observer runs; Byzantium took the Ottoman land.
- **Castile and Portugal +200 opinion of each other for 100 years** (2026-10-06, `biases/pp_country_finetune_opinions.txt`,
  given in `on_action/pp_country_finetunes.txt`; replaces vanilla's +50 good relations that fade by ~1387).
  Why: Castile conquered Portugal in every game; +100 for 150 years did not stop the war declaration.
- **France +3 diplomatic reputation** (2026-10-06, `pp_estate_privilege_adjustments.txt`, Great Offices of the Crown).
  Why: Jan's call, on the same privilege as the noble tax; vanilla privileges give at most +2.
