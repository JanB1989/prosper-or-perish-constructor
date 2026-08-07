# Physical-gap re-audit: Angkor, Iceland fisheries, and Upper Mantaro

Reviewed 2026-08-03. This is an append-only evidence/diagnostic report. It does not modify the accepted table, normalization, or model-selection artifact.

## Greater Angkor

The crop/water label contract is closed (736 cell-by-crop rows in the existing follow-up), but the current feature set does not represent the dated food system that the historical literature describes.

The Lower Mekong rice synthesis documents two distinct systems: deepwater/floating rice in seasonal flood depths and flood-recession rice in areas that remain flooded during the wet season. Recession production traps water behind embankments, ponds and dams and uses canals or pumps for a dry-season crop. The same synthesis records that Angkor (800–1350) depended partly on deepwater/floating and flood-recession rice around Tonle Sap, while barays, canals and bunded paddies enabled managed wet rice. A 1296–1297 visitor reports three to four rice crops per year, but the account does not say what share of the landscape had that calendar. The source also reports an out-of-period Angkor Borei analogue: 80,000 farm workers using flood-recession cultivation were estimated to support 40,000 additional people within 10 km.

These are generic physical features and a validation analogue, not an Angkor multiplier. The implementation must add a flood-recession/deepwater calendar pathway with land, water and labor conservation and a shared hydraulic-efficiency uncertainty prior. Observed Angkor field area remains validation-only.

Current Angkor row (from the frozen diagnostic source): 205,976 p50 people unscaled, 187,249 rain-fed crop component, 18,575 irrigation increment, 132,423 wet-rice component, and 61 freshwater component. The packet is [asia_greater_angkor_hydraulic_calendar_wave21.json](../physical_evidence/asia_greater_angkor_hydraulic_calendar_wave21.json).

Sources: [Lower Mekong rice-farming synthesis](https://link.springer.com/chapter/10.1007/978-981-15-0998-8_1), [Angkor population model](https://doi.org/10.1126/sciadv.abf8441), [Angkor archaeobotany](https://doi.org/10.1177/0959683617752841), [Angkor landscape systems](https://doi.org/10.1007/s10816-021-09535-5).

## Iceland fisheries

The current implementation does not omit marine food: 18 of 21 Iceland EU5 locations have `observed_positive` marine labels. Summed p50 components are 13,931 terrestrial people, 11,129 marine people and 994 freshwater people, for 26,059 total mechanistic people. The fish-inclusive model therefore remains below Haraldsson–Ólafsdóttir's 40,000–80,000 environmental interval, but that interval was built from biological production available to livestock and is not a fish-inclusive catch estimate. The old diagnosis “the source model excludes fisheries” should be read as a scope mismatch, not as evidence that marine rows are zero.

Hambrecht et al.'s millennium synthesis supplies date-compatible access evidence: 13th–15th-century marine-fish NISP is 16,296 at Gjögur, 101,549 at Akurvík and 9,748 at Gásir. The coastal sites show cod-processing/export signatures, and preserved gadids were transferred from coastal producers to inland consumers. This proves a local fishing and preservation channel, but NISP is not annual catch. Walser et al.'s isotope study independently shows terrestrial and marine dietary contrasts within Iceland; its monastery sample is later than the target window and is validation-only.

The correct next model work is to expose terrestrial-only and fish-inclusive comparisons, represent coast-to-interior preserved-fish access, and propagate fisheries climate/access uncertainty jointly. Do not convert archaeological counts into annual yields or add an Iceland correction. The packet is [europe_iceland_fisheries_local_food_wave21.json](../physical_evidence/europe_iceland_fisheries_local_food_wave21.json).

Sources: [Hambrecht et al. 2019](https://doi.org/10.1017/qua.2019.35), [Smiarowski et al. 2005](https://doi.org/10.1179/env.2005.10.2.127), [Walser et al. 2020](https://doi.org/10.1002/ajpa.23973), [Haraldsson and Ólafsdóttir 2006](https://doi.org/10.1016/j.scitotenv.2006.08.013).

## Upper Mantaro

The source evidence directly confirms the food and technology system: Wanka II territories span roughly 3,500 m to above 4,200 m, with potato, quinoa, some maize and upland puna herding. The Wanka II irrigation network is just over 24 km long, waters at least 100–200 ha above 3,800 m, and includes three rudimentary aqueducts. Drained fields, lynchets/terraces and ridged fields address frost and excess-water risk. The Tunanmarca polity's approximately 150 km² core is estimated at about 20,000 people; the existing 61,000 observation is a broader settlement-derived one-sided floor.

The current EU5 containment selector covers 11,046.64 km², while the published JASP umbrella survey is approximately 1,900 km² (17.2% of the selector). Therefore the six-location selector is not an exact historical boundary. `tunanmarca` is a direct named-settlement match; `hatun_xauxa` is broad containment; `pumaruri`, `tarmatambo`, `ingapirca` and `llampqui` have no direct Wanka II feature overlap established by the cited boundary. Current potato p50 yields are 68.63, 130.29, 1.05, 1.92, 0 and 0 kg DM/ha respectively. The last two are valid finite physical structural zeros, not missing values; they must not be replaced by regional medians. Their historical meaning remains unresolved because the selector is too broad.

The correct resolution is to digitize or obtain the UMARP/JASP historical polygon, intersect it with calibrated EU5 geometry, retain unobserved high-puna area explicitly, and then run an exact high-altitude crop/irrigation audit. Until that is done, this record remains a lower-bound/validation case, not a precise two-sided aggregate target. The packet is [america_upper_mantaro_crop_crosswalk_wave21.json](../physical_evidence/america_upper_mantaro_crop_crosswalk_wave21.json).

Sources: [Earle, Tunanmarca chiefdom](https://wiki.santafe.edu/images/7/70/Earle_TunanMarcaChiefdom.pdf), [JASP/UMARP Wanka survey](https://sites.lsa.umich.edu/archaeology-books/2013/01/07/prehispanic-settlement-patterns-in-the-upper-mantaro-and-tarma-drainages-junin-peru-volume-2-the-wanka-region/), [Hastorf and DeNiro](https://doi.org/10.1038/315489a0), [Earle, How Chiefs Come to Power](https://doi.org/10.1515/9781503616349).

## Acceptance impact

These packets close evidence semantics and quantify the remaining scope/mapping issues. They do not claim that grouped anchor gates now pass. No normalization, acceptance, or deployment change is authorized by this report.
