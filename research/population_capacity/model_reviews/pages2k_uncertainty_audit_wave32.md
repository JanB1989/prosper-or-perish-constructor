# Wave32: PAGES2k spatial climate-risk evidence

## Acquisition and provenance

The official NOAA/NCEI PAGES2k Database S1 metadata workbook (11 April 2013
release) was acquired from
`https://www.ncei.noaa.gov/pub/data/paleo/pages2k/DatabaseS1-All-proxy-records.xlsx`.
The source is the PAGES2k Consortium proxy database and is documented alongside
[PAGES2k (Scientific Data 4, 170088, DOI 10.1038/sdata.2017.88)](https://doi.org/10.1038/sdata.2017.88)
and is listed in the [NOAA/NCEI archive](https://www.ncei.noaa.gov/pub/data/paleo/pages2k/).

The local source SHA-256 is
`201edbf4d7470804d87f376677d648b0de50bc6f8d41699e5d7379b19a60fbe5`.
The deterministic parser and audit are in
`src/prosper_or_perish_population_capacity/pages2k_uncertainty.py` and
`scripts/audit_pages2k_uncertainty_wave32.py`.

## What the source actually provides

The workbook contains 522 non-separator proxy records (the spreadsheet also
contains eight visual separator rows). At year 1337, 291 records have
published temporal bounds that include the year:

| PAGES2k region | records active at 1337 |
|---|---:|
| North America | 137 |
| Asia | 68 |
| Arctic | 53 |
| Europe | 10 |
| Africa | 9 |
| Antarctica | 7 |
| South America | 4 |
| Australasia | 3 |

Across the full 1100–1500 window, 204 records span both endpoints. The
audited metadata retain archive type, proxy measurement, location coordinates,
temporal bounds, and resolution; documented coordinate ranges are retained as
range-precision diagnostics rather than silently collapsed into exact EU5
locations.

## Modeling disposition

This closes an independent, globally distributed climate-proxy receipt for
spatial/correlated uncertainty diagnostics only. PAGES2k is not a crop-yield,
food-availability, cultivated-area, or population series. Proxy values are not
absolute yields and do not establish 1337 Malthusian saturation. The audit
therefore sets:

```text
absolute_1337_yield       = false
absolute_1337_population  = false
training_target_allowed   = false
training_feature_allowed  = false
mapping_status             = not_mapped_to_eu5_in_this_audit
```

No banana, cassava, taro, or other crop-specific risk labels are inferred from
the climate-only source. PAGES2k can be used later to test whether propagated
climate scenarios have plausible spatial covariance, but it does not close the
remaining absolute 1337 crop-risk, crop-parameter covariance, or exact EU5
label gaps. The Wave31 uncertainty gate is therefore unchanged.
