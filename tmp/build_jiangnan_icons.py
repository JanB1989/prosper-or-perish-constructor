from pathlib import Path
from PIL import Image, ImageDraw
from eu5_building_pipeline import render_template, write_icon_asset
r=Path.cwd(); source=Path('/mnt/c/Users/Anwender/.codex/generated_images/01a0bf15-1954-7590-b620-f4ba2556643e')
preview=Image.new('RGB',(560,330),'#242b2e'); d=ImageDraw.Draw(preview)
for row,(key,filename) in enumerate([('jiangnan_canal_network','exec-92ae8581-3dcf-4bb2-ae38-a06e2c7d27e0.png'),('jiangnan_hill_terraces','exec-fd2a8d81-3c0d-4bad-8c1a-1532872f7343.png')]):
 im=Image.open(source/filename).convert('RGBA'); assert im.getchannel('A').getextrema()==(0,255)
 im=im.resize((512,512),Image.Resampling.LANCZOS); im.save(r/f'blueprints/accepted/assets/icons/{key}.png')
 bundle=render_template(r/f'blueprints/accepted/buildings/{key}.yml'); write_icon_asset(bundle.icon,r/f'mod/Prosper or Perish (Population Growth & Food Rework)/in_game/gfx/interface/icons/buildings/{key}.dds',overwrite=True)
 d.text((10,row*165+5),key,fill='white')
 for x,size in [(10,48),(100,64),(220,96),(390,128)]:
  small=im.resize((size,size),Image.Resampling.LANCZOS); preview.paste(small,(x,row*165+25),small)
preview.save(r/'tmp/jiangnan_icons_preview.png')
