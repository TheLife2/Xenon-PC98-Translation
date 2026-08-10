"""의성어·의태어와 관용구를 문맥과 함께 점검한다.

번역은 아직 _script-korean.txt 에 병합되지 않았으므로
translation/새 폴더(낱개) 를 함께 읽어 현재 상태를 만든다.

    py tools/review_sfx.py             지정 항목 + 문맥
    py tools/review_sfx.py --all-sfx   의성어로 보이는 줄 전량
    py tools/review_sfx.py --dup       같은 원문이 다르게 번역된 것
"""
import os
import re
import sys
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kocfg as C
from kobatch import read_units
from koscript import key_of

SINGLE = os.path.join(C.ROOT, "translation", "새 폴더")


def current_map():
    """병합본 + 새 폴더 를 합친 {일본어: 한국어}."""
    km = {jp: ko for jp, ko in C.load_pairs() if ko.strip()}
    if os.path.isdir(SINGLE):
        for fn in sorted(os.listdir(SINGLE)):
            if not fn.endswith(".txt") or fn.startswith("_"):
                continue
            for _, jp, ko in read_units(os.path.join(SINGLE, fn)):
                if ko.strip():
                    km[jp] = ko
    return km


def script_order():
    """(스크립트, 인덱스, 키) 를 게임 진행 순서대로."""
    seq = []
    for name in C.SCRIPT_NAMES:
        data = open(os.path.join(C.SCRIPTS_CC, name + ".U.CC"), "rb").read()
        for n, (_, _, s, e) in enumerate(C.iter_blocks(data)):
            seq.append((name, n, key_of(data[s:e])))
    return seq


KM = current_map()
SEQ = script_order()
POS = {}
for i, (name, n, k) in enumerate(SEQ):
    POS.setdefault(k, []).append(i)


def show_context(key, before=3, after=3):
    for at in POS.get(key, [])[:1]:
        name = SEQ[at][0]
        lo, hi = max(0, at - before), min(len(SEQ), at + after + 1)
        print(f"  --- {name} #{SEQ[at][1]} ---")
        for i in range(lo, hi):
            nm, _, k = SEQ[i]
            if nm != name:
                continue
            mark = ">>" if i == at else "  "
            ko = KM.get(k, "")
            print(f"  {mark} JP {k[:64]}")
            print(f"     KO {ko[:64] if ko else '(미번역)'}")
        print()


TARGETS = [
    "ずりゅっ", "下の下", "クチュクチュ", "くちゅっ", "コリッ",
    "乳首もしごかれ", "ぬりゅ", "にちゃっ", "ズリュッ",
]

# 의성어 판정 : 화자 태그가 없고, 가나(+제어코드/문장부호)로만 이루어진 짧은 줄
KANA = re.compile(r"^[ぁ-んァ-ヶー・、。！？‥…～＝\s　!?.,～~\-—ー<>$0-9A-Fa-f]+$")


def is_sfx(k):
    body = re.sub(r"<[$][0-9A-Fa-f]{2}>", "", k).strip()
    if not body or body.startswith("［") or len(body) > 30:
        return False
    return bool(KANA.match(body))


if "--dup" in sys.argv:
    print("=== 같은 원문이 다르게 번역된 것 ===")
    inv = collections.defaultdict(set)
    for jp, ko in KM.items():
        pass
    # 원문이 같으면 키가 같으므로 중복 불가. 대신 '비슷한 의성어' 군집을 본다.
    fam = collections.defaultdict(list)
    for name, n, k in SEQ:
        if is_sfx(k) and k in KM:
            base = re.sub(r"[っッぅィゥ‥…！～~。、\s　]", "", k)[:3]
            fam[base].append((k, KM[k]))
    for base, rows in sorted(fam.items(), key=lambda x: -len({r[1] for r in x[1]})):
        uniq = {}
        for k, v in rows:
            uniq.setdefault(v, set()).add(k)
        if len(uniq) < 2:
            continue
        print(f"  [{base}]")
        for v, ks in uniq.items():
            print(f"     {v:28s} <- {' / '.join(sorted(ks))[:70]}")
        print()
    sys.exit(0)

if "--all-sfx" in sys.argv:
    print("=== 의성어로 보이는 줄 전량 ===")
    seen = set()
    rows = []
    for name, n, k in SEQ:
        if k in seen or not is_sfx(k):
            continue
        seen.add(k)
        rows.append((name, k, KM.get(k, "")))
    print(f"  {len(rows)}줄\n")
    for name, k, ko in rows:
        print(f"  {name:8s} {k[:38]:40s} -> {ko[:44]}")
    sys.exit(0)

for t in TARGETS:
    keys = [k for _, _, k in SEQ if t in k]
    seen = set()
    keys = [k for k in keys if not (k in seen or seen.add(k))]
    print("=" * 72)
    print(f"■ {t}   ({len(keys)}줄)")
    print("=" * 72)
    for k in keys:
        show_context(k)
