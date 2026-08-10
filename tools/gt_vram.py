"""캡처 PNG -> **VRAM 평면 4장** (정답 데이터).

캡처는 창 클라이언트 642x402 이고 PC-98 화면 640x400 은 그 안 (1,1) 에 있다
(tools/gt_calib.py 로 0010.GDT 에지맵 완전일치로 확정).
PC-98 16색은 채널당 4비트라 np2 가 값*0x11 로 그린다 -> RGB 는 무손실이다.
따라서 화면 팔레트만 알면 픽셀 -> 4비트 인덱스 -> 평면 4장으로 정확히 되돌아간다.

화면 팔레트는 **그 순간 화면에 떠 있는 byte-mode GDT** 로부터 배운다.
(GDT 파일 안의 팔레트가 아니라 실제 화면 색이다 - 게임이 페이드 등으로 바꾼다)

    py tools/gt_vram.py check  <프레임.png> <기준.GDT>
        기준 GDT 를 디코드해 화면과 대조한다. 픽셀 완전일치면 파이프라인이 정확하다.

    py tools/gt_vram.py dump   <프레임.png> <기준.GDT> <출력.npz>
        화면 전체를 인덱스맵 + VRAM 평면 4장으로 저장한다.

    py tools/gt_vram.py diff   <before.png> <after.png> <기준.GDT> <출력.npz>
        두 프레임의 VRAM 을 비교해 '무엇이 그려졌는가' 를 뽑는다.
        word-mode 스트림 하나가 만든 결과가 바로 이것이다.
"""
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import da1

DX, DY = 1, 1
SCREEN_W, SCREEN_H = 640, 400
STRIDE = 80


def screen(path):
    """캡처 PNG -> 400x640x3 uint8 (PC-98 화면만)."""
    a = np.array(Image.open(path).convert("RGB"))
    s = a[DY:DY + SCREEN_H, DX:DX + SCREEN_W]
    if s.shape[:2] != (SCREEN_H, SCREEN_W):
        raise SystemExit("캡처가 640x400 을 못 담습니다: %s" % (a.shape,))
    return s


def key32(rgb):
    r = rgb.astype(np.int32)
    return (r[..., 0] << 16) | (r[..., 1] << 8) | r[..., 2]


def ref_index(gdt_path):
    d = open(gdt_path, "rb").read()
    m = da1.decode_full(d)
    px = np.frombuffer(da1._compose(m), dtype=np.uint8).reshape(m["h"], m["w"] * 8)
    am = np.frombuffer(da1.alpha_mask(m), dtype=np.uint8).reshape(px.shape) > 0
    return m, px, am


def learn_palette(scr, gdt_path):
    """화면에 떠 있는 기준 GDT 로부터 '색 -> 인덱스' 사전을 만든다."""
    m, px, am = ref_index(gdt_path)
    x0, y0 = m["x"] * 8, m["y"]
    sub = scr[y0:y0 + px.shape[0], x0:x0 + px.shape[1]]
    k = key32(sub)
    pal = {}
    stats = []
    for i in range(16):
        sel = (px == i) & am
        n = int(sel.sum())
        if not n:
            stats.append((i, 0, None, 0.0))
            continue
        vals, cnt = np.unique(k[sel], return_counts=True)
        top = int(vals[cnt.argmax()])
        pal[top] = i
        stats.append((i, n, top, cnt.max() / n))
    return pal, stats, m, px, am, (x0, y0)


def to_planes(idx):
    """400x640 인덱스맵 -> 4 x (400x80) uint8 평면."""
    b = idx.reshape(SCREEN_H, STRIDE, 8)
    planes = []
    for p in range(4):
        bit = (b >> p) & 1
        v = np.zeros((SCREEN_H, STRIDE), dtype=np.uint8)
        for j in range(8):
            v |= (bit[:, :, j] << (7 - j)).astype(np.uint8)
        planes.append(v)
    return np.stack(planes)


def index_map(scr, pal):
    k = key32(scr)
    out = np.full(k.shape, 255, dtype=np.uint8)
    for c, i in pal.items():
        out[k == c] = i
    return out


def cmd_check(frame, gdt):
    scr = screen(frame)
    pal, stats, m, px, am, (x0, y0) = learn_palette(scr, gdt)
    print("기준 %s  rect x=%d..%d y=%d..%d" %
          (os.path.basename(gdt), x0, x0 + px.shape[1], y0, y0 + px.shape[0]))
    for i, n, top, pur in stats:
        if n:
            print("  idx %2d  %7d px  화면색 #%06X  순도 %.4f" % (i, n, top, pur))
        else:
            print("  idx %2d  (미사용)" % i)
    idx = index_map(scr, pal)
    sub = idx[y0:y0 + px.shape[0], x0:x0 + px.shape[1]]
    bad = int(((sub != px) & am).sum())
    tot = int(am.sum())
    print("기준 rect 픽셀 %d 중 불일치 %d (%.4f%%)" % (tot, bad, 100.0 * bad / tot))
    unk = int((idx == 255).sum())
    print("화면 전체에서 팔레트에 없는 픽셀 %d / %d" % (unk, idx.size))
    return bad, tot


def cmd_dump(frame, gdt, out):
    scr = screen(frame)
    pal, stats, m, px, am, xy = learn_palette(scr, gdt)
    idx = index_map(scr, pal)
    idx2 = np.where(idx == 255, 0, idx)
    planes = to_planes(idx2)
    np.savez_compressed(out, index=idx, planes=planes,
                        unknown=(idx == 255))
    print("-> %s  (미지 픽셀 %d)" % (out, int((idx == 255).sum())))


def cmd_diff(before, after, gdt, out):
    sb, sa = screen(before), screen(after)
    pal, *_ = learn_palette(sa, gdt)
    ib, ia = index_map(sb, pal), index_map(sa, pal)
    ch = ib != ia
    nz = np.argwhere(ch)
    if len(nz):
        y0, y1 = nz[:, 0].min(), nz[:, 0].max()
        x0, x1 = nz[:, 1].min(), nz[:, 1].max()
        print("바뀐 픽셀 %d  y=%d..%d x=%d..%d  (바이트열 x=%d..%d)"
              % (len(nz), y0, y1, x0, x1, x0 // 8, x1 // 8))
    else:
        print("바뀐 픽셀 없음")
    np.savez_compressed(out, before=ib, after=ia, changed=ch,
                        planes_before=to_planes(np.where(ib == 255, 0, ib)),
                        planes_after=to_planes(np.where(ia == 255, 0, ia)))
    print("->", out)


def main():
    c = sys.argv[1]
    if c == "check":
        cmd_check(sys.argv[2], sys.argv[3])
    elif c == "dump":
        cmd_dump(sys.argv[2], sys.argv[3], sys.argv[4])
    elif c == "diff":
        cmd_diff(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
