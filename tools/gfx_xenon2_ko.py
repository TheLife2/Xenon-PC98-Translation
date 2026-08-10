"""XENON2.GDT (엔딩 타이틀) 한국어판 만들기 — 그래픽 번역 실증.

    肉奴隷            -> 육 노 예
    トレイシーの憂鬱   -> 트레이시의 우울

원본에서 글자만 지우고 같은 자리에 한글을 그린다.
배경(분홍 곡선 그라데이션)은 건드리지 않는다.

    py tools/gfx_xenon2_ko.py                     미리보기 PNG 만 만든다
    py tools/gfx_xenon2_ko.py --write             gfx/edit/XENON2.GDT 까지 만든다
    py tools/gfx_xenon2_ko.py --font <ttf> [--index N]     아래 줄 글꼴 지정
    py tools/gfx_xenon2_ko.py --top-font <ttf> [--top-index N]
    py tools/gfx_xenon2_ko.py --out <파일.png>    미리보기 저장 위치 바꾸기

글꼴 고르기
-----------
원본 「トレイシーの憂鬱」는 **붓글씨 계열**이다 (획 두께 변동계수 1.07).
`tools/gfx_font_survey.py` 가 설치된 글꼴을 같은 지표로 재서 순위를 매긴다.
기본값은 그 조사에서 1위로 나온 **궁서**다.
"""
import os
import sys
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kocfg as C
import da1
from PIL import Image, ImageDraw, ImageFont

GFX = os.path.join(C.ROOT, "gfx")
SRC = os.path.join(GFX, "raw", "XENON2.GDT")
PNG = os.path.join(GFX, "png", "XENON2_GDT.png")
OUT_PNG = os.path.join(GFX, "png", "XENON2_KO.png")
CLEAN_PNG = os.path.join(GFX, "png", "XENON2_clean.png")
OUT_GDT = os.path.join(GFX, "edit", "XENON2.GDT")

# 글자가 들어갈 상자 - 원본 순백 픽셀 분포 실측값 (+여백 2px)
#   肉奴隷           : x 116..244, y 0..31
#   トレイシーの憂鬱 : x 6..366,  y 46..95
BOX_TOP = (114, 0, 247, 33)
BOX_BOT = (4, 44, 368, 96)

# 자간은 spread 가 알아서 벌린다 — 문자열에 공백을 넣지 않는다.
KO_TOP = "육노예"
KO_BOT = "트레이시의우울"

# 글꼴 지정: (파일, 얼굴 인덱스[, 가변 웨이트 이름]).
# 아래 줄 기본값은 Noto Serif KR Medium — 조사(gfx_font_survey.py) 최상위권 중
# 유일하게 OFL 라이선스라 배포물에 넣어도 문제가 없다.
# (거리 1위 궁서·4위 HY궁서 등은 한양정보통신 저작이라 배포용으로 부적합)
FONT_BOT = (r"C:\Windows\Fonts\NotoSerifKR-VF.ttf", 0, "Medium")
FONT_TOP = (r"C:\Windows\Fonts\NotoSansKR-VF.ttf", 0, "Bold")

INK_MIN = 620                   # 밝기 합이 이 이상이면 원본 글자로 본다


def truetype(spec, size):
    path, idx = spec[0], spec[1]
    f = ImageFont.truetype(path, size, index=idx)
    if len(spec) > 2 and spec[2]:
        f.set_variation_by_name(spec[2])
    return f


def face_name(spec):
    try:
        n = truetype(spec, 20).getname()
        base = " ".join(x for x in n if x)
    except Exception:
        base = os.path.basename(spec[0])
    if len(spec) > 2 and spec[2]:
        base += " [%s]" % spec[2]
    return base


WHITE = (255, 255, 255)
FRINGE = (255, 153, 238)        # 글자 가장자리에 붙는 연분홍. 배경 광선에도 쓰이는 색이라
                                # **흰 픽셀과 붙어 있을 때만** 글자 잔재로 본다.


def erase_text(img, boxes=(BOX_TOP, BOX_BOT)):
    """글자 상자 안의 순백 픽셀(+흰 픽셀에 붙은 연분홍 테두리)만 지우고,
    지운 자리를 가장자리부터 안쪽으로 8방향 평균으로 메운다.

    상자 밖과 글자가 아닌 픽셀은 **바이트 단위로 원본 그대로** 남는다
    (2026-08-10 사용자 지시: 원본 배경을 그대로 살릴 것).
    좌우로만 늘리면 배경이 곡선 그라데이션이라 가로 줄무늬가 남는다.
    """
    W, H = img.size
    px = img.load()

    def in_box(x, y):
        return any(b[0] <= x < b[2] and b[1] <= y < b[3] for b in boxes)

    NB = [(-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)]
    ink = [[False] * W for _ in range(H)]
    front = []
    for y in range(H):
        for x in range(W):
            if in_box(x, y) and px[x, y] == WHITE:
                ink[y][x] = True
                front.append((x, y))
    # 연분홍 테두리는 2~4겹이다 - 흰 글자에 붙은 것부터 연쇄로 전부 글자로 본다.
    # (배경 광선의 연분홍은 글자와 떨어져 있어 딸려 오지 않는다)
    while front:
        nxt = []
        for x, y in front:
            for dx, dy in NB:
                nx, ny = x + dx, y + dy
                if 0 <= nx < W and 0 <= ny < H and not ink[ny][nx] \
                        and px[nx, ny] == FRINGE and in_box(nx, ny):
                    ink[ny][nx] = True
                    nxt.append((nx, ny))
        front = nxt

    known = [[not ink[y][x] for x in range(W)] for y in range(H)]
    buf = [[px[x, y] for x in range(W)] for y in range(H)]
    hole = sum(r.count(True) for r in ink)
    while True:
        edge = []
        for y in range(H):
            for x in range(W):
                if known[y][x]:
                    continue
                acc = [0, 0, 0]
                n = 0
                for dx, dy in NB:
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < W and 0 <= ny < H and known[ny][nx]:
                        c = buf[ny][nx]
                        acc[0] += c[0]; acc[1] += c[1]; acc[2] += c[2]
                        n += 1
                if n:
                    edge.append((x, y, (acc[0] // n, acc[1] // n, acc[2] // n)))
        if not edge:
            break
        for x, y, c in edge:
            buf[y][x] = c
            known[y][x] = True
    for y in range(H):
        for x in range(W):
            px[x, y] = buf[y][x]
    return ink, hole


def fit_text(dr, text, box, spec, max_size, fill, spread=False):
    """상자에 들어가는 가장 큰 글꼴을 골라 그린다.

    spread=True 면 남는 가로 여백을 글자 사이에 고르게 나눠 **상자 폭을 꽉 채운다.**
    원본 「トレイシーの憂鬱」가 좌우 가장자리까지 닿아 있어 이렇게 해야 인상이 맞는다.
    """
    bw, bh = box[2] - box[0], box[3] - box[1]
    for size in range(max_size, 7, -1):
        try:
            f = truetype(spec, size)
        except OSError:
            continue
        bb = dr.textbbox((0, 0), text, font=f)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        if tw > bw or th > bh:
            continue
        y = box[1] + (bh - th) // 2 - bb[1]
        if not spread or len(text) < 2:
            dr.text((box[0] + (bw - tw) // 2 - bb[0], y), text, font=f, fill=fill)
            return size
        # 글자별로 그리며 남는 폭을 자간으로 나눈다
        widths = [dr.textlength(ch, font=f) for ch in text]
        gap = (bw - sum(widths)) / float(len(text) - 1)
        x = box[0] - bb[0]
        for ch, w in zip(text, widths):
            dr.text((x, y), ch, font=f, fill=fill)
            x += w + gap
        return size
    return 0


def build(font_bot=FONT_BOT, font_top=FONT_TOP, top=KO_TOP, bot=KO_BOT,
          save_clean=True, verbose=True):
    """원본에서 글자를 지우고 한글을 얹은 RGB 이미지를 돌려준다."""
    orig = Image.open(PNG).convert("RGB")
    img = orig.copy()
    ink, hole = erase_text(img)
    if verbose:
        print("  지운 글자 픽셀:", hole)
    if save_clean:
        img.save(CLEAN_PNG)

    dr = ImageDraw.Draw(img)
    s1 = fit_text(dr, top, BOX_TOP, font_top, 34, WHITE, spread=True)
    s2 = fit_text(dr, bot, BOX_BOT, font_bot, 60, WHITE, spread=True)
    if verbose:
        print("  위 : %-28s %2dpx  %s" % (face_name(font_top), s1, top))
        print("  아래: %-28s %2dpx  %s" % (face_name(font_bot), s2, bot))

    # 배경 보존 검증 - 원본과 달라진 픽셀은 전부
    # (지운 글자 자리) 또는 (새로 그린 글자 자리 = 상자 안)이어야 한다
    W, H = img.size
    po, pn = orig.load(), img.load()
    leak = 0
    for y in range(H):
        for x in range(W):
            if pn[x, y] == po[x, y]:
                continue
            if ink[y][x]:
                continue
            if (BOX_TOP[0] <= x < BOX_TOP[2] and BOX_TOP[1] <= y < BOX_TOP[3]) or \
               (BOX_BOT[0] <= x < BOX_BOT[2] and BOX_BOT[1] <= y < BOX_BOT[3]):
                continue
            leak += 1
    if verbose:
        print("  배경 보존 검증: 상자 밖에서 달라진 픽셀 %d개 (0 이어야 한다)" % leak)
    if leak:
        raise SystemExit("배경이 변형됐다 - erase_text 를 확인하라")
    return img


def encode(png_path, out_gdt=OUT_GDT, verbose=True):
    """PNG -> DA1. da1enc.py 가 팔레트·좌표·플래그를 원본에서 물려받는다."""
    import subprocess
    os.makedirs(os.path.dirname(out_gdt), exist_ok=True)
    r = subprocess.run([sys.executable, os.path.join(C.ROOT, "tools", "da1enc.py"),
                        "frompng", SRC, png_path, out_gdt],
                       capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        print("인코딩 실패:", (r.stderr or "").strip()[-600:])
        return False
    if verbose:
        for line in (r.stdout or "").splitlines():
            if line.startswith(("wrote", "verify", "NOTE")):
                print("  " + line)
        a, b = os.path.getsize(SRC), os.path.getsize(out_gdt)
        print("  %s %d -> %d 바이트 (%.3f배)" % (os.path.basename(SRC), a, b, b / a))
        m = da1.decode_full(open(out_gdt, "rb").read())
        print("  재검증: %dx%d 디코드 성공" % (m["w"] * 8, m["h"]))
    return True


def arg(name, default=None):
    a = sys.argv
    return a[a.index(name) + 1] if name in a else default


def main():
    fb = (arg("--font", FONT_BOT[0]), int(arg("--index", FONT_BOT[1])),
          arg("--weight", FONT_BOT[2] if len(FONT_BOT) > 2 else None))
    ft = (arg("--top-font", FONT_TOP[0]), int(arg("--top-index", FONT_TOP[1])),
          arg("--top-weight", FONT_TOP[2] if len(FONT_TOP) > 2 else None))
    out = arg("--out", OUT_PNG)

    img = build(font_bot=fb, font_top=ft)
    img.save(out)
    print("  한국어판 PNG :", out, img.size)

    if "--write" not in sys.argv:
        print("\n--write 를 붙이면 gfx/edit/XENON2.GDT 까지 만듭니다.")
        return 0
    return 0 if encode(out) else 1


if __name__ == "__main__":
    sys.exit(main())
