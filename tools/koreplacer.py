"""원본 .U.CC 에 한국어를 삽입한다.

원본 도구(xenreplacer.py)는 마커 패턴 11개를 바꿔가며 파일을 11번 훑는 방식이었다.
블록 포맷이 확정된 지금은 그럴 필요가 없다. 한 번만 훑으면서

    FD <len> <본문> 00      ->      FD <새len> <새본문> 00

로 바꾼다. 원본 도구와 달라진 점 두 가지:

  1. 길이 바이트를 갱신한다. 원본은 갱신하지 않아 영문판 15,423 블록 중 13,405 개가
     길이 불일치 상태다(게임이 NUL 종단으로 읽어서 문제가 안 났을 뿐이다).
  2. \\n 과 <$XX> 를 실제 바이트로 되돌린다. 원본에 이 역변환이 없어서 영문판에
     '¥n' 이 그대로 찍히는 버그가 있었다.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kocfg as C
from koscript import split_affix, key_of, text_to_bytes


def build_map():
    """{키: 한국어} - 번역이 채워진 것만."""
    return {jp: ko for jp, ko in C.load_pairs() if ko.strip()}


def process(data: bytes, tmap: dict, table: dict, stats: dict, where: str) -> bytes:
    out = bytearray()
    pos = 0
    for b_off, len_off, s, e in C.iter_blocks(data):
        blk = data[s:e]
        key = key_of(blk)
        stats["blocks"] += 1
        ko = tmap.get(key)
        if not ko:
            continue
        head, _core, tail = split_affix(blk)
        try:
            body = head + text_to_bytes(ko, table) + tail
        except ValueError as err:
            stats["errors"].append(f"{where}: {err} / {ko[:40]!r}")
            continue
        if len(body) > C.MAX_BLOCK_BYTES:
            stats["errors"].append(
                f"{where}: 블록 {len(body)}바이트 > {C.MAX_BLOCK_BYTES} / {ko[:40]!r}")
            continue
        out += data[pos:b_off]
        out += bytes([0xFD, len(body)])
        out += body
        out += b"\x00"
        pos = e + 1
        stats["replaced"] += 1
    out += data[pos:]
    return bytes(out)


def main(argv=None):
    tmap = build_map()
    table = C.load_table()
    stats = {"blocks": 0, "replaced": 0, "errors": []}
    names = argv or C.SCRIPT_NAMES
    for name in names:
        src = os.path.join(C.SCRIPTS_CC, name + ".U.CC")
        dst = os.path.join(C.MERGE_DIR, name + ".U.CC")
        data = open(src, "rb").read()
        new = process(data, tmap, table, stats, name)
        open(dst, "wb").write(new)
    cov = 100 * stats["replaced"] / stats["blocks"] if stats["blocks"] else 0
    print(f"삽입: {stats['replaced']}/{stats['blocks']} 블록 ({cov:.1f}%), "
          f"파일 {len(names)}개 -> {C.MERGE_DIR}")
    for e in stats["errors"][:20]:
        print("  ERROR", e)
    if len(stats["errors"]) > 20:
        print(f"  ... 외 {len(stats['errors'])-20}건")
    return len(stats["errors"])


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
