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
comes only next to existing holdings (whole-country annexation and vassalisation are unchanged). The "Recipient's
Desire" tooltip in the peace screen shows the desire without the selection factor, so its numbers are 20,000 x
smaller than in vanilla (often 0.00); the ranking between locations is the same.

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
- Japan: the Nanbokucho situation ends about four years earlier (around 1340 instead of 1344-1345). It ends with the
  peace term that makes a court abdicate (AI desire +1000 for the shogun and the courts); without scattered daimyo
  land in the deal the winner takes that term sooner. Fewer Nanbokucho wars follow; no other region showed this.
- Population-weighted control is 0.02 lower (six runs each: 0.424 -> 0.407), almost all of it in Hindustan
  (0.43 -> 0.32, consistent across runs); east China (0.36 -> 0.33) is within the spread, Europe, Africa and America
  are unchanged, and control per location is the same (0.456 both). Delhi collapses in every run. Under the new
  defines neighbouring powers keep connected blocks of it: 21 % of Hindustan's population is ruled from a capital
  outside the region (vanilla 8 %; e.g. Bengal, Malwa, western India), the population-weighted distance to the
  owner's capital is 98 vs 76 map units and owners are larger (26 vs 21 locations). Control falls with distance to
  the capital, hence the drop: conquests stick and become cross-regional realms instead of scattered pieces.
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
- Tested and not adopted: `AI_CONQUER_TREATY_DESIRE_POTENTIAL_BORDERGORE = 0` (deals may never split the loser's
  remaining land) on top of the new defines, one 1337-1357 run: cut-offs after cessions 432 (new-define runs 254 +- 53),
  exclave stock 791 (721 +- 135), detached gains 78, land exchange and wars unchanged. No gain, so it stays at 0.005.
- Tested and not adopted: `AI_CONQUER_TREATY_DESIRE_SAME_PROVINCE = 10` (vanilla 3; prefer completing provinces) on
  top of the new defines, one run: exclave stock 798, border edges per location 0.742 (new-define runs 721 and
  0.721 +- 0.026), partial cessions 1,534 locations (1,925): tidier borders did not follow, land exchange fell.
- One pair continued 1357-1387: detached share 6.4 % -> 2.2 % (partial cessions 6.1 % -> 1.2 %), land changing
  owner 9,543 -> 11,062, wars started 905 -> 1,050; exclaves in 1387 264 vs 256.
- Late game (observer run a3e3bb2a, 1837.4.1, two years each way): 84 vs 102 locations changed owner, about 1 %
  detached in both; the late game is too static to show the overseas consequence (no first foothold from a deal).

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
