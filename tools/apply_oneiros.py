"""「드림 프로그램」 -> 「ONEIROS 프로그램」 통일.

2026-08-09 확정. 화면 라벨을 ＯＮＥＩＲＯＳ 로 유지하기로 했으므로, 대사 속 기계 이름도
같은 말로 맞춘다. 그리스어 부분은 한글 음차(오네이로스)가 아니라 로마자로 적는다.

  화면 라벨 : ＯＮＥＩＲＯＳ   (전각 - 원문 ＤＲＥＡＭ 이 전각이었다)
  대사 속   : ONEIROS 프로그램 (반각 - 문장 안에 섞이므로. 전각보다 7바이트 절약)

조사 호응 : '램'(받침 ㅁ) 으로 끝나므로 '드림 프로그램' 과 동일. 바꿀 것이 없다.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kocfg as C

SINGLE = os.path.join(C.ROOT, "translation", "새 폴더")
TODO = os.path.join(C.ROOT, "translation", "todo")
RULES = [("드림 프로그램", "ONEIROS 프로그램"), ("드림프로그램", "ONEIROS 프로그램")]


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
        print(f"  - {old[:66]}")
        print(f"  + {new[:66]}")

    # 길이 확인 (255바이트 상한)
    def blen(s):
        return sum(1 if ord(c) < 0x80 else 2 for c in s)
    worst = max((blen(n), n) for _, _, n in hits) if hits else (0, "")
    print(f"\n최장 {worst[0]}바이트 (상한 255)")
    for _, o, n in hits:
        d = blen(n) - blen(o)
        if d > 0:
            print(f"  +{d}바이트 : {n[:56]}")

    if not write:
        print("\n--write 를 붙이면 반영합니다.")
        return

    # 원본 작업 파일도 함께 고친다 (--collect 가 되돌리지 않도록)
    table = {jp: new for jp, _o, new in hits}
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

    # overrides 10번 섹션
    path = os.path.join(C.ROOT, "translation", "overrides.txt")
    MARK = "# 10) 드림 프로그램 -> ONEIROS 프로그램"
    cur = open(path, encoding="utf-8").read()
    cut = cur.find(MARK)
    head = cur[:cut] if cut >= 0 else cur.rstrip("\n") + "\n\n"
    blk = (MARK + " (2026-08-09 확정)\n"
           "#    화면 라벨을 ＯＮＥＩＲＯＳ 로 유지하기로 했으므로 대사 속 기계 이름도 맞춘다.\n"
           "#    그리스어 부분은 한글 음차가 아니라 로마자로 적는다.\n"
           "#    영문판은 이 통일을 메모(translation-notes.rtf)에만 남기고 배포본에는\n"
           "#    'dream program' 으로 내보내 같은 불일치를 안고 있다.\n"
           "# ============================================================\n")
    for jp, _o, new in hits:
        blk += f"//{jp}\n{new}\n"
    open(path, "w", encoding="utf-8", newline="\n").write(head + blk)
    print(f"\n반영: 원본 작업 파일 {nf}개 수정, overrides 10번 섹션에 {len(hits)}줄 기록")


if __name__ == "__main__":
    main("--write" in sys.argv)
