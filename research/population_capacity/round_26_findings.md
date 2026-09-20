# Round 26: crop sources and dated Taihu yields

**Model status: not accepted.** These are paired diagnostics over the same 22 complete provinces. Building balance and game export remain deferred.

The legacy historical model combines joint-scenario rainfed support with static irrigated sample support. The matching-source candidate uses static calorie/protein and suitable-area denominators for both modes. This corrects comparability, but is not itself proof of medieval yield accuracy. It worsens several heartlands and is not accepted as a global replacement.

The Taihu attained-yield candidate uses the cached Liu (1991) Song observation: 450 source catties per mou × 0.6 kg × 15 mou/ha = 4,050 kg gross paddy/ha for one harvest. Dry matter of 0.80–0.90 is an explicit sensitivity assumption. Existing crop retention and calorie/protein requirements give 704.63–792.71 standalone people per cultivated km² before game scaling. The scenario carries that Song system to 1337; it does not borrow later Ming yields.

The attained density replaces support on assigned water-managed fields. It is divided by the assessed starting development factor before flat infrastructure is calculated, so management is not multiplied twice. No extra harvest or adoption hectare is added. The unchanged cultivated range remains inferred, not a measured medieval cadastral total.

Rank experiments preserve native tribal cancellation. They are diagnostic and unaccepted; neither demand nor capacity changes. Extent experiments vary only Taihu within the previously documented 35–55% range, holding neighbouring assignments fixed.

| Candidate | Province | Year | Minimum location population retention | Unmet location-months after startup | Viability |
|---|---|---:|---:|---:|---|
| legacy | jiaxing_province | 100 | 78.7% | 12 | failed |
| legacy | jiaxing_province | 200 | 75.4% | 12 | failed |
| legacy | songjiang_province | 100 | 115.3% | 0 | passed |
| legacy | songjiang_province | 200 | 111.1% | 0 | passed |
| legacy | suzhou_province | 100 | 101.5% | 0 | passed |
| legacy | suzhou_province | 200 | 98.2% | 0 | passed |
| matched | jiaxing_province | 100 | 64.8% | 165 | failed |
| matched | jiaxing_province | 200 | 61.0% | 165 | failed |
| matched | songjiang_province | 100 | 88.2% | 0 | failed |
| matched | songjiang_province | 200 | 81.2% | 0 | failed |
| matched | suzhou_province | 100 | 89.5% | 0 | failed |
| matched | suzhou_province | 200 | 82.7% | 0 | failed |
| taihu_attained | jiaxing_province | 100 | 82.9% | 0 | failed |
| taihu_attained | jiaxing_province | 200 | 79.1% | 0 | failed |
| taihu_attained | songjiang_province | 100 | 106.8% | 0 | passed |
| taihu_attained | songjiang_province | 200 | 100.8% | 0 | passed |
| taihu_attained | suzhou_province | 100 | 96.7% | 0 | passed |
| taihu_attained | suzhou_province | 200 | 92.5% | 0 | passed |
| taihu_extent_high | jiaxing_province | 100 | 94.8% | 0 | passed |
| taihu_extent_high | jiaxing_province | 200 | 90.7% | 0 | passed |
| taihu_extent_high | songjiang_province | 100 | 120.1% | 0 | passed |
| taihu_extent_high | songjiang_province | 200 | 114.3% | 0 | passed |
| taihu_extent_high | suzhou_province | 100 | 105.1% | 0 | passed |
| taihu_extent_high | suzhou_province | 200 | 101.8% | 0 | passed |
| taihu_extent_low | jiaxing_province | 100 | 71.1% | 99 | failed |
| taihu_extent_low | jiaxing_province | 200 | 67.6% | 99 | failed |
| taihu_extent_low | songjiang_province | 100 | 90.2% | 0 | passed |
| taihu_extent_low | songjiang_province | 200 | 85.0% | 0 | failed |
| taihu_extent_low | suzhou_province | 100 | 83.9% | 0 | failed |
| taihu_extent_low | suzhou_province | 200 | 78.7% | 0 | failed |
| taihu_half_rank_penalty | jiaxing_province | 100 | 85.2% | 3 | failed |
| taihu_half_rank_penalty | jiaxing_province | 200 | 83.1% | 3 | failed |
| taihu_half_rank_penalty | songjiang_province | 100 | 110.2% | 0 | passed |
| taihu_half_rank_penalty | songjiang_province | 200 | 107.5% | 0 | passed |
| taihu_half_rank_penalty | suzhou_province | 100 | 99.8% | 0 | passed |
| taihu_half_rank_penalty | suzhou_province | 200 | 97.5% | 0 | passed |
| taihu_no_rank_penalty | jiaxing_province | 100 | 87.4% | 3 | failed |
| taihu_no_rank_penalty | jiaxing_province | 200 | 86.8% | 3 | failed |
| taihu_no_rank_penalty | songjiang_province | 100 | 113.7% | 0 | passed |
| taihu_no_rank_penalty | songjiang_province | 200 | 113.6% | 0 | passed |
| taihu_no_rank_penalty | suzhou_province | 100 | 102.8% | 0 | passed |
| taihu_no_rank_penalty | suzhou_province | 200 | 102.2% | 0 | passed |

Viability applies the user’s peaceful-control food, population and development checks independently at each horizon. It does not certify geographical evidence, water budgets, holdouts, demographic plausibility or the remaining scenario matrix. A province total cannot override a failing location.

All candidates preserve slave consumption and reserve workers/land for the 75% agricultural-employment diagnostic. Current building employment and food remain separate from direct infrastructure.

Artifacts: `artifacts/data/population_simulation/repair_round_26/crop_contract/` contains each starting ledger, provincial food budget and monthly trajectory; `viability_criteria.csv` covers every compared province at both horizons; `province_comparison.csv` records totals; `crop_density_comparison.parquet` records the physical/game-unit comparison. `manifest.json` binds scenarios and preparation to the input fingerprint.

Evidence fingerprint: `b0e49b03bf364fd848802412def59d3ba00a945ddbd577f0abc6d04ec3490b53`.

Reproduce from the repository:

```sh
uv run python research/population_capacity/run_matched_crop_contract.py
uv run python research/population_capacity/summarize_crop_contract.py
uv run ppc test tests/test_behavior_acceptance.py tests/test_historical_model.py tests/test_crop_intensification.py
uv run ppc test
```

Remaining work: resolve Bali/Java and other regional food deficits; complete dated physical and demographic benchmarks, water opportunity validation, holdouts and sensitivity; rerun the full mandatory acceptance matrix for a defensible shared candidate. No accepted manifest is issued by this report.

Validation: `uv run ppc test` — 840 passed, 1 skipped. Existing environment-dependent setup-building check: local error.log contains no setup building errors.

Additional Bali research: [Mediani (1989) evidence ledger](bali_mediani_1989_evidence.json) records medieval cooperative clearing and irrigation, the 12th–19th-century documentation gap, and unresolved historical area units. It supplies no automatic hectare or capacity increase.
