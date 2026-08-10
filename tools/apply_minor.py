"""용어 소소한 교정 (2026-08-09 사용자 지시).

    無機質            -> 삭막한      ('무기질적인/무기질한' 은 번역투)
    ネームプレート     -> 명찰        (같은 소품을 '명찰' 로 부르는 줄이 이미 있어 그쪽으로 통일)
    冷然と            -> 싸늘하게    ('냉연히' 는 한국어에서 거의 쓰이지 않는다)

    py tools/apply_minor.py            미리보기
    py tools/apply_minor.py --write    반영
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kocfg as C

SINGLE = os.path.join(C.ROOT, "translation", "새 폴더")
TODO = os.path.join(C.ROOT, "translation", "todo")

# 긴 형태를 먼저 (무기질적이고 가 무기질적인 보다 먼저)
RULES = [
    ("무기질적이고", "삭막하고"),
    ("무기질적인", "삭막한"),
    ("무기질한", "삭막한"),
    ("무기질", "삭막"),
    ("네임 플레이트", "명찰"),
    ("네임플레이트", "명찰"),
    ("냉연히", "싸늘하게"),
    ("냉연하게", "싸늘하게"),
]


def convert(ko):
    for a, b in RULES:
        ko = ko.replace(a, b)
    return ko


def main(write):
    pairs = C.load_pairs()
    hits = [(jp, ko, convert(ko)) for jp, ko in pairs
            if ko.strip() and convert(ko) != ko]
    print(f"대상 {len(hits)}줄")
    for jp, old, new in hits:
        print(f"  - {old[:70]}")
        print(f"  + {new[:70]}")

    def blen(s):
        return sum(1 if ord(c) < 0x80 else 2 for c in s)
    over = [n for _, _, n in hits if blen(n) > C.MAX_BLOCK_BYTES]
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
                    nxt = lines[i + 1].rstrip("\r") if i + 1 < len(lines) else None
                    has = nxt is not None and not nxt.startswith(("//", "#"))
                    cur = nxt if has else ""
                    new = convert(cur)
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
    MARK = "# 12) 용어 소소한 교정"
    cur = open(path, encoding="utf-8").read()
    cut = cur.find(MARK)
    head = cur[:cut] if cut >= 0 else cur.rstrip("\n") + "\n\n"
    blk = (MARK + " (2026-08-09 사용자 지시)\n"
           "#    無機質 -> 삭막한 / ネームプレート -> 명찰 / 冷然と -> 싸늘하게\n"
           "# ============================================================\n")
    for jp, _o, new in hits:
        blk += f"//{jp}\n{new}\n"
    open(path, "w", encoding="utf-8", newline="\n").write(head + blk)
    print(f"\n반영: 원본 작업 파일 {nf}개, overrides 12번 섹션에 {len(hits)}줄")


if __name__ == "__main__":
    main("--write" in sys.argv)
