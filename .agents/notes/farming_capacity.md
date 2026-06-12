# Rural Capacity Design Notes

These notes capture the farming/fishing/forest capacity cleanup decisions from
the audit thread. Use them before changing `farm_capacity`, `fish_capacity`,
`forest_capacity`, capacity tooltip rows, or related map-mode/Europedia
localization.

## Design Intent

- Farming, Fishing, and Forest Capacity are each one visible remaining/free
  capacity value: a sum of sources that add capacity minus the buildings that
  already consume that capacity.
- Rural capacity building `max_levels` should use the matching flat
  per-building max value: `farm_capacity_max_<building_key>`,
  `fish_capacity_max_<building_key>`, or `forest_capacity_max_<building_key>`.
  These values equal remaining capacity plus that building's current level.
- A source either affects the capacity directly or it does not affect it.
- Avoid user-facing abstractions such as "capacity used", "available capacity",
  "gross capacity", generic capacity-improvement buckets, or separate
  capacity-cost pools for rural buildings.
- Existing farming, fishing, forest, and lumber buildings subtract their
  building levels directly from the relevant capacity. Water-control buildings,
  river size, population capacity, rank, RGO suitability, Maximum RGO Size,
  Manorial Customals, and other sources add or subtract as direct rows where
  relevant. The per-building max values copy those same rows and omit only that
  building's own capacity-consumption row.
- Performance may be revisited later, but not at the cost of making the visible
  tooltip stop showing the actual direct sources of the sum.

## Tooltip Rule

`GetMaxLevelInformation` displays the rows from the scripted value used by
`max_levels`. For rural-capacity buildings, hovering the max level in
`[building.getlevel]/[building.getmaxlevel]` should show every active plus or
minus to that capacity as rows.

It should not show hidden helper totals, inverted "sum" rows, or missing
localization keys. The previous complicated paths produced a tooltip with
correct source rows plus an extra missing-key row that was the opposite sign of
the visible source sum.

The practical fix is to keep `farm_capacity`, `fish_capacity`, and
`forest_capacity` as flat remaining-capacity paths, and to give each building a
separate flat max-level path:

- no nested helper values in the `max_levels` path;
- no `value = farm_capacity` plus an own-level add-back row;
- one `desc` per visible source row;
- source-specific labels such as `Farm Related RGO`, `Natural Fishing Grounds`,
  `Forest Geography and [rgo|e]`, `Maximum RGO Size`, `[river|e] Size`,
  `Location Rank`, linked building names, and
  `Reduced Capacity from [pp_buildings_in_location|e]`;
- no generic "Capacity Improvements" bucket for rural capacities.

## Performance Rule

For land-farm buildings, `max_levels = farm_capacity_max_<building_key>` is the
canonical capacity consumer. Do not also add `allow = { farm_capacity > 0 }` to
those building definitions unless an in-game regression proves it is required.
Profiling showed that duplicate gate as a major repeated evaluation cost
because the full flat capacity sum is calculated once for `allow` and again for
`max_levels`.

The core invariant is:

```text
max_levels(building X) = remaining_capacity + current_level_of_X
                       = total_capacity - levels_of_other_capacity_buildings
```

For example, if total farming capacity is 10 and the location has three
farming villages plus one fruit orchard, then `farm_capacity` is 6,
`farm_capacity_max_farming_village` is 9, and
`farm_capacity_max_fruit_orchard` is 7. The max-level tooltip should express
that by omitting the hovered building's own subtraction row, not by hiding an
add-back helper behind another value.

Fruit orchard is a special hotspot because it is a replaced vanilla building and
the engine evaluates its static location potential very frequently. Keep its
startup/setup exception list inside the single
`pp_fruit_orchard_location_potential` trigger so the live building potential and
game-start invalid-building cleanup ask one shared static question.

## River Size

River size needs small bridge modifiers, currently
`farm_capacity_from_river_size` and `fish_capacity_from_river_size`, injected
into the vanilla river static modifiers. These are not meant as second capacity
variables. They exist because checking `has_location_modifier =
river_flowing_through_X` directly did not produce the desired visible row for
locations like Prague, while reading the source-specific modifier does.

Keep the tooltip row labelled as river size. Do not collapse it into a generic
capacity-improvement bucket or a hidden gross-capacity row.

## Fishing and Forest Details

- `fish_capacity` includes natural fishing grounds, Maximum RGO Size scaling,
  river size, Manorial Customals, and direct fish-building level subtraction.
- Fish Maximum RGO Size scaling follows farming and forest capacity: it scales
  the baseline only. River size and Manorial Customals stay as separate visible
  rows, and fish should not get urbanization pressure.
- `forest_capacity` includes forest geography/RGO, Maximum RGO Size scaling,
  Manorial Customals, location-rank pressure, direct forest/lumber-building
  level subtraction, and reduced capacity from other buildings in the location.
- Manorial Customals and forest location-rank effects should be visible rows in
  the scripted value, not modifier buckets.
- Fish/forest map modes should show current capacity only and direct players to
  the building maximum-level tooltip for source breakdowns.

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
- Rural capacity map modes should show current capacity and direct players to
  the building maximum-level tooltip for the active source breakdown.

## Relevant Files

- `mod/Prosper or Perish (Population Growth & Food Rework)/in_game/common/script_values/pp_farming_capacity.txt`
- `mod/Prosper or Perish (Population Growth & Food Rework)/in_game/common/script_values/pp_fishing_capacity.txt`
- `mod/Prosper or Perish (Population Growth & Food Rework)/in_game/common/script_values/pp_forest_capacity.txt`
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
uv run ppc blueprint tag fishing_capacity
uv run ppc blueprint tag forest_capacity
uv run eu5-orchestrator validate --project constructor.toml
```

When Europedia text or the Europedia GUI filter changes, also run:

```bash
uv run ppc europedia
```
