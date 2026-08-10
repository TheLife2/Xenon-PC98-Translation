#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DA1 word-mode (flags bit14 = 0) decoder.

AGS.EXE 의 압축 해제 루틴을 그대로 옮긴 것이다 (추측 아님).
로드 모듈(= AGS.EXE[3584:]) 기준 코드 세그먼트 베이스 0x4560.

  0x4680  컬럼 분배기 : x(=di) 홀짝 / w 홀짝으로 바이트컬럼·워드컬럼을 섞는다
  0x46bc  flags & 0x4000 검사 -> 세워졌으면 바이트모드(0x7e05), 아니면 워드모드
  0x83c4  워드모드 진입 직전 **평면 4개의 스트림 포인터를 짝수로 올림** (핵심)
  0x47a7  워드모드 디스패치 : lodsw -> al=피연산자, ah=opcode, 점프테이블 cs:0x258

바이트모드와의 차이
  * 스트림을 **워드 단위**로 읽는다. 낮은 바이트가 피연산자, **높은 바이트가 opcode**.
  * emit 이 16비트다. 즉 한 컬럼이 가로 2바이트를 덮는다. 컬럼 수 = w>>1.
  * w 나 x 가 홀수면 남는 1바이트 컬럼을 **바이트모드 디코더로** 처리한다.
    (이것이 "컬럼 수 = w/2" 가설이 전부 실패한 이유다)
"""

import struct

STRIDE = 80
VRAM_H = 400
VRAM_SZ = STRIDE * VRAM_H
PAD = 2048                      # 양의 델타(+638 등) 참조가 배열을 넘지 않도록

MAGIC = b"DA1\0"


class Da1Error(Exception):
    pass


# opcode 0xD3..0xF2 : 같은 평면 VRAM 역/순참조 델타 (AGS.EXE 에서 그대로 추출)
BACKREF = {
    0xD3: -1280, 0xD4: -960, 0xD5: -640, 0xD6: -320, 0xD7: -160, 0xD8: -80,
    0xD9: -642, 0xDA: -322, 0xDB: -162, 0xDC: -82, 0xDD: -2,
    0xDE: 78, 0xDF: 158, 0xE0: 318, 0xE1: 638,
    0xE2: -644, 0xE3: -324, 0xE4: -164, 0xE5: -84, 0xE6: -4,
    0xE7: 76, 0xE8: 156, 0xE9: 316, 0xEA: 636,
    0xEB: -326, 0xEC: -166, 0xED: -86, 0xEE: -6,
    0xEF: 74, 0xF0: 154, 0xF1: 314, 0xF2: -8,
}
PLANE_COPY = {0xF3: 0, 0xF4: 1, 0xF5: 2}          # 다른 평면에서 그대로 복사
PLANE_NOT = {0xF6: 0, 0xF7: 1, 0xF8: 2}           # 다른 평면의 NOT
PLANE_AND = {0xF9: (0, 1), 0xFA: (0, 2), 0xFB: (1, 2)}


def _rep(b):
    return (b << 8) | b


def _ror16(v, n):
    return ((v >> n) | (v << (16 - n))) & 0xFFFF


def parse_header(data):
    if len(data) < 24 or data[0:4] != MAGIC:
        raise Da1Error("bad magic")
    size, = struct.unpack_from("<I", data, 4)
    x = data[8]
    w = data[9]
    y, h, flags = struct.unpack_from("<HHH", data, 10)
    p = 16
    pal = None
    if flags & 0x8000:
        pal = bytes(data[p:p + 24]); p += 24
    sizes = struct.unpack_from("<4H", data, p); p += 8
    streams = []
    off = p
    for s in sizes:
        streams.append((off, off + s)); off += s
    return dict(size=size, x=x, w=w, y=y, h=h, flags=flags,
                byte_mode=bool(flags & 0x4000), has_palette=bool(flags & 0x8000),
                palette_raw=pal, plane_sizes=sizes, streams=streams,
                data_end=off, file_len=len(data))


# --------------------------------------------------------------- 워드 컬럼
def _word_column(data, si, end, plane, planes, mask, di, trace=None):
    """0x47a0 한 번 = 평면 하나의 워드 컬럼 하나. (새 si, 최종 di) 반환."""
    while True:
        if si + 2 > end:
            raise Da1Error("word stream overrun")
        n = data[si]
        op = data[si + 1]
        si += 2
        if trace is not None:
            trace[op] = trace.get(op, 0) + 1

        if op == 0xFF:                                   # 컬럼 끝 (ret)
            return si, di

        if op < 0x80:                                    # 2행 니블 메시, 반복 op회
            lo = (n & 0x0F) * 0x11
            hi = (n >> 4) * 0x11
            r0, r1 = _rep(lo), _rep(hi)
            for _ in range(op):
                planes[plane][di] = r0 & 0xFF; planes[plane][di + 1] = r0 >> 8
                planes[plane][di + 80] = r1 & 0xFF; planes[plane][di + 81] = r1 >> 8
                mask[di] = mask[di + 1] = mask[di + 80] = mask[di + 81] = 1
                di += 160

        elif op < 0xC0:                                  # 4행 니블 메시 (+ror2)
            lo = (n & 0x0F) * 0x11
            hi = (n >> 4) * 0x11
            r0, r1 = _rep(lo), _rep(hi)
            r2, r3 = _ror16(r0, 2), _ror16(r1, 2)
            for _ in range(op & 0x3F):
                for k, v in ((0, r0), (80, r1), (160, r2), (240, r3)):
                    planes[plane][di + k] = v & 0xFF
                    planes[plane][di + k + 1] = v >> 8
                    mask[di + k] = mask[di + k + 1] = 1
                di += 320

        elif op < 0xD0:                                  # 균일 워드 (opcode 니블)
            v = _rep((op & 0x0F) * 0x11)
            for _ in range(n):
                planes[plane][di] = v & 0xFF; planes[plane][di + 1] = v >> 8
                mask[di] = mask[di + 1] = 1
                di += 80

        elif op < 0xD2:                                  # 리터럴 워드 n개 (9비트 카운트)
            cnt = ((op << 8) | n) & 0x1FF
            for _ in range(cnt):
                if si + 2 > end:
                    raise Da1Error("literal overrun")
                planes[plane][di] = data[si]; planes[plane][di + 1] = data[si + 1]
                mask[di] = mask[di + 1] = 1
                si += 2; di += 80

        elif op == 0xD2:                                 # 투명 스킵 n행
            di += 80 * n

        elif op in BACKREF:                              # 같은 평면 VRAM 참조
            src = di + BACKREF[op]
            es = planes[plane]
            for _ in range(n):
                es[di] = es[src]; es[di + 1] = es[src + 1]
                mask[di] = mask[di + 1] = 1
                src += 80; di += 80

        elif op in PLANE_COPY:                           # 다른 평면 복사
            sp = planes[PLANE_COPY[op]]
            es = planes[plane]
            src = di
            for _ in range(n):
                es[di] = sp[src]; es[di + 1] = sp[src + 1]
                mask[di] = mask[di + 1] = 1
                src += 80; di += 80

        elif op in PLANE_NOT:                            # 다른 평면의 NOT
            sp = planes[PLANE_NOT[op]]
            es = planes[plane]
            for _ in range(n):
                es[di] = sp[di] ^ 0xFF; es[di + 1] = sp[di + 1] ^ 0xFF
                mask[di] = mask[di + 1] = 1
                di += 80

        elif op in PLANE_AND:                            # 두 평면의 AND
            ia, ib = PLANE_AND[op]
            pa, pb = planes[ia], planes[ib]
            es = planes[plane]
            for _ in range(n):
                es[di] = pa[di] & pb[di]; es[di + 1] = pa[di + 1] & pb[di + 1]
                mask[di] = mask[di + 1] = 1
                di += 80

        elif op == 0xFC:                                 # 임의 워드 런
            if si + 2 > end:
                raise Da1Error("FC operand overrun")
            v0, v1 = data[si], data[si + 1]; si += 2
            for _ in range(n):
                planes[plane][di] = v0; planes[plane][di + 1] = v1
                mask[di] = mask[di + 1] = 1
                di += 80

        elif op == 0xFD:                                 # 2행 패턴
            if n < 0x80:                                 # 바이트 2개를 각각 확장
                b0, b1 = data[si], data[si + 1]; si += 2
                rows = (_rep(b0), _rep(b1))
                cnt = n
            else:                                        # 워드 2개 그대로
                rows = (data[si] | (data[si + 1] << 8),
                        data[si + 2] | (data[si + 3] << 8))
                si += 4
                cnt = n & 0x7F
            for _ in range(cnt):
                for k, v in ((0, rows[0]), (80, rows[1])):
                    planes[plane][di + k] = v & 0xFF
                    planes[plane][di + k + 1] = v >> 8
                    mask[di + k] = mask[di + k + 1] = 1
                di += 160

        elif op == 0xFE:                                 # 4행 패턴 (4갈래)
            if n < 0x40:
                # AGS.EXE 0x4abe 를 그대로 옮긴 것. b1/b2 를 버리는 기묘한 조합이지만
                # 바이너리가 이렇게 한다.
                b0, b1 = data[si], data[si + 1]
                b2, b3 = data[si + 2], data[si + 3]; si += 4
                r0 = _rep(b0)
                r2 = (_ror16(_rep(b0), 4) & 0xFF00) | b3
                r1 = _rep(b3)
                r3 = _ror16(b2 | (b3 << 8), 4)
                rows = (r0, r1, r2, r3)
                cnt = n
            elif n < 0x80:                               # 니블 4개
                b0, b1 = data[si], data[si + 1]; si += 2
                rows = (_rep((b0 & 0x0F) * 0x11), _rep((b0 >> 4) * 0x11),
                        _rep((b1 & 0x0F) * 0x11), _rep((b1 >> 4) * 0x11))
                cnt = n & 0x3F
            elif n < 0xC0:                               # 바이트 4개
                b = data[si:si + 4]; si += 4
                rows = (_rep(b[0]), _rep(b[1]), _rep(b[2]), _rep(b[3]))
                cnt = n & 0x3F
            else:                                        # 워드 4개
                rows = tuple(data[si + 2 * k] | (data[si + 2 * k + 1] << 8)
                             for k in range(4))
                si += 8
                cnt = n & 0x3F
            for _ in range(cnt):
                for k, v in ((0, rows[0]), (80, rows[1]),
                             (160, rows[2]), (240, rows[3])):
                    planes[plane][di + k] = v & 0xFF
                    planes[plane][di + k + 1] = v >> 8
                    mask[di + k] = mask[di + k + 1] = 1
                di += 320

        else:
            raise Da1Error("unreachable word opcode %02X" % op)


# --------------------------------------------------------------- 바이트 컬럼
def _byte_column(data, si, end, plane, planes, mask, di, trace=None):
    """0x7e4a 한 번 = 평면 하나의 바이트 컬럼 하나 (기존 da1.py 와 동일한 표)."""
    es = planes[plane]
    while True:
        if si >= end:
            raise Da1Error("byte stream overrun")
        op = data[si]; si += 1
        if trace is not None:
            trace[('b', op)] = trace.get(('b', op), 0) + 1

        if op == 0xFF:
            return si, di
        elif op < 0x20:
            n = op
            if n == 0:
                n = data[si]; si += 1
            for _ in range(n):
                es[di] = 0x00; mask[di] = 1; di += STRIDE
        elif op < 0x40:
            n = op & 0x1F
            if n == 0:
                n = data[si]; si += 1
            for _ in range(n):
                es[di] = 0xFF; mask[di] = 1; di += STRIDE
        elif op < 0xA0:
            src = planes[(op >> 5) - 2]
            n = op & 0x1F
            if n == 0:
                n = data[si]; si += 1
            for _ in range(n):
                es[di] = src[di]; mask[di] = 1; di += STRIDE
        elif op < 0xF0:
            delta = (-1280, -640, -320, -160, -2)[(op >> 4) - 0x0A]
            n = op & 0x0F
            if n == 0:
                n = data[si]; si += 1
            for _ in range(n):
                es[di] = es[di + delta]; mask[di] = 1; di += STRIDE
        elif op <= 0xF8:
            n = data[si] if op == 0xF0 else op - 0xF0
            if op == 0xF0:
                si += 1
            for _ in range(n):
                es[di] = data[si]; si += 1; mask[di] = 1; di += STRIDE
        elif op == 0xF9:
            di += data[si] * STRIDE; si += 1
        elif op == 0xFA:
            n = data[si]; v = data[si + 1]; si += 2
            for _ in range(n):
                es[di] = v; mask[di] = 1; di += STRIDE
        elif op == 0xFB:
            k = data[si]; si += 1
            src = planes[0] if k < 0x80 else planes[1]
            for _ in range(k & 0x7F):
                es[di] = src[di] ^ 0xFF; mask[di] = 1; di += STRIDE
        elif op == 0xFC:
            k = data[si]; si += 1
            if k < 0x80:
                src = planes[2]
                for _ in range(k & 0x7F):
                    es[di] = src[di] ^ 0xFF; mask[di] = 1; di += STRIDE
            else:
                n = k & 0x7F
                b = data[si]; si += 1
                r0 = (b & 0x0F) * 0x11; r1 = (b >> 4) * 0x11
                for _ in range(n):
                    es[di] = r0; mask[di] = 1
                    es[di + 80] = r1; mask[di + 80] = 1
                    di += 160
        elif op == 0xFD:
            k = data[si]; si += 1
            if k < 0x80:
                b0, b1 = data[si], data[si + 1]; si += 2
                for _ in range(k):
                    es[di] = b0; mask[di] = 1
                    es[di + 80] = b1; mask[di + 80] = 1
                    di += 160
            else:
                n = k & 0x3F
                if k < 0xC0:
                    b = data[si]; si += 1
                    r0 = (b & 0x0F) * 0x11; r1 = (b >> 4) * 0x11
                    r2 = ((r0 >> 2) | (r0 << 6)) & 0xFF
                    r3 = ((r1 >> 2) | (r1 << 6)) & 0xFF
                else:
                    b0, b1 = data[si], data[si + 1]; si += 2
                    r0 = (b0 & 0x0F) * 0x11; r1 = (b0 >> 4) * 0x11
                    r2 = (b1 & 0x0F) * 0x11; r3 = (b1 >> 4) * 0x11
                for _ in range(n):
                    for k2, v in ((0, r0), (80, r1), (160, r2), (240, r3)):
                        es[di + k2] = v; mask[di + k2] = 1
                    di += 320
        elif op == 0xFE:
            k = data[si]; si += 1
            if k < 0x40:
                b = data[si:si + 4]; si += 4
                for _ in range(k):
                    for k2 in range(4):
                        es[di + 80 * k2] = b[k2]; mask[di + 80 * k2] = 1
                    di += 320
            else:
                ia, ib = {0x40: (0, 1), 0x80: (0, 2), 0xC0: (1, 2)}[k & 0xC0]
                pa, pb = planes[ia], planes[ib]
                for _ in range(k & 0x3F):
                    es[di] = pa[di] & pb[di]; mask[di] = 1; di += STRIDE
        else:
            raise Da1Error("unreachable byte opcode %02X" % op)


# --------------------------------------------------------------- 본체
def decode_full(data, strict=True, trace=None, planes=None, mask=None):
    """planes/mask 를 넘기면 **그 VRAM 위에 이어서 그린다.**

    ADT 차분 프레임은 이전 프레임이 남긴 화면을 역참조한다(D8 = 한 행 위 등).
    프레임마다 빈 VRAM 으로 시작하면 그 참조가 0 을 읽어 가로 줄무늬가 생긴다.
    애니메이션을 재현하려면 VRAM 한 벌을 유지하며 순서대로 넘겨야 한다.
    """
    m = parse_header(data)
    x, w, y, h = m["x"], m["w"], m["y"], m["h"]
    if x + w > STRIDE or y + h > VRAM_H:
        raise Da1Error("rect outside 80x400")

    if planes is None:
        planes = [bytearray(VRAM_SZ + PAD) for _ in range(4)]
    if mask is None:
        mask = bytearray(VRAM_SZ + PAD)
    si = [s[0] for s in m["streams"]]
    end = [s[1] for s in m["streams"]]

    di0 = y * STRIDE + x
    ncol = w >> 1                                    # cs:[0xd4]
    word_mode = not (m["flags"] & 0x4000)
    advances = []

    def byte_col(d):
        for p in range(4):
            s2, dend = _byte_column(data, si[p], end[p], p, planes, mask, d, trace)
            advances.append(dend - d)
            si[p] = s2

    def align():
        # 0x83c4 -> 0x8409 : 평면별 스트림 오프셋을 짝수로 올린다
        for p in range(4):
            if si[p] & 1:
                si[p] += 1

    def word_cols(d, cnt):
        if cnt == 0:
            return d
        if word_mode:
            align()
            for _ in range(cnt):
                for p in range(4):
                    s2, dend = _word_column(data, si[p], end[p], p,
                                            planes, mask, d, trace)
                    advances.append(dend - d)
                    si[p] = s2
                d += 2
        else:
            for _ in range(cnt):
                byte_col(d); d += 1
                byte_col(d); d += 1
        return d

    d = di0
    if di0 & 1:
        if w & 1:                                    # 0x46b0
            byte_col(d); d += 1
            d = word_cols(d, ncol)
        else:                                        # 0x4698
            ncol -= 1
            byte_col(d); d += 1
            d = word_cols(d, ncol)
            byte_col(d); d += 1
    else:
        if w & 1:                                    # 0x4691
            d = word_cols(d, ncol)
            byte_col(d); d += 1
        else:                                        # 0x468d
            d = word_cols(d, ncol)

    if strict:
        if d != di0 + w:
            raise Da1Error("column cursor %d, expected %d" % (d - di0, w))
        bad = [a for a in advances if a != h * STRIDE]
        if bad:
            raise Da1Error("%d/%d columns advanced wrong (first %d, want %d)"
                           % (len(bad), len(advances), bad[0], h * STRIDE))
        for p in range(4):
            if si[p] != end[p]:
                raise Da1Error("plane %d left %d bytes" % (p, end[p] - si[p]))

    m["planes"] = planes
    m["mask"] = mask
    m["columns"] = len(advances)
    m["consumed"] = si
    return m


def compose(m):
    x, w, y, h = m["x"], m["w"], m["y"], m["h"]
    pl = m["planes"]
    out = bytearray(w * 8 * h)
    o = 0
    for row in range(h):
        base = (y + row) * STRIDE + x
        for cb in range(w):
            off = base + cb
            b0, b1, b2, b3 = pl[0][off], pl[1][off], pl[2][off], pl[3][off]
            for bit in range(7, -1, -1):
                out[o] = (((b0 >> bit) & 1) | (((b1 >> bit) & 1) << 1)
                          | (((b2 >> bit) & 1) << 2) | (((b3 >> bit) & 1) << 3))
                o += 1
    return bytes(out)


def alpha_mask(m):
    x, w, y, h = m["x"], m["w"], m["y"], m["h"]
    mk = m["mask"]
    out = bytearray(w * 8 * h)
    o = 0
    for row in range(h):
        base = (y + row) * STRIDE + x
        for cb in range(w):
            v = 255 if mk[base + cb] else 0
            for _ in range(8):
                out[o] = v; o += 1
    return bytes(out)
