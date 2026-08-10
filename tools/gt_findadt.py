"""캡처 프레임 열에서 **word-mode(.ADT) 서브 이미지가 그려진 순간**을 찾는다.

.ADT 항목은 헤더에 (x, w, y, h) 를 들고 있다. 그 사각형은 파일마다 제각각이라
'연속 두 프레임의 변화 영역이 어느 항목의 사각형 안에 정확히 들어가는가' 로 짚을 수 있다.

    py tools/gt_findadt.py <캡처폴더>

출력 : 프레임쌍마다 변화 bbox 와, 그 bbox 를 감싸는 .ADT 항목 후보들.
"""
import glob
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import da1
import gfx_adt

DX, DY = 1, 1


def adt_rects():
    out = []
    for fn in gfx_adt.ADTS:
        d = open(os.path.join(gfx_adt.RAW, fn), "rb").read()
        for i, (o, s) in enumerate(gfx_adt.entries(d)):
            h = da1.parse_header(d[o:o + s])
            out.append(("%s#%02d" % (fn, i), h["x"] * 8, (h["x"] + h["w"]) * 8,
                        h["y"], h["y"] + h["h"], s))
    return out


def main():
    capdir = sys.argv[1]
    rects = adt_rects()
    fs = sorted(glob.glob(os.path.join(capdir, "f*.png")))
    prev = None
    lines = []
    for f in fs:
        a = np.array(Image.open(f).convert("RGB"))
        if prev is not None:
            ch = (a != prev).any(2)
            nz = np.argwhere(ch)
            if len(nz):
                y0 = int(nz[:, 0].min()) - DY
                y1 = int(nz[:, 0].max()) - DY + 1
                x0 = int(nz[:, 1].min()) - DX
                x1 = int(nz[:, 1].max()) - DX + 1
                cand = [n for (n, rx0, rx1, ry0, ry1, sz) in rects
                        if rx0 <= x0 and x1 <= rx1 and ry0 <= y0 and y1 <= ry1]
                if cand:
                    lines.append("%s  n=%6d  x=%3d..%3d y=%3d..%3d  후보 %s"
                                 % (os.path.basename(f), len(nz), x0, x1, y0, y1,
                                    ",".join(cand[:6])))
        prev = a
    print("\n".join(lines) if lines else "후보 없음")
    with open(os.path.join(capdir, "adt_candidates.txt"), "w",
              encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
