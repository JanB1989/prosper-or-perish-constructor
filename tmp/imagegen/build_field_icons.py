from pathlib import Path

from PIL import Image, ImageDraw
from eu5_building_pipeline import render_template, write_icon_asset

root = Path(__file__).resolve().parents[2]
names = ('field_management', 'irrigated_fields')
output = root / 'mod/Prosper or Perish (Population Growth & Food Rework)/in_game/gfx/interface/icons/buildings'
preview = Image.new('RGB', (640, 350), '#242b2e')
draw = ImageDraw.Draw(preview)
for row, name in enumerate(names):
    source = root / 'blueprints/accepted/assets/icons' / f'{name}.png'
    with Image.open(source) as original:
        icon = original.convert('RGBA').resize((512, 512), Image.Resampling.LANCZOS)
    icon.save(source)
    bundle = render_template(root / 'blueprints/accepted/buildings' / f'{name}.yml')
    assert bundle.icon is not None
    assert write_icon_asset(bundle.icon, output / f'{name}.dds', overwrite=True)
    with Image.open(output / f'{name}.dds') as dds:
        assert dds.size == (512, 512)
        assert dds.convert('RGBA').tobytes() == icon.tobytes()
    alpha = icon.getchannel('A')
    assert alpha.getextrema() == (0, 255)
    print(f'{name}: 512x512 RGBA, transparent, pipeline DDS matches source')
    y = row * 175
    draw.text((14, y + 8), name, fill='white')
    for x, size in ((16, 48), (110, 64), (224, 96), (400, 128)):
        small = icon.resize((size, size), Image.Resampling.LANCZOS)
        preview.paste(small, (x, y + 30), small)
        draw.text((x, y + 33 + size), f'{size}px', fill='white')
preview.save(root / 'tmp/imagegen/field_icons_preview.png')
