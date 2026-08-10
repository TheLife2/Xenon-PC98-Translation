"""특수 모드 스크립트(K/L/M) 번역.

  K.CC  LADY'S ROOM — CG 감상 모드의 선택지
  L.CC  데이터 로드 메뉴
  M.CC  뮤직 모드 — 곡명은 대부분 로마자라 그대로 두고, 제목줄과 일본어 곡명만 옮긴다

선두·말미의 전각 공백은 화면 정렬이다. 개수를 그대로 유지한다.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kocfg as C

FW = "　"

SEED = {
    # --- K.CC : LADY'S ROOM ---
    "　　　　　　　　　 ＬＡＤＹ’Ｓ　ＲＯＯＭ":
        "　　　　　　　　　 ＬＡＤＹ’Ｓ　ＲＯＯＭ",      # 로마자 제목 - 그대로
    "　◆ 先に進む　　": "　◆ 다음으로　　",
    "　◆ 最後尾に進む": "　◆ 맨 뒤로",
    "　◆ メニューに戻る　　　": "　◆ 메뉴로　　　",
    "　◆ 前に戻る": "　◆ 이전으로",
    "　◆ 最初の絵に戻る　": "　◆ 첫 그림으로　",
    "　◆ メニューに戻る": "　◆ 메뉴로",

    # --- L.CC : 로드 메뉴 ---
    "　ゲームの続きをロードする。　": "　이어서 불러온다.　",
    "　メニューへ戻る。": "　메뉴로 돌아간다.",
    "　データ１をロードする。　": "　데이터１을 불러온다.　",
    "　データ２をロードする。": "　데이터２를 불러온다.",
    "　データ３をロードする。": "　데이터３을 불러온다.",
    "　データ４をロードする。": "　데이터４를 불러온다.",

    # --- M.CC : 뮤직 모드 ---
    "　　　　　　　　～　ミュージックモード　～":
        "　　　　　　　　～　뮤직 모드　～",
    # 곡명은 원곡 제목이라 로마자를 그대로 둔다. 일본어 제목 하나만 옮긴다.
    # 「蝶」(1자) -> 「나비」(2자) 라 2칼럼 오른쪽으로 밀리므로 선두 공백을 하나 줄인다.
    "　　　　　　　　　　     　蝶": "　　　　　　　　　     　나비",
}


def main(write):
    pairs = C.load_pairs()
    todo = [(jp, ko) for jp, ko in pairs if not ko.strip()]
    hit = [(jp, SEED[jp]) for jp, _ in todo if jp in SEED]
    miss = [jp for jp, _ in todo if jp not in SEED]

    print(f"미번역 {len(todo)}줄 중 {len(hit)}줄 번역, {len(miss)}줄은 로마자라 원문 유지")

    def blen(s):
        return sum(1 if ord(c) < 0x80 else 2 for c in s)

    def cols(s):
        return sum(1 if ord(c) < 0x80 else 2 for c in s)

    print()
    for jp, ko in hit:
        flag = ""
        if cols(jp) != cols(ko):
            flag = f"   폭 {cols(jp)} -> {cols(ko)}"
        print(f"  {jp[:44]}")
        print(f"  {ko[:44]}{flag}")
    if miss:
        print(f"\n원문 유지({len(miss)}줄) - 곡명·제목이라 로마자 그대로:")
        for jp in miss[:6]:
            print(f"    {jp.strip()[:40]}")
        print(f"    ...")

    over = [k for _, k in hit if blen(k) > C.MAX_BLOCK_BYTES]
    print(f"\n255바이트 초과 {len(over)}줄")

    if not write:
        print("--write 를 붙이면 반영합니다.")
        return

    # 로마자 곡명은 원문 그대로 채워 '번역 완료' 로 만든다
    allfix = hit + [(jp, jp) for jp in miss]
    path = os.path.join(C.ROOT, "translation", "overrides.txt")
    MARK = "# 14) 특수 모드 (K/L/M)"
    cur = open(path, encoding="utf-8").read()
    cut = cur.find(MARK)
    head = cur[:cut] if cut >= 0 else cur.rstrip("\n") + "\n\n"
    blk = (MARK + " - LADY'S ROOM / 로드 메뉴 / 뮤직 모드 (2026-08-09)\n"
           "#    원본 저장소 scripts_cc 에 없어 파이프라인 밖이던 파일들이다.\n"
           "#    영문판도 이 셋은 번역하지 않았다(JP/EN 이미지에서 바이트 동일).\n"
           "#    뮤직 모드 곡명은 원곡 제목이라 로마자를 그대로 둔다.\n"
           "#    선두·말미 전각 공백은 화면 정렬이므로 개수를 유지한다.\n"
           "# ============================================================\n")
    for jp, ko in allfix:
        blk += f"//{jp}\n{ko}\n"
    open(path, "w", encoding="utf-8", newline="\n").write(head + blk)
    print(f"\noverrides 14번 섹션에 {len(allfix)}줄 기록")


if __name__ == "__main__":
    main("--write" in sys.argv)
