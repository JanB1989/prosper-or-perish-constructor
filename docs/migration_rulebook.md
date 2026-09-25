# EU5 migration rulebook

Verified 2026-09-25 on EU5 1.3.11 with Prosper or Perish, from 10 monthly saves (1345.5-12) with per-location
dumps of `migration_attraction`, its modifiers and probe markers, checked against the game's own per-pop migration
records. Code: `src/prosper_or_perish_constructor/worldbuilder/migration.py` (engine rules),
`food_sim.py` (`migration = true` switch). Numbers are thousands of people (k) unless noted.

## 1. Channels

| Channel | Size (1345) | Mechanism |
|---|---|---|
| Market migration | ~20k people/month worldwide | this rulebook, monthly |
| Scripted migrations (`migration_manager`) | ~4.5k/month | `add_migration` effect: fixed amount per month for N months, province to province, one culture |
| Colonial charters | small | `colonial_migration_size` |
| Country action "Migrate Pops", expel, force-migrate peace term | ~0.9k/month | whole pops, player/AI action |

## 2. Market migration, once per month (at the monthly tick)

1. **Attraction** of a location: `A = local_migration_attraction + global_migration_attraction + (rural_migration_attraction if rank = rural_settlement else non_rural_migration_attraction)`. Script value `migration_attraction` returns it.
2. **Receivers**: the market's `migration={...}` list = its members with `A > average`, where the average is the plain mean of `A` over all market members, unowned ones included (saved as `average_migration_attraction`).
3. **Senders**: owned locations not on the list with at least 1,000 people. Smaller locations never send.
4. **Target**: one per sending location, used by all its pops.
   - Candidates: receivers in the same market with `A > A(source)` owned by the same country. Only if there are none: receivers of other countries.
   - Score = `(A(target) − A(source)) × exp(−distance / 480)`, distance = straight map-pixel distance between location centroids (≈ 900 km on the calibrated lon/lat). Highest score wins.
5. **Who moves**, pop by pop:
   - the pop type needs `local_<type>_migration_allowed` or `global_<type>_migration_allowed`. Base country: nobles, clergy, burghers yes; laborers, peasants, soldiers, tribesmen, slaves no. `province_starving` (mod) allows laborers and peasants; Free Peasantry allows peasants and laborers.
   - **room**: the target's size of that type must be below its `population_ratio` for that type (no ratio = no room). Peasants have no cap. A full target blocks; the pop does not look for another target. This makes nobles and clergy move every other month.
   - **abroad**: a pop only goes to a foreign target if its religion is the target country's primary religion or the target location's dominant religion. Others stay.
6. **How many**: per pop `max(0.001, size × migration_factor × (global_speed + local_speed) × (1 + global_speed_modifier + local_speed_modifier))`. `migration_factor`: nobles 1, clergy 1, tribesmen 1, burghers 0.5, laborers 0.1, peasants 0.1, soldiers 0.05, slaves 0.01. So most pops send exactly 1 person; starving provinces send ~1.5 % of nobles/clergy, 0.75 % of burghers and 0.15 % of peasants/laborers per month. Attraction never changes the amount.
7. Migrants keep culture and religion and join a matching pop at the target or form a new one.

## 3. What makes up attraction (per location)

| Term | Value × scale | Engine scale |
|---|---|---|
| `location_base_values` | +0.1 | always 1 |
| `development` | +0.0025 | development |
| `prosperity` | +0.1 | prosperity if > 0, else 0 |
| `surplus_jobs` | +2.0 (0.1 vanilla + 1.9 mod) | min(1, laborer jobs − laborers) in k; jobs = RGO worker slots + laborer building jobs (mod define `POP_JOB_SURPLUS_SCALE_CAP = 1`) |
| `unemployed_peasants` | −0.001 | unemployed peasants (k), approximately |
| `raw_material_relative_price` | +0.05 | relative price of the RGO good (can be negative) |
| `abundant_free_land` | +2.0 | 1 − pop/capacity when pop/capacity < 0.1 and pop < 10k |
| `available_free_land` | +1.0 | ≈ 1 − pop/capacity otherwise, while below capacity |
| `overpopulation` | −0.25 | max(0, pop/capacity − 1) |
| `province_starving` | −7.5 | province starving |
| `positive_province_food_growth` | +0.045 | stored food in years (marker `pp_province_food_storage_months` = 12 × scale) |
| `capital` / `province_capital` / `market_center` | +0.025 / +0.01 / +0.025 | 1 |
| RGO bonus `pp_rgo_bonus_<good>` | −0.05 … +0.1 | 1 |
| `pp_wb_lake` | +0.3 | 1 |
| buildings (`modifier` block) | 0.003 … 1.5 per level | employed levels |
| town rights | +0.1 … +0.33 | 1 |
| cabinet `promote_culture` / `promote_religion` | −0.15 on every location of the target province | ~1.3 … 1.9 (not the minister's skill; open) |
| cabinet `encourage_migration` | +1 on the target location | 1 |
| diseases (active outbreak) | −1.5 (plague −5.0) | outbreak |
| event and other timed modifiers | see `static_modifiers` | size |

For a simulation: take `A` from a dump and each month update only the dynamic terms (starving, free land,
overpopulation, surplus jobs, unemployed peasants, food storage, prosperity, development). This reproduced the next
month's `A` within 0.05 for 96 % of locations.

## 4. What makes up migration speed

- `global_migration_speed` = 0.0001 in every country (`country_base_values`).
- `local_migration_speed` = 0.015 × province starving (mod) + 0.0025 × overpopulation scale; plague +0.01, expel people
  +0.01, `granary_town` town right −0.5 (stops emigration).
- `global_migration_speed_modifier`: societal value individualism (+0.5) … communalism (−0.5) by slider position, laws
  (cameralism +0.1), privileges (free towns +0.05, libro d'argento −0.1, creaghts +1.0), cabinet encourage migration +0.5.
  Most countries in 1345 sit between −0.1 and −0.4.
- `local_migration_speed_modifier`: expel people +0.5.

## 5. Where it is in a save

- Location: `population.pop_stats.<type>.changes.MigrationIn/MigrationOut` (last month, per type) and
  `population.last_months_migrations = { from_pop destination pop_type pop_culture pop_religion amount allow }`
  (every moving pop with its target). `population_ratio` per type is the room cap.
- Market: `average_migration_attraction`, `migration={...}` (the receivers at the last tick, members order).
- Scripted migrations: `migration_manager`. Values change only on the monthly tick.
- Measuring kit, `tools/migration/`: copy `pp_mig.txt` (attraction, speed, allowed flags, starving) or `pp_mig3.txt`
  (plus land, food, jobs and probe scales) to `Documents/.../run/`, run it in the console before a save; values land in
  location/country variables (stored × 100000, negatives as unsigned 64-bit, booleans as 1e-05).
  `probe_*.txt` are the temporary marker files for engine scales. `save_extract.py SAVE OUT.pkl` parses a save
  (variables, flows, `last_months_migrations`, markets, buildings, town rights, countries). The in-game procedure is
  in `Documents/.../pp_testing/README.md`.

## 6. In the start-food simulator

`ppc worldbuilder food-sim --migration` (or `migration = true` in `[worldbuilder.start.food_sim]`) runs the rules above
between province/owner pools and drops the flat starving out-migration. Pool approximations: a pool stands for its
locations (average fixed attraction from base, development, setup statics, RGO bonus, market centre, province
capital and staffed buildings; dynamic terms from its state per average location), distance is km between pool
centres with decay 900 km, a capped pop type finds room while the target pool is below its start size
(`migration_room`), and the country speed modifier is one number (`migration_speed_modifier`, default 0). Religion
abroad is checked against the target pool's dominant religion. The exact location-level rules are
`migration.monthly_flows`.

## 7. Accuracy and open items

- Predicting every pop from the pre-tick state: 93–96 % of per-location outflow and 85–92 % of inflow by pop type,
  target of each sender 90–93 %, world volume within 3–4 %, also on months the rules were not fitted on.
- Remaining misses: near-ties between two targets and the few days between dump and tick.
- Open: the size of the promote culture/religion modifier; the exact laborer job count (building employment sizes).
