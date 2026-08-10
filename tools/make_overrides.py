"""조사 결과를 overrides.txt 항목으로 생성한다.

  D) 마이의 「宏治サン」 말버릇 : 한국어 '씨' -> '상' 으로 구분
     게임이 이 말버릇을 지문에서 세 번 명시적으로 설명하므로, 한국어에서도
     표기로 드러나야 한다. 「코지 씨」(보통) vs 「코지 상」(마이) 으로 가른다.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kocfg as C

pairs = C.load_pairs()
out = []

# 「씨」는 모음으로 끝나고 「상」은 받침(ㅇ)으로 끝난다. 뒤따르는 조사를 바꿔 줘야 한다.
PARTICLE = [("상는", "상은"), ("상가", "상이"), ("상를", "상을"),
            ("상와", "상과"), ("상랑", "상이랑"), ("상로", "상으로"),
            ("상라고", "상이라고"), ("상야", "상이야"), ("상다", "상이다")]


def san(ko):
    for a, b in (("코우지 씨", "코우지 상"), ("코지 씨", "코지 상"),
                 ("코우지씨", "코우지 상"), ("코지씨", "코지 상")):
        ko = ko.replace(a, b)
    for a, b in PARTICLE:
        ko = ko.replace(a, b)
    return ko


# --- D-1. 마이가 「宏治サン / コウジサン」 이라고 부르는 줄 ---
n_line = 0
for jp, ko in pairs:
    if not ko.strip():
        continue
    if "宏治サン" not in jp and "コウジサン" not in jp:
        continue
    # 이미 반영된 줄도 빠짐없이 적어 둔다. 배치를 처음부터 다시 돌려도
    # overrides.txt 만으로 말버릇 표기가 복원되어야 한다.
    out.append((jp, san(ko), "마이 말버릇"))
    n_line += 1

# --- D-2. 말버릇을 설명하는 지문 3줄 : 「씨」 -> 「상」 ---
NARR = {
    "最後の「さん」のイントネーションが、少し妙な発音になっている。この子の特徴だった。":
        "마지막 「상」의 억양이, 조금 묘한 발음이 되어 있다. 이 아이의 특징이었다.",
    "相変わらず、「さん」のイントネーションが少し変だったが、そこがまた魅力のような気がする‥‥舞だ。":
        "여전히 「상」의 억양이 조금 이상했지만, 그게 또 매력처럼 느껴진다‥‥마이다.",
    "さんの敬称に、妙な発音をする女だった。この女は私のことを知っているらしいが‥‥。":
        "「상」이라는 경칭을 묘하게 발음하는 여자였다. 이 여자는 나를 아는 모양이지만‥‥.",
}
kmap = dict(pairs)
for jp, ko in NARR.items():
    if jp in kmap:
        out.append((jp, ko, "말버릇 설명 지문"))

print(f"마이 말버릇 줄 {n_line}개, 설명 지문 {len(NARR)}개")

# --- E. 용어 확정 (2026-08-09 사용자 지시) ---
# 치환 순서가 중요하다. 조사가 붙은 형태를 먼저 잡아야 호응이 맞는다.
#   흡반(받침 ㄴ) -> 흡착판(받침 ㄴ)  : 조사 그대로
#   소망(받침 ㅇ) -> 욕구(모음)       : 을->를, 은->는, 이->가, 과->와
TERM_FIX = [
    ("吸盤", [("흡반", "흡착판")]),
    ("回帰願望", [("회귀 소망을", "퇴행 욕구를"), ("회귀 소망은", "퇴행 욕구는"),
                 ("회귀 소망이", "퇴행 욕구가"), ("회귀 소망과", "퇴행 욕구와"),
                 ("회귀 소망", "퇴행 욕구")]),
    ("心的価値", [("심적 가치", "정신적 가치")]),
]
n_term = 0
for jp, ko in pairs:
    if not ko.strip():
        continue
    new = ko
    for jpterm, rules in TERM_FIX:
        if jpterm not in jp:
            continue
        for a, b in rules:
            new = new.replace(a, b)
    if new != ko:
        out.append((jp, new, "용어 확정"))
        n_term += 1
print(f"용어 확정 치환 {n_term}줄")

# --- overrides.txt 의 '# 5)' 이후를 통째로 다시 쓴다 (손으로 적은 1~4번은 보존) ---
MARK = "# 5) 마이의"
path = os.path.join(C.ROOT, "translation", "overrides.txt")
cur = open(path, encoding="utf-8").read()
cut = cur.find(MARK)
head = cur[:cut] if cut >= 0 else cur.rstrip("\n") + "\n\n"

block = (MARK + " 「さん」 말버릇 - make_overrides.py 자동 생성분\n"
         "#    게임이 지문에서 이 말버릇을 세 번 설명하므로 한국어에도 드러나야 한다.\n"
         "#    보통 「코지 씨」 / 마이만 「코지 상」.\n"
         "#    「씨」는 모음, 「상」은 받침으로 끝나므로 조사도 바꾼다\n"
         "#    (상는->상은, 상가->상이, 상를->상을, 상와->상과).\n"
         "# ============================================================\n")
for jp, ko, why in out:
    block += f"# {why}\n//{jp}\n{ko}\n"

with open(path, "w", encoding="utf-8", newline="\n") as f:
    f.write(head + block)
print(f"작성: {path}  (총 {len(out)}개 항목)")
