"""정답 이미지(ground truth) 수집기.

에뮬레이터를 띄우고 **클라이언트 영역 640x400 만** 고속으로 캡처해
화면이 바뀔 때마다 PNG 로 남긴다. 포커스를 뺏지 않는다(PrintWindow).

    py tools/gt_capture.py --secs 40 --out out/gt/logo
    py tools/gt_capture.py --secs 90 --clk 1 --out out/gt/logo_slow
    py tools/gt_capture.py --secs 60 --enter 25,28,31 --out out/gt/title

옵션
  --secs N     캡처를 N초 동안 돈다 (창이 뜬 시점부터)
  --clk M      np2.ini 의 clk_mult 를 M 으로 바꾼다 (기본 4 = 실기속도).
               1 로 두면 CPU 가 1/4 속도 -> 애니메이션 프레임이 벌어져 잡기 쉽다.
  --fps F      폴링 목표 fps (기본 25)
  --enter t1,t2,...  해당 초에 Enter 를 보낸다
  --out DIR    출력 폴더

출력
  DIR/f0000_t012.345.png   변화가 감지된 프레임만. 파일명에 창 뜬 뒤 경과초.
  DIR/index.txt            프레임 목록 + 이전 프레임 대비 바뀐 픽셀 수
"""
import argparse
import ctypes
import ctypes.wintypes as wt
import hashlib
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
user32.SetProcessDPIAware()

PW_RENDERFULLCONTENT = 2
WM_KEYDOWN, WM_KEYUP = 0x0100, 0x0101
VK_RETURN, SC_RETURN = 0x0D, 0x1C
KEYS = {                       # 이름 -> (VK, 스캔코드)
    "enter": (0x0D, 0x1C), "esc": (0x1B, 0x01), "space": (0x20, 0x39),
    "up": (0x26, 0x48), "down": (0x28, 0x50),
    "left": (0x25, 0x4B), "right": (0x27, 0x4D),
    "x": (0x58, 0x2D), "z": (0x5A, 0x2C),
}
EMU_EXE = r"C:\thelife\pc98\np2fmgen\extracted\np2fmgen_260802\np2fmgen\np2.exe"


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG),
                ("biPlanes", wt.WORD), ("biBitCount", wt.WORD),
                ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD),
                ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG),
                ("biClrUsed", wt.DWORD), ("biClrImportant", wt.DWORD)]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wt.DWORD * 3)]


class POINT(ctypes.Structure):
    _fields_ = [("x", wt.LONG), ("y", wt.LONG)]


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


def client_box(hwnd):
    """(win_w, win_h, cx, cy, cw, ch) - 창 캡처 안에서 클라이언트 영역의 위치."""
    wr = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(wr))
    cr = wt.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(cr))
    p = POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(p))
    return (wr.right - wr.left, wr.bottom - wr.top,
            p.x - wr.left, p.y - wr.top, cr.right, cr.bottom)


class Grabber:
    """창 크기가 안 바뀌는 동안 DC/비트맵을 재사용해 캡처를 빠르게 한다."""

    def __init__(self, hwnd):
        self.hwnd = hwnd
        self.w = self.h = 0
        self.hdc = self.mdc = self.bmp = None
        self._resize()

    def _resize(self):
        w, h, cx, cy, cw, ch = client_box(self.hwnd)
        if (w, h) == (self.w, self.h):
            self.box = (cx, cy, cw, ch)
            return
        self.free()
        self.w, self.h = w, h
        self.box = (cx, cy, cw, ch)
        self.hdc = user32.GetWindowDC(self.hwnd)
        self.mdc = gdi32.CreateCompatibleDC(self.hdc)
        self.bmp = gdi32.CreateCompatibleBitmap(self.hdc, w, h)
        gdi32.SelectObject(self.mdc, self.bmp)
        self.bi = BITMAPINFO()
        self.bi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        self.bi.bmiHeader.biWidth = w
        self.bi.bmiHeader.biHeight = -h
        self.bi.bmiHeader.biPlanes = 1
        self.bi.bmiHeader.biBitCount = 32
        self.buf = ctypes.create_string_buffer(w * h * 4)

    def grab(self):
        self._resize()
        user32.PrintWindow(self.hwnd, self.mdc, PW_RENDERFULLCONTENT)
        gdi32.GetDIBits(self.mdc, self.bmp, 0, self.h, self.buf,
                        ctypes.byref(self.bi), 0)
        cx, cy, cw, ch = self.box
        if cw <= 0 or ch <= 0:
            return None, None
        raw = self.buf.raw
        stride = self.w * 4
        rows = [raw[(cy + y) * stride + cx * 4:(cy + y) * stride + (cx + cw) * 4]
                for y in range(ch)]
        return b"".join(rows), (cw, ch)

    def free(self):
        if self.bmp:
            gdi32.DeleteObject(self.bmp)
        if self.mdc:
            gdi32.DeleteDC(self.mdc)
        if self.hdc:
            user32.ReleaseDC(self.hwnd, self.hdc)
        self.bmp = self.mdc = self.hdc = None


def send_key(hwnd, name="enter"):
    vk, sc = KEYS[name]
    dn = (sc << 16) | 1
    up = ((sc << 16) | 0xC0000001) & 0xFFFFFFFF
    user32.PostMessageW(hwnd, WM_KEYDOWN, vk, dn)
    time.sleep(0.06)
    user32.PostMessageW(hwnd, WM_KEYUP, vk, up)


def send_enter(hwnd):
    send_key(hwnd, "enter")


def prepare_run_dir(clk_mult):
    run = os.path.join(C.OUT_DIR, "run")
    os.makedirs(run, exist_ok=True)
    for src, dst in ((EMU_EXE, "np2.exe"),
                     (os.path.join(C.OUT_DIR, "font.tmp"), "font.tmp"),
                     (os.path.join(C.OUT_DIR, "xenon_ko.hdi"), "xenon_ko.hdi")):
        if not os.path.exists(src):
            raise SystemExit("없음: " + src)
        if not os.path.exists(os.path.join(run, dst)) or \
                os.path.getsize(src) != os.path.getsize(os.path.join(run, dst)):
            shutil.copy(src, os.path.join(run, dst))
    ini = os.path.join(run, "np2.ini")
    lines = open(ini, encoding="ascii", errors="replace").read().splitlines()
    out = []
    for l in lines:
        if clk_mult and l.startswith("clk_mult="):
            l = "clk_mult=%d" % clk_mult
        elif l.startswith("HDfolder="):
            l = "HDfolder=" + run
        elif l.startswith("HDD1FILE="):
            l = "HDD1FILE=" + os.path.join(run, "xenon_ko.hdi")
        elif l.startswith("SkpFrame="):
            l = "SkpFrame=0"
        out.append(l)
    open(ini, "w", encoding="ascii").write("\n".join(out) + "\n")
    return run


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--secs", type=float, default=40.0)
    ap.add_argument("--clk", type=int, default=0)
    ap.add_argument("--fps", type=float, default=25.0)
    ap.add_argument("--enter", default="")
    ap.add_argument("--script", default="",
                    help='"22:down,23:down,24:enter" 형태의 시각:키 목록')
    ap.add_argument("--enter-every", type=float, default=0.0)
    ap.add_argument("--enter-from", type=float, default=0.0)
    ap.add_argument("--hashrect", default="",
                    help="x0,y0,x1,y1 (화면 좌표). 이 영역이 바뀔 때만 저장한다. "
                         "대사창을 빼면 그래픽 변화만 남는다")
    ap.add_argument("--out", default=os.path.join(C.OUT_DIR, "gt", "logo"))
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args()

    outdir = os.path.abspath(a.out)
    shutil.rmtree(outdir, ignore_errors=True)
    os.makedirs(outdir, exist_ok=True)

    run = prepare_run_dir(a.clk)
    subprocess.run(["taskkill", "/IM", "np2.exe", "/F"], capture_output=True)
    time.sleep(0.5)
    subprocess.Popen([os.path.join(run, "np2.exe")], cwd=run)

    hwnd = None
    for _ in range(60):
        time.sleep(0.5)
        hwnd = find_window()
        if hwnd:
            break
    if not hwnd:
        raise SystemExit("에뮬레이터 창을 못 찾았습니다")
    print("창 발견 hwnd=%s  geometry=%s" % (hwnd, client_box(hwnd)))

    enters = [(float(x), "enter") for x in a.enter.split(",") if x.strip()]
    for item in a.script.split(","):
        if item.strip():
            t, k = item.split(":")
            enters.append((float(t), k.strip()))
    if a.enter_every > 0:
        t = a.enter_from
        while t < a.secs:
            enters.append((t, "enter"))
            t += a.enter_every
    enters.sort()
    hr = [int(v) for v in a.hashrect.split(",")] if a.hashrect else None
    g = Grabber(hwnd)
    t0 = time.time()
    period = 1.0 / a.fps
    last = None
    idx = 0
    log = []
    nxt = t0
    while time.time() - t0 < a.secs:
        now = time.time()
        if now < nxt:
            time.sleep(min(period, nxt - now))
            continue
        nxt += period
        if nxt < now:
            nxt = now + period
        el = now - t0
        while enters and el >= enters[0][0]:
            send_key(hwnd, enters[0][1])
            print("  [%.2f] %s" % (el, enters[0][1]))
            enters.pop(0)
        try:
            data, size = g.grab()
        except Exception:
            data = size = None
        if data is None:
            nh = find_window()
            if nh and nh != hwnd:
                print("  [%.2f] 창이 바뀌었다(에뮬레이터 재시작?) hwnd %s -> %s"
                      % (el, hwnd, nh), flush=True)
                hwnd = nh
                g.free()
                g = Grabber(hwnd)
            continue
        if hr:
            hx0, hy0, hx1, hy1 = hr
            stride = size[0] * 4
            key = b"".join(data[(y + 1) * stride + (hx0 + 1) * 4:
                                (y + 1) * stride + (hx1 + 1) * 4]
                           for y in range(hy0, hy1))
        else:
            key = data
        h = hashlib.md5(key).digest()
        if h == last:
            continue
        last = h
        name = "f%04d_t%07.3f.png" % (idx, el)
        Image.frombuffer("RGB", size, data, "raw", "BGRX", 0, 1).save(
            os.path.join(outdir, name), compress_level=1)
        log.append("%s  %dx%d" % (name, size[0], size[1]))
        idx += 1
    g.free()
    open(os.path.join(outdir, "index.txt"), "w", encoding="utf-8").write(
        "\n".join(log) + "\n")
    print("프레임 %d장 -> %s" % (idx, outdir))
    if not a.keep:
        subprocess.run(["taskkill", "/IM", "np2.exe", "/F"], capture_output=True)


if __name__ == "__main__":
    main()
