# Round 52: original Nile basin evidence and source arithmetic

Status: source audit completed; geography remains unaccepted. Round49 remains
the working candidate. No capacity, consumption, development or infrastructure
assignment changes in this round.

The [1889 Willcocks edition](https://archive.org/details/egyptianirrigati00will)
is now cached, including the Upper Egypt foldout and original tables. This
supersedes round51's statement that the scan had not been obtained. The source
contract pins the downloaded files by SHA256 and retains original units and
printed values alongside conversions.

## What the source establishes

The author uses Egyptian acres, or feddans, with 4,200 square metres in the
engineering calculations. Using international acres would understate these
areas by 3.646%. The appendix's more precise 4,200.833333 square metres changes
the result by only 0.01984%; this precision distinction is recorded explicitly.

Table XVIII (printed p71, scan leaf126) separates seasonal basins, high Nile
berms, and summer-irrigation tracts. Its basin bank totals and province totals
reconcile at 1,462,414 feddans, or 6,142.1388km². High berms add 1,222.2km².
These are dated categories, not 1337 assignments. The nineteenth-century summer
tracts must not be added to medieval support by default.

The printed table contains an internal discrepancy: Assiut's total is
2,000 feddans below its components, and the summer-tract grand total is
2,000 below the province entries. The difference is 8.4km². Both discrepancies
are preserved; no digit is silently changed to make the source reconcile.
The basin totals themselves are unaffected.

Table XVI (p57, leaf112) identifies section A's Banban basin at 1,374 feddans
(5.7708km²), and section B's six basins around Edfu/Esna at 33,318 feddans
(139.9356km²). The individual section B entries reconcile. These support an
explicit southern-valley spatial check; they exclude other banks, berms and
islands and therefore are not whole game-location field totals.

## Consequences for calibration

Plate XII and its section explanation (p56) distinguish the basin chains and
later summer-irrigation areas. Sections are grouped by discharge, not simply
by their feeder canal or modern administrative boundary. The next Nile
crosswalk must respect those distinctions instead of assigning the same regional
total through alternative raster weights and choosing by survival.

The observation is 552 years later than the game start. It cannot replace the
rough1315 estimate, establish a medieval capacity ceiling, or justify importing
later irrigation systems. Borsch also cites Willcocks, so these are related
hydraulic evidence, not an independent source holdout. Population and food
deficits never enter the source audit.

Urban food remains a separate account: cookeries and victuals supply urban
demand with staffing and recipe assumptions visible. Accommodation does not
create food or agricultural opportunity, and an urban supply deficit is not a
reason to enlarge cultivated land. Existing observed food contributions remain
in the working candidate.

## Reproduction

```sh
uv run python research/population_capacity/audit_willcocks_basins.py --output artifacts/data/population_capacity/repair_round_52/willcocks_source_audit
uv run ppc test -q
```

The source audit verifies hashes, original-unit basin arithmetic, conversions
and the exact preserved discrepancies. Its manifest reports the printed-table
arithmetic as unresolved rather than labeling all source accounts passed.
The output includes `dated_province_areas.csv` and `manifest.json`.

Full-suite verification: **878 passed, 1 skipped in620.86seconds**. A focused
`uv run ppc test tests/test_setup_building_corrections.py -q -rs` confirms the
skip at line221: the local error log has no setup-building errors. That focused
check reports5passed/1skipped.
No new simulation or model-acceptance claim follows from a source-only audit.
The historical spatial crosswalk, remaining mandatory behavioral/source gates
and final evidence package still require completion. No export or live deploy.
