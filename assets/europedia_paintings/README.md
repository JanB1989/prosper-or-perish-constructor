# Europedia banner paintings

The banner of every styled Europedia card is a painting of the page's topic in the style of the game's loading screens
(Jan, 2026-10-10: no more stitched landscapes). `tools/build_europedia_banners.py` cuts the 2900 x 500 strip out of each
painting here (the row it starts at is set per painting in that tool) and writes the DDS into the mod.

Provenance: painted on 2026-10-10 by Codex (GPT-6.1 Sol, high, its image generation) from the brief below. The style
references were the eleven vanilla loading screens, composed from their layers in the game's
`loading_screen/gfx/loading_screen_assets/00/images` (not committed: game art).

A new page: give Codex the same brief with one new picture (a culture and scene no other banner uses, the subject in the
middle band), save it here as `<card>.jpg`, add it to `PAINTINGS` in the tool, and run the tool.

---

# Brief: ten painted banner images for the Prosper or Perish Europedia

## What this is for
Prosper or Perish is a large economy, food and population mod for Europa Universalis V. Its repo is
`/home/jan/development/ProsperOrPerishConstructor` (WSL; the mod lives in `mod/Prosper or Perish (Population Growth & Food Rework)`).
The mod has its own in-game encyclopedia ("Europedia"). Every page (card) opens with a wide picture across the top, the
banner. It is shown at 1450 x 250 px (stored at 2900 x 500). Today these banners are stitched-together landscapes, and
they all look alike. We want each page to open with a real painting of its topic instead.

## The style: match the game's loading screens exactly
The game's own loading screens are in `style_references/` next to this file. Look at every one of them before you
start, and match their style as closely as you can:
- painterly, richly detailed digital oil painting in a historical genre-painting manner;
- warm, natural, slightly golden light; deep, saturated but not garish colour;
- crowded, lively scenes of ordinary people doing things, with several figures in the foreground cut off by the frame, a
  middle ground full of activity, and an atmospheric background;
- historically grounded clothing, tools, architecture and goods, from the late Middle Ages to the early modern era
  (1337 to 1837);
- a different culture and region for each picture, as the loading screens do: Europe, the Middle East, South Asia,
  East Asia, Africa, the Americas.

No text, letters, logos, UI, frames, borders, watermarks or anything modern.

## Format
- Wide landscape, as wide as you can generate (16:9 or wider), at the highest resolution you can.
- The picture is cut to a very wide strip (about 5.8 : 1) around its middle, so keep the subject and every face that
  matters inside the central horizontal band, roughly the middle 40 % of the height. Nothing important at the very top
  or bottom.
- Save each picture as PNG into `output/` next to this file as `<name>.png`, using the names below. If you cannot
  write there, tell me where the files are.

## The ten pictures (name: what the page is about, then the scene)
1. **labor**: hired hands. Idle peasants supply labour to their market; workshops buy it, and porters' halls, hiring fairs
   and slave gangs hire people out.
   Scene: a busy morning hiring fair or porters' quay in a Hanseatic or Flemish town. Porters heave sacks and barrels,
   day labourers wait to be hired, a foreman points, carts and cranes are behind.
2. **logistics**: goods reaching the market. River barges, coasters, carters and caravans carry goods to market; bulky
   goods cost more to move.
   Scene: a river landing below a walled Middle Eastern or Ottoman market town. Barges unload sacks and stone, camels and
   mules are loaded, carters and a caravan set off along the road.
3. **harvest**: fat years and lean years. Every September each region learns what its fields will give: good years
   bring surplus, bad years hunger.
   Scene: peasants in a wide grain field at harvest, scything and binding sheaves under golden sun, while on one side a
   dark storm front rolls in over the fields.
4. **arable_land**: the land a place can feed. Land is cleared, drained, irrigated and terraced; people and farms use it.
   Scene: villagers clearing forest and breaking new ground: felled trees, oxen pulling stumps, men digging a drainage
   ditch, a new field being ploughed beside the old village (Central or Eastern Europe).
5. **food**: the province store. There is no food market: food sits in the province's own store or is traded as goods.
   Scene: the great granary and storehouse of a South Asian town after the harvest. Workers carry sacks of grain up into
   the store, a scribe counts them, and baskets of rice, lentils and spices are everywhere.
6. **food_production**: how food gets into the store. Peasants grow it on their own plots; farms, fisheries, cookshops,
   granges, victualling yards and taverns make it.
   Scene: an East Asian river valley at work, with farmers planting in flooded rice paddies, fishermen landing their
   catch, and a village kitchen steaming with food.
7. **food_consumption**: who eats what. Every pop eats from the province store; nobles eat far more than peasants;
   winter and good times raise what people eat.
   Scene: a crowded Aztec or Mesoamerican market feast. Families eat at long tables, cooks serve from great pots, nobles
   are served richer dishes on a raised terrace, and children and dogs wait for scraps.
8. **rural_capacities**: room for farms, fisheries and forest villages.
   Scene: a northern coast at the edge of a forest. Woodcutters fell and haul timber, fishermen mend nets and pull boats
   up a shingle beach, small fields lie between (Scandinavia or Scotland).
9. **trade_goods**: victuals and other goods. Victuals are packed, traded and served again; there is manual labour too.
   Scene: a busy victualling yard at a harbour. Coopers seal casks of salted meat and fish, biscuit is packed, and
   provisions are rolled aboard a tall ship (Iberian or Portuguese port, late fifteenth century).
10. **population_growth**: towns grow from stored food. Full stores make people grow; empty ones make provinces shrink.
   Scene: a thriving West African (Ashanti) town in growth. New houses are being built, a crowded market is full of
   families and children, granaries are full, and newcomers arrive with their belongings.

## When you are done
List the ten files with their paths and one line per picture on what it shows. If a picture came out with text,
modern objects or a style far from the loading screens, make it again before you report.
