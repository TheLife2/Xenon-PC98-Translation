"""디스크 이미지 안의 그래픽을 되읽어 확인한다.

    py tools/gfx_check.py                 gfx/edit 에 있는 것만 확인
    py tools/gfx_check.py --all           이미지 안의 모든 GDT/ADT 를 디코드해 본다
    py tools/gfx_check.py --png <이름>    되읽은 것을 gfx/png/<이름>_HDI.png 로 저장

디스크에 쓴 바이트가 gfx/edit 의 것과 같은지, 그리고 그것이 실제로
디코드되는지를 본다. build.py 8단계는 스크립트만 검사하므로 그래픽은 여기서 본다.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kocfg as C
from kohdi import Fat12
import da1

GFX = os.path.join(C.ROOT, "gfx")
EDIT = os.path.join(GFX, "edit")
RAW = os.path.join(GFX, "raw")
PNG = os.path.join(GFX, "png")


def save_png(m, path):
    """디코드 결과를 PNG 로 (da1.py 의 png 명령과 같은 방식)"""
    from PIL import Image
    px = da1._compose(m)
    pal = da1.palette_rgb(m["palette_raw"], "GRB") if m["palette_raw"] else None
    lut = [pal[i] for i in range(16)] if pal else [(i * 17,) * 3 for i in range(16)]
    am = da1.alpha_mask(m)
    img = Image.new("RGBA", (m["w"] * 8, m["h"]))
    img.putdata([(lut[v][0], lut[v][1], lut[v][2], am[i]) for i, v in enumerate(px)])
    img.save(path)


def main():
    hdi = os.path.join(C.OUT_DIR, "xenon_ko.hdi")
    if not os.path.isfile(hdi):
        print("out/xenon_ko.hdi 가 없다. build.py 를 먼저 돌려라.")
        return 1
    fs = Fat12(hdi)

    if "--all" in sys.argv:
        names = [e[0] for e in fs.entries()
                 if e[0].upper().endswith((".GDT", ".ADT"))]
    else:
        names = sorted(os.listdir(EDIT)) if os.path.isdir(EDIT) else []
        names = [n for n in names if n.upper().endswith((".GDT", ".ADT"))]
    if not names:
        print("확인할 대상이 없다. (gfx/edit 가 비었으면 --all 로 전체를 본다)")
        return 0

    want_png = None
    if "--png" in sys.argv:
        want_png = sys.argv[sys.argv.index("--png") + 1].upper()

    ok = bad = 0
    for name in names:
        got = fs.read(name)
        if got is None:
            print(f"  [없음] {name}")
            bad += 1
            continue
        note = []
        e = os.path.join(EDIT, name)
        if os.path.isfile(e):
            same = got == open(e, "rb").read()
            note.append("edit 와 동일" if same else "⚠ edit 와 다름")
            if not same:
                bad += 1
                print(f"  [불일치] {name}")
                continue
        r = os.path.join(RAW, name)
        if os.path.isfile(r):
            note.append("원본 그대로" if got == open(r, "rb").read() else "원본과 다름")
        try:
            m = da1.decode_full(got)
            h = da1.parse_header(got)
        except Exception as ex:
            print(f"  [디코드 실패] {name}: {ex}")
            bad += 1
            continue
        ok += 1
        print(f"  {name:14s} {len(got):6d}B  {m['w']*8}x{m['h']} @({h['x']*8},{h['y']})"
              f"  {' / '.join(note)}")
        if want_png and name.upper() == want_png:
            os.makedirs(PNG, exist_ok=True)
            p = os.path.join(PNG, os.path.splitext(name)[0] + "_HDI.png")
            save_png(m, p)
            print("     ->", p)

    print(f"\n디코드 성공 {ok} / 실패 {bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
