"""메뉴 2장 · 시작 로고 · 책장 소품 한국어화 (2026-08-10 사용자 지시).

    MENU1.GDT : GAME START / DATA LOAD / SPECIAL MODE -> 게임 시작 / 데이터 로드 / 스페셜 모드
    MENU2.GDT : LADY'S ROOM / MUSIC MODE              -> 레이디스 룸 / 뮤직 모드
    ROGO.GDT  : 「C's ware presents」 를 18px 올리고 아래에 「번역: THL.kr」
    1010.GDT  : 책등 「量子力学と宇宙」->「양자역학과 우주」,
                「Dr.大槻○神論」->「Dr.오쓰키 정신론」 (○ 판독 불가 - 작품 배경에 맞춘 추정)

    py tools/gfx_misc_ko.py            미리보기 (gfx/png/*_KO.png)
    py tools/gfx_misc_ko.py --write    gfx/edit/*.GDT 까지

메뉴 막대는 단색(#337777)이라 통째로 다시 칠하고, 책등은 주변 표본 복사로 메운다.
바뀐 픽셀이 지정 영역 밖에 없음을 파일마다 기계 검증한다.
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kocfg as C
import da1
from PIL import Image, ImageDraw, ImageFont

GFX = os.path.join(C.ROOT, "gfx")
GULIM = r"C:\Windows\Fonts\gulim.ttc"

PINK = (0xCC, 0x99, 0xCC)       # 메뉴 글자색 (원본과 동일)
TEAL = (0x33, 0x77, 0x77)       # 메뉴 막대 속색
MINT = (0x99, 0xBB, 0xAA)       # ROGO 문구색


def text_centered(dr, text, box, size, fill, tracking=0, font=GULIM, vname=None):
    """상자 가운데에 자간을 두고 그린다. 그린 픽셀은 상자 안에만 생긴다.

    '.' 은 저크기 폰트에서 쉼표처럼 뭉개져 2x2 정사각형으로 직접 찍는다.
    """
    f = ImageFont.truetype(font, size)
    if vname:
        f.set_variation_by_name(vname)
    dr.fontmode = "1"
    DOT = max(2, size // 7)
    widths = [DOT + 2 if ch == "." else dr.textlength(ch, font=f) for ch in text]
    total = sum(widths) + tracking * (len(text) - 1)
    x = box[0] + (box[2] - box[0] - total) / 2.0
    bb = dr.textbbox((0, 0), text.replace(".", ""), font=f)
    y = box[1] + (box[3] - box[1] - (bb[3] - bb[1])) // 2 - bb[1]
    base = y + bb[3]                      # 베이스라인 근사
    for ch, w in zip(text, widths):
        if ch == ".":
            dr.rectangle((int(x) + 1, base - DOT, int(x) + DOT, base - 1), fill=fill)
        else:
            dr.text((x, y), ch, font=f, fill=fill)
        x += w + tracking


def leak_check(name, orig, img, allowed):
    po, pn = orig.load(), img.load()
    leak = 0
    for y in range(img.size[1]):
        for x in range(img.size[0]):
            if pn[x, y] != po[x, y] and \
               not any(a[0] <= x < a[2] and a[1] <= y < a[3] for a in allowed):
                leak += 1
    print("%s: 영역 밖 변경 %d (0 이어야 함)" % (name, leak))
    if leak:
        raise SystemExit("영역 밖이 변형됐다")


def sample_refill(img, cells, dark=280):
    """셀 안을 셀 밖 표본(±2 걸음, 어두운 글자 픽셀 제외)으로 메운다."""
    px = img.load()
    W, H = img.size

    def inside(x, y):
        return any(c[0] <= x < c[2] and c[1] <= y < c[3] for c in cells)

    for x1, y1, x2, y2 in cells:
        for y in range(y1, y2):
            for x in range(x1, x2):
                got = None
                for k in range(1, 16):
                    for cx in (x - 2 * k, x + 2 * k):
                        if 0 <= cx < W and not inside(cx, y) \
                                and sum(px[cx, y]) >= dark:
                            got = px[cx, y]
                            break
                    if got:
                        break
                if got is None:
                    for k in range(1, 16):
                        for cy in (y - 2 * k, y + 2 * k):
                            if 0 <= cy < H and not inside(x, cy) \
                                    and sum(px[x, cy]) >= dark:
                                got = px[x, cy]
                                break
                        if got:
                            break
                if got is not None:
                    px[x, y] = got


def do_menu(name, png, items, write):
    """items = [(문구, y1, y2)]. 막대 속을 다시 칠하고 가운데 정렬로 쓴다."""
    orig = Image.open(os.path.join(GFX, "png", png)).convert("RGB")
    img = orig.copy()
    dr = ImageDraw.Draw(img)
    cells = []
    for text, y1, y2 in items:
        box = (58, y1, 246, y2)
        dr.rectangle((box[0], box[1], box[2] - 1, box[3] - 1), fill=TEAL)
        text_centered(dr, text, box, 19, PINK, tracking=4)
        cells.append(box)
    leak_check(name, orig, img, cells)
    return finish(name, png, img, write)


def do_rogo(write):
    """시작 로고(C's ware)에 「번역: THL.kr」 를 넣는다.

    ⛔ 자리를 옮기지 마라. 실기에서 **y246~288 은 화면에 나오지 않는다.**
       게임이 스프라이트를 그린 뒤 그 띠를 덮어쓴다.
       (2026-08-10 대조 실험으로 확정 — 같은 문구를 y200 과 y265 에 동시에 넣고
        DOSBox-X 로 캡처했더니 y200 만 보였다. 파일에는 둘 다 들어 있었다.)
       원본에서 그 띠가 비어 있어 아무도 눈치채지 못한 것으로 보인다.

       살아남는 구간은 y <= 245(로고 마크)와 y >= 289(「C's ware presents」)뿐이라
       검은 여백에 넣을 수는 없다. 마크 아래쪽 끝이 가장 덜 방해된다.
    """
    name, png = "ROGO.GDT", "ROGO_GDT.png"
    orig = Image.open(os.path.join(GFX, "png", png)).convert("RGB")
    img = orig.copy()
    W, H = img.size
    box = (0, 226, W, 245)                  # 안전 구간의 맨 아래
    dr = ImageDraw.Draw(img)
    text_centered(dr, "번역: THL.kr", box, 14, (255, 255, 255), tracking=1)
    leak_check(name, orig, img, [box])
    # 원본이 투명한 자리에도 그리려면 전면 불투명 인코딩이 필요하다 (finish 주석)
    return finish(name, png, img, write, flat=True)


def do_books(write):
    """1010 책등 두 권. 세로쓰기 - 글자를 한 자씩 쌓는다."""
    name, png = "1010.GDT", "1010_GDT.png"
    orig = Image.open(os.path.join(GFX, "png", png)).convert("RGB")
    img = orig.copy()
    dr = ImageDraw.Draw(img)
    dr.fontmode = "1"
    DARK_INK = (0x44, 0x44, 0x44)       # 원본 책등 글자색

    def vertical(text, x, y0, cell_h, size, fill):
        cells = []
        f = ImageFont.truetype(GULIM, size)
        for i, ch in enumerate(text):
            y = y0 + i * cell_h
            bb = dr.textbbox((0, 0), ch, font=f)
            w = bb[2] - bb[0]
            cells.append((x, y, x + size + 1, y + cell_h))
            yield_ = (x + (size - w) // 2 - bb[0], y - bb[1])
            dr.text(yield_, ch, font=f, fill=fill)
        return cells

    # 책등1 「量子力学と宇宙」 x52..64 y112..175 (9px/자) -> 양자역학과 우주
    c1 = [(51, 110, 66, 176)]
    sample_refill(img, c1)
    list(vertical("양자역학과우주", 52, 112, 9, 9, DARK_INK))
    # 책등2 「大槻○神論」 x70..86 y115..183 -> 오쓰키정신론 ('Dr.'/'2' 는 원본 유지)
    c2 = [(69, 113, 88, 185)]
    sample_refill(img, c2)
    list(vertical("오쓰키정신론", 72, 114, 11, 11, DARK_INK))
    leak_check(name, orig, img, c1 + c2)
    return finish(name, png, img, write)


def finish(name, png, img, write, flat=False):
    """flat=True 면 네 평면을 모두 쓴다.

    ⚠ 원본이 **투명한 자리**에 새로 글자를 그렸다면 flat 이 필수다.
    `da1enc frompng` 는 기본적으로 원본의 평면별 투명도를 그대로 물려받아,
    원본에서 안 그리던 행은 새 픽셀이 있어도 "안 그림" 으로 인코딩한다.
    ROGO 의 로고와 문구 사이 빈 띠(y246~288)가 정확히 그 경우였고,
    그래서 크레딧이 파일에는 있는데 화면에 안 나왔다 (2026-08-10 실기 확인).
    """
    out_png = os.path.join(GFX, "png", png.replace("_GDT", "_KO"))
    img.save(out_png)
    if not write:
        return True
    src = os.path.join(GFX, "raw", name)
    out_gdt = os.path.join(GFX, "edit", name)
    os.makedirs(os.path.join(GFX, "edit"), exist_ok=True)
    a = os.path.getsize(src)

    if flat:
        # frompng 는 원본에서 **아무 평면도 안 쓴 칸**을 계속 투명으로 남긴다.
        # (`--flat` 은 일부 평면만 쓴 칸에만 듣는다) 그래서 원본이 비어 있던 자리에
        # 새로 그린 글자가 파일에는 있어도 화면에 안 나온다.
        # encode() 를 직접 불러 **사각형 전체를 불투명**으로 만든다.
        import da1enc
        om = da1.decode_full(open(src, "rb").read())
        oh = da1.parse_header(open(src, "rb").read())
        pal = [tuple(c) for c in da1.palette_rgb(om["palette_raw"], "GRB")]
        inv = {}
        for i, c in enumerate(pal):
            inv.setdefault(c, i)
        W, H = img.size
        px = []
        for c in img.convert("RGB").getdata():
            px.append(inv[c] if c in inv else
                      min(range(16), key=lambda i: sum((p - q) ** 2
                                                       for p, q in zip(pal[i], c))))
        enc = da1enc.encode(bytes(px), W, H, oh["x"], oh["y"],
                            palette=om["palette_raw"], alpha=b"\xff" * (W * H),
                            flags=oh["flags"])
        open(out_gdt, "wb").write(enc)
        m2 = da1.decode_full(enc, strict=True)
        ok = bytes(da1._compose(m2)) == bytes(px)
        print("   -> %s  %d -> %d 바이트 (전면 불투명)  검증 %s"
              % (name, a, len(enc), "OK" if ok else "실패"))
        if not ok:
            raise SystemExit("재디코드 픽셀 불일치")
        return ok

    r = subprocess.run([sys.executable, os.path.join(C.ROOT, "tools", "da1enc.py"),
                        "frompng", src, out_png, out_gdt],
                       capture_output=True, text=True, encoding="utf-8")
    ok = "MATCHES" in (r.stdout or "")
    b = os.path.getsize(out_gdt) if os.path.isfile(out_gdt) else 0
    print("   -> %s  %d -> %d 바이트  검증 %s" % (name, a, b, "OK" if ok else "실패"))
    if not ok:
        print((r.stdout or "")[-400:], (r.stderr or "")[-200:])
        raise SystemExit(1)
    m = da1.decode_full(open(out_gdt, "rb").read())
    print("   재검증: %dx%d 디코드 성공" % (m["w"] * 8, m["h"]))
    return ok


def main():
    write = "--write" in sys.argv
    do_menu("MENU1.GDT", "MENU1_GDT.png",
            [("게임 시작", 44, 68), ("데이터 로드", 91, 116), ("스페셜 모드", 139, 164)],
            write)
    do_menu("MENU2.GDT", "MENU2_GDT.png",
            [("레이디스 룸", 41, 68), ("뮤직 모드", 91, 116)],
            write)
    do_rogo(write)
    do_books(write)
    if not write:
        print("\n미리보기: gfx/png/MENU1_KO.png, MENU2_KO.png, ROGO_KO.png, 1010_KO.png")


if __name__ == "__main__":
    main()
