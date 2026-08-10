"""그래픽 작업용 원본 추출.

    py tools/gfx_extract.py

  gfx/AGS.EXE      게임 실행 파일 (DA1 디코더가 들어 있다)
  gfx/raw/*.GDT    그래픽 210개
  gfx/INDEX.tsv    파일 목록 + 헤더 필드
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kocfg as C
from kohdi import Fat12

GFX = os.path.join(C.ROOT, "gfx")
RAW = os.path.join(GFX, "raw")


def main():
    os.makedirs(RAW, exist_ok=True)
    fs = Fat12(C.BASE_HDI)

    open(os.path.join(GFX, "AGS.EXE"), "wb").write(fs.read("AGS.EXE"))

    rows = []
    for n, s, c, o in fs.entries():
        if not n.upper().endswith((".GDT", ".ADT")):
            continue
        b = fs.read(n)
        open(os.path.join(RAW, n), "wb").write(b)
        magic = b[:4]
        if magic == b"DA1\x00":
            size = struct.unpack_from("<I", b, 4)[0]
            f = struct.unpack_from("<BBHH", b, 8)
            rows.append((n, s, "DA1", size, f[0], f[1], f[2], f[3]))
        else:
            rows.append((n, s, magic.decode("latin-1", "replace").rstrip("\x00"),
                         0, 0, 0, 0, 0))

    with open(os.path.join(GFX, "INDEX.tsv"), "w", encoding="utf-8", newline="\n") as f:
        f.write("파일\t크기\t매직\t헤더크기\tf08\tf09\tf10_11\tf12_13\n")
        for r in rows:
            f.write("\t".join(str(x) for x in r) + "\n")

    da1 = [r for r in rows if r[2] == "DA1"]
    print(f"AGS.EXE + 그래픽 {len(rows)}개 -> {RAW}")
    print(f"  DA1 형식 {len(da1)}개 / 그 밖 {len(rows)-len(da1)}개")
    print(f"  헤더 크기 필드가 실제 크기와 일치: "
          f"{sum(1 for r in da1 if r[1] == r[3])}/{len(da1)}")
    print(f"  목록: {os.path.join(GFX, 'INDEX.tsv')}")


if __name__ == "__main__":
    main()
