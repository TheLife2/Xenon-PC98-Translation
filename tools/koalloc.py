"""번역문에 실제로 쓰인 글자에 JIS 区点 슬롯을 할당한다.

  * 할당표는 append-only 다. 한 번 배정된 글자의 코드는 절대 바뀌지 않는다.
    (코드가 바뀌면 이미 만든 폰트와 스크립트가 서로 어긋난다)
  * 슬롯 순서 : 区14,15,84,85,88,93,94  (아무것도 희생 안 함, 658칸)
              -> 区48-83 제2수준한자    (한국어판에선 불필요, 3,384칸)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kocfg as C


def scan_chars(pairs):
    """번역문에서 자체 슬롯이 필요한 글자를 등장 순서대로."""
    out = []
    seen = set()
    for _, ko in pairs:
        for ch in ko:
            if ch in seen:
                continue
            seen.add(ch)
            if C.needs_slot(ch):
                out.append(ch)
    return out


def allocate(verbose=True):
    pairs = C.load_pairs()
    table = C.load_table()
    used = {b for b in table.values()}
    gen = C.slots()
    # 이미 쓴 슬롯은 건너뛴다
    pool = []
    for ku, ten in gen:
        b = C.ku_ten_to_sjis(ku, ten)
        if b not in used:
            pool.append((ku, ten, b))
        if len(pool) > 5000:
            break

    need = [ch for ch in scan_chars(pairs) if ch not in table]
    if len(need) > len(pool):
        raise SystemExit(f"슬롯 부족: {len(need)}자 필요, {len(pool)}칸 남음")

    for ch, (ku, ten, b) in zip(need, pool):
        table[ch] = b
    C.save_table(table)

    total = len(C.SLOT_KU) * 94
    if verbose:
        print(f"번역 단위 {len(pairs)}개 중 번역 완료 {sum(1 for _, k in pairs if k.strip())}개")
        print(f"신규 할당 {len(need)}자 / 누적 {len(table)}자 / 총 슬롯 {total}칸 "
              f"({100*len(table)/total:.1f}% 사용)")
        if need:
            head = "".join(need[:24])
            print(f"  신규: {head}{'…' if len(need) > 24 else ''}")
        by_ku = {}
        for ch, b in table.items():
            lead = b[0]
            by_ku.setdefault(lead, 0)
            by_ku[lead] += 1
        print("  선두바이트별:", ", ".join(f"0x{k:02X}:{v}" for k, v in sorted(by_ku.items())))
    return table


if __name__ == "__main__":
    allocate()
