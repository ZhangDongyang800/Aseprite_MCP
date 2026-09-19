"""把吞噬怪动画打包成 demo：精灵表 + 四方向 GIF + .ase。"""

import shutil
from pathlib import Path

from PIL import Image

import monster as mo

HERE = Path(__file__).parent
SRC = HERE / ".build"        # build_monster.py / finalize.py 的产物
DST = HERE.parent            # demo/slime_devourer/
SCALE = 4
CELL = mo.W * SCALE
DUR = [int(d * 1000) for d in (0.2, 0.1, 0.08, 0.09, 0.22)]

DST.mkdir(parents=True, exist_ok=True)

for d in mo.DIRS:
    frames = [Image.open(SRC / "frames" / f"frame{mo.frame_index(d, p)}.png")
              .convert("RGBA").resize((CELL, CELL), Image.NEAREST)
              for p in range(len(mo.PHASES))]
    first, rest = frames[0], frames[1:]
    out = DST / f"slime_devourer_devour_{d}.gif"
    first.save(out, save_all=True, append_images=rest, duration=DUR,
               loop=0, optimize=True, disposal=2)
    print(out.name, first.size, len(frames), "frames", DUR)

shutil.copyfile(SRC / "monster_sheet.png", DST / "slime_devourer_spritesheet.png")
shutil.copyfile(SRC / "monster.ase", DST / "slime_devourer_devour.ase")
print("copied sheet + ase")
