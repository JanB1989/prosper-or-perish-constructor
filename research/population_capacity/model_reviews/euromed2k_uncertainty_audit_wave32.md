# Wave32: EuroMed2k spatial climate uncertainty

## Acquisition and provenance

The official NOAA/NCEI EuroMed2k reconstruction was acquired as
`BHM_Eu2k2_Recon.nc` from
`https://www.ncei.noaa.gov/pub/data/paleo/pages2k/EuroMed2k/BHM_Eu2k2_Recon.nc`.
The accompanying metadata identify it as the annually resolved 5° European
June–August temperature reconstruction back to 755 CE. The primary publication
is Luterbacher et al., *European summer temperatures since Roman times*,
Environmental Research Letters 11 (2016), DOI
[10.1088/1748-9326/11/2/024001](https://doi.org/10.1088/1748-9326/11/2/024001); the
official [NOAA/NCEI EuroMed2k archive](https://www.ncei.noaa.gov/pub/data/paleo/pages2k/EuroMed2k/)
provides the file and readme.

Local source SHA-256:
`1f5f64f7d2aaca5e0a2effb042071701feb8a4c6ef35b8f6ebab0dd7de2d06fd`.
Audit implementation:
`src/prosper_or_perish_population_capacity/euromed2k_uncertainty.py` and
`scripts/audit_euromed2k_uncertainty_wave32.py`.

## Verified coverage

The file contains 70 grid cells (10 longitudes × 7 latitudes), annual values
from 755–2003, and `TT`, `Tlow25`, and `Tup25` variables. The Wave32 audit
finds:

| quantity | result |
|---|---:|
| years in 1100–1500 | 401 |
| 1337 present | yes |
| valid grid cells at 1337 | 61 / 70 |
| cells valid for every year 1100–1500 | 0 (missing years/cells are retained, not filled) |
| median 1337 95% quantile width | 2.621 K |

The nine missing 1337 cells and incomplete cell histories remain explicit
coverage limits. No interpolation or EU5 mapping is performed by this audit.

## Modeling disposition

EuroMed2k is a climate reconstruction, not a crop-yield, food-availability,
cultivated-area, or population series. Its ensemble quantiles can validate the
spatial covariance and uncertainty width of European climate scenarios, but
they cannot establish 1337 Malthusian saturation or absolute capacity. The
audit therefore sets:

```text
absolute_1337_yield       = false
absolute_1337_population  = false
training_target_allowed   = false
training_feature_allowed  = false
mapping_status             = not_mapped_to_eu5_in_this_audit
```

This source closes a real European climate-uncertainty receipt, not the global
crop-risk/parameter-covariance gap. The Wave31 physical-uncertainty gate is
unchanged, and no crop-specific values (including banana, cassava, or taro)
are inferred.

