"""사용자 요청 조사 - DREAM 표기 / 화자 오배정 / 말버릇 / 료코 어체"""
import os
import re
import sys
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kocfg as C

pairs = C.load_pairs()
kmap = {jp: ko for jp, ko in pairs}
order = [jp for jp, _ in pairs]

# 영문판
EN = {}
p = os.path.join(C.TL_REPO, "script-japanese-with-translation.txt")
lines = open(p, encoding="utf-8").read().split("\n")
i = 0
while i < len(lines):
    if lines[i].rstrip("\r").startswith("//"):
        EN[lines[i].rstrip("\r")[2:]] = lines[i + 1].rstrip("\r") if i + 1 < len(lines) else ""
        i += 2
    else:
        i += 1

what = sys.argv[1] if len(sys.argv) > 1 else "all"


def show(jp, mark=""):
    print(f"  {mark}JP: {jp}")
    if EN.get(jp):
        print(f"     EN: {EN[jp]}")
    print(f"     KO: {kmap.get(jp, '(미번역)')}")
    print()


if what in ("all", "dream"):
    print("=" * 70)
    print("1) ＤＲＥＡＭ / ＯＮＥＩＲＯＳ 표기")
    print("=" * 70)
    for jp in order:
        if "ＤＲＥＡＭ" in jp or "DREAM" in jp or "ＯＮＥＩＲＯＳ" in (EN.get(jp) or ""):
            show(jp)
    print("-- 앞뒤 문맥 (알파벳 언급) --")
    for jp in order:
        if "アルファベット" in jp:
            show(jp)

if what in ("all", "kuse"):
    print("=" * 70)
    print("2) 「宏治サン」 말버릇 - 그것을 설명하는 대사")
    print("=" * 70)
    n = 0
    for jp in order:
        if "宏治サン" in jp or "コウジサン" in jp:
            n += 1
    print(f"  「宏治サン」/「コウジサン」 총 {n}줄\n")
    print("-- 억양/발음/호칭을 언급하는 줄 --")
    for jp in order:
        if re.search(r"(イントネーション|抑揚|呼び方|呼び名|言い方|発音|アクセント|サン.*妙|妙.*サン)", jp):
            show(jp)

if what in ("all", "speaker"):
    print("=" * 70)
    print("3) 화자 오배정 - 원문 태그와 영문판 태그가 다른 줄")
    print("=" * 70)
    RE_JP = re.compile(r"^[(?]?［([^］]{1,12})］")
    RE_EN = re.compile(r"^\[([^\]]{1,20})\]")
    TAGMAP = {
        "宏治": "Kouji", "コウジ": "Kouji", "涼子": "Ryouko", "トレイシー": "Tracy",
        "ランファ": "Lanhua", "ファル": "Far", "沙夜香": "Sayaka", "舞": "Mai",
        "恵": "Megumi", "ビアンカ": "Bianca",
    }
    hits = []
    for jp in order:
        mj = RE_JP.match(jp)
        me = RE_EN.match(EN.get(jp) or "")
        if not mj or not me:
            continue
        j, e = mj.group(1), me.group(1)
        if j not in TAGMAP:
            continue
        want = TAGMAP[j]
        if e.lower().replace("ij", "ji") != want.lower():
            hits.append((jp, j, e, want))
    print(f"  불일치 {len(hits)}줄\n")
    for jp, j, e, want in hits:
        print(f"  ［{j}］ (영문판 [{e}], 기대 [{want}])")
        show(jp, "  ")

if what in ("all", "ryouko"):
    print("=" * 70)
    print("4) 료코 어체 - 존댓말로 되어 있는 줄 전량")
    print("=" * 70)
    POL = re.compile(r"(습니다|입니다|십시오|세요|어요|아요|예요|이에요|해요|죠[.?!‥]|죠$|"
                     r"군요|네요|지요|시죠|주죠|두죠|합쇼|시오)")
    for jp in order:
        if not jp.startswith("［涼子］"):
            continue
        ko = kmap.get(jp, "")
        if not ko or not POL.search(ko):
            continue
        sama = "宏治様" in jp or "コウジ様" in jp
        other = ("沙夜香" in jp or "さん" in jp) and not sama
        tag = "[様구간-유지]" if sama else ("[타인상대-유지]" if other else "[반말화 대상]")
        print(f"  {tag}")
        show(jp, "  ")
