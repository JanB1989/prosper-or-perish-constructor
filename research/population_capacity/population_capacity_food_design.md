# Population Capacity and Food-System Design

This is the shared design reference for:

- [Location-capacity playground](location_capacity_playground.py)
- [Population-simulation playground](population_simulation_playground.py)

It defines what each modeled value means, how it is calculated, what it does in
gameplay, and the boundaries the implementation must respect.

| Element | Calculation | Calculation components | Meaning | Gameplay role | In-game restrictions | Objectives / boundaries |
|---|---|---|---|---|---|---|
| `population_capacity` | `(sum of absolute capacity values) × (sum of capacity modifiers)` | **Absolute:** `location_potential`, `infrastructure`<br>**Modifier:** `development` | Food resources currently available from the land.<br>At capacity, the population can barely feed itself locally. | Determines peasant food consumption and migration through `abundant_free_land`, `available_free_land`, and `overpopulation`. | Numeric value; minimum `0`. | Must fit EU5 starting populations.<br>No location may begin more than 15% over capacity. |
| `location_potential` | Calibrated flat capacity from natural resources. | Arable land, pasture, wild game, fish, freshwater, climate, and terrain. | The food-supporting potential of the natural, unimproved location. | Provides the permanent natural base of population capacity. | Flat, non-negative absolute capacity value. | Independent of infrastructure, development, and population.<br>Must provide most capacity in undeveloped locations without infrastructure. |
| `infrastructure` | `sum of flat capacity added by active infrastructure` | Irrigation systems, bunds, land clearing, polders, canals, and similar buildings. | Permanent human alterations that create or unlock additional food resources. | Buildings add flat population capacity for scaling construction and maintenance costs. | Each source adds a non-negative absolute capacity value. | Must be derived independently of population and be the main explanation for exceptional high-capacity locations. |
| `development` | Converts development points into a population-capacity modifier. | Current development and its capacity effect per point. | How thoroughly the location's land, labor, and food systems are organized and optimized. | Multiplies total capacity.<br>Development grows through investment, prosperity, parliament actions, and buildings. | Starting value bounded from `0` to `80`.<br>Applies to all absolute capacity. | Must be derived independently of population and be high in historically well-developed locations without replacing infrastructure as the explanation for extreme capacity. |
| `prosperity` | `previous prosperity + monthly gains - proportional decay` | Food stored, base prosperity changes, and other prosperity modifiers. | The location's current economic security and wellbeing. | Increases development over time and modifies population growth, food consumption, and unrest. | Bounded from `0` to `100`.<br>Effects scale linearly with prosperity. | Must reward sustained food security without creating an uncontrolled food–prosperity–development feedback loop. |
| `abundant_free_land` | Active when `population / capacity < 10%` and population is below `10,000`.<br>Strength: `1 - population / capacity`. | Population and population capacity. | The location has far more usable land and food resources than its population can exploit. | Strongly attracts migration and reduces peasant food consumption.<br>Current full-strength values: `+2` attraction, `-50%` consumption, `0` absolute monthly food. | Exclusive capacity-pressure state.<br>Strength ranges from `0` to `1`. | Reserved for genuinely small, sparsely populated frontier locations. |
| `available_free_land` | Active from `10%` through `100%` capacity.<br>Strength: `1 - population / capacity`. | Population and population capacity. | Productive land remains available, but becomes scarcer as population approaches capacity. | Attracts migration and reduces peasant food consumption.<br>Current full-strength values: `+1` attraction, `-32%` consumption, `0` absolute monthly food. | Exclusive capacity-pressure state.<br>Reaches zero strength at capacity. | Benefits must decline smoothly as capacity fills. |
| `overpopulation` | Active above capacity.<br>Strength: `population / capacity - 1`. | Population and population capacity. | The population exceeds what local resources can normally support. | Raises peasant food consumption, reduces migration attraction, and encourages outward migration.<br>Current full-strength values: `+100%` consumption and `-0.25` attraction. | Exclusive capacity-pressure state.<br>Strength is non-negative and currently uncapped. | No location may start above `0.15` strength.<br>Should create escalating pressure rather than immediate collapse. |
| `population_food_consumption` | `sum(population of each type × base food rate × max(0, 1 + consumption modifiers))` | Population by type, type-specific base rates, prosperity, capacity pressure, weather, and other modifiers. | The food required by the province's population each month. | Removes food from provincial storage and determines food surplus, food security, and food-supported population growth. | Effective consumption cannot be negative. | Must produce historically plausible demand while preserving meaningful differences between pop types. |
| `peasant_food_consumption` | `peasant population × 1.0 × max(0, 1 + peasant consumption modifiers)` | All peasants, including employed and unemployed peasants; capacity pressure, prosperity, and other peasant modifiers. | The total food consumed by the peasant population. | Usually the largest part of provincial food demand.<br>Free land reduces it; overpopulation and prosperity increase it. | Base rate is currently `1.0` food per peasant game unit per month.<br>Cannot fall below zero. | Must connect population capacity directly to food pressure without making peasants disappear from the food economy. |
| `subsistence_agriculture` | `unemployed peasants × subsistence rate` | Unemployed peasants and `SUBSISTENCE_AGRICULTURE`, currently `1.0`. | Food produced directly by peasants who are not employed in formal production. | Adds food to provincial storage and offsets the consumption of unemployed peasants. | Rate must be non-negative.<br>Only unemployed peasants produce it. | Should let unemployed peasants support themselves at baseline, but not sustain unlimited population independently of capacity. |
| `food_stored` | `max(0, previous food + food inflow - population consumption) × (1 - decay rate)` | Subsistence output, other food inflows, population consumption, and food decay. | The province's accumulated food reserve. | Buffers temporary deficits and determines food-supported population growth and prosperity. | Province-level stock; minimum `0`.<br>The current simulator does not yet enforce an upper storage capacity. | Must make sustained surpluses valuable and allow provinces to survive short shortages without making long-term deficits harmless. |
| `food_decay` | `food before decay × combined decay rate` | Global decay, climate, and storage-infrastructure modifiers. | Food lost through spoilage, pests, leakage, and inadequate storage. | Removes part of stored food every month and makes storage infrastructure valuable. | Loss cannot be negative or exceed the available stock.<br>The simulator currently uses a fixed `1%` monthly rate. | Climate and granaries should eventually modify it without making long-term storage either free or pointless. |
| `population_growth` | `new population = current population × (1 + total yearly growth)^(1/12)` | Stored-food growth, prosperity, location rank, capacity pressure, and other population-growth modifiers. | Natural population change from births and deaths.<br>Migration is separate. | Changes every pop type each month, which changes food consumption, capacity pressure, and future growth. | Population cannot become negative.<br>The same proportional growth normally applies to every pop type in the location. | Food security must remain the principal source of sustained growth.<br>Must reproduce plausible historical global and regional trajectories without runaway growth. |

## Agricultural-infrastructure split

Infrastructure is divided by physical task, but only where the existing EU5
catalogue has a real gap. Cultural names are regional names or production methods
unless they describe a different land transformation. Buildability uses only
EU5 attributes available in location scope: `topography`, `vegetation`,
`climate`, `soil_quality`, `raw_material`, `has_river`,
`is_adjacent_to_lake`, and `is_coastal`.

### Existing buildings retained

| Building key | Clear role |
|---|---|
| `irrigation_systems` | Surface irrigation canals supplied by a river or lake. |
| `bund` | Contour bunds, stone lines, and runoff-retaining field banks; no river or lake required. |
| `terraces` | Dry cultivation terraces on hills, mountains, and plateaus. |
| `polders` | Embanked and drained coastal or lakeside wetlands. |
| `khmer_baray` | The existing Khmer regional reservoir-and-rice system. |
| `incamisana` | The existing Andean regional terracing and water-management system. |
| `aqueduct_system` | Large-scale water conveyance into a location. |

### Six new buildings

| Building key | Player-facing name | Physical task | EU5 location-potential gate | Starting-placement evidence |
|---|---|---|---|---|
| `land_clearance` | Land Clearance | Converts woodland into maintained farmland through felling, grubbing, burning, stone removal, and control of regrowth; medieval European assarts are one historical form. | `vegetation` is `woods`, `forest`, or `jungle`; exclude `mountain_wasteland`, `atoll`, `soil_barren`, and `soil_permafrost`. | LUH2/PNV clearing increment, non-population HYDE cropland, land cover, and parsed farm buildings. |
| `field_drainage` | Drainage Ditches | Removes excess surface and root-zone water from inland wet ground using open ditches, ridges, and collector drains. | `topography = wetlands`; exclude coastal and lake-adjacent locations already covered by polders, plus barren and permafrost soil. | Inland wetlands, non-population HYDE cropland, land cover, terrain, and parsed drainage or farm buildings. |
| `irrigation_reservoirs` | Irrigation Reservoirs | Captures seasonal rainfall and runoff in tanks or small reservoirs, then releases it through sluices when rainfall fails. | No river or lake adjacency; `climate` is `tropical`, `subtropical`, `arid`, or `cold_arid`; `topography` is `flatland`, `hills`, or `plateau`; exclude barren and permafrost soil. | HYDE irrigation, precipitation seasonality, catchment and terrain evidence, and parsed reservoirs. Khmer baray remains the regional special form. |
| `qanats` | Qanats | Taps groundwater through gently sloping underground galleries, conveying it by gravity while limiting evaporation. | No river or lake adjacency; `climate` is `arid` or `cold_arid`; `vegetation` is `desert` or `sparse`; exclude wetlands, atolls, and mountain wasteland. | Existing groundwater-access pipeline, arid settlement evidence, HYDE irrigation, and parsed qanat/falaj buildings when available. |
| `irrigated_rice_paddies` | Irrigated Rice Paddies | Levels rice fields and encloses them with small bunds so rainfall or supplied water can be retained and controlled. | `raw_material = goods:rice`; `topography` is `flatland`, `hills`, `plateau`, or `wetlands`; exclude barren and permafrost soil. River or lake adjacency is not required. | HYDE rice and irrigation, GAEZ wet-rice suitability, terrain, and parsed rice infrastructure. |
| `raised_fields` | Raised Fields | Builds planting platforms above saturated ground while adjacent channels drain, irrigate, and provide fertile sediment. | `topography = wetlands`; exclude coastal locations already covered by polders, barren soil, and permafrost. | Inland wetlands, non-population HYDE cropland, freshwater and land-cover evidence, and regional raised-field evidence. Chinampas and waru-waru are regional forms. |

These gates control where a player may construct a building. Starting levels are
stricter and must come from the independent evidence in the final column; mere
eligibility never proves that the infrastructure existed in 1337. Irrigation
evidence must be partitioned so canals, reservoirs, qanats, and rice paddies do
not each claim the same irrigated area.

Water-lifting devices such as shadufs, sakias, norias, Persian wheels, and chain
pumps belong under `irrigation_systems` or `qanats` as production methods. Spate
irrigation combines irrigation canals with contour bunds. Water meadows belong
under irrigation production methods, while subak, falaj, foggara, khettara,
chinampa, waru-waru, and dyke-pond systems are regional names or production
methods on the closest physical building rather than additional global types.

Historical design references include FAO's descriptions of [tank cascades](https://www.fao.org/giahs/giahs-around-the-world/sri-lanka-cascaded-tank-village-system/en),
[field drainage](https://www.fao.org/4/Y3796E/y3796e06.htm),
[spate irrigation](https://www.fao.org/4/i1680e/i1680e00.htm),
[chinampas](https://www.fao.org/giahs/giahs-around-the-world/mexico-chinampas-agricultural-system/en),
[Kuttanad reclamation](https://www.fao.org/giahs/giahs-around-the-world/india-kuttanad-farming-system/en),
and [dyke-pond agriculture](https://www.fao.org/giahs/giahs-around-the-world/china-zhejiang-huzhou-system/en),
UNESCO's descriptions of [qanats](https://whc.unesco.org/en/list/1506/) and
[Balinese subak](https://whc.unesco.org/en/list/1194/), and Historic England's
evidence for [woodland assarting](https://historicengland.org.uk/research/results/reports/5427/TheForestofDeanMappingProjectGloucestershire_AReportfortheNationalMappingProgramme).

## Population-capacity tuning requirements

The capacity inputs and modifiers must remain tunable enough to satisfy all of
the following requirements together:

- Starting population is validation-only. Other than testing the overpopulation
  boundary, it must never determine `location_potential`, `development`, or
  `infrastructure`. Those values must come from independent GAEZ and
  non-population HYDE evidence such as land suitability, cropland, pasture, and
  irrigation.
- At game start, no location may exceed `115%` of its population capacity.
  Explicitly named supercities may be exceptions, but their complete province
  must still satisfy `sum(location population) / sum(location capacity) <= 1.15`.
- Total global population capacity must remain below `1.2 billion`; a lower
  credible result is preferable.
- The highest non-zero `location_potential` may be at most `100×` the lowest
  non-zero `location_potential`. A narrower range is preferable.
- Exceptionally fertile breadbasket regions must have correspondingly high
  population capacity.
- Location size must affect capacity through a defensible method, but the
  relationship does not need to be linear. It must not distort the other game
  mechanics merely to force a size correlation.
- Starting development must remain within `0–80` and represent historically
  developed locations sensibly. Development's total capacity modifier must not
  exceed `+10%`.
- If necessary, a global negative population-capacity modifier may provide
  additional tuning room, but it must not be lower than `-50%` and should be
  avoided when the underlying capacity values can meet the goals directly.
- The simulator's 100-year population result must be historically plausible
  for every macro-region.

## Calibration objective

The objective is to establish sensible values and magnitudes for
`location_potential`, `development`, infrastructure buildings, and all of their
population-capacity effects. Infrastructure design is not limited to irrigation;
it includes the full set of historically appropriate improvements. The existing
building blueprint pipeline may be used to define, evaluate, and generate those
buildings and their effects.

Existing data sources, ingestion pipelines, map-to-location processing, and
building-generation workflows must be reused. New processing should only be
introduced when the existing pipelines cannot provide the required result.

## Implementation rule

When the notebooks, simulator, or deployed modifiers disagree with this document,
the discrepancy must be made explicit. Design changes should update this document
in the same change as their implementation.

## Implemented calibration contract

The canonical configuration is
[`population_capacity_simulation.toml`](../../population_capacity_simulation.toml).
The simulator and game deployment use exactly:

```text
population_capacity = (location_potential + infrastructure)
                    × (1 + development × 0.00125 + global_modifier)
```

- `location_potential` uses one global constrained decision-tree model over
  GAEZ, non-population HYDE, geometry, hydrology, and parsed starting-building
  evidence. The tree is supervised by independent physical capacity, not EU5
  population, and has `2,310` shared physical regimes with at least `7`
  locations per regime. Starting population is neither a feature nor a target;
  it is used only by the one-sided `population / capacity <= 1.15` calibration
  constraint applied to every ordinary location.
- Starting development uses HYDE cropland and pasture against GAEZ-manageable
  land. Population is not an input. Starting development is clamped to `0–80`.
- Infrastructure placement uses the parsed game-start save buildings, HYDE cropland and
  irrigation, terrain, rivers, lakes, coasts, and ownership. Land clearance is
  represented by the existing `farming_village`; wetland drainage/reclamation
  is represented by `polders` rather than a redundant new building.
- Flat capacity per level is currently: irrigation systems `9.81`, bunds
  `9.49`, terraces `2`, polders `6.23`, pound-lock canals `0`, and farming
  villages `7.65` EU5 population units.
- Development has no flat capacity term. The optional global modifier is `0%`.
- Climate, vegetation, location rank, RGO, river-size, and special Nile capacity
  modifiers are neutralized so they cannot silently alter this formula.

The three tracked provinces for every real macro-region are stored explicitly
under `[tracking.provinces]` in the canonical TOML, ordered as expected high,
representative middle, and constrained low. `suzhou_province` and
`cairo_province` are the explicit China/Lower-Nile global-ranking sentinels.

The year-zero capacity calibration passes all static gates. The separate
100-year population-growth gate remains unresolved because the unchanged growth
system contracts almost identically even under infinite capacity. See
[`population_capacity_calibration_log.md`](population_capacity_calibration_log.md)
for measured attempts and unresolved source contradictions.
