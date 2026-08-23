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
| `development` | Converts development points into a population-capacity modifier. | Current development and its capacity effect per point. | How thoroughly the location's land, labor, and food systems are organized and optimized. | Multiplies total capacity.<br>Development grows through investment, prosperity, parliament actions, and buildings. | Bounded from `0` to `100`.<br>Applies to all absolute capacity. | Must be derived independently of population and be high in historically well-developed locations without replacing infrastructure as the explanation for extreme capacity. |
| `prosperity` | `previous prosperity + monthly gains - proportional decay` | Food stored, base prosperity changes, and other prosperity modifiers. | The location's current economic security and wellbeing. | Increases development over time and modifies population growth, food consumption, and unrest. | Bounded from `0` to `100`.<br>Effects scale linearly with prosperity. | Must reward sustained food security without creating an uncontrolled food–prosperity–development feedback loop. |
| `abundant_free_land` | Active when `population / capacity < 10%` and population is below `10,000`.<br>Strength: `1 - population / capacity`. | Population and population capacity. | The location has far more usable land and food resources than its population can exploit. | Strongly attracts migration, reduces peasant food consumption, and adds local food.<br>Current full-strength values: `+2` attraction, `-50%` consumption, `+8` monthly food. | Exclusive capacity-pressure state.<br>Strength ranges from `0` to `1`. | Reserved for genuinely small, sparsely populated frontier locations. |
| `available_free_land` | Active from `10%` through `100%` capacity.<br>Strength: `1 - population / capacity`. | Population and population capacity. | Productive land remains available, but becomes scarcer as population approaches capacity. | Attracts migration, reduces peasant food consumption, and adds local food.<br>Current full-strength values: `+1` attraction, `-32%` consumption, `+3` monthly food. | Exclusive capacity-pressure state.<br>Reaches zero strength at capacity. | Benefits must decline smoothly as capacity fills. |
| `overpopulation` | Active above capacity.<br>Strength: `population / capacity - 1`. | Population and population capacity. | The population exceeds what local resources can normally support. | Raises peasant food consumption, reduces migration attraction, and encourages outward migration.<br>Current full-strength values: `+100%` consumption and `-0.25` attraction. | Exclusive capacity-pressure state.<br>Strength is non-negative and currently uncapped. | No location may start above `0.15` strength.<br>Should create escalating pressure rather than immediate collapse. |
| `population_food_consumption` | `sum(population of each type × base food rate × max(0, 1 + consumption modifiers))` | Population by type, type-specific base rates, prosperity, capacity pressure, weather, and other modifiers. | The food required by the province's population each month. | Removes food from provincial storage and determines food surplus, food security, and food-supported population growth. | Effective consumption cannot be negative. | Must produce historically plausible demand while preserving meaningful differences between pop types. |
| `peasant_food_consumption` | `peasant population × 1.0 × max(0, 1 + peasant consumption modifiers)` | All peasants, including employed and unemployed peasants; capacity pressure, prosperity, and other peasant modifiers. | The total food consumed by the peasant population. | Usually the largest part of provincial food demand.<br>Free land reduces it; overpopulation and prosperity increase it. | Base rate is currently `1.0` food per peasant game unit per month.<br>Cannot fall below zero. | Must connect population capacity directly to food pressure without making peasants disappear from the food economy. |
| `subsistence_agriculture` | `unemployed peasants × subsistence rate` | Unemployed peasants and `SUBSISTENCE_AGRICULTURE`, currently `1.0`. | Food produced directly by peasants who are not employed in formal production. | Adds food to provincial storage and offsets the consumption of unemployed peasants. | Rate must be non-negative.<br>Only unemployed peasants produce it. | Should let unemployed peasants support themselves at baseline, but not sustain unlimited population independently of capacity. |
| `food_stored` | `max(0, previous food + food inflow - population consumption) × (1 - decay rate)` | Subsistence output, other food inflows, population consumption, and food decay. | The province's accumulated food reserve. | Buffers temporary deficits and determines food-supported population growth and prosperity. | Province-level stock; minimum `0`.<br>The current simulator does not yet enforce an upper storage capacity. | Must make sustained surpluses valuable and allow provinces to survive short shortages without making long-term deficits harmless. |
| `food_decay` | `food before decay × combined decay rate` | Global decay, climate, and storage-infrastructure modifiers. | Food lost through spoilage, pests, leakage, and inadequate storage. | Removes part of stored food every month and makes storage infrastructure valuable. | Loss cannot be negative or exceed the available stock.<br>The simulator currently uses a fixed `1%` monthly rate. | Climate and granaries should eventually modify it without making long-term storage either free or pointless. |
| `population_growth` | `new population = current population × (1 + total yearly growth)^(1/12)` | Stored-food growth, prosperity, location rank, capacity pressure, and other population-growth modifiers. | Natural population change from births and deaths.<br>Migration is separate. | Changes every pop type each month, which changes food consumption, capacity pressure, and future growth. | Population cannot become negative.<br>The same proportional growth normally applies to every pop type in the location. | Food security must remain the principal source of sustained growth.<br>Must reproduce plausible historical global and regional trajectories without runaway growth. |

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
