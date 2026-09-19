"""本地试片：把 20 帧拼成 4x5 接触表 PNG，便于目视（不经过 Aseprite）。"""

import sys
from pathlib import Path

from PIL import Image

import monster as mo

SCALE = int(sys.argv[1]) if len(sys.argv) > 1 else 5
BG = (28, 30, 26)

sheet = Image.new("RGB", (mo.W * SCALE * len(mo.PHASES),
                          mo.H * SCALE * len(mo.DIRS)), BG)
for r, d in enumerate(mo.DIRS):
    for c, p in enumerate(range(len(mo.PHASES))):
        img = Image.new("RGBA", (mo.W, mo.H), (0, 0, 0, 0))
        px = img.load()
        for y, row in enumerate(mo.build(d, p)):
            for x, ch in enumerate(row):
                if ch != ".":
                    h = mo.PALETTE[ch].lstrip("#")
                    px[x, y] = (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255)
        sheet.paste(img.resize((mo.W * SCALE, mo.H * SCALE), Image.NEAREST),
                    (c * mo.W * SCALE, r * mo.H * SCALE))
out = Path(__file__).parent / ".build" / "sheet_preview.png"
out.parent.mkdir(parents=True, exist_ok=True)
sheet.save(out)
print(out, sheet.size)
