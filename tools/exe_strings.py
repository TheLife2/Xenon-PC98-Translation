"""`AGS.EXE` 안의 Shift-JIS 일본어 문자열을 찾는다.

2026-08-10 발견 — 「ゲーム終了後にお楽しみ下さい」(레이디스 룸 잠금 안내)가
실행 파일에 하드코딩돼 있었다. 이전 조사의 「AGS.EXE 에 일본어 문자열 없음」 판정은
**틀렸다.** 스크립트(.CC)만 훑었기 때문이다.

    py tools/exe_strings.py            일본어 문자열 목록
    py tools/exe_strings.py --all      ASCII 문자열도 함께
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kocfg as C

EXE = os.path.join(C.ROOT, "gfx", "AGS.EXE")


def is_sjis_lead(b):
    return 0x81 <= b <= 0x9F or 0xE0 <= b <= 0xEF


def is_sjis_trail(b):
    return 0x40 <= b <= 0x7E or 0x80 <= b <= 0xFC


def looks_japanese(s):
    """실제 일본어 문장인지. 코드 바이트 오탐을 걸러낸다.

    기준: 가나(ひらがな·カタカナ)나 흔한 한자·기호가 섞여 있고,
    U+FFFD(디코드 실패)가 없어야 한다.
    """
    if "�" in s:
        return False
    kana = sum(1 for c in s if 0x3040 <= ord(c) <= 0x30FF)
    cjk = sum(1 for c in s if 0x4E00 <= ord(c) <= 0x9FFF)
    punct = sum(1 for c in s if c in "。、！？「」・ー～：")
    # 가나가 하나도 없으면 한자만 우연히 이어진 코드일 가능성이 높다
    return kana >= 1 and (kana + cjk + punct) >= 3


def scan(data, min_chars=2, strict=True):
    """전각 Shift-JIS 가 min_chars 자 이상 이어지는 구간"""
    out = []
    i = 0
    n = len(data)
    while i < n - 1:
        if is_sjis_lead(data[i]) and is_sjis_trail(data[i + 1]):
            j = i
            cnt = 0
            while j < n - 1 and is_sjis_lead(data[j]) and is_sjis_trail(data[j + 1]):
                j += 2
                cnt += 1
            # 뒤에 반각(가나·영문)이 붙는 경우도 같이 잡는다
            k = j
            while k < n and 0x20 <= data[k] < 0x80:
                k += 1
            if cnt >= min_chars:
                raw = data[i:k]
                try:
                    s = raw.decode("shift-jis")
                except UnicodeDecodeError:
                    s = raw.decode("shift-jis", "replace")
                if not strict or looks_japanese(s):
                    out.append((i, cnt, s))
            i = j
        else:
            i += 1
    return out


def main():
    data = open(EXE, "rb").read()
    hits = scan(data)
    print("AGS.EXE %d바이트 — 일본어 문자열 %d건\n" % (len(data), len(hits)))
    for off, cnt, s in hits:
        print("  0x%05X  %2d자  %s" % (off, cnt, s.replace("\n", "\\n")))
    if hits:
        print("\n※ 이것들은 실행 파일 안에 있어 .CC 스크립트 파이프라인 대상이 아니다.")
        print("   바꾸려면 EXE 를 직접 패치해야 하고, Shift-JIS 자리에 한글을 넣으려면")
        print("   폰트 슬롯 할당(tools/koalloc.py)과 같은 방식이 필요하다.")
        print("   길이가 원본을 넘으면 안 된다 (문자열 테이블이 고정 배치다).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
