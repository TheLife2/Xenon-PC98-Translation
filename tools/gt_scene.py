"""캡처 프레임마다 '지금 화면에 떠 있는 GDT 가 무엇인가' 를 판정한다.

팔레트가 달라도 되도록 **에지맵**(왼쪽 픽셀과 색이 다른가)으로 대조한다.
0010.GDT 로 실측했을 때 일치하는 프레임은 재현율 1.0000 이 나오고
아닌 프레임은 0.7 이하다 - 경계가 뚜렷하다.

    py tools/gt_scene.py cache                      gfx/raw/*.GDT 전부 디코드해 캐시
    py tools/gt_scene.py map <캡처폴더> [간격]      프레임 -> GDT 지도
"""
import glob
import os
import pickle
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kocfg as C
import da1

RAW = os.path.join(C.ROOT, "gfx", "raw")
CACHE = os.path.join(C.OUT_DIR, "gt", "gdt_edges.pkl")
DX, DY = 1, 1


def edges(px, am):
    e = px[:, 1:] != px[:, :-1]
    m = am[:, 1:] & am[:, :-1]
    return e, m


def build_cache():
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    out = {}
    for f in sorted(glob.glob(os.path.join(RAW, "*.GDT"))):
        d = open(f, "rb").read()
        try:
            m = da1.decode_full(d)
        except Exception as ex:
            print("  skip %s: %s" % (os.path.basename(f), ex))
            continue
        px = np.frombuffer(da1._compose(m), np.uint8).reshape(m["h"], m["w"] * 8)
        am = np.frombuffer(da1.alpha_mask(m), np.uint8).reshape(px.shape) > 0
        e, mk = edges(px, am)
        out[os.path.basename(f)] = (m["x"] * 8, m["y"], px.shape,
                                    np.packbits(e), np.packbits(mk))
    pickle.dump(out, open(CACHE, "wb"), 2)
    print("GDT %d개 캐시 -> %s" % (len(out), CACHE))


def load_cache():
    c = pickle.load(open(CACHE, "rb"))
    out = {}
    for k, (x0, y0, shape, pe, pm) in c.items():
        es = (shape[0], shape[1] - 1)
        e = np.unpackbits(pe)[:es[0] * es[1]].reshape(es).astype(bool)
        mk = np.unpackbits(pm)[:es[0] * es[1]].reshape(es).astype(bool)
        out[k] = (x0, y0, shape, e, mk)
    return out


def cmd_map(capdir, step=1):
    cache = load_cache()
    fs = sorted(glob.glob(os.path.join(capdir, "f*.png")))[::step]
    rows = []
    for f in fs:
        a = np.array(Image.open(f).convert("RGB"))
        best = (0.0, "-")
        for name, (x0, y0, shape, e, mk) in cache.items():
            h, w = shape
            sub = a[y0 + DY:y0 + DY + h, x0 + DX:x0 + DX + w]
            if sub.shape[:2] != (h, w):
                continue
            se = (sub[:, 1:] != sub[:, :-1]).any(-1)
            r = ((se == e) & mk).sum() / max(mk.sum(), 1)
            if r > best[0]:
                best = (r, name)
        rows.append((os.path.basename(f), best[1], best[0]))
        print("%s  %-14s %.4f" % rows[-1])
    with open(os.path.join(capdir, "scene_map.tsv"), "w") as fh:
        for r in rows:
            fh.write("%s\t%s\t%.4f\n" % r)


def main():
    if sys.argv[1] == "cache":
        build_cache()
    elif sys.argv[1] == "map":
        cmd_map(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 1)
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
