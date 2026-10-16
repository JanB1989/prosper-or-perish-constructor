# War planning: when and whom the AI attacks (EU5 1.4.1)

How the AI decides to start a war, where it stops, what PP changes, and how it was measured. Behaviour only; measured
on 2026-10-16 (branch `ai-war-willingness`) from Jan's observer game (1667) and two of its autosaves (1662, 1657),
full world, normal aggression.

Starting point: in the 1667 save only 19 wars were running, nearly all revolts and independence wars. The six
offensive wars all used the parliament conquest CB. No top-10 power was at war, although several sat on large
treasuries (Ottomans 19k gold, Portugal 61k, Korea 19k).

## The pipeline

Each month every AI at peace goes through these steps; any step can stop it.

1. **Planning roll.** chance = `DEFAULT_CHANCE_OF_EXPANSION` (0.30) x (1 + aggressiveness x
   `CHANCE_OF_EXPANSION_AGGRESSIVENESS_SCALE`) - war exhaustion x `AI_WAR_EXHAUSTION_EXPANSION_PENALTY`, halved for
   rank-1 countries, reduced by unintegrated land (`AI_UNINTEGRATED_LAND_EXPANSION_PENALTY` x unintegrated share, from 5
   unintegrated locations), x `PARLIAMENT_IN_SESSION_EXPANSION_CHECK_MULTIPLIER` while parliament sits, capped at 1.
   An AI whose aggressiveness is 0 or lower also waits `ai_months_between_wars` after its last war (any war it took
   part in); the parliament multiplies that wait by `PARLIAMENT_IN_SESSION_MONTHS_BETWEEN_WARS_MULTIPLIER`.
   Aggressiveness = the `aggressiveness_modifier` sum: personality (aggressive +0.3, expansionist +0.2, opportunistic
   +0.1, friendly -0.1, cautious -0.15, defensive -0.2, isolationist -0.25), ruler traits, societal values
   (belligerent +-0.15, outward/inward +0.05/-0.1). Balanced AIs mostly sit between -0.02 and -0.18.
   `ai_months_between_wars` = game rule (low 60, normal 24, high 6) + personality (balanced +6, defensive +12,
   cautious +18, isolationist +24, expansionist -6, aggressive -12).
2. **Coalition check.** No new plan while the countries holding more than `SAFE_AMOUNT_OF_ANTAGONISM` (30) against it
   together reach `POTENTIAL_COALITION_MAX_SAFE_RELATIVE_STRENGTH` (0.75) x its strength. Never fired for the top 30
   powers in 1668.
3. **Candidates.** Countries in the AI's conquer-desire map that it may declare on (no truce etc.), sorted by desire;
   the top `AI_NUM_EXPANSION_TARGETS` are war-gamed.
4. **Score.** A target scores 0 unless the war estimate (both sides with subjects, allies and likely joiners,
   weighted by `WAR_ALLY_DISTANCE_BASE`; armies: levies x1 + regulars x3; a logistic curve with
   `WAR_WIN_CHANCE_SENSITIVITY` on the strength difference, the lower of the army and total estimates) reaches the
   country's `win_war_chance_threshold` (auto modifier 0.6 + personality: balanced 0.65, defensive 0.675, isolationist
   0.75) or `win_war_chance_lower_limit` (0.5). Then x`AI_BORDERING_CONQUEST_FACTOR` (5) for neighbours,
   x`AI_USE_CONQUER_CB_FACTOR` (25) with a usable CB, x (aggressiveness + 0.25) x a power-balance term, opinion, rival,
   marriage, alliance and dynastic terms, scripted expansion scores. Without a CB the score is x
   `NO_CASUS_BELLI_CONQUEST_FACTOR` (0.8, parliament may grant one) or x`NO_CASUS_BELLI_AND_NO_PARLIAMENT_CONQUEST_FACTOR`
   (0.25); `ai_require_cb_for_war` (cautious, isolationist, friendly, low aggression) makes it 0. A target needs
   `EXPANSION_TARGET_SCORE_NEEDED_TO_PICK` (20) to become the war objective. Aggressiveness of -0.25 or lower makes
   every score 0 or negative: isolationists never pick a target.
5. **Objective.** One objective at a time. While it exists the AI re-scores only that target
   (`EXPANSION_TARGET_SCORE_NEEDED_TO_KEEP`) and looks at no other.
6. **Declaration check**, monthly: war exhaustion above `SAFE_AMOUNT_OF_WAR_EXHAUSTION` -> no; no usable CB -> wait
   (for a parliament agenda or a CB being fabricated through a spy network, `casus_belli_creation` costs 20 spy
   network); a fresh war estimate against the threshold; then readiness: stability not below 0, no active disaster,
   treasury at least 0.5 x `AI_BUFFER_TAX_BASE_FACTOR` (3) x tax base (double while at war); then the declaration
   costs (a war without CB costs 15 stability, 30 against the same religion) must fit war_declaration_stab_hit_tolerance
   + half the stability. Only then it declares.

## What stops the powers (1667 save, 120 largest AIs, one game year)

| Outcome | Countries |
|---|---|
| never passed the planning roll (at war, or the months-between-wars wait, or aggressiveness at or below -0.1) | 44 |
| war-gamed targets, all failed the win estimate (742 of 801 zero scores were estimates below 0.6, most below 0.1) | 27 |
| roll passed, no valid candidate | 15 |
| objective waiting for a CB the whole year | 14 |
| objective blocked by readiness (disaster, negative stability, treasury) | 5 |
| declared a war | 3 |

Examples:
- **Ottomans** (aggressive, aggressiveness 2.8, win threshold 0.5): picked east Muntenia (estimate 0.65) at load and
  waited for a CB for two full years, looking at nothing else. Their spy network on Hungary reached its target in
  about 8 months and they hold `cb_prevent_annexation` against Hungary from 1668, yet the objective kept waiting
  (inferred: the declaration wants a CB on the objective's own target). Georgia, Hungary and the Mamluks, their
  biggest desires, were not war-gamed while the objective stood.
- **Mamluks** (defensive, aggressiveness -0.34): never plan a war at all.
- **England**: CB on the Outer Hebrides, estimate 1.0, 14k gold, never declares: `religious_turmoil` has been active
  since 1537. An active disaster fails the readiness check (the check's counter was 1 for England and Brandenburg,
  the two probed powers with an active disaster); this one ends only at stability > 30 plus religious unity
  > 0.9 (or extreme spiritualism/humanism), which England (stability ~4) never reaches. Brandenburg the same since 1544.
- **Castile**: CB on Girona, estimate 1.0, 662-804 gold against the 845 it needs (1.5 x tax base).
- **Portugal** vs Morocco: estimate 0.57 (MOR + its ally TLE + TAT) against its threshold 0.6.

## PP changes (branch ai-war-willingness)

| Setting | Vanilla | PP | Why |
|---|---|---|---|
| `NAI.CHANCE_OF_EXPANSION_AGGRESSIVENESS_SCALE` | 10 | 5 | At 10 an aggressiveness of -0.1 already zeroes the planning roll; most balanced AIs sit at -0.02..-0.18. At 5 they plan now and then; defensive (-0.2 and lower) and isolationist AIs still never do; aggressive/expansionist AIs keep a roll near 1. |
| `NAI.AI_NUM_EXPANSION_TARGETS` | 20 | 40 | Desire order puts big, allied neighbours first and they fail the estimate; weaker neighbours further down were never war-gamed. Tick time unchanged within noise. |
| static modifier `normal_aggression` `ai_months_between_wars` (`pp_ai_aggression_rule.txt`) | 24 | 12 | Under the normal aggression rule a balanced AI stayed 30 months out of planning after every war it was part of, allied and defensive wars included. Now 18. Low/high aggression unchanged. |

Not changed, tested without effect: `MONTHS_TO_WAIT_FOR_CASUS_BELLI` 24 -> 12 (identical runs: the waiting objectives
are held by their CB sub-tasks, not by this timer), `WAR_ALLY_DISTANCE_BASE` 200 -> 100 (ally weights moved by a few
percent, no decision changed). Not changed on purpose: `AI_BUFFER_TAX_BASE_FACTOR` (the same buffer steers the AI's
building and budget spending), `WAR_WIN_CHANCE_SENSITIVITY` (8 -> 12 would move 1-4 target pairs a year: most failed
estimates are below 0.1, the targets really are stronger with their allies), parliament cadence
(`PARLIAMENT_COOLDOWN_MONTHS` 59 is the main CB source for AIs but also a player mechanic).

## Measured effect

Probe on the 120 largest AIs (by 1667 tax base), two game years from each start, same save = deterministic run:

| Start | Declaring countries vanilla -> PP | Declarations (monthly checks returning "declare") |
|---|---|---|
| 1667.12 (Jan's save) | 4 -> 7 | 18 -> 34 |
| 1662.4 (autosave) | 3 -> 6 | 3 -> 27 |
| 1657.4 (autosave) | 10 -> 11 | 22 -> 31 |
| total | 17 -> 24 | 43 -> 92 |

Four game years (same probe, end saves `pp_war_long*_base` / `_branch`):

| Start | Declaring countries | Declarations | Offensive wars running at the end | Locations changed owner | Top-30 powers gained / lost | Top-30 stability, war exhaustion |
|---|---|---|---|---|---|---|
| 1667.12 vanilla / PP | 19 / 23 | 68 / 76 | 15 / 16 | 207 / 247 | 23 / 55 -> 68 / 40 | 10.6, 0.45 -> 12.0, 0.45 |
| 1662.4 vanilla / PP | 8 / 14 | 14 / 45 | 8 / 12 | 640 / 578 | 62 / 220 -> 63 / 201 | 7.2, 0.41 -> 7.9, 0.96 |

Land changing hands is dominated by revolts and independence wars, so it moves both ways; world control (0.55) and the
powers' gold and stability did not change.

New wars are neighbour wars the attacker should win: MOS -> farghana_province (estimate 0.83), WUU -> its Chinese
neighbours (seongwi, jinzhou, zezhou), INJ -> KLB, lower_sindh -> PUN, jinzhou -> xingzhou. Single components (1667 start): scale 5
alone 4 -> 6, months 12 alone 4 -> 8 (1662 start: no change), 40 targets alone (one year) 3 -> 4. Runs diverge after
the first changed decision, so a single pair carries about +-2 countries of noise; the package was positive from all
three starts. Not yet checked: a long run (land changing hands, war length, border gore, AI economy), player-visible
balance. Kit: private `~/pp_ai_run/warai`.

## Open problems no define reaches

- **Stuck disasters**: `religious_turmoil` (England since 1537, Brandenburg since 1544) never ends at PP stability
  levels and blocks every war declaration of the country. Fix belongs in the disaster's end trigger or in stability.
- **Objective tied to the wrong CB**: an AI that plans against a subject gets its fabricated CB against the overlord
  and waits forever (Ottomans -> Muntenia / Hungary). It keeps re-scoring that one target.
- **CB supply**: parliament agendas (every 59 months) are the main CB source; only ~50 spy networks exist worldwide.
- **Treasury and stability readiness**: Castile, Yemen and others hold a CB and a won estimate but stay below
  1.5 x tax base in gold or below 0 stability.
