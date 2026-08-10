"""`.ADT` 애니메이션을 **누적 합성**해 렌더한다.

ADT 서브 이미지는 차분 프레임이다 - 각 프레임이 이전 화면 위에 덧그린다.
그래서 한 장만 따로 풀면 깨져 보인다. VRAM 한 벌을 유지하며 순서대로 얹어야
실제 화면이 나온다.

    py tools/gfx_adt_anim.py                    전부
    py tools/gfx_adt_anim.py 0100B.ADT          하나만
    py tools/gfx_adt_anim.py 0100B.ADT --base 0100B.GDT   바탕 그림 위에 얹기

산출물: gfx/png_anim/<컨테이너>_NN.png  (누적 상태)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kocfg as C
import da1
import da1w
from gfx_adt import entries, ADTS

GFX = os.path.join(C.ROOT, "gfx")
RAW = os.path.join(GFX, "raw")
OUT = os.path.join(GFX, "png_anim")
STRIDE, VRAM_H = 80, 400


def palette_for(name):
    """차분에는 팔레트가 없다. 같은 이름의 GDT 에서 빌려 온다."""
    base = name.replace(".ADT", ".GDT")
    p = os.path.join(RAW, base)
    if os.path.isfile(p):
        m = da1.decode_full(open(p, "rb").read())
        if m["palette_raw"]:
            return m["palette_raw"]
    for cand in ("0100B.GDT", "ROGO.GDT", "0010.GDT"):
        p = os.path.join(RAW, cand)
        if os.path.isfile(p):
            m = da1.decode_full(open(p, "rb").read())
            if m["palette_raw"]:
                return m["palette_raw"]
    return None


def render(planes, pal_raw):
    from PIL import Image
    lut = ([tuple(c) for c in da1.palette_rgb(pal_raw, "GRB")] if pal_raw
           else [(i * 17,) * 3 for i in range(16)])
    px = bytearray(STRIDE * 8 * VRAM_H)
    for y in range(VRAM_H):
        for bx in range(STRIDE):
            o = y * STRIDE + bx
            b0, b1, b2, b3 = (planes[0][o], planes[1][o], planes[2][o], planes[3][o])
            base = y * (STRIDE * 8) + bx * 8
            for bit in range(8):
                sh = 7 - bit
                px[base + bit] = (((b0 >> sh) & 1) | (((b1 >> sh) & 1) << 1)
                                  | (((b2 >> sh) & 1) << 2) | (((b3 >> sh) & 1) << 3))
    img = Image.new("RGB", (STRIDE * 8, VRAM_H))
    img.putdata([lut[v] for v in px])
    return img


def run(name, base_gdt=None):
    os.makedirs(OUT, exist_ok=True)
    d = open(os.path.join(RAW, name), "rb").read()
    ent = entries(d)
    pal = palette_for(name)

    planes = [bytearray(STRIDE * VRAM_H) for _ in range(4)]
    if base_gdt:
        bm = da1.decode_full(open(os.path.join(RAW, base_gdt), "rb").read())
        for pi in range(4):
            src = bm["planes"][pi]
            planes[pi][:len(src)] = src[:len(planes[pi])]
        if bm["palette_raw"]:
            pal = bm["palette_raw"]

    print("%s : %d프레임 (팔레트 %s)"
          % (name, len(ent), "있음" if pal else "없음-회색조"))
    for i, (o, s) in enumerate(ent):
        seg = d[o:o + s]
        m = da1w.decode_full(seg, strict=True)
        # 이 프레임이 쓴 픽셀만 누적 VRAM 에 반영
        msk = m["mask"]
        for pi in range(4):
            src, dst = m["planes"][pi], planes[pi]
            for k in range(len(msk)):
                if msk[k]:
                    dst[k] = src[k]
        render(planes, pal).save(
            os.path.join(OUT, "%s_%02d.png" % (name.replace(".", "_"), i)))
    print("  ->", OUT)


def main():
    argv = sys.argv[1:]
    base = None
    if "--base" in argv:
        k = argv.index("--base")
        base = argv[k + 1]
        argv = argv[:k] + argv[k + 2:]          # 옵션과 그 값을 함께 뺀다
    names = [a for a in argv if not a.startswith("--")]
    for name in (names or ADTS):
        run(name, base)


if __name__ == "__main__":
    main()
