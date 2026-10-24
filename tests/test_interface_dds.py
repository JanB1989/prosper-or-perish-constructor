"""Interface DDS files are in the game format (interface_dds.py, the last finalize pass of ppc build / sync)."""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw

from eu5_building_pipeline.dds import dds_info, encode_dds, is_game_format
from prosper_or_perish_constructor import interface_dds

ROOT = Path(__file__).resolve().parents[1]
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"


def test_every_mod_interface_dds_is_in_the_game_format() -> None:
    # block-compressed with a full mip chain; pictures BC7 in one level (shown at half size, a chain blurs them)
    files = interface_dds.interface_files(MOD_ROOT)
    assert len(files) > 300
    bad = []
    for path in files:
        relative = path.relative_to(MOD_ROOT)
        info = dds_info(path)
        if interface_dds.is_picture(relative):
            if not interface_dds.is_picture_format(path):
                bad.append(f"{relative}: picture {info}, not {interface_dds.PICTURE_FORMAT} in one level")
        elif info is None or not info.compressed or not info.has_full_mips:
            bad.append(f"{relative}: {info}")
        elif (limit := interface_dds.max_side(relative)) is not None and max(info.width, info.height) > limit:
            bad.append(f"{relative}: {info.width}x{info.height} > {limit}")
    assert bad == [], "run interface_dds.apply (ppc build's finalize step):\n" + "\n".join(bad)


def test_building_icons_are_at_most_128_px() -> None:
    icons = [p for p in interface_dds.interface_files(MOD_ROOT) if p.parent.name == "buildings"]
    assert icons
    too_big = [p.name for p in icons if max(dds_info(p).width, dds_info(p).height) > 128]
    assert too_big == []


def test_map_mode_icons_live_only_in_main_menu() -> None:
    in_game = MOD_ROOT / "in_game" / "gfx" / "interface" / "icons" / "map_modes"
    assert not in_game.exists() or not any(in_game.glob("*.dds"))


def _icon(size: int) -> Image.Image:
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(image).ellipse((size // 8, size // 8, size * 7 // 8, size * 7 // 8), fill=(150, 90, 40, 255))
    return image


def test_apply_converts_old_icons_and_leaves_compliant_files_alone(tmp_path: Path) -> None:
    icons = tmp_path / "in_game" / "gfx" / "interface" / "icons"
    old = icons / "buildings" / "old.dds"
    old.parent.mkdir(parents=True)
    _icon(512).save(old, format="DDS")                       # the old pipeline output: 512 px RGBA, no mips
    flat = icons / "modifiers" / "flat.dds"
    flat.parent.mkdir(parents=True)
    _icon(128).save(flat, format="DDS", pixel_format="DXT5")  # Pillow DXT5 without mips
    good = icons / "modifiers" / "good.dds"
    good.write_bytes(encode_dds(_icon(64)))
    good_bytes, good_mtime = good.read_bytes(), good.stat().st_mtime_ns
    banner = tmp_path / "main_menu" / "gfx" / "interface" / "illustrations" / "banner.dds"
    banner.parent.mkdir(parents=True)
    Image.new("RGBA", (600, 100), (10, 20, 30, 255)).save(banner, format="DDS")
    map_texture = tmp_path / "in_game" / "gfx" / "map" / "x.dds"
    map_texture.parent.mkdir(parents=True)
    _icon(64).save(map_texture, format="DDS")

    result = interface_dds.apply(tmp_path)

    assert result.checked == 4 and len(result.converted) == 3 and result.failed == []
    assert is_game_format(old, size=(128, 128))
    assert dds_info(old).format == "DXT5"
    assert is_game_format(flat, size=(128, 128))
    assert good.read_bytes() == good_bytes and good.stat().st_mtime_ns == good_mtime
    assert (dds_info(banner).width, dds_info(banner).height) == (600, 100)   # illustrations keep their size
    assert interface_dds.is_picture_format(banner)           # pictures are BC7 in one level
    assert dds_info(map_texture).compressed is False         # gfx/map is not touched
    with Image.open(old) as image:
        rgba = image.convert("RGBA")
    assert rgba.getpixel((0, 0))[3] == 0 and rgba.getpixel((64, 64))[3] == 255

    again = interface_dds.apply(tmp_path)
    assert again.converted == [] and again.checked == 4


def test_mipless_dxt5_keeps_its_first_level_bytes(tmp_path: Path) -> None:
    path = tmp_path / "main_menu" / "gfx" / "interface" / "icons" / "modifiers" / "x.dds"
    path.parent.mkdir(parents=True)
    _icon(128).save(path, format="DDS", pixel_format="DXT5")
    before = path.read_bytes()
    top = dds_info(before).top_level_size

    interface_dds.apply(tmp_path)

    after = path.read_bytes()
    assert is_game_format(after, size=(128, 128))
    assert after[128:128 + top] == before[128:128 + top]


def test_dxt_pictures_become_one_bc7_level(tmp_path: Path) -> None:
    # a DXT5 picture with a full chain is compliant as a texture, but pictures are BC7 in one level (they are shown at
    # half their size, so the game drew the chain's blurred second level)
    path = tmp_path / "main_menu" / "gfx" / "interface" / "illustrations" / "situation" / "x.dds"
    path.parent.mkdir(parents=True)
    picture = Image.new("RGBA", (1080, 440), (180, 120, 60, 255))
    ImageDraw.Draw(picture).rectangle((200, 100, 700, 300), fill=(40, 90, 160, 255))
    path.write_bytes(encode_dds(picture))
    assert not interface_dds.is_compliant(path, path.relative_to(tmp_path))

    result = interface_dds.apply(tmp_path)

    assert len(result.converted) == 1
    data = path.read_bytes()
    info = dds_info(data)
    assert (info.format, info.width, info.height, info.mip_count) == ("BC7", 1080, 440, 1)
    assert int.from_bytes(data[128:132], "little") == interface_dds.DXGI_FORMAT_BC7_UNORM
    with Image.open(path) as image:                          # a standard reader takes it
        rgba = image.convert("RGBA")
    assert rgba.size == (1080, 440)
    assert max(abs(a - b) for a, b in zip(rgba.getpixel((50, 50)), (180, 120, 60, 255))) <= 4
    assert max(abs(a - b) for a, b in zip(rgba.getpixel((450, 200)), (40, 90, 160, 255))) <= 4
    assert interface_dds.apply(tmp_path).converted == []


def test_bc7_picture_pads_to_whole_blocks() -> None:
    data = interface_dds.encode_bc7(Image.new("RGBA", (1082, 442), (10, 200, 30, 255)))
    info = dds_info(data)
    assert (info.width, info.height, info.mip_count) == (1082, 442, 1)
    assert len(data) == 148 + 16 * 271 * 111                # ceil(1082 / 4) x ceil(442 / 4) blocks
    with Image.open(io.BytesIO(data)) as image:
        assert image.size == (1082, 442) and image.convert("RGBA").getpixel((1081, 441)) == (10, 200, 30, 255)


def test_size_limits_follow_vanilla_folders() -> None:
    assert interface_dds.max_side(Path("in_game/gfx/interface/icons/buildings/a.dds")) == 128
    assert interface_dds.max_side(Path("main_menu/gfx/interface/icons/map_modes/a.dds")) == 128
    assert interface_dds.max_side(Path("main_menu/gfx/interface/advance/a.dds")) == 256
    assert interface_dds.max_side(Path("main_menu/gfx/interface/icons/trade_goods/illustrations/a.dds")) is None
    assert interface_dds.max_side(Path("main_menu/gfx/interface/illustrations/pp_europedia/a.dds")) is None
