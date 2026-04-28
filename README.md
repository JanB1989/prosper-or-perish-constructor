# Prosper or Perish Constructor

Concrete orchestration workspace for the Prosper or Perish population growth and food rework mod.

This repo owns a local working copy of the mod under `mod/Prosper or Perish (Population Growth & Food Rework)`
and uses the shared EU5 parser/orchestrator tooling to inspect and analyze it without writing back to the live
Paradox mod folder.

## Local workflow

```powershell
uv sync --dev
uv run eu5-orchestrator inspect --project constructor.toml
uv run eu5-orchestrator blueprint list --project constructor.toml
uv run eu5-orchestrator blueprint parity --project constructor.toml
.\scripts\analyze-constructor.ps1
.\scripts\sync-constructor.ps1
```

The sync script builds accepted blueprints into the local mod copy, deploys that full mod copy to the configured
`[deploy].target`, then exports parser fact tables and the interactive goods-flow explorer to:

```text
artifacts/parser/goods_flow_explorer.html
```

No deploy target is committed to the repo. Keep live-game writes in an ignored `constructor.local.toml`, for example:

```toml
[deploy]
target = "C:/Users/Anwender/Documents/Paradox Interactive/Europa Universalis V/mod/Prosper or Perish (Population Growth & Food Rework)"
```

## Building blueprints

Accepted building blueprints live under `blueprints/accepted/buildings` and are enabled by
`blueprints/buildings.manifest.yml`. These blueprints are the active source for the mod's generated
`zz_constructor_*` building, production method, price, advancement, localization, and icon files.
The generated filename prefix is configured as `building_outputs.prefix` in `constructor.toml`.
