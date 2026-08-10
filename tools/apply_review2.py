# -*- coding: utf-8 -*-
"""2026-08-10 전수 검수(워크플로우 81 에이전트, 확정 177건) 반영.

    py tools/apply_review2.py            미리보기
    py tools/apply_review2.py --write    overrides 15번 섹션 기록 + merge 실행

구성
  1) 자동 반영: 재검 통과 지적 중 수정안이 완결된 것 (scratchpad/apply_table.json)
  2) 수동 확정: 같은 줄 중복 지적 합성 + 지시문형 수정안 판단분 (아래 HAND)
  3) 전역 통일: 표기 흔들림 (콰드라·에이레이트·함선·기시감각·컴퓨터 룸·엔진 룸 등)

원칙
  * 최종값은 overrides.txt 15번 섹션(원문 키)으로 남긴다 - 배치 재병합에도 이긴다.
  * 반영 전 두 파일을 .bak 으로 백업한다.
  * merge 후 대상 줄들을 되읽어 기대값과 대조한다.
"""
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kocfg as C

TR = C.TRANSLATION
OV = os.path.join(C.ROOT, "translation", "overrides.txt")
TABLE = os.path.join(os.environ.get("CLAUDE_SCRATCH", ""), "apply_table.json")
if not os.path.isfile(TABLE):
    TABLE = r"C:\Users\nobep\AppData\Local\Temp\claude\C--thelife\0eb1e584-6b3f-44c3-b465-d61ad0febf31\scratchpad\apply_table.json"

# ---------------------------------------------------------------- 수동 확정
# 같은 줄 중복 지적은 두 수정을 합성했고, 지시문형 수정안은 아래 근거로 확정했다.
#   기시감각: 콜백 대사가 있어 작품 조어 쪽으로 통일 (보고서 5-1)
#   컴퓨터 룸/엔진 룸: 파일 전체 다수 표기(22:3 / 18:6) 쪽으로 통일
#   란파 어체: 원문이 반말이고 후반 장면도 반말 - 반말 통일 (보고서 지적)
#   네년: 료코(여성)를 부르는 4줄만 - 다른 네놈은 남성 대상이라 유지
HAND = {
    6159: "［파르］：그러니까, ３명째일 가능성이 있다는 거야.",
    6201: "［코우지］：（그리고 어쩌면, ３명째가 발견될지도 모른다‥‥.）",
    11497: "［란파］：저는, 그걸 깨닫게 하려고, 여러 번 넌지시 알려 드렸어요. 당신의 메모리에 액세스해서‥‥.",
    11614: "「잠들어 꿈이라도 꾸자. 인간이 다시, 번영할 것을 생각하면서‥‥.」",
    11800: "［료코］：괜―찮아, 그런 얼굴 하지 않아도. 이번에야말로, 성공해 보이겠어.",
    14109: "［코우지］：료코, 네년에게는 달리 할 일이 있다.",
    14137: "［코우지］：네년은 저 머신을 어떤 콘셉트에 기반해 설계한 것이냐?",
    14199: "［코우지］：네년이 저 머신을 이용할 때 사용한, 또 한 명의 인간을 말한다.",
    14288: "［코우지］：네년은 알 필요 없다. 지금 당장 여기로 불러라.",
    14530: "［료코］：응후후‥‥여전히 작은 가슴이네. 귀여워‥‥쪽.",
    14563: "［마이］：앗‥‥아얏.",
    14597: "［료코］：그러면 못써어, 내가 젊었을 때는 하루에 세 번 정도는 했었거든.",
    14600: "［마이］：정, 정말?",
    14609: "［료코］：왠지 나도 찌릿찌릿해지기 시작했어‥‥후우‥‥.",
    14636: "［료코］：좋아‥‥아후, 윽‥‥.",
    14646: "［료코］：아아아아아악! 응후후, 코지 님의 정액이 가득 차 있어. 곧 나올 거야‥‥.",
    14649: "［마이］：음-음‥‥음음음음!!",
    14658: "［료코］：아후우우!!　그 즙을‥‥그 즙을 전부 마시는 거야‥‥.",
    14689: "［료코］：아아아아, 마이, 제대로 마셔‥‥아후, 윽‥‥.",
    14713: "［료코］：그래, 좋아‥‥후우‥‥소변도 마시게 해주고 싶지만, 그건 다음으로 미룰게.",
    14791: "［료코］：마이짱, 어서 되어 버려. 코지 님은 참 좋아. 의지도 되고.",
    14803: "［료코］：되어 버려, 응?　응?　있잖아, 나랑 같이 되자.",
    14810: "［마이］：그래도‥‥노예라니‥‥아윽!　학대당하거나‥‥윽, 그러는 거잖아?　아아아앗!",
    14814: "［료코］：그런 짓 안 하셔어.　코지 님 말씀에 절대복종하기만 하면 돼.",
    14866: "［료코］：아아아, 코지 님, 제 입에 싸 주세요!",
    14892: "［료코］：굉, 굉장해‥‥코지 님 것이, 펄떡이고 있어‥‥.",
    15283: "세반고리관에, 급격하게 균형이 무너지는 감각이 밀려왔다. 지면이 흔들렸나 싶더니, 한쪽 무릎을 바닥에 대고 있었다.",
    18721: "［란파］：트레이시, 당신 아직 인코더 계측 결과 정리 안 했잖아!",
    18728: "［란파］：흐응, 코우지 님한테 혼난다아.",
    18745: "［란파］：자, 어서 가, 가!",
    19042: "［코지］：제너레이터라고 했는데‥‥.",
    19134: "［코지］：파르네리아란, 대체 누구 얘기야.",
    19993: "［코지］：좋―아, 점점 깨끗해지는군.",
    20058: "나는 서늘한 감촉을 손바닥으로 느끼며, 사다리를 한 단씩, 신중하게 내려갔다‥‥.",
    25071: "［코지］：소, 손 씻는 것도 만전‥‥?",
    25101: "밖에서는, 또각또각 발소리가 여기저기서 들려온다. 아무래도, 선내 수색이 이미 시작된 모양이었다.",
    22405: "찰싹!",
    28765: "［트레이시］：무, 뭐 말인가요?",
}
# 조각 교체만 필요한 것
HAND_FRAG = {
    9231: ("갈겨 쓰여", "갈겨쓰여"),
}
# 기각: L3963 '기시감' 제안은 기시감각 통일과 상충, L19733 은 다수 표기가 이미 맞다
DROP_LINES = {3963, 19733}

# ---------------------------------------------------------------- 전역 통일
GLOBAL = [
    ("쿠와드라", "콰드라"),
    ("에이레트", "에이레이트"),
    ("흉폭", "흉포"),
    ("라던가", "라든가"),
    ("시프", "함선"),
    ("컴퓨터룸", "컴퓨터 룸"),
    ("엔진룸", "엔진 룸"),
]
RE_KISI = re.compile(r"기시감(?!각)")


def apply_global(s):
    for a, b in GLOBAL:
        s = s.replace(a, b)
    return RE_KISI.sub("기시감각", s)


def blen(s):
    return sum(1 if ord(c) < 0x80 else 2 for c in s)


def main(write):
    lines = io.open(TR, encoding="utf-8").read().split("\n")
    data = json.load(io.open(TABLE, encoding="utf-8"))

    final = {}                      # line0 -> new text
    src = {}                        # line0 -> 출처
    # 1) 자동 표 (중복 줄과 수동 확정 줄은 건너뛴다)
    auto_lines = {}
    for t in data["table"]:
        auto_lines.setdefault(t["line0"], []).append(t)
    for l0, items in auto_lines.items():
        ln1 = l0 + 1
        if ln1 in HAND or ln1 in DROP_LINES:
            continue
        if len(items) > 1:
            print("!! 합성 안 된 중복 줄 L%d - HAND 에 넣어라" % ln1)
            return 1
        final[l0] = items[0]["new"]
        src[l0] = "auto"
    # 2) 수동 확정
    for ln1, new in HAND.items():
        l0 = ln1 - 1
        final[l0] = new
        src[l0] = "hand"
    for ln1, (a, b) in HAND_FRAG.items():
        l0 = ln1 - 1
        cur = final.get(l0, lines[l0])
        if a not in cur:
            print("!! L%d 조각 '%s' 없음" % (ln1, a))
            return 1
        final[l0] = cur.replace(a, b)
        src[l0] = "frag"
    # 3) 전역 통일 - 이미 잡힌 줄에도, 아직 안 잡힌 줄에도
    for l0 in list(final):
        final[l0] = apply_global(final[l0])
    for i, l in enumerate(lines):
        if l.startswith(("#", "//")) or i in final:
            continue
        g = apply_global(l)
        if g != l:
            final[i] = g
            src[i] = "global"

    # 무변화 제거 + 검증
    changed = {l0: v for l0, v in final.items() if v != lines[l0]}
    print("반영 대상 %d줄 (auto %d / hand %d / frag %d / global %d)" % (
        len(changed),
        sum(1 for k in changed if src[k] == "auto"),
        sum(1 for k in changed if src[k] == "hand"),
        sum(1 for k in changed if src[k] == "frag"),
        sum(1 for k in changed if src[k] == "global")))

    problems = []
    entries = []                    # (jp, new)
    jp_seen = {}
    for l0 in sorted(changed):
        new = changed[l0]
        old = lines[l0]
        if l0 < 1 or not lines[l0 - 1].startswith("//"):
            problems.append("L%d: 위에 //원문이 없다" % (l0 + 1))
            continue
        jp = lines[l0 - 1][2:]
        if blen(new) > C.MAX_BLOCK_BYTES:
            problems.append("L%d: %d바이트 초과" % (l0 + 1, blen(new)))
        for tok in re.findall(r"<\$[0-9A-F]{2}>|\\n", old):
            if old.count(tok) != new.count(tok):
                problems.append("L%d: 제어코드 %s 개수 변화" % (l0 + 1, tok))
        if jp in jp_seen and jp_seen[jp] != new:
            problems.append("L%d: 같은 원문에 다른 값 (L%d 와 충돌)\n    %s\n    %s"
                            % (l0 + 1, jp_seen[jp][0] + 1, jp_seen[jp][1], new))
            continue
        jp_seen[jp] = (l0, new)
        entries.append((jp, new))

    if problems:
        print("\n문제 %d건:" % len(problems))
        for p in problems:
            print("  " + p)
        return 1

    # 같은 jp 를 가진 다른 줄(이번에 안 건드린)도 override 로 함께 바뀐다 - 표시
    jp_all = {}
    for i, l in enumerate(lines):
        if l.startswith("//"):
            jp_all.setdefault(l[2:], []).append(i + 1)
    extra = []
    ent_jp = {jp for jp, _ in entries}
    for jp, locs in jp_all.items():
        if jp in ent_jp and len(locs) > 1:
            tgt = [l0 + 2 for l0 in changed if lines[l0 - 1][2:] == jp]
            others = [x for x in locs if x + 1 not in [t for t in tgt]]
            extra.append((jp, locs))
    if extra:
        print("\n같은 원문이 여러 곳에 있어 함께 통일되는 줄:")
        for jp, locs in extra:
            print("  %s  (원문 줄 %s)" % (jp[:50], locs))

    print("\n표본:")
    for l0 in sorted(changed)[:6]:
        print("  L%-6d- %s" % (l0 + 1, lines[l0][:64]))
        print("  %8s+ %s" % ("", changed[l0][:64]))

    if not write:
        print("\n--write 를 붙이면 반영합니다.")
        return 0

    ts = time.strftime("%Y%m%d_%H%M%S")
    shutil.copy(OV, OV + ".bak." + ts)
    shutil.copy(TR, TR + ".bak." + ts)
    print("\n백업: *.bak." + ts)

    MARK = "# 15) 전수 검수 반영"
    cur = io.open(OV, encoding="utf-8").read()
    cut = cur.find(MARK)
    head = cur[:cut] if cut >= 0 else cur.rstrip("\n") + "\n\n"
    blk = ["# ============================================================",
           MARK + " (2026-08-10 워크플로우 81 에이전트, 확정 지적 + 표기 통일)",
           "#    보고서: translation/REVIEW_FULL_20260810.md",
           "#    전역: 콰드라/에이레이트/함선/기시감각/컴퓨터 룸/엔진 룸/흉포/라든가",
           "# ============================================================"]
    for jp, new in entries:
        blk.append("//" + jp)
        blk.append(new)
    io.open(OV, "w", encoding="utf-8", newline="\n").write(
        head + "\n".join(blk) + "\n")
    print("overrides 15번 섹션: %d줄" % len(entries))

    r = subprocess.run([sys.executable, os.path.join(C.ROOT, "tools", "kobatch.py"),
                        "merge"], capture_output=True, text=True, encoding="utf-8")
    print(r.stdout.strip()[-1200:])
    if "ERROR" in (r.stdout or "") or r.returncode != 0:
        print("merge 에서 문제 발생 - 중단")
        print((r.stderr or "")[-500:])
        return 1

    after = io.open(TR, encoding="utf-8").read().split("\n")
    bad = 0
    for l0, want in changed.items():
        # merge 가 파일을 다시 쓰므로 줄 번호가 밀릴 수 있다 - jp 로 재탐색
        jp = lines[l0 - 1][2:]
        hits = [i for i, l in enumerate(after) if l.startswith("//") and l[2:] == jp]
        okc = any(i + 1 < len(after) and after[i + 1] == want for i in hits)
        if not okc:
            bad += 1
            print("  불일치: L%d %s" % (l0 + 1, want[:56]))
    print("반영 확인: %d/%d 일치" % (len(changed) - bad, len(changed)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main("--write" in sys.argv))
