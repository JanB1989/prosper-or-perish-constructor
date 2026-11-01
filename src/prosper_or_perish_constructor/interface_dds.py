"""Interface DDS files in the game format: block-compressed (DXT) with a full mip chain, icons at vanilla size.

Vanilla's interface textures are all DXT1/DXT5 (some BC7) with ``floor(log2(max side)) + 1`` mip levels; icons are at
most 128 px (building icons 128 or 125, modifier icons 64, map mode icons 128), the advance icons 256. Files written
with a plain ``Image.save(format="DDS")`` are uncompressed RGBA without mips (the old 512 px building icons were 1 MB
each, half the mod). The finalize step of ``ppc build`` / ``ppc sync`` runs :func:`apply` over
``<layer>/gfx/interface/**/*.dds`` of the mod:

- a compliant file is left alone, byte for byte: compressed, full mip chain, within its folder's size; a picture (below
  an ``illustrations`` folder: the Europedia banners, situation and goods pictures) BC7 in one level;
- a picture in any other form is decoded and written as BC7 in one level;
- a DXT1/DXT3/DXT5 file of the right size that only lacks mips keeps its first level byte for byte and gets the chain
  appended (no second compression pass);
- anything else (uncompressed, oversized, BCn Pillow cannot encode) is decoded, scaled to its folder's limit (aspect
  kept) and written as DXT5 with a full mip chain.

Pictures are stored at twice the size they are shown (vanilla's ``texture_density = 2``: 1080 x 440 situation and goods
pictures in 220 px high frames; the Europedia banners 2900 x 500 at 1450 x 250), so with a mip chain the game draws
their half-size second level at UI scale 1 and blends the two levels between UI scales 1 and 2. After the 2026-10-24
cleanup appended DXT5 mips to the banners they looked soft and blocky. Measured against the uncompressed banner at the
shown size (UI scale 0.75 / 1 / 1.33 / 2): DXT5 with mips 31 / 31 / 32 / 32 dB, BC7 with mips 33 / 39 / 34 / 41, BC7
in one level 33 / 40 / 40 / 41. BC7 (like vanilla's painted location-view illustrations and tutorial pictures) costs
a byte per pixel like DXT5; one level saves the chain's third. Write a picture from its source with
:func:`encode_bc7` (``tools/build_europedia_banners.py``, ``tools/build_harvest_situation_art.py``, ``good_icons``).

The DXT writer is ``eu5_building_pipeline.dds`` (the building pipeline writes its icons the same way).
"""

from __future__ import annotations

from dataclasses import dataclass, field
import io
from pathlib import Path
import struct

INTERFACE = ("gfx", "interface")
# only <layer>/gfx/interface is walked, so gfx/map, gfx/terrain2 and map_data stay out; .metadata is no game layer
EXCLUDED_LAYERS = frozenset({".metadata"})
ICON_MAX_SIDE = 128
ADVANCE_MAX_SIDE = 256
PICTURE_FORMAT = "BC7"
DXGI_FORMAT_BC7_UNORM = 98   # the DX10 header format of vanilla's BC7 illustrations


@dataclass
class NormalizeResult:
    checked: int = 0
    converted: list[Path] = field(default_factory=list)   # mod-relative
    bytes_before: int = 0
    bytes_after: int = 0
    failed: list[tuple[Path, str]] = field(default_factory=list)


def interface_files(mod_root: Path) -> list[Path]:
    files: list[Path] = []
    for layer in sorted(p for p in mod_root.iterdir() if p.is_dir() and p.name not in EXCLUDED_LAYERS):
        root = layer.joinpath(*INTERFACE)
        if root.is_dir():
            files.extend(path for path in sorted(root.rglob("*")) if path.suffix.lower() == ".dds" and path.is_file())
    return files


def max_side(relative: Path) -> int | None:
    """The largest side a file may have, from its folder below ``<layer>/gfx/interface`` (None = keep its size).

    ``icons/**`` (not illustrations) 128 like every vanilla icon folder, the advance icons 256 like vanilla's;
    illustrations, banners and the like keep their size."""
    parts = relative.parts
    try:
        inner = parts[parts.index("interface") + 1:]
    except ValueError:
        return None
    if inner and inner[0] == "icons" and "illustrations" not in inner:
        return ICON_MAX_SIDE
    if len(inner) == 2 and inner[0] == "advance":
        return ADVANCE_MAX_SIDE
    return None


def is_picture(relative: Path) -> bool:
    """Below an ``illustrations`` folder, vanilla's place for pictures (situations, events, goods, our banners)."""
    return "illustrations" in relative.parts


def is_picture_format(source: Path | bytes) -> bool:
    """BC7 in one level, the picture format."""
    from eu5_building_pipeline.dds import dds_info

    info = dds_info(source)
    return info is not None and info.format == PICTURE_FORMAT and info.mip_count == 1


def is_compliant(path: Path, relative: Path | None = None) -> bool:
    from eu5_building_pipeline.dds import is_game_format

    relative = relative or path
    return is_picture_format(path) if is_picture(relative) else is_game_format(path, max_side=max_side(relative))


def encode_bc7(image) -> bytes:
    """``image`` (a PIL image) as a BC7 DDS in one level, the picture format: etcpak's bc7enc (~41 dB on a banner
    painting, 0.5 s), DX10 header like vanilla's BC7 illustrations."""
    import etcpak
    import numpy as np

    image = image.convert("RGBA")
    # whole 4x4 blocks, edges padded by repetition (the decoder crops them)
    rgba = np.pad(np.asarray(image), ((0, -image.height % 4), (0, -image.width % 4), (0, 0)), mode="edge")
    params = etcpak.BC7CompressBlockParams()
    if image.getextrema()[3][0] == 255:
        # opaque: modes 0-5 keep alpha at 255 at the same quality; bc7enc's mode 6 stored 254 in a quarter of the blocks
        params.m_mode_mask = 0x3F
    blocks = etcpak.compress_bc7(rgba.tobytes(), rgba.shape[1], rgba.shape[0], params)
    flags = 0x1 | 0x2 | 0x4 | 0x1000 | 0x20000 | 0x80000   # caps, height, width, pixel format, mip count, linear size
    return (
        b"DDS " + struct.pack("<7I", 124, flags, image.height, image.width, len(blocks), 0, 1) + bytes(44)
        + struct.pack("<8I", 32, 0x4, int.from_bytes(b"DX10", "little"), 0, 0, 0, 0, 0)   # FourCC DX10
        + struct.pack("<5I", 0x1000, 0, 0, 0, 0)                                           # a plain texture
        + struct.pack("<5I", DXGI_FORMAT_BC7_UNORM, 3, 0, 1, 0)                            # 2D, array size 1
        + blocks
    )


def normalized(data: bytes, relative: Path) -> bytes:
    """The game-format bytes of one interface DDS (``data`` itself when it already complies)."""
    from PIL import Image

    from eu5_building_pipeline.dds import ENCODABLE, add_mips, dds_info, encode_dds, fit, is_game_format

    limit = max_side(relative)
    picture = is_picture(relative)
    if (is_picture_format(data) if picture else is_game_format(data, max_side=limit)):
        return data
    info = dds_info(data)
    if info is None:
        raise ValueError("not a DDS file")
    with Image.open(io.BytesIO(data)) as source:
        image = source.convert("RGBA")
    if picture:
        return encode_bc7(image)
    oversized = limit is not None and max(image.size) > limit
    if info.compressed and info.format in ENCODABLE and not oversized:
        # DXT1 has no alpha to speak of: one with transparent pixels is re-encoded as DXT5 rather than risk the mips
        if info.format != "DXT1" or image.getextrema()[3][0] == 255:
            return add_mips(data)
    if oversized:
        scale = limit / max(image.size)
        image = fit(image, (max(1, round(image.width * scale)), max(1, round(image.height * scale))))
    pixel_format = "DXT1" if info.format == "DXT1" and image.getextrema()[3][0] == 255 else "DXT5"
    return encode_dds(image, pixel_format)


def apply(mod_root: Path, *, skip: frozenset[str] = frozenset()) -> NormalizeResult:
    """Convert every non-compliant interface DDS of the mod in place (idempotent). ``skip``: file names to leave."""
    result = NormalizeResult()
    for path in interface_files(mod_root):
        relative = path.relative_to(mod_root)
        result.checked += 1
        if path.name in skip:
            continue
        data = path.read_bytes()
        try:
            fixed = normalized(data, relative)
        except (OSError, ValueError) as error:
            result.failed.append((relative, str(error)))
            continue
        if fixed is data:
            continue
        path.write_bytes(fixed)
        result.converted.append(relative)
        result.bytes_before += len(data)
        result.bytes_after += len(fixed)
    return result


def summary(result: NormalizeResult) -> str:
    failed = f"; {len(result.failed)} unreadable: " + ", ".join(f"{p} ({e})" for p, e in result.failed) if result.failed else ""
    if not result.converted:
        return f"Interface DDS: {result.checked} files in game format (DXT, full mips; pictures BC7), none converted{failed}."
    return (
        f"Interface DDS: converted {len(result.converted)} of {result.checked} files to the game format "
        f"(DXT, full mips, icons <= {ICON_MAX_SIDE} px; pictures BC7), {result.bytes_before / 1e6:.1f} MB -> "
        f"{result.bytes_after / 1e6:.1f} MB{failed}."
    )
