"""후보 글꼴을 원본 글자와 **수치로** 비교한다.

원본(`XENON2.GDT` 하단 「トレイシーの憂鬱」)의 획 성질을 재고,
설치된 글꼴로 같은 자리에 같은 문구를 그린 뒤 같은 방법으로 재서 거리를 매긴다.

    py tools/gfx_font_survey.py                     설치된 글꼴 전수 조사
    py tools/gfx_font_survey.py --dir D:\fonts      폴더를 추가로 훑는다
    py tools/gfx_font_survey.py --text "트레이시의 우울"
    py tools/gfx_font_survey.py --top 20            대지에 올릴 개수

산출물 (`gfx/font_survey/`)
    report.tsv    순위 + 지표 전량
    sheet.png     상위 N개를 원본과 나란히 놓은 대지
    each/*.png    글꼴별 렌더 결과

왜 이런 지표인가
----------------
원본 글자는 **안티에일리어싱이 없는 순백**이고, 획 두께가 심하게 들쭉날쭉하다.
런렝스의 **변동계수(표준편차/평균)** 가 1.0 을 넘는데, 이는 붓글씨의 특징이다
(획이 굵었다 가늘어진다). 균일한 고딕이라면 0.3~0.6 쯤 나온다.
그래서 「잉크 비율 · 평균 획 두께 · 변동계수 · 런렝스 분포」 넷으로 비교한다.
"""
import os
import sys
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kocfg as C
from PIL import Image, ImageDraw, ImageFont

GFX = os.path.join(C.ROOT, "gfx")
SRC_PNG = os.path.join(GFX, "png", "XENON2_GDT.png")
OUT = os.path.join(GFX, "font_survey")

# 원본에서 잴 영역과, 후보를 그려 넣을 상자 (같은 크기여야 공정하다)
BOX = (4, 28, 364, 92)          # 「トレイシーの憂鬱」
BOX_W, BOX_H = BOX[2] - BOX[0], BOX[3] - BOX[1]

FONT_DIRS = [r"C:\Windows\Fonts",
             os.path.join(os.environ.get("LOCALAPPDATA", ""),
                          r"Microsoft\Windows\Fonts")]

DEFAULT_TEXT = "트레이시의 우울"
PROBE = "\ue000"                 # 사용자 영역 - 어느 글꼴에도 없다 (.notdef 판별용)
COVER = "트레이시의우울육노예힣"    # 이게 다 있어야 한글 글꼴로 본다


# ---------------------------------------------------------------- 지표

def runs(mask, w, h, vertical):
    """1(잉크)/0 배열에서 연속 길이 분포"""
    out = collections.Counter()
    if vertical:
        for x in range(w):
            r = 0
            for y in range(h):
                if mask[y * w + x]:
                    r += 1
                elif r:
                    out[r] += 1
                    r = 0
            if r:
                out[r] += 1
    else:
        for y in range(h):
            r = 0
            for x in range(w):
                if mask[y * w + x]:
                    r += 1
                elif r:
                    out[r] += 1
                    r = 0
            if r:
                out[r] += 1
    return out


def stats(cnt):
    tot = sum(cnt.values())
    if not tot:
        return 0.0, 0.0, tot
    mean = sum(k * v for k, v in cnt.items()) / tot
    var = sum(v * (k - mean) ** 2 for k, v in cnt.items()) / tot
    return mean, (var ** 0.5) / mean if mean else 0.0, tot


def norm_hist(cnt, nbins=16):
    """런 길이를 1..nbins 로 자른 정규화 히스토그램 (nbins 이상은 마지막 칸에)"""
    h = [0.0] * nbins
    for k, v in cnt.items():
        h[min(k, nbins) - 1] += v
    s = sum(h)
    return [x / s for x in h] if s else h


def measure(mask, w, h):
    ink = sum(mask)
    v = runs(mask, w, h, True)
    hz = runs(mask, w, h, False)
    vm, vcv, _ = stats(v)
    hm, hcv, _ = stats(hz)
    return {"ink": ink / float(w * h),
            "v_mean": vm, "v_cv": vcv, "h_mean": hm, "h_cv": hcv,
            "v_hist": norm_hist(v), "h_hist": norm_hist(hz)}


def distance(a, b):
    """원본 a 와 후보 b 의 거리. 0 에 가까울수록 닮았다."""
    def rel(k, scale):
        return abs(a[k] - b[k]) / scale
    d = (rel("ink", 0.16) * 1.0 +
         rel("v_mean", 4.3) * 0.8 +
         rel("h_mean", 5.9) * 0.8 +
         rel("v_cv", 1.0) * 1.4 +          # 붓글씨다움 - 가중치를 높게
         rel("h_cv", 1.0) * 1.4)
    for k in ("v_hist", "h_hist"):
        d += sum(abs(x - y) for x, y in zip(a[k], b[k])) * 0.6
    return d


# ---------------------------------------------------------------- 렌더

def load(path, index, vname=None, size=40):
    """vname 은 가변 폰트의 명명 인스턴스 (예: 'Black'). 지정하면 그 웨이트로 렌더."""
    try:
        f = ImageFont.truetype(path, size, index=index)
        if vname:
            f.set_variation_by_name(vname)
        return f
    except Exception:
        return None


def variation_names(path, index):
    f = load(path, index)
    if not f:
        return []
    try:
        return [n.decode() if isinstance(n, bytes) else str(n)
                for n in f.get_variation_names()]
    except Exception:
        return []


def family(path, index, vname=None):
    f = load(path, index)
    if not f:
        return None
    try:
        n = f.getname()
        base = " ".join(x for x in n if x)
    except Exception:
        base = os.path.basename(path)
    return base + (" [%s]" % vname if vname else "")


def _bitmap(f, ch):
    """글자를 그려 바이트로. Pillow 버전에 따라 getmask 반환형이 달라 이 방식이 안전하다."""
    im = Image.new("L", (72, 72), 0)
    ImageDraw.Draw(im).text((4, 4), ch, font=f, fill=255)
    return im.tobytes()


def covers(path, index, text):
    """글자가 실제로 있는가 (.notdef 상자와 같으면 없는 것). 웨이트와 무관하므로 vname 불요."""
    f = load(path, index)
    if not f:
        return False
    try:
        miss = _bitmap(f, PROBE)
    except Exception:
        miss = None
    for ch in text:
        try:
            b = _bitmap(f, ch)
        except Exception:
            return False
        if not any(b):
            return False
        if miss is not None and b == miss:
            return False
    return True


def render(path, index, text, w, h, thresh=128, vname=None):
    """상자에 맞는 최대 크기로 그린 뒤 이진화. 원본처럼 안티에일리어싱을 없앤다."""
    best = None
    for size in range(h + 24, 7, -1):
        f = load(path, index, vname, size)
        if not f:
            continue
        im = Image.new("L", (w, h), 0)
        dr = ImageDraw.Draw(im)
        try:
            bb = dr.textbbox((0, 0), text, font=f)
        except Exception:
            continue
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        if tw <= w and th <= h:
            dr.text(((w - tw) // 2 - bb[0], (h - th) // 2 - bb[1]),
                    text, font=f, fill=255)
            best = (im, size)
            break
    if not best:
        return None, 0
    im, size = best
    px = im.load()
    mask = [1 if px[x, y] >= thresh else 0 for y in range(h) for x in range(w)]
    return mask, size


def mask_to_img(mask, w, h):
    im = Image.new("L", (w, h))
    im.putdata([255 if v else 0 for v in mask])
    return im


# ---------------------------------------------------------------- 수집

def collect(extra_dirs):
    seen = set()
    out = []
    for d in FONT_DIRS + extra_dirs:
        if not d or not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if os.path.splitext(fn)[1].lower() not in (".ttf", ".ttc", ".otf", ".otc"):
                continue
            p = os.path.join(d, fn)
            key = fn.lower()
            if key in seen:
                continue
            seen.add(key)
            for idx in range(32):
                if load(p, idx) is None:
                    break
                names = variation_names(p, idx)
                if names:
                    # 가변 폰트: 명명 인스턴스마다 별개 후보로 (기본 웨이트만 재면 불공정)
                    for nm in names:
                        out.append((p, idx, nm))
                else:
                    out.append((p, idx, None))
    return out


def main():
    a = sys.argv[1:]
    text = a[a.index("--text") + 1] if "--text" in a else DEFAULT_TEXT
    topn = int(a[a.index("--top") + 1]) if "--top" in a else 16
    extra = [a[a.index("--dir") + 1]] if "--dir" in a else []

    # 원본 재기
    im = Image.open(SRC_PNG).convert("RGB")
    p = im.load()
    orig = [1 if p[x, y] == (255, 255, 255) else 0
            for y in range(BOX[1], BOX[3]) for x in range(BOX[0], BOX[2])]
    ref = measure(orig, BOX_W, BOX_H)
    print("원본 「トレイシーの憂鬱」 %dx%d" % (BOX_W, BOX_H))
    print("  잉크 %.1f%%  세로획 평균 %.2fpx 변동계수 %.3f  가로획 평균 %.2fpx 변동계수 %.3f"
          % (ref["ink"] * 100, ref["v_mean"], ref["v_cv"], ref["h_mean"], ref["h_cv"]))
    print("  (변동계수 1.0 이상 = 획 두께가 심하게 변한다 = 붓글씨 계열)\n")

    cands = collect(extra)
    print("글꼴 파일에서 얼굴 %d개 발견. 한글 지원 여부 확인 중 ..." % len(cands))

    os.makedirs(os.path.join(OUT, "each"), exist_ok=True)
    rows = []
    covered = {}
    for path, idx, vname in cands:
        ck = (path, idx)
        if ck not in covered:
            covered[ck] = covers(path, idx, COVER)
        if not covered[ck]:
            continue
        mask, size = render(path, idx, text, BOX_W, BOX_H, vname=vname)
        if not mask or not any(mask):
            continue
        m = measure(mask, BOX_W, BOX_H)
        name = family(path, idx, vname) or os.path.basename(path)
        d = distance(ref, m)
        rows.append({"name": name, "file": os.path.basename(path), "idx": idx,
                     "vname": vname or "", "size": size, "dist": d,
                     "mask": mask, **m})

    rows.sort(key=lambda r: r["dist"])
    print("한글 글꼴 %d개 측정 완료\n" % len(rows))

    print("%-4s %-26s %6s %6s %6s %6s %6s %5s" %
          ("순위", "글꼴", "거리", "잉크%", "세로CV", "가로CV", "세로px", "크기"))
    print("-" * 78)
    for i, r in enumerate(rows, 1):
        print("%-4d %-26.26s %6.3f %6.1f %6.3f %6.3f %6.2f %5d" %
              (i, r["name"], r["dist"], r["ink"] * 100, r["v_cv"], r["h_cv"],
               r["v_mean"], r["size"]))

    with open(os.path.join(OUT, "report.tsv"), "w", encoding="utf-8", newline="\n") as f:
        f.write("순위\t글꼴\t파일\t인덱스\t웨이트\t글자크기\t거리\t잉크비율\t"
                "세로평균\t세로변동계수\t가로평균\t가로변동계수\n")
        f.write("0\t** 원본 **\tXENON2.GDT\t-\t-\t-\t0.000\t%.4f\t%.3f\t%.4f\t%.3f\t%.4f\n"
                % (ref["ink"], ref["v_mean"], ref["v_cv"], ref["h_mean"], ref["h_cv"]))
        for i, r in enumerate(rows, 1):
            f.write("%d\t%s\t%s\t%d\t%s\t%d\t%.4f\t%.4f\t%.3f\t%.4f\t%.3f\t%.4f\n"
                    % (i, r["name"], r["file"], r["idx"], r["vname"] or "-",
                       r["size"], r["dist"], r["ink"], r["v_mean"], r["v_cv"],
                       r["h_mean"], r["h_cv"]))

    for r in rows:
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in r["name"])[:60]
        mask_to_img(r["mask"], BOX_W, BOX_H).save(
            os.path.join(OUT, "each", safe + ".png"))

    # 대지 - 원본을 맨 위에 두고 상위 N개를 아래로
    show = rows[:topn]
    LAB = 16
    sheet = Image.new("RGB", (BOX_W + 8, (BOX_H + LAB + 6) * (len(show) + 1) + 6),
                      (20, 20, 24))
    dr = ImageDraw.Draw(sheet)
    try:
        lf = ImageFont.truetype(r"C:\Windows\Fonts\malgun.ttf", 11)
    except Exception:
        lf = ImageFont.load_default()

    def row(i, img, label, color):
        y = 6 + i * (BOX_H + LAB + 6)
        dr.text((4, y), label, font=lf, fill=color)
        sheet.paste(img, (4, y + LAB))

    row(0, mask_to_img(orig, BOX_W, BOX_H).convert("RGB"),
        "원본 (トレイシーの憂鬱)  잉크 %.1f%%  CV %.2f / %.2f"
        % (ref["ink"] * 100, ref["v_cv"], ref["h_cv"]), (255, 220, 120))
    for i, r in enumerate(show, 1):
        row(i, mask_to_img(r["mask"], BOX_W, BOX_H).convert("RGB"),
            "%d. %s   거리 %.3f  잉크 %.1f%%  CV %.2f / %.2f"
            % (i, r["name"], r["dist"], r["ink"] * 100, r["v_cv"], r["h_cv"]),
            (190, 215, 160))
    sp = os.path.join(OUT, "sheet.png")
    sheet.save(sp)
    print("\n대지 : %s" % sp)
    print("표   : %s" % os.path.join(OUT, "report.tsv"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
