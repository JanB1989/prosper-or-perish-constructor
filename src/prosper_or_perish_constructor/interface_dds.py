"""Interface DDS files in the game format: block-compressed (DXT) with a full mip chain, icons at vanilla size.

Vanilla's interface textures are all DXT1/DXT5 (some BC7) with ``floor(log2(max side)) + 1`` mip levels; icons are at
most 128 px (building icons 128 or 125, modifier icons 64, map mode icons 128), the advance icons 256. Files written
with a plain ``Image.save(format="DDS")`` are uncompressed RGBA without mips (the old 512 px building icons were 1 MB
each, half the mod). The finalize step of ``ppc build`` / ``ppc sync`` runs :func:`apply` over
``<layer>/gfx/interface/**/*.dds`` of the mod:

- a compliant file (compressed, full mip chain, within its folder's size) is left alone, byte for byte;
- a DXT1/DXT3/DXT5 file of the right size that only lacks mips keeps its first level byte for byte and gets the chain
  appended (no second compression pass);
- anything else (uncompressed, oversized, BCn Pillow cannot encode) is decoded, scaled to its folder's limit (aspect
  kept) and written as DXT5 with a full mip chain.

The writer is ``eu5_building_pipeline.dds`` (the building pipeline writes its icons the same way).
"""

from __future__ import annotations

from dataclasses import dataclass, field
import io
from pathlib import Path

INTERFACE = ("gfx", "interface")
# only <layer>/gfx/interface is walked, so gfx/map, gfx/terrain2 and map_data stay out; .metadata is no game layer
EXCLUDED_LAYERS = frozenset({".metadata"})
ICON_MAX_SIDE = 128
ADVANCE_MAX_SIDE = 256


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


def is_compliant(path: Path, relative: Path | None = None) -> bool:
    from eu5_building_pipeline.dds import is_game_format

    return is_game_format(path, max_side=max_side(relative or path))


def normalized(data: bytes, relative: Path) -> bytes:
    """The game-format bytes of one interface DDS (``data`` itself when it already complies)."""
    from PIL import Image

    from eu5_building_pipeline.dds import ENCODABLE, add_mips, dds_info, encode_dds, fit, is_game_format

    limit = max_side(relative)
    if is_game_format(data, max_side=limit):
        return data
    info = dds_info(data)
    if info is None:
        raise ValueError("not a DDS file")
    with Image.open(io.BytesIO(data)) as source:
        image = source.convert("RGBA")
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
        return f"Interface DDS: {result.checked} files in game format (DXT, full mips), none converted{failed}."
    return (
        f"Interface DDS: converted {len(result.converted)} of {result.checked} files to the game format "
        f"(DXT, full mips, icons <= {ICON_MAX_SIDE} px), {result.bytes_before / 1e6:.1f} MB -> "
        f"{result.bytes_after / 1e6:.1f} MB{failed}."
    )
