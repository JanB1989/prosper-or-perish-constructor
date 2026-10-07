"""Trace which mod files the World Builder stage reads and check them against cli.WORLDBUILDER_MOD_INPUTS.

    uv run python tools/trace_worldbuilder_inputs.py

Runs `ppc worldbuilder apply` in this process with an audit hook that logs every file opened and every folder listed
under the mod root (the stage runs its helper scripts in-process with runpy, so they are traced too). Prints the inputs
the fingerprint misses (it exits 1 then) and the listed inputs the stage no longer reads.

Running the stage alone skips the sync's finalize step, so it leaves some generated files half done. The tool restores
every mod file that was clean before the run (`git restore`); run it on a clean mod tree.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from prosper_or_perish_constructor import cli  # noqa: E402

# Map data and setup count whole (cli.WORLDBUILDER_MOD_INPUTS); the trace narrows the script folders.
ROOTS = ("in_game/common", "in_game/map_data", "main_menu/common", "main_menu/setup", "loading_screen/common")


def _dirty(mod: Path) -> set[str]:
    out = subprocess.run(["git", "status", "--porcelain", "--", str(mod)], cwd=REPO, capture_output=True, text=True,
                         check=True).stdout
    return {line[3:].strip('"') for line in out.splitlines()}


def main() -> int:
    project = REPO / "constructor.toml"
    mod = cli._project_mod_root(REPO, project)
    prefix = str(mod) + os.sep
    reads: set[str] = set()
    writes: set[str] = set()
    lists: set[str] = set()

    def hook(event: str, args: tuple) -> None:
        if event not in ("open", "os.listdir", "os.scandir") or not args:
            return
        path = args[0]
        if isinstance(path, (bytes, os.PathLike)):
            path = os.fsdecode(path)
        if not isinstance(path, str):
            return
        path = os.path.abspath(path)
        if not path.startswith(prefix):
            return
        rel = path[len(prefix):]
        if event == "open":
            mode = str(args[1] or "r")
            (writes if any(c in mode for c in "wax+") else reads).add(rel)
        else:
            lists.add(rel)

    before = _dirty(mod)
    sys.addaudithook(hook)
    try:
        cli._worldbuilder_apply(REPO, project)
    finally:
        changed = sorted(_dirty(mod) - before)
        if changed:
            subprocess.run(["git", "restore", "--", *changed], cwd=REPO, check=True)
            print(f"restored {len(changed)} generated files the stage left without the finalize step")

    def root_of(rel: str) -> str | None:
        return next((r for r in ROOTS if rel == r or rel.startswith(r + "/")), None)

    inputs = set(cli.WORLDBUILDER_MOD_INPUTS)

    def covered(rel: str) -> bool:
        return any(rel == item or rel.startswith(item + "/") for item in inputs)

    # A listed folder counts whole, so it must be an input itself (or lie inside one); a read file must be covered.
    missing = [d for d in lists if root_of(d) and not covered(d)]
    missing += [f for f in reads if root_of(f) and not covered(f)]
    unused = sorted(i for i in inputs if not any(r == i or r.startswith(i + "/") for r in reads | lists))
    print(f"traced {len(reads)} reads, {len(writes)} writes, {len(lists)} listed folders under the mod root")
    for rel in sorted(set(missing)):
        print(f"MISSING from WORLDBUILDER_MOD_INPUTS: {rel}")
    for rel in unused:
        print(f"no longer read (could drop): {rel}")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
