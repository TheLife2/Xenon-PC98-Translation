"""시작 로고 화면에 번역 크레딧을 「별도 스프라이트」로 표시 (2026-08-10 사용자 지시).

원리
  로고 장면은 AGS.EXE 가 하드코딩으로 ROGO.GDT(로고) + 0100BB.GDT(저작권 배너,
  화면 y324..348)를 그린다. DA1 파일은 헤더에 자기 좌표·크기를 갖고 있으므로,
  **배너의 캔버스를 아래로 24줄 늘려(24->48) 그 안에 크레딧을 넣으면**
  기존 표시 호출이 크레딧까지 그려 준다. ROGO 는 건드리지 않고,
  엑스박스 화면(y348..372)은 원래 검정이라 검정 배경 + 흰 글자가 자연스럽게 얹힌다.

  (지난번 ROGO 안에 넣었을 때 잘린 원인이 바로 이 배너다 - 배너가 y324..348 을
   나중에 덮어 그린다. 이번엔 그 배너 자신에 넣으므로 덮일 것이 없다.)

    py tools/gfx_credit_banner.py            미리보기 (gfx/png/0100BB_KO.png)
    py tools/gfx_credit_banner.py --write    gfx/edit/0100BB.GDT 까지

주의: 세로 크기가 원본과 달라지므로 gfx_build.py 의 크기 검사에
0100BB.GDT 를 예외로 등록해 두었다 (x·y·w 는 그대로여야 한다).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kocfg as C
import da1
import da1enc
from PIL import Image, ImageDraw, ImageFont

GFX = os.path.join(C.ROOT, "gfx")
SRC = os.path.join(GFX, "raw", "0100BB.GDT")
OUT_PNG = os.path.join(GFX, "png", "0100BB_KO.png")
OUT_GDT = os.path.join(GFX, "edit", "0100BB.GDT")

EXTRA = 24                      # 아래로 늘리는 줄 수
TEXT = "번역 : THL.kr"
FONT = (r"C:\Windows\Fonts\NotoSansKR-VF.ttf", "Medium")   # OFL - 배포 안전


def main():
    write = "--write" in sys.argv
    src = open(SRC, "rb").read()
    m = da1.decode_full(src)
    h = da1.parse_header(src)
    W, H = m["w"] * 8, m["h"]
    pal = da1.palette_rgb(m["palette_raw"], "GRB")
    lut = [pal[i] for i in range(16)]

    # 원본 24줄 + 검정 24줄 캔버스
    img = Image.new("RGB", (W, H + EXTRA), (0, 0, 0))
    px_src = da1._compose(m)
    img.putdata([lut[v] for v in px_src] + [(0, 0, 0)] * (W * EXTRA))

    dr = ImageDraw.Draw(img)
    dr.fontmode = "1"
    f = ImageFont.truetype(FONT[0], 16)
    f.set_variation_by_name(FONT[1])
    bb = dr.textbbox((0, 0), TEXT, font=f)
    dr.text(((W - (bb[2] - bb[0])) // 2 - bb[0],
             H + (EXTRA - (bb[3] - bb[1])) // 2 - bb[1] - 1),
            TEXT, font=f, fill=(255, 255, 255))
    img.save(OUT_PNG)
    print("미리보기:", OUT_PNG, img.size)

    # 원본 24줄이 바이트 단위로 그대로인지 확인
    top = list(img.crop((0, 0, W, H)).getdata())
    orig = [lut[v] for v in px_src]
    assert top == orig, "원본 배너 부분이 변형됐다"
    print("원본 배너 24줄: 무변형 확인")

    if not write:
        print("--write 를 붙이면 gfx/edit/0100BB.GDT 를 만듭니다.")
        return 0

    # 팔레트 인덱스로 변환 (검정/흰색 모두 팔레트에 있다)
    inv = {}
    for i, c in enumerate(lut):
        inv.setdefault(c, i)
    pix = bytearray()
    missing = set()
    for c in img.getdata():
        if c in inv:
            pix.append(inv[c])
        else:
            missing.add(c)
            pix.append(min(range(16), key=lambda i: sum((a - b) ** 2 for a, b
                                                        in zip(lut[i], c))))
    if missing:
        print("팔레트 밖 색 %d종 -> 최근접 매핑" % len(missing))

    enc = da1enc.encode(bytes(pix), W, H + EXTRA, h["x"], h["y"],
                        palette=m["palette_raw"], flags=h["flags"])
    os.makedirs(os.path.dirname(OUT_GDT), exist_ok=True)
    open(OUT_GDT, "wb").write(enc)

    m2 = da1.decode_full(enc)
    h2 = da1.parse_header(enc)
    px2 = da1._compose(m2)
    same = list(px2) == list(pix)
    print("wrote %s : %d -> %d 바이트" % (OUT_GDT, len(src), len(enc)))
    print("헤더: (%d,%d) %dx%d  (원본 y·x·폭 유지, 높이 %d->%d)"
          % (h2["x"] * 8, h2["y"], h2["w"] * 8, h2["h"], H, h2["h"]))
    print("재검증:", "픽셀 완전 일치" if same else "!! 불일치")
    return 0 if same else 1


if __name__ == "__main__":
    sys.exit(main())
