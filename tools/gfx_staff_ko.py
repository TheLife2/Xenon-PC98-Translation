"""스태프 롤(ST01~ST08) + 뮤직 모드 타이틀 한국어화 (2026-08-10 사용자 지시).

역할명은 한국어로, 인명은 한글 표기로 옮긴다. 배경이 검정이라
글줄 띠를 자동 검출해 지우고 같은 색·같은 자리에 다시 그린다.

그대로 두는 것: ST00(XENON 로고) · ST09(FIN 장식) · 0100BB(저작권 고지) ·
0040B(작중 화면 표시) · ROGO 의 「C's ware presents」(브랜드 문구).
ST05 의 「?　?　?」 줄은 원본부터 물음표인 장난 크레딧이라 물음표를 유지한다.

    py tools/gfx_staff_ko.py            미리보기
    py tools/gfx_staff_ko.py --write    gfx/edit/*.GDT 까지
"""
import collections
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kocfg as C
import da1
from PIL import Image, ImageDraw, ImageFont

GFX = os.path.join(C.ROOT, "gfx")
SERIF = r"C:\Windows\Fonts\NotoSerifKR-VF.ttf"      # OFL - 배포 안전

# 파일 -> 글줄 띠(위에서 아래 순서)별 대체 문구. None 이면 그 띠는 원본 유지.
STAFF = {
    "ST01.GDT": ["연출 & 게임 디자인", "켄노 유키히로"],
    "ST02.GDT": ["아트 디렉션", "노구치 마사츠네"],
    "ST03.GDT": ["작곡", "우메모토 류"],
    "ST04.GDT": ["메인 프로그램", "칸노 히로유키"],
    "ST05.GDT": ["캐릭터 디자인", "야사마타 시야미　(겐.다이)", "?　　?　　?　(미.라.이)"],
    "ST06.GDT": ["그래픽 에디터", "미야시타 마사야", "이즈카 아야코",
                 "우스키 카츠히사", "마츠모토 케이"],
    "ST07.GDT": ["특별 감사", "오쿠무라 유코"],
    "ST08.GDT": ["제작", None],          # 「C's ware」 로고 문구는 유지
}


def bands(img, gap=4):
    """비검정 픽셀이 있는 행을 띠로 묶는다 -> [(y1, y2)]"""
    W, H = img.size
    px = img.load()
    rows = [y for y in range(H) if any(px[x, y] != (0, 0, 0) for x in range(W))]
    out = []
    for y in rows:
        if out and y - out[-1][1] <= gap:
            out[-1][1] = y
        else:
            out.append([y, y])
    return [(a, b + 1) for a, b in out]


def dominant(img, y1, y2):
    """띠의 대표(최빈 비검정) 색"""
    W = img.size[0]
    px = img.load()
    cnt = collections.Counter(px[x, y] for y in range(y1, y2) for x in range(W)
                              if px[x, y] != (0, 0, 0))
    return cnt.most_common(1)[0][0] if cnt else (255, 255, 255)


def draw_line(dr, W, text, y1, y2, color, size, spread_to=0, weight="SemiBold"):
    """spread_to > 0 이면 자간을 벌려 그 폭을 채운다 (가운데 정렬).
    자간이 글자 폭의 절반을 넘으면 보기 흉하므로 그만큼에서 멈춘다."""
    f = ImageFont.truetype(SERIF, size)
    f.set_variation_by_name(weight)
    dr.fontmode = "1"
    bb = dr.textbbox((0, 0), text, font=f)
    y = y1 + (y2 - y1 - (bb[3] - bb[1])) // 2 - bb[1]
    if spread_to and len(text) > 1:
        widths = [dr.textlength(ch, font=f) for ch in text]
        gap = max(0.0, (spread_to - sum(widths)) / (len(text) - 1))
        gap = min(gap, size * 0.5)
        total = sum(widths) + gap * (len(text) - 1)
        x = (W - total) / 2.0
        for ch, w in zip(text, widths):
            dr.text((x, y), ch, font=f, fill=color)
            x += w + gap
    else:
        dr.text(((W - (bb[2] - bb[0])) // 2 - bb[0], y), text, font=f, fill=color)


def process(name, texts, write):
    png = os.path.join(GFX, "png", name.replace(".GDT", "_GDT.png"))
    orig = Image.open(png).convert("RGB")
    img = orig.copy()
    W, H = img.size
    bs = bands(orig)
    if len(bs) != len(texts):
        print("%s: 띠 %d개 != 문구 %d개 - 띠 %s" % (name, len(bs), len(texts), bs))
        raise SystemExit(1)
    dr = ImageDraw.Draw(img)
    # 파일 안에서 크기·색을 통일한다 - 띠 높이가 줄마다 달라도 글자는 같아야 한다
    repl = [(b, t) for b, t in zip(bs, texts) if t is not None]
    uni = min(20, min(b[1] - b[0] for b, _ in repl) - 2)
    role_color = dominant(orig, *bs[0])
    name_color = dominant(orig, *bs[1]) if len(bs) > 1 else role_color
    allowed = []
    for i, ((y1, y2), text) in enumerate(zip(bs, texts)):
        if text is None:
            continue
        color = role_color if i == 0 else name_color
        dr.rectangle((0, y1, W - 1, y2 - 1), fill=(0, 0, 0))
        draw_line(dr, W, text, y1, y2, color, uni)
        allowed.append((0, y1, W, y2))
    # 영역 밖 보존 검증
    po, pn = orig.load(), img.load()
    leak = sum(1 for y in range(H) for x in range(W)
               if pn[x, y] != po[x, y]
               and not any(a[1] <= y < a[3] for a in allowed))
    print("%s: 띠 %d개 교체, 영역 밖 변경 %d" % (name, len(allowed), leak))
    if leak:
        raise SystemExit("영역 밖이 변형됐다")
    return finish(name, img, write)


def process_music(write):
    """MUSIC.GDT - 하단 「MUSIC MODE」.

    장미(역시 빨강)가 y185 부근까지 내려오므로 y190 아래에서만 찾는다.
    기타리스트의 발·그림자가 글자와 겹치므로 **빨간 픽셀만** 지우고
    같은 열의 비빨강 표본으로 메운다. 한글은 원본처럼 폭을 채워 그린다.
    """
    name = "MUSIC.GDT"
    png = os.path.join(GFX, "png", name.replace(".GDT", "_GDT.png"))
    orig = Image.open(png).convert("RGB")
    img = orig.copy()
    W, H = img.size
    px = img.load()
    po = orig.load()

    def is_red(c):
        return c[0] > 130 and c[1] < 90 and c[2] < 90

    rows = [y for y in range(190, H) if any(is_red(po[x, y]) for x in range(W))]
    y1, y2 = min(rows) - 1, max(rows) + 2
    red = collections.Counter(po[x, y] for y in range(y1, y2) for x in range(W)
                              if is_red(po[x, y])).most_common(1)[0][0]
    xs = [x for y in range(y1, y2) for x in range(W) if is_red(po[x, y])]
    span = max(xs) - min(xs)              # 원본 글자가 차지하던 폭
    for y in range(y1, y2):
        for x in range(W):
            if not is_red(px[x, y]):
                continue
            got = (0, 0, 0)
            for k in range(1, 40):
                for cy in (y - k, y + k):
                    if 0 <= cy < H and not is_red(po[x, cy]):
                        got = po[x, cy]
                        break
                else:
                    continue
                break
            px[x, y] = got
    dr = ImageDraw.Draw(img)
    draw_line(dr, W, "뮤직 모드", y1, y2, red, y2 - y1 - 3,
              spread_to=span, weight="Black")
    leak = sum(1 for y in range(H) for x in range(W)
               if px[x, y] != po[x, y] and not (y1 <= y < y2))
    print("%s: 글자띠 y%d..%d 교체 (폭 %d), 영역 밖 변경 %d"
          % (name, y1, y2, span, leak))
    if leak:
        raise SystemExit("영역 밖이 변형됐다")
    return finish(name, img, write)


def finish(name, img, write):
    out_png = os.path.join(GFX, "png", name.replace(".GDT", "_KO.png"))
    img.save(out_png)
    if not write:
        return True
    src = os.path.join(GFX, "raw", name)
    out_gdt = os.path.join(GFX, "edit", name)
    r = subprocess.run([sys.executable, os.path.join(C.ROOT, "tools", "da1enc.py"),
                        "frompng", src, out_png, out_gdt],
                       capture_output=True, text=True, encoding="utf-8")
    ok = "MATCHES" in (r.stdout or "")
    print("   -> %s  %d -> %d 바이트  검증 %s"
          % (name, os.path.getsize(src),
             os.path.getsize(out_gdt) if os.path.isfile(out_gdt) else 0,
             "OK" if ok else "실패"))
    if not ok:
        print((r.stdout or "")[-400:], (r.stderr or "")[-200:])
        raise SystemExit(1)
    return ok


def main():
    write = "--write" in sys.argv
    for name, texts in STAFF.items():
        process(name, texts, write)
    process_music(write)
    if not write:
        print("\n미리보기: gfx/png/ST0*_KO.png, MUSIC_KO.png")


if __name__ == "__main__":
    main()
