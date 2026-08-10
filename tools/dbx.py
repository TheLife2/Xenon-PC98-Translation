"""DOSBox-X 창을 캡처하고 키를 보내는 도우미 (포커스를 뺏지 않는다).

    py tools/dbx.py shot <파일.png>          현재 화면 저장
    py tools/dbx.py type "AGS" [--enter]     문자열 입력
    py tools/dbx.py key <VK16진수> [반복]     가상키 코드로 입력 (예: 0D=Enter)
    py tools/dbx.py wait <초>                기다린다

kotest.py 와 같은 방식(PrintWindow + PostMessage)이라 창이 가려져 있어도 된다.
"""
import ctypes
import ctypes.wintypes as wt
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kotest import BITMAPINFO, BITMAPINFOHEADER, PW_RENDERFULLCONTENT

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
WM_KEYDOWN, WM_KEYUP, WM_CHAR = 0x0100, 0x0101, 0x0102

# 문자 -> (가상키, 시프트필요)
def vk_of(ch):
    r = user32.VkKeyScanW(ord(ch))
    return r & 0xFF, bool(r & 0x100)


def find():
    found = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(hwnd, _):
        n = user32.GetWindowTextLengthW(hwnd)
        if n:
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            t = buf.value
            if "DOSBox-X" in t and user32.IsWindowVisible(hwnd):
                # PC-98 디버깅 창을 우선 (title=XENON-DBG)
                found.append((0 if "XENON-DBG" in t else 1, hwnd, t))
        return True

    user32.EnumWindows(cb, 0)
    if not found:
        return None, None
    found.sort()
    return found[0][1], found[0][2]


def shot(hwnd, path):
    r = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    w, h = r.right - r.left, r.bottom - r.top
    hdc = user32.GetWindowDC(hwnd)
    mdc = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    gdi32.SelectObject(mdc, bmp)
    user32.PrintWindow(hwnd, mdc, PW_RENDERFULLCONTENT)
    bi = BITMAPINFO()
    bi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bi.bmiHeader.biWidth = w
    bi.bmiHeader.biHeight = -h
    bi.bmiHeader.biPlanes = 1
    bi.bmiHeader.biBitCount = 32
    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bi), 0)
    gdi32.DeleteObject(bmp); gdi32.DeleteDC(mdc); user32.ReleaseDC(hwnd, hdc)
    from PIL import Image
    Image.frombuffer("RGB", (w, h), buf, "raw", "BGRX", 0, 1).save(path)
    return w, h


def press(hwnd, vk, shift=False):
    if shift:
        user32.PostMessageW(hwnd, WM_KEYDOWN, 0x10, 0)
    user32.PostMessageW(hwnd, WM_KEYDOWN, vk, 0)
    time.sleep(0.03)
    user32.PostMessageW(hwnd, WM_KEYUP, vk, 0xC0000000)
    if shift:
        user32.PostMessageW(hwnd, WM_KEYUP, 0x10, 0xC0000000)
    time.sleep(0.05)


def main():
    a = sys.argv[1:]
    if not a:
        print(__doc__)
        return 1
    hwnd, title = find()
    if not hwnd:
        print("DOSBox-X 창을 못 찾음")
        return 1
    cmd = a[0]
    if cmd == "shot":
        w, h = shot(hwnd, a[1])
        print("저장 %s (%dx%d)  창: %s" % (a[1], w, h, title))
    elif cmd == "type":
        for ch in a[1]:
            vk, sh = vk_of(ch)
            press(hwnd, vk, sh)
        if "--enter" in a:
            press(hwnd, 0x0D)
        print("입력: %s" % a[1])
    elif cmd == "key":
        vk = int(a[1], 16)
        rep = int(a[2]) if len(a) > 2 and a[2].isdigit() else 1
        for _ in range(rep):
            press(hwnd, vk)
        print("키 %02X x%d" % (vk, rep))
    elif cmd == "wait":
        time.sleep(float(a[1]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
