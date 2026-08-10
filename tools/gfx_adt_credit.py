"""시작 로고 애니메이션(`0100B.ADT`)의 마지막 프레임에 번역 크레딧을 넣는다.

원리 — **word 모드 인코더를 만들지 않는다.**
  ADT 서브 이미지는 word 모드(flags bit14=0)로 압축돼 있고 우리는 그 인코더가 없다.
  그런데 AGS.EXE 는 `TEST word ptr CS:[0x9a],0x4000` **한 줄로** 디코더를 고른다
  (`1456:0169`, 세워지면 바이트모드 0x7e05, 아니면 워드모드).
  따라서 **flags 에 bit14 를 세우고 이미 검증된 byte 모드 인코더로 다시 쓰면** 게임이 읽는다.

  프레임 28 실측: word 10,645바이트 -> byte 9,293바이트(0.87배). 픽셀·알파 완전 일치.

    py tools/gfx_adt_credit.py            미리보기 PNG 만
    py tools/gfx_adt_credit.py --write    gfx/edit/0100B.ADT 까지

주의
  * ADT 컨테이너는 각 서브 이미지의 **헤더 크기 필드로 걸어서** 자른다(gfx_adt.entries).
    프레임 크기가 바뀌면 뒤가 밀리므로, 마지막 프레임만 손대면 파일 꼬리만 바뀐다.
  * 프레임 28 은 로고가 완성된 상태로 가장 오래 보인다.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kocfg as C
import da1
import da1w
import da1enc
from gfx_adt import entries
from PIL import Image, ImageDraw, ImageFont

GFX = os.path.join(C.ROOT, "gfx")
RAW = os.path.join(GFX, "raw")
SRC = os.path.join(RAW, "0100B.ADT")
BASE = os.path.join(RAW, "0100B.GDT")
OUT_ADT = os.path.join(GFX, "edit", "0100B.ADT")
PNG_DIR = os.path.join(GFX, "png")

FRAME = 28                      # 마지막 프레임 (로고 완성 상태)
TEXT = "번역 : THL.kr"
FONT = (r"C:\Windows\Fonts\NotoSansKR-VF.ttf", "Medium")
SIZE = 15

# 크레딧을 놓을 자리 (프레임 좌표계, 448x140).
# 로고가 프레임을 거의 채우므로(98.5%) 글자 아래 여백에 넣는다.
BOX = (0, 122, 448, 140)


def load_palette():
    m = da1.decode_full(open(BASE, "rb").read())
    return m["palette_raw"]


def main():
    write = "--write" in sys.argv
    d = open(SRC, "rb").read()
    ent = entries(d)
    o, s = ent[FRAME]
    seg = d[o:o + s]

    # 차분 프레임이므로 **VRAM 을 유지하며 0..FRAME 을 순서대로 그려야** 한다.
    # (프레임마다 빈 VRAM 으로 시작하면 역참조가 0 을 읽어 가로 줄무늬가 생긴다)
    planes = [bytearray(da1w.VRAM_SZ + da1w.PAD) for _ in range(4)]
    mask = bytearray(da1w.VRAM_SZ + da1w.PAD)
    bm = da1.decode_full(open(BASE, "rb").read())
    for p in range(4):
        src = bm["planes"][p]
        planes[p][:len(src)] = src[:len(planes[p])]
    for i in range(FRAME):
        oo, ss = ent[i]
        da1w.decode_full(d[oo:oo + ss], strict=True, planes=planes, mask=mask)

    m = da1w.decode_full(seg, strict=True, planes=planes, mask=mask)
    h = da1w.parse_header(seg)
    W, H = m["w"] * 8, m["h"]
    px = bytearray(da1w.compose(m))
    am = bytearray(da1w.alpha_mask(m))
    print("프레임 %d: %dx%d @(%d,%d) 원본 %d바이트" % (FRAME, W, H, h["x"], h["y"], s))

    pal_raw = load_palette()
    pal = da1.palette_rgb(pal_raw, "GRB")

    # 크레딧을 1비트 마스크로 렌더
    mask = Image.new("L", (W, H), 0)
    dr = ImageDraw.Draw(mask)
    dr.fontmode = "1"
    f = ImageFont.truetype(FONT[0], SIZE)
    f.set_variation_by_name(FONT[1])
    bb = dr.textbbox((0, 0), TEXT, font=f)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    if tw > BOX[2] - BOX[0] or th > BOX[3] - BOX[1]:
        raise SystemExit("크레딧이 상자보다 크다 (%dx%d)" % (tw, th))
    dr.text((BOX[0] + (BOX[2] - BOX[0] - tw) // 2 - bb[0],
             BOX[1] + (BOX[3] - BOX[1] - th) // 2 - bb[1]),
            TEXT, font=f, fill=255)
    mp = mask.load()

    # 글자색: 팔레트에서 가장 밝은 색
    idx_white = max(range(16), key=lambda i: sum(pal[i]))
    print("  글자색 인덱스 %d = #%02X%02X%02X" % (idx_white, *pal[idx_white]))

    # 크레딧 자리가 원본에서 비어 있는지(=로고와 겹치지 않는지) 확인
    clash = sum(1 for y in range(BOX[1], BOX[3]) for x in range(BOX[0], BOX[2])
                if mp[x, y] and am[y * W + x] and px[y * W + x] != 0)
    print("  로고와 겹치는 글자 픽셀: %d" % clash)

    n = 0
    for y in range(H):
        for x in range(W):
            if mp[x, y]:
                px[y * W + x] = idx_white
                n += 1
    print("  크레딧 픽셀 %d개 삽입" % n)

    # 마지막 프레임은 **완성된 화면을 통째로** 그리게 만든다.
    # 원본은 앞 프레임이 남긴 VRAM 을 역참조하는 차분이지만, 우리가 새로 쓰는 것은
    # 자기완결형 byte 모드 스프라이트다 - 사각형 전체를 불투명으로 칠하면
    # 앞 프레임이 무엇을 남겼든 결과가 같아진다.
    am = bytearray(b"\xff" * (W * H))

    # 미리보기 (프레임 단독)
    lut = [tuple(c) for c in pal]
    img = Image.new("RGBA", (W, H))
    img.putdata([(lut[v][0], lut[v][1], lut[v][2], am[i])
                 for i, v in enumerate(px)])
    p = os.path.join(PNG_DIR, "0100B_frame%02d_KO.png" % FRAME)
    img.save(p)
    print("  미리보기:", p)

    # byte 모드(flags bit14)로 인코딩
    enc = da1enc.encode(bytes(px), W, H, h["x"], h["y"],
                        palette=None, alpha=bytes(am), flags=0x4F00)
    print("  byte 인코딩: %d바이트 (원본 %d, %.2f배)" % (len(enc), s, len(enc) / s))

    # 자기 디코더로 되읽어 검증
    m2 = da1.decode_full(enc, strict=True)
    if bytes(da1._compose(m2)) != bytes(px):
        raise SystemExit("재디코드 픽셀 불일치")
    if bytes(da1.alpha_mask(m2)) != bytes(am):
        raise SystemExit("재디코드 알파 불일치")
    print("  재검증: 픽셀·알파 완전 일치")

    if not write:
        print("\n--write 를 붙이면 gfx/edit/0100B.ADT 를 만듭니다.")
        return 0

    os.makedirs(os.path.dirname(OUT_ADT), exist_ok=True)
    out = bytearray(d[:o]) + bytearray(enc) + bytearray(d[o + s:])
    open(OUT_ADT, "wb").write(out)
    print("\n  %s : %d -> %d 바이트" % (OUT_ADT, len(d), len(out)))

    # 컨테이너 전체를 다시 걸어 검증
    nd = bytes(out)
    ne = entries(nd)
    if len(ne) != len(ent):
        raise SystemExit("프레임 수가 %d -> %d 로 변했다" % (len(ent), len(ne)))
    ok = 0
    for i, (oo, ss) in enumerate(ne):
        sub = nd[oo:oo + ss]
        mm = (da1 if da1.parse_header(sub)["byte_mode"] else da1w).decode_full(
            sub, strict=True)
        ok += 1
    print("  컨테이너 재검증: %d/%d 프레임 디코드 성공" % (ok, len(ne)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
