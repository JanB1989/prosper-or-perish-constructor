"""Prepare generated husbandry art and export building/advance DDS assets.

Usage: uv run python tools/build_husbandry_icons.py [--convertible RAW_PNG --improved RAW_PNG]
Without raw inputs, rebuild DDS files from the accepted transparent PNGs.
"""
from pathlib import Path
import argparse
import json
import re

import numpy as np
from PIL import Image, ImageDraw
from eu5_building_pipeline import render_template, write_icon_asset

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / 'mod/Prosper or Perish (Population Growth & Food Rework)'

def prepare(raw, destination):
    rgba = np.array(Image.open(raw).convert('RGBA'))
    rgb = rgba[:, :, :3].astype(float)
    # Key only magenta hues; retain natural earth, straw, foliage and white cattle.
    strength = np.minimum(rgb[:, :, 0], rgb[:, :, 2]) - rgb[:, :, 1]
    alpha = 1 - np.clip((strength - 25) / 100, 0, 1)
    rgba[:, :, 3] = np.minimum(rgba[:, :, 3], np.round(alpha * 255)).astype('uint8')
    edge = (strength > 25) & (alpha > 0)
    rgba[:, :, 0][edge] = np.minimum(rgb[:, :, 0][edge], rgb[:, :, 1][edge] + 25)
    rgba[:, :, 2][edge] = np.minimum(rgb[:, :, 2][edge], rgb[:, :, 1][edge] + 15)
    rgba[alpha == 0] = 0
    image = Image.fromarray(rgba)
    image = image.crop(image.getbbox())
    image.thumbnail((480, 480), Image.Resampling.LANCZOS)
    canvas = Image.new('RGBA', (512, 512))
    canvas.paste(image, ((512-image.width)//2, (512-image.height)//2))
    canvas.save(destination)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--convertible', type=Path)
    parser.add_argument('--improved', type=Path)
    args = parser.parse_args()
    prompts = json.loads((ROOT / 'docs/field_management_icon_prompts.json').read_text(encoding='utf-8-sig'))['prompts']
    for tier in ('convertible', 'improved'):
        key = f'field_management_{tier}'
        source = ROOT / 'blueprints/accepted/assets/icons' / f'{key}.png'
        raw = getattr(args, tier)
        if raw:
            prepare(raw, source)
        blueprint = ROOT / 'blueprints/accepted/buildings' / f'{key}.yml'
        text = blueprint.read_text()
        text = re.sub(r'^  prompt:.*$', '  prompt: ' + json.dumps(prompts[key]), text, flags=re.MULTILINE)
        blueprint.write_text(text)
        bundle = render_template(blueprint)
        for folder in ('in_game/gfx/interface/icons/buildings', 'main_menu/gfx/interface/advance'):
            output = MOD / folder / f'{key}.dds'
            output.parent.mkdir(parents=True, exist_ok=True)
            assert write_icon_asset(bundle.icon, output, overwrite=True)
            with Image.open(output) as dds, Image.open(source) as png:
                assert dds.size == (512, 512)
                assert dds.convert('RGBA').tobytes() == png.convert('RGBA').tobytes()
                assert png.getchannel('A').getextrema() == (0, 255)
            print(f'Verified {output.relative_to(ROOT)}')
    preview = Image.new('RGB', (960, 430), '#252c30')
    draw = ImageDraw.Draw(preview)
    for col, (key, label) in enumerate((('field_management', 'Field Management'), ('field_management_convertible', 'Convertible Husbandry'), ('field_management_improved', 'Improved Husbandry'))):
        icon = Image.open(ROOT / 'blueprints/accepted/assets/icons' / f'{key}.png').convert('RGBA')
        draw.text((col*320+18, 12), label, fill='white')
        large = icon.resize((300, 300), Image.Resampling.LANCZOS)
        preview.paste(large, (col*320+10, 36), large)
        for offset, size in ((26, 48), (112, 64)):
            small = icon.resize((size, size), Image.Resampling.LANCZOS)
            preview.paste(small, (col*320+offset, 348), small)
    output = ROOT / 'docs/images/field_management_icons.png'
    output.parent.mkdir(parents=True, exist_ok=True)
    preview.save(output)

if __name__ == '__main__':
    main()
