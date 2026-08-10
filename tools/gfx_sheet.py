"""렌더한 PNG 를 한 장의 대지(contact sheet)로 묶어 글자가 그려진 그림을 찾기 쉽게 한다.

    py tools/gfx_sheet.py [칸수] [행수]

  gfx/sheet_NN.png 로 저장한다. 파일명이 각 칸 위에 찍힌다.
"""
import os
import sys
import glob

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kocfg as C
from PIL import Image, ImageDraw

GFX = os.path.join(C.ROOT, "gfx")
PNG = os.path.join(GFX, "png")

CELL_W, CELL_H = 320, 210
LABEL = 14


def main():
    cols = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    rows = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    per = cols * rows
    files = sorted(glob.glob(os.path.join(PNG, "*.png")))
    n = 0
    for page in range(0, len(files), per):
        chunk = files[page:page + per]
        sheet = Image.new("RGB", (cols * CELL_W, rows * (CELL_H + LABEL)), (24, 24, 28))
        dr = ImageDraw.Draw(sheet)
        for k, f in enumerate(chunk):
            im = Image.open(f).convert("RGBA")
            bg = Image.new("RGBA", im.size, (0, 0, 0, 255))
            im = Image.alpha_composite(bg, im).convert("RGB")
            im.thumbnail((CELL_W - 4, CELL_H - 4))
            cx = (k % cols) * CELL_W
            cy = (k // cols) * (CELL_H + LABEL)
            sheet.paste(im, (cx + 2, cy + LABEL + 2))
            dr.text((cx + 3, cy + 2), os.path.basename(f)[:-4], fill=(200, 220, 160))
        out = os.path.join(GFX, f"sheet_{n:02d}.png")
        sheet.save(out)
        print(out, f"{len(chunk)}장")
        n += 1


if __name__ == "__main__":
    main()
