"""Install the icons of the two schools and their three advances (literacy rework, 2026-11-25), and of the Academy of
Sciences and its advance (2026-11-27).

The schools and the academy are hand-written buildings (in_game/common/building_types/pp_school_buildings.txt; their blueprints are
disabled and carry only the footprint class), so the blueprint pipeline does not render their icons. This tool does:
it runs the building drawings (assets/icon_drawings/pp_village_school, pp_trade_school) through
`eu5-building icon build`, keeps the 512 px result as assets/icons/<icon>.png and writes the game icon to
in_game/gfx/interface/icons/buildings/<icon>.dds. The three advance drawings write their own DDS
(main_menu/gfx/interface/advance/<icon>.dds).

    uv run python tools/build_school_icons.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image

from eu5_building_pipeline.dds import fit, write_game_dds

ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT.parent / "eu5-building-pipeline"
DRAWINGS = ROOT / "assets/icon_drawings"
BUILDINGS = ("pp_village_school", "pp_trade_school", "pp_academy_of_sciences")
ADVANCES = ("pp_village_schools_advance", "pp_reckoning_schools_advance", "pp_common_schooling_advance",
            "pp_academy_of_sciences_advance")
BUILDING_ICONS = ROOT / "mod/pp/in_game/gfx/interface/icons/buildings"
SIZE = 128


def main() -> int:
    env = {**os.environ, "EU5_VANILLA_DIR": os.environ.get("EU5_VANILLA_DIR", str(Path.home() / ".cache/eu5-vanilla/game"))}
    for icon in BUILDINGS:
        out = ROOT / "artifacts/icons" / icon
        subprocess.run(["uv", "run", "eu5-building", "icon", "build", "--script", str(DRAWINGS / icon / "draw.py"),
                        "--out", str(out)], cwd=PIPELINE, env=env, check=True, stdout=subprocess.DEVNULL)
        source = ROOT / "assets/icons" / f"{icon}.png"
        shutil.copyfile(out / f"{icon}_512.png", source)
        target = BUILDING_ICONS / f"{icon}.dds"
        write_game_dds(fit(Image.open(source).convert("RGBA"), (SIZE, SIZE)), target)
        print(f"wrote {target.relative_to(ROOT)}")
    for icon in ADVANCES:
        subprocess.run([sys.executable, str(DRAWINGS / icon / "draw.py")], cwd=ROOT, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
