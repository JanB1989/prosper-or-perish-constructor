# Population Capacity Simulation Report

**Overall: FAIL**

- Profile: `/home/jan/development/ProsperOrPerishConstructor/population_capacity_simulation.toml`
- Runtime: 22.2 seconds
- Runtime split: preparation 19.45s; simulation 2.64s
- Source cache: hit
- Modifier cache: miss
- Reproducible run hash: `153e2a355ab3d00f`
- Locations: 20,929
- Checkpoints: 0, 25, 100 years
- Primary target window: 0–100 years; later checkpoints are advisory
- Global primary target result: PASS
- Scored HYDE region checkpoints: 76.5% pass (required 75.0%)
- Location sanity result: FAIL

## Global checkpoints

| Years | Calendar | Population | Growth | HYDE target | Error | Capacity | Fill | Development | Result |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|
| 0 | 1337 | 394.5m | 1.00× | 1.00× | +0.0% | 849.1m | 46.5% | 7.4 | PASS |
| 25 | 1362 | 367.1m | 0.93× | — | — | 849.2m | 43.2% | 7.5 | — |
| 100 | 1437 | 289.4m | 0.73× | 0.97× | -24.4% | 849.5m | 34.1% | 7.8 | reference |

## HYDE regional benchmarks

Targets are normalized to each region's simulated year-0 population. The ordinary tolerance is ±25%. Rows marked reference are plague/contact-shock observations; rows after the primary window are advisory. Neither is scored against the capacity-only model.
HYDE source slices are 1300 (baseline), 1400, 1500, 1600, 1740, and 1840; the report compares them with simulation years 0, 100, 200, 300, 400, and 500 from 1337.

| Region | Years | Population | Growth | HYDE target | Error | Fill | Development | Result |
|---|---:|---:|---:|---:|---:|---:|---:|:---:|
| Europe | 100 | 52.3m | 0.68× | 0.73× | -7.1% | 29.3% | 12.4 | reference |
| North Africa | 100 | 10.4m | 0.76× | 0.92× | -17.0% | 43.3% | 7.1 | PASS |
| West Africa | 100 | 9.2m | 0.89× | 1.12× | -20.6% | 37.0% | 5.0 | PASS |
| Central Africa | 100 | 7.2m | 0.99× | 1.15× | -14.5% | 27.9% | 2.1 | PASS |
| East Africa | 100 | 10.1m | 0.92× | 1.15× | -19.5% | 29.9% | 2.1 | PASS |
| Southern Africa | 100 | 684.5k | 1.00× | 1.11× | -10.1% | 9.0% | 1.3 | PASS |
| Near East | 100 | 12.0m | 0.72× | 0.85× | -15.3% | 30.7% | 12.0 | PASS |
| Central Asia | 100 | 2.2m | 0.71× | 1.09× | -34.1% | 14.3% | 4.7 | FAIL |
| South Asia | 100 | 67.9m | 0.69× | 1.04× | -34.0% | 60.3% | 10.0 | FAIL |
| East Asia | 100 | 73.1m | 0.70× | 0.93× | -24.8% | 49.0% | 10.8 | PASS |
| Southeast Asia | 100 | 13.2m | 0.75× | 1.20× | -37.5% | 27.4% | 2.7 | FAIL |
| Oceania | 100 | 1.5m | 1.00× | 1.04× | -4.0% | 5.8% | 1.5 | PASS |
| North America | 100 | 2.4m | 0.99× | 1.11× | -11.0% | 3.1% | 1.4 | PASS |
| Mesoamerica | 100 | 11.8m | 0.90× | 1.10× | -18.3% | 37.9% | 7.4 | PASS |
| Caribbean | 100 | 133.2k | 1.00× | 1.44× | -30.7% | 2.8% | 1.4 | FAIL |
| Andes | 100 | 7.7m | 0.95× | 1.06× | -10.3% | 56.2% | 5.6 | PASS |
| Tropical South America | 100 | 5.4m | 0.99× | 1.08× | -8.4% | 24.5% | 2.5 | PASS |
| Southern Cone | 100 | 786.7k | 1.00× | 1.10× | -8.7% | 11.3% | 1.6 | PASS |

## HYDE region starting composition

The current simulator has no migration or pop-type promotion/demotion. Tribesmen have a parsed zero food-consumption baseline, so this profile exempts them from negative location-rank growth. That keeps tribesmen-heavy regions stable, but it does not manufacture the later transitions needed to follow every HYDE growth target.

| Region | Game population | HYDE population signal | Peasants | Tribesmen | Capacity fill | Population within capacity | Development | Irrigation levels |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Europe | 77.0m | 124.6m | 72.3% | 3.7% | 43.1% | 44.3% | 12.6 | 173 |
| North Africa | 13.7m | 15.5m | 51.9% | 28.5% | 56.7% | 51.0% | 6.7 | 451 |
| West Africa | 10.3m | 21.8m | 22.4% | 66.3% | 41.7% | 57.0% | 4.2 | 105 |
| Central Africa | 7.2m | 8.5m | 2.4% | 96.0% | 28.3% | 63.5% | 1.0 | 6 |
| East Africa | 10.9m | 12.1m | 18.6% | 75.5% | 32.4% | 55.8% | 1.0 | 117 |
| Southern Africa | 684.5k | 721.3k | 0.0% | 100.0% | 9.1% | 65.9% | 0.0 | 1 |
| Near East | 16.7m | 20.8m | 55.9% | 13.5% | 42.9% | 58.7% | 12.2 | 741 |
| Central Asia | 3.1m | 3.4m | 62.3% | 11.1% | 20.1% | 75.1% | 3.9 | 166 |
| South Asia | 98.7m | 200.3m | 64.8% | 4.0% | 87.7% | 26.0% | 9.9 | 1,742 |
| East Asia | 104.9m | 127.7m | 76.8% | 10.3% | 70.3% | 30.7% | 10.8 | 755 |
| Southeast Asia | 17.7m | 16.7m | 62.1% | 23.3% | 36.8% | 42.1% | 1.6 | 21 |
| Oceania | 1.5m | 1.0m | 0.1% | 99.7% | 5.8% | 60.6% | 0.3 | 0 |
| North America | 2.4m | 2.3m | 1.1% | 95.9% | 3.2% | 95.7% | 0.2 | 22 |
| Mesoamerica | 13.2m | 30.9m | 22.8% | 68.3% | 42.3% | 44.9% | 7.0 | 44 |
| Caribbean | 133.2k | 399.9k | 0.0% | 100.0% | 2.8% | 100.0% | 0.1 | 0 |
| Andes | 8.1m | 5.7m | 9.8% | 85.9% | 59.0% | 38.4% | 4.9 | 77 |
| Tropical South America | 5.5m | 18.3m | 1.8% | 97.7% | 24.7% | 63.7% | 1.3 | 0 |
| Southern Cone | 786.7k | 612.1k | 0.0% | 100.0% | 11.4% | 95.9% | 0.1 | 0 |

## Maximum infrastructure — Phase 1

This is a building-independent physical opportunity target. HYDE land use is reported only as geographical validation and does not fit the capacity values.

| Metric (people) | Count | Minimum | Maximum | Mean | Median | Std. dev. | Sum |
|---|---:|---:|---:|---:|---:|---:|---:|
| Irrigation opportunity | 20,929 | 0 | 2,341,333 | 32,976 | 605 | 93,933 | 690,145,995 |
| Land-improvement opportunity | 20,929 | 0 | 4,206,447 | 80,373 | 0 | 208,265 | 1,682,119,479 |
| Total maximum infrastructure | 20,929 | 0 | 4,237,632 | 113,348 | 35,784 | 220,754 | 2,372,265,474 |
| Development-100 maximum capacity | 20,929 | 7,875 | 4,826,961 | 168,872 | 83,999 | 254,598 | 3,534,317,408 |

Global development-100 capacity: **3.534b** against a 4.000b ceiling (**PASS**).
Raw joint-scenario component quantiles crossed in **15,475** locations; P50 is unchanged and diagnostic P10/P90 use lower/upper envelopes.
Implausible global leaders flagged for map review: **15**.

### Highest-capacity locations

| Location | Province | Macro-region | Irrigation | Land improvement | Infrastructure | Final maximum |
|---|---|---|---:|---:|---:|---:|
| uele_ca | bomokandi_province | central_africa | 31,184 | 4,206,447 | 4,237,632 | 4,826,961 |
| charrua | guenoa_province | south_america | 30,481 | 3,358,529 | 3,389,010 | 3,872,261 |
| yi | guenoa_province | south_america | 16,525 | 3,351,154 | 3,367,678 | 3,848,263 |
| yacegua | guenoa_province | south_america | 36,660 | 3,194,321 | 3,230,981 | 3,677,604 |
| arachan | guenoa_province | south_america | 0 | 3,166,224 | 3,166,224 | 3,604,752 |
| kotto | djemah_province | central_africa | 148,263 | 3,001,209 | 3,149,472 | 3,602,781 |
| isiro | bomokandi_province | central_africa | 20,735 | 2,948,847 | 2,969,582 | 3,400,404 |
| bosobolo | boali_province | central_africa | 41,546 | 2,925,397 | 2,966,943 | 3,397,435 |
| guatacuba | upper_tocantins_province | south_america | 15,485 | 2,957,664 | 2,973,149 | 3,387,543 |
| bangui | boali_province | central_africa | 66,871 | 2,725,692 | 2,792,562 | 3,201,257 |

### HYDE geographical validation (not fitted)

| Opportunity / year | Spearman rank correlation | Top-opportunity locations with realized land use |
|---|---:|---:|
| irrigation 1300 | 0.101 | 10.5% |
| irrigation 1800 | 0.131 | 14.9% |
| irrigation modern | 0.295 | 49.0% |
| land improvement 1300 | -0.148 | 80.8% |
| land improvement 1800 | -0.102 | 95.1% |
| land improvement modern | 0.056 | 97.7% |

Review artifacts:
- Locations: `/home/jan/development/ProsperOrPerishConstructor/tmp/population_capacity_design_review/fresh_modifiers_baseline_maximum.parquet`
- Macro Regions: `/home/jan/development/ProsperOrPerishConstructor/tmp/population_capacity_design_review/fresh_modifiers_baseline_maximum_macro_regions.csv`
- Province Statistics: `/home/jan/development/ProsperOrPerishConstructor/tmp/population_capacity_design_review/fresh_modifiers_baseline_maximum_province_statistics.csv`
- Province Totals: `/home/jan/development/ProsperOrPerishConstructor/tmp/population_capacity_design_review/fresh_modifiers_baseline_maximum_province_totals.csv`
- Location Rankings: `/home/jan/development/ProsperOrPerishConstructor/tmp/population_capacity_design_review/fresh_modifiers_baseline_maximum_location_rankings.csv`
- Tracked Provinces: `/home/jan/development/ProsperOrPerishConstructor/tmp/population_capacity_design_review/fresh_modifiers_baseline_maximum_tracked_provinces.csv`
- Summary: `/home/jan/development/ProsperOrPerishConstructor/tmp/population_capacity_design_review/fresh_modifiers_baseline_maximum_summary.json`

## Macro-region calibration statistics

All capacity and population values are EU5 units (1 = 1,000 people). Ocean sentinel regions remain visible so incomplete classification cannot be hidden.

### Location level

| Macro region | Metric | Count | Minimum | Maximum | Mean | Median | Stddev | Sum |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| australasia | location_potential | 492 | 6.928 | 354.944 | 41.100 | 25.440 | 43.767 | 20,221.104 |
| central_africa | location_potential | 563 | 6.928 | 406.369 | 45.809 | 28.047 | 51.475 | 25,790.426 |
| central_asia | location_potential | 417 | 6.928 | 350.753 | 31.676 | 18.663 | 36.940 | 13,209.005 |
| east_africa | location_potential | 605 | 6.928 | 495.222 | 47.364 | 27.908 | 56.661 | 28,655.510 |
| east_asia | location_potential | 3146 | 6.928 | 692.824 | 43.253 | 23.011 | 60.454 | 136,074.565 |
| eastern_europe | location_potential | 2517 | 6.928 | 692.824 | 39.574 | 21.614 | 51.224 | 99,607.188 |
| middle_east | location_potential | 1262 | 6.928 | 306.959 | 24.638 | 17.565 | 24.911 | 31,093.573 |
| north_africa | location_potential | 397 | 6.928 | 365.124 | 40.759 | 22.940 | 59.531 | 16,181.448 |
| north_america | location_potential | 3084 | 6.928 | 692.824 | 35.788 | 18.014 | 55.136 | 110,369.726 |
| north_asia | location_potential | 874 | 6.928 | 206.948 | 17.122 | 6.928 | 24.351 | 14,964.390 |
| north_atlantic_ocean_sub_continent | location_potential | 1 | 46.889 | 46.889 | 46.889 | 46.889 | 0.000 | 46.889 |
| pacific_islands | location_potential | 298 | 6.928 | 363.798 | 30.923 | 11.784 | 50.179 | 9,215.103 |
| south_america | location_potential | 1357 | 6.928 | 451.780 | 30.609 | 19.923 | 37.572 | 41,536.896 |
| south_asia | location_potential | 1230 | 6.928 | 692.824 | 60.485 | 46.350 | 56.823 | 74,396.334 |
| south_atlantic_sub_continent | location_potential | 1 | 6.928 | 6.928 | 6.928 | 6.928 | 0.000 | 6.928 |
| south_east_asia | location_potential | 1044 | 6.928 | 692.824 | 44.796 | 19.547 | 69.415 | 46,766.818 |
| southern_africa | location_potential | 293 | 6.928 | 365.124 | 38.607 | 23.406 | 46.520 | 11,311.950 |
| west_africa | location_potential | 575 | 6.928 | 321.246 | 41.317 | 27.765 | 39.652 | 23,757.487 |
| western_europe | location_potential | 2773 | 6.928 | 285.085 | 20.766 | 14.463 | 21.994 | 57,583.068 |
| australasia | infrastructure | 492 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| central_africa | infrastructure | 563 | 0.000 | 19.620 | 0.188 | 0.000 | 1.218 | 105.620 |
| central_asia | infrastructure | 417 | 0.000 | 87.010 | 9.778 | 0.000 | 15.448 | 4,077.220 |
| east_africa | infrastructure | 605 | 0.000 | 48.730 | 4.589 | 0.000 | 9.045 | 2,776.600 |
| east_asia | infrastructure | 3146 | 0.000 | 127.650 | 4.761 | 0.000 | 14.173 | 14,978.960 |
| eastern_europe | infrastructure | 2517 | 0.000 | 87.010 | 0.998 | 0.000 | 4.981 | 2,511.910 |
| middle_east | infrastructure | 1262 | 0.000 | 96.500 | 13.426 | 9.810 | 14.367 | 16,943.360 |
| north_africa | infrastructure | 397 | 0.000 | 96.500 | 11.406 | 0.000 | 20.625 | 4,528.140 |
| north_america | infrastructure | 3084 | 0.000 | 106.500 | 0.810 | 0.000 | 5.015 | 2,498.500 |
| north_asia | infrastructure | 874 | 0.000 | 31.150 | 0.489 | 0.000 | 3.424 | 427.820 |
| north_atlantic_ocean_sub_continent | infrastructure | 1 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| pacific_islands | infrastructure | 298 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| south_america | infrastructure | 1357 | 0.000 | 67.710 | 0.891 | 0.000 | 4.610 | 1,208.730 |
| south_asia | infrastructure | 1230 | 0.000 | 96.500 | 9.077 | 0.000 | 18.509 | 11,165.160 |
| south_atlantic_sub_continent | infrastructure | 1 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| south_east_asia | infrastructure | 1044 | 0.000 | 50.770 | 1.071 | 0.000 | 5.126 | 1,118.610 |
| southern_africa | infrastructure | 293 | 0.000 | 19.620 | 0.291 | 0.000 | 1.897 | 85.320 |
| west_africa | infrastructure | 575 | 0.000 | 39.430 | 2.551 | 0.000 | 6.567 | 1,466.760 |
| western_europe | infrastructure | 2773 | 0.000 | 96.500 | 2.681 | 0.000 | 7.064 | 7,434.210 |
| australasia | development | 492 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| central_africa | development | 563 | 0.000 | 16.260 | 0.895 | 0.360 | 1.874 | 503.790 |
| central_asia | development | 417 | 0.000 | 32.940 | 4.475 | 2.250 | 5.611 | 1,865.880 |
| east_africa | development | 605 | 0.000 | 21.640 | 1.607 | 0.630 | 2.665 | 972.200 |
| east_asia | development | 3146 | 0.000 | 65.020 | 10.212 | 4.105 | 13.388 | 32,127.920 |
| eastern_europe | development | 2517 | 0.000 | 51.620 | 5.544 | 3.040 | 6.873 | 13,954.990 |
| middle_east | development | 1262 | 0.000 | 47.050 | 9.481 | 5.825 | 9.922 | 11,964.720 |
| north_africa | development | 397 | 0.000 | 53.470 | 6.871 | 3.900 | 8.616 | 2,727.640 |
| north_america | development | 3084 | 0.000 | 52.480 | 1.482 | 0.010 | 4.313 | 4,570.090 |
| north_asia | development | 874 | 0.000 | 21.230 | 0.445 | 0.000 | 1.700 | 388.850 |
| north_atlantic_ocean_sub_continent | development | 1 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| pacific_islands | development | 298 | 0.000 | 12.900 | 0.669 | 0.010 | 1.754 | 199.340 |
| south_america | development | 1357 | 0.000 | 49.100 | 2.084 | 0.110 | 6.147 | 2,828.370 |
| south_asia | development | 1230 | 0.000 | 48.120 | 11.993 | 10.565 | 9.352 | 14,751.980 |
| south_atlantic_sub_continent | development | 1 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| south_east_asia | development | 1044 | 0.000 | 28.770 | 1.737 | 0.545 | 3.197 | 1,813.420 |
| southern_africa | development | 293 | 0.000 | 2.330 | 0.141 | 0.040 | 0.291 | 41.390 |
| west_africa | development | 575 | 0.000 | 45.630 | 4.062 | 2.120 | 5.105 | 2,335.560 |
| western_europe | development | 2773 | 0.000 | 69.880 | 23.106 | 22.070 | 17.154 | 64,072.180 |
| australasia | capacity | 492 | 7.000 | 355.000 | 41.565 | 26.000 | 43.818 | 20,450.000 |
| central_africa | capacity | 563 | 7.000 | 407.036 | 46.499 | 29.029 | 51.548 | 26,178.900 |
| central_asia | capacity | 417 | 7.000 | 362.998 | 42.120 | 27.843 | 40.157 | 17,564.021 |
| east_africa | capacity | 605 | 7.000 | 504.004 | 52.572 | 37.004 | 56.296 | 31,806.081 |
| east_asia | capacity | 3146 | 7.000 | 754.719 | 49.170 | 28.005 | 64.462 | 154,689.440 |
| eastern_europe | capacity | 2517 | 7.000 | 696.396 | 41.300 | 23.240 | 51.830 | 103,950.850 |
| middle_east | capacity | 1262 | 7.000 | 307.311 | 38.983 | 36.039 | 29.204 | 49,197.000 |
| north_africa | capacity | 397 | 7.000 | 487.550 | 53.293 | 33.006 | 73.351 | 21,157.410 |
| north_america | capacity | 3084 | 7.000 | 697.167 | 37.080 | 19.000 | 55.625 | 114,355.222 |
| north_asia | capacity | 874 | 7.000 | 207.000 | 17.883 | 7.000 | 25.110 | 15,629.467 |
| north_atlantic_ocean_sub_continent | capacity | 1 | 47.000 | 47.000 | 47.000 | 47.000 | 0.000 | 47.000 |
| pacific_islands | capacity | 298 | 7.000 | 368.163 | 31.317 | 12.005 | 50.454 | 9,332.551 |
| south_america | capacity | 1357 | 7.000 | 461.461 | 32.027 | 21.033 | 38.157 | 43,460.567 |
| south_asia | capacity | 1230 | 7.000 | 715.484 | 71.219 | 59.272 | 59.171 | 87,599.074 |
| south_atlantic_sub_continent | capacity | 1 | 7.000 | 7.000 | 7.000 | 7.000 | 0.000 | 7.000 |
| south_east_asia | capacity | 1044 | 7.000 | 694.776 | 46.379 | 21.020 | 70.178 | 48,419.189 |
| southern_africa | capacity | 293 | 7.000 | 366.005 | 39.397 | 25.006 | 46.490 | 11,543.377 |
| west_africa | capacity | 575 | 7.000 | 326.919 | 44.615 | 32.353 | 40.020 | 25,653.630 |
| western_europe | capacity | 2773 | 7.000 | 292.950 | 24.554 | 18.074 | 23.728 | 68,088.706 |
| australasia | fill | 492 | 0.000 | 0.319 | 0.025 | 0.015 | 0.032 | 12.302 |
| central_africa | fill | 563 | 0.009 | 4.325 | 0.459 | 0.319 | 0.451 | 258.161 |
| central_asia | fill | 417 | 0.007 | 5.538 | 0.342 | 0.161 | 0.592 | 142.769 |
| east_africa | fill | 605 | 0.000 | 6.764 | 0.590 | 0.394 | 0.586 | 357.181 |
| east_asia | fill | 3146 | 0.000 | 7.352 | 1.010 | 0.664 | 1.101 | 3,177.275 |
| eastern_europe | fill | 2517 | 0.004 | 5.277 | 0.496 | 0.311 | 0.534 | 1,248.689 |
| middle_east | fill | 1262 | 0.015 | 4.446 | 0.506 | 0.282 | 0.599 | 638.507 |
| north_africa | fill | 397 | 0.000 | 4.665 | 0.734 | 0.528 | 0.655 | 291.504 |
| north_america | fill | 3084 | 0.000 | 7.089 | 0.198 | 0.030 | 0.452 | 609.469 |
| north_asia | fill | 874 | 0.000 | 1.369 | 0.043 | 0.022 | 0.081 | 37.279 |
| north_atlantic_ocean_sub_continent | fill | 1 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| pacific_islands | fill | 298 | 0.000 | 1.909 | 0.268 | 0.101 | 0.370 | 79.778 |
| south_america | fill | 1357 | 0.000 | 5.014 | 0.473 | 0.288 | 0.515 | 642.013 |
| south_asia | fill | 1230 | 0.024 | 7.000 | 1.416 | 1.273 | 0.982 | 1,741.951 |
| south_atlantic_sub_continent | fill | 1 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| south_east_asia | fill | 1044 | 0.002 | 7.395 | 0.734 | 0.340 | 0.972 | 766.290 |
| southern_africa | fill | 293 | 0.000 | 4.098 | 0.269 | 0.092 | 0.430 | 78.794 |
| west_africa | fill | 575 | 0.000 | 6.127 | 0.672 | 0.513 | 0.655 | 386.469 |
| western_europe | fill | 2773 | 0.000 | 7.427 | 1.190 | 0.885 | 1.181 | 3,299.584 |
| australasia | population_growth_100y | 492 | 1.000 | 2.986 | 1.012 | 1.000 | 0.155 | 497.959 |
| central_africa | population_growth_100y | 563 | 0.679 | 1.000 | 0.994 | 1.000 | 0.031 | 559.417 |
| central_asia | population_growth_100y | 417 | 0.613 | 0.903 | 0.745 | 0.690 | 0.077 | 310.660 |
| east_africa | population_growth_100y | 605 | 0.614 | 2.986 | 0.884 | 1.000 | 0.226 | 534.922 |
| east_asia | population_growth_100y | 3146 | 0.607 | 2.986 | 0.782 | 0.683 | 0.221 | 2,459.304 |
| eastern_europe | population_growth_100y | 2517 | 0.611 | 1.000 | 0.718 | 0.684 | 0.080 | 1,806.571 |
| middle_east | population_growth_100y | 1262 | 0.612 | 1.000 | 0.738 | 0.687 | 0.083 | 930.984 |
| north_africa | population_growth_100y | 397 | 0.610 | 2.986 | 0.851 | 0.848 | 0.272 | 337.703 |
| north_america | population_growth_100y | 3084 | 0.000 | 2.986 | 0.987 | 1.000 | 0.137 | 3,044.867 |
| north_asia | population_growth_100y | 874 | 0.000 | 1.642 | 0.936 | 1.000 | 0.200 | 817.930 |
| north_atlantic_ocean_sub_continent | population_growth_100y | 1 | 2.986 | 2.986 | 2.986 | 2.986 | 0.000 | 2.986 |
| pacific_islands | population_growth_100y | 298 | 0.849 | 2.986 | 1.036 | 1.000 | 0.280 | 308.741 |
| south_america | population_growth_100y | 1357 | 0.709 | 2.986 | 1.016 | 1.000 | 0.232 | 1,378.212 |
| south_asia | population_growth_100y | 1230 | 0.609 | 1.000 | 0.700 | 0.679 | 0.071 | 861.369 |
| south_atlantic_sub_continent | population_growth_100y | 1 | 2.986 | 2.986 | 2.986 | 2.986 | 0.000 | 2.986 |
| south_east_asia | population_growth_100y | 1044 | 0.608 | 1.000 | 0.816 | 0.847 | 0.121 | 852.269 |
| southern_africa | population_growth_100y | 293 | 0.753 | 1.000 | 0.988 | 1.000 | 0.039 | 289.531 |
| west_africa | population_growth_100y | 575 | 0.615 | 2.986 | 0.894 | 0.875 | 0.242 | 514.039 |
| western_europe | population_growth_100y | 2773 | 0.607 | 2.986 | 0.708 | 0.679 | 0.157 | 1,963.765 |

### Province level

| Macro region | Metric | Count | Minimum | Maximum | Mean | Median | Stddev | Sum |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| australasia | location_potential | 65 | 6.928 | 856.390 | 311.094 | 303.242 | 161.972 | 20,221.104 |
| central_africa | location_potential | 80 | 66.443 | 1,099.539 | 322.380 | 270.747 | 201.462 | 25,790.426 |
| central_asia | location_potential | 75 | 30.427 | 524.553 | 176.120 | 154.383 | 110.053 | 13,209.005 |
| east_africa | location_potential | 127 | 6.928 | 1,244.819 | 225.634 | 187.681 | 175.282 | 28,655.510 |
| east_asia | location_potential | 627 | 13.856 | 1,950.741 | 217.025 | 155.807 | 215.373 | 136,074.565 |
| eastern_europe | location_potential | 459 | 20.785 | 942.878 | 217.009 | 172.876 | 164.575 | 99,607.188 |
| middle_east | location_potential | 212 | 27.949 | 524.797 | 146.668 | 130.163 | 75.812 | 31,093.573 |
| north_africa | location_potential | 72 | 6.928 | 1,322.245 | 224.742 | 158.066 | 224.311 | 16,181.448 |
| north_america | location_potential | 602 | 20.785 | 1,292.052 | 183.338 | 131.953 | 163.567 | 110,369.726 |
| north_asia | location_potential | 149 | 20.785 | 459.825 | 100.432 | 72.601 | 78.458 | 14,964.390 |
| north_atlantic_ocean_sub_continent | location_potential | 1 | 46.889 | 46.889 | 46.889 | 46.889 | 0.000 | 46.889 |
| pacific_islands | location_potential | 85 | 6.928 | 667.269 | 108.413 | 51.474 | 143.425 | 9,215.103 |
| south_america | location_potential | 183 | 27.344 | 779.817 | 226.978 | 199.040 | 149.298 | 41,536.896 |
| south_asia | location_potential | 180 | 6.928 | 1,163.382 | 413.313 | 391.691 | 238.632 | 74,396.334 |
| south_atlantic_sub_continent | location_potential | 1 | 6.928 | 6.928 | 6.928 | 6.928 | 0.000 | 6.928 |
| south_east_asia | location_potential | 191 | 20.785 | 1,477.143 | 244.852 | 178.924 | 214.101 | 46,766.818 |
| southern_africa | location_potential | 61 | 38.326 | 434.541 | 185.442 | 170.750 | 88.435 | 11,311.950 |
| west_africa | location_potential | 114 | 22.888 | 653.471 | 208.399 | 183.995 | 121.420 | 23,757.487 |
| western_europe | location_potential | 535 | 13.856 | 469.339 | 107.632 | 93.062 | 65.614 | 57,583.068 |
| australasia | infrastructure | 65 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| central_africa | infrastructure | 80 | 0.000 | 21.620 | 1.320 | 0.000 | 3.558 | 105.620 |
| central_asia | infrastructure | 75 | 0.000 | 296.680 | 54.363 | 29.430 | 72.202 | 4,077.220 |
| east_africa | infrastructure | 127 | 0.000 | 168.100 | 21.863 | 2.000 | 39.876 | 2,776.600 |
| east_asia | infrastructure | 627 | 0.000 | 330.780 | 23.890 | 4.000 | 47.235 | 14,978.960 |
| eastern_europe | infrastructure | 459 | 0.000 | 295.450 | 5.473 | 0.000 | 21.274 | 2,511.910 |
| middle_east | infrastructure | 212 | 0.000 | 365.920 | 79.922 | 69.050 | 63.958 | 16,943.360 |
| north_africa | infrastructure | 72 | 0.000 | 422.300 | 62.891 | 27.715 | 88.440 | 4,528.140 |
| north_america | infrastructure | 602 | 0.000 | 182.660 | 4.150 | 0.000 | 16.220 | 2,498.500 |
| north_asia | infrastructure | 149 | 0.000 | 70.390 | 2.871 | 0.000 | 11.719 | 427.820 |
| north_atlantic_ocean_sub_continent | infrastructure | 1 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| pacific_islands | infrastructure | 85 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| south_america | infrastructure | 183 | 0.000 | 229.630 | 6.605 | 0.000 | 24.773 | 1,208.730 |
| south_asia | infrastructure | 180 | 0.000 | 559.170 | 62.029 | 10.000 | 109.785 | 11,165.160 |
| south_atlantic_sub_continent | infrastructure | 1 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| south_east_asia | infrastructure | 191 | 0.000 | 116.650 | 5.857 | 0.000 | 16.618 | 1,118.610 |
| southern_africa | infrastructure | 61 | 0.000 | 19.620 | 1.399 | 0.000 | 4.184 | 85.320 |
| west_africa | infrastructure | 114 | 0.000 | 117.720 | 12.866 | 0.000 | 24.576 | 1,466.760 |
| western_europe | infrastructure | 535 | 0.000 | 212.600 | 13.896 | 2.000 | 23.501 | 7,434.210 |
| australasia | development | 65 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| central_africa | development | 80 | 0.007 | 9.950 | 1.060 | 0.485 | 1.628 | 84.762 |
| central_asia | development | 75 | 0.045 | 14.031 | 4.115 | 2.850 | 3.882 | 308.603 |
| east_africa | development | 127 | 0.000 | 11.230 | 1.635 | 0.920 | 2.062 | 207.595 |
| east_asia | development | 627 | 0.000 | 57.835 | 10.475 | 6.160 | 12.024 | 6,567.583 |
| eastern_europe | development | 459 | 0.000 | 31.703 | 5.644 | 3.495 | 5.834 | 2,590.564 |
| middle_east | development | 212 | 0.256 | 39.918 | 9.560 | 7.210 | 7.758 | 2,026.774 |
| north_africa | development | 72 | 0.000 | 34.904 | 6.843 | 4.848 | 6.790 | 492.698 |
| north_america | development | 602 | 0.000 | 26.477 | 1.464 | 0.035 | 3.672 | 881.461 |
| north_asia | development | 149 | 0.000 | 12.658 | 0.540 | 0.000 | 1.708 | 80.519 |
| north_atlantic_ocean_sub_continent | development | 1 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| pacific_islands | development | 85 | 0.000 | 5.764 | 0.457 | 0.002 | 1.057 | 38.887 |
| south_america | development | 183 | 0.000 | 33.054 | 2.043 | 0.158 | 4.681 | 373.934 |
| south_asia | development | 180 | 0.000 | 32.806 | 11.748 | 10.869 | 7.747 | 2,114.568 |
| south_atlantic_sub_continent | development | 1 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| south_east_asia | development | 191 | 0.015 | 17.585 | 1.726 | 0.648 | 2.720 | 329.748 |
| southern_africa | development | 61 | 0.000 | 1.262 | 0.148 | 0.070 | 0.243 | 9.042 |
| west_africa | development | 114 | 0.000 | 27.510 | 4.082 | 2.543 | 4.165 | 465.342 |
| western_europe | development | 535 | 0.000 | 65.764 | 24.596 | 25.677 | 15.158 | 13,158.854 |
| australasia | capacity | 65 | 7.000 | 861.000 | 314.615 | 307.000 | 162.612 | 20,450.000 |
| central_africa | capacity | 80 | 68.320 | 1,107.124 | 327.236 | 275.723 | 202.038 | 26,178.900 |
| central_asia | capacity | 75 | 40.428 | 621.789 | 234.187 | 202.936 | 141.197 | 17,564.021 |
| east_africa | capacity | 127 | 7.000 | 1,277.868 | 250.442 | 214.902 | 172.699 | 31,806.081 |
| east_asia | capacity | 627 | 14.001 | 2,179.180 | 246.714 | 178.946 | 235.287 | 154,689.440 |
| eastern_europe | capacity | 459 | 21.000 | 1,119.154 | 226.472 | 182.039 | 169.688 | 103,950.850 |
| middle_east | capacity | 212 | 48.690 | 745.496 | 232.061 | 214.772 | 104.219 | 49,197.000 |
| north_africa | capacity | 72 | 7.013 | 1,707.868 | 293.853 | 214.770 | 296.581 | 21,157.410 |
| north_america | capacity | 602 | 21.000 | 1,297.000 | 189.959 | 138.500 | 167.183 | 114,355.222 |
| north_asia | capacity | 149 | 21.000 | 463.413 | 104.896 | 74.000 | 83.287 | 15,629.467 |
| north_atlantic_ocean_sub_continent | capacity | 1 | 47.000 | 47.000 | 47.000 | 47.000 | 0.000 | 47.000 |
| pacific_islands | capacity | 85 | 7.000 | 673.118 | 109.795 | 53.000 | 144.757 | 9,332.551 |
| south_america | capacity | 183 | 28.000 | 830.763 | 237.489 | 203.046 | 158.044 | 43,460.567 |
| south_asia | capacity | 180 | 7.000 | 1,213.356 | 486.662 | 448.701 | 264.013 | 87,599.074 |
| south_atlantic_sub_continent | capacity | 1 | 7.000 | 7.000 | 7.000 | 7.000 | 0.000 | 7.000 |
| south_east_asia | capacity | 191 | 21.033 | 1,518.117 | 253.504 | 191.986 | 218.406 | 48,419.189 |
| southern_africa | capacity | 61 | 41.000 | 437.474 | 189.236 | 174.000 | 88.840 | 11,543.377 |
| west_africa | capacity | 114 | 24.015 | 703.125 | 225.032 | 210.064 | 125.267 | 25,653.630 |
| western_europe | capacity | 535 | 14.682 | 494.263 | 127.269 | 108.953 | 73.177 | 68,088.706 |
| australasia | fill | 65 | 0.000 | 0.084 | 0.015 | 0.012 | 0.013 | 0.964 |
| central_africa | fill | 80 | 0.034 | 1.068 | 0.317 | 0.266 | 0.239 | 25.328 |
| central_asia | fill | 75 | 0.030 | 0.825 | 0.205 | 0.133 | 0.181 | 15.363 |
| east_africa | fill | 127 | 0.000 | 1.475 | 0.433 | 0.299 | 0.340 | 54.942 |
| east_asia | fill | 627 | 0.000 | 5.023 | 0.715 | 0.522 | 0.623 | 448.212 |
| eastern_europe | fill | 459 | 0.015 | 1.829 | 0.337 | 0.238 | 0.300 | 154.896 |
| middle_east | fill | 212 | 0.051 | 2.257 | 0.408 | 0.292 | 0.368 | 86.452 |
| north_africa | fill | 72 | 0.000 | 1.353 | 0.548 | 0.511 | 0.328 | 39.451 |
| north_america | fill | 602 | 0.000 | 2.039 | 0.142 | 0.026 | 0.279 | 85.614 |
| north_asia | fill | 149 | 0.004 | 0.300 | 0.034 | 0.020 | 0.043 | 5.039 |
| north_atlantic_ocean_sub_continent | fill | 1 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| pacific_islands | fill | 85 | 0.000 | 1.142 | 0.211 | 0.118 | 0.261 | 17.940 |
| south_america | fill | 183 | 0.000 | 1.459 | 0.333 | 0.235 | 0.303 | 60.872 |
| south_asia | fill | 180 | 0.060 | 3.816 | 1.116 | 1.152 | 0.498 | 200.802 |
| south_atlantic_sub_continent | fill | 1 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| south_east_asia | fill | 191 | 0.017 | 2.361 | 0.448 | 0.249 | 0.474 | 85.560 |
| southern_africa | fill | 61 | 0.000 | 1.171 | 0.173 | 0.102 | 0.221 | 10.554 |
| west_africa | fill | 114 | 0.000 | 1.329 | 0.481 | 0.400 | 0.313 | 54.823 |
| western_europe | fill | 535 | 0.000 | 3.614 | 0.960 | 0.860 | 0.682 | 513.757 |
| australasia | population_growth_100y | 65 | 1.000 | 2.986 | 1.031 | 1.000 | 0.246 | 66.988 |
| central_africa | population_growth_100y | 80 | 0.821 | 1.000 | 0.993 | 1.000 | 0.028 | 79.469 |
| central_asia | population_growth_100y | 75 | 0.650 | 0.876 | 0.743 | 0.699 | 0.075 | 55.709 |
| east_africa | population_growth_100y | 127 | 0.645 | 2.986 | 0.900 | 0.930 | 0.298 | 114.278 |
| east_asia | population_growth_100y | 627 | 0.627 | 2.986 | 0.771 | 0.683 | 0.182 | 483.726 |
| eastern_europe | population_growth_100y | 459 | 0.628 | 1.000 | 0.716 | 0.685 | 0.076 | 328.454 |
| middle_east | population_growth_100y | 212 | 0.638 | 0.999 | 0.735 | 0.703 | 0.076 | 155.839 |
| north_africa | population_growth_100y | 72 | 0.626 | 2.986 | 0.889 | 0.857 | 0.373 | 63.980 |
| north_america | population_growth_100y | 602 | 0.818 | 2.986 | 0.985 | 1.000 | 0.093 | 593.150 |
| north_asia | population_growth_100y | 149 | 0.678 | 1.642 | 0.962 | 1.000 | 0.109 | 143.407 |
| north_atlantic_ocean_sub_continent | population_growth_100y | 1 | 2.986 | 2.986 | 2.986 | 2.986 | 0.000 | 2.986 |
| pacific_islands | population_growth_100y | 85 | 0.908 | 2.986 | 1.042 | 1.000 | 0.304 | 88.600 |
| south_america | population_growth_100y | 183 | 0.828 | 2.986 | 1.022 | 1.000 | 0.256 | 187.105 |
| south_asia | population_growth_100y | 180 | 0.644 | 1.000 | 0.703 | 0.679 | 0.071 | 126.511 |
| south_atlantic_sub_continent | population_growth_100y | 1 | 2.986 | 2.986 | 2.986 | 2.986 | 0.000 | 2.986 |
| south_east_asia | population_growth_100y | 191 | 0.631 | 1.000 | 0.810 | 0.812 | 0.105 | 154.628 |
| southern_africa | population_growth_100y | 61 | 0.861 | 1.000 | 0.988 | 1.000 | 0.034 | 60.245 |
| west_africa | population_growth_100y | 114 | 0.641 | 2.986 | 0.893 | 0.873 | 0.224 | 101.746 |
| western_europe | population_growth_100y | 535 | 0.619 | 2.986 | 0.698 | 0.672 | 0.159 | 373.607 |

## Province capacity rankings

### Highest global province capacities

| Rank | Province | Macro region | Population | Potential | Infrastructure | Development | Capacity | Fill |
|---:|---|---|---:|---:|---:|---:|---:|---:|
| 1 | suzhou_province | east_asia | 2,783.45 | 1,950.74 | 151.99 | 28.05 | 2,179.18 | 1.277× |
| 2 | gharbiyya_province | north_africa | 587.85 | 1,322.25 | 322.54 | 20.11 | 1,707.87 | 0.344× |
| 3 | yingtian_province | east_asia | 2,241.31 | 1,614.19 | 40.96 | 21.89 | 1,701.67 | 1.317× |
| 4 | jiaxing_province | east_asia | 1,946.46 | 1,487.09 | 38.92 | 25.36 | 1,575.18 | 1.236× |
| 5 | jinhua_province | east_asia | 1,757.32 | 1,506.08 | 18.00 | 22.39 | 1,569.29 | 1.120× |
| 6 | cirebon_province | south_east_asia | 660.27 | 1,477.14 | 31.15 | 4.36 | 1,518.12 | 0.435× |
| 7 | shaoxing_province | east_asia | 1,777.39 | 1,313.44 | 101.01 | 26.09 | 1,461.03 | 1.217× |
| 8 | buhayra_province | north_africa | 537.73 | 924.83 | 422.30 | 16.26 | 1,374.74 | 0.391× |

### Tracked provinces

| Rank | Province | Macro region | Population | Potential | Infrastructure | Development | Capacity | Fill |
|---:|---|---|---:|---:|---:|---:|---:|---:|
| 325 | umbindhamu_province | australasia | 3.29 | 478.64 | 0.00 | 0.00 | 483.00 | 0.007× |
| 723 | dadi_dadi_province | australasia | 5.05 | 325.76 | 0.00 | 0.00 | 329.00 | 0.015× |
| 3816 | motu_maha_province | australasia | 0.00 | 6.93 | 0.00 | 0.00 | 7.00 | 0.000× |
| 98 | kinhasa_province | central_africa | 300.12 | 724.44 | 12.00 | 1.85 | 740.09 | 0.406× |
| 1429 | kouilou_province | central_africa | 12.18 | 218.20 | 0.00 | 0.68 | 220.15 | 0.055× |
| 1732 | bomokandi_province | central_africa | 202.18 | 187.24 | 0.00 | 1.00 | 189.24 | 1.068× |
| 1473 | jizzakh_province | central_asia | 127.75 | 211.46 | 0.00 | 2.73 | 214.70 | 0.595× |
| 1504 | khaqmar_province | central_asia | 50.65 | 185.62 | 21.62 | 1.99 | 211.05 | 0.240× |
| 3633 | wakhan_province | central_asia | 1.79 | 38.93 | 0.00 | 8.92 | 40.43 | 0.044× |
| 1059 | equatoria_province | east_africa | 213.53 | 264.09 | 0.00 | 1.12 | 269.41 | 0.793× |
| 2573 | bale_province | east_africa | 69.00 | 108.61 | 2.00 | 0.49 | 114.04 | 0.605× |
| 3717 | erg_selima_province | east_africa | 4.68 | 21.39 | 9.81 | 0.10 | 31.81 | 0.147× |
| 1 | suzhou_province | east_asia | 2,783.45 | 1,950.74 | 151.99 | 28.05 | 2,179.18 | 1.277× |
| 1426 | shimousa_province | east_asia | 206.35 | 152.83 | 58.54 | 26.07 | 220.61 | 0.935× |
| 3427 | western_gobi_province | east_asia | 13.08 | 53.82 | 0.00 | 0.17 | 55.01 | 0.238× |
| 345 | majar_province | eastern_europe | 32.96 | 466.32 | 2.00 | 2.92 | 473.93 | 0.070× |
| 2897 | kozelsk_province | eastern_europe | 41.41 | 90.01 | 0.00 | 1.29 | 92.14 | 0.449× |
| 3776 | vorkuta_province | eastern_europe | 7.11 | 20.78 | 0.00 | 0.00 | 21.00 | 0.339× |
| 747 | gorgan_province | middle_east | 116.47 | 300.54 | 15.81 | 6.56 | 323.27 | 0.360× |
| 1814 | hawran_province | middle_east | 83.14 | 120.03 | 53.43 | 16.13 | 180.13 | 0.462× |
| 2039 | sudair_province | middle_east | 83.51 | 53.94 | 98.48 | 18.11 | 158.11 | 0.528× |
| 10 | cairo_province | north_africa | 1,141.22 | 963.62 | 281.29 | 21.19 | 1,285.29 | 0.888× |
| 418 | guzzula_province | north_africa | 98.77 | 299.49 | 137.02 | 1.97 | 440.28 | 0.224× |
| 2743 | tih_province | north_africa | 29.85 | 89.51 | 9.81 | 0.14 | 101.83 | 0.293× |
| 2596 | iowa_province | north_america | 3.44 | 110.15 | 0.00 | 0.20 | 112.02 | 0.031× |
| 3310 | south_ktunaxa_province | north_america | 1.91 | 63.53 | 0.00 | 0.00 | 65.00 | 0.029× |
| 3642 | malemiut_province | north_america | 1.05 | 39.11 | 0.00 | 0.00 | 40.00 | 0.026× |
| 1104 | bayanaul_province | north_asia | 7.59 | 194.85 | 62.30 | 5.24 | 261.01 | 0.029× |
| 3284 | central_omok_province | north_asia | 0.94 | 64.94 | 0.00 | 0.00 | 67.00 | 0.014× |
| 3514 | olyuben_province | north_asia | 1.10 | 48.50 | 0.00 | 0.00 | 49.00 | 0.022× |
| 202 | kanaky_province | pacific_islands | 33.84 | 560.62 | 0.00 | 0.09 | 567.07 | 0.060× |
| 2908 | kuki_airani_province | pacific_islands | 4.01 | 90.32 | 0.00 | 0.00 | 92.00 | 0.044× |
| 3691 | niue_province | pacific_islands | 0.35 | 34.46 | 0.00 | 0.00 | 35.00 | 0.010× |
| 2241 | tapuy_province | south_america | 18.23 | 137.12 | 0.00 | 0.04 | 140.01 | 0.130× |
| 2277 | yaghan_province | south_america | 3.80 | 136.44 | 0.00 | 0.00 | 137.00 | 0.028× |
| 2383 | rangkullmapu_province | south_america | 36.21 | 125.94 | 0.00 | 0.09 | 129.02 | 0.281× |
| 12 | kalahandi_garjat | south_asia | 716.79 | 1,163.38 | 30.00 | 6.87 | 1,213.36 | 0.591× |
| 156 | meghalaya_province | south_asia | 293.39 | 564.68 | 42.00 | 8.48 | 619.34 | 0.474× |
| 3818 | laccadive_province | south_asia | 0.92 | 6.93 | 0.00 | 0.00 | 7.00 | 0.131× |
| 128 | timor_province | south_east_asia | 96.85 | 665.45 | 2.00 | 0.93 | 670.67 | 0.144× |
| 2675 | htamanthi_province | south_east_asia | 79.31 | 101.23 | 2.00 | 1.39 | 106.24 | 0.747× |
| 2740 | tru_vien_province | south_east_asia | 12.10 | 101.26 | 0.00 | 0.01 | 102.00 | 0.119× |
| 1524 | xun_province | southern_africa | 22.03 | 206.62 | 0.00 | 0.01 | 209.01 | 0.105× |
| 2475 | upper_runde_province | southern_africa | 75.78 | 120.61 | 0.00 | 0.12 | 122.02 | 0.621× |
| 3628 | karas_province | southern_africa | 2.87 | 38.33 | 0.00 | 0.00 | 41.00 | 0.070× |
| 920 | kawar_province | west_africa | 85.09 | 238.21 | 49.05 | 0.32 | 290.20 | 0.293× |
| 2189 | baoule_province | west_africa | 117.91 | 140.17 | 0.00 | 1.76 | 143.32 | 0.823× |
| 2691 | mende_province | west_africa | 117.17 | 101.76 | 0.00 | 0.97 | 105.13 | 1.115× |
| 582 | zealand_province | western_europe | 161.78 | 317.91 | 43.61 | 14.18 | 371.25 | 0.436× |
| 2831 | slesvig_province | western_europe | 89.95 | 59.67 | 31.15 | 38.81 | 96.42 | 0.933× |
| 3051 | gardr_province | western_europe | 0.23 | 81.53 | 0.00 | 0.00 | 82.00 | 0.003× |

## Named start-location checks

| Location | HYDE region | Population | Capacity | Fill | Zero-dev potential | GAEZ zero-dev | HYDE zero-dev | Development | Irrigation |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| wuxian | east_asia | 530.3k | 422.2k | 1.26× | 404.1 | 76.9 | 0.0 | 34.0 | 0 |
| changshu | east_asia | 627.9k | 507.7k | 1.24× | 495.2 | 57.3 | 0.0 | 18.8 | 0 |
| chongde | east_asia | 451.7k | 353.8k | 1.28× | 342.5 | 39.5 | 0.0 | 25.3 | 0 |
| delhi | south_asia | 79.5k | 22.5k | 3.53× | 21.2 | 75.5 | 0.0 | 19.1 | 0 |
| bijnot | south_asia | 341.4k | 297.2k | 1.15× | 257.6 | 16.3 | 0.0 | 0.0 | 4 |
| cairo | north_africa | 529.0k | 422.0k | 1.25× | 365.1 | 4.7 | 0.0 | 14.0 | 4 |
| alexandria | north_africa | 227.6k | 174.8k | 1.30× | 75.9 | 29.9 | 0.0 | 10.8 | 5 |
| london | europe | 42.8k | 7.5k | 5.69× | 6.9 | 15.6 | 0.0 | 60.0 | 0 |
| stockholm | europe | 21.8k | 15.1k | 1.44× | 14.4 | 43.3 | 0.0 | 6.5 | 0 |
| fanxian | east_asia | 9.4k | 60.1k | 0.16× | 6.9 | 33.4 | 0.0 | 62.8 | 4 |

## Development and capacity settings

- Starting-population capacity floor: none (starting population is validation-only)
- Location potential: frozen shared physical-regime model from GAEZ, non-population HYDE, geometry, hydrology, and parsed starting-building features; starting population is excluded from the feature matrix and used only by the one-sided 115% calibration boundary
- Independent physical inputs: rainfed_crop_capacity_people_p50, livestock_capacity_people_p50, marine_capacity_people_p50, freshwater_capacity_people_p50, wild_capacity_people_p50, open_rainfed_capacity_people_p50, extensive_livestock_capacity_people_p50, retained_wild_capacity_people_p50
- Development capacity: no absolute term; +0.00125 relative per point
- Parsed inherent development change: -0.0001 local monthly development per current development point
- Infrastructure capacity per level: bund=9.49, field_drainage=6.23, irrigated_rice_paddies=9.49, irrigation_reservoirs=9.81, irrigation_systems=9.81, land_clearance=7.65, polders=6.23, pound_lock_canal_infrastructure=0, qanats=9.81, terraces=2
- HYDE development model: HYDE cropland / GAEZ `feasible_cultivated_fraction` through an exponential saturation curve at rate 1.5 toward 42 points; full pasture share +5; no population or regional-offset input

```text
U = HYDE cropland share / GAEZ manageable cropland
D = clamp(42 × (1 - exp(-1.5 × U)) + 5 × HYDE pasture share, 0, 80)
P0 = calibrated physical-regime potential from the configured artifact
I = sum(infrastructure building levels × configured flat capacity per level)
Capacity = (ceil(P0) + I) × (1 + 0.00125 × D +0)
```

- Location-potential totals: physical GAEZ 1.884b, selected 760.8m
- Starting capacity attribution: natural Location Potential 90.6%, Development 0.8%, Infrastructure 8.6%

| Development | Minimum | Median | Mean | P90 | Maximum |
|---|---:|---:|---:|---:|---:|
| Raw game start | -13.0 | 9.0 | 9.4 | 25.0 | 45.0 |
| Profile game start | 0.0 | 1.6 | 7.4 | 24.8 | 69.9 |
| Final | 1.2 | 2.7 | 7.8 | 23.1 | 62.8 |

## Irrigation placement

- Enabled: True
- HYDE evidence locations: 850
- Starting irrigation locations: 1,633
- Starting irrigation levels: 4,425
- River/lake or parsed-building-supported placements: 100.0%
- Levels backed by river size or parsed buildings: 99.9%
- Non-river/lake placements: 0
- Legal-cap violations: 0

## Capacity-pressure food settings

| Band | Peasant consumption modifier | Absolute monthly food |
|---|---:|---:|
| Abundant | -0.50 | 0 |
| Available | -0.32 | 0 |
| Overpopulation | +1.00 | 0 |

- Pop types exempt from negative location-rank growth: tribesmen
- Pop types exempt from food-storage population growth: tribesmen

## Capacity-pressure coverage

Population share reports how much of the world is actually receiving each band. The neutral gap is the intentional below-10%-fill, 10k-or-more population case.

| Years | Abundant pop | Available pop | Neutral-gap pop | Over-capacity pop | Abundant locations | Available locations | Neutral-gap locations | Over-capacity locations |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 2.2% | 35.9% | 0.7% | 61.2% | 5,872 | 9,779 | 169 | 5,109 |
| 25 | 2.4% | 38.8% | 0.7% | 58.1% | 5,983 | 10,021 | 171 | 4,754 |
| 100 | 3.5% | 57.7% | 1.0% | 37.8% | 6,545 | 10,854 | 178 | 3,352 |

## Location ranges by checkpoint

| Years | Population min | Population max | Capacity min | Capacity max | Fill min | Fill max | Development min | Development max | Over capacity |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 0.000 | 913.0 | 7.000 | 754.7 | 0.000× | 7.427× | 0.0 | 69.9 | 5,109 |
| 25 | 0.000 | 821.6 | 7.002 | 754.3 | 0.000× | 7.082× | 0.2 | 68.0 | 4,754 |
| 100 | 0.000 | 564.2 | 7.011 | 753.2 | 0.000× | 6.983× | 1.2 | 62.8 | 3,352 |

## Location sanity checks

| Check | Observed | Limit | Result |
|---|---:|---:|:---:|
| Finite population/capacity/development | 1 | 1 | PASS |
| Non-negative population and capacity | 1 | 1 | PASS |
| Maximum-infrastructure location coverage | 20,929 rows / 20,929 unique | 20,929 / 20,929 | PASS |
| Finite non-negative maximum infrastructure | 1 | 1 | PASS |
| Maximum-infrastructure P10/P50/P90 ordering | 1 | 1 | PASS |
| Maximum-infrastructure component summation | 1 | exact | PASS |
| Global development-100 maximum population capacity | 3.534b | <= 4.000b | PASS |
| Global start capacity/population | 2.151× | >= 1.000× | PASS |
| Start population living within local capacity | 38.8% | >= 0.0% | PASS |
| Worst scored HYDE-region start population within local capacity | 26.0% | >= 0.0% | PASS |
| Maximum established-location start capacity fill | 2.669× | <= 1.150× | FAIL |
| Minimum location capacity | 7.000 | >= 0.000 | PASS |
| Maximum location capacity | 754.7 | <= 20,000.0 | PASS |
| Maximum location population | 913.0 | <= 10,000.0 | PASS |
| Maximum capacity fill | 7.427× | <= 1.150× | FAIL |
| Maximum development | 69.88 | <= 80.00 | PASS |
| Starting development P90 | 24.83 | 15.00–25.00 | PASS |
| Locations at starting development ceiling | 0.00% | <= 0.50% | PASS |
| Natural Location Potential share of starting capacity | 90.6% | >= 60.0% | PASS |
| Development share of starting capacity | 0.8% | <= 20.0% | PASS |
| Ordinary starting-location maximum fill | 7.427× | <= 1.150× | FAIL |
| Named supercity province maximum fill | 0.000× | <= 1.150× | PASS |
| Global starting population capacity | 849.1m | < 1.20b | PASS |
| Positive location-potential spread | 100.000× | <= 100.000× | PASS |
| Maximum starting development capacity contribution | 8.73% | <= 10.00% | PASS |
| Optional global capacity modifier | 0.00% | >= -50.00% | PASS |
| Absolute free-land food bonuses | 0, 0 | 0, 0 | PASS |
| Exactly three tracked provinces per real macro-region | 17 macro-regions | 17 complete macro-regions | PASS |
| China and Lower Nile province capacity ranking | suzhou_province, cairo_province | all in global top 20 | PASS |
| Population-independent capacity inputs | location potential + infrastructure + development only | starting population excluded | PASS |
| Infrastructure TOML/blueprint/compiled parity | matched | exact | PASS |
| Global 25y stability | 0.931× | within 5.0% of start | FAIL |
| Global 100y stability | 0.734× | within 10.0% of start | FAIL |
| Global 100y population benchmark | 0.734× | 0.900×–1.100× | FAIL |
| Real macro-region 100y population range | 0.666×–1.000× | 0.800×–1.250× | FAIL |
| Global mean development change at 100y | 0.39 | <= 2.00 | PASS |
| Maximum HYDE-region mean development change at 100y | 1.51 | <= 3.00 | PASS |
| HYDE-region 25y stability range | 0.915×–1.000× | 0.800×–1.250× | PASS |
| HYDE-region 100y stability range | 0.679×–1.000× | 0.600×–1.500× | PASS |
| Irrigation locations with physical or parsed-building support | 100.0% | >= 85.0% | PASS |
| Irrigation levels supported by river size or parsed buildings | 99.9% | >= 50.0% | PASS |
| Irrigation legal-cap violations | 0 | <= 0 | PASS |
| Minimum established-location 25y growth | 0.883× | >= 0.800× | PASS |
| Maximum established-location 25y growth | 1.000× | <= 2.000× | PASS |
| Minimum established-location 100y growth | 0.607× | >= 0.500× | PASS |
| Maximum established-location 100y growth | 1.000× | <= 4.500× | PASS |

## Starting-capacity contradictions

### Highest starting capacity pressure

| Location | HYDE region | Game population | HYDE population signal | Capacity | Fill | GAEZ full | GAEZ zero-dev | HYDE zero-dev | Final zero-dev | HYDE cropland share | Development | Irrigation |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| albi | europe | 55.1k | 80.8k | 7.42 | 7.43× | 199.4 | 55.5 | 0.0 | 7.0 | 55.0% | 48.5 | 0 |
| quan_da_chau | southeast_asia | 51.8k | 28.3k | 7.00 | 7.39× | 168.3 | 80.6 | 0.0 | 6.9 | 0.0% | 0.0 | 0 |
| shangshui | east_asia | 54.8k | 88.5k | 7.45 | 7.35× | 88.9 | 37.1 | 0.0 | 6.9 | 23.6% | 51.4 | 0 |
| quwo | east_asia | 53.3k | 41.8k | 7.36 | 7.24× | 269.2 | 42.6 | 0.0 | 6.9 | 40.9% | 41.2 | 0 |
| huian | east_asia | 51.4k | 23.8k | 7.12 | 7.21× | 94.0 | 32.2 | 0.0 | 6.9 | 3.1% | 13.9 | 0 |
| bukcheong | east_asia | 50.3k | 29.9k | 7.01 | 7.17× | 487.9 | 102.7 | 0.0 | 6.9 | 0.9% | 1.4 | 0 |
| laoling | east_asia | 52.5k | 74.2k | 7.38 | 7.10× | 123.6 | 39.3 | 0.0 | 6.9 | 16.5% | 44.0 | 0 |
| oztoman | mesoamerica | 49.7k | 112.3k | 7.01 | 7.09× | 730.4 | 101.7 | 0.0 | 6.9 | 0.3% | 1.7 | 0 |

### Highest established-location starting capacity pressure

| Location | HYDE region | Game population | HYDE population signal | Capacity | Fill | GAEZ full | GAEZ zero-dev | HYDE zero-dev | Final zero-dev | HYDE cropland share | Development | Irrigation |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| kapasia | south_asia | 110.6k | 508.8k | 41.44 | 2.67× | 369.2 | 80.1 | 0.0 | 39.3 | 22.2% | 28.8 | 0 |
| parma | europe | 104.5k | 82.5k | 41.96 | 2.49× | 289.2 | 56.7 | 0.0 | 38.6 | 84.2% | 60.7 | 0 |
| kosi | south_asia | 100.7k | 537.6k | 40.96 | 2.46× | 614.1 | 91.6 | 0.0 | 39.6 | 17.3% | 19.3 | 0 |
| dasong | east_asia | 100.7k | 48.7k | 42.07 | 2.39× | 588.0 | 81.3 | 0.0 | 41.5 | 0.0% | 1.4 | 0 |
| seohara | south_asia | 103.4k | 291.4k | 43.66 | 2.37× | 942.1 | 106.0 | 0.0 | 42.6 | 10.7% | 12.2 | 0 |
| sambhal | south_asia | 102.3k | 262.8k | 43.23 | 2.37× | 1,193.6 | 114.6 | 0.0 | 42.6 | 0.8% | 4.2 | 0 |
| fatehabad | south_asia | 105.3k | 222.0k | 45.00 | 2.34× | 593.6 | 89.7 | 0.0 | 43.7 | 18.2% | 18.2 | 0 |
| treviso | europe | 110.4k | 148.1k | 47.96 | 2.30× | 186.8 | 46.9 | 0.0 | 44.2 | 65.1% | 52.6 | 0 |

### Largest independent capacities in locations below 10k population

| Location | HYDE region | Game population | HYDE population signal | Capacity | Fill | GAEZ full | GAEZ zero-dev | HYDE zero-dev | Final zero-dev | HYDE cropland share | Development | Irrigation |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| jangyeon | east_asia | 9.8k | 24.3k | 702.59 | 0.01× | 287.4 | 51.3 | 0.0 | 692.8 | 7.0% | 8.7 | 0 |
| nauhtlan | mesoamerica | 8.8k | 18.9k | 697.17 | 0.01× | 292.2 | 49.5 | 0.0 | 692.8 | 4.4% | 4.8 | 0 |
| volkona | europe | 5.6k | 7.9k | 696.40 | 0.01× | 291.8 | 61.8 | 0.0 | 692.8 | 3.5% | 3.9 | 0 |
| trengganu | southeast_asia | 6.2k | 4.9k | 693.24 | 0.01× | 302.2 | 78.3 | 0.0 | 692.8 | 0.2% | 0.3 | 0 |
| manitoulin | north_america | 850 | 0 | 693.00 | 0.00× | 296.5 | 75.3 | 0.0 | 692.8 | 0.0% | 0.0 | 0 |
| carmacks | north_america | 159 | 6 | 693.00 | 0.00× | 300.9 | 97.5 | 0.0 | 692.8 | 0.0% | 0.0 | 0 |
| pictou | unassigned | 212 | 246 | 693.00 | 0.00× | 298.1 | 59.5 | 0.0 | 692.8 | 0.0% | 0.0 | 0 |
| accomac | north_america | 3.8k | 1.4k | 693.00 | 0.01× | 297.2 | 58.9 | 0.0 | 692.8 | 0.0% | 0.0 | 0 |


## Location extremes

### Largest populations at 100 years

| Location | HYDE region | Population | Capacity | Fill | Growth | Development | Irrigation |
|---|---|---:|---:|---:|---:|---:|---:|
| jiaxing | east_asia | 564.17 | 753.17 | 0.75× | 0.62× | 23.2 | 3 |
| nanhui | east_asia | 410.57 | 484.25 | 0.85× | 0.68× | 17.2 | 3 |
| haiyan | east_asia | 397.45 | 465.61 | 0.85× | 0.68× | 24.1 | 0 |
| huating | east_asia | 392.93 | 507.10 | 0.77× | 0.62× | 17.3 | 4 |
| mugamba | east_africa | 388.17 | 338.42 | 1.15× | 1.00× | 8.2 | 0 |
| changshu | east_asia | 387.33 | 507.05 | 0.76× | 0.62× | 17.8 | 0 |
| kunshan | east_asia | 360.38 | 411.18 | 0.88× | 0.68× | 28.4 | 3 |
| nduga | east_africa | 328.76 | 247.24 | 1.33× | 1.00× | 14.0 | 0 |

### Highest capacity fill at 100 years

| Location | HYDE region | Population | Capacity | Fill | Growth | Development | Irrigation |
|---|---|---:|---:|---:|---:|---:|---:|
| youyang | east_asia | 49.02 | 7.02 | 6.98× | 1.00× | 2.4 | 0 |
| el_obeid | north_africa | 47.57 | 7.04 | 6.76× | 1.00× | 4.5 | 0 |
| shuihui | east_asia | 47.35 | 7.02 | 6.74× | 1.00× | 2.7 | 0 |
| oztoman | mesoamerica | 44.58 | 7.02 | 6.35× | 0.90× | 2.7 | 0 |
| quan_da_chau | southeast_asia | 44.11 | 7.01 | 6.29× | 0.85× | 1.2 | 0 |
| bukcheong | east_asia | 42.47 | 7.02 | 6.05× | 0.84× | 2.5 | 0 |
| jianghua | east_asia | 40.88 | 7.03 | 5.82× | 1.00× | 3.4 | 0 |
| ondo | west_africa | 40.78 | 7.05 | 5.78× | 0.94× | 6.1 | 0 |

### Fastest growth at 100 years

| Location | HYDE region | Population | Capacity | Fill | Growth | Development | Irrigation |
|---|---|---:|---:|---:|---:|---:|---:|
| reunion | europe | 0.00 | 131.57 | 0.00× | 2.99× | 3.5 | 0 |
| sandnes | north_america | 0.00 | 7.03 | 0.00× | 2.99× | 3.5 | 0 |
| santo_antao | unassigned | 0.00 | 7.03 | 0.00× | 2.99× | 3.5 | 0 |
| gronnedal | north_america | 0.00 | 7.03 | 0.00× | 2.99× | 3.5 | 0 |
| anaco | tropical_south_america | 0.00 | 13.06 | 0.00× | 2.99× | 3.8 | 0 |
| ponta_delgada | europe | 0.00 | 7.03 | 0.00× | 2.99× | 3.5 | 0 |
| tupirvialuit | north_america | 0.00 | 7.03 | 0.00× | 2.99× | 3.5 | 0 |
| saipuru | andes | 0.00 | 7.03 | 0.00× | 2.99× | 3.7 | 0 |

### Largest capacities at 100 years

| Location | HYDE region | Population | Capacity | Fill | Growth | Development | Irrigation |
|---|---|---:|---:|---:|---:|---:|---:|
| jiaxing | east_asia | 564.17 | 753.17 | 0.75× | 0.62× | 23.2 | 3 |
| asadabad_kunar | south_asia | 11.41 | 714.86 | 0.02× | 0.68× | 15.8 | 0 |
| jangyeon | east_asia | 6.66 | 702.78 | 0.01× | 0.68× | 9.0 | 0 |
| nauhtlan | mesoamerica | 7.84 | 697.75 | 0.01× | 0.90× | 5.5 | 0 |
| volkona | europe | 3.82 | 697.10 | 0.01× | 0.69× | 4.7 | 0 |
| wangung | southeast_asia | 49.63 | 695.66 | 0.07× | 0.68× | 3.1 | 0 |
| qabala | near_east | 13.58 | 695.24 | 0.02× | 0.83× | 2.6 | 0 |
| trengganu | southeast_asia | 4.53 | 694.31 | 0.01× | 0.73× | 1.5 | 0 |

### Lowest positive capacities at 100 years

| Location | HYDE region | Population | Capacity | Fill | Growth | Development | Irrigation |
|---|---|---:|---:|---:|---:|---:|---:|
| ehwae | north_america | 3.53 | 7.01 | 0.50× | 1.00× | 1.2 | 0 |
| umpqua | north_america | 0.70 | 7.01 | 0.10× | 1.00× | 1.2 | 0 |
| voikar | europe | 0.67 | 7.01 | 0.10× | 1.00× | 1.2 | 0 |
| kittaning | north_america | 0.98 | 7.01 | 0.14× | 1.00× | 1.2 | 0 |
| kengdey | europe | 0.16 | 7.01 | 0.02× | 1.00× | 1.2 | 0 |
| olekma | europe | 0.16 | 7.01 | 0.02× | 1.00× | 1.2 | 0 |
| tignish | north_america | 0.21 | 7.01 | 0.03× | 1.00× | 1.2 | 0 |
| tuyandina | europe | 0.16 | 7.01 | 0.02× | 1.00× | 1.2 | 0 |


## Iteration notes

Edit the profile TOML and rerun the same command. This report is replaced in place; no monthly history files are produced.
