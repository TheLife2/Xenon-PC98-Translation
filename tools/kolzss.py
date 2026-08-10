"""LZSS 압축/해제.

.CC 컨테이너 = 24바이트 헤더 + Okumura LZSS 스트림
    [0x00..0x13]  원본은 "LCZ" + 잔여 바이트. 게임이 읽지 않는다(영문판이 0으로 채워도 동작)
    [0x14..0x17]  압축 전 크기 (LE32)
    [0x18..   ]   LZSS 스트림  (N=4096, F=18, THRESHOLD=2)

기본값은 원본 도구 xenon_lzss.exe 를 쓰고, 없거나 못 돌리면 파이썬 구현으로 넘어간다.
두 경로가 같은 결과를 내는 것은 원본 37개 파일로 확인했다
(exe 출력 == 파이썬 출력 == 저장소 scripts_build, 37/37 바이트 일치).
"""
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kocfg as C

N, F, THRESHOLD, NIL = 4096, 18, 2, 4096
HDR = 0x18


# ------------------------------------------------------------- 해제 ----
def decompress(data: bytes) -> bytes:
    out = bytearray()
    buf = bytearray(N + F - 1)
    for i in range(N - F):
        buf[i] = 0x20
    r, flags, pos, n = N - F, 0, HDR, len(data)
    while True:
        flags >>= 1
        if not (flags & 256):
            if pos >= n:
                break
            flags = data[pos] | 0xFF00
            pos += 1
        if flags & 1:
            if pos >= n:
                break
            c = data[pos]; pos += 1
            out.append(c); buf[r] = c; r = (r + 1) & (N - 1)
        else:
            if pos + 1 >= n:
                break
            i, j = data[pos], data[pos + 1]; pos += 2
            i |= (j & 0xF0) << 4
            j = (j & 0x0F) + THRESHOLD
            for k in range(j + 1):
                c = buf[(i + k) & (N - 1)]
                out.append(c); buf[r] = c; r = (r + 1) & (N - 1)
    return bytes(out)


# ------------------------------------------------------- 압축(파이썬) ----
class _Enc:
    def __init__(self, src):
        self.src, self.sp = src, 0
        self.tb = bytearray(N + F - 1)
        self.lson = [0] * (N + 1)
        self.rson = [0] * (N + 257)
        self.dad = [0] * (N + 1)
        self.mp = self.ml = 0
        self.out = bytearray()

    def _get(self):
        if self.sp >= len(self.src):
            return -1
        c = self.src[self.sp]; self.sp += 1
        return c

    def _insert(self, r):
        tb, lson, rson, dad = self.tb, self.lson, self.rson, self.dad
        cmp_, p = 1, N + 1 + tb[r]
        rson[r] = lson[r] = NIL
        self.ml = 0
        while True:
            if cmp_ >= 0:
                if rson[p] != NIL:
                    p = rson[p]
                else:
                    rson[p] = r; dad[r] = p; return
            else:
                if lson[p] != NIL:
                    p = lson[p]
                else:
                    lson[p] = r; dad[r] = p; return
            i = 1
            while i < F:
                cmp_ = tb[r + i] - tb[p + i]
                if cmp_:
                    break
                i += 1
            if i > self.ml:
                self.mp, self.ml = p, i
                if i >= F:
                    break
        dad[r], lson[r], rson[r] = dad[p], lson[p], rson[p]
        dad[lson[p]] = dad[rson[p]] = r
        if rson[dad[p]] == p:
            rson[dad[p]] = r
        else:
            lson[dad[p]] = r
        dad[p] = NIL

    def _delete(self, p):
        lson, rson, dad = self.lson, self.rson, self.dad
        if dad[p] == NIL:
            return
        if rson[p] == NIL:
            q = lson[p]
        elif lson[p] == NIL:
            q = rson[p]
        else:
            q = lson[p]
            if rson[q] != NIL:
                while rson[q] != NIL:
                    q = rson[q]
                rson[dad[q]] = lson[q]; dad[lson[q]] = dad[q]
                lson[q] = lson[p]; dad[lson[p]] = q
            rson[q] = rson[p]; dad[rson[p]] = q
        dad[q] = dad[p]
        if rson[dad[p]] == p:
            rson[dad[p]] = q
        else:
            lson[dad[p]] = q
        dad[p] = NIL

    def run(self):
        tb = self.tb
        for i in range(N + 1, N + 257):
            self.rson[i] = NIL
        for i in range(N):
            self.dad[i] = NIL
        code = bytearray(17)
        cp, mask, s, r = 1, 1, 0, N - F
        for i in range(s, r):
            tb[i] = 0x20
        length = 0
        while length < F:
            c = self._get()
            if c < 0:
                break
            tb[r + length] = c
            length += 1
        if not length:
            return b""
        for i in range(1, F + 1):
            self._insert(r - i)
        self._insert(r)
        while True:
            if self.ml > length:
                self.ml = length
            if self.ml <= THRESHOLD:
                self.ml = 1
                code[0] |= mask
                code[cp] = tb[r]; cp += 1
            else:
                code[cp] = self.mp & 0xFF; cp += 1
                code[cp] = (((self.mp >> 4) & 0xF0) | (self.ml - THRESHOLD - 1)) & 0xFF
                cp += 1
            mask = (mask << 1) & 0xFF
            if not mask:
                self.out += code[:cp]
                code[0], cp, mask = 0, 1, 1
            last = self.ml
            i = 0
            while i < last:
                c = self._get()
                if c < 0:
                    break
                self._delete(s)
                tb[s] = c
                if s < F - 1:
                    tb[s + N] = c
                s = (s + 1) & (N - 1); r = (r + 1) & (N - 1)
                self._insert(r); i += 1
            while i < last:
                i += 1
                self._delete(s)
                s = (s + 1) & (N - 1); r = (r + 1) & (N - 1)
                length -= 1
                if length:
                    self._insert(r)
            if length <= 0:
                break
        if cp > 1:
            self.out += code[:cp]
        return bytes(self.out)


def _compress_py(raw: bytes) -> bytes:
    cc = bytearray(HDR) + _Enc(raw).run()
    cc[0x14:0x18] = len(raw).to_bytes(4, "little")
    return bytes(cc)


_exe_ok = None


def exe_available():
    global _exe_ok
    if _exe_ok is None:
        _exe_ok = False
        if os.path.exists(C.LZSS_EXE):
            with tempfile.TemporaryDirectory() as td:
                a, b = os.path.join(td, "a"), os.path.join(td, "b")
                open(a, "wb").write(b"XENON" * 64)
                try:
                    subprocess.run([C.LZSS_EXE, "e", a, b], capture_output=True, timeout=20)
                    _exe_ok = os.path.exists(b) and os.path.getsize(b) > HDR
                except OSError:
                    _exe_ok = False
    return _exe_ok


def compress(raw: bytes, prefer_exe=True) -> bytes:
    if prefer_exe and exe_available():
        with tempfile.TemporaryDirectory() as td:
            a, b = os.path.join(td, "in.bin"), os.path.join(td, "out.bin")
            open(a, "wb").write(raw)
            subprocess.run([C.LZSS_EXE, "e", a, b], capture_output=True, timeout=120)
            return open(b, "rb").read()
    return _compress_py(raw)


if __name__ == "__main__":
    print("xenon_lzss.exe 사용 가능:", exe_available())
    # 원본으로 자기검사
    import glob
    ok = 0
    files = sorted(glob.glob(os.path.join(C.SCRIPTS_CC, "*.U.CC")))
    for f in files:
        cc = f[:-5] + ".CC"
        if decompress(open(cc, "rb").read()) == open(f, "rb").read():
            ok += 1
    print(f"자기검사(해제): {ok}/{len(files)} 일치")
