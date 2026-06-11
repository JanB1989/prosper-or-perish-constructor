---
name: prosper-or-perish-workflows
description: Use for Prosper or Perish Constructor repo workflows, including setup, tests, parser inspection, static analysis, savegame export, docs publishing, blueprint list/parity/evaluate/tag/good/build, and guarded live sync/deploy commands.
---

# Prosper Or Perish Workflows

Use the repo command surface before reaching for raw commands:

```bash
uv run ppc --help
```

Resolve the repository dynamically instead of hardcoding a user's checkout path:

```bash
repo="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
test -f "$repo/constructor.toml"
cd "$repo"
```

When running from another folder, pass the repo explicitly:

```bash
repo=/path/to/ProsperOrPerishConstructor
uv run --project "$repo" ppc --repo "$repo" --help
```

Do not run project tooling from the old Windows-mounted checkout. Treat that
checkout as quarantined: read or copy specific files only when recovering data
from it.

Use tracked configuration for game paths:

- `constructor.load_order.toml` is the actual parser load-order config.
- `constructor.load_order.example.toml` is the portable template for other PCs.
- `[paths].vanilla_root` may be a Windows path such as `C:\Games\steamapps\common\Europa Universalis V`; parser tooling resolves it to `/mnt/c/...` on WSL/Linux.
- Keep `[[mods]].root` relative to the repo so clones can live anywhere.
- Machine-local live deploy targets belong in ignored `constructor.local.toml`; start from `constructor.local.example.toml`.

## Command Index

- `uv run ppc setup`: install dev dependencies and inspect the project.
- `uv run ppc inspect`: inspect the configured constructor project.
- `uv run ppc test`: run pytest; pass file names or pytest args after the command.
- `uv run ppc analyze`: export static parser tables and refresh the goods-flow docs example.
- `uv run ppc savegame`: export latest savegame facts and the savegame explorer.
- `uv run ppc europedia`: export the custom Prosper or Perish Europedia into the docs examples.
- `uv run ppc publish-docs`: copy generated graph outputs into `docs/examples`.
- STATIC_HTML_GRAPH_UPDATE: run `uv run ppc analyze` for `graphs/goods_flow_explorer.html` and `docs/examples/goods_flow_explorer.html`.
- STATIC_HTML_GRAPH_UPDATE: run `uv run ppc savegame` for `graphs/savegame_explorer.html` and `docs/examples/savegame_explorer.html`.
- STATIC_HTML_GRAPH_UPDATE: run `uv run ppc europedia` for `graphs/europedia.html`, `graphs/europedia_entries.json`, and matching files under `docs/examples/`.
- `uv run ppc dashboard`: serve the current population-capacity dashboard at `http://127.0.0.1:8000/`.
- `uv run ppc blueprint list`: list accepted blueprints.
- `uv run ppc blueprint parity`: compare accepted blueprints with generated mod output.
- `uv run ppc blueprint evaluate`: evaluate blueprint economics and balance rules.
- `uv run ppc blueprint tag <tag>`: evaluate accepted blueprints matching one building key, blueprint tag, custom tag, or filename stem.
- `uv run ppc blueprint good <good>`: compare methods that produce one trade good.
- `uv run ppc blueprint build`: build accepted blueprints into the constructor mod copy.
- `uv run ppc build`: same build workflow as `blueprint build`.
- `uv run ppc setup-corrections`: dry-run pre-tick setup building corrections from the current EU5 `error.log`.
- `uv run ppc setup-corrections --write`: regenerate the static setup correction override files.
- `uv run ppc setup-corrections --disable`: remove the generated setup correction files so a fresh game launch can prove which corrections are still needed.
- `uv run ppc sync --yes`: guarded live mirror into the configured Paradox mod folder.

## Safety Rules

- Do not run `sync --yes` unless the user explicitly asks to update the live Paradox mod folder.
- If `sync` is requested, confirm `constructor.local.toml` exists and contains the intended deploy target.
- If dashboard output is missing, generate or refresh the population-capacity artifacts before serving it.
- Prefer `test`, `inspect`, `blueprint evaluate`, and `blueprint parity` before changes that affect accepted blueprints or generated output.
- Use parser/evaluator command output as source of truth for game-data answers; do not infer economics from raw text search.

## Building Override Pattern

- For existing vanilla buildings, use a top-level `REPLACE:<building>` blueprint render.
- If replacing inline `unique_production_methods`, never reuse the vanilla method key. Add a mod-owned `pp_*` method key, reference that same key in `production_method_slots`, define it in `unique_production_methods`, and localize it.
- Do not put `TRY_REPLACE`, `REPLACE`, or `INJECT` inside `unique_production_methods`; those modes only apply to top-level common database entries.
- After changing a building override, run `uv run eu5-orchestrator validate --project constructor.toml` and `uv run ppc test tests/test_project_config.py::test_replaced_buildings_do_not_reuse_vanilla_unique_method_names tests/test_project_config.py::test_constructor_building_methods_are_resolved_and_unique`.

## Building Icon Style

- Building icons must be generated as detailed historic bitmap cutouts: material-rich, painterly, three-quarter-view isolated buildings or production complexes with real period props and readable machinery/worksite details.
- Use the approved `water_sawmill` and `lumber_mill_improved` icons as the reference style for new generated building icons.
- Do not use SVG-like, flat-vector, UI-glyph, simple 2D symbol, or square scenic landscape styles for building icons.
- Generate icon subjects on a perfectly flat magenta chroma-key background and remove it locally so the committed `source_png` has real alpha before writing the DDS output.

## Output Style

When reporting results, mention the exact `ppc` command used and summarize the important pass/fail lines. If a command writes a graph or dashboard, report the path under `graphs/`, `docs/examples/`, or `artifacts/data/population_capacity/current_capacity_map/`.

## Localization Style

- Treat localization as player-facing in-game text, not developer notes or a restatement of requested implementation details.
- Do not hardcode balance values in localization when a modifier, scripted value, building tooltip, or generated modifier effect can show the current value.
- Write localization around what the player sees, what it means, and where to inspect the effects; let modifiers carry exact changing numbers.
- When a linked modifier or concept tooltip already displays food-storage modifier effects, do not restate those values in Europedia prose.
- Use plain text in situation panes and generated static-modifier descriptions unless that target UI is verified to support inline concept links; unsupported formatter tags spam `error.log`.
- Use mod-owned plain localization keys for situation map legends rather than inherited or generic `LEGEND_KEY_*` keys; the legend UI is sensitive to formatter syntax.
- In GUI files, do not prefix `default_format` style names with `#`; use the raw style key such as `yellow_titles` so the text formatter does not parse it as an inline tag.

## Rural Capacity Memory

Before changing farming, fishing, or forest capacity math, tooltip rows,
map-mode copy, or the Farming/Fishing/Forest Capacities Europedia entry, read:

```bash
sed -n '1,220p' .agents/notes/farming_capacity.md
```

Core rule: rural capacities should be one visible sum each: `farm_capacity`,
`fish_capacity`, and `forest_capacity`. Building max-level tooltips should
expose the actual active plus/minus sources directly, not hidden "capacity used"
or "improvement bucket" abstractions.
