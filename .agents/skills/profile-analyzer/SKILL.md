---
name: profile-analyzer
description: Analyze EU5 in-game profiler dumps, visualize script hotspots and inferred call graphs, and compare vanilla or modded captures using the standalone Profile Analyzer.
---

# Profile Analyzer

Use the standalone [Profile Analyzer](https://github.com/JanB1989/profile-analyzer).
Its implementation and tests belong in that repository; the constructor only keeps this skill.

## Run

From the constructor repository, run:

```bash
uvx --from https://github.com/JanB1989/profile-analyzer/archive/refs/heads/main.zip profile-analyzer "path/to/logs" --output "graphs/profiler" --label "run-name"
```

`uvx` manages an isolated tool environment; no constructor dependency or sibling checkout is required.
For additional options, run the same command with `--help` instead of the input and report arguments.

- Use the user's input and output folders when supplied. Otherwise read `[profiler].logs_dir`
  from ignored `constructor.local.toml`; if absent, locate the current user's EU5 logs under
  `Documents/Paradox Interactive/Europa Universalis V/logs`. Do not guess between multiple users or captures.
- Pass the complete capture folder so `profiling.csv`, `profiling_roots.csv`, and optional
  `performance_degradation.log` can contribute. Do not combine files from different runs.
- Quoted Windows drive paths are supported from WSL. Run in the native WSL checkout when using WSL.
- Each run creates a timestamped directory with an offline `index.html`, data exports, and input snapshots.
  Use existing snapshots when the game has overwritten a capture. Keep reports untracked.

## Source graphs and comparisons

For source context and inferred graph edges, add `--game-root "path/to/EU5"` and
repeat `--source "mod-name=path/to/mod"` in the capture's actual load order; later roots win.
Without sources, measured hotspots still work.

Read `constructor.load_order.toml` for `[paths].vanilla_root`, `[[mods]]` roots, and
`[profiles]`. Translate the selected capture's profile into these standalone flags:
vanilla gets only the game root; a constructor capture also gets its configured mod root.
Resolve relative roots against the constructor repository. For other mods, use their actual
source folders and load order. The standalone tool does not read constructor config itself.
Use source versions matching the capture; current scripts may have different line numbers.

Add `--baseline "path/to/earlier/report-or-logs"` to compare runs. An earlier report uses
its preserved input snapshots, so it remains usable after the next in-game dump.

## Read and show the result

Open the generated `index.html` and give the user its full path. Summarize the largest
self-time hotspots and any parsing warnings. If serving the report for browser access,
bind the server to localhost.

Graphs are inferred from script structure and references, not recorded call stacks.
Summary and detail are separate measurement views; inclusive times overlap. Self-time
shares refer to profiled script time, not wall-clock time. Keep raw timing units unless
independently known. Baselines match type/file/line and compare shares, so changed sources
or workloads do not establish an FPS improvement.
