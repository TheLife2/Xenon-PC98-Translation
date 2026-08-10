"""편집한 그래픽을 디스크 이미지에 반영한다.

    gfx/edit/*.GDT  에 놓인 파일만 교체 대상이다. 비어 있으면 아무것도 하지 않는다.

    py tools/gfx_build.py            무엇이 반영될지 미리보기
    py tools/gfx_build.py --write    out/xenon_ko.hdi 에 반영

build.py 가 이미지를 만든 뒤 자동으로 호출하므로 보통은 직접 부를 일이 없다.
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


def pending():
    """반영 대기 중인 파일 [(이름, 새 바이트, 원본 크기)]"""
    if not os.path.isdir(EDIT):
        return []
    out = []
    for fn in sorted(os.listdir(EDIT)):
        if not fn.upper().endswith((".GDT", ".ADT")):
            continue
        new = open(os.path.join(EDIT, fn), "rb").read()
        orig = os.path.join(RAW, fn)
        old = open(orig, "rb").read() if os.path.isfile(orig) else b""
        out.append((fn, new, len(old)))
    return out


def check(name, data):
    """넣기 전 확인. 문제가 있으면 사유 문자열, 없으면 None."""
    if data[:3] == b"ADT":
        return check_adt(name, data)
    if data[:4] != da1.MAGIC:
        return "매직이 DA1\\0 이 아니다"
    try:
        h = da1.parse_header(data)
    except Exception as e:
        return f"헤더를 못 읽는다: {e}"
    if h["size"] != len(data):
        return f"헤더의 크기 {h['size']} != 실제 {len(data)}"
    try:
        da1.decode_full(data)
    except Exception as e:
        return f"자기 디코더로 풀리지 않는다: {e}"
    # 원본과 그리는 위치·크기가 같아야 게임이 같은 자리에 그린다.
    # 예외: 0100BB(저작권 배너)는 크레딧을 위해 아래로만 늘리는 것을 허용
    # (x·y·w 는 유지, 화면 400줄 안이면 엔진은 헤더대로 그린다 - gfx_credit_banner.py)
    orig = os.path.join(RAW, name)
    if os.path.isfile(orig):
        o = da1.parse_header(open(orig, "rb").read())
        keys = ("x", "y", "w") if name.upper() == "0100BB.GDT" else ("x", "y", "w", "h")
        for k in keys:
            if o[k] != h[k]:
                return f"{k} 가 원본과 다르다 ({o[k]} -> {h[k]})"
        if name.upper() == "0100BB.GDT":
            if h["h"] < o["h"] or h["y"] + h["h"] > 400:
                return f"h 확장이 잘못됐다 ({o['h']} -> {h['h']}, 화면 밖)"
    return None


def check_adt(name, data):
    """ADT 컨테이너: 프레임 수가 원본과 같고 전부 디코드되는지 본다."""
    import da1w
    from gfx_adt import entries
    orig = os.path.join(RAW, name)
    try:
        ent = entries(data)
    except Exception as e:
        return f"컨테이너를 못 걷는다: {e}"
    if os.path.isfile(orig):
        try:
            n0 = len(entries(open(orig, "rb").read()))
        except Exception:
            n0 = None
        if n0 is not None and n0 != len(ent):
            return f"프레임 수가 다르다 ({n0} -> {len(ent)})"
    for i, (o, s) in enumerate(ent):
        sub = data[o:o + s]
        try:
            mod = da1 if da1.parse_header(sub)["byte_mode"] else da1w
            mod.decode_full(sub, strict=True)
        except Exception as e:
            return f"프레임 {i} 디코드 실패: {e}"
    return None


def apply(hdi, write):
    items = pending()
    if not items:
        print("  gfx/edit 가 비어 있다 - 그래픽 교체 없음")
        return 0

    fs = Fat12(hdi)
    free_before = len(fs.free_clusters())
    ok = 0
    for name, data, oldsize in items:
        why = check(name, data)
        if why:
            print(f"  [거부] {name}: {why}")
            continue
        d = len(data) - oldsize
        if data[:3] == b"ADT":
            from gfx_adt import entries
            print(f"  {name}: {oldsize} -> {len(data)} ({d:+d}B)  "
                  f"ADT 컨테이너 {len(entries(data))}프레임")
        else:
            h = da1.parse_header(data)
            print(f"  {name}: {oldsize} -> {len(data)} ({d:+d}B)  "
                  f"{h['w']*8}x{h['h']} @({h['x']*8},{h['y']})")
        if write:
            need, had = fs.write(name, data)
            if need > had:
                print(f"      클러스터 {had} -> {need}")
        ok += 1

    if write and ok:
        fs.save(hdi)
        after = len(Fat12(hdi).free_clusters())
        print(f"  반영 {ok}개, 빈 클러스터 {free_before} -> {after}")
    return ok


def main():
    write = "--write" in sys.argv
    hdi = os.path.join(C.OUT_DIR, "xenon_ko.hdi")
    if not os.path.isfile(hdi):
        print("out/xenon_ko.hdi 가 없다. build.py 를 먼저 돌려라.")
        return 1
    n = apply(hdi, write)
    if not write and n:
        print("\n--write 를 붙이면 반영합니다. (build.py 가 자동으로 호출한다)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
