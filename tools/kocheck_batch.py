"""배치 하나(ko_NNN.txt)를 기계적으로 검사한다.

    py tools/kocheck_batch.py 000          한 배치
    py tools/kocheck_batch.py --all        번역된 배치 전부 (요약)

검사 결과는 사람/에이전트가 바로 고칠 수 있게 '번호 | 등급 | 내용' 으로 낸다.
LLM 이 눈으로 볼 필요가 없는 항목(줄 수·번호·제어코드·바이트수·금지문자·고유명사)은
전부 여기서 확정적으로 잡는다.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kocfg as C
from koscript import text_to_bytes
from koverify import load_terms
from kobatch import BATCH_DIR, read_units, RE_KO

RE_SPACES = re.compile(r" {3,}")
RE_CTRL = re.compile(r"<[$][0-9A-Fa-f]{2}>")
BAD = {"…": "U+2026 …", "–": "U+2013 –", "—": "U+2014 —"}


def check_batch(idx):
    src = os.path.join(BATCH_DIR, f"src_{idx}.txt")
    dst = os.path.join(BATCH_DIR, f"ko_{idx}.txt")
    if not os.path.exists(src):
        return [f"-- | 치명 | src_{idx}.txt 없음"], 0
    if not os.path.exists(dst):
        return [f"-- | 치명 | ko_{idx}.txt 없음"], 0

    jps = [u[1] for u in read_units(src)]
    terms = load_terms()
    table = C.load_table()
    issues = []
    seen = {}

    for raw in open(dst, encoding="utf-8-sig").read().split("\n"):
        line = raw.rstrip("\r")
        if not line.strip():
            continue
        m = RE_KO.match(line)
        if not m:
            issues.append(f"-- | 치명 | 형식 위반(‘번호|한국어’ 아님): {line[:60]}")
            continue
        # rstrip() 을 그냥 걸면 원문의 말미 전각 공백(메뉴 정렬용 패딩)이 날아간다.
        n, txt = int(m.group(1)), m.group(2).rstrip("\r\n")
        if not 1 <= n <= len(jps):
            issues.append(f"{n:03d} | 치명 | 번호 범위 밖 (1..{len(jps)})")
            continue
        if n in seen:
            issues.append(f"{n:03d} | 치명 | 번호 중복")
            continue
        seen[n] = txt

    for n in range(1, len(jps) + 1):
        if n not in seen:
            issues.append(f"{n:03d} | 치명 | 줄 누락 : {jps[n-1][:50]}")

    for n, ko in sorted(seen.items()):
        jp = jps[n - 1]
        if not ko.strip() or ko.strip().upper() == "#SKIP":
            issues.append(f"{n:03d} | 경고 | 건너뜀 : {jp[:50]}")
            continue

        if RE_SPACES.search(ko):
            issues.append(f"{n:03d} | 치명 | 연속 공백 3개 이상(게임 크래시) : {ko[:50]}")
        for ch, label in BAD.items():
            if ch in ko:
                issues.append(f"{n:03d} | 치명 | 금지 문자 {label} : {ko[:50]}")

        sc, dc = sorted(RE_CTRL.findall(jp)), sorted(RE_CTRL.findall(ko))
        if sc != dc:
            issues.append(f"{n:03d} | 치명 | 제어코드 불일치 {sc} -> {dc} : {ko[:40]}")
        if jp.count(chr(92) + "n") != ko.count(chr(92) + "n"):
            issues.append(f"{n:03d} | 치명 | 줄바꿈(\\n) 개수 불일치 "
                          f"{jp.count(chr(92)+'n')} -> {ko.count(chr(92)+'n')} : {ko[:40]}")

        # 고유명사 배타
        for g in {gg for _, _, gg in terms if gg}:
            hits = [(j, k) for j, k, gg in terms if gg == g and j in jp]
            if not hits:
                continue
            want = {k for _, k in hits}
            others = {k for j2, k, g2 in terms if g2 == g and k not in want}
            wrong = [o for o in others if o in ko]
            if wrong:
                issues.append(f"{n:03d} | 치명 | 고유명사 배타 위반: 원문 "
                              f"'{'/'.join(j for j, _ in hits)}' 인데 '{wrong[0]}' 사용 "
                              f"(→ '{'/'.join(sorted(want))}') : {ko[:40]}")
            elif not any(w in ko for w in want):
                issues.append(f"{n:03d} | 경고 | 고유명사 누락 "
                              f"'{'/'.join(sorted(want))}' : {ko[:40]}")

        # 길이 (슬롯 미할당 문자는 2바이트로 가정해 추정)
        try:
            nb = len(text_to_bytes(ko, table))
        except ValueError:
            nb = sum(1 if ord(c) < 0x80 else 2 for c in RE_CTRL.sub("", ko))
        jb = sum(1 if ord(c) < 0x80 else 2 for c in RE_CTRL.sub("", jp))
        if nb > C.MAX_BLOCK_BYTES:
            issues.append(f"{n:03d} | 치명 | {nb}바이트 > 255 : {ko[:40]}")
        elif nb > jb + 24:
            issues.append(f"{n:03d} | 경고 | 원문보다 {nb-jb}바이트 김 "
                          f"({jb}->{nb}) : {ko[:40]}")

    return issues, len(seen)


def main():
    if "--all" in sys.argv:
        ids = sorted(f[3:6] for f in os.listdir(BATCH_DIR) if f.startswith("ko_"))
        tot_f = tot_w = 0
        for i in ids:
            iss, n = check_batch(i)
            f = sum(1 for x in iss if "| 치명 |" in x)
            w = len(iss) - f
            tot_f += f
            tot_w += w
            flag = "  <-- 확인 필요" if f else ""
            print(f"  ko_{i}: {n}줄, 치명 {f} / 경고 {w}{flag}")
        print(f"\n합계: 배치 {len(ids)}개, 치명 {tot_f} / 경고 {tot_w}")
        return 1 if tot_f else 0

    idx = sys.argv[1] if len(sys.argv) > 1 else "000"
    idx = idx.zfill(3)
    issues, n = check_batch(idx)
    fatal = [x for x in issues if "| 치명 |" in x]
    print(f"ko_{idx}.txt : {n}줄, 치명 {len(fatal)} / 경고 {len(issues)-len(fatal)}")
    for x in issues:
        print("  " + x)
    if not issues:
        print("  문제 없음")
    return 1 if fatal else 0


if __name__ == "__main__":
    sys.exit(main())
