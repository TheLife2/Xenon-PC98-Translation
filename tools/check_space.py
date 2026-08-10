"""전각 공백(U+3000) 들여쓰기 점검.

두 가지를 본다.
  1. '연속 공백 3개 이상 = 크래시' 규칙이 전각 공백에도 적용되는가
     -> 원본 일본어 스크립트 자체에 전각 공백이 몇 개까지 연속하는지 보면 답이 나온다.
        원본이 3개 이상 쓰고 있다면 그 규칙은 반각 공백(U+0020) 전용이다.
  2. 원문의 선두 들여쓰기를 번역이 얼마나 보존했는가
"""
import os
import re
import sys
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kocfg as C
from koscript import key_of

FW = "　"
RE_CTRL = re.compile(r"<[$][0-9A-Fa-f]{2}>")


def runs(s, ch):
    return [len(m.group(0)) for m in re.finditer(re.escape(ch) + "+", s)]


def strip_ctrl(s):
    return RE_CTRL.sub("", s).replace(chr(92) + "n", "\n")


def main():
    pairs = C.load_pairs()

    # ---- 1. 원본이 쓰는 공백 ----
    jp_fw = collections.Counter()
    jp_hw = collections.Counter()
    for jp, _ in pairs:
        t = strip_ctrl(jp)
        for n in runs(t, FW):
            jp_fw[n] += 1
        for n in runs(t, " "):
            jp_hw[n] += 1

    print("=== 1. 일본어 원문이 실제로 쓰는 연속 공백 ===")
    print("  전각 공백(U+3000) 연속 길이별 등장 횟수")
    for n in sorted(jp_fw):
        mark = "   <- 3개 이상" if n >= 3 else ""
        print(f"    {n:2d}개 연속 : {jp_fw[n]:5d}회{mark}")
    print(f"  최대 {max(jp_fw) if jp_fw else 0}개 연속")
    print()
    print("  반각 공백(U+0020) 연속 길이별")
    for n in sorted(jp_hw):
        print(f"    {n:2d}개 연속 : {jp_hw[n]:5d}회")
    print(f"  최대 {max(jp_hw) if jp_hw else 0}개 연속")
    print()
    over3 = sum(v for k, v in jp_fw.items() if k >= 3)
    print(f"  판정 : 원본이 전각 공백을 3개 이상 연속으로 {over3}회 쓴다.")
    print("         원본은 크래시 없이 동작하므로, '연속 공백 3개 = 크래시' 규칙은")
    print("         반각 공백(U+0020) 전용이며 전각 공백에는 적용되지 않는다."
          if over3 else "         전각 공백 3연속 사례가 없어 판단 보류.")

    # ---- 2. 영문판이 쓰는 반각 공백 ----
    en = {}
    p = os.path.join(C.TL_REPO, "script-japanese-with-translation.txt")
    L = open(p, encoding="utf-8").read().split("\n")
    i = 0
    while i < len(L):
        if L[i].rstrip("\r").startswith("//"):
            en[L[i].rstrip("\r")[2:]] = L[i + 1].rstrip("\r") if i + 1 < len(L) else ""
            i += 2
        else:
            i += 1
    en_hw = collections.Counter()
    for v in en.values():
        for n in runs(strip_ctrl(v), " "):
            en_hw[n] += 1
    print()
    print("=== 2. 배포된 영문판의 반각 공백 (실제로 동작하는 패치) ===")
    for n in sorted(en_hw):
        if n >= 2:
            print(f"    {n:2d}개 연속 : {en_hw[n]:5d}회")
    print(f"  최대 {max(en_hw) if en_hw else 0}개 연속")

    # ---- 3. 선두 들여쓰기 보존 ----
    print()
    print("=== 3. 원문 선두 들여쓰기(전각 공백) 보존 상태 ===")
    keep = drop = add = same0 = 0
    dropped = []
    for jp, ko in pairs:
        if not ko.strip():
            continue
        j = len(strip_ctrl(jp)) - len(strip_ctrl(jp).lstrip(FW))
        k = len(strip_ctrl(ko)) - len(strip_ctrl(ko).lstrip(FW))
        if j == 0 and k == 0:
            same0 += 1
        elif j > 0 and k == j:
            keep += 1
        elif j > 0 and k < j:
            drop += 1
            if len(dropped) < 12:
                dropped.append((j, k, jp[:40], ko[:40]))
        elif k > j:
            add += 1
    tot = keep + drop + add
    print(f"  들여쓰기 있는 원문 {keep+drop}줄 중")
    print(f"    그대로 보존 {keep}줄 / 줄었거나 사라짐 {drop}줄")
    print(f"  원문에 없는데 추가된 줄 {add}")
    for j, k, a, b in dropped:
        print(f"    JP({j}) {a}")
        print(f"    KO({k}) {b}")

    # ---- 4. 현재 번역의 위험 여부 ----
    print()
    print("=== 4. 현재 번역의 반각 공백 3연속 (진짜 위험한 것) ===")
    risky = [(jp, ko) for jp, ko in pairs if ko.strip() and re.search(r" {3,}", strip_ctrl(ko))]
    print(f"  {len(risky)}줄")
    for jp, ko in risky[:10]:
        print(f"    {ko[:60]}")


if __name__ == "__main__":
    main()
