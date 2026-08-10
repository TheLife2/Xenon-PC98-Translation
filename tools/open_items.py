"""미결 항목을 앞뒤 문맥과 함께 뽑아 판단 자료로 만든다.

    py tools/open_items.py            요약을 화면에
    py tools/open_items.py --write    translation/OPEN_ITEMS.md 작성

게임 진행 순서대로 자르므로 앞뒤 줄이 실제 대화 흐름이다.
"""
import os
import re
import sys
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kocfg as C
from koscript import key_of

TAG = re.compile(r"^[(?]?［([^］]{1,14})］：?")


def build():
    km = dict(C.load_pairs())
    seq = []
    seen = set()
    for name in C.SCRIPT_NAMES:
        data = open(os.path.join(C.SCRIPTS_CC, name + ".U.CC"), "rb").read()
        for _, _, s, e in C.iter_blocks(data):
            k = key_of(data[s:e])
            if k in km and k not in seen:
                seen.add(k)
                seq.append((name, k, km[k]))
    pos = {k: i for i, (_, k, _) in enumerate(seq)}
    return seq, pos, km


SEQ, POS, KM = build()


def ctx(key, before=2, after=2):
    i = POS.get(key)
    if i is None:
        return []
    name = SEQ[i][0]
    out = []
    for j in range(max(0, i - before), min(len(SEQ), i + after + 1)):
        if SEQ[j][0] != name:
            continue
        out.append((j == i, SEQ[j][1], SEQ[j][2]))
    return out


def block(f, key, note=""):
    i = POS.get(key)
    loc = f"{SEQ[i][0]} #{i}" if i is not None else "?"
    f.write(f"<details>\n<summary><code>{loc}</code>  {KM.get(key,'')[:52]}</summary>\n\n")
    if note:
        f.write(f"> {note}\n\n")
    f.write("```\n")
    for is_t, jp, ko in ctx(key):
        m = ">>" if is_t else "  "
        f.write(f"{m} JP {jp[:76]}\n")
        f.write(f"   KO {ko[:76]}\n")
    f.write("```\n\n</details>\n\n")


def main(write):
    pairs = [(jp, ko) for jp, ko in C.load_pairs() if ko.strip()]

    # ① 君 -> 당신
    kimi = [(jp, ko) for jp, ko in pairs if "당신" in ko and "君" in jp]
    # ② 정형 인사 합쇼체
    GREET = ["알겠습니다", "죄송합니다", "부탁드립니다", "실례하겠습니다", "감사합니다"]
    greet = [(jp, ko) for jp, ko in pairs if any(g in ko for g in GREET)]
    # ③ 、という 쉼표
    pat = re.compile(r"[가-힣][,，]\s*(라는|이라는|라고|인가|이라|하는)")
    comma = [(jp, ko) for jp, ko in pairs if pat.search(ko)]
    # ④ 숫자
    fw = [(jp, ko) for jp, ko in pairs if re.search(r"[０-９]", ko)]
    asc = [(jp, ko) for jp, ko in pairs if re.search(r"(?<![A-Za-z])\d", ko)]
    hg = [(jp, ko) for jp, ko in pairs
          if re.search(r"(한|두|세|네|다섯|여섯|일곱|여덟|아홉|열)\s?(개|명|층|번|사람|시간|살|송이|장|대)", ko)]

    print(f"① 君->당신 {len(kimi)} / ② 정형인사 합쇼체 {len(greet)} / "
          f"③ 쉼표 {len(comma)} / ④ 숫자 전각{len(fw)} 반각{len(asc)} 한글{len(hg)}")
    if not write:
        print("--write 로 translation/OPEN_ITEMS.md 를 만듭니다.")
        return

    p = os.path.join(C.ROOT, "translation", "OPEN_ITEMS.md")
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write("# 미결 항목 — 판단 자료\n\n")
        f.write("각 항목의 해당 줄을 **앞뒤 문맥과 함께** 뽑았다. "
                "`>>` 가 해당 줄이고, 위아래는 게임에서 실제로 이어지는 대사다.\n\n")
        f.write("배경과 선택지는 [`../TRANSLATION_NOTES.md`](../TRANSLATION_NOTES.md) §8 참조.\n\n")
        f.write("---\n\n")

        f.write(f"## ① 2인칭 — 원문이 `君` 인 {len(kimi)}줄\n\n")
        f.write("`あなた` 102줄은 성인 화자 간이라 「당신」이 맞다. "
                "여기 모은 것은 원문이 `君`(친근하거나 손윗사람이 아랫사람에게)인 줄이다.\n\n")
        f.write("**선택지** : 「당신」 유지 / 「그대」 / 이름 호칭 / 「너」\n\n")
        for jp, ko in kimi:
            block(f, jp, f"화자 ［{(TAG.match(jp).group(1) if TAG.match(jp) else '지문')}］")

        f.write(f"---\n\n## ② 정형 인사 — 합쇼체로 남은 {len(greet)}줄\n\n")
        f.write("해요체 화자가 쓴 합쇼체 인사말이다. 한국어에서는 이런 정형 인사를 "
                "해요체 화자도 합쇼체로 쓰는 것이 자연스러워 예외로 둘 근거가 있다.\n\n")
        f.write("**선택지** : 전부 해요체 통일 / 정형 인사만 합쇼체 허용\n\n")
        for jp, ko in greet:
            g = next((x for x in GREET if x in ko), "")
            block(f, jp, f"`{g}`")

        f.write(f"---\n\n## ③ 「、という」의 쉼표 — {len(comma)}줄\n\n")
        f.write("일본어 쉼표 위치를 그대로 옮긴 것. 70줄이 일관되게 이 방식이라 오류는 아니다.\n\n")
        f.write("**선택지** : 현행 유지 / 쉼표 일괄 제거\n\n")
        for jp, ko in comma[:24]:
            block(f, jp)
        if len(comma) > 24:
            f.write(f"> 외 {len(comma)-24}줄. 같은 패턴이라 생략했다.\n\n")

        f.write("---\n\n## ④ 숫자 표기\n\n")
        f.write(f"| 방식 | 줄 |\n|---|---|\n")
        f.write(f"| 전각 `０-９` | {len(fw)} |\n| 반각 `0-9` | {len(asc)} |\n"
                f"| 한글 수사 | {len(hg)} |\n\n")
        f.write("원문은 전각으로 통일돼 있다. 전각 2바이트 / 반각 1바이트라 길이에도 영향이 있고, "
                "메뉴·화면 표시는 정렬 때문에 전각이 맞다.\n\n")
        f.write("**선택지** : 본문 반각 통일 + 메뉴·화면만 전각 / 원문 그대로 전각 통일\n\n")
        for label, rows in (("전각을 쓴 줄", fw[:10]), ("반각을 쓴 줄", asc[:10]),
                            ("한글 수사를 쓴 줄", hg[:10])):
            f.write(f"### {label}\n\n")
            for jp, ko in rows:
                block(f, jp)
    print("작성:", p)


if __name__ == "__main__":
    main("--write" in sys.argv)
