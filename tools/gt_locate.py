"""특정 GDT 가 화면에 떠 있는 프레임을 빠르게 찾는다 (GDT 1~수개만 대조).

팔레트가 달라도 되도록 **에지맵**(왼쪽 픽셀과 색이 다른가)의 재현율로 판정한다.
실측 기준: 그 장면이면 0.98~1.0000, 아니면 0.7 이하로 뚜렷하게 갈린다.

    py tools/gt_locate.py <캡처폴더> <GDT...>
"""
import glob
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import da1

DX, DY = 1, 1


def load(gdt):
    m = da1.decode_full(open(gdt, "rb").read())
    px = np.frombuffer(da1._compose(m), np.uint8).reshape(m["h"], m["w"] * 8)
    am = np.frombuffer(da1.alpha_mask(m), np.uint8).reshape(px.shape) > 0
    e = px[:, 1:] != px[:, :-1]
    mk = am[:, 1:] & am[:, :-1]
    return m["x"] * 8, m["y"], px.shape, e, mk


def main():
    capdir = sys.argv[1]
    refs = [(os.path.basename(g),) + load(g) for g in sys.argv[2:]]
    fs = sorted(glob.glob(os.path.join(capdir, "f*.png")))
    hits = {}
    for f in fs:
        a = np.array(Image.open(f).convert("RGB"))
        for name, x0, y0, shape, e, mk in refs:
            h, w = shape
            sub = a[y0 + DY:y0 + DY + h, x0 + DX:x0 + DX + w]
            if sub.shape[:2] != (h, w):
                continue
            se = (sub[:, 1:] != sub[:, :-1]).any(-1)
            r = ((se == e) & mk).sum() / max(mk.sum(), 1)
            b = hits.get(name)
            if b is None or r > b[0]:
                hits[name] = (r, os.path.basename(f))
            if r > 0.95:
                print("%-14s %.4f  %s" % (name, r, os.path.basename(f)))
    print("--- 최고치 ---")
    for n, (r, f) in hits.items():
        print("%-14s %.4f  %s" % (n, r, f))


if __name__ == "__main__":
    main()
