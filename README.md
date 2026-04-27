# Prosper or Perish Constructor

Concrete orchestration workspace for the Prosper or Perish population growth and food rework mod.

This repo owns a local working copy of the mod under `mod/Prosper or Perish (Population Growth & Food Rework)`
and uses the shared EU5 parser/orchestrator tooling to inspect and analyze it without writing back to the live
Paradox mod folder.

## Local workflow

```powershell
uv sync --dev
uv run eu5-orchestrator inspect --project constructor.toml
.\scripts\analyze-constructor.ps1
```

The analyze script exports parser fact tables and the interactive goods-flow explorer to:

```text
artifacts/parser/goods_flow_explorer.html
```

There is intentionally no deploy target configured yet. Keep live-game writes disabled until a separate,
explicit target is chosen.
