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

This public rulebook holds the game behaviour and what it means for building design. The measurement tooling and
engine-level notes are kept in a separate private research repository.

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
~400-450. Roads and rank upgrades also run through the same queue (see 2.1). RGO upgrades never appear in it in any PP save checked. PP blocks RGO upgrades for all 52 raw materials (`block_rgo_upgrade = yes`), and in Jan's 1337–1398 run not a single existing RGO grew (only 293 new RGOs on newly settled land).

## 2. Country AI

### 2.1 The queue (verified)

- Every country keeps a **building queue** in its AI memory (`ai_memory.building_candidates`): building type +
  location (or a road with target, a rank upgrade, a town specialisation pair), each with a **utility** score. Typical length:
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
   - **It saves up for the top entry instead of taking a cheaper one** (PP AI Lab, 13,880 country-months,
     `lab/lab_saving.py`):

     | Top entry | Built nothing | Built the top entry | Built a lower entry instead |
     |---|---|---|---|
     | Too expensive (gold < price), 8,795 | 97.6 % | 1.9 % | 0.4 % |
     | Affordable, 5,085 | 81 % | 14 % | 4 % |

   - The 37 "lower instead" cases cost about the same as the top entry (median price ratio 1.0).
   - Even when it can afford the top entry, it starts it in only about 1 month in 5.
   - **Decoded 2026-09-29:** that is a gold buffer plus the processing interval.
     - The walk starts only when treasury ≥ the "Gold Buffer Target" = **3 × the country's tax base** (sum of
       location tax; `AI_BUFFER_TAX_BASE_FACTOR`, doubled in some war state).
     - Checked: the logged target ÷ (3 × Σ tax) has median 0.99, and 95 % of lab starts had treasury ≥ the target.
     - After the gate, an entry starts if the treasury covers its price. The first entry it cannot pay stops the walk.
     - Entries walked past leave the queue.
     - A country only processes its queue every max(4 − rank, 1) months: counties every 3, duchies every 2,
       kingdoms and empires monthly (`AI_CONSTRUCTION_DAILY_RANK_BASE_DIVISION`). The lab's gaps between starts
       are mostly 3, 6, 9 and 12 months.
   - **For PP:** poor, low-tax countries hit the buffer quickly. Raising a country's tax base raises the gold it
     keeps idle before it builds anything.
   - The price is already a cost inside the utility, so the queue order already weighs price against benefit.
   - Caveats:
     - Lab prices are the buildings' recorded prices, so "affordable" is approximate at the edge.
     - The lab rescores queues every month. In a normal game the entry it saves for can be an old, frozen score.
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

7. **The gold term is a multiplier, not a cost.** Fitting u = A + B·min(gold, K) per candidate gives B·K ≈ A + B·K:
   the utility at zero gold is only 1-13 % of the utility at full buffer (tags DGH 4 %, GRA 13 %, HAB 6 %, HOL 13 %,
   SGN and WAL 1-2 %). So **u ≈ V · (a₀ + (1 − a₀) · min(gold, K) / K)** with a₀ ≈ 0.02-0.13: a
   poor country scales its whole queue down, the order inside the queue barely moves (90-96 % of candidate pairs keep
   exactly the same ratio between neighbouring gold levels). K is the engine's "Gold Buffer Target" (label in the
   executable, see 2.4c).
8. **Mass re-score (2026-09-28, `pp_ai_U_ALL1`):** all 984 queues cleared on 1340.8.14, one month ticked: 4,297 fresh
   candidates in 709 countries, all scored on the same day. The engine is deterministic (two identical branches: 99.8 %
   of candidates identical, within-country spread 0.008 in log10 utility). Variance of log10 utility: country alone
   63 %, building type alone 33 %, **country × building type 91 %**; the location inside one (country, type) moves
   utility by a factor ~2 (sd 0.34 log10). So the AI mostly decides *which type* per country; the location rule is
   type-specific (cloth guild: R² 0.88 from margin, tax, control, rank; Victualling Yard 0.81 from tax/possible tax;
   ocean fishery 0.62 from control and tax; tavern 0.51 from pop-type population; glass guild 0.20).
   A LightGBM on all observable features predicts the within-country order of held-out countries only moderately
   (Spearman 0.57 median, top-1 hit 54 %): the missing part is the country-specific valuation of each modifier.
9. **Why a country prefers a type** (same type across countries, its utility relative to the country's other
   candidates): the more levels of that type the country already has, the lower the score (correlation grange -0.79,
   fine cloth guild -0.61, tar kiln -0.56, Victualling Yard -0.40, cookshop -0.39): the AI saturates on a type.
   Market margin helps only moderately (+0.2 to +0.4 for glass guild, scriptorium, furniture guild, rural clothmaker,
   winery, grange; ~0 for tavern, cookshop, Victualling Yard, whose value is not their goods profit).
10. **Queue refill timing:** after a clear, a queue stays empty until the country's monthly AI construction day and
   then refills completely in one step (FRA, ENG, CAS, HUN cleared 13 Sep, all four 0 for 17 days, then full on
   1 Oct: 43 / 34 / 61 / 47 entries).

### 2.4c The engine's own breakdown: console `ai_debug` (verified 2026-09-28)

`ai_debug` is an engine console variable. Typing `ai_debug` in the console answers "Enabled". Then, **playing a country**
(`tag FRA`), every build button in the Production panel (building → per-location list → hover "+") shows the AI's
values: *Gold Buffer Target*, *Build Queue Size*, *Available Maintenance*, *Maintenance Leeway*, *Expected profit
from scale of production*, **AI Utility**; hovering the AI Utility number opens **Reasons**, the term list. The terms
add up to the utility. France, 2 Oct 1340 (gold buffer target 1,564.6, queue 43):

| Building, location | Costs (gold → term) | Profit to state (→ term) | Estate enrichment | Other terms | AI utility |
|---|---|---|---|---|---|
| Cookshop, Paris | 37.23 → -0.2036 | 0.417 → +0.0959 | +0.0234 | Scaled modifier +0.0480, **Unscaled modifier +0.3394**, Food utility 0, multiplier 0.9 "Peasants in city" -0.0295 | +0.2657 |
| Field Management, Soissons | 229.99 → -1.2766 | -0.0099 → -0.0022 | 0 | Consuming input goods shortage -0.0681, **Unscaled modifier 0.0000** | -1.3470 |
| Tavern, Paris (1/31) | 15.78 → -0.0861 | 0.082 → +0.0188 | +0.0045 | Nobles ratio 0, Scaled modifier +0.0109, Unscaled modifier +0.0006 | -0.0570 |
| Sergeantry, Paris | 22.40 → -0.1223 | -0.657 → -0.1510 | 0 | Consuming input goods shortage -0.1029, Unscaled modifier +0.3086, **Capital modifier +31.4558** | +31.3880 |

Read off so far:
- **Cost term = -0.00546 × gold cost** (all four within 2 %, slightly steeper for the 230-gold building).
- **Profit term = 0.2299 × monthly profit to state**: one gold of monthly profit is worth ~42 gold of build cost.
- **Capital modifier** (sergeantry's country modifier when built in the capital) outweighs everything by 100×: why
  military/government buildings top every queue.
- **Unscaled modifier** = the valued `raw_modifier` lines. The cookshop's comes from the mod's footprint
  `local_population_capacity` and is its biggest term; Field Management's capacity effect is valued 0 (AI-blind
  `pp_wb_levels_*`), so a country never builds it, only estates do.
- "Peasants in city" = `PEASANT_BUILDING_IN_CITY_UTILITY_MULT` (0.9) applied to peasant buildings in cities: it
  multiplies the whole sum (utility = 0.9 × Σ terms).

**Per-modifier valuation (probe mod, 2026-09-28).** Test mod "PP AI Probe" (playset "PP AI Probe" = main mod + probe,
`eu5_playset.ps1 -Mode probe`, generator `~/pp_ai_run/probe/gen_pm_probes.py`) adds 71 one-gold-cost probe buildings
that each carry up to five of the 323 modifiers used by building definitions, one per block (`modifier`,
`raw_modifier`, `capital_modifier`, `market_center_modifier`, `capital_country_modifier`); each block is one line in
Reasons. Read for France in Paris (capital + market center), 13 Sep 1340. Table: `docs/data/ai_modifier_valuation_FRA_paris_1340.csv`
(modifier, block, probe amount, term, per unit, status).
- The same amount gives the same value in `modifier` (scaled) and `raw_modifier` and `capital_modifier`
  (`local_manpower` 0.015: 33.65 each; `local_population_capacity` 1: 0.688 each); values are linear in the amount
  for capacity (1 → 0.688, 10 → 6.884) but saturate for manpower (0.015 → 33.65 = 2,243/unit; 0.1 → 125.4 = 1,254/unit).
- **81 valued**, largest per probe: `local_manpower` (125 for 0.1), `monthly_legitimacy` 0.35 (36.8),
  `global_distance_from_capital_speed` 0.1 (34.4), `monthly_diplomats` 0.15 (21.2), `local_sailors` 0.13 (19.3),
  `monthly_towards_innovative`/`tolerance_own` (17-19), `monthly_towards_humanist` (-17.0 for France), `global_max_literacy`
  5 (13.8), `global_monthly_development` 0.01 (11.9), `selling_efficiency` 1 (11.1), `global_estate_max_tax` 0.1 (10.2),
  `monthly_gold_income` 20 (7.8), `local_trade_center_power` 0.05 (7.2), `fort_level` 2 (7.2), `research_speed_modifier`
  0.05 (6.9), `local_pop_conversion_speed` 0.1 (4.5), `local_monthly_development(_modifier)` (1-3.4), `local_crown_estate_power`
  0.25 (1.6), `local_production_efficiency` 0.1 (0.88), `local_population_capacity` 0.1 (0.07).
- **78 zero** (line shown, 0.0000): all `local_<good>_output_modifier` (in Paris), `local_monthly_food(_modifier)`,
  `local_*_food_consumption`, `local_max_control`, `local_monthly_control`, `local_garrison_size`, literacy caps,
  `local_migration_attraction`, `local_cultural_tradition`, `manpower_to_building_owner`.
- **164 no line** (AI-blind): every `farm_capacity_from_*` and `pp_wb_levels_*`, `local_market_access`,
  `local_food_decay_modifier`, `free_building_levels`, `local_supply_limit_modifier`, `local_build_buildings_efficiency`,
  `local_defensive`, `local_repair_speed`, `can_recruit_regiment_in_this_location`, `can_build_ships_in_this_location`,
  `merchant_power_from_building`, `maximum_stockpile_capacity`, `local_monthly_prosperity`, `local_life_expectancy`.
- `Country.GetAiUtility('<modifier>', '<amount>')` (GUI, shown by the probe mod's replacement of the `ai_currency_viewer`
  window) is the country-level currency curve and does **not** equal the building term (manpower 0.01 → 0.40 there).
- Cost term changes with the country's state but not with its treasury (France 13 Sep: 0.00681/gold at 365 and at
  5,365 gold; 2 Oct: 0.00546/gold) and is slightly convex (10 / 100 / 1,000-gold probes: 0.00681 / 0.00683 / 0.00701 per gold).

### 2.4e Measured at scale: the PP AI Lab run (2026-09-28)

Test mod "PP AI Lab" = live main mod (constructor 884115fa) + measurement layer (`~/pp_ai_run/lab/gen_lab.py --sync`):
`AI_CONSTRUCTIONS_CLEAR_QUEUE_MONTHS = 1` (every queue rescored monthly), `AI_EARLY_GAME_MONTHS = 0`, queue size min 120 /
2 × locations, monthly telemetry of summed country and location modifiers into save variables, 42 carrier-pair probe
buildings in every capital (scored, never built: 200 gold, allowed only below 40 gold). New game 1337.4 → 1339.5,
26 monthly saves: 228,000 freshly scored real candidates, 5,500 probe readings per modifier from 753 countries.

**Prediction (LightGBM on building, location, market, country and telemetry features; target = log utility relative to
the country's queue that month):**

| Test | R² | Spearman in queue | Top candidate right | Starts in the model's top k (true utility) |
|---|---|---|---|---|
| unseen months, type mean | 0.23 | 0.43 | 21 % | 30 % (76 %) |
| **unseen months, LightGBM** | **0.58** | **0.80** | **65 %** | **51 % (76 %)** |
| unseen countries, LightGBM | 0.36 | 0.75 | 56 % | 47 % (72 %) |

82 % of country building starts come from the previous month's queue. Strongest predictors after building type: output
price vs default, output value, margin, supply/demand of the output, loan capacity, gold, levels of the type already in
the country, control. On probe countries, adding the probe-measured value of the candidate's modifiers raises the
in-queue Spearman from 0.68 to 0.75.

**What the probes say (value of the tested modifier on top of a 0.5 local-manpower building, relative to that
building; `~/pp_ai_run/lab/lab_probe_summary.csv`):**
- Valued in (almost) every country-month: local and global development, monthly gold income, trade-centre power, fort
  level, sailors, local population growth, max literacy, institution growth, estate max tax, research speed, crown
  power, gold to building owner. Relative value falls with country size (Spearman -0.5 to -0.75 with owned locations).
- Never valued: `local_market_access`, `local_max_control`, `local_migration_attraction`, and more `local_manpower`
  beyond 0.5 (saturated).
- Conditional: `local_monthly_food` 30 % of country-months, `local_food_capacity` 48 % (more in populous capitals,
  +0.50), `local_population_capacity` 47 % (+0.34 with capital population), `monthly_legitimacy` 47 %, harbour 45 %;
  rarely: wheat output 22 %, noble power 8 %, food purchase 7 %, monthly literacy 2 %.

**Does the known shape help prediction? (`lab_structured.py`, `lab_formula.py`)** The probe values were turned into value
curves per modifier (country + capital state → value per unit). They give every candidate a structural modifier value
Σ amount × value.
- Added to LightGBM: on unseen months, top candidate right 64.7 → 65.7 % and starts in top k 52.8 → 54.5 %. On unseen
  countries it adds nothing.
- The pure formula, 0.9^[peasants in city] × softplus(category + a·margin + b·cost + c·modifier value), reaches only
  Spearman 0.38–0.48 and top candidate 21–27 %. The fit gives cost a positive sign and the modifier value a weight of about 0.

The shape is right, but its inputs are not observed. The terms that order the queue (profit to state, estate
enrichment, Food Utility, location-dependent modifier values) are computed by the engine from quantities that a market
margin and capital-only probes do not reproduce. The next gain is reading those terms from the engine's own
breakdown (2.4f), not a better model.

### 2.4f The engine's own breakdown for every candidate (logged, 2026-09-28)

**Method.** The same term breakdown the `ai_debug` tooltip shows (2.4c) was logged for every candidate the engine
scored during one month. The tooling is in the private research repository.

The run: 1339.5.3 → 1339.6.3 in the PP AI Lab game, 161,064 scored candidates, save `pp_ai_lab_h01`. 99.5 % of the
saved queue entries match a logged row exactly on the raw utility.

**Exact facts:**
- **Saved utility = utility × 2^30** (engine fixed point). There is no gold factor on the whole utility.
- **Every term is a currency change priced on the country's currency curve.** The building's effect becomes a change of
  a currency (gold, estate enrichment, province food stockpile, conversion, estate power, …). The change is multiplied
  by a time multiplier and valued by "utility of moving <currency> from A to B".
- **Gold utility is exactly U(g) = a·ln(g + a·L)**, with L = loan capacity. The per-country fit error is 0.000, and
  b = a·L holds in almost all countries. So the first gold coin is worth 1/L, and a is about 0.18 (0.08–0.2).
  Only countries hoarding far above their buffer target (MAL, PAP) deviate.
- **Time multiplier T, one per country** (the planning horizon in months), observed from 24 to 833.33; costs can
  reach 2,400. Cost, estate enrichment and all modifier terms use T. Profit to state uses T·√min(T, 833.33)
  (GLH: T = 24 → 117.58 = 24^1.5), so profit weighs far more in long-horizon countries.
  - T is longer for countries with gold and much shorter for countries in debt.
  - It is small for large countries and for countries in deficit (FRA 42, HCN 28), median 328.
- **Cost term ≈ inherent × 1.2 × "affects self" multiplier.**
- **The cost is the real price** (`cost_check.py`). The "Costs X gold" amount equals the gold the construction actually
  charged, to 0.001 %, for 33 of the 47 country constructions started during the logged month.
  - So it is the fully modified price, as of the moment of scoring.
  - The other 14 have no candidate scored at that price. This fits queue scores being frozen at insertion: the
    utility keeps the old price, while the start pays the current one.
- **Gates on all 161k scored candidates:**
  - "Too low profit margin" multiplies 31.5 % by 0.
  - 41 % end negative; only 27 % are positive.
  - Peasant buildings in cities get ×0.9 (8 %).
  - A "Per capita factor" (×0.3 … ×300) applies to 1.4 %.

**What orders the queue (real buildings, probes excluded, 8,152 entries).** Median utility is 0.8. By share of |terms|:

| Term | Share of \|terms\| | Spearman with utility in the queue |
|---|---|---|
| Scaled modifier | 30 % | 0.21 |
| Unscaled modifier | 27 % | 0.06 |
| Gold cost | 22 % | −0.07 |
| Profit to state | 9 % | 0.29 |
| Other (e.g. "producing goods used in construction") | 8 % | 0.18 |
| Estate enrichment | 2 % | 0.30 |

Rare large terms decide the top of queues:

| Building | Term | Mean value |
|---|---|---|
| Stockade | fort / zone of control | +846 |
| Castle | fort / zone of control | +111 |
| Cookshop | scaled modifier | +229 |
| Victualling yard | scaled modifier | +124 |
| Mason | producing goods for construction | +71 |

The scripts and tables behind this section are in the private research repository.

**Food is valued by the food situation, not as a flat bonus** (`food_value.py`, `stock_curve.py`, `vy_analysis.py`).
Province food state comes from the save: the engine's `province_food` table now has `food_current`,
`cached_food_change`, `base_food_consumption` and more.

Two currencies carry food:
- **ProvinceFoodStockpile, the storage switch (precise, 2026-09-28, `stock_exact.py`, 1 June re-score rows).**
  Storage capacity counts only while **Provincial Food stockpile ÷ monthly consumption < about 23 months**; above that
  it is worth exactly 0. That rule is right in 96.9 % of cases.
  - Store fill does not matter, and production only matters through the stock.
  - This matches the design target of 2 years of storage (Jan: "2 × 12 months") and the 24-month define
    `MARKET_FOOD_STOCKPILE_TRESHOLD_MONTHS = 24.0` (vanilla and PP). The value matches; that the AI reads this define is
    not proven. Test: change the define in the lab and see whether the switch moves.
  - Within a province the value is linear in the added capacity (no diminishing return); a log form fits no better.
  - The size scales like the food term (T² × market food price × gold marginal value) times a province factor that
    falls with province size (log correlation −0.40 to −0.47 with stock, capacity and consumption). The exact formula
    is not decoded yet.
- **ProvinceFoodStockpile (earlier, blurrier view).** The currency's value is the province's food **capacity**: "from"
  equals `max_food_value`, so +400 is valued as capacity C → C + 400. No food is created. It is valued only while the
  province's **stock** covers less than about **24 months of consumption**:

  | Stock in months of consumption | Share valued |
  |---|---|
  | ≤ 20 | 98–100 % |
  | 20–26 | falling |
  | over 30 | 0 % |

  **How full the store is does not matter.** Valued cases are often half-empty stores (log correlation of value with
  fill −0.17). The AI pays for capacity the province cannot use yet.

  The value per unit of T falls steeply with the province's size: about capacity^−1.3 × consumption^−0.4 ×
  added^0.5, which explains 54 % of the log value. On top of that sits a per-country factor (about 100× between
  countries).
  - +400 on a capacity of 130–500 is worth 1–9 per T, i.e. hundreds to thousands of utility.
  - +400 on a capacity of 4,000+ is worth 0.001–0.1 per T.

  Define `AI_PROVINCE_FOOD_STOCKPILE_UTILITY` (vanilla 0.1, PP 0.50) is "utility for province food stockpile modifier,
  upper limit based on total province food consumption change". How it enters the value is not decoded yet.

- **LocationFood.** Two things move it:
  - the `local_monthly_food` modifier;
  - a separate top-level **Food Utility** term: the building's output of goods with a food value (`local_food`
    food = 1, raw fish/rice), converted to monthly food.

  It is valued in about 42 % of positive changes, mostly where the location's food is low. Negative monthly food is
  penalised only when the province store is under about 65 % full or losing food fast (32 % of cases, small).
  **Victuals have food = 0**, so the victualling yard's output never counts as food. Cookshops, public kitchens,
  forest-village provisioning and fisheries do get Food Utility.

**The LocationFood term as an equation** (`lf_curve.py`, 22,163 monthly-food nodes of the month):

  V_food = T × c × (max(0, L + ΔF) − L)

- L is the location's LocationFood level, never below 0.
- ΔF is either the `local_monthly_food` amount, or, for the Food Utility term, the building's monthly output of goods
  with a food value × that food value (cookshop ≈ 19–25).
- T is the country's time horizon.
- **The value is linear.** c is one number per country (72 % of countries within 1 % across all their locations and
  provinces).
- **Solved** (`lf_exact.py`, 94 % of 904 unrounded rows within 3 %, median ratio 0.99):

    **c = T × P_food × a / (g + a·L)**,  so  **V_food = T² × P_food × ΔF × a / (g + a·L)**

  - P_food is the market food price of the location's market (PP: 0.00987–0.00993, since market food is off).
  - a / (g + a·L) is the marginal value of gold from the exact gold curve: g is gold at scoring, L is loan capacity.

  So the engine prices a month of food at the market food price, sums it over the horizon (× T), and values it as
  gold at the current marginal value, over the horizon again (× T). **Food scales with T², profit with T^1.5.**
  No food define appears in this term; the market food price does.
- **Losses are valued exactly like gains** (ratio 1.00 in the same location), but only down to L = 0. So
  `FOOD_NEGATIVE_IN_PROV_UTILITY` (PP 0.5) does not act in this term.
- **L is the location trigger `food_production`.** Checked in game: Bourganeuf 17.00004 logged vs 16.99–17.01 by
  console trigger; Brosse 36.28324 vs 36.27–36.30. In the interface it is the location Food tooltip line
  "Monthly production of +36.28": gross production, before Food Decay and Pop Food Consumption (both shown per
  location). The location trigger `food_consumption` reads 0, so it does not measure pop consumption.
- **The on/off switch in game terms** (`food_gate.py`, 10,669 nodes of the 1 June re-score): food counts only while the
  province's monthly Provincial Food change **without Food Decay** is negative (save: `cached_structural_food_change`
  < 0). This is right in 97.3 % of cases, and the misses sit near zero.
  - The save's `cached_food_change` (what the province tooltip shows as the monthly change) equals the structural
    change minus Food Decay.
  - Food Decay is about 1.5 % of the stockpile per month: exactly 0.0150 in full stores, 1.5–2.1 % elsewhere.
- Earlier empirical view of the same switch (store fill, food change), kept for reference:

  | Province state | Food valued |
  |---|---|
  | Store fill under 50 % | 63–69 % |
  | Store fill 50–75 % | 30 % |
  | Store fill 75–90 % | 7 % |
  | Store fill over 99 % | 0.4 % |
  | Losing over 50 food/month | 66 % |
  | Balanced or gaining | ≤ 10 % |

**Victualling yard, 273 queue entries:** median utility 10.8, p90 336.
- `+400 local_food_capacity` explains 70 % of the spread between yards. It is a heavy tail: the median food-capacity
  value is only 1–3, a few yards get several hundred.
- Sailors explain 10 %, profit to state 4 %. The −20 food adds nothing measurable.

No random jitter: the terms sum exactly to the saved utility.

**Population capacity (`local_population_capacity`, 70,306 nodes of the logged month).**
The capacity step is exact (to − from = added, in thousands). Two paths, switched by the location's fill before the
building:
- **Pop ≥ 90 % of capacity** (free land 1 − pop/capacity ≤ 0.10, sharp in the data):
  **V = `AI_LOCAL_POPULATION_CAPACITY_UTILITY` × T × Δcapacity**. The define is vanilla 0.01; PP does not set it.
  Ratio 0.0100 in 10,836 nodes. There is no gold marginal, food price or country size in it; only T. Negative
  capacity (footprint) costs the same per point.
  - **Confirmed:** the define counts when pop ÷ capacity > 0.90000 (5-decimal precision), or when capacity is 0.
  - **The 0.9 is a fixed engine threshold, not a define:** mods can change the value per point, not the switch.
- **Pop < 90 % of capacity:** the define part is 0. The only value comes from the change in the scale of the
  `available_free_land` static modifier (scale ≈ 1 − pop/capacity), valued through that modifier's contents.
  - In PP these are migration attraction, peasant food consumption, tribesmen growth and RGO output +30 %, and most
    of them are AI-blind.
  - The result is 30–100× smaller per point (median ratio 0.0001–0.0006). 15 % of these nodes, and most nodes
    without the child line, are exactly 0.
- In gold terms: cost is valued at about 1.2 × T × a/(g + a·L) per gold, so 1k capacity at capacity ≈ 0.046 × (g + a·L)
  gold of build cost. That is a few gold for a poor country and tens of gold for a rich one.
- Only 15 % of the month's capacity nodes were on the define path: in 1339 most PP locations sit well under capacity
  (median fill 0.4).

**Which modifiers the AI values: the complete list** (`docs/data/ai_modifier_valuation_all.csv`, 260 modifiers).
The first three groups come from every modifier line of every candidate scored in the logged month; the AI-blind group
comes from the probe run (2.4c).

| Status | Count | Meaning | Examples |
|---|---|---|---|
| always | 33 | valued in ≥ 95 % of candidates | manpower, sailors, development, trade-centre power, institution growth, max literacy, gold to owner, pop growth, fort level, research speed |
| conditional | 51 | valued only in some situations | population capacity (pop > 90 %), food capacity (stock < ~24 months), monthly food (province losing food), goods output modifiers, max control, garrison size, legitimacy, harbour, estate power |
| never | 16 | line shown, always 0 | desired pops (all estates), migration attraction, manpower to owner, maritime presence, some output modifiers (legumes, fibre crops, tea, sugar, coffee, horses) |
| ai_blind | 160 | no line at all | every `farm_capacity_from_*`, every `pp_wb_levels_*`, market access, food decay, free building levels, supply limit, stockpile capacity, merchant power from building, prosperity, life expectancy |

**Goods output modifiers** (`local_<good>_output_modifier`) are valued where the location produces the good:
- 78–100 % of the time when the location's RGO is that good;
- about 0–5 % elsewhere, except goods that buildings also make there (wheat 24 %, millet 32 %, livestock 42 %,
  fish 56 %).

So an output bonus on a building helps the AI only in locations that already make that good.

**How a goods output modifier is valued** (9,394 paired lines of the logged month; `outmod_*.py`). An output modifier
on a candidate counts twice. Both parts are gold per month, valued like profit (× T^1.5 on the gold curve).

1. **The modifier's own value** (the line under "Scaled/Unscaled Modifier").
   - Measured: value ÷ (T^1.5 × monthly gold × gold marginal) = 0.999 (median).
   - Its monthly gold is exactly linear in Δmodifier × price ÷ (1 + current modifier) within a location and good
     (spread 0.004 %).
   - **Its base is not decoded**, i.e. which output and which shares it counts.
2. **"X profit to state from <good> output"** (confirmed in the engine), added straight to the total utility:
   - Δmodifier × market price × base output of the good in the location. Base output = the location's RGO output of
     that good plus the output of the country's own buildings there making it, divided by the current output
     multiplier (1 + modifier).
   - × the state's cut: summed over the location's pop types, each type's share × the state's cut for that pop type.
     This is the in-game estate, crown-share and tax split, so it depends on the pops.
   - 0 where nothing of the good is made.

Part 1 ÷ part 2 differs by location and also between goods in the same location (median spread 37 %). So the two
parts do not use the same base; how they relate is open. Consequences that hold either way:
- No value where the good isn't produced.
- +10 % adds 10 % of the unmodified output, so there is no diminishing return from stacking.
- The value scales with the good's price and the location's production.
- The value scales with T^1.5 (the country's horizon) and the country's gold marginal.

**How a food consumption modifier is valued** (`local_clergy_food_consumption`, the only one on candidate buildings in
the logged month: 197 lines; `consumption_*.py`).
- It is turned into a change of the **LocationFood** currency, the same one as monthly food:
  **ΔF = −Δmodifier × pop of that type in the location (k) × that pop type's `pop_food_consumption`**.
  - Clergy in PP: 10. The fit is ΔF / (Δmod × clergy k) = −9.9999 where the save's pop matches the logged month.
  - It uses base consumption only: the location's current consumption modifier does not enter.
- It is then valued exactly like food (value ÷ (T² × food price × ΔF × gold marginal) = 0.999). It gets the same
  switch: it counts only while the province's food change without Food Decay is negative (26 of 197 lines), and only
  down to LocationFood = 0.
- More consumption is a loss. Less consumption would be a gain of the same size.
- `AI_POP_FOOD_CONSUMPTION_MODIFIER_UTILITY` (vanilla −0.05) does not enter this value; changing it does nothing
  here.
- Inferred, not measured: the other `local_<pop type>_food_consumption` modifiers work the same way with their own
  pop's consumption rate. None were on candidate buildings that month.

**Food price ×10 counterfactual** (`food_price_x10.py`).
- The lab month ran at market food price 0.0099. `pp_defines_adjustments.txt` now sets FOOD_PRICE = 0.10.
- The LocationFood part of each breakdown is linear in the price, so it was scaled by 10. Storage, profit and the
  on/off switch were left as logged.
- 38 of 576 countries change their top candidate.
- 872 rejected candidates turn positive.
- Taverns and cookshops move up. Victualling yards and granges move down relatively, because their value is mostly
  storage, which does not scale with the price.

**Production method switches** (`pm_switch.py`, consecutive monthly lab saves, margins at the earlier month's prices).
- About 1.4 % of method slots switch per month.
- Non-food → non-food: 81 % of switches go to the higher margin.
- Non-food → food: 99 % go to the higher margin.
- Food → non-food: only 4 % go to the higher margin. The AI leaves food methods even when they pay more, and these
  switches happen in provinces that are not in food deficit.
- The switching rule itself is not decoded yet.

**Fishing villages are not AI-built.**
- Zero AI constructions in the lab month.
- In Jan's game the count is flat from game start: 4,815 at start vs 4,674 buildings (7,615 levels) at 1398.3.6.
  They come from start placement.
- Queue utility median is 0.24. Their +0.5 population capacity is worth about 1.2, but only in locations over 90 %
  full (see above).

### 2.4d Utility terms and what the AI cannot value

- Utility terms (the `ai_debug` tooltip labels): *Unscaled Modifier* (`raw_modifier`), *Scaled Modifier* (`modifier`, scaled by
  employment), *Capital Modifier*, *Capital Country Modifier*, *Market Center Modifier*, *Profit to state*, *estate
  enrichment*, *Export profit*, *Expected profit from scale of production*, *Food Utility*, *Missing pop need*,
  *Missing military goods need*, *Producing / Consuming Input Goods Shortage*, *No market access*, *Per capita factor*,
  *Peasants in city*, *Location rank modifier*, *Upgrading Building*, *removal of obsolete upkeep*, *loss of
  satisfaction*, *Costs*, *Upgrade Cost*, *Too low profit margin*, *Profit Margin Multi*, *Maintenance Leeway*,
  *Available Maintenance*, *Build Queue Size*, *Gold Buffer Target*, *Proximity Candidate*.
- Each modifier is valued through the **AI currency** system (per-modifier "currency", *Time Multiplier*). The value of a modifier depends on the country's own
  state (how much it has and needs), which is why the same building scores so differently per country.
- **Modifiers the AI cannot value** (`ai_currency_misses` console command → `docs/ai_currency_misses.log`, hits in
  this run): `local_food_decay_modifier` 6,387, `free_building_levels` 5,198, `local_supply_limit_modifier` 3,545,
  `local_build_buildings_efficiency` 3,440, `local_construction_speed` 3,439, **`pp_wb_levels_irrigation_systems`
  1,837, `pp_wb_levels_field_management` 1,766, `pp_wb_levels_irrigated_fields` 877, `pp_wb_levels_incamisana` 34,
  every `farm_capacity_from_*`**, `merchant_power_from_building` 1,093, **`local_market_access` 567**,
  `local_marketplace_building_levels` 408, `maximum_stockpile_capacity` 73, `local_province_food_sales/purchase_output_modifier`,
  `pp_land_available`, `pp_province_food_storage_months`, the `local_<good>_output_modifier`s. A building whose point is
  one of these gets no utility for it; the AI builds it only for its other terms (profit, employment, capacity).
  `local_population_capacity` is **not** missed (valued).
- Console: `ai_currency_viewer` opens a window with each currency's utility curve; `dump_data_types` writes the GUI
  data functions to `logs/data_types/` (`Country.GetAiUtility(Arg0, Arg1)` returns the AI's valuation string of a
  modifier: the way to read per-country valuations from a test GUI).

**Not yet exact.** Still open: the formula of A and B per building (the modifier valuation), the exact K. The fastest
way to exact coefficients is a define sweep (each `NAI` utility define changes one term: `AI_GLOBAL_BUILDING_COST_UTIL`,
`AI_DEVELOPMENT_UTILITY`, `AI_PROFIT_MARGIN_TARGET`, `AI_GOLD_COST_UTIL_FROM_LOW_PROFIT_MARGIN`,
`AI_UTILITY_PER_CAPITA_*`, the shortage factors) with the same clear-and-rescore method; defines hot-reload in debug
mode but need a mod in the active playset to carry them. Next console experiments: a finer treasury grid around K,
loan capacity changes, and market prices via `stockpile` per good.

### 2.4g Farms in Jan's game (save 1398.3.6, FOOD_PRICE 0.10; `hook/farms_*.py`)

Measured from the save's queues and running constructions. The save has no term breakdowns.
- **Only countries build farms**: every crop farm is `forbidden_for_estates`.
- Running country constructions (started within the last year): horse breeders 43, fruit orchard 31, millet 28,
  wheat 23, legume 20, cattle 16, rice 8, fibre crops 6, hurdled sheepcotes 6, others 1–2.
  - Horse breeders stand out: 43 constructions against 508 existing buildings and 58 queue entries.
- **Farms are average queue entries.** Their median utility equals the country's median entry (relative log10 −0.01
  to −0.1), and they are rank 1 in only 3–18 % of queues.
- **The price of the farm's good does not order them.** The correlation of relative utility with price ÷ default price
  is −0.02.
- Farm entries in provinces losing food (27 % of provinces) are in the country's top 3 in 45 % of cases, against 29 %
  elsewhere. Horse breeders, which have no food effect, show the same shift, so this is not clean evidence of food
  valuation.

Expected from the valuation rules and the farm definitions (inferred, not measured on these farms):
- **Population capacity.** Crop farms carry `local_population_capacity = -5`; cattle, horse and sheep farms carry −2.
  In a location over 90 % full that costs 0.01 × T per point: about −15 utility at T 300 for a crop farm, −6 for the
  others. Below 90 % it costs nothing.
- **Food.** `local_monthly_food +1.5` and the provision method's local food count only in provinces losing food, with
  the 10× food price.
- **AI-blind:** `farm_capacity_from_*`.
- **Cross effects:** the legume and cattle farms' output bonuses for other crops count only where those crops are
  produced.

### 2.4h The AI's food slider (budget; save 1398.3.6, confirmed in the engine)

The food slider (`FoodMaintenance`) is set by the AI's budget routine, which sets all ten sliders. There is **no
utility valuation**: no currency and no food need enter it. It depends only on the country's saving mode (save:
`ai_memory.saving_mode`; engine table `country_ai.saving_mode`, `slider_*`).

| Saving mode | Countries | Food slider |
|---|---|---|
| none (normal) | 1,688 | always 100 % (fixed) |
| Low | 576 | 100 % (all but 3) |
| High | 170 | computed from the budget: 79 % sit at the 10 % floor, 12 % at 100 %, the rest between (mean 24 %) |

High saving mode:
- Rule: slider = min(1, 0.8 × free monthly money ÷ cost of a budget item at 100 %), at least 10 %, and that spend is
  taken from the free money before the court slider.
- The budget item it divides by is the **diplomatic** slider's cost, not the food bill. That looks like an engine
  quirk.
- In the same mode the AI sets the colonial, exploration, cultural and diplomatic sliders to 0.
- Province food shortages never raise the slider.
- In PP the slider barely matters: markets hold no food (FOOD_CAPACITY_FACTOR 0), and the bill is kept near 0 by
  `food_purchase_efficiency`.

### 2.4i Profit, the profit-margin gate and the whole utility (h02 run, 2026-09-29)

How the AI estimates a building's profit (confirmed against the logged breakdowns):
- It takes one level of the building. For every production-method group it picks the most profitable method among
  those allowed in the location whose inputs the market can supply. The groups add up.
- One method's profit = market access × (output × (1 + output modifiers) × market price − inputs × market price).
  Market access is clamped to 0..1. A good from another market is priced at its minimum price.
- A building that already stands in the location is judged by its active methods instead.
- The profit is split by the location's pops:
  - the state gets each pop type's share × its estate tax rate (at most 35 %) × a location factor × 0.95;
  - the estates get the rest ("estate enrichment").
  - So the state's share is the same for every building in one location. It is not tied to the building's own
    workers.
- Profit is valued as gold: √T × monthly profit on the gold curve, weighted by T·√T.

The **"Too low profit margin"** gate (utility × 0) hits about half of all candidates:
- It applies to buildings that produce goods whose margin is below **AI_BUILDING_PROFIT_THRESHOLD (1.2)**.
  Margin = revenue ÷ input cost.
- The margin that counts is that of the **last** method the estimate looks at, not the best one. For PP farms that
  is `sell_surplus` (no inputs, so the margin is huge): farms are almost never gated.
- A building never gets gated when its goods include one with `ai_rgo_expansion_priority` (clay, iron, gold, silver,
  stone, lumber, masonry).
- This predicts the gate for 90 % of candidates. Taverns are the main exception (half of them are gated and the rule
  does not tell which).

Horizons:
- Every currency is valued over T' = min(T, 833).
- The building cost uses the country's full T, which can reach 2,400.
- Gold is valued on the log gold curve; every other currency is linear in its amount.

The rebuilt utility (cost + profit + estate enrichment + every modifier's currencies, times the gate, 0.9 for peasant
buildings in cities and the per-capita factor):
- On 46k candidates of the h02 run it matches the engine within 5 % for 90 % of them (measured against the size of the
  candidate's terms).
- It orders each country's candidates like the engine (rank correlation 0.99).
- Each country's per-currency rates (manpower, sailors, merchant capacity, estate power, static modifiers, food
  stockpile) are still read from the run, not computed.

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

- The engine's modifier scoring behind the utility (why sergeantry beats cookshop) is not in the save. Two ways to
  measure it: a test GUI that prints `Country.GetAiUtility(...)` per modifier for chosen countries, and a define sweep
  (e.g. `AI_DEVELOPMENT_UTILITY`, `AI_GLOBAL_BUILDING_COST_UTIL`) with the clear-and-rescore method. Both need a test
  mod in the playset.
- The exact war/deficit budget rule (France builds nothing with 3,300 gold and a surplus while at war).
- Whether estate plans are chosen by the estate's own profit (nobles pick capacity buildings consistently).

## 7. Method notes

- `tick_day N` advances **2N hours** in 1.3.11 (N=366 ≈ one month, 4,380 = one year; ~5 s per month, <60 s per year).
- The game autosaves once when a `tick_day` finishes (with the monthly autosave setting): tick + autosave replaces
  manual saves. Autosaves rotate after 100; `~/pp_ai_run/watch_auto.py` copies each one out.
- Console output (`building_queue_*`, `ai_monthly_print`, trigger results) is written to `logs/debug.log`.
- Observer mode blocks `declarewar`; use `effect c:A = { declare_war_with_cb = { target = c:B type = casus_belli:cb_war_from_event } }`.
- Money: `effect c:TAG = { add_gold = N }`, estates `add_gold_to_estate = { estate_type = estate_type:burghers_estate value = N }`.
