"""캡처 PNG 와 da1 디코드 결과를 맞춰 **화면 원점 오프셋**을 확정하고,
캡처를 16색 인덱스(=VRAM 평면 4장)로 되돌린다.

    py tools/gt_calib.py offset <캡처.png> <GDT>     오프셋 탐색
    py tools/gt_calib.py vram   <캡처.png> <출력.npz> [dx dy]

원리
  PC-98 16색은 채널당 4비트다. np2 는 그것을 값*0x11 로 그린다.
  따라서 캡처 RGB 는 (r/17,g/17,b/17) 로 **무손실 복원**되고,
  화면 팔레트만 알면 픽셀 -> 4비트 인덱스 -> 평면 4장으로 정확히 되돌릴 수 있다.
"""
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import da1

SCREEN_W, SCREEN_H = 640, 400


def load_capture(path):
    a = np.array(Image.open(path).convert("RGB")).astype(np.int32)
    return a


def gdt_render(path):
    d = open(path, "rb").read()
    m = da1.decode_full(d)
    px = np.frombuffer(da1._compose(m), dtype=np.uint8).reshape(m["h"], m["w"] * 8)
    am = np.frombuffer(da1.alpha_mask(m), dtype=np.uint8).reshape(px.shape)
    pal = da1.palette_rgb(m["palette_raw"], "GRB")
    return m, px, am, pal


def cmd_offset(cap_path, gdt_path):
    a = load_capture(cap_path)
    m, px, am, pal = gdt_render(gdt_path)
    if pal is None:
        raise SystemExit("팔레트 없는 GDT 로는 보정할 수 없습니다")
    lut = np.array(pal, dtype=np.int32)                  # 16x3
    ref = lut[px]                                        # h x w x 3
    x0, y0 = m["x"] * 8, m["y"]
    best = []
    for dy in range(-3, 4):
        for dx in range(-3, 4):
            sy, sx = y0 + dy, x0 + dx
            if sy < 0 or sx < 0 or sy + px.shape[0] > a.shape[0] \
                    or sx + px.shape[1] > a.shape[1]:
                continue
            sub = a[sy:sy + px.shape[0], sx:sx + px.shape[1]]
            ok = ((sub == ref).all(2) | (am == 0))
            best.append((ok.mean(), dx, dy, int((~ok).sum())))
    best.sort(reverse=True)
    print("이미지 %s  rect x=%d..%d y=%d..%d  (불투명 %d px)"
          % (os.path.basename(gdt_path), x0, x0 + px.shape[1],
             y0, y0 + px.shape[0], int((am > 0).sum())))
    for r, dx, dy, bad in best[:8]:
        print("  dx=%+d dy=%+d  일치율 %.4f  불일치 %d px" % (dx, dy, r, bad))
    return best[0][1], best[0][2]


def cmd_vram(cap_path, out_path, dx=0, dy=1):
    """캡처 -> 16색 인덱스 화면(400x640) + VRAM 평면 4장(400x80)."""
    a = load_capture(cap_path)
    scr = a[dy:dy + SCREEN_H, dx:dx + SCREEN_W]
    if scr.shape[:2] != (SCREEN_H, SCREEN_W):
        raise SystemExit("캡처가 640x400 을 못 담습니다: %s" % (a.shape,))
    q, rem = np.divmod(scr, 17)
    if rem.any():
        n = int((rem.any(2)).sum())
        print("  주의: 17 의 배수가 아닌 픽셀 %d 개 (스케일/보간 의심)" % n)
    cols = q.reshape(-1, 3)
    uniq, inv = np.unique(cols, axis=0, return_inverse=True)
    print("  화면에 쓰인 색 %d 종" % len(uniq))
    for i, c in enumerate(uniq):
        print("    %2d  RGB4=%X%X%X  %d px" % (i, c[0], c[1], c[2], int((inv == i).sum())))
    np.savez_compressed(out_path, rgb4=q.astype(np.uint8))
    print("->", out_path)


def main():
    cmd = sys.argv[1]
    if cmd == "offset":
        cmd_offset(sys.argv[2], sys.argv[3])
    elif cmd == "vram":
        dx = int(sys.argv[4]) if len(sys.argv) > 4 else 0
        dy = int(sys.argv[5]) if len(sys.argv) > 5 else 1
        cmd_vram(sys.argv[2], sys.argv[3], dx, dy)
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
