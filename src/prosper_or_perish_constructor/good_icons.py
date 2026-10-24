"""Icons of the mod's internal trade goods: PNG sources in ``assets/icons/trade_goods`` -> game DDS files.

For a good ``g`` with ``assets/icons/trade_goods/icon_goods_g.png`` (128 px) and, optionally,
``assets/icons/trade_goods/illustrations/icon_goods_g.png`` (1080 x 440), the build writes

- ``main_menu/gfx/interface/icons/trade_goods/icon_goods_g.dds`` (the goods icon),
- ``main_menu/gfx/interface/icons/modifier_types/g_positive.dds`` (the icon of its modifier types),
- ``main_menu/gfx/interface/icons/trade_goods/illustrations/icon_goods_g.dds`` (the market illustration),

as DXT5 with a full mip chain, the layout of the hand-converted offset icons. A missing PNG is skipped (the build runs
before the art exists); a DDS newer than its PNG is left alone.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

ASSET_ROOT = Path("assets/icons/trade_goods")
ICON_ROOT = Path("main_menu/gfx/interface/icons")
ICON_SIZE = (128, 128)
ILLUSTRATION_SIZE = (1080, 440)


@dataclass
class IconResult:
    written: list[Path] = field(default_factory=list)
    missing: list[Path] = field(default_factory=list)


def targets(good: str) -> list[tuple[Path, Path, tuple[int, int]]]:
    """(source PNG, mod-relative DDS, size) for one good."""
    icon = ASSET_ROOT / f"icon_goods_{good}.png"
    return [
        (icon, ICON_ROOT / "trade_goods" / f"icon_goods_{good}.dds", ICON_SIZE),
        (icon, ICON_ROOT / "modifier_types" / f"{good}_positive.dds", ICON_SIZE),
        (ASSET_ROOT / "illustrations" / f"icon_goods_{good}.png", ICON_ROOT / "trade_goods" / "illustrations" / f"icon_goods_{good}.dds", ILLUSTRATION_SIZE),
    ]


def install(repo: Path, mod_root: Path, goods: Iterable[str]) -> IconResult:
    result = IconResult()
    for good in goods:
        for source, relative, size in targets(good):
            png = repo / source
            dds = mod_root / relative
            if not png.is_file():
                result.missing.append(source)
                continue
            if dds.is_file() and dds.stat().st_mtime >= png.stat().st_mtime:
                continue
            write_dxt5(png, dds, size)
            result.written.append(relative)
    return result


def write_dxt5(png: Path, dds: Path, size: tuple[int, int]) -> None:
    """DXT5 DDS with a full mip chain (``floor(log2(max side)) + 1`` levels), the shared game-format writer."""
    from PIL import Image

    from eu5_building_pipeline.dds import write_game_dds

    with Image.open(png) as source:
        image = source.convert("RGBA")
    if image.size != size:
        image = image.resize(size, Image.Resampling.LANCZOS)
    write_game_dds(image, dds)
