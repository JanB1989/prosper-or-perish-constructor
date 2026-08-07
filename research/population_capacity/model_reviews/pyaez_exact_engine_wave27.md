# PyAEZ exact-engine closure review (wave27)

## Result

The official PyAEZ v2.2 source executes successfully, but it cannot currently
produce an exact EU5 challenger matrix. The pinned checkout is
`b314640710a3ec398482b0065f4f26f45494eefa`. Its `data_input` tree contains 23
files, all hash-recorded by the wave27 audit. The crop parameter bundle is a
Laos tutorial containing maize, sugarcane, and `maiz49`; sugarcane is not one of
the registered EU5 crops. No official PyAEZ parameter/constraint bundle exists
for the other 22 registered crops.

The source-backed runtime smoke uses the official maize low-input workbook and
climate arrays, and returns finite non-negative paired yields:

```text
rain-fed:   6092.401208765886 kg DM/ha
irrigated:  6377.0          kg DM/ha
```

This is a runtime proof only. It is explicitly outside the EU5 footprint and
does not enter labels or training.

## EU5 coverage

The matrix audit checks every `location_tag × crop × water_mode` key against
the current accepted label artifact:

```text
required exact EU5 rows: 962,734
exact PyAEZ EU5 rows:    0
GAEZ fallback rows:      962,734
duplicate keys:          0
```

Maize is classified as `official_parameter_example_only_not_EU5_mapped`.
Every other registered crop is classified as
`missing_official_pyaez_crop_parameters`. Rain-fed and irrigated rows remain
unresolved for all 23 crops. The existing GAEZ v5 rows remain
`source_engine=GAEZ v5`, `resolution_method=physical_fallback`; none are
relabelled as PyAEZ.

## Technical blocker

PyAEZ requires crop-specific cycle/biomass, crop-water, agroclimatic, soil, and
terrain inputs. The official repository only supplies those files for its
maize/sugarcane tutorial. GAEZ v5 Appendix 4-6/4-2 values are a separate model
and cannot be silently substituted for PyAEZ parameters. Doing so would turn a
physical fallback or adaptation into a falsely labelled exact engine result.

The isolated `uv` project environment also cannot build the PyAEZ GDAL
dependency because `gdal-config` and native headers are absent. The source
checkout itself runs with the cached PyAEZ dependencies (`numba`, `openpyxl`)
and a narrow GDAL import shim for the in-memory smoke; this does not solve the
missing crop/input contract.

## Gate

`exact_engine_ready=false` and `training_challenger_eligible=false` in
`pyaez_exact_engine_audit_wave27.json`. The challenger may only be promoted
after every registered crop and both water modes have source-backed, same-
footprint EU5 inputs and one classified row per matrix key. No regional or
global crop-parameter fill is permitted.
