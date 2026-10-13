# Peace deals and border gore (EU5 1.4)

How the AI picks the land it takes in a peace deal, why it produced border gore (detached, scattered holdings), what PP
changes, and how to measure it. Behaviour only; measured on 2026-10-09 in high-aggression observer runs on 0.10 (ten 1337-1357 runs, a 1837 check, console scenarios).

## How the AI picks locations

For every location of the enemy it could take, the AI computes a desire:

```
desire = FROM_WORTH_MULT x (LOCATION_TREATY_BASE_SCORE + LOCATION_TREATY_WAR_WORTH_FACTOR x war worth)
         x (1 + LOCATION_DISTANCE_FACTOR x min(distance to its capital, DISTANCE_MAX) / DISTANCE_DIVIDER)
         x conquer desire / 100
         x (1 + WARGOAL_BASE) for the war goal's province, x NOT_WARGOAL_MULT elsewhere
```

(all `NAI.AI_CONQUER_TREATY_DESIRE_*` / `NAI.AI_CONQUER_LOCATION_TREATY_*` defines; vanilla 5 x (3 + 0.5 x worth),
-0.1 per 250 map units up to 1500, war goal x3, others x0.5).

Then a selection factor against the locations already in the deal:

- x `AI_CONQUER_TREATY_DESIRE_ADJECENT` when the location borders the taker's land **or a location already in the
  deal**, x 1 / ADJECENT when it does not (vanilla 5 and 0.2);
- x `AI_CONQUER_TREATY_DESIRE_POTENTIAL_BORDERGORE` (0.005) when taking it would split the loser's remaining land;
- x `AI_CONQUER_TREATY_DESIRE_SAME_PROVINCE` (3) when the taker already holds part of the province;
- x `AI_CONQUER_TREATY_DESIRE_SMALL_AREA_FACTOR` (1.5) for adjacent land of a loser with at most
  `SMALL_AREA_THRESHOLD` (5) locations; +5 / +10 on the factor for pockets the loser would keep with 1 / 0 neighbours;
  x (0.5 + 0.5 x share of the location's neighbours held by the taker or in the deal).

The deal is filled greedily: after each pick the touched candidates are scored again, and every candidate with a
score above zero stays in the running while the warscore lasts. **A low score does not keep a location out of a
deal; only a score of exactly zero does.** A location next to an earlier pick counts as adjacent, so a first
non-adjacent pick grows a detached block.

The war goal is the province with the highest summed conquer desire for the casus belli; conquer desire has no term
for bordering the attacker.

## Where the gore came from (vanilla defines, high aggression, 1337-1357)

- 4,450 locations changed owner; 259 (5.8 %) ended detached from the gainer's land, 155 of them in partial cessions
  (7.9 % of those).
- Partial cessions from a loser the gainer did not border: 121 of 138 locations detached (88 %). From a bordering
  loser: 34 of 1,814 (1.9 %).
- Typical cases: a war goal province that does not border the attacker (Yuan took a 26-location block of Laos and
  Cambodia around its war goal), allies paid in land far from home (an ally of Delhi's rebels took 25 locations of
  Bihar), land around an army's occupation behind a third country.
- The share of land in exclaves rises and falls with empire breakups (Golden Horde civil war, Yuan), not with peace
  deals; judge peace deals by the transfers.

## PP setting (pp_defines_adjustments.txt)

```
AI_CONQUER_TREATY_DESIRE_ADJECENT = 100001        # 5
AI_CONQUER_TREATY_DESIRE_FROM_WORTH_MULT = 0.00025  # 5
```

Above 100,000 the 1 / ADJECENT step is exactly 0 in the engine's fixed point (5 decimals), so a deal only takes land
that connects to the taker's land, directly or through other land in the same deal. FROM_WORTH_MULT scales every
location's desire: 0.00025 x 100,001 = 25 = vanilla 5 x 5, so connected land keeps its vanilla value against gold,
vassalisation and the other terms. A test keeps the two coupled. Raising ADJECENT alone (25 or 50, value kept) changed
nothing measurable, because non-adjacent land still scored above zero.

Consequences: no partial cession of land that does not touch the taker; a war goal that does not border the attacker
is only taken when the deal reaches it through connected land; allies far away get no land; an overseas foothold
comes only next to existing holdings or through the exception below (whole-country annexation and vassalisation are
unchanged). The "Recipient's
Desire" tooltip in the peace screen shows the desire without the selection factor, so its numbers are 20,000 x
smaller than in vanilla (often 0.00). The engine floors the desire at 1.0 (decompiled 2026-10-11), so in PP it
no longer ranks the locations (war goal and conquer desire included); the selection factors do.

### The one exception: conquest preferences outside the home region (2026-10-09)

`in_game/common/peace_treaties/pp_cede_preferred_location.txt`, AI winners only: a location that does not touch the
winner may be taken when the winner has a conquest preference on its area (`common/area_preferences`, multiplier
above 1) and it lies outside the winner's capital region. It costs the engine's own cession cost
(`location_peace_cost`). To allow more distant land, give the country a conquest preference; the term never changes.

Why this rule (all detached gains in the five vanilla runs, flags read from the save before each transfer, per run;
overseas = a landmass where the winner held nothing, same land = behind a third country or a gap):

| Rule | Overseas cessions allowed (of 17.8) | Same-land gore allowed (of 160.6) |
| --- | --- | --- |
| Conquest preference outside the home region (shipped) | 6.6 | 1.8 |
| Conquest preference anywhere | 12.4 | 17.8 |
| Cores | 0.8 | 6.2 |
| Claims (casus belli on the province) | 0.6 | 1.8 |
| War goal | 9 % | 9 % |

Home-region preferences are mostly gore (vanilla gives `russia_conquer_region` to every Russian principality, China's
unification preference to its warlords); war goals do not separate the two at all. Kept: England in France, and
whatever vanilla's or PP's preferences name (Aragon's islands, Venice, the Ottomans' Balkans, Castile's Maghreb).
Blocked: Majapahit on Borneo (its home region), Tunis on Sardinia, England on the Hanse, Naples in Greece, Sweden in
Livonia (no preference behind them).

## Measured effect (1341-1357, high aggression, five runs per setting)

Each setting ran from the same 1337 start; four more runs per setting were relaunched from its 1338-1341 saves (runs
diverge within a year, so these show the chance spread; a relaunch from the same save repeats itself exactly). Every
number is per run, from each run's own 1341.4.1 save to 1357.4.1.

| | vanilla defines (5 runs) | connected land only (5 runs) |
|---|---|---|
| detached locations gained | 249 / 308 / 321 / 333 / 279 (mean 298) | 67 / 112 / 169 / 70 / 93 (102) |
| detached share of partial cessions | 7.0-11.6 % (mean 9.2) | 0.7-4.5 % (2.1) |
| partial cessions from a loser the gainer did not border | 136-194 locations (168) | 6-56 (31) |
| deals with detached land | 48-62 (56) | 21-28 (24) |
| locations changing owner | 3,412-4,255 (3,851) | 3,483-4,859 (4,024) |
| wars started between neighbours | 200-221 (211) | 191-231 (212) |
| wars started, without Nanbokucho | 353-382 (370) | 323-384 (369) |
| Nanbokucho wars (Japan) | 73-104 (93) | 30-59 (43) |
| control of all land, 1357 (mean per location) | 0.447-0.466 (0.456) | 0.450-0.468 (0.458) |
| control, population-weighted, 1357 | 0.419-0.433 (0.426) | 0.399-0.417 (0.407) |
| locations of the 10 largest countries, 1357 | 2,828-3,481 (3,181) | 2,808-3,398 (3,243) |

- What is left of the detached land is not peace-deal land: civil-war reconquest (a country retaking land from its
  own rebels), inheritance and diplomatic annexation, subjects annexed.
- Japan: the Nanbokucho wars die out about four years earlier (none after year 5-6 of the runs instead of year 8-9;
  93 -> 43 such wars). Their deals use the scripted term peace_expand_clan_influence (it targets one location) and
  gold; the stored ideal offers never contain the abdication term, and both courts still exist in 1342 under both
  settings. The situation itself ends 1344.1.1 / 1344.12.1 (vanilla) vs 1340.2.1 / 1339.8.1 (new defines), read
  from the saves (engine table situations). In every run, vanilla and new, the Southern Court loses the emperor status
  and the Northern Court prevails (engine table io_special_status) - the historical outcome; only the timing moves.
  The court loses the status because it drops out of the shogunate when a clan wins a Nanbokucho war and takes the
  term peace_expand_clan_influence on the court's seat: the court's palace (gosho) is destroyed and replaced by the
  winner's yakata, and a court without its palace leaves the shogunate (status rescinded automatically). Without
  scattered daimyo land in the deal, clans pick that term years earlier. The abdication term is not the path (a
  same-name copy that forbids it changed nothing).
- Japan, not fixed (Jan 2026-10-09: fix systemic things only, no country patches): the Nanbokucho ends ~4 years
  earlier with the same outcome. A court gate on the clan-influence term (four years) was tried and removed; with it
  the situation ended 1345.3.1 or later (156 / 192 wars in 1338.4-1347.4 vs vanilla 137 / 142).
- Population-weighted control is 0.02 lower (six runs each: 0.424 -> 0.407), almost all of it in Hindustan
  (0.43 -> 0.32, consistent across runs); east China (0.36 -> 0.33) is within the spread, Europe, Africa and America
  are unchanged, and control per location is the same (0.456 both). Delhi collapses in every run. Under the new
  defines neighbouring powers keep connected blocks of it: 21 % of Hindustan's population is ruled from a capital
  outside the region (vanilla 8 %; e.g. Bengal, Malwa, western India), the population-weighted distance to the
  owner's capital is 98 vs 76 map units and owners are larger (26 vs 21 locations). Control falls with distance to
  the capital: the vanilla Asian control-by-distance curve predicts 0.48 -> 0.43 from the longer distances alone,
  about half of the observed 0.43 -> 0.32. Tenure does not explain the rest (the new runs' owners have held the land
  slightly longer, 9.3 vs 8.5 years). The holders themselves are in worse shape: war exhaustion 0.62 vs 0.28 and
  control 0.41 vs 0.48 across all their land (at war about as often, 24 vs 20 % of the population). Conquests stick
  and become cross-regional realms instead of scattered pieces, and those realms run at lower control.
- Region by region (49 regions over 500k people, six runs each, population-weighted control 1357): Hindustan is the
  only one that differs beyond chance (t = -4.2, 7 % of the world population); five regions pass |t| > 2 where 2.5
  are expected by chance. Land changing owner inside Hindustan is the same (300 vs 298 locations per run) and
  detached gains there are few in both (6 vs 11), so the region trades as much land as before; what differs is who
  ends up holding it (cross-regional, war-worn neighbours). No narrow lever was found that would not touch the
  conquest behaviour itself.
- With three runs per setting the largest empires looked more stable under the new defines; the fourth and fifth pair
  reversed that (a giant broke up in a new run, none in a vanilla one). The 10 largest countries end the same size.
- The standing map changes less than the deals: exclave fragments in 1357 average 244 (vanilla) vs 222 (new),
  exclaves of countries with at least 20 locations 88 vs 70, small ones (<= 3 locations) 207 vs 196. The 1337 map
  already has ~195 exclaves, and most of the stock comes from the start map, civil wars, inheritance and annexation.
  Vanilla's pocket bonus (+5/+10 on the selection factor for land the loser would keep with 0-1 neighbours) is
  negligible next to ADJECENT 100001; enclave clean-up through deals still gets the neighbour-share factor (up to x2)
  and the conquer-desire exclave bonus. A faster clean-up is the next lever to test.
- Where exclaves come from (five runs each, 1341-1357, locations): gained detached 397 -> 285; cut off from their
  owner while it kept them 1,240 -> 1,172 (after a cession to an existing country ~270, after a loss to a new country
  ~520 - revolts, independence, releases - and ~430 when an owner's main body moves). The loser side is the larger
  source and the new defines do not touch it.
- The Japan and Hindustan effects come with removing detached land, not with this particular pair: every tested
  variant that zeroes non-adjacent land moves both (Nanbokucho ends 1339.8-1342.4 instead of 1344.1, always the
  Northern Court; Hindustan control 0.36-0.40 instead of 0.44, one run each). ADJECENT alone moves them least but
  costs ~20 % of the vassalisations, adds ~14 % wars between neighbours and leaves more exclaves (below), so the
  shipped pair has the smallest side effects overall among the tested options.
- Tested and not adopted: `AI_CONQUER_TREATY_DESIRE_POTENTIAL_BORDERGORE = 0` (deals may never split the loser's
  remaining land) on top of the new defines, one 1337-1357 run: cut-offs after cessions 432 (new-define runs 254 +- 53),
  exclave stock 791 (721 +- 135), detached gains 78, land exchange and wars unchanged. No gain, so it stays at 0.005.
- Why FROM_WORTH_MULT has to move with ADJECENT (one run with ADJECENT 100001 and vanilla FROM_WORTH_MULT 5):
  detached gains 72 as well, but connected land is then worth 20,000 x more against the other terms. New vassal
  links fell to 130 (vanilla 166 +- 11, new defines 162 +- 8), wars between neighbours rose to 242 (211 / 212),
  wars without Nanbokucho to 397 (370 / 369), and the exclave stock to 973 (795 / 721). With the compensation all
  of these stay at vanilla level.
- Tested and not adopted: `AI_CONQUER_TREATY_DESIRE_SAME_PROVINCE = 10` (vanilla 3; prefer completing provinces) on
  top of the new defines, one run: exclave stock 798, border edges per location 0.742 (new-define runs 721 and
  0.721 +- 0.026), partial cessions 1,534 locations (1,925): tidier borders did not follow, land exchange fell.
- One pair continued 1357-1387: detached share 6.4 % -> 2.2 % (partial cessions 6.1 % -> 1.2 %), land changing
  owner 9,543 -> 11,062, wars started 905 -> 1,050; exclaves in 1387 264 vs 256.
- Late game (observer run a3e3bb2a, 1837.4.1, two years each way): 84 vs 102 locations changed owner, about 1 %
  detached in both; the late game is too static to show the overseas consequence (no first foothold from a deal).

## Enclaves (2026-10-12/13)

Observer run 075b0d4e (1342-1837) ended with 29 nations in 4+ pieces of home land (most in China and Japan). Half of
their cut-off land had been cut off for 100+ years. Within 25 years only 8 % of cut-off land became a new nation and
under 7 % reconnected. Cut-off land is badly held (control 0.17 vs 0.43 in the capital's piece, 16 % rebel support vs
6 %), but its nationalist movements are mostly under the 5,000 supporters a revolt needs, and the owner never aims at
the land between its pieces. Landlocked enclaves and sea footholds have the same control and proximity, so no define
can tell them apart.

PP changes (2026-10-13, on 0.10; tuned on branch `enclave-release`):

- `generic_actions/create_province_subject.txt` (same-name copy of vanilla, which bans the AI with `ai_tick = never`).
  Once a year an AI nation that may create subjects, is not in the HRE and is broken into 4+ pieces on its home
  continent releases its small enclaves, each whole enclave as one country. An enclave (`pp_enclave_kept_location`) is
  land not connected to the capital by land or strait (`every_connected_location`), at most 6 locations, control
  under 0.5 everywhere (the nation cannot govern it), no location held by an enemy. Kept by design: footholds reached
  by sea that reach outside the capital's region (`pp_is_sea_coast`: river channels and lakes are not sea), bigger
  pieces, the exclaves of nations in fewer than 4 pieces (border gore), HRE members.
  - The new country is a subject while the nation has at least 1 diplomatic capacity left
    (`pp_free_diplomatic_capacity`, vanilla's AI measure), else independent. Subject type: tributary where the
    government allows one, else vassal, or samanta in India.
  - An enclave that borders one of the nation's subjects joins that subject instead.
  - The target is a province, but the AI releases by location (`create_country_from_location` + `make_subject_of`),
    since an enclave often shares its province with the capital's piece or a kept piece. The player's action is
    unchanged.
- `generic_actions/pp_release_enclave_independence.txt` (+ AI list, localization): subjects and union juniors may not
  create subjects (`pp_cannot_create_subjects`), so they let each such enclave go as an independent nation (AI only).
- Shared steps: `scripted_triggers/pp_enclave_triggers.txt`, `scripted_effects/pp_enclave_effects.txt`,
  `script_values/pp_enclave_values.txt`.
- `CONQUER_DESIRE_EXCLAVED_BONUS` stays vanilla (50). It is the only define built for enclaves (a neighbour's conquer
  desire for a location whose surroundings are all its own, its subjects' or impassable; clamped at 100 with the
  rest). At 300 it removed no more splintered nations than at 50, and neighbours took Austria's HRE enclaves in both
  1537 runs with it.

Engine facts found on the way:

- `any_connected_location` counts the location itself (`count >= 6` kept pieces of 6).
- The subject-type list of `create_province_subject` is cached from the first province of the list
  (`cache_targets`), and the engine's `subject_can_be_created_by` fails for a province that also holds the capital:
  one such province blocked a whole nation. The AI's types now depend on the nation only.
- `samanta_advance` hides the vassal type (Indian states release samantas). A union junior cannot create subjects.
  No subject type may create subjects. A march cannot be created from a province.
- Each subject uses diplomatic capacity; over it a country gets `unsupported_diplomatic_capacity` (subject loyalty
  -25, cabinet efficiency and crown estate power -50 % at full overuse). Hungary went over it with 6-9 released
  vassals and lost the 1541 Vbk independence war more often.
- `local_control` is 0..1. Target enclaves average control 0.19-0.24, capital pieces 0.47-0.50; 3-10 % of target
  enclaves reach 0.5 somewhere.

Tests: saves of run 075b0d4e loaded in observer mode (PP Main Test), 25 years from 1537 and 15 years from 1737.
Independent histories from one save: +1/+2/+3 gold to every country at day 1 (+1 gold to one country was not enough).
"Weird" = 4+ home pieces without sea footholds and pieces over 6 locations; "stuck" = weird in the last two saves
(5 years apart). Land classes from the start save; "lost" = held by another existing nation at the end.

| | unchanged | with the release |
|---|---|---|
| 1737 + 15 years | 5 runs | 4 runs (v10) |
| weird / stuck nations | 32-36 / 30-33 | 0-2 / 0 |
| HRE land kept | 96-100 % | 99-100 % |
| bigger pieces lost | 13-25 % | 17-23 % |
| sea footholds lost | 9-12 % | 9-27 % |
| all land conquered by existing nations | 3.7-5.2 % | 4.2-5.3 % |
| countries | 626-638 | 973-983 |
| 5-year tick | about 116 s | about 126 s |
| 1537 + 25 years | 5 runs | 3 runs (v11) |
| weird / stuck nations | 38-43 / 35-36 | 0-1 / 0 |
| HRE land kept | 98-100 % | 98-100 % |
| bigger pieces lost | 11-19 % | 10-26 % |
| sea footholds lost | 1.7-14.8 % | 5.9-6.7 % |
| countries | 831-854 | 1,075-1,136 |
| 5-year tick | 100-113 s | 108-124 s |

- The 1737 sea-foothold losses are two pieces: Poland's Black Sea coast (half or more lost in every run, unchanged
  ones too; all of it in 3 of 4 runs with the release) and Junagarh's Makran coast (lost in the 2 runs where its
  Timurid tributary broke free). No mechanism found: the rule never releases these pieces, total conquest and the
  rate at which subjects break free are unchanged. v11 (capacity gate) was not run from 1737; the control filter
  was not run in game.
- Released subjects stay: of 248 released by 1742, 228 were still subjects of the same overlord in 1752, 10 taken,
  7 independent, 2 annexed back (the AI annexes only subjects it borders).
- Script errors: about +20 % per minute, all base-game kinds that grow with countries and subjects. The coat of arms
  "dynasty not valid" bursts run at the same rate in unchanged runs; `frustrate_annexation` checks a cabinet action
  of the Across the Pillars DLC.

Tuning steps: v1 released every landlocked enclave province (Pegu's and Dai's halves too); v2/v3 size cap and vassal
fallback; v4 whole enclave as one subject; v5 only nations in 4+ pieces (every nation had released its single
exclave: 660 -> 940 countries); v6 river channels and lakes are not sea; v7 coastal splinters inside the home region,
releases in war unless occupied, subjects let enclaves go; v8 an enclave next to an own subject joins it, the exclave
bonus back to 50; v9 union juniors, samantas, coastal pieces reaching outside the home region kept; v10 release by
location, pieces up to 6, subject types by nation; v11 subjects only within diplomatic capacity, governed enclaves
(control 0.5+) kept.

Metric: `~/pp_ai_run/splinter/scripts/splinter2.py <playthrough>` (stuck splinter episodes, how they end). Test kit
there: `enc_rep.py` (replicate table), `enc_errors.py` (error rates per run), `enc_fates.py`, `enc_lost.py`,
`enc_followup.py`; runner `~/pp_ai_run/splinter/runner/enc_variant.ps1` (`-Perturb` for the day-1 change).

## How to measure

Kit in the private research repo (`~/pp_ai_run/bordergore`): location adjacency from `locations.png` + `adjacencies.csv`,
yearly saves read with the save engine (new tables `wars` and `peace_offers`), metrics per run:

- detached share: transferred locations (gainer existed before) whose land component of the gainer holds none of
  its old land; split by partial cession (loser survives) and by whether the gainer bordered the loser;
- gore events: (year, gainer, loser) with at least one detached location;
- side effects: locations changing owner, partial cessions between neighbours, wars started, war length, countries
  at war, countries gone, new subject links, control of gained land, distance to the gainer's capital.

One run pair is not enough: runs diverge within a year, so compare against noise twins (the same defines relaunched
from the year-1 and year-2 saves; a relaunch from the same save repeats itself exactly). Save every year; gore comes in
blocks of 10-26 locations, so 3-year windows are too noisy. The AI's stored preferred peace offers
(`ai_memory.preffered_peace_offers`, engine table `peace_offers`) are ideal wish lists that barely react to these
defines; judge the AI by ownership changes between saves.

Controlled check (console, 1337 start, both settings): `add_casus_belli` + `declare_war_with_cb` (conquer province on
the target's capital province), `transfer_location_occupation` of the whole target, `add_bonus_warscore` 100. Strong
countries against neighbours (Castile-Navarre, Aragon-Arborea, Byzantium-Candar, Mamluks-Hutaym) took the same land
under both settings, except Delhi-Khorasan (11 locations under vanilla by day 90; with the new defines still at war
on day 90, its wish list one location longer); against non-neighbours (England-Hainaut, Hungary-Freising, Khmer-Muang Sua, ...) both settled for gold
within 45 days. Gore needs longer wars, allies and occupation behind third countries, which the runs measure.
