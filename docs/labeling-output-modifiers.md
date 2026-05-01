# Labeling Output Modifiers

This document describes how labeled raw-good suitability becomes EU5 output
modifiers in the constructor build. The executable settings live in
`labeling_output_modifiers.yaml`.

## Current Pipeline

The constructor's `[labeling]` step calls the labeling pipeline's
`mod_injector` package through `eu5-mod-orchestrator`. The orchestrator reads
`constructor.toml`, loads `labeling_output_modifiers.yaml`, and then overrides
the target mod path, modifier prefix, generated label, and write mode from the
constructor project config.

For each enabled good, `mod_injector` rebuilds OpenSkill ratings from that
good's `*_ranking_runs.parquet` file. The exported MMR value is the OpenSkill
ordinal score, which is derived from `mu` and `sigma` and is used as the source
score for suitability.

The score is broadcast back to baseline locations by `feature_hash`. The hash is
computed from the used `location_features` in the good's evaluator config. Rows
with the same canonical feature combination receive the same MMR. Dealbreaker
rows are kept in the export path and can receive a fixed configured
productivity.

After broadcast, MMR is scaled into a `productivity` value in `[-1, 1]`. The
scaled value is then rounded and written as a EU5 static modifier entry:

```txt
local_<good>_output_modifier = <productivity>
```

The writer groups all exported goods for the same location into one generated
per-location static modifier, then applies those modifiers at game start through
a generated on-action file.

## Config File

`labeling_output_modifiers.yaml` is intentionally local to this constructor repo
so output-modifier behavior can be changed without editing the labeling pipeline
repository.

Important fields:

- `baseline_parquet`: baseline location table used for feature hashing and raw
  material coverage checks.
- `goods_evaluator_root`: folder containing `GoodsEvaluator/<good>/config.yaml`
  directories. The constructor currently uses an explicit `goods:` list; this
  root remains useful if the list is intentionally removed later to restore
  auto-discovery.
- `defaults.mmr_mean_center`: subtracts the mean MMR before export/debug output.
  Current scale modes are translation-equivariant, so this does not change the
  final `productivity` value for the existing modes.
- `defaults.scale`: default MMR-to-productivity scale mode for every good unless
  a per-good override is configured.
- `defaults.scale_args`: arguments passed to the selected scale mode.
- `defaults.scale_args.output_min`: optional lower bound for scaled non-null
  MMR output. When omitted, the labeler keeps the historical `-1` lower bound.
- `defaults.scale_args.output_max`: optional upper bound for scaled non-null
  MMR output. When omitted, the labeler keeps the historical `1` upper bound.
- `defaults.null_productivity`: optional constructor-level replacement for
  dealbreaker/fallback productivity rows that previously used each evaluator's
  `dealbreaker_productivity`, usually `-1.0`.
- `defaults.round_decimals`: decimal places used when writing EU5 modifier
  values.
- `defaults.drop_zero_productivity`: drops rounded `0.00` entries from generated
  static modifiers.

## Scale Modes

Supported scale modes are implemented by the labeling pipeline:

- `rank_uniform`: ranks non-null MMR values and spreads them uniformly over
  `[-1, 1]`. This is the current default.
- `min_max_linear`: maps the observed minimum MMR to `-1` and maximum MMR to
  `1`.
- `linear_percentile`: maps configurable percentile bounds to `[-1, 1]` and
  clips values outside that range. Useful arguments are `low_q`, `high_q`, and
  `apply_nudge`.
- `tanh_iqr`: maps distance from the median through a tanh curve using the IQR
  as spread. Useful argument: `k`.

## Per-Good Overrides

The constructor config uses an explicit `goods:` list so the exported good set is
stable and each good can be tuned independently. Each item includes
`trade_good`, `evaluator_config`, and `enabled`; optional per-good `scale` /
`scale_args` values override the shared defaults.

Example:

```yaml
goods:
  - trade_good: fish
    evaluator_config: "../ProsperOrPerishLabelingPipeline/GoodsEvaluator/fish/config.yaml"
    enabled: true
    scale: linear_percentile
    scale_args:
      low_q: 0.05
      high_q: 0.95
```

## Current Defaults

The current test baseline is:

- `scale: rank_uniform`
- `mmr_mean_center: true`
- `scale_args.output_min: -0.6`
- `scale_args.output_max: 0.4`
- `null_productivity: -0.6`
- `round_decimals: 2`
- `drop_zero_productivity: true`
- explicit `goods:` list covering the current labeler evaluator goods
