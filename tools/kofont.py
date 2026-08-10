"""할당표대로 한글 글리프를 PC-98 폰트 시트에 그려 넣는다.

폰트 시트 좌표 규칙 (NP2kai font/fontmake.c:308-310, font/fontpc98.c 에서 확정,
区16点1 = '亜' 로 실측 검증)

    x = 16 * 区                     区   = JIS 상위바이트 - 0x20   (1..94)
    y = 16 * (点 + 32)              点   = JIS 하위바이트 - 0x20   (1..94)
    y = 0..15                       8x16 반각(ANK) 256자 띠
    1bpp bottom-up BMP, stride 256, 비트 0 = 잉크 (로더가 반전해서 읽는다)

출력은 두 벌 :
    out/font.tmp     Neko Project II 계열
    out/anex86.bmp   Anex86  (포맷 동일)
"""
import os
import sys
import struct

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kocfg as C

try:
    from PIL import Image, ImageFont, ImageDraw
except ImportError:
    raise SystemExit("Pillow 가 필요합니다:  py -m pip install pillow")

W = H = 2048
STRIDE = 256

FONT_CANDIDATES = [
    (r"C:\Windows\Fonts\gulim.ttc", 0),      # 굴림 - 16px 비트맵 힌팅이 가장 또렷하다
    (r"C:\Windows\Fonts\gulim.ttc", 1),      # 굴림체
    (r"C:\Windows\Fonts\batang.ttc", 0),
    (r"C:\Windows\Fonts\malgun.ttf", 0),
]


def pick_font(size=16):
    for path, idx in FONT_CANDIDATES:
        if not os.path.exists(path):
            continue
        try:
            f = ImageFont.truetype(path, size, index=idx)
            im = Image.new("L", (size + 2, size + 2), 0)
            ImageDraw.Draw(im).text((0, 0), "한", font=f, fill=255)
            if im.getbbox():
                return f, f"{os.path.basename(path)}#{idx}"
        except OSError:
            continue
    raise SystemExit("쓸 수 있는 한글 폰트를 못 찾았습니다")


def render(ch, font, dy=-1, thr=110):
    im = Image.new("L", (18, 18), 0)
    ImageDraw.Draw(im).text((0, dy), ch, font=font, fill=255)
    px = im.load()
    return [sum(1 << (15 - x) for x in range(16) if px[x, y] > thr) for y in range(16)]


def sjis_to_ku_ten(b):
    s1, s2 = b[0], b[1]
    ku = (s1 - 0x81) * 2 + 1 if s1 <= 0x9F else (s1 - 0xE0) * 2 + 63
    if s2 >= 0x9F:
        ku += 1
        ten = s2 - 0x9E
    else:
        ten = s2 - 0x3F
        if s2 > 0x7F:
            ten -= 1
    return ku, ten


def build(table, src, dst, font=None, name=""):
    d = bytearray(open(src, "rb").read())
    off = struct.unpack_from("<I", d, 10)[0]
    for ch, code in table.items():
        ku, ten = sjis_to_ku_ten(code)
        bm = render(ch, font)
        x0, y0 = 16 * ku, 16 * (ten + 32)
        for r in range(16):
            base = off + (H - 1 - (y0 + r)) * STRIDE + (x0 >> 3)
            v = bm[r] & 0xFFFF
            d[base] = (~(v >> 8)) & 0xFF
            d[base + 1] = (~v) & 0xFF
    open(dst, "wb").write(bytes(d))
    print(f"  {os.path.basename(dst)}: {len(table)}자 기록 ({name})")


def main():
    table = C.load_table()
    if not table:
        raise SystemExit("할당표가 비었습니다. koalloc.py 를 먼저 돌리세요.")
    font, name = pick_font()
    print(f"폰트: {name}")
    build(table, C.FONT_SRC, os.path.join(C.OUT_DIR, "font.tmp"), font, name)
    build(table, C.ANEX_SRC, os.path.join(C.OUT_DIR, "anex86.bmp"), font, name)


if __name__ == "__main__":
    main()
