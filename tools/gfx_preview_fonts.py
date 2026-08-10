"""후보 글꼴을 **실제 배경 위에** 얹어 나란히 비교한다.

`gfx_font_survey.py` 는 흑백 실루엣으로 수치를 재고,
이 도구는 색·배경·팔레트 제약까지 포함해 눈으로 고르게 한다.

    py tools/gfx_preview_fonts.py                 report.tsv 상위 6개
    py tools/gfx_preview_fonts.py --n 10          상위 10개
    py tools/gfx_preview_fonts.py --quant         16색 팔레트로 실제 양자화까지 해서 보여준다
    py tools/gfx_preview_fonts.py --text "트레이시의 우울"

산출물 : gfx/font_survey/preview.png
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kocfg as C
import da1
import gfx_xenon2_ko as KO
from PIL import Image, ImageDraw, ImageFont

GFX = os.path.join(C.ROOT, "gfx")
OUT = os.path.join(GFX, "font_survey")
TSV = os.path.join(OUT, "report.tsv")
FONT_DIRS = [r"C:\Windows\Fonts",
             os.path.join(os.environ.get("LOCALAPPDATA", ""),
                          r"Microsoft\Windows\Fonts")]


def find_file(basename):
    for d in FONT_DIRS:
        p = os.path.join(d, basename)
        if os.path.isfile(p):
            return p
    return None


def read_ranking(n):
    """report.tsv 에서 상위 n개 (원본 행 0 은 건너뛴다)"""
    out = []
    with open(TSV, encoding="utf-8") as f:
        next(f)
        for line in f:
            c = line.rstrip("\n").split("\t")
            if c[0] == "0":
                continue
            p = find_file(c[2])
            if not p:
                continue
            vname = None if c[4] in ("-", "") else c[4]
            out.append({"rank": int(c[0]), "name": c[1],
                        "spec": (p, int(c[3]), vname), "dist": float(c[6])})
            if len(out) >= n:
                break
    return out


def quantize_like_game(img):
    """실제 파이프라인과 같은 양자화 — 원본 팔레트 16색으로 스냅한 결과를 본다."""
    d = open(os.path.join(GFX, "raw", "XENON2.GDT"), "rb").read()
    m = da1.decode_full(d)
    pal = da1.palette_rgb(m["palette_raw"], "GRB")
    if not pal:
        return img
    lut = [pal[i] for i in range(16)]
    px = img.load()
    W, H = img.size
    for y in range(H):
        for x in range(W):
            c = px[x, y]
            px[x, y] = min(lut, key=lambda p: (p[0]-c[0])**2 + (p[1]-c[1])**2
                           + (p[2]-c[2])**2)
    return img


def arg(name, default=None):
    a = sys.argv
    return a[a.index(name) + 1] if name in a else default


def main():
    n = int(arg("--n", 6))
    text = arg("--text", KO.KO_BOT)
    quant = "--quant" in sys.argv
    if not os.path.isfile(TSV):
        print("먼저 gfx_font_survey.py 를 돌리세요.")
        return 1

    rows = read_ranking(n)
    print("후보 %d개 렌더 중 ..." % len(rows))

    orig = Image.open(KO.PNG).convert("RGB")
    W, H = orig.size
    LAB = 15
    sheet = Image.new("RGB", (W + 8, (H + LAB + 5) * (len(rows) + 1) + 5), (18, 18, 22))
    dr = ImageDraw.Draw(sheet)
    try:
        lf = ImageFont.truetype(r"C:\Windows\Fonts\malgun.ttf", 11)
    except Exception:
        lf = ImageFont.load_default()

    def put(i, im, label, color):
        y = 5 + i * (H + LAB + 5)
        dr.text((4, y), label, font=lf, fill=color)
        sheet.paste(im, (4, y + LAB))

    put(0, orig, "원본 (일본어)", (255, 210, 110))
    for i, r in enumerate(rows, 1):
        im = KO.build(font_bot=r["spec"], bot=text, save_clean=False, verbose=False)
        if quant:
            im = quantize_like_game(im)
        put(i, im, "%d. %s   거리 %.3f%s"
            % (r["rank"], r["name"], r["dist"], "  (16색 양자화)" if quant else ""),
            (185, 215, 155))
        print("  %d. %s" % (r["rank"], r["name"]))

    p = os.path.join(OUT, "preview_quant.png" if quant else "preview.png")
    sheet.save(p)
    print("\n미리보기 :", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
