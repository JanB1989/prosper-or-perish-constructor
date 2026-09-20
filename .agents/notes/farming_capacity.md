# Rural Capacity Design Notes

Updated 2026-09-20 for the World Builder capacity model. Use these notes before changing
`farm_capacity`, `fish_capacity`, `forest_capacity`, farm blueprints or the rural-capacity generator.

## Design Intent

- Population capacity flat = farmland. Attribute rows (World Builder classes) and improvement
  buildings add it; every farm building level takes land from it
  (`raw_modifier local_population_capacity = -land`, unscaled by staffing).
- Farm capacity is the land still held by subsistence farmers:
  `floor((modifier:local_population_capacity - reserve) / land)` in farming-village levels. Each
  farm building's max level uses its own land and reserve
  (`[worldbuilder.farm_land]` in `constructor.toml`: arable, plantation, herd classes) and adds its own
  levels back (its `farm_capacity_from_<building>` counter is -1 per level, so the row subtracts it),
  plus replaceable lower tiers. The max is the same number no matter how many of the building exist.
- No source other than the flat capacity enters farm capacity: no RGO size, no rank rows, no river
  rows, no improvement bridges. Fish and forest capacity keep their own geography rows.
- Improvement buildings (land clearance, field management, irrigation systems, paddies, bunds,
  drainage, polders, qanats) have `max_levels = pp_wb_cap_<key>` (base + attribute class terms +
  levels per development point x development) and gates from the World Builder contract.

## Tooltip Rule

`GetMaxLevelInformation` displays the rows of the scripted value used by `max_levels`. Farm values
show one "Free subsistence land" row and the building's own level row; keep them flat, no nested
helpers, no hidden totals.

## Performance Rule

Every farm cap is two cached modifier reads and arithmetic. Do not add `allow` gates that recompute
the same value.

## Relevant Files

- `scripts/generate_rural_capacity_values.py` (run by `ppc worldbuilder apply`)
- `src/prosper_or_perish_constructor/worldbuilder/` (contract, geography, modifiers, buildings, stage)
- `mod/.../in_game/common/script_values/pp_farming_capacity.txt`, `pp_fishing_capacity.txt`,
  `pp_forest_capacity.txt`, `pp_wb_building_caps.txt`
- `tests/test_worldbuilder_stage.py`

## Checks

```bash
uv run ppc test tests/test_worldbuilder_stage.py tests/test_project_config.py tests/test_building_upgrade_chains.py
uv run ppc worldbuilder check
uv run ppc blueprint parity
uv run eu5-orchestrator validate --project constructor.toml
```
