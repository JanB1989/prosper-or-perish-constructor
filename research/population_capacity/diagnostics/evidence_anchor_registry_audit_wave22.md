# Evidence and anchor registry audit — wave 22

Reviewed 2026-08-04. This is an append-only diagnostic; the central registry was not modified.

## Bottom line

Training can start from the evidence/mapping perspective. The required pre-fit contract is closed: 145 packets are dispositioned, all 28 training-eligible rows have resolved crosswalks, and there are no packet-schema or required-label blockers. The 88 unresolved crosswalk rows belong to validation-only or rejected packets and must not be promoted silently.

The work is not yet scientifically accepted or deployable. The current selected candidate is the mechanistic model, but full correlated climate/yield/parameter scenario propagation through the joint land, calorie, protein, water, livestock, fisheries, and wild-food optimization is still incomplete. Therefore p10/p50/p90 headcounts are not ready to freeze, even though grouped aggregate holdout artifacts have been produced.

## Registry and fit status

| Check | Current result | Meaning |
|---|---:|---|
| Evidence packets | 145 (142 active) | Three packets are superseded, not missing |
| Training-eligible rows | 28 | 3 interval anchors, 1 scale anchor, 24 one-sided lower bounds |
| Required crosswalk rows unresolved | 0 | Mapping no longer blocks pre-fit training |
| Super-regions represented | 5 | Asia, Europe, Africa, America/Oceania, Oceania |
| Declared source families | 18 | Holdout artifact has 18 groups, 17 excluding scale-anchor-only England |
| Mechanistic interval coverage | 1.0 (8 rows) | Aggregate interval inequality gate only |
| Mechanistic lower-bound pass rate | 1.0 (48 rows) | One-sided guard test, not a numeric fit metric |
| Scientific acceptance | false | Uncertainty/scenario gates remain incomplete |
| Deployment status | provisional | No final frozen headcount table should be rendered |

The mechanistic holdout’s zero log-distance summary is not evidence that every location is historically accurate. It means every tested interval inequality and lower-bound inequality passed; lower bounds have no upper error penalty, and there are no location-level historical population targets.

## Strongest two-sided evidence

- **Artois (1290–1300):** 1.095–1.415 million across 5,545.58 km² at 96% mapping coverage; current mechanistic prediction 1,097,627. The rich-loam/agrarian-pressure evidence is the strongest local fertile-region interval in the registry.
- **England (1290 food-security interval):** 4.25–6.2 million across 130,279 km² with exact coverage; current mechanistic prediction 5,729,912. Keep the England demographic record as a scale anchor only. It overlaps geography and Campbell/manorial inputs with this interval, so the pair is one evidence bundle for holdouts, not two independent anchors.
- **Iceland (1290–1330):** 40,000–80,000 across the exact island boundary; current mechanistic prediction 76,565. It is useful hostile-island evidence, but the companion Ice-CC floor shares the Haraldsson model family and cannot count as an independent replication.

No lower-bound record should be promoted to a two-sided capacity interval. In particular, lower bounds from Japan, Gyeongsang, Angkor, Sicily, Faroe, Tenerife, Tonga, Hohokam, France, and the archaeological sites do not establish an upper capacity.

## Lower bounds worth retaining

The most informative one-sided checks are Greater Angkor (700,000 hydraulic/rice floor), Gyeongsang (355,069 register floor), Tenerife (15,000 local-food island floor), Sicily (340,000 fiscal floor), Faroe (2,224 pastoral floor), Hohokam Lower Salt (53,000 irrigation floor), and Tongatapu (15,000 intensive local-food floor). Japan’s eleven Farris records are one source-family group, not eleven independent anchors. Great Zimbabwe, Mapungubwe, Mesa Verde, and Upper Mantaro remain useful conservative containment diagnostics but should not be treated as exact surrounding-land aggregates.

## Mapping caveats requiring conservative semantics

The machine crosswalk is complete, but several historical sources are much smaller than the containing EU5 selector:

- Upper Mantaro: approximately 1,900 km² source survey versus an 11,046.64 km² selector (17.2%).
- Mesa Verde: approximately 1,800 km² versus 9,158.81 km² (19.7%).
- Mapungubwe: approximately 1,329.7 km² versus 8,154.75 km² (16.3%).
- Great Zimbabwe: approximately 0.8 km² archaeological urban property versus 5,509.97 km² (a site, not a rural catchment).
- Hohokam Lower Salt: canal corridor narrower than the 19,001.88 km² selector and not yet quantified as a polygon.

Keep these as validation/containment lower bounds until exact source polygons are available. A high EU5 coverage fraction does not turn a containing location into an exact historical boundary.

## Independence audit

The registry’s 18 declared family names meet the nominal minimum, but documented dependence reduces the effective evidence diversity. Collapse the eleven Farris Japan records to one group, hold the two England records together because of shared geography/Campbell inputs, and hold the Iceland interval and Ice-CC floor together because they share the Haraldsson model family. The current source-family holdout grouping must preserve these bundles; a nominal family count must not be presented as 18 independent replications. A conservative effective independent-bundle floor is 16 under the documented overlaps.

## What remains before final acceptance

1. Generate correlated 101-year climate/yield scenarios and physical-parameter draws, and re-optimize each location through all land, calorie, protein, water, livestock, fisheries, wild-food, and uncertainty constraints.
2. Produce valid p10/p50/p90 joint capacity estimates and rerun physical-invariant, interval, lower-bound, source-family, geographic-family, and super-region holdouts.
3. Evaluate the PyAEZ challenger at matching geography, or explicitly retain GAEZ as the frozen production baseline with the required reason and uncertainty treatment.
4. Preserve conservative semantics for broad containment/site records and repair the missing `source_family_independence` metadata on the England scale anchor.
5. Only after those gates pass, freeze source hashes, absolute headcounts, global normalization, and the static modifier table.

The full machine-readable details and artifact hashes are in [evidence_anchor_registry_audit_wave22.json](evidence_anchor_registry_audit_wave22.json).
