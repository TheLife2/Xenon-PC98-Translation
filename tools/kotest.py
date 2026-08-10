"""빌드한 이미지를 에뮬레이터로 띄우고 자동으로 진행시키며 스크린샷을 남긴다.

    py tools/kotest.py              기본 30컷
    py tools/kotest.py 60           60컷
    py tools/kotest.py 40 --keep    끝나도 에뮬레이터를 닫지 않는다

동작 방식
  * PrintWindow(hwnd, hdc, PW_RENDERFULLCONTENT) 로 창을 캡처한다.
    창이 다른 창에 가려져 있어도 찍히고, 포커스를 뺏지 않는다.
  * PostMessage(WM_KEYDOWN/WM_KEYUP) 로 키를 보낸다. 역시 포커스가 필요 없다.
  * 부팅에 25~40초 걸린다. 그 전에 보낸 키는 삼켜진다.

주의 : np2.exe(PC-9801) 를 써야 한다. np21(PC-9821)은 이 Anex86 SASI 이미지를 못 읽는다.
"""
import ctypes
import ctypes.wintypes as wt
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kocfg as C

from PIL import Image

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)

PW_RENDERFULLCONTENT = 2
WM_KEYDOWN, WM_KEYUP = 0x0100, 0x0101
VK_RETURN, SC_RETURN = 0x0D, 0x1C

EMU_EXE = r"C:\thelife\pc98\np2fmgen\extracted\np2fmgen_260802\np2fmgen\np2.exe"
EMU_INI = os.path.join(C.TOOLS_REPO, "tools", "np2", "cfg", "np2_eng.ini")
SHOTS = os.path.join(C.OUT_DIR, "shots")


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG),
                ("biPlanes", wt.WORD), ("biBitCount", wt.WORD),
                ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD),
                ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG),
                ("biClrUsed", wt.DWORD), ("biClrImportant", wt.DWORD)]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wt.DWORD * 3)]


def find_window():
    found = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(hwnd, _):
        n = user32.GetWindowTextLengthW(hwnd)
        if n:
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            if "Neko Project" in buf.value and user32.IsWindowVisible(hwnd):
                found.append(hwnd)
        return True

    user32.EnumWindows(cb, 0)
    return found[0] if found else None


def capture(hwnd):
    r = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    w, h = r.right - r.left, r.bottom - r.top
    if w <= 0 or h <= 0:
        return None
    hdc = user32.GetWindowDC(hwnd)
    mdc = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    gdi32.SelectObject(mdc, bmp)
    user32.PrintWindow(hwnd, mdc, PW_RENDERFULLCONTENT)

    bi = BITMAPINFO()
    bi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bi.bmiHeader.biWidth = w
    bi.bmiHeader.biHeight = -h          # top-down
    bi.bmiHeader.biPlanes = 1
    bi.bmiHeader.biBitCount = 32
    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bi), 0)

    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mdc)
    user32.ReleaseDC(hwnd, hdc)
    return Image.frombuffer("RGB", (w, h), buf, "raw", "BGRX", 0, 1)


def send_enter(hwnd):
    dn = (SC_RETURN << 16) | 1
    up = (SC_RETURN << 16) | 0xC0000001
    user32.PostMessageW(hwnd, WM_KEYDOWN, VK_RETURN, dn)
    time.sleep(0.09)
    user32.PostMessageW(hwnd, WM_KEYUP, VK_RETURN, up & 0xFFFFFFFF)


def prepare_run_dir():
    run = os.path.join(C.OUT_DIR, "run")
    os.makedirs(run, exist_ok=True)
    for f, dst in ((EMU_EXE, "np2.exe"),
                   (os.path.join(C.OUT_DIR, "font.tmp"), "font.tmp"),
                   (os.path.join(C.OUT_DIR, "xenon_ko.hdi"), "xenon_ko.hdi")):
        if not os.path.exists(f):
            raise SystemExit(f"없음: {f}  (build.py 를 먼저 돌리세요)")
        shutil.copy(f, os.path.join(run, dst))
    ini = open(EMU_INI, encoding="ascii", errors="replace").read().splitlines()
    ini = [("HDfolder=" + run) if l.startswith("HDfolder=")
           else ("HDD1FILE=" + os.path.join(run, "xenon_ko.hdi")) if l.startswith("HDD1FILE=")
           else l for l in ini]
    open(os.path.join(run, "np2.ini"), "w", encoding="ascii").write("\n".join(ini) + "\n")
    return run


def main():
    shots = int(next((a for a in sys.argv[1:] if a.isdigit()), 30))
    keep = "--keep" in sys.argv

    for f in ("xenon_ko.hdi", "font.tmp"):
        p = os.path.join(C.OUT_DIR, f)
        print(f"  {f}: {os.path.getsize(p):,} 바이트")

    run = prepare_run_dir()
    shutil.rmtree(SHOTS, ignore_errors=True)
    os.makedirs(SHOTS, exist_ok=True)

    subprocess.Popen([os.path.join(run, "np2.exe")], cwd=run)
    print("에뮬레이터 기동, 부팅 대기 40초 ...")
    hwnd = None
    for _ in range(60):
        time.sleep(1)
        hwnd = find_window()
        if hwnd:
            break
    if not hwnd:
        raise SystemExit("에뮬레이터 창을 못 찾았습니다")
    time.sleep(40)

    im = capture(hwnd)
    if im:
        im.save(os.path.join(SHOTS, "shot_000.png"))
    print(f"타이틀 화면 캡처. {shots}컷 진행 시작 ...")

    for i in range(1, shots + 1):
        send_enter(hwnd)
        time.sleep(2.2)
        im = capture(hwnd)
        if im:
            im.save(os.path.join(SHOTS, f"shot_{i:03d}.png"))
        if i % 10 == 0:
            print(f"  {i}/{shots}")

    alive = find_window() is not None
    print(f"완료. 에뮬레이터 살아있음={alive}, 스크린샷 {SHOTS}")
    if not keep:
        subprocess.run(["taskkill", "/IM", "np2.exe", "/F"], capture_output=True)
        print("에뮬레이터 종료")
    return 0 if alive else 1


if __name__ == "__main__":
    sys.exit(main())
