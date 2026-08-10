"""번역 작업을 배치로 쪼개고, 번역된 배치를 다시 합친다.

    py tools/kobatch.py split [단위수]     미번역 줄을 batches/src_NNN.txt 로 분할
    py tools/kobatch.py merge              batches/ko_NNN.txt 를 _script-korean.txt 에 반영
    py tools/kobatch.py status             진행 상황

배치 파일 형식은 작업 파일과 같다. 번역자(사람이든 에이전트든)는
'//' 줄 바로 다음의 빈 줄만 채운다. 그 밖의 줄은 손대지 않는다.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kocfg as C
from koverify import load_terms

BATCH_DIR = os.path.join(C.ROOT, "translation", "batches")
os.makedirs(BATCH_DIR, exist_ok=True)


def read_units(path):
    """배치/작업 파일 -> [(주석줄 리스트, 일본어, 한국어)]"""
    lines = open(path, encoding="utf-8").read().split("\n")
    out = []
    notes = []
    i = 0
    while i < len(lines):
        l = lines[i].rstrip("\r")
        if l.startswith("#"):
            notes.append(l)
            i += 1
        elif l.startswith("//"):
            ko = ""
            if i + 1 < len(lines) and not lines[i + 1].rstrip("\r").startswith(("//", "#")):
                ko = lines[i + 1].rstrip("\r")
                i += 2
            else:
                i += 1
            out.append((notes, l[2:], ko))
            notes = []
        else:
            i += 1
    return out


def split(size=160):
    terms = load_terms()
    en = {}
    p = os.path.join(C.TL_REPO, "script-japanese-with-translation.txt")
    lines = open(p, encoding="utf-8").read().split("\n")
    i = 0
    while i < len(lines):
        if lines[i].rstrip("\r").startswith("//"):
            en[lines[i].rstrip("\r")[2:]] = lines[i + 1].rstrip("\r") if i + 1 < len(lines) else ""
            i += 2
        else:
            i += 1

    units = read_units(C.TRANSLATION)
    todo = [(jp, ko) for _, jp, ko in units if not ko.strip()]
    for f in os.listdir(BATCH_DIR):
        os.remove(os.path.join(BATCH_DIR, f))

    n = 0
    for b in range(0, len(todo), size):
        chunk = todo[b:b + size]
        idx = b // size
        with open(os.path.join(BATCH_DIR, f"src_{idx:03d}.txt"), "w",
                  encoding="utf-8", newline="\n") as f:
            f.write(f"# 배치 {idx:03d} : {len(chunk)}줄\n")
            f.write("# 규칙은 translation/TRANSLATE_GUIDE.md 를 따른다.\n")
            f.write(f"# 출력은 ko_{idx:03d}.txt 에 'nnn|한국어' 형식으로 "
                    f"정확히 {len(chunk)}줄.\n\n")
            for k, (jp, _) in enumerate(chunk, 1):
                f.write(f"#NO {k:03d}\n")
                e = en.get(jp, "")
                if e:
                    f.write("#EN " + e + "\n")
                need = sorted({f"{j}→{ko2}" for j, ko2, g in terms if g and j in jp})
                if need:
                    f.write("#!! 표기 " + "  ".join(need) + "\n")
                f.write("//" + jp + "\n\n")
        n += 1
    print(f"미번역 {len(todo)}줄 -> 배치 {n}개 (배치당 {size}줄)")
    print("  ", BATCH_DIR)
    return n


# 구분자 뒤는 반각 공백/탭만 흘려보낸다.
# 파이썬의 \s 는 전각 공백(U+3000)도 공백으로 보기 때문에 \s* 를 쓰면
# 원문의 들여쓰기(중앙 정렬용 U+3000)가 소리 없이 사라진다.
RE_KO = re.compile(r"^\s*(\d{1,3})[ \t]*[|｜][ \t]*(.*)$")


def merge():
    units = read_units(C.TRANSLATION)
    got = {}
    bad = []
    skipped = []
    files = sorted(f for f in os.listdir(BATCH_DIR) if f.startswith("ko_"))
    for fn in files:
        src = os.path.join(BATCH_DIR, fn.replace("ko_", "src_"))
        if not os.path.exists(src):
            bad.append(f"{fn}: 대응하는 src 파일이 없음")
            continue
        jps = [u[1] for u in read_units(src)]
        seen = {}
        for raw in open(os.path.join(BATCH_DIR, fn), encoding="utf-8-sig").read().split("\n"):
            m = RE_KO.match(raw.rstrip("\r"))
            if not m:
                continue
            idx = int(m.group(1))
            # 말미 전각 공백(메뉴 정렬용 패딩)을 보존하기 위해 개행만 떼어 낸다
            txt = m.group(2).rstrip("\r\n")
            if not 1 <= idx <= len(jps):
                bad.append(f"{fn}: 번호 {idx} 범위 밖 (1..{len(jps)})")
                continue
            if idx in seen:
                bad.append(f"{fn}: 번호 {idx} 중복")
                continue
            seen[idx] = txt
        missing = [i for i in range(1, len(jps) + 1) if i not in seen]
        if missing:
            bad.append(f"{fn}: {len(missing)}줄 누락 (예: {missing[:6]})")
        for idx, txt in seen.items():
            if not txt.strip() or txt.strip().upper() == "#SKIP":
                skipped.append(f"{fn} #{idx:03d}: {jps[idx-1][:50]}")
                continue
            got[jps[idx - 1]] = txt
    # 사용자 확정 수정은 배치 결과보다 우선한다
    ov_path = os.path.join(C.ROOT, "translation", "overrides.txt")
    ov = {}
    if os.path.exists(ov_path):
        ov = {jp: ko for _, jp, ko in read_units(ov_path) if ko.strip()}

    filled = 0
    over = 0
    unmatched = []
    out = []
    for notes, jp, ko in units:
        if not ko.strip() and jp in got:
            ko = got[jp]
            filled += 1
        if jp in ov and ko != ov[jp]:
            ko = ov[jp]
            over += 1
        out.append((notes, jp, ko))
    seen_jp = {jp for _, jp, _ in units}
    unmatched = [jp for jp in ov if jp not in seen_jp]
    with open(C.TRANSLATION, "w", encoding="utf-8", newline="\n") as f:
        f.write("# XENON ~夢幻の肢体~  한국어 번역 작업 파일\n")
        f.write("#   '//' 줄 = 일본어 원문(수정 금지).  바로 다음 줄에 한국어를 적는다.\n")
        f.write("#   고유명사는 translation/GLOSSARY.md 규약을 따를 것\n\n")
        for notes, jp, ko in out:
            for nline in notes:
                if nline.startswith(("#EN", "#!!")):
                    f.write(nline + "\n")
            f.write("//" + jp + "\n" + ko + "\n")
    print(f"배치 {len(files)}개에서 {filled}줄 반영")
    if ov:
        print(f"  overrides.txt 적용 {over}줄 (등록 {len(ov)}줄)")
    for jp in unmatched:
        print(f"  ERROR overrides.txt 의 원문이 작업 파일에 없음: {jp[:60]}")
    if skipped:
        print(f"  건너뜀 {len(skipped)}줄:")
        for m in skipped[:10]:
            print("   ", m)
    for m in bad:
        print("  ERROR", m)
    status()


def status():
    units = read_units(C.TRANSLATION)
    done = sum(1 for _, _, ko in units if ko.strip())
    src = len([f for f in os.listdir(BATCH_DIR) if f.startswith("src_")])
    ko = len([f for f in os.listdir(BATCH_DIR) if f.startswith("ko_")])
    print(f"번역 {done}/{len(units)} ({100*done/len(units):.1f}%)  배치 {ko}/{src} 완료")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "split":
        split(int(sys.argv[2]) if len(sys.argv) > 2 else 160)
    elif cmd == "merge":
        merge()
    else:
        status()
