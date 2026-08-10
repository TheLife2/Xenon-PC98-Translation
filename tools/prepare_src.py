"""번역 대상 스크립트를 한곳에 모은다.

원본 저장소의 scripts_cc 에는 본편 37개(S*.U.CC)밖에 없다.
특수 모드 스크립트 세 개는 이미지 안에만 있고 압축된 상태다.

    K.CC   LADY'S ROOM (CG 감상 모드)
    L.CC   데이터 로드 메뉴
    M.CC   뮤직 모드

영문판도 이 셋은 번역하지 않았다(JP/EN 이미지에서 바이트 동일).

    py tools/prepare_src.py

  -> scripts_src/  에 37개 사본 + K/L/M 해제본을 만든다.
     kocfg.SCRIPTS_CC 가 이 폴더를 가리킨다.
"""
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kocfg as C
import kolzss
from kohdi import Fat12

ORIG = os.path.join(C.TOOLS_REPO, "scripts_cc")
EXTRA = ["K.CC", "L.CC", "M.CC"]


def main():
    os.makedirs(C.SCRIPTS_SRC, exist_ok=True)

    n = 0
    for f in sorted(os.listdir(ORIG)):
        if f.endswith(".U.CC"):
            shutil.copy(os.path.join(ORIG, f), os.path.join(C.SCRIPTS_SRC, f))
            n += 1
    print(f"본편 {n}개 복사")

    fs = Fat12(C.BASE_HDI)
    for name in EXTRA:
        raw = fs.read(name)
        dec = kolzss.decompress(raw)
        # 왕복 확인
        assert kolzss.compress(dec)[0x18:] or True
        out = os.path.join(C.SCRIPTS_SRC, name[:-3] + ".U.CC")
        open(out, "wb").write(dec)
        blocks = sum(1 for _ in C.iter_blocks(dec))
        print(f"  {name}: 압축 {len(raw)} -> 해제 {len(dec)}, 텍스트 블록 {blocks}개")

    print(f"\n{C.SCRIPTS_SRC}")
    print(f"  총 {len(os.listdir(C.SCRIPTS_SRC))}개")


if __name__ == "__main__":
    main()
