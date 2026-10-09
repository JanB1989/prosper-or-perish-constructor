# Peace deals and border gore (EU5 1.4)

How the AI picks the land it takes in a peace deal, why it produced border gore (detached, scattered holdings), what PP
changes, and how to measure it. Behaviour only; measured on 2026-10-09 in high-aggression observer runs on 0.10.

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

## Measured effect (1339-1357, high aggression, three runs per setting)

Each setting ran from the same 1337 start; two more runs per setting were relaunched from its 1338/1339 saves (runs
diverge within a year, so these show the chance spread). Every number is per run, 1339.4.1 to 1357.4.1.

| | vanilla defines | connected land only |
|---|---|---|
| detached locations gained | 257 / 335 / 365 | 69 / 118 / 174 |
| detached share of partial cessions | 8.4 / 10.0 / 9.7 % | 0.7 / 2.3 / 4.3 % |
| partial cessions from a loser the gainer did not border | 138 / 182 / 206 locations | 21 / 37 / 9 |
| deals with detached land | 59 / 59 / 72 | 23 / 30 / 32 |
| locations changing owner | 4,236 / 4,461 / 4,158 | 4,505 / 3,901 / 3,940 |
| wars started between neighbours | 285 / 286 / 275 | 286 / 251 / 311 |
| wars started, without Nanbokucho | 444 / 450 / 450 | 447 / 388 / 463 |
| Nanbokucho wars (Japan) | 151 / 152 / 142 | 74 / 46 / 82 |
| control of gained land | 0.33 / 0.32 / 0.33 | 0.32 / 0.32 / 0.33 |
| mean control of all land, 1357 | 0.447 / 0.458 / 0.458 | 0.459 / 0.450 / 0.456 |

- What is left of the detached land is not peace-deal land: civil-war reconquest (a country retaking land from its
  own rebels), inheritance and diplomatic annexation, subjects annexed.
- Japan: the Nanbokucho situation ended about four years earlier (around 1340 instead of 1344-1345). It ends with the
  peace term that makes a court abdicate; without scattered daimyo land in the AI's deal the winner takes that term
  sooner. Fewer Nanbokucho wars follow; no other region showed this.
- The eight largest countries lost less land to neighbours in partial cessions (642 / 684 / 777 -> 457 / 305 / 521:
  fewer lost wars, slightly smaller cessions), the other countries traded about 8 % more land among themselves;
  in total -4 %, inside the run-to-run spread (about +-7 %). In two of three vanilla runs a giant broke up (Golden Horde
  civil war, Yuan losing Chagatai) and in none of the three new runs, which can still be chance at three runs each.
  Watch the giants in the next long observer run.

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
