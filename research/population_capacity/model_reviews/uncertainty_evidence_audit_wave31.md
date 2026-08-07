# Wave 31: independent uncertainty evidence audit

This wave evaluates whether the acquired historical and modern sources can
support p10/p50/p90 capacity propagation without becoming 1337 population or
absolute-yield targets.

## Measured evidence

- **BAHS English manorial yields:** 4 in-period crop series (barley, oats, rye,
  wheat), 1211–1349, with p10/p50/p90 yield-per-seed tails. They map to one
  EU5 location (`taunton`, about 0.005% of locations), so they are a local,
  one-sided harvest-risk validation only.
- **FAOSTAT:** 233,666 resolved modern relative-risk rows across 18 crop
  families and 19,054 mapped locations (91.04%). Country-level modern series
  test relative tails only; they cannot calibrate 1337 absolute capacity.
- **GDHY:** 864 modern annual super-region rows for maize, rice, soybean, and
  wheat (1981–2016). Area coverage is incomplete (median valid fraction
  0.156), so this supports grouped modern risk validation only.
- **ISIMIP2a:** 396 rice rows (1980–2012), paired rain-fed/full-irrigation
  modes. It supports modern model spread and water-mode correlation, not
  historical yield labels.
- **Tree-ring drought atlases:** NADA, SADA, MADA, and OWDA provide climate
  p10/p50/p90 proxies in the 1100–1500 window, but location coverage is only
  2.8%–26.6% by atlas. They test spatial climate covariance, not crop yield.
- **GAEZ parameter evidence:** 168 official biomass LUT variants across 23
  crops plus the crop-specific Appendix 4.2 water bridge (40/46 crop-mode
  entries) provide physical parameter spread. They do not provide empirical
  cross-parameter covariance or exact PyAEZ outputs.

## Gate decision

The source set supports partial tail, climate-correlation, and physical
parameter diagnostics, but no source closes correlated crop/management/
parameter uncertainty for every EU5 location in 1100–1500. Modern sources
remain validation-only; BAHS is local and one-sided. Therefore:

```text
p10_p50_p90_capacity_propagation_ready = false
independent_risk_validation_complete = false
physical_uncertainty_gate_eligible = false
training_target_added = false
gate_update = none
```

No acceptance manifest was loosened. The complete machine-readable audit is
`research/population_capacity/model_reviews/uncertainty_evidence_audit_wave31.json`
with audit SHA-256
`4e34086d278cdb54b069694ae27ab434d5f131c94bc3e68decd8cfc272756006`.

