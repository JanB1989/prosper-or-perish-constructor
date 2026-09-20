# Round 56 — hierarchical historical management and physical accounting

This bounded research round implements a historical-management hierarchy, corrects
field recovery and water attribution, and evaluates two frozen variants through
100 and 200 years. **Neither broad assignment variant is accepted balance.**
The round55 dataset remains the unchanged comparison baseline. No food/growth
coefficient, higher-pop consumption rate, building balance or deployment changed.

## What changed, from the shared model downwards

1. **Management can be independent of potential.** The canonical model now accepts
   dated world defaults, regional/provincial practice assessments and named local
   systems, in that order. Local evidence wins. Same-tier overlaps are errors.
   Population, density and potential are not allowed management selectors.
   Unknown potential labels cannot block an independently assessed historical system.
   Missing land evidence is separate from zero reconstructed cultivation; neither
   establishes a foraging-only economy.
2. **Current reconstructed fields use the same geometry contract as named fields.**
   A crop-mixture suitability denominator is not a surveyed maximum field union.
   The candidate recovers reconstructed fields on known land, displaces grazing/wild
   support, and consumes existing opportunities before recovering additional known
   land. Unclassified cover is unavailable. Unused recovered land does not become
   free future opportunity. Named extent assignments remain authoritative.
3. **Irrigation is incremental.** `capacity__water_control` remains the whole
   served-field system for compatibility. New `capacity__water_managed_baseline`
   and `capacity__water_increment` columns partition it exactly. Adding all three
   is prohibited. The handoff's irrigation share uses the increment, not all
   infrastructure or all irrigated-field output. The canonical preparation summary
   no longer aliases all infrastructure to irrigation. A missing incremental ledger
   is reported as unavailable, not zero. Its legacy additive breakdown is labelled
   explicitly; a separate full-development increment includes effects on both
   natural support and infrastructure and must not be added to that breakdown again.
4. **Dated local practice was added selectively.** Existing Java rice-presence
   crosswalks and new Kaveri, Kyaukse and Red River evidence inform named practice
   and maintained water systems. Existing Taihu, Nile, Bali/Trowulan and Cusco
   assessments retain priority. Broad Chinese and Gangetic analogues exclude
   unrelated frontier/mountain provinces. These are uncertain game assessments,
   not measured medieval development scores or newly surveyed hectares.

The annual crop source already accounts for fallow and post-harvest losses. No
second European fallow deduction was justified or applied. HYDE total irrigation
already includes rice and non-rice irrigation. The earlier suspicion of omitted
rice irrigation was not confirmed.

## Historical evidence and its limits

The first variant used a basic mixed-agriculture default with local/regional
overrides. Its regressions exposed insufficient historical coverage in that default.
The pipeline's three ArchaeoGLOBE intensity/value columns were entirely null across
20,929 locations despite populated resolution labels. Naming the source had not
made it an input to historical management.

The second variant maps the authors' **146-region ArchaeoGLOBE assessment** to
canonical location centroids in the source's Eckert IV projection. It matches
20,567 locations; 362 remain unmapped, without nearest-region imputation. Raw data,
boundaries, source commit and hashes are pinned. Data are CC0 with attribution
requested; upstream analysis code was not incorporated.

Its approximately **950 CE** intensive-agriculture assessment supplies a coarse
regional prior for 1337. The 1500 CE column is retained for diagnosis but does not
grant future practices. Continuity between dates is an explicit uncertain inference.
Regional “common” (1–20%) and “widespread” (>20%) prevalence is **not** a local field
survey, a water-service fraction or additional hectares. Only locations with dated
cultivation qualify; more specific historical evidence overrides the prior. The
central inferred developments are 31.25 and 34.375, respectively, from their frozen
intervals. They remain experimental translations of regional evidence.

Sources and interpretations:

- [ArchaeoGLOBE research compendium](https://doi.org/10.7910/DVN/6ZXAGT), associated
  with Stephens et al. (2019), [Science paper](https://doi.org/10.1126/science.aax1192).
  HYDE-related reconstructions and this source are not treated as independent validation.
- [Chen Pu's 1149 farming text](https://afe.easia.columbia.edu/ps/china/farming_chenpu.pdf):
  cultivation, labour and field/water management; prescription is not universal adoption.
- [Chakravarti, agricultural technology in India 500–1300](https://doi.org/10.1177/097194580801100203)
  and [Heitzman, Chola state formation 850–1280](https://doi.org/10.1177/001946468702400102):
  historical practice analogues; publisher access limitations and inferred ranges
  remain in the evidence file. No quantitative acreage is claimed from inaccessible text.
- [Sakurai, Tran-period Red River agriculture](https://www.jstage.jst.go.jp/article/tak/27/3/27_KJ00000131529/_article/-char/en):
  dated embankment and crop-system development, with flood limitations.
- Existing Java/Bali rice-presence evidence is reused without adding an unsupported
  second annual rice crop. Kyaukse's cached secondary historical account supports
  system presence, not a measured medieval irrigation area.

See [first frozen evidence](hierarchical_management_round_56_evidence.json),
[regional-practice evidence](archaeoglobe_round_56_evidence.json), and
[pinned source objects](archaeoglobe_source_objects.json).

## Evaluated outcomes

Identical starting populations, food/growth parameters, physical scale 4.5,
area exponent 0.75, development coefficient 0.05, subsistence output 1.3,
12 months of initial stocks, agricultural slave hiring 0.75 and the existing
25%-of-D50 decay offset are used throughout. Infrastructure remains direct
magnitudes; observed employment and existing food production are retained.

| Metric | Round55 baseline | Basic hierarchy | Historical-practice hierarchy |
|---|---:|---:|---:|
| Starting capacity, million people | 1,661.39 | 1,521.89 | 1,840.88 |
| Mean starting development | 27.57 | 21.29 | 28.53 |
| Population at 100, million | 484.51 | 476.13 | 493.42 |
| Population at 200, million | 522.92 | 514.53 | 536.54 |
| Original complete-province horizon checks | 52/52 | 52/52 | 52/52 |
| Expanded year 100 checks | 46/48 | 46/48 | 47/48 |
| Expanded year 200 checks | 46/48 | 45/48 | 46/48 |
| Locations with any unmet food by 200 | 5,058 | 5,279 | 4,903 |
| Newly affected relative to baseline | — | 312 | 159 |
| Resolved relative to baseline | — | 91 | 314 |

These are controlled economic diagnostics, not historical population targets.
Original core passes do not override global collateral failures. Current unmet-food
locations at year 200 are2,350/2,356/2,352; the lower historical-variant cumulative
count mainly improves earlier scarcity, not the entire late food economy.

Specific diagnoses:

- **Hatunqulla:** the basic hierarchy introduced40 post-startup unmet location-months
  despite a higher provincial capacity total. Capacity was concentrated differently
  while neighbouring management assessments fell. The regional historical-practice
  variant removes this regression. Coarse Andean practice evidence does not justify
  assigning every Tiwanaku raised field to 1337: local continuity remains uncertain.
- **Indrapura Khmer:** already below the retention threshold in the baseline,
  it worsens to73.17%/72.72% population retention in the historical variant, with140
  post-startup unmet location-months. The starting budget contains pressure-recoverable
  demand; regional practice alone is insufficient to establish local maintained land
  and water support. Do not close this through invented imports or urban-food assumptions.
- **Caozhou:** improves from79.70%/75.16% to92.04%/88.07%. It still misses year 200,
  without unmet food. Its low-pressure starting diagnostic has little remaining
  recoverable consumption. More capacity is therefore not a sufficient explanation
  or justified remedy for its food-stock/growth balance.
  At year200 its mean food-stock bonus is +0.4764% annually against the retained
  −0.5% rank baseline: net growth remains about −0.0236% annually despite a positive
  production-minus-consumption balance. This directly demonstrates the distinction
  between food break-even and growth equilibrium. Food/growth coefficients remain
  frozen for this geographical comparison.
- **Global hierarchy collateral:** North American capacity rises22.09million entirely
  through the management reassignment; South Asia rises50.19million, of which47.98million
  is the sequential management effect. East Asia rises50.90million, mostly43.77million
  from recovered physical support. This is why the broader prior is not adopted
  simply because its aggregate survival count improves.

The coarse practice layer applies to 13,008 locations. Of these, 4,588 have less
than 1% reconstructed crop/fallow area. This is a diagnostic flag, not a new
development cutoff: sparse cultivation can still be intensive, and reconstruction
gaps remain possible. It identifies where regional practice is particularly weak
evidence for location-wide management. The flag does not change any candidate.

## Physical and reporting checks

All 20,929 locations conserve physical land, have no recorded assignment-area conflict,
and reconcile the water partition. Maximum land residual is below 8e-12 km².
The first variant adds/recovers 66,512.40 km² of reconstructed fields and 3,439.93 km²
of water-served fields relative to the baseline. These are source/scenario assignments,
not proof of precise 1337 survey accuracy. Recovered fields do not create new unused
clearing opportunity.

Both candidate starting states and all 3,819 provincial food budgets reproduce
through the canonical food auditor. Population components, consumption components
and subsistence surplus reconcile in every saved monthly diagnostic frame and world
checkpoint. Monthly complete-province histories agree with the world checkpoints.

Final `uv run ppc test -q -ra`: **892 passed, 1 skipped** in607.79 seconds.
The existing skip is `tests/test_setup_building_corrections.py:221`: this machine's
local error log contains no setup-building errors. The final test manifest verifies
that simulator and test sources were unchanged during that run. The final replay
also verifies byte-identical world checkpoints after the reporting corrections.

The macro table includes min/max/median/mean capacity and development, density,
fill, irrigated-field area share, incremental irrigation capacity share and remaining
clearing share. Capacity units in the CSV are **thousands of people**; density is
people/km². Shares use regional sums, rather than averages of local percentages.
In the historical-practice variant, incremental irrigation is **1.69%** of current
capacity; the previous alias would have called all **95.27%** infrastructure
“irrigation.” Removing development while holding its physical ledger fixed reduces
native capacity by **62.59%**, whereas the legacy additive decomposition attributes
only development-on-natural-base (**2.64%**) to its development row. Both meanings
are now explicit; the full-development counterfactual overlaps the source shares.
Remaining water support is kept separate as an upper opportunity pending water-volume
evidence. Neither this nor the very large remaining-clearing pools establishes a
defensible final building maximum. Construction balancing remains deferred.

The shared area exponent remains0.75 for both current support and improvement
gains. For an otherwise identical physical system, splitting one location into
two equal locations raises summed game support by18.9%; four equal locations
raise it by41.4%. This follows the retained sublinear conversion, not a new land
gain. The round does not claim subdivision invariance.

## Decision and artifacts

Retain the canonical accounting fixes, explicit evidence hierarchy, source crosswalk,
new named-system experiments and reproducible comparisons. **Do not promote either
broad assignment set as accepted balance.** The main unresolved issue is now explicit:
how regional evidence applies to individual cultivated systems, especially mixed
livelihoods and Khmer/other Southeast Asian locations. Broad regional prevalence
cannot automatically become intensive local management.

Artifacts are under `artifacts/data/population_simulation/repair_round_56`:

- `handoff/starting_comparison.png` and `historical_variant_changes.png`: comparable
  point maps with fixed colour scales, visually checked.
- `handoff/macro_starting_statistics.csv`: all macro regions and all three candidates.
- `handoff/*_attribution.csv` and `*_location_attribution.parquet`: top-down attribution.
- `handoff/coarse_practice_coverage.csv` and `coarse_practice_sparse_field_flags.csv`:
  regional-prior applicability warnings, with a separate diagnostic contract.
- `handoff/diagnostic_growth_budgets.csv`: the food-stock/growth distinction for
  Caozhou, Hatunqulla and Indrapura at saved diagnostic dates.
- `comparison/` and `archaeoglobe/comparison/`: every evaluated horizon, failures,
  new unmet locations, provincial starting budgets and world/region/province summaries.
- `world/` and `archaeoglobe/world/`: canonical inputs, monthly provincial histories,
  annual world aggregates, checkpoints and all-province food audits.
- `handoff/full_tests.log`, `test_manifest.json` and `final_replay_manifest.json`:
  final verification evidence. Do not infer completion from this document if those
  artifacts are missing, nonzero, or report changed tested sources.

```sh
uv run python research/population_capacity/build_hierarchical_round_56.py
uv run python research/population_capacity/audit_hierarchical_round_56.py
uv run python research/population_capacity/run_hierarchical_round_56.py
uv run python research/population_capacity/fetch_archaeoglobe_round_56.py
uv run python research/population_capacity/build_archaeoglobe_round_56.py
uv run python research/population_capacity/run_archaeoglobe_round_56.py
uv run python research/population_capacity/report_hierarchical_round_56.py
uv run python research/population_capacity/report_hierarchical_round_56.py --archaeoglobe
uv run python research/population_capacity/summarize_hierarchical_round_56.py
uv run python research/population_capacity/audit_candidate_food_accounts.py --experiment artifacts/data/population_simulation/repair_round_56/world --all-provinces
uv run python research/population_capacity/audit_candidate_food_accounts.py --experiment artifacts/data/population_simulation/repair_round_56/archaeoglobe/world --all-provinces
uv run ppc test tests/test_management_hierarchy.py tests/test_historical_model.py tests/test_annual_crop.py tests/test_physical_support.py -q
uv run ppc test -q -ra
uv run python research/population_capacity/verify_hierarchical_round_56.py
```

Cached predecessor datasets remain prerequisites, with their hashes checked by the
canonical preparation. No game export, repo-local mod build or live deployment is
part of this round. The authorized infrastructure and tribal assumptions are retained;
they are not repeatedly used to block independent geographical work.
