# Goods paintings

The market pictures of the mod's own goods (`icons/trade_goods/illustrations/icon_goods_<good>.dds`). The game shows a
good's picture across the top of its goods panel, behind the header of every market whose leading good it is, and in
building panels. Until 2026-11-01 offset, logistics, manual labour and surplus sales showed their icon on black there.

Provenance: painted on 2026-11-01 by Codex (GPT-6.1 Sol, high, its image generation), one run per good, three takes
each, from the brief below; Jan chose the takes in use the same day. Style references were four vanilla goods pictures (beer, tools, fish, wheat) and the mod's
victuals and Province Food pictures (`assets/icons/trade_goods/illustrations`).

| Good | a | b | c | Used |
| --- | --- | --- | --- | --- |
| offset | Bruges weigh house, a cask balanced against iron weights | Florentine banker's counting table | Ming counting house in Suzhou | b |
| logistics | Rhine river landing, barges and bales | Persian caravanserai at dawn | Banjara bullock caravan to a Deccan hill fort | c |
| manual_labor | cathedral building site, treadwheel crane | hiring square at dawn, the day's wage on the table | Ming canal dyke earthworks | b |
| province_food_sales | monastery grange, a loaded cart off to market | Nile granary on an Ottoman quay | Osaka rice warehouses (Edo) | a |

To use another take or add a good: cut the widest 1080 : 440 window around the middle of the painting, scale it to
1080 x 440 and save it as `assets/icons/trade_goods/illustrations/icon_goods_<good>.png`; the build writes the DDS
(`good_icons.py`, BC7 in one level; a test keeps every source at 1080 x 440). The province_food_sales takes came out
of Codex at 1080 x 440 already.

---

## Brief (shared by the four runs)

Every trade good in the game has a wide painted picture; four of the mod's goods have none. We want a real painting
for each, as good as the game's own and with real atmosphere: warm light, depth, a place you want to be in.

- Match the four vanilla goods pictures in composition, palette and finish: a painterly, richly detailed digital
  painting; warm, natural, slightly golden light; deep but not garish colour; the good's objects as a lush still life
  in the foreground, mostly in the left and right thirds; the place they belong to behind them, with depth.
- The mod's victuals and Province Food pictures show the life and mood we like. Figures are welcome where the good is
  people's work, but in the middle ground and secondary to the objects; no portrait close-ups.
- Late Middle Ages to early modern (1337 to 1837). No text, letters, numbers, logos, UI, frames, borders, watermarks
  or anything modern; writing on ledgers and coins illegible.
- Shown at 1080 x 440 (about 2.45 : 1); generated as wide as possible and cropped around the centre. In the market
  header the game draws a round chart over the middle and fades the sides, so the main objects sit in the left and
  right thirds and the centre is a calmer view into the depth.

Per good: what it is in the game (its description), its icon, and three scenes in three different places and
cultures (the table above).
