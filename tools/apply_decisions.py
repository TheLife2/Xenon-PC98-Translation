"""2026-08-09 사용자 결정 반영.

  ① 2인칭 : 화자가 ［私］(나) 면 「당신」 유지, ［コウジ］ 면 「너」로 대체
             (원문이 君 인 줄에 한함. あなた 102줄은 성인 화자 간이라 그대로 둔다)
  ② 정형 인사 : 유지 (변경 없음)
  ③ 「、という」 쉼표 : 제거
  ④ 숫자 표기 : 유지 (변경 없음)

    py tools/apply_decisions.py            미리보기
    py tools/apply_decisions.py --write    반영
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kocfg as C

SINGLE = os.path.join(C.ROOT, "translation", "새 폴더")
TODO = os.path.join(C.ROOT, "translation", "todo")
TAG = re.compile(r"^[(?]?［([^］]{1,14})］：?")

# ---------------------------------------------------------------- ① 2인칭 ----
# 「너」는 주격에서 '네가' 가 되고 관형격은 '네' 다. 형태별로 명시한다.
YOU = [("당신은", "너는"), ("당신이", "네가"), ("당신을", "너를"),
       ("당신의", "네"), ("당신에게", "너한테"), ("당신도", "너도"),
       ("당신 ", "네 "), ("당신?", "너?"), ("당신", "너")]


def to_neo(ko):
    for a, b in YOU:
        ko = ko.replace(a, b)
    return ko


# ---------------------------------------------------------------- ③ 쉼표 ----
# 조사·어미가 붙는 것은 쉼표와 공백을 함께 지운다.
BOUND = ("이라는", "라는", "이라", "라고", "인가")
# 「하는」 은 동사라 쉼표만 지우고 공백은 남긴다.
VERB = ("하는",)
RE_BOUND = re.compile(r"([가-힣])[,，]\s*(" + "|".join(BOUND) + r")")
RE_VERB = re.compile(r"([가-힣])[,，]\s*(" + "|".join(VERB) + r")")

# 쉼표가 진짜 절 경계인 곳. 지우면 뜻이 바뀐다.
KEEP_COMMA = [
    "해서는, 하는 말도",      # 「~해서는」 + 「하는 말도」 — 연결어미 뒤의 절 경계
    "있지만, 하는 짓은",      # 「~있지만」 + 「하는 짓은」
    "잘 있어라, 라고",        # 인용문 끝 「-어라」 + 라고. 붙이면 '있어라라고' 가 된다
]


def drop_comma(ko):
    for k in KEEP_COMMA:
        if k in ko:
            return ko
    ko = RE_BOUND.sub(r"\1\2", ko)
    ko = RE_VERB.sub(r"\1 \2", ko)
    return ko


def convert(jp, ko):
    m = TAG.match(jp)
    who = m.group(1) if m else None
    new = ko
    why = []
    if "君" in jp and "당신" in ko and (who == "コウジ" or (who is None and "君" in jp)):
        new = to_neo(new)
        why.append("2인칭 -> 너")
    n2 = drop_comma(new)
    if n2 != new:
        new = n2
        why.append("쉼표 제거")
    return new, ", ".join(why)


def main(write):
    pairs = C.load_pairs()
    hits = []
    for jp, ko in pairs:
        if not ko.strip():
            continue
        new, why = convert(jp, ko)
        if new != ko:
            hits.append((jp, ko, new, why))

    a = [h for h in hits if "2인칭" in h[3]]
    b = [h for h in hits if "쉼표" in h[3]]
    print(f"① 2인칭 -> 너 : {len(a)}줄")
    for jp, o, n, _ in a:
        print(f"    - {o[:60]}")
        print(f"    + {n[:60]}")
    print(f"\n③ 쉼표 제거 : {len(b)}줄")
    for jp, o, n, _ in b[:16]:
        print(f"    - {o[:64]}")
        print(f"    + {n[:64]}")
    if len(b) > 16:
        print(f"    ... 외 {len(b)-16}줄")

    print(f"\n쉼표를 남긴 예외 {len(KEEP_COMMA)}건:")
    for k in KEEP_COMMA:
        print(f"    {k}")

    def blen(s):
        return sum(1 if ord(c) < 0x80 else 2 for c in s)
    over = [n for _, _, n, _ in hits if blen(n) > C.MAX_BLOCK_BYTES]
    print(f"\n255바이트 초과 {len(over)}줄")

    if not write:
        print("--write 를 붙이면 반영합니다.")
        return

    nf = 0
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
                    cur = nxt if has else ""
                    new, _ = convert(jp, cur) if cur else (cur, "")
                    if new != cur:
                        out.append(new)
                        touched = True
                    elif has:
                        out.append(cur)
                    i += 2 if has else 1
                    continue
                i += 1
            if touched:
                open(p, "w", encoding="utf-8", newline="\n").write("\n".join(out))
                nf += 1

    path = os.path.join(C.ROOT, "translation", "overrides.txt")
    MARK = "# 13) 2인칭 / 쉼표"
    cur = open(path, encoding="utf-8").read()
    cut = cur.find(MARK)
    head = cur[:cut] if cut >= 0 else cur.rstrip("\n") + "\n\n"
    blk = (MARK + " (2026-08-09 사용자 결정)\n"
           "#    2인칭 : 화자가 ［私］면 '당신' 유지, ［コウジ］면 '너'. 원문이 君 인 줄에 한함\n"
           "#    쉼표  : 「、という」 계열의 쉼표 제거. 조사·어미는 붙이고, 동사 '하는' 앞은 공백 유지\n"
           "#            절 경계인 쉼표 3곳은 예외로 남겼다\n"
           "# ============================================================\n")
    for jp, _o, new, _w in hits:
        blk += f"//{jp}\n{new}\n"
    open(path, "w", encoding="utf-8", newline="\n").write(head + blk)
    print(f"\n반영: 원본 작업 파일 {nf}개, overrides 13번 섹션에 {len(hits)}줄")


if __name__ == "__main__":
    main("--write" in sys.argv)
