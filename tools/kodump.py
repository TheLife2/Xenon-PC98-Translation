"""빌드 결과 확인용 덤프.

할당표를 역방향으로 써서, 삽입된 한국어를 사람이 읽을 수 있게 되돌린다.
(할당된 코드는 cp932 상 미정의 영역이라 그냥 디코딩하면 안 보인다)

    py tools/kodump.py S00              한 파일의 번역된 블록 전부
    py tools/kodump.py S00 --all        번역 안 된 블록까지
    py tools/kodump.py --find 셋        문자열로 검색
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kocfg as C
from koscript import block_to_text, split_affix


def rev_decode(blk: bytes, rev: dict) -> str:
    out = []
    i = 0
    n = len(blk)
    while i < n:
        b = blk[i]
        if i + 1 < n and blk[i:i + 2] in rev:
            out.append(rev[blk[i:i + 2]])
            i += 2
            continue
        if b == 0x04 and i + 1 < n:
            out.append("<$%02X><$%02X>" % (b, blk[i + 1])); i += 2
        elif b == 0x0A:
            out.append(chr(92) + "n"); i += 1
        elif b < 0x20:
            out.append("<$%02X>" % b); i += 1
        elif (0x81 <= b <= 0x9F) or (0xE0 <= b <= 0xFC):
            out.append(blk[i:i + 2].decode("cp932", "replace")); i += 2
        else:
            out.append(blk[i:i + 1].decode("cp932", "replace")); i += 1
    return "".join(out)


def main():
    rev = {v: k for k, v in C.load_table().items()}
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    show_all = "--all" in sys.argv
    find = None
    if "--find" in sys.argv:
        find = sys.argv[sys.argv.index("--find") + 1]
        args = [a for a in args if a != find]

    names = args or C.SCRIPT_NAMES
    hits = 0
    for name in names:
        p = os.path.join(C.MERGE_DIR, name + ".U.CC")
        if not os.path.exists(p):
            continue
        data = open(p, "rb").read()
        orig = open(os.path.join(C.SCRIPTS_CC, name + ".U.CC"), "rb").read()
        origmap = {}
        for _, _, s, e in C.iter_blocks(orig):
            origmap.setdefault(len(origmap), block_to_text(orig[s:e]))
        idx = 0
        for b_off, l_off, s, e in C.iter_blocks(data):
            blk = data[s:e]
            txt = rev_decode(blk, rev)
            translated = any(blk[i:i + 2] in rev for i in range(len(blk) - 1))
            idx += 1
            if find and find not in txt:
                continue
            if not find and not show_all and not translated:
                continue
            hits += 1
            print(f"{name} #{idx} @0x{b_off:04x} len={data[l_off]}(실제 {len(blk)})"
                  f"{' [KO]' if translated else ''}")
            print(f"   원문 : {origmap.get(idx-1, '')}")
            print(f"   현재 : {txt}")
            if find:
                print(f"   hex  : {blk.hex(' ')}")
    print(f"\n{hits}개 블록")


if __name__ == "__main__":
    main()
