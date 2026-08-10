"""확정된 수정을 원본 작업 파일(새 폴더 / todo)에 직접 적용한다.

overrides.txt 는 나중에 붙은 항목이 이기므로, 원본 파일을 고치지 않으면
--collect 가 옛 값으로 되돌려 놓는다. 원본이 진실이어야 한다.

    py tools/apply_fix.py            무엇이 바뀔지만 보여 준다
    py tools/apply_fix.py --write    적용
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kocfg as C
from kobatch import read_units

SINGLE = os.path.join(C.ROOT, "translation", "새 폴더")
TODO = os.path.join(C.ROOT, "translation", "todo")

# 2026-08-09 : 의성어·관용구 점검에서 확정한 수정
FIX = {
    # 관용구 : 「下の下」 = 최하위. '최하의 최하' 는 직역투
    "［ファル］：フン、コウジなんか、下の下‥‥。":
        "［파르］：흥, 코우지 따위, 최하급이지‥‥.",
    # 오역 : しごく = 훑다/문지르다(피동). '단단해지고 있어' 는 상태변화라 주체가 사라진다
    "［ファル］：（乳首もしごかれてる‥‥。）":
        "［파르］：（젖꼭지도 주물러지고 있어‥‥.）",
    # 음차 '쿠츄쿠츄' -> 표준표 くちゅ 계열
    "［ファル］：（アソコが、あんなにクチュクチュ言ってる‥‥。）":
        "［파르］：（그곳이, 저렇게 질척질척 소리를 내고 있어‥‥.）",
    # 음차 '둑둑' -> 표준표 どく 계열
    "［トレイシー］：（ドクドクって、お口の中にたっぷり射精してくださるのよ‥‥。）":
        "［트레이시］：（울컥울컥 하고, 입안에 듬뿍 사정해 주시는 거야‥‥.）",
    # 음차 '즈르르' -> 부사 「ずるりと」 는 '주르륵'
    "ずるりと先っぽまで引き抜き、そのまま根本まで突き入れる。オレはこの単純な反復運動に、"
    "いい知れない快感を覚えていた。":
        "주르륵 귀두까지 빼고, 그대로 뿌리까지 밀어 넣는다. 나는 이 단순한 반복 운동에, "
        "형언할 수 없는 쾌감을 느끼고 있었다.",
}

# 2026-08-09 재확정 : ランファ 는 '란파'.
# 게임 자체의 뮤직 모드가 'Ranfa' 로 로마자 표기한다.
# '란화'(모음 끝) -> '란파'(모음 끝) 라 조사는 그대로다.
GLOBAL = [("란화", "란파")]


def run(write):
    hit = collections_hit = 0
    files = 0
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
                    g = cur
                    for a, b in GLOBAL:
                        g = g.replace(a, b)
                    if jp not in FIX and g != cur:
                        out.append(g)
                        touched = True
                        hit += 1
                        i += 2 if has else 1
                        continue
                    if jp in FIX and cur != FIX[jp]:
                        print(f"  {fn}")
                        print(f"    - {cur[:60]}")
                        print(f"    + {FIX[jp][:60]}")
                        out.append(FIX[jp])
                        touched = True
                        hit += 1
                    elif has:
                        out.append(cur)
                    i += 2 if has else 1
                    continue
                i += 1
            if touched:
                files += 1
                if write:
                    open(p, "w", encoding="utf-8", newline="\n").write("\n".join(out))
    print(f"\n{'적용' if write else '적용 예정'}: {hit}줄 / 파일 {files}개")
    if not write:
        print("실제로 반영하려면 --write 를 붙이세요.")


if __name__ == "__main__":
    run("--write" in sys.argv)
