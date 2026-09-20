# Evidence used in the capacity repair

This register supplements the existing benchmark and physical-evidence packets.
It distinguishes measurements from game design guardrails. None of these sources
supplies a per-location population floor or an upper capacity limit.

## Land transformation

The supplied [land-use](https://ourworldindata.org/grapher/land-use-over-the-long-term)
and [grazing](https://ourworldindata.org/grapher/grazing-land-use-over-the-long-term)
downloads use HYDE 3.5, released by OWID on 2026-06-08. Their common grazing series
has indicator ID 1269906. It is one observation presented twice, not two validations.
Cropland and grazing are hectares; convert to km² by dividing by 100. Exclude the
built-up column from quantitative use until its display conversion is reconciled.

World cropland rises from 257.89 million hectares in 1300 to 539.90 million in
1830; grazing rises from 543.68 to 993.15 million. These are reconstruction trends
for explicit land-conversion scenarios, not automatic game growth targets. HYDE
land use incorporates historical population assumptions. LUH land-use products
also inherit HYDE inputs, so related evidence must remain in one source family.
Country boundaries and annual cultivated versus harvested area require care.

Original HYDE terms are CC BY-NC 4.0; OWID processing is CC BY 4.0. Original files,
metadata, versions and checksums are recorded by `acquire_repair_sources.py`.

## Demographic adjustment

[Madsen, Robertson and Ye (2019)](https://api.research-repository.uwa.edu.au/ws/files/68455717/Malthus_Was_Right_Explaining_a_Millennium_of_Stagnation.pdf)
analyse up to 17 European countries over 900–1870. Their preferred convergence
estimates imply adjustment half-lives around 10–30 years. Table 6 contrasts these
with earlier estimates often exceeding a century. These are estimated responses
around a moving equilibrium, not universal biological growth rates or the time
needed for an empty frontier to fill.

Report simulated perturbation half-lives against the 10–30-year reference band
and a slower 100–300-year sensitivity band. Do not force either band on Arctic,
American or African cases without regional evidence. A zero-investment simulation
does not reproduce the paper's continuing technological change. Neither this
study nor a good fit to its adjustment range validates the game engine's native
tribal demographic rules.

## Nile agriculture

[Bowman and Rogan (1999), pp. 2–4](https://www.thebritishacademy.ac.uk/documents/3871/96p001.pdf)
distinguish seasonal basin irrigation from perennial canals. Basin agriculture
normally supports one annual crop; multiple cropping requires additional water
infrastructure. Canals need maintenance, and flood height can damage as well as
support harvests. Modern triple cropping and large dams must not be granted in
1337. Their antiquity-area comparison (p. 3, note 11) totals about 27,300 km² across
Valley, Delta and Fayyum. It is contextual evidence, not a measured 1337 footprint.

The existing cadastre packet reports assessed feddans for 1298–1315. Before using
that as a physical-hectare constraint, verify the historical feddan conversion,
tax coverage and boundary. A population inferred from the same cadastre is not
independent validation of its agricultural land reconstruction.

## Audited problems requiring the next geographic round

- The current candidate classifies Cairo as generic dryland mixed farming and
  Wuxian as a hydraulic rice system whose cited calendar is from the lower Mekong.
  These are model assignments requiring review, not new historical findings.
- Historical cropland sometimes exceeds the candidate's suitable fraction.
  Diagnose crop coverage, physical coordinates and units before choosing a
  suitability ceiling or extrapolating yields across the additional hectares.
- Upstream joint quantiles select coherent total-capacity scenarios. Their
  component values can cross. Sorting each component independently loses that
  coherence and must not be described as a joint uncertainty distribution.
- Current cultivation is now limited to inherited LUH2 cropland plus a shared
  baseline-access fraction of unused open suitable land. The remainder is future
  opportunity. Historical suitability conflicts and inherited hydraulics still
  require regional validation.

## Native growth rule correction

The user confirmed during implementation that `local_<type>_pop_growth` adds to
`local_population_growth`; their sum can be negative or positive. Earlier rounds
05–08 used an incorrect positive-birth multiplier interpretation and cannot
validate population-type outcomes. The candidate now adds
`local_tribesmen_pop_growth = -0.0075` beside the generic food bonus `+0.0075`.
Both scale with stored years, so food contributes zero tribal growth at every
stock level. Rank, prosperity, starvation and other sources remain separate.
This is a user-confirmed mechanics contract, not an engine measurement. The
starvation treatment of food-neutral populations remains an open question.

## Additional regional research leads

- Casarabe landscape engineering: [Lombardo et al., Nature (2025)](https://www.nature.com/articles/s41586-024-08473-y)
  reports drainage canals and farm ponds supporting intensive maize cultivation
  in seasonally flooded savannah. Treat the transformed landscape separately
  from unmodified tropical land; a universal tropical penalty would erase an
  established agricultural centre. The [2025 Casarabe population simulation](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0325104)
  is contextual model evidence, not an independent capacity label.
- [Arneborg et al., Radiocarbon 41(2), 1999](https://doi.org/10.1017/S0033822200019512)
  measures 27 Norse Greenland skeletons across approximately AD 1000–1450.
  The authors infer increasing marine dietary dependence, approximately 20% to
  80%. These are dietary estimates with isotope/reservoir uncertainty, not a
  carrying-capacity density. Marine hunting must remain distinct from both
  agricultural support and present-day commercial fish catches.
- [Blaydes, Politics & Society 47(3), 2019](https://blaydes.people.stanford.edu/sites/g/files/sbiybj24621/files/media/file/land1.pdf)
  uses Mamluk cadastral land records. Its land-area observations may help audit
  inherited Nile agriculture independently of historical population estimates.
  Do not convert historical feddans with the modern unit without resolving the
  period-specific measure and whether a figure describes surveyed, assessed or
  cultivated land. The existing modern-feddan conversion remains unaccepted.

These leads were located through primary publications on September 6, 2026.
They have not yet supplied an accepted numerical geographic parameter.

## Land-use source interpretation repair

[Hurtt et al. (2020), sections 2.1 and 2.7](https://doi.org/10.5194/gmd-13-5425-2020)
define LUH2 states as fractions of whole grid cells with ice/water excluded from
the twelve land states. The forest split uses a static potential-biomass
threshold of 2 kg C/m². Applying those fractions to land-only samples without
normalization deducts water twice. Treating primf/secdf as measured tree canopy
also misstates what the source establishes. Historical v2h uses HYDE 3.2 2016
beta; related HYDE 3.5/OWID observations remain one reconstruction family.

[Ma et al. (2020)](https://doi.org/10.5194/gmd-13-3203-2020) show that translating
land use into land cover requires assumptions. The repair overlays PNV forest
classes on the remaining natural-land fraction after dated cropland, pasture,
rangeland and urban uses. This is a model choice: it assumes uniform within-cell
land-use shares and does not reconstruct tree age, wood harvest or regrowth.
Unknown PNV is retained separately. The previous algorithm's redistribution of
LUH2 biomass-defined forest outside PNV forest classes has been removed.

[SAGE's PNV provider](https://sage.nelson.wisc.edu/data-and-models/datasets/global-potential-vegetation-dataset/)
cautions that its product is intended for broad-scale work. It describes
potential vegetation in the absence of human land use, not a dated historical
forest inventory. Forest/open model alternatives and local uncertainty must
remain part of sensitivity analysis.

## Modern crop masks and historical extrapolation

The current GAEZ/TraCE fallback copies sample output density and suitability
from modern GAEZ before applying climate anomalies. Source availability flags
do not resolve modern land exclusions. The cached exact-PyAEZ demonstration
emits no EU5 rows; it cannot certify the current crop map as an exact 1337 run.

[FAO's GAEZ v5 input documentation](https://github.com/un-fao/gaezv5/wiki/02.-GAEZ-input-datasets)
describes circa-2020 land cover and modern protection/wetland/tree-cover
exclusions. The official LR-LCC built-up raster and RES02-YLD low-input wheat
rasters are cached with provider metadata. `audit_modern_land_mask.py` compares
them at nine canonical location footprints: Paris has 69.68% sample-weighted
modern built-up cover and Wuxian 40.44%. Their climatic wheat yields remain
positive while source agro-edaphic suitability covers much smaller fractions.
This is a diagnostic association, not proof that urban masking explains every
zero. Grid resolution, soil and slope effects still need to be separated.

Climatic potential omits edaphic constraints and must not directly substitute
for attainable subsistence yield. No automatic density uplift has been applied.
All numerical diagnostic inputs, units, hashes and missing coverage are in
`artifacts/data/population_capacity/repair_sources/modern_land_mask_diagnostic.json`.

## Historical land-unit clarification

[Blaydes (2019), note 96](https://blaydes.people.stanford.edu/sites/g/files/sbiybj24621/files/media/file/land1.pdf)
uses 6,368 m² per pre-nineteenth-century feddan, rather than the modern 4,200 m².
Its 1376/1480 land-holding categories can overlap: the table's upper bounds must
not be added as if they were disjoint cultivated land. This resolves one unit
lead but does not validate the coverage or cultivated-versus-assessed meaning
of the earlier 1298–1315 cadastre packet. No capacity coefficient has been fitted
to either land total or the population inferred from it.

## Taihu cultivation intensity and water management

[Liu (1991), Table 1](https://idv.sinica.edu.tw/ectjliu/%E5%8A%89%E7%BF%A0%E6%BA%B6%E5%AD%B8%E8%A1%93%E8%91%97%E4%BD%9C/W6-%E7%B6%93%E6%BF%9F%E5%8F%B22pdf/1991Rice%20Culture%20in%20South%20China.pdf)
reports approximate paddy yields of 450 catties/mou for Song Taihu, 667 for
Ming Taihu and 550 for Qing Taihu. The table explicitly uses **0.6 kg/catty and
15 mou/hectare**, giving 4,050, 6,003 and 4,950 kg of paddy per hectare per
harvest. Substituting a modern 0.5 kg catty would misread this source. These
managed field yields reflect cultivation, fertilization, water control and
seed selection. They are neither net edible food nor annual yields across an
entire location. The source distinguishes rice-wheat rotation from rice-rice
systems and discusses uncertainty in the apparent Ming-to-Qing rice decline.

`historical_rice_yields.json` records the source's metrology and comparative
Song observations for Hubei, Hunan, Anhui and Fujian. The conversion helper
uses the existing pipeline's rice processing, storage, seed, calorie and protein
constants. Moisture is unspecified by the source: dry-matter fractions 0.80,
0.86 and 0.90 are explicit sensitivity assumptions. No additional annual
calendar multiplier is applied. Field adoption shares remain unmeasured.

[Zhou, Wu and Chen (2026)](https://doi.org/10.13284/j.cnki.rddl.20250418)
reconstruct Tang-Song water management from historical maps, gazetteers,
water-management records, archaeology and hydrology. Taihu's water advantages
depended on interconnected embankments, drainage channels, gates and maintenance.
Reclamation could also obstruct drainage and increase flooding elsewhere.
This supports a shared land-and-water improvement account, rather than separate
full bonuses for paddies, canals and embankments. Their cited Southern Song
Pingjiang cultivated total of approximately 150,000 qing remains excluded from
numerical capacity inputs until its unit, fiscal/cultivated meaning, historical
territory and shoreline are reconciled. Availability of the system does not
prove every mapped trace was functioning in 1337.

## Angkor and Java/Bali: transformed landscapes

[Klassen et al. (2021/2022)](https://doi.org/10.1007/s10816-021-09535-5)
describe more than 1,000 km² of ricefields in the Angkor Metropolitan Area,
alongside communal water infrastructure and maintenance. Zhou Daguan's account
of three or four harvests may describe staggered harvests over different fields;
it cannot justify three or four annual crops on every hectare. The surveyed
metropolitan landscape is not automatically identical to game location `angkor`.
Its peak and subsequent changes require dated maintenance/occupancy evidence.
The supplement is cached, but the exact field-to-game geometry remains unresolved.

[Hawken (2014)](https://cdn.angkordatabase.asia/libs/docs/publications/designs-of-kings-and-farmers-landscape-systems-of-the-greater-angkor-urban-complex/Designs_of_Kings_and_Farmers_Landscape_S.pdf)
provides the underlying field-morphology research: approximately 1,000 km² of
mapped ricefields and 22,000 km of bunds. Dated examples include the roughly
300-hectare field grid at Pre Rup. This is related archaeological evidence, not
a second independent confirmation of Klassen's aggregate area. It distinguishes
medieval field systems from later changes, including Khmer Rouge fields.

The [Java/Bali inscription study](https://pure.mpg.de/rest/items/item_922657_3/component/file_3636125/content)
documents historical wet-rice cultivation and water management. Its evidence
supports dated local starting infrastructure. It supplies no blanket Indonesian
yield coefficient or island-wide adoption area. The cached PDF is the entire
edited book; site-level spatial and chronological extraction is still required.

## Chinese land transformation and contrasting regions

[Li et al. (2018)](https://doi.org/10.1007/s11442-018-1576-8)
reconstruct 535.4 million modern mu of cropland in the study's Yuan territory
in 1290. Household-to-land relationships contribute to the reconstruction;
the data are not independent demographic validation. Historical provincial
boundaries and Yuan versus modern mu require explicit crosswalks.
[Li et al. (2020)](https://doi.org/10.11821/dlyj020181315)
estimate corrected Ming cropland of 495.5 million modern mu in 1393 and
754.3 million in 1583. Raw taxable land includes non-cropland. Later expansion
was spatially uneven, so these are dated progression comparisons, not an
instruction to grant future cultivation across China in 1337.

[Jia et al. (2024)](https://doi.org/10.5194/essd-16-4971-2024) and its
[version-2 dataset](https://doi.org/10.6084/m9.figshare.25450468.v2)
provide a useful contrasting Northeast China case. The 1300 workbook yields
4,350.15 km² of reconstructed cropland across its three study territories.
Medieval estimates use households, garrisons and land-per-worker assumptions;
they are not population-independent capacity measurements. The authors warn
against reading provincial fractions as uniformly distributed fields. Temporary
land use and fallow are not fully represented, and subsequent contractions
include historical disruptions absent from peaceful game simulations.

`audit_northeast_cropland.py` verifies downloaded files against the provider's
checksums, joins workbook identifiers to the source polygons, transforms
CGCS2000 coordinates to WGS84, and intersects canonical physical sample points.
Mapped game land covers 96.6–99.1% of the source polygon areas; source polygons
include water. At that footprint the model's LUH2 inherited cropland totals
5,660.90 km², while its shared 2% open-access assumption adds 14,268.30 km².
This is a warning about the size of a modelling assumption. It is **not** a
reason to cap capacity at reconstructed cultivation or to fit local populations.
Only the 1300 land observations are compared to LUH2 1300; the later source
slices remain separate progression context.


## Demographic adjustment: interval coefficients are not annual population growth

The Madsen–Robertson–Ye paper reports substantially faster convergence than much
of the literature it reviews. Its preferred summary is roughly 10–30-year
half-lives, while contrasting studies often imply centuries. This is contested
wage/income/population-adjustment evidence at historical country scale, not a
universal famine rule or a measured subsistence-food coefficient.

The Table 1 wage example is particularly important for units: beta=-0.029 at a
30-year observation interval gives a half-life of about 10.2 years through
`-ln(2)/(ln(1+beta*T)/T)`. Treating beta as continuous exponential decay would
produce a different result. It must never be installed as a 2.9% population
growth/decline rate. The versioned `demographic_adjustment_benchmarks.json`
records this example, source hash, contrasting ranges and comparison exclusions.
A direct audit of the contrasting primary papers and population-specific
estimates remains necessary before numerical demographic acceptance.

Source: [Madsen, Robertson and Ye (2019)](https://doi.org/10.1016/j.euroecorev.2019.05.004),
sections 6.1/6.5, Table 1 and conclusion. The country's wage-adjustment result
cannot independently validate an Angkor village or food-neutral tribal control.
