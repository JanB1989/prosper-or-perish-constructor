# Establishment (know-how) for the craft lines

Branch `establishment-know-how` (2026-10-06, Jan). Goal: specialization and entrenched industries through know-how,
more trade of manufactured goods, no global buff.

## What changed

- EU5 1.4's building establishment is on (`ESTABLISHMENT_SYSTEM_ENABLED = yes`), only for the buildings of the 18
  final-goods manufacturing lines (beer, books, cannons, cloth, fine cloth, firearms, furniture, glass, jewelry,
  lacquerware, leather, liquor, naval supplies, porcelain, pottery, tools, weaponry, wine; 64 buildings). Dyes, paper
  and saltpeter are intermediate goods and stay out.
- A building's share = progress / `startup_ramp_target`. Below the threshold (1/3) it runs at share / threshold
  throughput (inputs and outputs alike); above it production efficiency grows to +20 % at full establishment
  (`STARTUP_MAX_PE_BONUS` 0.30 x (1 - 1/3)).
- Their producing methods make 0.9 of the old output: a mastered workshop makes 1.08, a newcomer 0.9 (market legs
  unchanged). Legacy methods follow (`ppc legacy apply`).
- Targets (points; gain = market access x (1 + local + global building speed) x (1 + per-good speed) x profit factor,
  about 0.5 per month in a typical country): guild tier 60 (beer, liquor, wine, pottery, leather), 90 (cloth, tools,
  glass, furniture, naval supplies), 120 (weaponry, firearms, cannons, fine cloth, books, jewelry, porcelain,
  lacquerware); workshop x1.25, manufactory x1.5, mill/factory x1.75. Halved from the first design because vanilla's
  burgher privileges and stability cut the speed by 52 % on average (Formal Guilds -33 %).
- Every other building has target 0: vanilla's shared ramp script values are 0 in the generated
  `default_values.txt` (`vanilla_food_productivity.zero_ramp_targets`).
- Defines: decay 1/month while closed, upgrades keep 50 %, profit cap 1 gold per level (vanilla 3), profit bonus up
  to x2. Crowded Establishment -10 % per other ramping building in the location (vanilla -30 %). AI cap stays 3.
- Game start: `pp_establishment_start` (+100000 per-good speed, 2 months) makes the start workshops fully established.
- Town rights of a craft (royal rights, charters, Flemish cloth, Bergslag, tar privileges, silk monopoly): +100 %
  establishment speed for their goods (halves the time).
- Cleanup (yearly country pulse): a craft building of these lines that is closed or has no workers on two yearly
  checks in a row is destroyed (location list `pp_est_idle` of building types, kept 2 years); new buildings are exempt
  for 8 years (`on_building_built` -> location list `pp_est_young`, df13ad39).

## Verified in game (new game, PP Main Test)

- No crash; defines load; all 7,978 start workshops fully established after the first month; others 0.
- Monthly gain matches the formula to the third decimal (London, Krakow, Buda); vanilla country speed averages -0.52.
- Throughput and bonus in the engine's market export: a new glass guild at 1.4 % throughput, established tools guilds
  at 1.24 x base output.
- Cleanup destroys idle crafts without script errors.
- The AI's profit estimate does not include a building's establishment bonus: the AI sees every craft at 0.9 output.
  Establishment reaches the AI only through the ramp delay for new buildings (expansions have none) and the cap.

## Test runs (2026-10-06, full world, PP Main Test, observer, 5-year autosaves)

- A = this branch without the young grace, 1337-1502 (playthrough 078a901e).
- B = this branch with the 8-year grace, 1337-1622 (078a901e_..._r1342_04_01, same start save pp_est_new0).
- C = clean baseline on the branch's base commit 118588aa, establishment off, 1337-1597 (79e10872).
- Older baselines 73a2a926 / cb516c0a ran on earlier commits and are not comparable for wealth.
- Kit: `tools/establishment_eval/` (spec_metrics, est_metrics, est_charts2, per_good, estab_sim replay).

B vs C at 1597:

| metric | B | C | B vs C |
| --- | --- | --- | --- |
| top-10 locations' share of staffed craft capacity (per good) | 6.9 % | 9.8 % | -29 % |
| craft levels in markets specialized >= 2x the world mix | 7.1 % | 9.7 % | -26 % |
| final craft goods traded between markets | 988 | 667 | +48 % |
| traded / supply | 3.3 % | 3.2 % | +6 % |
| exporting market-goods | 421 | 347 | +21 % |
| final craft goods supply | 29,572 | 21,160 | +40 % |
| craft price / default | 1.08 | 1.04 | +4 % |
| staffed craft capacity (k workers) | 6,643 | 4,639 | +43 % |
| levels per craft building | 2.51 | 2.04 | +23 % |
| new craft buildings per 5 years (1547-1597) | 507 | 149 | x3.4 |
| craft buildings gone per 5 years (1547-1597) | 350 | 55 | x6.4 |
| location wealth per 1k people | 262 | 174 | +51 % |
| burghers | 8.85 M | 7.03 M | +26 % |
| population | 529 | 534 | -1 % |

Findings:
- No specialization gain. Concentration rises in the first 60 years (the cleanup removes ~3,800 empty start
  workshops: 1402 top-10 share +17 %, trade share +17 %), then falls below the baseline: the AI founds 2.4-3.4x as many
  new workshops everywhere and the cleanup removes the ones that fail.
- The AI does not see establishment: its profit estimate uses location/country efficiency, not the building's bonus, so
  it never prefers expanding a mastered workshop; the ramp only delays its view of new ones.
- Survivors entrench (age 20: 0.47 gold per level vs 0.27 in the old baselines), newcomers face a valley of death
  (median 0.03 gold per level in the first years, 36 % unstaffed): ~1,000 of 3,800 new workshops died within 10 years
  even with the grace (A: 1,440 of 4,000; baseline: 25).
- Global effect (against "no global buffs"): building profits +61 %, tax and country gold +48 %, raw-material output
  +14 %, RGO-building levels +17 %, estate buildings +21 % by 1482. The AI's construction money shifts from crafts to
  RGO and estate buildings, and incumbents run at 1.08.
- Engine values hold in the run: ~92 % of craft levels fully established, ~97 % at full output; the cap of 3 ramping
  buildings binds in 20-40 locations.

## v2 (ef11fde2): mastery weight for the AI, craft output 0.8

- Producing methods of the 64 craft buildings make 0.8 of the old output (mastered 0.96).
- `ai_construct_weight` on each of them, only where the location already has the building (expansion): 0.2 x best
  own output x market price x min(market access, 1) x sqrt(owner gold + 100) x 0.2845. Script cannot read a
  building's establishment (only interface data functions exist), so the weight goes to every standing building; ~89 %
  of craft levels are fully established, so it is mostly the mastered ones.
- K fitted in game on twin buildings (copies of six craft buildings with 1.2x output vs copies with the weight, same
  location and pass): the AI values +20 % output at about +20 % of the candidate's own utility; median weight / true
  value 1.08, Spearman 0.33 (country state dominates). `tools/establishment_eval/calib/make_twins.py`.
- Run D = v2 from the same start save as B, 1337-1612 (playthrough 057c295e).

D vs B vs C at 1602:

| metric | D | B | C | D vs C |
| --- | --- | --- | --- | --- |
| top-10 locations' share of staffed craft capacity | 11.5 % | 6.9 % | 9.8 % | +18 % |
| craft levels in markets >= 2x world mix | 9.1 % | 6.4 % | 9.3 % | -2 % |
| final craft goods traded between markets | 781 | 902 | 608 | +28 % |
| traded / supply | 3.6 % | 3.1 % | 3.0 % | +21 % |
| final craft goods supply | 21,870 | 29,451 | 20,590 | +6 % |
| craft price / default | 1.09 | 1.08 | 1.05 | +4 % |
| staffed craft capacity (k workers) | 5,164 | 6,846 | 4,728 | +9 % |
| levels per craft building | 2.94 | 2.53 | 2.06 | +43 % |
| new / gone craft buildings per 5 years (1582-1602) | 496 / 369 | 555 / 377 | 179 / 46 | |
| location wealth per 1k people | 198 | 267 | 168 | +18 % |
| burghers | 7.33 M | 9.17 M | 7.15 M | +3 % |
| population | 554 | 533 | 536 | +3 % |

Findings:
- The economy no longer explodes: craft supply +6 %, staffed capacity +9 %, burghers +3 % (B: +43 %, +45 %, +28 %).
  Wealth per capita +18 % (B +59 %); most of it is price, not output (1422: craft profit equal on 24 % fewer workers;
  villages, RGO and rural workshops earn more on dearer cloth, glass, beer).
- Concentration in locations holds all game (top-10 share +57 % 1422, +35 % 1482, +18 % 1602; B fell below the
  baseline after 1480); workshops are deeper (2.94 levels). Market-level specialization stays at the baseline.
- The AI reacts to the weight: a working mastered workshop gains a level within 5 years 45-65 % more often than in B
  in the profitable half (2-3 % vs 1-2 %); new workshops expand far more often (~13 %) in both runs.
- Churn stays: 4,956 of 8,888 new workshops gone by 1592, 2,886 of them at age 5-9 (right after the grace), 80 % with
  no workers, median profit 0. The AI keeps founding level-1 workshops in markets that cannot carry them; without the
  cleanup they would sit empty (baseline: ~2,500).
- Trade: crafts traded +28 % (mass goods 3-6x: tools, weaponry, beer, wine, pottery, furniture); luxuries fell
  (fine cloth 61 vs 137, porcelain and lacquerware supply a third of C's). Traded share follows the base price
  (Spearman 0.54-0.68); every craft has transport cost 1 in PP (vanilla 0.5 for most). World merchant capacity grows
  ~40 % over 260 years in C while goods supply doubles (capacity per 100 units of supply 5.0 -> 3.2), use 92-95 % by
  1560: crafts compete with raw goods for a shrinking share; one unit = one capacity, the AI ranks trades by profit per
  (transport cost x path cost), maintenance 0.25 flat per unit.

## v3 (b5eeb4c9): full output at start, profit-driven mastery (run E, stopped at 1377)

- Threshold 0 (no throughput ramp), max bonus 0.20 (newcomer 0.8, mastered 0.96), profit cap 0.25 gold per level,
  profit bonus 9 (a profitable workshop learns 10x as fast as an idle one), targets 480 / 720 / 900 x tier, expansion
  weight K 0.85, craft transport cost 0.5, AI cap 5, cleanup grace 2 years and never subsidised buildings.
- Run E (playthrough 7c5f432a, new game) at 1377 vs C: crafts traded between markets +52 %, traded / supply 5.7 % vs
  3.7 %, exporting market-goods +55 %, market-level specialization +17 %, top-10 location share +43 %, supply -1 %,
  wealth +15 %. Learning workshops earn a median 0.16-0.2 gold per level; ~30 % of them idle.
- Shelved by Jan on 2026-10-06; the transport cost 0.5 went to 0.10 on its own (commit 00623863).

## Idea F (not built): town right = know-how

Nobody learns by default (location_base_values local_<good>_establishment_speed -1 for the 18 goods, per-good factor
0); a town right of the craft adds +2 (factor 1). Threshold 0, +10 % at mastery, small profit speedup (cap 0.5, bonus
0.5), crowding modifier emptied, AI cap 1000 (every non-learning craft building counts as ramping forever), original
outputs, no cleanup, no start modifier, no AI weight. Porcelain and lacquerware have no town right (add to the silk
monopoly). Open: how many town rights the AI takes.
