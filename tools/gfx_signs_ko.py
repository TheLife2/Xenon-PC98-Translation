"""병원 복도 안내판 3장 한국어화 (2026-08-10 조사에서 발견).

    1020.GDT / 1020_3.GDT : 「受付 →」   -> 「접수 →」   (컬러/흑백)
    1030.GDT              : 「← 第2…」  -> 「← 제2진…」 (第2診察室 로 추정, 화면 밖 잘림)

방식
  * 글자마다 직사각 셀을 잡아, 셀 안을 판의 체커 디더로 재구성해 덮는다.
    디더는 주기 2 라서 같은 열/행에서 2씩 떨어진 픽셀을 복사하면 위상이 맞는다.
  * 같은 셀 안에 검정으로 한국어를 그린다 (원본 글자도 검정 획이다).
    판이 기울어 있으므로 오른쪽 글자일수록 셀을 아래(1020)/위(1030)로 내려 잡았다.
  * 셀 밖은 픽셀 단위로 원본 그대로임을 기계 검증한다.

    py tools/gfx_signs_ko.py            미리보기 PNG 만
    py tools/gfx_signs_ko.py --write    gfx/edit/*.GDT 까지
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kocfg as C
import da1
from PIL import Image, ImageDraw, ImageFont

GFX = os.path.join(C.ROOT, "gfx")
FONT = r"C:\Windows\Fonts\gulim.ttc"      # 도트 크기라 굴림이 제일 또렷하다

# cells: (문자, 셀 x1,y1,x2,y2, 폰트 px).  셀 = 지우는 영역이자 그리는 영역.
SIGNS = [
    {
        "name": "1020.GDT", "png": "1020_GDT.png",
        "cells": [("접", 7, 25, 20, 42, 13), ("수", 19, 29, 32, 46, 13)],
    },
    {
        "name": "1020_3.GDT", "png": "1020_3_GDT.png",
        "cells": [("접", 7, 25, 20, 42, 13), ("수", 19, 29, 32, 46, 13)],
    },
    {
        "name": "1030.GDT", "png": "1030_GDT.png",
        "cells": [("제", 527, 30, 538, 45, 13), ("2", 538, 29, 547, 44, 12),
                  ("진", 548, 28, 560, 43, 13)],
    },
]

DARK = 150          # 밝기 합이 이보다 작으면 글자 획 (디더 복원 표본에서 제외)


def refill(img, cells):
    """셀 안 전부를 셀 밖의 디더에서 복사해 덮는다 (주기 2 위상 유지)."""
    px = img.load()
    W, H = img.size

    def inside(x, y):
        return any(c[1] <= x < c[3] and c[2] <= y < c[4] for c in cells)

    n = 0
    for c in cells:
        for y in range(c[2], c[4]):
            for x in range(c[1], c[3]):
                got = None
                for k in range(1, 14):
                    for cy in (y - 2 * k, y + 2 * k):
                        if 0 <= cy < H and not inside(x, cy) \
                                and sum(px[x, cy]) >= DARK:
                            got = px[x, cy]
                            break
                    if got:
                        break
                if got is None:
                    for k in range(1, 14):
                        for cx in (x - 2 * k, x + 2 * k):
                            if 0 <= cx < W and not inside(cx, y) \
                                    and sum(px[cx, y]) >= DARK:
                                got = px[cx, y]
                                break
                        if got:
                            break
                if got is not None:
                    px[x, y] = got
                    n += 1
    return n


def draw_text(img, cells):
    """1비트(안티에일리어싱 없이)로 또렷하게 검정 글자를 얹는다."""
    dr = ImageDraw.Draw(img)
    dr.fontmode = "1"
    for ch, x1, y1, x2, y2, size in cells:
        f = ImageFont.truetype(FONT, size)
        bb = dr.textbbox((0, 0), ch, font=f)
        w, h = bb[2] - bb[0], bb[3] - bb[1]
        cx = x1 + max(0, (x2 - x1 - w) // 2) - bb[0]
        cy = y1 + max(0, (y2 - y1 - 2 - h) // 2) - bb[1]
        dr.text((cx, cy), ch, font=f, fill=(0, 0, 0))


def process(sign, write):
    src = os.path.join(GFX, "raw", sign["name"])
    png = os.path.join(GFX, "png", sign["png"])
    out_png = os.path.join(GFX, "png", sign["png"].replace("_GDT", "_KO"))
    out_gdt = os.path.join(GFX, "edit", sign["name"])

    orig = Image.open(png).convert("RGB")
    img = orig.copy()
    n = refill(img, sign["cells"])
    draw_text(img, sign["cells"])

    po, pn = orig.load(), img.load()
    cells = sign["cells"]
    leak = 0
    for y in range(img.size[1]):
        for x in range(img.size[0]):
            if pn[x, y] != po[x, y] and \
               not any(c[1] <= x < c[3] and c[2] <= y < c[4] for c in cells):
                leak += 1
    print("%s: 덮은 픽셀 %d, 셀 밖 변경 %d (0 이어야 함)" % (sign["name"], n, leak))
    if leak:
        raise SystemExit("셀 밖이 변형됐다")
    img.save(out_png)

    if not write:
        return
    os.makedirs(os.path.join(GFX, "edit"), exist_ok=True)
    r = subprocess.run([sys.executable, os.path.join(C.ROOT, "tools", "da1enc.py"),
                        "frompng", src, out_png, out_gdt],
                       capture_output=True, text=True, encoding="utf-8")
    ok = "MATCHES" in (r.stdout or "")
    a = os.path.getsize(src)
    b = os.path.getsize(out_gdt) if os.path.isfile(out_gdt) else 0
    print("   -> %s  %d -> %d 바이트  검증 %s" % (out_gdt, a, b, "OK" if ok else "실패"))
    if not ok:
        print((r.stdout or "")[-400:], (r.stderr or "")[-200:])
        raise SystemExit(1)
    m = da1.decode_full(open(out_gdt, "rb").read())
    print("   재검증: %dx%d 디코드 성공" % (m["w"] * 8, m["h"]))


def main():
    write = "--write" in sys.argv
    for s in SIGNS:
        process(s, write)
    if not write:
        print("\n미리보기: gfx/png/1020_KO.png, 1020_3_KO.png, 1030_KO.png")
        print("--write 를 붙이면 gfx/edit/ 까지 만듭니다.")


if __name__ == "__main__":
    main()
