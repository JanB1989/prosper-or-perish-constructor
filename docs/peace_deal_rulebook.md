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
comes only next to existing holdings (no exception since 2026-10-13, below; whole-country annexation and vassalisation are
unchanged). The "Recipient's
Desire" tooltip in the peace screen shows the desire without the selection factor, so its numbers are 20,000 x
smaller than in vanilla (often 0.00); the ranking between locations is the same.

### No exception (2026-10-13, Jan)

From 2026-10-09 to 2026-10-13 a scripted term (`pp_cede_preferred_location`) let an AI winner take a location away
from its land where it had a conquest preference outside its capital region (meant for overseas footholds: 6.6 of 17.8
overseas cessions per vanilla run, 1.8 of 160.6 same-land gore). Removed: in observer games it handed out landlocked
enclaves the winner could never govern (Hungary 57 locations in Ruthenia at control 0.03 through `pp_hungary_go_east`,
Muscovy 9 in the steppe through `pp_muscovy_conquer_steppe`, Hungary's Podolia from Jochi in 1355). Every AI winner now
takes connected land only; conquest preferences still steer whom it fights and which land it wants.

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

PP changes (v13, 2026-10-13, on 0.10; v1-v12 tuned on branch `enclave-release`, see the tuning steps below):

- `generic_actions/create_province_subject.txt` (same-name copy of vanilla, which bans the AI with `ai_tick = never`).
  Once a year every AI nation that may create subjects and is not in the HRE lets go each piece of its land it can
  never govern (`pp_enclave_kept_location`): land not connected to the capital by land or strait
  (`every_connected_location`), `max_control` under 0.5 in every location (control never rises above max_control,
  so land that has stayed ungoverned stays so), no location held by an enemy. Kept: footholds reached by sea that reach
  outside the capital's region (`pp_is_sea_coast`: river channels and lakes are not sea), colonies being settled,
  pieces where the nation can reach control 0.5 anywhere, HRE members. No piece count, size or continent limit
  (v12: 4+ pieces on the home continent, at most 6 locations, current control).
  - Paused during a civil war and for rebel states (`pp_enclave_release_paused`: `in_civil_war`, `is_rebel_country`;
    2026-10-15, both actions). Run 4b42459e: the rebel Castile of 1378 (capital Briviesca, 33 scattered locations)
    released Madrid/Avila, Granada/Almeria, Carmona, Hellin and Valencia as its vassals in 1379-1380; when Castile won
    the revolt in 1380 it inherited them. The loyalist side is cut apart by the rebels' land in the same way.
  - Paused in any war (`at_war`, 2026-10-15, Jan: a player cannot release land at war either). An independence war
    against one's own rebels is no civil war: run 4b90876a, the Celali uprising broke away as Hudavendigar (Bursa) in
    October 1608 with 225 of 456 Ottoman locations, interleaved with the Ottoman land in 15 of 16 areas; the Ottomans
    released 15 tributaries during that war and 9 more after it, Hudavendigar 24 vassals after it (465 -> 185 + 102
    locations and ~40 small subjects by 1622). After a peace the release runs as before.
  - Never for colonial nations or subjects of a player (`pp_enclave_release_exempt`, 2026-10-19, Jan, both actions).
    Jan's Portugal (1482-1492): its AI colonial nations (Bahamas, Leeward Islands) let their low-control islands go as
    16 one-location vassals of Portugal, and those vassals then colonized Cuba, Jamaica and Puerto Rico themselves.
  - A piece that borders one of the nation's subjects joins that subject (Morocco's land in Spain next to its vassal
    Jaen); any other becomes a new subject: a tributary where the government allows one
    (`pp_can_hold_tributary`: horde, tribe, `allow_tributary_subject`), else a vassal (a samanta in India), over
    diplomatic capacity too (Jan: released land becomes subjects; they can fight for their freedom).
  - The target is a province, but the AI releases by location (`create_country_from_location` + `make_subject_of`),
    since a piece often shares its province with kept land. The player's action is unchanged.
- `generic_actions/pp_release_enclave_independence.txt` (+ localization): subjects and union juniors may not create
  subjects (`pp_cannot_create_subjects`); a subject's piece joins or becomes a subject of its overlord, a union
  junior's piece becomes independent (AI only).
- Shared steps: `scripted_triggers/pp_enclave_triggers.txt`, `scripted_effects/pp_enclave_effects.txt`
  (`pp_enclave_list_provinces`, `pp_enclave_release_piece`). Not tested in game yet.
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
- A province is destroyed as soon as its last location of the nation changes owner, and every effect that still runs
  in its scope fails ("Scoped object is not valid. Type: Province (4294967295)", 563 lines in the first month of a
  new 1.4.1 game, 2026-10-15). In those releases the new country stayed independent, with the seat only and no cores
  or truce. Since then only `pp_enclave_pick_piece` runs in the target province; `pp_enclave_release_piece` runs in
  the nation's scope (tested in game: a new game to 1338.4, no errors, new countries become subjects).
- `local_control` is 0..1. Target enclaves average control 0.19-0.24, capital pieces 0.47-0.50; 3-10 % of target
  enclaves reach 0.5 somewhere.
- Vassals and samantas always join their overlord's offensive wars, tributaries only defensive ones. With released
  vassals (v10), countries new since the start made up 32-104 of the active war participants in the 1737 runs
  (unchanged runs: 5); Hungary's 1745 war on Poland had 8 of its 10 participants from its released enclaves.

Tests: saves of run 075b0d4e loaded in observer mode (PP Main Test), 25 years from 1537 and 15 years from 1737.
Independent histories from one save: +1/+2/+3 gold to every country at day 1 (+1 gold to one country was not enough).
"Weird" = 4+ home pieces without sea footholds and pieces over 6 locations ("ungoverned": only pieces with control
under 0.5 everywhere, as the rule); "stuck" = weird in the last two saves (5 years apart). Land classes from the
start save; "lost" = held by another existing nation at the end.

| | unchanged | with the release |
|---|---|---|
| 1737 + 15 years | 4 runs | 4 runs (v12, final) |
| weird ungoverned / stuck | 29-30 / 26-28 | 0-1 / 0 |
| weird incl. governed pieces | 32-36 | 1-5 (control 0.5+ pieces, kept by design) |
| HRE land kept | 96-100 % | 100 % |
| bigger pieces lost | 13-25 % | 13.5-16.4 % |
| exclaves of nations in < 4 pieces lost | 15.3-20.6 % | 14.5-20.6 % |
| sea footholds lost | 8.6-11.8 % | 12.0-20.8 % (v10: 8.6-26.5 %) |
| all land conquered by existing nations | 3.7-5.2 % | 4.0-5.6 % |
| countries | 626-638 | 887-937 |
| 5-year tick | about 116 s | about 121 s |
| 1537 + 25 years | 5 runs | 3 runs (v11, subjects within capacity) |
| weird / stuck nations | 38-43 / 35-36 | 0-1 / 0 |
| HRE land kept | 98-100 % | 98-100 % |
| bigger pieces lost | 11-19 % | 10-26 % |
| sea footholds lost | 1.7-14.8 % | 5.9-6.7 % |
| countries | 831-854 | 1,075-1,136 |
| 5-year tick | 100-113 s | 108-124 s |

- The 1737 sea-foothold excess is Poland's Black Sea coast: 56-64 of its 64 locations lost with v12 against 31-58
  in the unchanged runs (Kyiv, Halych, Hungary, Brandenburg; Poland collapses from 83 to 19-44 locations by 1742 in
  every run; the coast's control averages 0.27). Junagarh's Makran coast fell in 1 of 4 v12 runs (2 of 4 with v10,
  after its Timurid tributary broke free). Poland releases nothing itself (3 pieces); releasing nations' stability
  is not lower; total conquest moves within the spread. v12 was not run from 1537 (the observer game started
  2026-10-13 covers it).
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
(control 0.5+) kept; v12 independent instead of vassals (tributaries only where allowed).

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

## Subjects outweighing their overlord (2026-10-13)

Subject loyalty (0-100, disloyal under 50: no war help, no annexation, may join an independence movement) adds up:
minus liberty desire (-100..100, decays 0.5 a month towards 0), opinion of the overlord x 0.15, trust x 0.1, the
`subject_loyalty` / `loyalty_to_overlord` modifiers (the diplomatic spending slider gives up to +30), at most -20 from
an independence movement, and the strength term: all subjects of one overlord form a bloc compared with the overlord on
army, income and population; above a 25 % bloc share each subject loses (share - 0.25) x its type's
`strength_vs_overlord`. A disloyal AI subject declares an independence war only above a 25 % win chance
(`AI_INDEPENDENCE_WAR_WIN_CHANCE`). Run 075b0d4e: vassals kept their overlord for 25 years at the same rate (69-72 %)
whether the subjects held under 25 % or over 75 % of the bloc's population; 4-7 % went independent. Worst cases:
Liang (29 subjects, 90 % of the population, 1352-1442), Tibet (86 %, 1352-1557), Junagarh holding the Timurids as a
tributary (2.9x its population, 1677-1837), the rebel state Ganzhou holding its secessionists from 1452 to 1837.

PP (`subject_types/pp_vassal.txt`, `pp_fiefdom.txt`, `pp_tributary.txt`, `pp_secessionists.txt`, vanilla copied
whole): `strength_vs_overlord` -0.75 for vassals and fiefdoms (vanilla -0.5), tributaries (-0.25) and secessionists
(-0.1); secessionists' `loyalty_to_overlord` 10 (vanilla 50). The term only bites above 25 % bloc share, so strong
overlords with small subjects are untouched; colonial nations, HRE and Hanseatic members, appanages and samantas keep
vanilla. Kit: `~/pp_ai_run/splinter/scripts/adhoc/subject_bloc.py`, `subject_offenders.py`.

How blocs break (checked in game 2026-10-13, observer game ac43ec8a with the change above):

- The bloc term is computed per subject type, on army, income and population; the population share overstates it
  (Mali's vassals hold 85-90 % of the bloc's people but 49 % by the game's measure).
- Disloyal vassals and fiefdoms still defend their overlord (they always join its defensive wars).
- A subject's AI rebels alone only above a 25 % win chance, and counts the overlord, its allies and every other
  subject of the overlord as defenders, loyal or not: 0-4 % in every case seen (Kaabu vs Mali, Djerba vs Tunis).
- Once disloyal subjects join one independence movement, its members count on the rebel side: Tibet's 13 disloyal
  vassals (bloc term -32.6) went from 0.1 % to 99.8 % and 9 of 14 were independent by 1401 (unchanged run: Tibet kept
  16 vassals to 1557). By 1397 18 overlords held subjects with over half the bloc's people (unchanged 26), holding 62
  subjects (unchanged 112).
- Tested and dropped: disloyal vassals not defending against a fellow subject; the AI's war estimate ignores the
  war-joining rules.
- `LOYALTY_FROM_INDEPENDENCE_MOVEMENT_SCALE` 12.5 (vanilla 10) and `_MAX` 25 (vanilla 20): a movement lowers its
  members' loyalty a little more, so it holds together until it fights. Not tested in game.

