"""`.ADT` 컨테이너를 다룬다 - DA1 서브 이미지 묶음 (얼굴 애니메이션 등).

구조 (FA09.ADT 실측으로 확정):
    "ADT" + u8 항목수 + u16 크기[항목수] + ... + 항목들(각각 완전한 DA1 스트림)
    첫 항목은 파일 오프셋 489 에서 시작하고, 이후는 크기를 차례로 더한 위치다.
    (헤더 뒤 489 까지의 영역은 용도 미상 - 건드리지 않는다)

    py tools/gfx_adt.py info                  각 ADT 의 목차
    py tools/gfx_adt.py png                   전부 gfx/png_adt/ 에 PNG 로
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kocfg as C
import da1
import da1w                     # 워드모드(flags 0F00) 포함 통합 디코더

GFX = os.path.join(C.ROOT, "gfx")
RAW = os.path.join(GFX, "raw")
OUT = os.path.join(GFX, "png_adt")
ADTS = ["0100B.ADT", "FA03.ADT", "FA08.ADT", "FA09.ADT", "MEG05.ADT", "RA03.ADT"]
FIRST = 489                     # 첫 서브 이미지의 파일 오프셋 (실측)


def entries(data):
    """[(오프셋, 크기)] - 489 부터 각 서브 이미지의 DA1 헤더 크기 필드로 걷는다.

    (헤더의 u16 표는 파일마다 해석이 어긋난다. DA1 스트림은 자기 크기를
    [4:8] 에 들고 있으므로 그것이 정본이다.)
    """
    assert data[:3] == b"ADT"
    cnt = data[3]
    out = []
    off = FIRST
    while off + 8 <= len(data) and data[off:off + 4] == b"DA1\x00":
        size = struct.unpack_from("<I", data, off + 4)[0]
        if size <= 8 or off + size > len(data):
            raise ValueError("오프셋 %d 의 크기 %d 가 파일을 벗어난다" % (off, size))
        out.append((off, size))
        off += size
    if off != len(data):
        raise ValueError("걷기가 %d 에서 멈췄다 (파일 %d)" % (off, len(data)))
    if len(out) != cnt:
        print("  주의: 헤더 항목수 %d != 실제 %d" % (cnt, len(out)))
    return out


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "info"
    os.makedirs(OUT, exist_ok=True)
    from PIL import Image
    total = 0
    for fn in ADTS:
        d = open(os.path.join(RAW, fn), "rb").read()
        ent = entries(d)
        print("%s : %d항목" % (fn, len(ent)))
        for i, (o, s) in enumerate(ent):
            seg = d[o:o + s]
            try:
                m = da1w.decode_full(seg)
                h = da1w.parse_header(seg)
            except Exception as e:
                print("  #%02d %6dB  디코드 실패: %s" % (i, s, e))
                continue
            pal = "pal" if m["palette_raw"] else "no-pal"
            print("  #%02d %6dB  %3dx%-3d @(%3d,%3d) %s"
                  % (i, s, m["w"] * 8, m["h"], h["x"] * 8, h["y"], pal))
            total += 1
            if cmd == "png":
                px = da1w.compose(m)
                raw = m["palette_raw"]
                if raw is None:
                    # 팔레트 없는 차분 - 본체 GDT 의 팔레트를 빌린다
                    base = fn.replace(".ADT", ".GDT")
                    bp = os.path.join(RAW, base)
                    if os.path.isfile(bp):
                        bm = da1.parse_header(open(bp, "rb").read())
                        raw = None  # parse_header 는 팔레트를 안 준다
                    bd = open(bp, "rb").read() if os.path.isfile(bp) else None
                    if bd is not None:
                        bmf = da1.decode_full(bd)
                        raw = bmf["palette_raw"]
                pal16 = da1.palette_rgb(raw, "GRB") if raw else None
                lut = ([pal16[k] for k in range(16)] if pal16
                       else [(k * 17,) * 3 for k in range(16)])
                am = da1w.alpha_mask(m)
                img = Image.new("RGBA", (m["w"] * 8, m["h"]))
                img.putdata([(lut[v][0], lut[v][1], lut[v][2], am[j])
                             for j, v in enumerate(px)])
                img.save(os.path.join(OUT, "%s_%02d.png" % (fn.replace(".", "_"), i)))
    print("서브 이미지 %d장" % total)
    if cmd == "png":
        print("->", OUT)


if __name__ == "__main__":
    main()
