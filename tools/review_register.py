"""화자별 어체(경어 등급) 일관성 점검.

한국어는 한 화자가 같은 상대에게 말할 때 어체를 섞으면 바로 어색하게 들린다.
일본어 원문은 보통체/정중체가 자연스럽게 섞이므로, 그대로 옮기면 이 문제가 생긴다.

등급
  합쇼체  -습니다 / -ㅂ니다 / -십시오      (가장 격식)
  해요체  -어요 / -아요 / -예요 / -세요     (부드러운 존대)
  해라체  -다 / -군 / -구나                 (서술·독백)
  반말    -야 / -어 / -지 / -니 / -자
"""
import os
import re
import sys
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kocfg as C

HAPSYO = re.compile(r"(습니다|습니까|ㅂ니다|입니다|십시오|ㅂ시다|겠습니|았습니|었습니)")
HAEYO = re.compile(r"(어요|아요|예요|이에요|에요|해요|세요|셔요|지요|죠|군요|네요|더군요|는데요|거든요|까요)")
HAERA = re.compile(r"(었다|았다|이다|한다|는다|었지|구나|군[.!?‥]|더라|리라)")
BANMAL = re.compile(r"(야[.!?‥]|어[.!?‥]|아[.!?‥]|지[.!?‥]|니[?‥]|자[.!]|잖아|거든[.!?‥]|는데[.?‥]|래[?.‥])")

TAG = re.compile(r"^[(?]?［([^］]{1,14})］：?")


def level(ko):
    body = re.sub(r"^[(?]?［[^］]{1,14}］：?", "", ko).rstrip("　 ")
    if HAPSYO.search(body):
        return "합쇼"
    if HAEYO.search(body):
        return "해요"
    if BANMAL.search(body):
        return "반말"
    if HAERA.search(body):
        return "해라"
    return "기타"


def main():
    pairs = [(jp, ko) for jp, ko in C.load_pairs() if ko.strip()]
    per = collections.defaultdict(collections.Counter)
    samples = collections.defaultdict(lambda: collections.defaultdict(list))
    for jp, ko in pairs:
        m = TAG.match(jp)
        if not m:
            continue
        who = m.group(1)
        lv = level(ko)
        per[who][lv] += 1
        if len(samples[who][lv]) < 3:
            samples[who][lv].append((jp, ko))

    print("화자별 어체 분포 (대사 30줄 이상)")
    print(f"{'화자':<14}{'줄':>6}  {'합쇼':>6}{'해요':>6}{'해라':>6}{'반말':>6}{'기타':>6}   혼용도")
    rows = []
    for who, c in per.items():
        tot = sum(c.values())
        if tot < 30:
            continue
        polite = c["합쇼"] + c["해요"]
        mix = 0.0
        if polite:
            mix = min(c["합쇼"], c["해요"]) / polite
        rows.append((who, tot, c, mix))
    for who, tot, c, mix in sorted(rows, key=lambda r: -r[3]):
        flag = "  <-- 합쇼/해요 혼용" if mix > 0.15 else ""
        print(f"  {who:<12}{tot:>6}  {c['합쇼']:>6}{c['해요']:>6}{c['해라']:>6}"
              f"{c['반말']:>6}{c['기타']:>6}   {mix*100:5.1f}%{flag}")

    print()
    print("=== 합쇼/해요 혼용이 심한 화자의 실제 예 ===")
    for who, tot, c, mix in sorted(rows, key=lambda r: -r[3])[:4]:
        if mix <= 0.15:
            continue
        print(f"\n■ ［{who}］  합쇼 {c['합쇼']} / 해요 {c['해요']}")
        for lv in ("합쇼", "해요"):
            for jp, ko in samples[who][lv][:2]:
                print(f"   [{lv}] {jp[:52]}")
                print(f"          {ko[:52]}")


if __name__ == "__main__":
    main()
