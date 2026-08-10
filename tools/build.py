"""전체 빌드 오케스트레이터.

    py tools/build.py            검사 -> 할당 -> 폰트 -> 삽입 -> 압축 -> 이미지
    py tools/build.py --run      빌드 후 에뮬레이터로 띄운다
    py tools/build.py --force    경고를 무시하고 진행 (치명적 문제는 그래도 중단)

산출물
    out/xenon_ko.hdi     게임 이미지
    out/font.tmp         Neko Project II 용 폰트 시트   (반드시 같이 배포)
    out/anex86.bmp       Anex86 용 폰트 시트
"""
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kocfg as C
import koalloc
import kofont
import koreplacer
import kolzss
import koverify
from kohdi import Fat12

EMU_EXE = r"C:\thelife\pc98\np2fmgen\extracted\np2fmgen_260802\np2fmgen\np2.exe"
EMU_INI = os.path.join(C.TOOLS_REPO, "tools", "np2", "cfg", "np2_eng.ini")


def step(n, title):
    print(f"\n=== {n}. {title} " + "=" * max(0, 52 - len(title)))


def main():
    force = "--force" in sys.argv
    t0 = time.time()

    # 할당이 먼저다 - 검사기가 할당표를 보고 인코딩 가능 여부를 판정한다
    step(1, "글리프 슬롯 할당")
    table = koalloc.allocate()
    if not table:
        print("번역된 줄이 없습니다. translation/_script-korean.txt 를 채우세요.")
        return 1

    step(2, "번역문 검사")
    fatal, warn = koverify.check()
    if fatal:
        print("\n치명적 문제가 있어 중단합니다.")
        return 1
    if warn and not force:
        print("(경고는 진행을 막지 않습니다)")

    step(3, "폰트 시트 생성")
    kofont.main()

    step(4, "스크립트에 한국어 삽입")
    if koreplacer.main():
        return 1

    step(5, "LZSS 압축")
    print("  압축기:", "xenon_lzss.exe" if kolzss.exe_available() else "파이썬 구현")
    total_in = total_out = 0
    for name in C.SCRIPT_NAMES:
        raw = open(os.path.join(C.MERGE_DIR, name + ".U.CC"), "rb").read()
        cc = kolzss.compress(raw)
        assert kolzss.decompress(cc) == raw, f"{name}: 압축 왕복 실패"
        open(os.path.join(C.BUILD_DIR, name + ".CC"), "wb").write(cc)
        total_in += len(raw)
        total_out += len(cc)
    print(f"  {len(C.SCRIPT_NAMES)}개 파일  {total_in:,} -> {total_out:,} 바이트 "
          f"(왕복 검증 통과)")

    step(6, "디스크 이미지 작성")
    fs = Fat12(C.BASE_HDI)
    before = len(fs.free_clusters())
    grown = 0
    for name in C.SCRIPT_NAMES:
        cc = open(os.path.join(C.BUILD_DIR, name + ".CC"), "rb").read()
        need, had = fs.write(name + ".CC", cc)
        if need > had:
            grown += 1
    out = os.path.join(C.OUT_DIR, "xenon_ko.hdi")
    fs.save(out)
    after = len(Fat12(out).free_clusters())
    print(f"  {out}")
    print(f"  빈 클러스터 {before} -> {after} (클러스터가 늘어난 파일 {grown}개)")

    step(7, "편집한 그래픽 반영")
    try:
        import gfx_build
        gfx_build.apply(out, write=True)
    except Exception as e:
        print(f"  건너뜀: {e}")

    step(8, "이미지 재검증")
    chk = Fat12(out)
    bad = 0
    for name in C.SCRIPT_NAMES:
        want = open(os.path.join(C.BUILD_DIR, name + ".CC"), "rb").read()
        got = chk.read(name + ".CC")
        src = open(os.path.join(C.MERGE_DIR, name + ".U.CC"), "rb").read()
        if got != want or kolzss.decompress(got) != src:
            print("  불일치:", name)
            bad += 1
    print(f"  이미지에서 되읽어 비교: {len(C.SCRIPT_NAMES)-bad}/{len(C.SCRIPT_NAMES)} 일치")
    if bad:
        return 1

    print(f"\n완료 ({time.time()-t0:.1f}초)")
    print(f"  이미지 : {out}")
    print(f"  폰트   : {os.path.join(C.OUT_DIR, 'font.tmp')}  (에뮬레이터 폴더에 같이 둘 것)")

    if "--run" in sys.argv:
        step(8, "에뮬레이터 실행")
        run_emu(out)
    return 0


def run_emu(hdi):
    """np2.exe(PC-9801) 로 띄운다. np21(PC-9821)은 이 SASI 이미지를 못 읽는다."""
    if not os.path.exists(EMU_EXE):
        print("  에뮬레이터를 못 찾음:", EMU_EXE)
        return
    run = os.path.join(C.OUT_DIR, "run")
    os.makedirs(run, exist_ok=True)
    shutil.copy(EMU_EXE, run)
    shutil.copy(os.path.join(C.OUT_DIR, "font.tmp"), run)
    shutil.copy(hdi, os.path.join(run, "xenon_ko.hdi"))
    ini = open(EMU_INI, encoding="ascii", errors="replace").read().splitlines()
    ini = [("HDfolder=" + run) if l.startswith("HDfolder=")
           else ("HDD1FILE=" + os.path.join(run, "xenon_ko.hdi")) if l.startswith("HDD1FILE=")
           else l for l in ini]
    open(os.path.join(run, "np2.ini"), "w", encoding="ascii").write("\n".join(ini) + "\n")
    subprocess.Popen([os.path.join(run, "np2.exe")], cwd=run)
    print("  실행:", run, "(부팅에 25~40초 걸립니다)")


if __name__ == "__main__":
    sys.exit(main())
