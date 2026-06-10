# Farming Capacity Design Notes

These notes capture the farming-capacity cleanup decisions from the audit thread.
Use them before changing `farm_capacity`, farm-capacity tooltip rows, or related
map-mode/Europedia localization.

## Design Intent

- Farming Capacity is one value: a sum of sources that add or subtract capacity.
- Farm building `max_levels` should use `farm_capacity` directly.
- A source either affects Farming Capacity directly or it does not affect it.
- Avoid user-facing abstractions such as "capacity used", "available land-farm
  capacity", or separate farm-cost pools for farming buildings.
- Existing farming buildings subtract their building levels directly from
  `farm_capacity`. Water-control buildings, river size, population capacity,
  rank, RGO suitability, Maximum RGO Size, Manorial Customals, and other sources
  add or subtract as direct rows in that same value.
- Performance may be revisited later, but not at the cost of making the visible
  tooltip stop showing the actual direct sources of the sum.

## Tooltip Rule

`GetMaxLevelInformation` displays the rows from the scripted value used by
`max_levels`. For farming buildings, hovering the max level in
`[building.getlevel]/[building.getmaxlevel]` should show every active plus or
minus to Farming Capacity as rows.

It should not show hidden helper totals, inverted "sum" rows, or missing
localization keys. The previous complicated paths produced a tooltip with
correct source rows plus an extra missing-key row that was the opposite sign of
the visible source sum.

The practical fix was to make `farm_capacity` the flat public path:

- no nested farm-only helper values in the `max_levels` path;
- one `desc` per visible source row;
- source-specific labels such as `Farm Related RGO`, `Maximum RGO Size`,
  `[river|e] Size`, linked building names, and
  `Reduced Capacity from [pp_buildings_in_location|e]`;
- no generic "Farming Capacity Improvements" bucket for farm capacity.

## River Size

River size needs a small bridge modifier, currently
`farm_capacity_from_river_size`, injected into the vanilla river static
modifiers. This is not meant as a second capacity variable. It exists because
checking `has_location_modifier = river_flowing_through_X` directly did not
produce the desired visible row for locations like Prague, while
`modifier:farm_capacity_from_river_size` does.

Keep the tooltip row labelled as river size. Do not collapse it into a generic
capacity-improvement bucket.

## Localization

- Player-facing docs should explain concepts and where to inspect values, not
  hardcode balance numbers.
- Exact values belong in modifier effects, scripted-value rows, map-mode
  tooltips, and building tooltips.
- Link relevant concepts and buildings when the UI supports links:
  `[rgo|e]`, `[river|e]`, `[pp_population_capacity|e]`,
  `[pp_buildings_in_location|e]`, and
  `[ShowBuildingTypeName('...')|e]`.
- Europedia should refer to the concept as
  `Farming/Fishing/Forest Capacities` and tell players the capacity map modes
  are in the Geography map-mode group.
- The farming-capacity map mode should show current `farm_capacity` and direct
  players to the building maximum-level tooltip for the active source breakdown.

## Relevant Files

- `mod/Prosper or Perish (Population Growth & Food Rework)/in_game/common/script_values/pp_farming_capacity.txt`
- `mod/Prosper or Perish (Population Growth & Food Rework)/main_menu/common/static_modifiers/pp_location_modifier_adjustments.txt`
- `mod/Prosper or Perish (Population Growth & Food Rework)/main_menu/common/modifier_type_definitions/pp_building_cap_modifiers.txt`
- `mod/Prosper or Perish (Population Growth & Food Rework)/main_menu/common/modifier_icons/pp_building_cap_modifier_icons.txt`
- `mod/Prosper or Perish (Population Growth & Food Rework)/main_menu/localization/english/pp_building_adjustments_l_english.yml`
- `mod/Prosper or Perish (Population Growth & Food Rework)/main_menu/localization/english/pp_europedia_l_english.yml`
- `tests/test_project_config.py`

## Checks

Use the repo wrapper first:

```bash
uv run ppc --help
uv run ppc test tests/test_project_config.py tests/test_population_capacity_config.py tests/test_building_upgrade_chains.py tests/test_custom_map_mode_styles.py
uv run eu5-orchestrator validate --project constructor.toml
```

When Europedia text or the Europedia GUI filter changes, also run:

```bash
uv run ppc europedia
```
