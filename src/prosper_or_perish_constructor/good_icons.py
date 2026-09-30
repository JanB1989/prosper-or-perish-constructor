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
import io
import math
from pathlib import Path
import struct
from typing import Iterable

ASSET_ROOT = Path("assets/icons/trade_goods")
ICON_ROOT = Path("main_menu/gfx/interface/icons")
ICON_SIZE = (128, 128)
ILLUSTRATION_SIZE = (1080, 440)

_DDSD_MIPMAPCOUNT = 0x20000
_DDSCAPS_COMPLEX = 0x8
_DDSCAPS_MIPMAP = 0x400000


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
    """DXT5 DDS with a full mip chain (``floor(log2(max side)) + 1`` levels)."""
    from PIL import Image

    with Image.open(png) as source:
        image = source.convert("RGBA")
    if image.size != size:
        image = image.resize(size, Image.Resampling.LANCZOS)
    levels = int(math.floor(math.log2(max(size)))) + 1
    header: bytearray | None = None
    data = bytearray()
    for level in range(levels):
        width, height = max(1, size[0] >> level), max(1, size[1] >> level)
        mip = image if level == 0 else image.resize((width, height), Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        mip.save(buffer, format="DDS", pixel_format="DXT5")
        raw = buffer.getvalue()
        if header is None:
            header = bytearray(raw[:128])
        data += raw[128:]
    assert header is not None
    flags, = struct.unpack_from("<I", header, 8)
    struct.pack_into("<I", header, 8, flags | _DDSD_MIPMAPCOUNT)
    struct.pack_into("<I", header, 28, levels)
    caps, = struct.unpack_from("<I", header, 108)
    struct.pack_into("<I", header, 108, caps | _DDSCAPS_COMPLEX | _DDSCAPS_MIPMAP)
    dds.parent.mkdir(parents=True, exist_ok=True)
    dds.write_bytes(bytes(header) + bytes(data))
