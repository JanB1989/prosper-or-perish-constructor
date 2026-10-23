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
| `NAI.WAR_BALANCE_LEVIES_IMPORTANCE` (2026-10-16, Jan, not tested in game) | 1 | 0.5 | The AI's strength estimate (war targets, win chance in peace demands, surrender, peace offers) counts the whole levy pool, raised or not, x this plus regulars x 3, then x (1 + land morale) x (1 + discipline); unit quality is not counted. Levy-heavy realms (1807: France 99 %, Mamluks 86 % of counted army from levies, Ottomans 29 %) looked as strong as professional armies that beat them. At 0.5 a regular counts as 6 levies. |
| `NDiplomacy.WAR_ENTHUSIASM_TIME_LATE_FACTOR`, `WAR_ENTHUSIASM_MILITARY_STRENGTH_FACTOR` (2026-10-16, section 8) | 0.01, 0.1 | 0.005, 0.05 | War enthusiasm drives AI peace acceptance. Past 24 months it fell 0.01 a month and spent manpower took up to 0.2 more, so a side that won its battles but lost the siege race gave up land worth about twice the war score. |
| `NCombat.DAYS_PER_SIEGE_PHASE_WITHOUT_FORT` (2026-10-16, Jan, not tested in game) | 15 | 30 | War score is occupied land; AI defenders chase instead of besieging. Unfortified land now falls as slowly per phase as a fort, so besiegers sit longer where field armies can break the siege. Players too. |
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

# Ending wars: war score, enthusiasm, peace offers, terms (EU5 1.4.1)

Decoded 2026-10-16 from the 1.4.1 executable: every define that decides when a war ends and on what terms. Behaviour
only. PP changes none of these (except the two peace-deal location defines in `docs/peace_deal_rulebook.md`). "WS" =
war score in points (-100..100), "e" = war enthusiasm (0..1). Values below are vanilla.

## 1. War score (players and AI alike)

- **Complete victory (+-100)**: the loser surrendered unconditionally, reached its maximum war exhaustion, or is fully
  occupied. Before `MONTHS_BEFORE_TOTAL_OCCUPATION` (60) a full occupation only counts when the whole enemy side is
  occupied; after it, the war leader alone is enough.
- Otherwise, between the two war leaders: bonus pools (`add_bonus_warscore`, each side 0..`WARGOAL_MAX_BONUS` 50) +
  ticking score of the side holding the war goal + battle score (sum of battle results, capped at
  +-`WARSCORE_MAX_FROM_BATTLES` 50, a CB's `max_warscore_from_battles` overrides), together capped at +-100; then
  occupation and blockade score of every participant; final cap +-99, 100 only for the side holding the war goal.
- **Battle result** = loss ratio x `BATTLE_RESULT_SCALE` (25), capped at `BATTLE_RESULT_CAP` (25), probably x (1 + the
  age's `war_score_from_battles`, -0.05..-0.20 from age 3).
- **Ticking**: the holder of the war goal gains `DEFAULT_WARGOAL_TICKINGWARSCORE_BONUS` (2) x the goal's
  `ticking_war_score` per step, up to `WARGOAL_MAX_TICKING_WAR_SCORE` (25); the other side's pool falls by the same.
  Superiority goals tick only while battle score is beyond +-`SUPERIORITY_WARGOAL_WARSCORE_THRESHOLD` (10); each won
  battle adds `DEFAULT_WARGOAL_BATTLESCORE_BONUS` (3) to the winner's bonus.

## 2. Forced endings and fixed rules (players and AI alike)

- **Enforceable offer** (refusing costs `STAB_HIT_GOOD_PEACE` -10 stability): WS >= 100; or WS >=
  `WAR_ENFORCE_DEMANDS_MAX_WARSCORE_FRACTION` x 100 (50) and the demand costs less than WS /
  `WAR_ENFORCE_DEMANDS_WARSCORE_COST_NEEDED` (2); or only the war goal once its ticking is full (superiority-type goals
  also need the goal held `PEACE_AUTO_ENFORCE_BASE_DAYS` 365 + `PEACE_AUTO_ENFORCE_RANK_DAY` 180 x attacker rank level
  days); the defender holding its goal the same way can enforce white peace. `PEACE_AUTO_ENFORCE_*` never end a war by
  themselves.
- **Call for peace**: the side whose leader has WS >= `CALL_FOR_PEACE_WARSCORE_LIMIT` (67) after
  `CALL_FOR_PEACE_THRESHOLD_MONTHS` (60) gets +1 per further month; after the enemy surrendered unconditionally +3 per
  month (`CALL_FOR_PEACE_FROM_UNCONDITIONAL_SURRENDER`) from `UNCONDITIONAL_SURRENDER_MONTHS` (2) on. It raises war
  exhaustion and AI acceptance. Wars older than the game start count at most `PEACE_MAX_MONTHS_AT_WAR_BEFORE_START_DATE`
  (12) months of history.
- **White peace after inactivity**: a war ends in white peace `YEARS_SINCE_LAST_WAR_ACTION_BEFORE_WHITE_PEACE` (3) years
  after its last war action unless a unit stands on enemy land; no player exemption. Rebel-type wars get a winner
  instead. `YEARS_BEFORE_WHITE_PEACE_ALERT_ADVANCE` (1) is the alert lead only.
- Separate peace not before `PEACE_SEPERATE_BLOCK_MONTHS` (12); unconditional surrender not before
  `UNCONDITIONAL_SURRENDER_MIN_MONTHS` (12). Truce = `TRUCE_YEARS` 5 + 10 x (share of WS used / 100) years.
  `DURATION_BEFORE_PURGING_WARS_IN_DAYS` is bookkeeping only.

## 3. War enthusiasm (AI decisions)

Per country per war, clamped 0..1, sum of (all `NDiplomacy.WAR_ENTHUSIASM_*`):

| Term | Value | War leader | Ally |
|---|---|---|---|
| base | 0.5 | 0.5 | x `ALLY_BASE_RELUCTANCE_MULT` 1.5 = 0.75 |
| time | (24 - months) x 0.0075 up to `TIME_MONTHS` 24, then x 0.01 (+0.18 at start, -0.5 at month 74) | x1 | x1 |
| war exhaustion | -0.02 per point | /2 | x1 |
| rebels | -0.2 x threat | /2 | x1 |
| desperation | -0.75 x share of own location value occupied or besieged | /2 | x1 |
| sieges | +0.25 x share we besiege, -0.5 x share of ours besieged | x1 | x1 |
| ongoing battles | 10 x share of force limit fighting (any battle with 10 % of it pins e at 1.0) | x1 | x1 |
| unit balance | 0.5 x side balance | x1 | 0 |
| war direction | 0.005 x gains, x5 when gaining | x1 | 0 |
| war goal achieved / capital held / independence | +0.05 each | x1 | goal 0 |
| military strength | -0.2..+0.1 (army vs force limit, manpower vs max) | x1 | x2 |
| losses | -2.5 x men lost, -4 x ships lost (per denominator) | x1 | x1 |
| separate peace | -0.1 | 0 | -0.1 |
| ally winning | 0.5 per WS point when WS > 0 (`ALLY_MULT`) | 0 | **an ally at WS >= +2 sits at 1.0** |
| CB script values | `additional_war_enthusiasm(_attacker/_defender)` | x1 | x1 |

Quirks in the code: `WAR_ENTHUSIASM_COALITION_FACTOR` 0.3 is truncated to an integer (0); `WAR_ENTHUSIASM_CALL_FOR_PEACE`
is 0 for leaders and allies (only coalition leaders use it); the late time factor also applies to negative enthusiasm.

## 4. AI peace decisions

- **Acceptance** (every offer to an AI, from a player or an AI): sum of script weights from
  `in_game/common/ai_diplochance/00_ai_diplochance.txt` `requestpeace`, accepted at >= 1: base -25, + WS (absolute WS
  for white peace or gifts), -100 x (e - 0.5), + call for peace, + 0.5 per month at war, -1 per WS the deal costs (gifts
  add cost and value), +2 per own defending siege, -5 per own attacking siege, -20 if the deal takes too much,
  +10 per demand, -30 for fragmenting the country, -50 x excess when a gift would push others over
  `TARGET_SAFE_ANTAGONISM_FOR_AI` (50) with more strength than 0.75 x ours; +50 when the offer contains the AI's own
  ideal deal or fits its white-peace entitlement (min(100, 100 (e - 0.5) + WS) <= cost); +100 for enforceable demands;
  -10000 after surrendering unconditionally to someone else. The AI's own demand budget = this acceptance for white
  peace - 1.
- **What the AI wants** (its ideal deal): win chance >= 0.8: 100; 0.6..0.8: 66 + 25 (e - 0.5); 0.4..0.6:
  (33 + 33 (e - 0.5) + WS) / 2; below: WS; then x (1 + `expected_warscore_modifier`). In the first
  `EARLY_PEACE_TIME_MONTHS` (4) months it is raised to (X + `EARLY_PEACE_TIME_BASE` 10) x `EARLY_PEACE_TIME_FACTOR` 1.5;
  afterwards it drops to white peace when WS < `MINIMUM_WAR_SCORE_TO_CONSIDER_DEFEAT` (-50) or win chance <
  `MINIMUM_WIN_CHANCE_TO_CONSIDER_DEFEAT` (0.25). Below `MIN_WARSCORE_TO_DEMAND` (10) it asks for nothing. The AI never
  offers concessions in normal wars, only demands or white peace.
- **When it sends**, every 90 days: a war leader keeps fighting while e > `PEACE_OFFER_WAR_ENTHUSIASM_THRESHOLD` (0.6)
  unless the war is 60+ months old or its goal is held; an ally leaves at e <= `PEACE_OFFER_ALLY_LEAVE_WAR_ENTHUSIASM`
  (0.25) or once `PEACE_OFFER_OCCUPATION_PERCENTAGE_THRESHOLD` (25 %) of its land is occupied. It sends when the enemy
  is 25 % occupied, when the demand uses >= `PEACE_OFFER_WARSCORE_PERCENTAGE_THRESHOLD` (0.33) of its WS, when e <=
  `PEACE_OFFER_WAR_ENTHUSIASM_STALE_WAR` (0.5), or when it is weaker than 0.5 x its enemies (0.1 x with
  `PEACE_OFFER_MISSING_IMPORTANT_TREATIES_STRENGTH_COMPARISON_MULT` when it still misses an important treaty).
- **Unconditional surrender** (AI): at WS -100 at once; else as war leader at WS <= `UNCONDITIONAL_SURRENDER_WARSCORE_LIMIT`
  (-90) with a strength share <= `MINIMUM_STRENGTH_TO_AVOID_UNCONDITIONAL_SURRENDER` (0.15), enemy >=
  `UNCONDITIONAL_SURRENDER_HOPELESS_STRENGTH_COMPARISON` (20) x stronger and balance <= `ACCEPTABLE_BALANCE_DEFAULT` (1.2).
- **Ally split**: the leader keeps 60 % of the unguaranteed war score and shares 40 % (`PEACE_OFFER_ALLY_DEFAULT_FAIRNESS`)
  by contribution (participation, tax base, negotiation power, opinion); promised land is 75 % guaranteed; shares below
  `PEACE_OFFER_ALLY_NOT_ENOUGH_TO_CARE_THRESHOLD` (3 %) get nothing.
- **Outnumbered** (side strength < `HEAVILY_OUTNUMBERED_RATIO` 0.4): the army AI chases only stacks of at most
  `OUTNUMBERED_BATTLE_ADVANTAGE` (0.6) of its own on good terrain (`OUTNUMBERED_TERRAIN_BONUS_MIN` 5 %) and focuses enemies
  with low enthusiasm (`OUTNUMBERED_ENTHUSIASM_WEIGHT` 2) that can sign a separate peace (`OUTNUMBERED_SEPARABLE_WEIGHT` 1.5).

## 5. Terms: what land costs, what the AI asks for

- **Cost of a location** = war worth / (1 + E), clamped 0.1..99, E >= -0.99, E summed from: revolt war 5.0 (and nothing
  else); small independent owner + location worth / owner's total worth; size discount (owner worth - 100) x 0.001 up to
  0.5; unoccupied fort -0.15 and never besieged another -0.18 (+49 % cost); same culture +0.10, same religion +0.10;
  power projection lead x 0.001; rival +0.33; war-score efficiency modifiers and lack of control; owner not an original
  participant -0.5 (double cost); taker an original defender +0.25. Applies to players too.
- **AI desire per term**: land = the cede desire (`docs/peace_deal_rulebook.md`); gold = 0.1 per WS (`PEACE_GOLD_AI_DESIRE`,
  max 2.5 at `PEACE_MAX_WARSCORE_FOR_GOLD` 25; amount 0.2 loan sizes per WS); reparations = income x 0.1 x 10 years x 12 x
  0.1 (in gold); noble sacrifice 1 % of nobles per WS (`PEACE_MAX_WARSCORE_FOR_SACRIFICE` 25), desire from the doom it
  removes; junior partner (worth + conquer desire) x `PEACE_BECOME_JUNIOR_PARTNER_FACTOR` 3; royal marriage
  10 / (1 + place in line) + 3 / (1 + age / 30); release nation = cut x future (product of two small factors, only for
  connected blocks of 5+ locations touching the taker); cancel/transfer subject only for AI takers that want the subject.
  All are 0 in revolt wars. With PP's land defines, adjacent land always wins over gold.
- **Allies after the peace** (anyone leading the peace): an ally expects contribution x 0.75 (promised land) or x 0.5;
  short allies lose up to 20 trust and opinion (halved if not promised; none below 20 % contribution when not
  promised, none for AI allies that want no land); over-paid allies owe favors.

## 6. Defines with no effect in 1.4.1

No code reads them (only registration; a read through a pointer would be missed, so "almost certainly dead"):
`AI_CALL_FOR_PEACE_CHANCE_MULTIPLIER`, `EXPECTED_WAR_SCORE_BASE`, `IDEAL_WARSCORE_DIFFERENCE_THRESHOLD_TO_CONSIDER_PEACE`,
`PEACE_OFFER_ACCEPTANCE_THRESHOLD`, `PEACE_OFFER_SEND_PEACE_ENEMY_STRENGTH_FACTOR`, `PEACE_OFFER_TOO_MUCH_ALLY_WARSCORE_THRESHOLD`,
`PEACE_OFFER_WAR_SCORE_THRESHOLD` (replaced by hardcoded bands, the `requestpeace` weights and the enforce rule),
`PEACE_CEDE_CITY_BASE_MULTIPLIER`, `PEACE_CEDE_PROVINCE_ALLY_DESIRE_BASE`,
`PEACE_CEDE_PROVINCE_ALLY_DESIRE_OUR_CONQUER_DESIRE_FACTOR`, `PEACE_RELEASE_COUNTRY_GORE_FACTOR`, `PEACE_SACRIFICE_AI_DESIRE`.

## 7. Levers

- **Longer or shorter wars**: `WAR_ENTHUSIASM_TIME_LATE_FACTOR` / `TIME_MONTHS` (the long-run decay), `WAR_ENTHUSIASM_BASE`,
  `ONGOING_BATTLES` (pins e during battles), `ALLY_MULT` (pins winning allies), `PEACE_OFFER_WAR_ENTHUSIASM_THRESHOLD`
  (AI only); `requestpeace` `months_at_war` / `war_enthusiam` (script, AI acceptance of anyone's offers); call-for-peace
  thresholds, ticking cap and rate, battle caps, `YEARS_SINCE_LAST_WAR_ACTION_BEFORE_WHITE_PEACE` (all players too).
- **Terms the AI accepts or asks for**: `requestpeace` weights (base, warscore, peaceoffer, war_enthusiam), the
  win-chance bands (hardcoded) via `expected_warscore_modifier`, `EARLY_PEACE_TIME_*`, `MINIMUM_*_TO_CONSIDER_DEFEAT`,
  `WAR_ENFORCE_DEMANDS_*` with `STAB_HIT_GOOD_PEACE`, the surrender limits, `TARGET_SAFE_ANTAGONISM_FOR_AI`, cost
  efficiency terms (forts, non-target, size discount).
- **AI only**: enthusiasm thresholds, ideal deal, send rules, surrender decision, ally split, outnumbered behaviour.
  **Everyone**: war score, enforceability, call for peace, forced white peace, location cost, ally expectations,
  and the `requestpeace` acceptance (it judges player offers to AIs too).

## 8. Case: a stronger army that gives up (Ottomans vs Mamluks 1806-1809, run d3b7a95a)

The Mamluk coalition (with the Qara Qoyunlu) won the first battles by numbers and occupied about an eighth of Ottoman
land; from mid 1807 the Ottomans won most battles at 2-4:1 losses but never besieged Mamluk land, so the war score
kept creeping toward the Mamluks (about -34). In year 3 the Ottomans accepted a cession worth about twice that war
score: acceptance adds the war score, the months at war (+0.5 each) and low enthusiasm (time past 24 months, spent
manpower, occupied land), and nothing in it compares the armies. The strength estimate (`WAR_BALANCE_*`, levies 0.5)
does not enter acceptance or enthusiasm at all: it steers whom to attack and the offers an AI sends.

Replays from 1807 and 1808 (seven runs; slower time decay `WAR_ENTHUSIASM_TIME_LATE_FACTOR` 0.005 with a weaker manpower term
`WAR_ENTHUSIASM_MILITARY_STRENGTH_FACTOR` 0.05 or a stronger `WAR_ENTHUSIASM_UNIT_BALANCE` 0.75): each tweak makes the Ottomans demand a peace
10-25 war score cheaper, but the outcome follows the war's path (occupations, deals that would split the empire): the
unchanged 0.10 held out for three years and lost nothing in one replay, both variants lost 17-20 locations in another.
No define lets the AI see that it can win while its war score is negative; the lever is the war itself (sieging the
enemy's land) or the `requestpeace` script weights.

Why the war score never turned: a battle counts its losses against the whole side's army, so at PP army sizes the
32 battles of this war summed to about one point (the Ottomans won 21 of them). The war score was the occupied
Ottoman land, doubled by `OCCUPATION_VALUE_SCALE` 2. The Ottomans never sent an army to retake it: their AI gives
each army the job with the best score, and chasing an enemy stack or joining a gathering (fixed priorities 8-10)
always beats sieging, even sieging their own occupied land next door (priority 4), although their armies were strong
enough for it. No define sets those priorities; the assignment defines only trade all priorities against distance
for every army in the world.

**World-wide test (2026-10-16), adopted.** Every war of 10 observer years from 1807 and from 1667, per variant (13-28
fought wars each; "field winner" = the side with fewer battle losses; land = locations that moved between the sides):

| Variant | Field winner ceded (1807 / 1667) | Field winner gained | Wars where the field winner ended net down |
|---|---|---|---|
| 0.10 | 120 / 67 | 83 / 210 | 4 / 5 |
| A: enthusiasm, `TIME_LATE_FACTOR` 0.005 + `MILITARY_STRENGTH_FACTOR` 0.05 | 64 / 9 | 207 / 205 | 2 / 2 |
| B: army jobs, `AI_MILITARY_ARMY_ASSIGNMENT_PROXIMITY_FACTOR` -2, `AI_STICK_TO_SIEGE_TIME_FACTOR` 0.01, `AI_FOW_FORGET_CHASE_ARMY_CHANCE` 0.66 | 74 / 29 | 132 / 179 | 4 / 2 |
| A + B | 41 / 68 | 142 / 182 | 2 / 3 |

A is the only variant better in both eras; it was adopted. B did not raise the defenders' share of sieging (it stays
about a fifth to a quarter), so the army-job defines do not reach the cause. Side effect of A: wars last a little
longer (1667: 8 instead of 3 still running after 10 years); the number of wars is unchanged. Almost every war a
field winner lost was a defender winning battles while the attacker took its land by sieges: the remaining cause is
the army job priorities, which no define sets. Small samples (about 45 fought wars per variant): watch it in the next
long run.

The Ottoman war itself, same 1807 save, 0.10 vs A: Ottoman war enthusiasm when they accepted 0.08 vs 0.33 (median over
the war 0.39 vs 0.46), the accepted cession cost 79 war score at a war score of 34 vs 42 at 27, Ottoman land lost 43 vs
25 (10-year runs: 43 vs 25). The Mamluk side still did all the sieging (siege score 2.8 vs 0.02), so the Ottomans hold
out longer and pay less, but they still do not win back their land.

# Sea Raid casus belli (PP, 2026-10-23, Jan; not tested in game)

A naval war for pirates and every country that may hire privateers. Files: `casus_belli/pp_naval_raid_cb.txt`,
`wargoals/pp_naval_raid_wargoal.txt`, `peace_treaties/pp_naval_raid_treaties.txt`,
`scripted_relations/pp_naval_raid_relations.txt`, `unit_abilities/pp_coastal_raid.txt`, localization
`pp_naval_raid_l_english.yml`; `tests/test_naval_raid_cb.py`.

- **Who and against whom:** `modifier:can_hire_privateers` and own ports (pirate republics, privateering laws, policies
  and advances); it builds up (speed 15, like Anti-Piracy) against a country with ports whose sea zone holds our
  privateers, no truce. No `ai_will_do`: the AI values it by the war goal like any other CB.
- **War goal:** vanilla's naval superiority type with vanilla `naval` numbers (land and subjugation x10 cost, ticking
  0.5). The engine already does the rest: ticking war score while we blockade ports and the enemy blockades none of
  ours, bonus war score per won naval battle. PP's blockade capacity x10 (`ppc blockade`) makes blockades easy.
- **Treaties (only in a war of this CB, base cost 10):** Tribute of the Seas (loser pays 10 % of its monthly income
  for 10 years, vanilla war reparations' share), Open Harbours (the winner's markets pull the loser's locations like
  Preferred Market Access, trade protection lifted, 10 years), Sack the Market (destroys one coastal market of the
  loser; cost 10 + half its trade income, max 50; AI desire -10 until seen in game). Vanilla treaties stay as they are.
- **Coastal Raid (navy ability, 30 days):** in a war of this CB, next to an enemy coastal location of that war with
  peasants and not Recently Razed: its peasants -1 %, 0.4 % of them arrive as slaves in the raider's capital (vanilla
  wokou ratios), Recently Razed for a year. AI weight 25 (like the clan raids); whether AI navies use it is unknown.
