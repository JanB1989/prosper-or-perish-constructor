# Procedural building icons

One folder per icon: `assets/icon_drawings/<icon>/draw.py` (the `<icon>` is the blueprint's
`icon.output_dds` without `.dds`, normally the building key). Each script defines `draw(icon)` using
`eu5_building_pipeline.iconkit`; the shared finalize step makes every icon match the measured vanilla
format. Rules, spec and the kit: `eu5-building-pipeline/docs/procedural_icons.md`.

```bash
# from ~/development/eu5-building-pipeline
EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
  --script ../ProsperOrPerishConstructor/assets/icon_drawings/<icon>/draw.py \
  --out ../ProsperOrPerishConstructor/artifacts/icons/<icon>
# which blueprints still use legacy art
uv run eu5-building icon status ../ProsperOrPerishConstructor/blueprints/accepted/buildings \
  --drawings ../ProsperOrPerishConstructor/assets/icon_drawings --legacy
# install into the blueprint source PNGs (then ppc build / sync)
uv run eu5-building icon install <blueprint.yml> ... --drawings ../ProsperOrPerishConstructor/assets/icon_drawings
```

Drawings are found by convention, so blueprints the build regenerates (crop farms, field
management, waterways) need no `drawing:` field.

## House style (mod author's direction)

Vanilla framing, camera and black silhouette outline (finalize adds the outline), and a finish that
is **slightly more realistic and very slightly less cartoony** than a flat icon: forms shaped by
light and shadow rather than lines, cast and contact shadows, material texture and colour
variation, believable proportions, little symmetry or repetition, weathering. Old icons show the
concept only; choose the composition that reads best at 64 px.

## Painterly helpers already written (copy what you need into your script)

Scripts must stay self-contained: copy helper functions, do not import from other drawings.

| Helper | Script | Use |
| --- | --- | --- |
| `stones`, `shingles`, `tint`, `union` | `cookshop` | stone blocks shaded as forms; tile roof with per-tile tone; clipped soft tint |
| `smoke`, `flame`, `ham`, `sausages`, `loaf`, `crock`, `log_end` | `cookshop` | fire, smoke, food, sealed crocks, firewood |
| `copper_pot`, `steam`, `grain_sack`, `quoins`, `bowl`, `jug` | `public_kitchen` | vessels, sacks of grain, dressed corner stones |
| `thatch`, `planks`, `cask`, `tankard`, `horse_head`, `hay` | `tavern` | thatched roof, board walls, painterly barrel, horse, hay |
| `bricks`, `cask`, `cask_end`, `crate`, `sack`, `rope` | `victualling_yard` | brick walls, casks standing and lying, crates, sacks, rope |
| `ashlar`, `kerb`, `water_strip`, `planks`, `timber`, `spout`, `canopy`, `weeds` | `canal_lock_works` | weathered masonry, coping, open water seen from above, squared beams, water jets, tree crowns, weeds |
| `gleaf`, `cherries`, `scatter`, `thatch`, `canopy`, `jute`, `shrub` | `coffee_grove` | glossy leaves, berries, grains on a surface, thatch, crowns, sacks, bushes |
| `vein`, `heap`, `chunk` (also in the kit) | `iron_mine` | ore veins, heaps of lumps |
| `net`, `fish`, `basket`, water band (also in the kit) | `ocean_fishery` | nets, fish, baskets, water buildings |
| `leaf`, `plant`, `bundle` (also in the kit) | `tobacco_farm` | broad-leaf crops, hanging bundles |

## Families and tiers

Buildings of one family or upgrade chain are drawn by one agent so they share materials, palette
and viewpoint, and so each tier visibly grows: more structure, better materials, more equipment.
Each icon must still read on its own and differ at a glance from its siblings and from vanilla.

## Agent rules

- Write only `assets/icon_drawings/<icon>/draw.py` for the icons you were given (create the folder),
  build outputs go to `artifacts/icons/<icon>/`. Scratch images go to your own scratchpad.
- Do not edit the kit, other drawings, blueprints, the mod folder or config; no git, no `ppc`.
- Shell: from Windows run `wsl.exe --exec bash -lc '<command>'`; if a command needs single quotes,
  put it in a script file.
- Look at `<icon>_compare_1x.png` first (does it read next to vanilla at game size?), then `_3x`.
- Done: every icon `on_spec: true` in its `metrics.json` and reads as its building. About 6-8 builds
  per icon at most. Report per icon: metrics line, what it shows, what still looks off.
