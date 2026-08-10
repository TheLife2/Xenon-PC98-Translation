"""전체 검수용 배치 분할 / 결과 반영.

    py tools/koreview.py split [단위수]   현재 번역을 rv_NNN.txt 로 분할 (기본 120)
    py tools/koreview.py apply            fix_NNN.txt 를 overrides.txt 에 반영
    py tools/koreview.py status           진행 상황

게임 진행 순서대로 자르므로 배치 안에서 장면 문맥이 이어진다.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kocfg as C
from koscript import key_of

RV = os.path.join(C.ROOT, "translation", "review")
os.makedirs(RV, exist_ok=True)
# \s 는 전각 공백(U+3000)도 먹으므로 반각 공백/탭만 흘려보낸다 (kobatch.py 와 동일)
RE_FIX = re.compile(r"^\s*(\d{1,4})[ \t]*[|｜][ \t]*(.*)$")


def ordered_units():
    """게임 진행 순서대로, 중복 없이 (일본어, 한국어)."""
    km = dict(C.load_pairs())
    out = []
    seen = set()
    for name in C.SCRIPT_NAMES:
        data = open(os.path.join(C.SCRIPTS_CC, name + ".U.CC"), "rb").read()
        for _, _, s, e in C.iter_blocks(data):
            k = key_of(data[s:e])
            if k in km and km[k].strip() and k not in seen:
                seen.add(k)
                out.append((name, k, km[k]))
    return out


def split(size=120):
    units = ordered_units()
    for f in os.listdir(RV):
        os.remove(os.path.join(RV, f))
    n = 0
    for b in range(0, len(units), size):
        chunk = units[b:b + size]
        idx = b // size
        with open(os.path.join(RV, f"rv_{idx:03d}.txt"), "w",
                  encoding="utf-8", newline="\n") as f:
            f.write(f"# 검수 배치 {idx:03d} : {len(chunk)}줄 "
                    f"({chunk[0][0]} ~ {chunk[-1][0]})\n")
            f.write("# 지침은 translation/REVIEW_GUIDE.md\n")
            f.write(f"# 고칠 줄만 fix_{idx:03d}.txt 에 'nnn|한국어' 로 적는다.\n\n")
            for k, (_, jp, ko) in enumerate(chunk, 1):
                f.write(f"#NO {k:03d}\n#JP {jp}\n#KO {ko}\n\n")
        n += 1
    print(f"번역 {len(units)}줄 -> 검수 배치 {n}개 (배치당 {size}줄)")
    print(f"  {RV}")
    return n


def apply():
    units = ordered_units()
    fixes = {}
    bad = []
    files = sorted(f for f in os.listdir(RV) if f.startswith("fix_"))
    for fn in files:
        idx = int(fn[4:7])
        src = os.path.join(RV, f"rv_{idx:03d}.txt")
        if not os.path.exists(src):
            bad.append(f"{fn}: rv_{idx:03d}.txt 없음")
            continue
        jps = [m.group(1) for m in
               re.finditer(r"^#JP (.*)$", open(src, encoding="utf-8").read(), re.M)]
        for raw in open(os.path.join(RV, fn), encoding="utf-8-sig").read().split("\n"):
            m = RE_FIX.match(raw.rstrip("\r"))
            if not m:
                continue
            n, txt = int(m.group(1)), m.group(2).rstrip("\r\n")
            if not 1 <= n <= len(jps):
                bad.append(f"{fn}: 번호 {n} 범위 밖 (1..{len(jps)})")
                continue
            if txt.strip():
                # 검수 배치는 '란화' 확정 이전 상태로 잘렸다. 교정문에 옛 표기가
                # 섞여 있으면 뒤에 놓이는 이 섹션이 9번(란파)을 덮어 버린다.
                for a, b in (("란화", "란파"),):
                    txt = txt.replace(a, b)
                fixes[jps[n - 1]] = txt

    cur = dict((jp, ko) for _, jp, ko in units)
    real = {jp: ko for jp, ko in fixes.items() if cur.get(jp) != ko}
    print(f"검수 파일 {len(files)}개에서 수정 {len(fixes)}줄 (실제 변경 {len(real)}줄)")
    for m in bad[:10]:
        print("  ERROR", m)
    if not real:
        return 0

    path = os.path.join(C.ROOT, "translation", "overrides.txt")
    MARK = "# 8) 전체 검수 반영 (koreview.py)"
    txt = open(path, encoding="utf-8").read()
    cut = txt.find(MARK)
    head = txt[:cut] if cut >= 0 else txt.rstrip("\n") + "\n\n"
    block = (MARK + "\n"
             "#    어체 일관성·직역투 교정. 가장 마지막에 적용되므로 앞선 모든 항목을 이긴다.\n"
             "# ============================================================\n")
    for jp, ko in real.items():
        block += f"//{jp}\n{ko}\n"
    open(path, "w", encoding="utf-8", newline="\n").write(head + block)
    print(f"  overrides.txt 8번 섹션에 {len(real)}줄 기록")
    print("  이어서:  py tools/kobatch.py merge  ->  py tools/build.py")
    return len(real)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "split":
        split(int(sys.argv[2]) if len(sys.argv) > 2 else 120)
    elif cmd == "apply":
        apply()
    else:
        rv = len([f for f in os.listdir(RV) if f.startswith("rv_")])
        fx = len([f for f in os.listdir(RV) if f.startswith("fix_")])
        print(f"검수 배치 {fx}/{rv} 완료")
