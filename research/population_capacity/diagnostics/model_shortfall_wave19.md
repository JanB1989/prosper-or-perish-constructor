# Grouped shortfall and Torch-variant audit (wave 19)

Date: 2026-08-03

This diagnostic records the current evidence/model conflict. It is not a
training target and does not authorize accepting or rendering a candidate.
All values below are from the canonical 20,929-location frame and the current
evidence registry (28 eligible packets: 4 interval records and 24 lower
bounds). The grouped scores are true leave-one-source-family or
leave-one-super-region fits.

## Holdout results

The current bounded Torch residual, trained for 150 epochs on CUDA, scored:

| Candidate | Lower-bound pass | Interval coverage | Mean log distance |
|---|---:|---:|---:|
| Mechanistic | 79.55% (35/44) | 33.33% (1/3) | 0.1241 |
| Hierarchical additive | 90.91% (40/44) | 33.33% (1/3) | 0.0776 |
| Monotone NAM | 90.91% (40/44) | 33.33% (1/3) | 0.0447 |

The following generic training-only variants were tested in fresh temporary
folds, with the same features and evidence:

| Variant | NAM lower-bound pass | NAM interval coverage | Mean log distance |
|---|---:|---:|---:|
| Residual scale 2.0 | 88.64% | 33.33% | 0.0910 |
| Residual penalty 0.005 | 95.45% | 33.33% | 0.0409 |
| Lower-bound loss weight 3 | 95.45% | 33.33% | 0.0395 |
| Scale 2.0 + lower-bound weight 3 | 95.45% | 33.33% | 0.0652 |
| Non-negative NAM residual | 90.91% | 33.33% | 0.0548 |

Longer training did not generalize: 600 epochs gave 88.64% NAM lower-bound
pass and 2,500 epochs gave 86.36%. No tested generic loss or epoch setting
passed the strict acceptance gates. No variant was written into the active
model manifest.

## Why the failures are not one missing multiplier

* **Artois**: the unscaled mechanistic aggregate is 1,325,526 people over
  5,545.6 km2 (239/km2), already inside the independently published
  1.1–1.41 million interval. The England scale factor 0.340333 reduces this
  to 451,121, below the interval. This is a conflict between a single global
  calibration anchor and a second independently sourced intensive agrarian
  interval, not an optimizer failure.
* **Greater Angkor**: the unscaled mechanistic estimate is about 603,144 over
  3,173 km2 (190/km2), close to the 700,000 lower bound in density before the
  England scale is applied. After calibration it is about 194,080, requiring a
  3.61x increase. The evidence describes a hydraulic, locally organized rice
  system; a generic dated multiple-cropping/flood-recession capability is not
  yet a closed input.
* **Iceland**: the physical baseline is about 26,058 against the independent
  40,000–80,000 natural-capacity interval. NAM variants that raise the lower
  endpoint tend to overshoot the upper endpoint (roughly 101,000–105,000 in
  held-out folds). The source model excludes fisheries, while the current
  fisheries labels are a separate diagnostic; this is unresolved food-system
  semantics, not a safe Iceland multiplier.
* **Japan Tajima/Buzen**: the one-sided floors are rice-register conversions
  from 1190s records to circa 1280, omit non-rice residents, and have no local
  saturation interval. Tajima is also a three-location crosswalk. Their
  failures are small (about 20–31%) and are consistent with conversion and
  boundary uncertainty; they should not be hand-corrected.
* **Upper Mantaro**: the six-location EU5 crosswalk covers 11,046.6 km2,
  substantially broader than the 1,900 km2 archaeological survey. Two mapped
  locations have complete, valid GAEZ coverage but all crop modes are
  structural zero; the frame labels them `arctic` at latitude about -11° and
  omits the documented highland potato/camelid production. This requires a
  high-altitude source/crosswalk review before model fitting.
* **Tongatapu**: the mechanistic aggregate already exceeds its 15,000-person
  lower bound after the explicit 0.5624 island-area weight. Some NAM
  held-outs underpredict it (~11,700), so accepting a learned residual would
  make a physically passing case fail.

## Required blockers before acceptance

1. Resolve the England-vs-Artois scale conflict with a shared physical
   calibration or additional validated technology/yield evidence; do not add
   a regional or anchor-specific factor.
2. Close generic pre-1337 multiple-cropping, flood-recession, and durable
   hydraulic-production inputs and test them across all climates; Angkor must
   not receive a named multiplier.
3. Re-audit high-altitude crop labels and historical boundaries for Upper
   Mantaro. Valid structural zeros must remain zeros; a semantic/location
   mismatch must be corrected at the source.
4. Resolve Iceland's omitted-fisheries semantics and uncertainty before using
   its interval as a joint two-sided training constraint.
5. Keep the strict grouped gates: every promoted interval must pass and all
   lower bounds must pass. Loss weighting, longer training, or wider residual
   caps are diagnostics only until those conditions hold.

