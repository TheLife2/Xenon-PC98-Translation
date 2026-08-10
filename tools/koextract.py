"""원본 스크립트에서 번역 작업 파일을 만든다.

  translation/_script-korean.txt   실제 작업 파일.  '//일본어' 다음 줄에 한국어를 적는다.
  translation/reference-jp-en.txt  참조용 일본어/영문 대조표

기존 번역이 있으면 그대로 보존하고 새로 생긴 줄만 추가한다(-> 몇 번을 다시 돌려도 안전).
"""
import os
import re
import sys
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kocfg as C
from koscript import key_of


# 'xenon_01', 'BI06E_M', 'S0104' 같은 애셋/라벨 이름. 번역 대상이 아니고
# 건드리면 게임이 파일을 못 찾는다. 공백 없는 단일 토큰만 걸러낸다.
RE_LABEL = re.compile(r"^[A-Za-z0-9_.\-]+$")


def collect():
    """원본 37개 파일에서 유일한 번역 단위를 등장 순서대로 모은다."""
    keys = []
    seen = set()
    count = collections.Counter()
    skipped = collections.Counter()
    for name in C.SCRIPT_NAMES:
        data = open(os.path.join(C.SCRIPTS_CC, name + ".U.CC"), "rb").read()
        for _, _, s, e in C.iter_blocks(data):
            k = key_of(data[s:e])
            if not k.strip():
                skipped["빈 블록"] += 1
                continue
            if RE_LABEL.match(k):
                skipped["라벨/파일명"] += 1
                continue
            count[k] += 1
            if k not in seen:
                seen.add(k)
                keys.append(k)
    return keys, count, skipped


def load_en():
    """영문판 번역을 참조용으로 읽어 둔다(키 형식이 달라 완전 일치는 아니다)."""
    p = os.path.join(C.TL_REPO, "script-japanese-with-translation.txt")
    lines = open(p, encoding="utf-8").read().split("\n")
    out = {}
    i = 0
    while i < len(lines):
        l = lines[i].rstrip("\r")
        if l.startswith("//"):
            en = lines[i + 1].rstrip("\r") if i + 1 < len(lines) else ""
            out[l[2:]] = en
            i += 2
        else:
            i += 1
    return out


def main():
    keys, count, skipped = collect()
    en = load_en()
    existing = dict(C.load_pairs())

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from koverify import load_terms
    terms = load_terms()

    hit = 0
    with open(C.TRANSLATION, "w", encoding="utf-8", newline="\n") as f:
        f.write("# XENON ~夢幻の肢体~  한국어 번역 작업 파일\n")
        f.write("#   '//' 줄 = 일본어 원문(수정 금지).  바로 다음 줄에 한국어를 적는다.\n")
        f.write("#   빈 줄 = 미번역.  '#' 로 시작하는 줄은 주석.\n")
        f.write("#   \\n = 줄바꿈,  <$XX> = 게임 제어코드. 위치를 바꾸지 말 것.\n")
        f.write("#   금지: 연속 공백 3개 이상(크래시), '…'(U+2026), '–'(U+2013)\n")
        f.write("#   고유명사는 translation/GLOSSARY.md 규약을 따를 것\n\n")
        for k in keys:
            e = en.get(k, "")
            if e:
                hit += 1
                f.write("#EN " + e + "\n")
            # 배타 group 이 걸린 고유명사는 줄마다 알려 준다 (宏治=코지 / コウジ=코우지)
            need = sorted({f"{j}→{ko}" for j, ko, g in terms if g and j in k})
            if need:
                f.write("#!! 표기 " + "  ".join(need) + "\n")
            f.write("//" + k + "\n")
            f.write(existing.get(k, "") + "\n")

    with open(C.REFERENCE, "w", encoding="utf-8", newline="\n") as f:
        for k in keys:
            f.write(f"[{count[k]}회] {k}\n     EN: {en.get(k, '(없음)')}\n\n")

    kept = sum(1 for k in keys if existing.get(k))
    print(f"번역 단위 {len(keys)}개 (전체 등장 {sum(count.values())}회)")
    print(f"제외: " + ", ".join(f"{k} {v}개" for k, v in skipped.items()))
    print(f"영문 참조 매칭 {hit}개 ({100*hit/len(keys):.1f}%)")
    print(f"기존 한국어 보존 {kept}개")
    print("작성:", C.TRANSLATION)
    print("작성:", C.REFERENCE)


if __name__ == "__main__":
    main()
