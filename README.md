# Prosper or Perish Constructor

Concrete EU5 mod workspace for the Prosper or Perish population growth and food rework mod.

This repo is the example project that wires together the reusable parser, building pipeline,
and orchestrator packages. It keeps a local mod copy under
`mod/Prosper or Perish (Population Growth & Food Rework)` and writes generated analysis output to
ignored artifact folders.

## Example Graphs

Curated example graph snapshots are published from the orchestrator docs site:

- [Goods Flow Explorer](https://janb1989.github.io/eu5-mod-orchestrator/examples/goods_flow_explorer.html)
- [Savegame Market Explorer](https://janb1989.github.io/eu5-mod-orchestrator/examples/savegame_explorer.html)

Generated local graph outputs stay ignored under `graphs/`; the orchestrator `docs/examples/`
files are the public demo snapshots.

## Setup

```powershell
uv sync --dev
uv run eu5-orchestrator inspect --project constructor.toml
```

Check `constructor.load_order.toml` before analyzing another machine or mod:

- `[paths].vanilla_root` must point at the EU5 install folder.
- `[[mods]].root` must point at the local mod copy for the project.
- `[profiles].constructor` controls the load order used by the parser.

Machine-local deploy targets stay in ignored `constructor.local.toml`. Example:

```toml
[deploy]
target = "C:/Users/<you>/Documents/Paradox Interactive/Europa Universalis V/mod/Prosper or Perish (Population Growth & Food Rework)"
```

## Static Mod Analysis

```powershell
uv run eu5-orchestrator analyze --project constructor.toml
.\scripts\analyze-constructor.ps1
```

This exports static parser tables to:

```text
artifacts/data/buildings/
```

and writes the goods-flow graph to:

```text
graphs/goods_flow_explorer.html
```

## Savegame Analysis

```powershell
uv run eu5-orchestrator savegame --project constructor.toml
.\scripts\savegame-constructor.ps1
```

By default this uses the newest `.eu5` save under the EU5 documents save folder. Pass `--save` or
`--save-dir` to choose a different save.

Savegame parquet tables are written to:

```text
artifacts/data/savegame/
```

and the market/savegame graph is written to:

```text
graphs/savegame_explorer.html
```

## Building Blueprints

Accepted building blueprints live under `blueprints/accepted/buildings` and are enabled by
`blueprints/buildings.manifest.yml`.

```powershell
uv run eu5-orchestrator blueprint list --project constructor.toml
uv run eu5-orchestrator blueprint parity --project constructor.toml
uv run eu5-orchestrator build --project constructor.toml --overwrite
```

The generated filename prefix is configured as `building_outputs.prefix` in `constructor.toml`.

## Deploying

After configuring `constructor.local.toml`, deploy the local mod copy into the live Paradox mod
folder:

```powershell
uv run eu5-orchestrator deploy --project constructor.toml --clean
.\scripts\sync-constructor.ps1
```

Generated parquet, HTML graphs, reports, and generated blueprints are reproducible and ignored by
Git. Commit reusable config, accepted blueprints, scripts, docs, and tests.

## Reusing This Structure

For a new mod workspace, use the orchestrator scaffold command:

```powershell
uv run eu5-orchestrator init C:/Development/my-eu5-mod --name "My EU5 Mod" --mod-name "My EU5 Mod" --vanilla-root "C:/Games/steamapps/common/Europa Universalis V"
```

That creates the same baseline folder layout, TOML config, scripts, and README pattern used here.
