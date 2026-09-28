# EU5 AI building rulebook

Measured 2026-09-28 on EU5 1.3.11 with Prosper or Perish only (no other mods), observer game from 1337.4.1:
14 daily saves (April 1337), 57 monthly saves (June 1337 - August 1340), 97 yearly saves (1341 - 1437), and three
controlled experiments that branch from one save. Saves and tables: WSL `~/pp_ai_run/` (`saves/`, `tables/<save>/`,
analysis scripts `explore*.py`, `exp*.py`, `estates1.py`); the game's own saves `save games/pp_ai_*.eu5`.
Save engine tables used (eu5-game-parser, added for this study): `building_candidates` (AI queue with utility),
`constructions` (who builds what, where), `country_ai` (treasury, income, expense, queue timers), `war_participants`,
`estates` (estate treasury and planned project).

Labels: **verified** = seen in the data or caused in an experiment; **inferred** = consistent with the data, not
tested directly.

## 1. Who builds

Of all building constructions started June 1337 - August 1340 (2,680 distinct ones):

| Builder | Share | Builds mostly |
|---|---|---|
| Country AI | 62 % | cookshops, taverns, masons, villages, guilds, libraries, sergeantries, granges |
| Nobles estate | 32 % | land clearance, field drainage, irrigation, irrigated fields, masons, granaries, noble buildings |
| Burghers estate | 3.5 % | local markets, burgher mansions, gravel roads |
| Clergy estate | 2 % | scriptoria, shrines |
| Others (peasants, crown, tribes, ...) | ~0 | - |

Over 100 years the country share rises to 75 % (1,400 of ~1,880 running constructions in 1437); nobles stay at
~400-450. Roads, rank upgrades and RGO expansions also run through the same queue (see 2.1).

## 2. Country AI

### 2.1 The queue (verified)

- Every country keeps a **building queue** in its AI memory (`ai_memory.building_candidates`): building type +
  location (or a road with target, a rank upgrade, an RGO expansion), each with a **utility** score. Typical length:
  5-40 entries; ~4,200 entries world-wide.
- The queue is **stable**: 93-98 % of entries survive from month to month. At game start queues fill up country by
  country over ~3 weeks (71 countries on day 2, 990 on day 18). Vanilla define `AI_CONSTRUCTION_QUEUE_CLEAR_MONTHS = 60`
  purges it every 5 years (inferred from the define; `building_queue_clear <TAG>` does it by console).
- After a level is built, the AI queues the **next level of the same building** with `iteration = level` (define
  `AI_CONSTRUCTION_QUEUE_REPEAT_MULT = 0.9`: utility × 0.9^iteration).
- Console: `building_queue_top/buildings/stats <TAG>` (output also lands in `logs/debug.log` as `console_success`
  lines).

### 2.2 Monthly selection (verified)

Each month the country walks its queue **from the highest utility down** and starts entries:

1. **Top utility first.** 90-100 % of country-started buildings were in the queue a month earlier at the same
   location; countries that start one building a month take the **rank-1 entry in 86 %** of cases. The stored queue
   order is irrelevant.
2. **Money gate.** It starts an entry only if the treasury covers the price: only 2.8 % of 2,345 starts had gold below
   the price paid (median treasury/price 2.8, 10th percentile 1.08). Age-1 buildings cost ~25-80 gold, and a
   construction takes 365 days.
3. **Starts per month = floor(1 + owned locations × 0.025)**, max 30 (vanilla `AI_CONSTRUCTION_QUEUE_PARALLEL_BUILD_RATIO`
   / `_MAX`): 98.8 % of country-months stay within it, 92 % hit it exactly. Most countries are small: 1 start a month.
   The 30-cap countries (median treasury ~11,000) go down to queue rank 15-30, which is how villages and clay pits
   get built (their median queue rank at start is 15-27).
4. Constructions already running do not block new ones.

### 2.3 What makes a country build more or less

Build rate = share of country-months with at least one start (countries with a queue):

| Treasury | peace, surplus | peace, deficit | war, surplus | war, deficit |
|---|---|---|---|---|
| < 50 | 1.8 % | 0.6 % | 1.6 % | 0.3 % |
| 50-150 | 11 % | 5.5 % | 5.4 % | 5.1 % |
| 150-500 | 22 % | 10 % | 16 % | 4.6 % |
| ≥ 500 | 50 % | 18 % | 30 % | 25 % (n=4) |

Experiments (same save, 1340.8.14, one month, control branch reloaded from the save; untreated countries behaved
identically in both branches = the runs are deterministic):

- **+300 gold to a random half of the 769 countries under 60 gold with a queue: 78 of 369 treated countries started a
  building within the month vs 8 in the control branch.** Money causes building (verified).
- **10 new wars among 20 countries that all built in the control month: 9 of 20 built in the war month, then 1-4 of 20
  per month**; the 20 untreated comparison countries built 20/20 as in the control. War suppresses the building queue
  (verified).
- **France (war with England since 1340.2, deficit 1337-1339) +3,000 gold, then also the queue cleared: no start from
  the queue in 4 months.** After the clear, France's new top was a town→city upgrade (Cahors, utility 1.6e11), then a
  sergeantry, eight gravel roads, cloth guilds; it built only army/navy plus 3 taverns (our yearly review script).
  England (same war) built 1 building in 3 years. A country at war with a deficit history is effectively frozen
  (verified for France/England; the exact budget rule is inferred).

The rank-based cadence define (`AI_CONSTRUCTION_DAILY_RANK_BASE_DIVISION`) is **not** visible: rank-0 countries build
in consecutive months.

### 2.4 Utility: what the data shows

- Highest utilities go to **non-producing buildings with military, control or religious modifiers**: sergeantry,
  city guard, stockade, castle, monastery, madrasa, royal court (log10 utility 10.9-11.8), then masons, granges,
  taverns, Victualling Yards, market villages, cookshops (10.4-10.6), producing guilds lower (9.9-10.2).
- After a queue reset, **rank upgrades** (town→city, median utility 5e11) and **gravel roads** (1e10) come first.
- Utility does **not** follow the building's actual profit (correlation ≈ 0.04 with market profit per level) and not
  its price (+0.22 across 51 types; age-1 prices are all similar). It is slightly higher in poorer locations (-0.2 with
  market access and development). The engine's scoring of modifiers is hard-coded; only defines steer it.

### 2.4b Utility algorithm: what the experiments established (2026-09-28)

Method: 40 peaceful mid-size countries, queues cleared with `building_queue_clear` in branches loaded fresh from one
save (1340.8.14), one change per branch, one month; the engine re-scores every candidate and the same candidates are
compared across branches (`~/pp_ai_run/ucompare.py`, `gold_shape.py`, `gold_curve.py`).

1. **Utility is computed once, when the entry enters the queue, and then frozen**: 98.8 % of surviving entries keep
   exactly the same value month to month (163,183 checks). A queue can hold years-old scores (France's top cookshop
   kept one value for 3 years). Any model must use the state at insertion time.
2. **Utility depends on the country's treasury, saturating**: with the treasury set to exactly 30 / 100 / 300 / 1,000 /
   3,000 / 10,000 gold, each candidate follows **u ≈ A + B · min(gold, K)** (median R² 0.988 over 82 candidates;
   g/(g+K) 0.966, 1-e^(-g/K) 0.990 median but worse tails, log 0.864). From 100 to 1,000 gold utilities rise ×4.4
   (median), from 1,000 to 10,000 ×1.03.
3. **K is a property of the country**, nearly equal for all its candidates (Dughlat 250-266, Qun 1,000-1,097, Denmark
   310-385), ranging ~250 to ~8,000 gold. It tracks the country's **loan capacity** best (log correlation 0.83; K ≈
   0.2-1.0 × loan capacity), expense 0.72, income 0.52. Six treasury levels pin K only to the interval between two
   levels.
4. **A and B are candidate-specific** and not simply "benefit × (gold − price)": A/B ranges ~24-900 gold. Because the
   gold term scales candidates differently, the order inside a country changes with the treasury in 85 of 402
   candidate pairs.
5. **Across countries, utility falls with country size** (within a building type, correlation -0.5 to -0.7 with owned
   locations): scores are relative to the country and only comparable inside one queue.
6. Observable features (building type, location population/development/market access/control, expected profit from
   the production-method recipes at market prices, level, follow-up iteration, country size and treasury) explain
   R² ≈ 0.50 of log utility; the rest comes from engine terms the save does not show (per-modifier valuations,
   goods-shortage bonuses, worker availability).

**Not yet exact.** Still open: the formula of A and B per building (the modifier valuation), the exact K. The fastest
way to exact coefficients is a define sweep (each `NAI` utility define changes one term: `AI_GLOBAL_BUILDING_COST_UTIL`,
`AI_DEVELOPMENT_UTILITY`, `AI_PROFIT_MARGIN_TARGET`, `AI_GOLD_COST_UTIL_FROM_LOW_PROFIT_MARGIN`,
`AI_UTILITY_PER_CAPITA_*`, the shortage factors) with the same clear-and-rescore method; defines hot-reload in debug
mode but need a mod in the active playset to carry them. Next console experiments: a finer treasury grid around K,
loan capacity changes, and market prices via `stockpile` per good.

### 2.5 Where (verified, queue of 1340.8.14)

Percentile of each queued location inside its own country (0 = the country's top location, 0.5 = middle; countries
with ≥ 5 locations, 4,000+ candidates):

| Placement | Building types | population / development / market access |
|---|---|---|
| Country's top towns | cloth, fine cloth, glass, jewelry, tools guilds, winery, hired labour yard, clay pit, bridge | 0.05-0.2 / 0.05-0.2 / 0.05-0.35 |
| Populous, any development | rural glassmaker, rural daywork yard, forest/fishing village, irrigation | 0.15-0.3 / 0.3-0.5 |
| Anywhere | cookshop, tavern, mason, tar kiln, rural clothmaker, market village, field management, land clearance | ~0.5 / ~0.5 / ~0.5 |

## 3. Estates (verified)

- An estate does **not** use a queue. It keeps **one planned project** (`estate_manager.database.*.building` +
  `location`, or a road): in 75-90 % of estate starts the save a month earlier had exactly that building at exactly
  that location as the plan.
- It starts the plan once its **own treasury** allows: nobles never build below 50 gold; with a plan they start in
  ~5-6 % of months at 50-250 gold and 44 % above 250.
- Median estate treasuries 1337-1340: nobles 33, clergy 10, **burghers 2.5**, everyone else < 1. That is why nobles
  do a third of all building and the others almost nothing.
- **Experiment (1437): +200 gold to the burghers of a random half of countries: in 190 of 490 treated countries the
  burghers started a construction within one month, in 2 of 469 untreated.** They built 104 gravel roads, 32 local
  markets, 30 burgher mansions, then guilds. Burghers are not unwilling, they are broke.

## 4. Mod scripts that build or remove buildings

Flagged since 2026-09-28 with `PPBLD;...` `error_log` lines and the location counters `pp_dbg_script_build` /
`pp_dbg_script_cull` (the counters only work from commit 15d35369 on: `change_variable` on an unset variable does
nothing). Logged 1340-1373 (lower bound, error.log rotates): 449 yearly-review culls of closed levels, 239 review
taverns, 85 river boatmen yards, 27 carrier inns, 18 transport offices, 7 coastal shipping offices (logistics
builder), 96 capacity culls (81 granges). Small next to the AI: tavern levels went from 1,359 (1340) to 11,779 (1437),
almost all from the AI queue.

## 5. 100 years (1341-1437, natural run)

| | 1341 | 1387 | 1437 |
|---|---|---|---|
| Building levels | 208,600 | 242,000 | 293,600 (+41 %) |
| Running building constructions | 1,231 | 1,620 | 1,882 |
| of them country / nobles | 788 / 382 | 989 / 483 | 1,405 / 369 |
| Country treasury median / 90th pct | 20 / 85 | 28 / 388 | 31 / 659 |

Countries build taverns first in every decade, then libraries, cookshops, granges, horse breeders, field management.
Taverns spread and stack: 1,335 locations × 1.0 levels (1340) → 4,242 locations × 2.8 levels, max 30 (1437), while
their `employed` stays ~0.001 (cookshops 1-2): the AI keeps adding levels to a building that is hardly staffed
(each built level re-queues the next one, section 2.1).
Nobles build land clearance, field drainage, irrigation, irrigated fields and masons throughout. The median country
stays at the money gate for 100 years while the richest tenth hoards.

## 6. Open

- The engine's modifier scoring behind the utility (why sergeantry beats cookshop) is not readable; a define sweep
  (e.g. `AI_DEVELOPMENT_UTILITY`, `AI_GLOBAL_BUILDING_COST_UTIL`) in the test mod would measure single terms.
- The exact war/deficit budget rule (France builds nothing with 3,300 gold and a surplus while at war).
- Whether estate plans are chosen by the estate's own profit (nobles pick capacity buildings consistently).

## 7. Method notes

- `tick_day N` advances **2N hours** in 1.3.11 (N=366 ≈ one month, 4,380 = one year; ~5 s per month, <60 s per year).
- The game autosaves once when a `tick_day` finishes (with the monthly autosave setting): tick + autosave replaces
  manual saves. Autosaves rotate after 100; `~/pp_ai_run/watch_auto.py` copies each one out.
- Console output (`building_queue_*`, `ai_monthly_print`, trigger results) is written to `logs/debug.log`.
- Observer mode blocks `declarewar`; use `effect c:A = { declare_war_with_cb = { target = c:B type = casus_belli:cb_war_from_event } }`.
- Money: `effect c:TAG = { add_gold = N }`, estates `add_gold_to_estate = { estate_type = estate_type:burghers_estate value = N }`.
