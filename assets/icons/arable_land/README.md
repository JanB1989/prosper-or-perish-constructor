# Arable Land icon

The tilled-field painting for **Arable Land** (the engine's population capacity; called Subsistence Land until
2026-10-10). Generated with the built-in image-generation tool; `arable_land.png` is the transparent source artwork.

`tools/build_arable_land_icons.py` exports it at 128 px (BC3/DXT5) into:

- `modifier_types/total_population_capacity_modifier.dds`: vanilla's population capacity concept icon;
- `map_modes/pp_population_capacity.dds`: the Arable Land map mode and the Europedia card header;
- `modifier_types/global_population_capacity_modifier.dds`: with vanilla's capacity mark (an arrow up to a bar), the
  icon every population capacity modifier type points at.

The same tool builds the three state icons (Abundant / Available / Overused Arable Land) from vanilla parts.
`preview.png` is the old 64 px export sheet.

## Generation prompt

Create one production-ready small strategy-game UI icon for 'Subsistence Land', matching richly painted historical Europa Universalis style. Isolated compact three-quarter view diamond-shaped small patch of brown tilled earth with three broad clearly separated furrows, a few short muted green crop shoots, and one small bundle of golden grain growing at the rear edge. Land/soil is the dominant recognizable subject, grain is secondary. Warm ochre highlights, earthy brown, restrained sage green, light from upper left, crisp strong readable silhouette, hand-painted realistic material shading. Designed to stay legible at 32x32 and 64x64 pixels: bold few forms, no tiny details. Centered square image, artwork fills about 85 percent of canvas with even margins. True transparent background with alpha, no scene background, no sky, no text, no numbers, no UI frame, no badge, no arrow, no people, no house. Deliver a single standalone icon.
