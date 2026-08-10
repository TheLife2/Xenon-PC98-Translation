"""의성어·의태어 정규화.

translation/sfx.json 의 표준표를 근거로, 일본어 원문에서 한국어를 다시 만들어 낸다.
기존 한국어를 고치는 게 아니라 원문에서 생성하므로, 같은 원문은 반드시 같은 표기가 된다.

    py tools/kosfx.py            검사만 (무엇이 바뀔지 보여 준다)
    py tools/kosfx.py --write    새 폴더 / todo / overrides.txt 에 반영

안전 장치
  * 한 줄의 가나 토큰이 전부 표에 있을 때만 정규화한다. 하나라도 없으면 건드리지 않는다.
  * 화자 태그(［…］)가 붙은 대사 줄은 대상이 아니다. 순수 의성어 줄만 본다.
  * 늘임 길이는 6까지로 자른다(255바이트 상한 보호).
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kocfg as C
from kobatch import read_units
from koscript import key_of

SFX_PATH = os.path.join(C.ROOT, "translation", "sfx.json")
SINGLE = os.path.join(C.ROOT, "translation", "새 폴더")
TODO = os.path.join(C.ROOT, "translation", "todo")
OVERRIDES = os.path.join(C.ROOT, "translation", "overrides.txt")

RAW = json.load(open(SFX_PATH, encoding="utf-8"))
FAM = {f["jp"]: f for f in RAW["families"]}
# 긴 어간 우선 (ぶちゅる 이 ぶちゅ 보다 먼저)
STEMS = sorted(FAM, key=len, reverse=True)
AVOID = RAW.get("avoid", [])

STRETCH_CH = "ぁぃぅぇぉーァィゥェォ"
MAX_STRETCH = 6


def kata_to_hira(s):
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s)


def expand(fam, n):
    """늘임 n 단계를 적용한 한국어.

    n=0 이면 base, n>=1 이면 long 의 '{}' 자리에 fill 을 (n-1)번 넣는다.
    """
    if n <= 0:
        return fam["base"]
    n = min(n, MAX_STRETCH)
    return fam["long"].replace("{}", fam["fill"] * (n - 1))


TOKEN = re.compile(r"[ぁ-んァ-ヶー]+|<[$][0-9A-Fa-f]{2}>|[^ぁ-んァ-ヶー]")

PUNCT = {"、": ", ", "。": ".", "！": "!", "？": "?", "　": "　",
         "‥": "‥", "…": "‥", "～": "~", "・": "·", " ": " "}


def repeat(fam, r):
    """어간 끝 가나가 r번 더 반복될 때 (ずぷぷぷ 처럼)."""
    if "rep" not in fam:
        return None
    r = min(r, MAX_STRETCH)
    return fam["rep"].replace("{}", fam["repfill"] * r)


def convert_run(run):
    """가나 덩어리 하나 -> 한국어. 실패하면 None."""
    h = kata_to_hira(run)
    out = []
    i = 0
    while i < len(h):
        hit = None
        for stem in STEMS:
            if h.startswith(stem, i):
                hit = stem
                break
        if hit is None:
            return None
        i += len(hit)
        fam = FAM[hit]
        # 어간 끝 가나의 추가 반복 (ずぷ + ぷぷぷ)
        r = 0
        while i < len(h) and h[i] == hit[-1]:
            r += 1
            i += 1
        n = 0
        while i < len(h) and h[i] in STRETCH_CH:
            n += 1
            i += 1
        # 촉음(っ)은 기본형에 이미 반영돼 있으므로 건너뛴다
        while i < len(h) and h[i] == "っ":
            i += 1
        if r:
            piece = repeat(fam, r)
            if piece is None:
                return None
        else:
            piece = expand(fam, n)
        out.append(piece)
    return "".join(out)


# 순수 의성어 줄이 아님을 알려 주는 문자 : 라틴 문자·숫자·한자·전각영숫자
NOT_SFX = re.compile(r"[A-Za-z0-9一-鿿０-９Ａ-Ｚａ-ｚ]")


def convert_line(jp):
    """의성어 줄 전체 -> 한국어. 대상이 아니거나 미지 토큰이 있으면 None."""
    body = re.sub(r"<[$][0-9A-Fa-f]{2}>", "", jp)
    if "［" in body or "］" in body:
        return None
    # 라벨·파일명·한자 섞인 문장은 대상이 아니다
    if NOT_SFX.search(body):
        return None
    # 가나가 하나도 없으면 대상이 아니다
    if not re.search(r"[ぁ-んァ-ヶー]", body):
        return None

    out = []
    matched = False
    for m in TOKEN.finditer(jp):
        t = m.group(0)
        if re.fullmatch(r"[ぁ-んァ-ヶー]+", t):
            c = convert_run(t)
            if c is None:
                return None
            matched = True
            out.append(c)
        elif t.startswith("<$"):
            out.append(t)
        else:
            out.append(PUNCT.get(t, t))
    if not matched:
        return None
    res = "".join(out).strip()
    res = re.sub(r",\s*$", "", res)
    return res or None


# ------------------------------------------------------------------ 수집 ----
def current_map():
    km = {jp: ko for jp, ko in C.load_pairs() if ko.strip()}
    if os.path.isdir(SINGLE):
        for fn in sorted(os.listdir(SINGLE)):
            if fn.endswith(".txt") and not fn.startswith("_"):
                for _, jp, ko in read_units(os.path.join(SINGLE, fn)):
                    if ko.strip():
                        km[jp] = ko
    return km


def sfx_keys():
    keys = []
    seen = set()
    for name in C.SCRIPT_NAMES:
        data = open(os.path.join(C.SCRIPTS_CC, name + ".U.CC"), "rb").read()
        for _, _, s, e in C.iter_blocks(data):
            k = key_of(data[s:e])
            if k not in seen:
                seen.add(k)
                keys.append(k)
    return keys


def plan():
    km = current_map()
    change, same, skip = [], [], []
    for k in sfx_keys():
        new = convert_line(k)
        if new is None:
            continue
        old = km.get(k, "")
        if old == new:
            same.append((k, old))
        else:
            change.append((k, old, new))
    # 표에 없어서 손대지 못한 의성어 중, 금지 표기가 남은 것
    left = []
    for k, ko in km.items():
        if convert_line(k) is not None:
            continue
        if "*" in ko or any(a in ko for a in AVOID):
            left.append((k, ko))
    return change, same, left


def write(change):
    # 1) 낱개 파일 / todo 파일을 줄 단위로 다시 쓴다
    table = {jp: new for jp, _old, new in change}
    n_files = 0
    for folder, pre in ((SINGLE, None), (TODO, "TODO_")):
        if not os.path.isdir(folder):
            continue
        for fn in sorted(os.listdir(folder)):
            if not fn.endswith(".txt") or fn.startswith("_"):
                continue
            if pre and not fn.startswith(pre):
                continue
            p = os.path.join(folder, fn)
            lines = open(p, encoding="utf-8").read().split("\n")
            out = []
            i = 0
            touched = False
            while i < len(lines):
                line = lines[i].rstrip("\r")
                out.append(line)
                if line.startswith("//"):
                    jp = line[2:]
                    nxt = lines[i + 1].rstrip("\r") if i + 1 < len(lines) else None
                    has = nxt is not None and not nxt.startswith(("//", "#"))
                    if jp in table:
                        out.append(table[jp])
                        touched = True
                    elif has:
                        out.append(nxt)
                    i += 2 if has else 1
                    continue
                i += 1
            if touched:
                open(p, "w", encoding="utf-8", newline="\n").write("\n".join(out))
                n_files += 1

    # 2) overrides.txt 에 기록 (배치를 다시 돌려도 유지되도록)
    cur = open(OVERRIDES, encoding="utf-8").read()
    MARK = "# 6) 의성어 정규화"
    cut = cur.find(MARK)
    head = cur[:cut] if cut >= 0 else cur.rstrip("\n") + "\n\n"
    block = (MARK + " - kosfx.py 자동 생성 (translation/sfx.json 기준)\n"
             "#    일본어 원문에서 한국어를 생성하므로 같은 원문은 항상 같은 표기가 된다.\n"
             "# ============================================================\n")
    for jp, _old, new in change:
        block += f"//{jp}\n{new}\n"
    open(OVERRIDES, "w", encoding="utf-8", newline="\n").write(head + block)
    return n_files, len(change)


if __name__ == "__main__":
    change, same, left = plan()
    print(f"표준표 계열 {len(FAM)}개")
    print(f"정규화 대상 의성어 줄 : 변경 {len(change)} / 이미 일치 {len(same)}")
    print()
    for jp, old, new in change[:40]:
        print(f"  {jp[:34]:36s}")
        print(f"     - {old[:52]}")
        print(f"     + {new[:52]}")
    if len(change) > 40:
        print(f"  ... 외 {len(change)-40}줄")
    print()
    if left:
        print(f"표에 없어 손대지 못했으나 금지 표기/별표가 남은 줄 {len(left)}개:")
        for k, ko in left[:12]:
            print(f"    {k[:34]:36s} -> {ko[:44]}")
    if "--write" in sys.argv:
        nf, nc = write(change)
        print()
        print(f"반영: 파일 {nf}개 수정, overrides.txt 에 {nc}줄 기록")
        print("  이어서:  py tools/kobatch.py merge  ->  py tools/build.py")
