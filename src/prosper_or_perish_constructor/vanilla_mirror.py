"""A copy of the game's data files on the local (WSL) disk.

The game install sits on a Windows drive. Under WSL every file access there is a slow round trip, and the
build and the test suite read thousands of game files, so that latency dominated both. ``ppc vanilla-mirror``
copies the install's ``game`` folder to a local directory, leaving out models, animations, audio and fonts
(no tooling reads them), and writes the git-ignored ``constructor.load_order.local.toml`` that points
``vanilla_root`` at the copy. The copy records the Steam build it was made from: after a game update the
parser warns and reads the install again until the copy is refreshed with the same command.
"""

from __future__ import annotations

import re
import subprocess
import tomllib
from pathlib import Path

from eu5gameparser.load_order import local_load_order_path

from prosper_or_perish_constructor.location_baseline import resolve_load_order_path

DEFAULT_TARGET = Path.home() / ".cache" / "eu5-vanilla"
EXCLUDED_PATTERNS = (
    "*.mesh", "*.anim", "*.animsm", "*.asset", "*.editordata", "*.schematic", "*.particle2",
    "*.wem", "*.bank", "*.bnk", "*.bk2", "*.ogg", "*.ttf", "*.otf", "*.lnk",
)


def mirror(load_order_path: Path, target: Path = DEFAULT_TARGET) -> dict[str, str]:
    """Copy (or refresh) the game folder into ``target`` and point the local load-order override at it."""
    tracked = tomllib.loads(load_order_path.read_text(encoding="utf-8"))
    source = resolve_load_order_path(str(tracked["paths"]["vanilla_root"]), load_order_path.parent)
    if not (source / "game").is_dir():
        raise FileNotFoundError(f"no game folder under the configured vanilla_root: {source}")
    manifest = steam_manifest(source)
    build_id = steam_build_id(manifest)
    target.mkdir(parents=True, exist_ok=True)
    command = ["rsync", "-a", "--delete", *(f"--exclude={pattern}" for pattern in EXCLUDED_PATTERNS)]
    subprocess.run([*command, f"{source / 'game'}/", f"{target / 'game'}/"], check=True)
    local = local_load_order_path(load_order_path)
    local.write_text(
        "# Machine-local override written by `ppc vanilla-mirror`; not tracked.\n"
        "# vanilla_root points at a local copy of the game's data files (fast under WSL). The parser ignores\n"
        "# the copy with a warning once the installed build differs; re-run `ppc vanilla-mirror` then.\n"
        "\n"
        "[paths]\n"
        f'vanilla_root = "{target.as_posix()}"\n'
        "\n"
        "[vanilla_mirror]\n"
        f'source = "{source.as_posix()}"\n'
        f'steam_manifest = "{manifest.as_posix()}"\n'
        f'buildid = "{build_id}"\n',
        encoding="utf-8",
    )
    return {"source": str(source), "target": str(target), "buildid": build_id, "override": str(local)}


def installed_build_id(load_order_path: Path) -> str | None:
    """Steam build of the game install the tracked load order names; None when it cannot be read."""
    try:
        tracked = tomllib.loads(load_order_path.read_text(encoding="utf-8"))
        source = resolve_load_order_path(str(tracked["paths"]["vanilla_root"]), load_order_path.parent)
        return steam_build_id(steam_manifest(source))
    except (OSError, KeyError, ValueError):
        return None


def steam_manifest(install: Path) -> Path:
    """The ``appmanifest_*.acf`` of the Steam library that holds ``install`` (``steamapps/common/<name>``)."""
    steamapps = install.parent.parent
    for manifest in sorted(steamapps.glob("appmanifest_*.acf")):
        text = manifest.read_text(encoding="utf-8", errors="replace")
        if re.search(rf'"installdir"\s+"{re.escape(install.name)}"', text):
            return manifest
    raise FileNotFoundError(f"no Steam app manifest for {install.name} in {steamapps}")


def steam_build_id(manifest: Path) -> str:
    match = re.search(r'"buildid"\s+"(\d+)"', manifest.read_text(encoding="utf-8", errors="replace"))
    if match is None:
        raise ValueError(f"no buildid in {manifest}")
    return match.group(1)
