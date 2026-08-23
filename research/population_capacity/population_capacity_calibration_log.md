# Population-Capacity Calibration Log

This log records meaningful calibration attempts against the fixed starting
population snapshot. Population is used only to evaluate the `115%` boundary;
it is never an input to location potential, development, or infrastructure.

## Attempt 1 — inherited population-backed baseline (rejected)

- Result: roughly `4.79b` global capacity.
- Rejected because HYDE population was used as a hidden natural-capacity floor,
  development added flat capacity, and irrigation added `110,000` people per
  level. These violate the design contract and obscured source errors.

## Attempt 2 — physical potential plus irrigation only (rejected)

- Values: `20%` weighted physical potential, `20 people/km²` density cap,
  sub-linear area exponent `0.72`, `40,000` people per irrigation level.
- Result: about `743m` global capacity, but only `30%` of starting population
  lived in locations within capacity. Extreme deficits remained in locations
  whose GAEZ/HYDE evidence was nearly zero.
- Rejected because irrigation alone cannot explain cultivated and reclaimed
  high-capacity locations.

## Attempt 3 — combined infrastructure at full initial magnitude (rejected)

- Added source-generated bunds, terraces, polders, land-clearance farming
  villages, and parsed starting buildings.
- Result: `1.285b` global capacity; positive potential spread exactly `100×`;
  repeated `0/100` run about `3.2s` after caching.
- Rejected because global capacity exceeded `1.2b`, infrastructure dominated too
  broadly, and China/Lower-Nile ranking and ordinary-location fill still failed.

## Attempt 4 — compact physical TPE + exact infrastructure LP (rejected)

- `300` trials without the parsed save-building inventory left `1,611`
  locations above the boundary; at the `1.2b` global ceiling the worst fill was
  `10.18×`.
- Reusing the parsed game-start building snapshot and running `400` further
  trials improved physical coverage, but still left `1,874` locations above the
  boundary and a worst fill of `8.24×`.
- A monotone calibration curve over the independently trained physical model
  required at least `6.31b` global capacity. An unsupervised `1,024`-regime
  physical clustering still required `1.287b` after integer deployment.
- These attempts prove that the compact and globally monotone formula families
  cannot satisfy the all-location boundary and the `1.2b` ceiling together.

## Current static solution — constrained physical-regime tree

- Inputs: configured GAEZ, non-population HYDE, geometry, hydrology, and parsed
  game-start building evidence. Starting population is never an input feature;
  it appears only in the one-sided `population / capacity <= 1.15` loss and LP
  constraints.
- Model: one global decision tree trained to reproduce independent physical
  capacity, with a minimum of `7` training locations per leaf, followed by an
  exact linear program for `2,310` shared regime values and
  six global building effects.
- Complexity search: with seven locations per leaf, `2,270` maximum leaves was
  rejected (`1,200,011,392` capacity). `2,271` barely passed the ceiling;
  `2,310` was selected to preserve the configured ten-million-person safety
  margin after integer deployment.
- Static result: all `20,929` locations checked, `0` overfilled locations,
  worst ordinary fill `1.149987×`, global capacity `1,189,964,242`, positive
  potential spread `100×`, maximum development `69.88`, maximum development
  contribution `8.735%`, Suzhou ranked first, and Cairo ranked eleventh among
  global province capacities.
- Deployed capacity per level, rounded to two decimals while preserving the
  all-map boundary: irrigation `9.81`, bund `9.49`, terraces `2`, polders
  `6.23`, pound-lock canals `0`, and farming villages `7.65` EU5 population
  units.

The tree never sees EU5 population as a feature or target. It defines shared
physical regimes from the independent evidence; starting population enters only
as a one-sided inequality in the exact solve. Consequently, changing the
starting population cannot alter the regime partition, development, building
placement, or building definitions.

The static capacity model passes every configured year-zero hard gate. The
unchanged population-growth system still produces `0.741×` global population
after 100 years, outside `0.90–1.10×`. An infinite-capacity control produces
approximately the same `0.739×`, proving this failure is not tunable through
population capacity without changing the explicitly frozen growth mechanics.
