"""`AGS.EXE` 안의 일본어 UI 문구를 한국어로 바꾼다.

    py tools/exe_patch.py            검사만 (무엇이 바뀌는지, 길이가 맞는지)
    py tools/exe_patch.py --write    out/AGS.EXE 생성

왜 스크립트 파이프라인과 따로인가
--------------------------------
`.CC` 스크립트는 압축 스트림 안의 텍스트 블록이라 길이를 늘릴 수 있다.
EXE 문자열은 **NUL 로만 구분돼 맞붙어 있는 고정 배치**라 원본 바이트를 넘으면
다음 문자열을 침범한다. 그래서 별도 도구로 다루고, 초과하면 거부한다.

한글은 스크립트와 **같은 방식**으로 넣는다 — 미사용 JIS 구획에 배정한 코드
(`table/kotable.json`)를 쓰고, 게임은 우리가 만든 폰트 시트(`out/font.tmp`)에서
그 글리프를 읽는다. 그래서 폰트를 새로 만들 필요가 없다.

주의: 여기 쓰인 글자도 슬롯이 필요하므로 `koalloc.py` 가 이 파일을 함께 훑는다.
"""
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kocfg as C

SRC = os.path.join(C.ROOT, "gfx", "AGS.EXE")
OUT = os.path.join(C.OUT_DIR, "AGS.EXE")
LIST = os.path.join(C.ROOT, "translation", "exe_strings.txt")


def load():
    """[(일본어, 한국어)] — load_pairs 와 같은 형식"""
    return [(jp, ko) for jp, ko in C.load_pairs(LIST) if ko.strip()]


def check(verbose=True):
    data = bytearray(open(SRC, "rb").read())
    table = C.load_table()
    rows = []
    bad = []
    for jp, ko in load():
        raw = jp.encode("shift-jis")
        off = data.find(raw)
        if off < 0:
            bad.append("원문을 EXE 에서 못 찾음: %s" % jp)
            continue
        if data.find(raw, off + 1) >= 0:
            bad.append("원문이 EXE 에 여러 번 나온다 (모호): %s" % jp)
            continue
        if data[off + len(raw)] != 0:
            bad.append("원문 뒤가 NUL 이 아니다 (0x%02X): %s"
                       % (data[off + len(raw)], jp))
            continue
        try:
            enc = C.encode(ko, table)
        except Exception as e:
            bad.append("인코딩 실패 (%s): %s" % (e, ko))
            continue
        if len(enc) > len(raw):
            bad.append("%d바이트 초과 (%d > %d): %s -> %s"
                       % (len(enc) - len(raw), len(enc), len(raw), jp, ko))
            continue
        rows.append((off, raw, enc, jp, ko))

    if verbose:
        print("대상 %d건 / 문제 %d건\n" % (len(rows), len(bad)))
        print("%-9s %-9s  %s" % ("오프셋", "바이트", "번역"))
        for off, raw, enc, jp, ko in rows:
            print("0x%05X  %3d->%-3d  %s" % (off, len(raw), len(enc), ko))
        for b in bad:
            print("  [문제] " + b)
    return data, rows, bad


def main():
    write = "--write" in sys.argv
    data, rows, bad = check()
    if bad:
        print("\n문제가 있어 중단합니다.")
        return 1
    if not write:
        print("\n--write 를 붙이면 out/AGS.EXE 를 만듭니다.")
        return 0

    for off, raw, enc, jp, ko in rows:
        data[off:off + len(raw)] = enc + b"\x00" * (len(raw) - len(enc))
    os.makedirs(C.OUT_DIR, exist_ok=True)
    open(OUT, "wb").write(bytes(data))
    orig = open(SRC, "rb").read()
    diff = sum(1 for a, b in zip(orig, data) if a != b)
    print("\n%s\n  크기 %d (원본과 같아야 한다: %s), 바뀐 바이트 %d"
          % (OUT, len(data), "예" if len(data) == len(orig) else "아니오", diff))

    # 되읽어 검증
    chk = open(OUT, "rb").read()
    table = C.load_table()
    ok = 0
    for off, raw, enc, jp, ko in rows:
        if chk[off:off + len(enc)] == enc and chk[off + len(raw)] == 0:
            ok += 1
        else:
            print("  불일치: %s" % ko)
    print("  검증 %d/%d" % (ok, len(rows)))
    return 0 if ok == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
