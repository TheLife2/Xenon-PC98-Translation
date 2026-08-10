"""전수 검수용 청크 내보내기.

`translation/_script-korean.txt` (// 원문 + 다음 줄 번역) 를 읽어
검수 에이전트가 먹기 좋은 청크 파일로 나눈다.

    py tools/review_export.py [청크당 쌍 수=220]

산출물 : translation/review_full/chunk_NN.txt
         각 줄  L<원본 줄번호> | <일본어>
                >>            | <한국어>
라벨 줄(한글도 가나·한자도 없는 것)은 뺀다.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kocfg as C

SRC = os.path.join(C.ROOT, "translation", "_script-korean.txt")
OUT = os.path.join(C.ROOT, "translation", "review_full")

RE_JA = re.compile(r"[ぁ-んァ-ヶ一-鿿]")
RE_KO = re.compile(r"[가-힣]")


def main():
    per = int(sys.argv[1]) if len(sys.argv) > 1 else 220
    lines = open(SRC, encoding="utf-8").read().splitlines()

    pairs = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("//"):
            jp = ln[2:]
            ko = lines[i + 1] if i + 1 < len(lines) else ""
            # 라벨(ra&to01 등)과 완전 동일 복사는 검수 대상이 아니다
            if RE_JA.search(jp) or RE_KO.search(ko):
                pairs.append((i + 2, jp, ko))   # 사람이 보는 줄번호는 1기준, ko 줄
            i += 2
        else:
            i += 1

    os.makedirs(OUT, exist_ok=True)
    for f in os.listdir(OUT):
        if f.startswith("chunk_"):
            os.remove(os.path.join(OUT, f))

    n = 0
    for s in range(0, len(pairs), per):
        chunk = pairs[s:s + per]
        p = os.path.join(OUT, "chunk_%02d.txt" % n)
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write("# _script-korean.txt 의 줄번호 기준. L<번호> 줄이 한국어 번역의 위치다.\n")
            for lineno, jp, ko in chunk:
                f.write("L%d\t%s\n>>\t%s\n" % (lineno, jp, ko))
        n += 1

    print("검수 대상 %d쌍 -> 청크 %d개 (%s)" % (len(pairs), n, OUT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
