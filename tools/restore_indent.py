"""원문의 전각 공백 들여쓰기를 복구한다.

배경
  배치 파싱 정규식이 `[|｜]\\s*` 였는데 파이썬의 \\s 는 전각 공백(U+3000)도
  공백으로 본다. 그래서 번역문 선두의 들여쓰기가 파싱 단계에서 조용히 지워졌다.
  배치 산출물(ko_*.txt) 자체에는 들여쓰기가 온전히 남아 있다.

  들여쓰기는 장식이 아니라 화면 정렬이다. 단말기 표시(P.P.E. / PSY encoder operating)와
  선택지(◆) 가 이것으로 위치를 잡는다. 왼쪽으로 몰리면 연출이 무너진다.

전각 공백과 크래시
  '연속 공백 3개 이상 = 크래시' 규칙은 반각 공백(U+0020) 전용이다.
  일본어 원문 자신이 전각 공백을 최대 13개까지 연속으로 쓰고 있고(3개 이상 27회),
  원본은 정상 동작한다. 반면 원문의 반각 공백은 최대 1개 연속,
  실제로 동작하는 영문판도 최대 2개 연속이다.

    py tools/restore_indent.py            무엇이 복구될지 보여 준다
    py tools/restore_indent.py --write    overrides.txt 11번 섹션에 기록
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kocfg as C

FW = "　"
RE_CTRL = re.compile(r"<[$][0-9A-Fa-f]{2}>")
BS = chr(92)


def lead(s):
    """선두 제어코드/줄바꿈 표기를 건너뛴 뒤의 전각 공백 개수와 그 위치."""
    i = 0
    while True:
        m = RE_CTRL.match(s, i)
        if m:
            i = m.end()
            continue
        if s.startswith(BS + "n", i):
            i += 2
            continue
        break
    n = 0
    while s.startswith(FW, i + n * len(FW)):
        n += 1
    return i, n


def trail(s):
    n = 0
    while s.endswith(FW * (n + 1)):
        n += 1
    return n


def main(write):
    pairs = C.load_pairs()
    fix = []
    for jp, ko in pairs:
        if not ko.strip():
            continue
        _, jn = lead(jp)
        ki, kn = lead(ko)
        jt, kt = trail(jp), trail(ko)
        new = ko
        why = []
        if jn > kn:
            new = new[:ki] + FW * (jn - kn) + new[ki:]
            why.append(f"선두 {kn}->{jn}")
        if jt > kt:
            new = new + FW * (jt - kt)
            why.append(f"말미 {kt}->{jt}")
        if new != ko:
            fix.append((jp, ko, new, ", ".join(why)))

    print(f"복구 대상 {len(fix)}줄")
    for jp, old, new, why in fix[:14]:
        print(f"  [{why}]")
        print(f"    JP {jp[:56]}")
        print(f"    -  {old[:56]}")
        print(f"    +  {new[:56]}")
    if len(fix) > 14:
        print(f"  ... 외 {len(fix)-14}줄")

    # 길이 확인
    def blen(s):
        return sum(1 if ord(c) < 0x80 else 2 for c in RE_CTRL.sub("", s))
    over = [(n, blen(n)) for _, _, n, _ in fix if blen(n) > C.MAX_BLOCK_BYTES]
    print(f"\n255바이트 초과 {len(over)}줄")
    for n, b in over[:5]:
        print(f"    {b}바이트 : {n[:50]}")

    if not write or not fix:
        if not write:
            print("\n--write 를 붙이면 반영합니다.")
        return

    path = os.path.join(C.ROOT, "translation", "overrides.txt")
    MARK = "# 11) 전각 공백 들여쓰기 복구"
    cur = open(path, encoding="utf-8").read()
    cut = cur.find(MARK)
    head = cur[:cut] if cut >= 0 else cur.rstrip("\n") + "\n\n"
    blk = (MARK + " (2026-08-09)\n"
           "#    배치 파싱 정규식의 \\s* 가 전각 공백(U+3000)까지 먹어 들여쓰기가 지워졌다.\n"
           "#    들여쓰기는 화면 정렬이다 - 단말기 표시와 선택지가 이것으로 위치를 잡는다.\n"
           "#    '연속 공백 3개 = 크래시' 규칙은 반각 공백 전용이며 전각 공백에는 적용되지 않는다\n"
           "#    (일본어 원문 자신이 전각 공백을 최대 13개 연속으로 쓴다).\n"
           "# ============================================================\n")
    for jp, _o, new, _w in fix:
        blk += f"//{jp}\n{new}\n"
    open(path, "w", encoding="utf-8", newline="\n").write(head + blk)
    print(f"\noverrides 11번 섹션에 {len(fix)}줄 기록")


if __name__ == "__main__":
    main("--write" in sys.argv)
