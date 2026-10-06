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
