# Population repair: native engine evidence

These checks concern native behavior that a parser cannot independently prove.
They do not authorize live deployment. Keep outcomes and screenshots/save values
with the exact game/mod revision when engine observations become available.

| Behavior | Current evidence | Status |
|---|---|---|
| Generic and population-type growth add, with either sign permitted | User confirmation in this thread | Confirmed rule; simulator parses actual type rates |
| Abundant Free Land requires both population <10,000 and fill <10%; otherwise below-capacity locations receive Available Free Land | User confirmation 2026-09-07 | Confirmed; scalar and NumPy paths and boundary regression agree |
| Existing direct building food/development generally depends on staffing; constructed infrastructure grants flat capacity | User clarification 2026-09-07 | Authorized model assumption; infrastructure staffing/building design deferred |
| Tribal food-growth cancellation, rank offsets and reduced starvation | Matching scripted modifiers and parsed simulator controls; user authorizes assuming native behavior | Authorized assumption for model pass; not an observed engine result; no simulator-only exemptions |
| Monthly growth-unit conversion, food sharing/storage and decay order | Parsed coefficients and regression controls | Focused engine comparison needed before acceptance |

## Minimal building probe

Use one location and a single building with an unconditional numeric direct food
or development effect. Record total levels, open levels, employed/required workers
and the visible modifier at 100% staffing, 50% staffing and closed. Hold development,
prosperity, advances, food stocks and all other buildings constant. Repeat for a
numeric `raw_modifier` if one is available. Conditional effects must be identified
separately. A tooltip recording both base and final effects distinguishes level
scaling from employment scaling.

## Minimal tribal probe

Use matched pure-peasant, pure-tribal and mixed locations in separate provinces,
with identical rank and capacity. Compare 0, 12 and 24 months of provincial food.
Record generic and type-specific growth contributions and the next-month population.
A pure tribal province has no provincial food demand or subsistence surplus; zero
stocks alone must not be mistaken for unmet demand. Then induce a real deficit in
a mixed province and compare the applied starvation rate for both types. Repeat
rural/town/city ranks. The current candidate cancels only the scripted food bonus,
adds the rank offsets and halves the scripted starvation penalty. It is not a
universal historical claim about tribal famine resilience.

## Minimal pressure/development probe

At fixed non-food modifiers test populations 9,999 / 10,000 / 10,001 and fills
just below, exactly at and above 10%, then 100%. The confirmed fallback means the
constant-minus-free-land development candidate has approximately P/K strength
below capacity and full strength at/above capacity. It must never be amplified
again by overpopulation. Compare flat and relative development source totals
before applying the native relative factor. Trial offsets are recalculated from
0%, 25% and 50% of D50 decay, with D50/75/100 decay remaining negative when
other positive contributions are absent.
