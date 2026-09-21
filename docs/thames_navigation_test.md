# Thames navigation prototype

An artificial London–Windsor experiment for **Prosper or Perish Building Test**.
It does not assert historical navigability, and does not implement global river
classification. It builds an overlay for the existing Building Test mod, whose
canal prices, upkeep production method and transport defines it uses.

## In-game test

1. Fully restart EU5. Enable only **Prosper or Perish Building Test**, without
   Navigable Rivers or another map mod. Start a fresh game as England.
2. Follow the Thames west from its existing sea zone. The new water locations are
   **Thames: London Reach**, **Thames: Upper Reach**, and
   **Thames: Permanent Barrier**, near Windsor.
3. Sail into London Reach, then Upper Reach. The first connection is navigable;
   the second is obstructed but passable. Record movement time and inspect the
   road/market-access tooltip before upgrading. Compare the same ship and route.
4. Try entering Permanent Barrier. It should reject fleet entry because it uses
   the same static impassable sea classification found in vanilla. This still
   needs an engine test, especially with a custom road pointing into it.
5. Build **Thames Navigation Works** in **London**. Its base price is 100 gold and
   base construction time is 30 days; ordinary modifiers can change these.
   The prerequisite test advance is granted to London's owner at game start.
   On completion, the London Reach–Upper Reach connection changes from
   **Obstructed River** to **Navigable River**. Repeat the same movement test and
   inspect market access around Harrow, Woking, Windsor and Wycombe.
6. Test an army crossing **London–Kingston**, then **Harrow–Kingston**.
   Seven original land adjacencies severed by the channel have explicit sea
   crossings. Also test **Henley–Windsor**, through the permanent barrier:
   whether a crossing through impassable water works needs engine verification.

The old Dover/Calais startup shipping experiment is disabled for new games. Its
road type remains defined so earlier experiments are not erased. A fresh start
does not place that extreme slowdown on the route to London.

## Water-to-land shore connections

The startup script now adds 14 roads, always declaring the water location as the
source and the adjacent land location as the target:

- London Reach → Rochester, Kingston, London, Barking: navigable.
- Upper Reach → Woking, Windsor, Kingston, Wycombe, Harrow, London: obstructed,
  with the +9900% movement penalty. London Navigation Works upgrades all six
  alongside the existing water-to-water connection.
- Permanent Barrier → Windsor, Reading, Wycombe, Henley: permanent-barrier type.

No reverse road creation is scripted. The documented `add_road_to` API has no
one-way flag, so this does not establish directional movement effects. Log lines
beginning `PP_THAMES_SHORE` report creation success and read-only reverse queries
for each edge. Test Harrow–Kingston in both directions before and after building
Thames Navigation Works to establish which connections army traversal uses.
A full restart and fresh game seed the new connections.

## Mechanics and limits

| State | Road level | Movement cost adjustment | Market cost adjustment |
|---|---:|---:|---:|
| Obstructed River | 8 | +9900% | +1500% |
| Permanent River Barrier | 9 | +200% | +1500% |
| Navigable River | 10 | −50% | −60% |

The obstructed connection now uses an extreme +9900% movement-cost probe to
check whether armies crossing its water location are also affected. Compare
Harrow–Kingston before and after completing the London navigation building.
The permanent barrier retains its +200% movement-cost adjustment.
The apparently large market penalty compensates for the existing test mod's
0.075 sea-distance factor: if these factors multiply, `0.075 × 16 = 1.2`,
roughly 20% costlier than an unmodified land distance factor of 1. That is a
calibration hypothesis, not a verified reconstruction of the engine formula.
The market may choose an alternative route, so displayed market access need not
change in proportion to this one edge. Neither test road changes proximity or
population movement.

The permanent barrier appears in both `sea_zones` and `impassable_mountains`,
with `ocean_wasteland` topography. Vanilla 1.3.11 has 47 locations in both lists.
The cost modifier is not what makes that location impassable. The local generated
effect documentation exposes road construction/addition, but no effect for
changing map impassability or topography during play. Consequently this test
does not promise a truly impassable-to-passable building upgrade.

Road types are disabled for ordinary construction. Only the London building
changes the selected edge. This is a one-way prototype: destroying the building
does not restore the obstruction, and ownership changes do not remove navigation
improvements. The building is limited to London and one level.

The raster follows the existing Thames river centerline, widened enough to meet
minimum location sizes. The three new zones contain 121, 144 and 116 pixels.
Small bank fragments are reassigned to adjoining land, with details in
`THAMES_TEST_REPORT.json`. Seven ports are assigned to valid shores, relevant
city/dock/unit anchors are supplied or adjusted, and vanilla location ordering
is preserved by appending a separate water-only hierarchy. The new area is
included in Western European starting discovery.

## Rebuild and validation

From the WSL repository, choose an empty staging directory:

```sh
uv run python tools/build_thames_navigation_test.py --output tmp/thames_stage
```

The tool reads the game install from `constructor.load_order.toml`. It never
deploys or runs the main mod build/sync. Copy its overlay only into the confirmed
Building Test target, with backups of overwritten files.

Checks include Clausewitz syntax, connected river zones, minimum areas, preserved
land connectivity, the exact adjacent edge chain, restored crossings, valid port
shore pixels and sea/impassable membership. These are static checks, not a game
launch or proof of navigation behavior.

Game log markers begin `PP_THAMES_TEST`. They check each road placement, the
upgrade and whether the obstructed type remains after replacement. The old
test's `has_road_of_type_to` errors revealed that its `type` field needs a scoped
`road_type:...` reference. The working `add_road_to` effect keeps its bare type
key. Custom canal price modifier definitions also address existing log warnings.

## References inspected

- [Navigable Rivers](https://steamcommunity.com/sharedfiles/filedetails/?id=3778399034):
  installed map data, ports, sea crossings and locator files; no global assets
  from the mod are copied into this experiment.
- [River_Barriers](https://github.com/mikejaklitsch/River_Barriers), commit
  `6d71be12bc6461011f9ca1bb58b0c3b60e35e63a`: sea/impassable classification,
  hierarchy ordering, ports, crossings and locator generation design.
- [Elevation_Friction](https://github.com/mikejaklitsch/Elevation_Friction), commit
  `13509f696c35c938cc423ebef3d9766fc6148f6c`: road variants encoding geographic
  edge costs, with construction disabled.
- Installed vanilla map data and the game's generated effect/trigger/event-target
  documentation. Engine behavior still requires the user's in-game test.
