#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DA1 (ANNEX library, Anazawa / TOKUMA SHOTEN INTERMEDIA) graphics decoder.

Target: XENON (PC-9801, 1993) -- gfx/raw/*.GDT whose magic is "DA1\\0".

Reconstructed from AGS.EXE segment 0x1456 (hand-written ASM module inside a
Borland C++ 1991 16-bit MZ image).  See tools/../doc or decoder_report.md.

Public API
----------
    parse_header(data)               -> dict
    decode(data)                     -> (pixels, w_px, h, palette)
    decode_full(data)                -> dict  (planes, mask, geometry, stats)
    palette_rgb(pal24, order='GRB')  -> [(r,g,b)] * 16

`pixels` is a bytes object of length w_px*h holding 4-bit colour indices
(one index per byte), row-major, top-left of the *sprite rectangle*.
`palette` is None when the file carries no palette (flags bit15 clear).

CLI
---
    py da1.py info    <file.GDT>...
    py da1.py verify  <dir-or-files>...        # exhaustive self-check
    py da1.py png     <out-dir> <file.GDT>...  # needs Pillow
"""

import glob
import os
import struct
import sys

MAGIC = b"DA1\0"
STRIDE = 80          # bytes per scanline per plane on PC-98 (640 px / 8)
VRAM_H = 400         # scanlines
VRAM_SZ = STRIDE * VRAM_H

# plane index -> colour bit.  plane0=B(bit0) A800, 1=R(bit1) B000,
# 2=G(bit2) B800, 3=I(bit3) E000
PLANE_BIT = (1, 2, 4, 8)


class Da1Error(Exception):
    pass


# ---------------------------------------------------------------- header

def parse_header(data):
    """Parse the fixed header.  Raises Da1Error on anything inconsistent."""
    if len(data) < 24 or data[0:4] != MAGIC:
        raise Da1Error("bad magic")
    size, = struct.unpack_from("<I", data, 4)
    x = data[8]                                  # left, in byte-columns
    w = data[9]                                  # width, in byte-columns
    y, h, flags = struct.unpack_from("<HHH", data, 10)

    p = 16
    pal = None
    if flags & 0x8000:
        if len(data) < p + 24:
            raise Da1Error("truncated palette")
        pal = bytes(data[p:p + 24])
        p += 24
    if len(data) < p + 8:
        raise Da1Error("truncated plane size table")
    sizes = struct.unpack_from("<4H", data, p)
    p += 8

    streams = []
    off = p
    for s in sizes:
        streams.append((off, off + s))
        off += s

    return {
        "size": size,                 # u32 file size field
        "x": x, "w": w,               # byte-columns
        "y": y, "h": h,               # scanlines
        "x_px": x * 8, "w_px": w * 8,
        "flags": flags,
        "byte_mode": bool(flags & 0x4000),
        "has_palette": bool(flags & 0x8000),
        "palette_raw": pal,
        "plane_sizes": sizes,
        "streams": streams,
        "data_end": off,
        "file_len": len(data),
    }


def palette_rgb(pal24, order="GRB"):
    """24 bytes -> 16 (r,g,b) tuples.  4-bit components scaled by 0x11."""
    if pal24 is None:
        return None
    nib = []
    for b in pal24:
        nib.append(b >> 4)
        nib.append(b & 0x0F)
    out = []
    for i in range(16):
        c = nib[3 * i:3 * i + 3]
        d = dict(zip(order, c))
        out.append((d["R"] * 0x11, d["G"] * 0x11, d["B"] * 0x11))
    return out


# ---------------------------------------------------------------- decoder

def _ror8(v, n):
    return ((v >> n) | (v << (8 - n))) & 0xFF


def decode_full(data, strict=True, opcount=None):
    """Decompress all four planes.

    Emulates the original renderer literally: four 80x400 VRAM planes, the
    sprite drawn at (x, y).  Back-references (opcodes A0..EF) address VRAM,
    so this geometry must be preserved even though every observed file is
    self-contained inside its own rectangle.

    strict=True enables the invariants used for verification:
        * every column must advance exactly h*STRIDE
        * every plane stream must be consumed to the byte
        * no write may leave the declared rectangle
    """
    m = parse_header(data)
    x, w, y, h = m["x"], m["w"], m["y"], m["h"]

    if not m["byte_mode"]:
        raise Da1Error("word-mode stream (flags bit14 clear) not implemented")
    if x + w > STRIDE or y + h > VRAM_H:
        raise Da1Error("rectangle %d,%d %dx%d outside 80x400" % (x, y, w, h))

    planes = [bytearray(VRAM_SZ) for _ in range(4)]
    mask = bytearray(VRAM_SZ)             # 1 where any plane was written
    cur = [s[0] for s in m["streams"]]
    lim = [s[1] for s in m["streams"]]

    lo_lim = y * STRIDE + x               # inclusive lower bound of the rect
    hi_lim = (y + h - 1) * STRIDE + x + w  # exclusive upper bound

    oob = []           # out-of-rectangle reads/writes seen (should stay empty)
    col_adv = []

    for c in range(w):
        di0 = lo_lim + c
        for pi in range(4):
            es = planes[pi]
            si = cur[pi]
            end = lim[pi]
            di = di0

            # NB: the emit(v) primitive (es[di]=v; di+=STRIDE) is inlined
            # everywhere below -- a helper call costs ~2x over 900k opcodes.
            while True:
                if si >= end:
                    raise Da1Error("stream %d overran (col %d)" % (pi, c))
                op = data[si]
                si += 1
                if opcount is not None:
                    opcount[op] = opcount.get(op, 0) + 1

                if op == 0xFF:                       # end of column
                    break

                elif op < 0x20:                      # run of 0x00
                    n = op
                    if n == 0:
                        n = data[si]; si += 1
                    for _ in range(n):
                        es[di] = 0x00; mask[di] = 1; di += STRIDE

                elif op < 0x40:                      # run of 0xFF
                    n = op & 0x1F
                    if n == 0:
                        n = data[si]; si += 1
                    for _ in range(n):
                        es[di] = 0xFF; mask[di] = 1; di += STRIDE

                elif op < 0xA0:                      # copy plane 0/1/2
                    src = planes[(op >> 5) - 2]      # 0x40->0, 0x60->1, 0x80->2
                    n = op & 0x1F
                    if n == 0:
                        n = data[si]; si += 1
                    for _ in range(n):
                        es[di] = src[di]; mask[di] = 1; di += STRIDE

                elif op < 0xF0:                      # copy earlier VRAM, same plane
                    delta = (-1280, -640, -320, -160, -2)[(op >> 4) - 0x0A]
                    n = op & 0x0F
                    if n == 0:
                        n = data[si]; si += 1
                    for _ in range(n):
                        s = di + delta
                        if not (y <= s // STRIDE < y + h
                                and x <= s % STRIDE < x + w):
                            oob.append((c, pi, op, s))
                        es[di] = es[s]; mask[di] = 1; di += STRIDE

                elif op <= 0xF8:                     # literal bytes
                    if op == 0xF0:
                        n = data[si]; si += 1
                    else:
                        n = op - 0xF0
                    for _ in range(n):
                        es[di] = data[si]; si += 1
                        mask[di] = 1; di += STRIDE

                elif op == 0xF9:                     # skip = transparent
                    di += data[si] * STRIDE; si += 1

                elif op == 0xFA:                     # run of arbitrary byte
                    n = data[si]; v = data[si + 1]; si += 2
                    for _ in range(n):
                        es[di] = v; mask[di] = 1; di += STRIDE

                elif op == 0xFB:                     # NOT plane0 / NOT plane1
                    k = data[si]; si += 1
                    src = planes[0] if k < 0x80 else planes[1]
                    for _ in range(k & 0x7F):
                        es[di] = src[di] ^ 0xFF; mask[di] = 1; di += STRIDE

                elif op == 0xFC:
                    k = data[si]; si += 1
                    if k < 0x80:                     # NOT plane2
                        src = planes[2]
                        for _ in range(k & 0x7F):
                            es[di] = src[di] ^ 0xFF; mask[di] = 1; di += STRIDE
                    else:                            # 2-row nibble mesh
                        n = k & 0x7F
                        b = data[si]; si += 1
                        r0 = (b & 0x0F) * 0x11
                        r1 = (b >> 4) * 0x11
                        for _ in range(n):
                            es[di] = r0; mask[di] = 1
                            es[di + 80] = r1; mask[di + 80] = 1
                            di += 160

                elif op == 0xFD:
                    k = data[si]; si += 1
                    if k < 0x80:                     # 2-row literal pattern
                        n = k
                        b0 = data[si]; b1 = data[si + 1]; si += 2
                        for _ in range(n):
                            es[di] = b0; mask[di] = 1
                            es[di + 80] = b1; mask[di + 80] = 1
                            di += 160
                    else:
                        n = k & 0x3F
                        if k < 0xC0:                 # 4-row mesh, rows 3/4 = ror2
                            b = data[si]; si += 1
                            r0 = (b & 0x0F) * 0x11
                            r1 = (b >> 4) * 0x11
                            r2 = _ror8(r0, 2)
                            r3 = _ror8(r1, 2)
                        else:                        # 4-row mesh, four nibbles
                            b0 = data[si]; b1 = data[si + 1]; si += 2
                            r0 = (b0 & 0x0F) * 0x11
                            r1 = (b0 >> 4) * 0x11
                            r2 = (b1 & 0x0F) * 0x11
                            r3 = (b1 >> 4) * 0x11
                        for _ in range(n):
                            es[di] = r0; mask[di] = 1
                            es[di + 80] = r1; mask[di + 80] = 1
                            es[di + 160] = r2; mask[di + 160] = 1
                            es[di + 240] = r3; mask[di + 240] = 1
                            di += 320

                elif op == 0xFE:
                    k = data[si]; si += 1
                    if k < 0x40:                     # 4-row literal pattern
                        n = k
                        b0, b1, b2, b3 = data[si:si + 4]; si += 4
                        for _ in range(n):
                            es[di] = b0; mask[di] = 1
                            es[di + 80] = b1; mask[di + 80] = 1
                            es[di + 160] = b2; mask[di + 160] = 1
                            es[di + 240] = b3; mask[di + 240] = 1
                            di += 320
                    else:                            # AND of two planes
                        ia, ib = {0x40: (0, 1), 0x80: (0, 2),
                                  0xC0: (1, 2)}[k & 0xC0]
                        pa = planes[ia]; pb = planes[ib]
                        for _ in range(k & 0x3F):
                            es[di] = pa[di] & pb[di]; mask[di] = 1; di += STRIDE

                else:
                    raise Da1Error("unreachable opcode %02X" % op)

            adv = di - di0
            col_adv.append(adv)
            if strict and adv != h * STRIDE:
                raise Da1Error("col %d plane %d advanced %d, expected %d"
                               % (c, pi, adv, h * STRIDE))
            cur[pi] = si

    if strict:
        for pi in range(4):
            if cur[pi] != lim[pi]:
                raise Da1Error("plane %d stream left %d bytes unconsumed"
                               % (pi, lim[pi] - cur[pi]))
        if oob:
            raise Da1Error("%d back-references left the rectangle, first=%r"
                           % (len(oob), oob[0]))

    m["planes"] = planes
    m["mask"] = mask
    m["consumed"] = cur
    m["columns"] = len(col_adv)
    m["oob"] = oob
    m["raw_bytes"] = w * h * 4        # (w_px/8)*h*4
    return m


def _compose(m):
    """planes -> per-pixel 4-bit indices, cropped to the rectangle."""
    x, w, y, h = m["x"], m["w"], m["y"], m["h"]
    planes = m["planes"]
    out = bytearray(w * 8 * h)
    o = 0
    for row in range(h):
        base = (y + row) * STRIDE + x
        for cb in range(w):
            off = base + cb
            b0 = planes[0][off]; b1 = planes[1][off]
            b2 = planes[2][off]; b3 = planes[3][off]
            for bit in range(7, -1, -1):
                out[o] = (((b0 >> bit) & 1)
                          | (((b1 >> bit) & 1) << 1)
                          | (((b2 >> bit) & 1) << 2)
                          | (((b3 >> bit) & 1) << 3))
                o += 1
    return bytes(out)


def alpha_mask(m):
    """1 byte per pixel: 0 = never written (transparent), 255 = opaque."""
    x, w, y, h = m["x"], m["w"], m["y"], m["h"]
    mask = m["mask"]
    out = bytearray(w * 8 * h)
    o = 0
    for row in range(h):
        base = (y + row) * STRIDE + x
        for cb in range(w):
            v = 255 if mask[base + cb] else 0
            for _ in range(8):
                out[o] = v
                o += 1
    return bytes(out)


def decode(data, order="GRB"):
    """decode(data) -> (pixels, w_px, h, palette)"""
    m = decode_full(data)
    return (_compose(m), m["w"] * 8, m["h"],
            palette_rgb(m["palette_raw"], order))


# ---------------------------------------------------------------- CLI

def _iter_files(args):
    for a in args:
        if os.path.isdir(a):
            for f in sorted(glob.glob(os.path.join(a, "*"))):
                if os.path.isfile(f):
                    yield f
        else:
            for f in sorted(glob.glob(a)):
                yield f


def _cmd_info(args):
    for f in _iter_files(args):
        d = open(f, "rb").read()
        if d[:4] != MAGIC:
            continue
        m = parse_header(d)
        print("%-14s x=%2d w=%2d (%4dpx) y=%3d h=%3d flags=%04X pal=%d "
              "planes=%s tail=%d"
              % (os.path.basename(f), m["x"], m["w"], m["w_px"], m["y"],
                 m["h"], m["flags"], m["has_palette"], list(m["plane_sizes"]),
                 m["file_len"] - m["data_end"]))


def _cmd_verify(args):
    ok = 0
    n = 0
    fails = []
    opcount = {}
    total_raw = 0
    transparent = 0
    for f in _iter_files(args):
        d = open(f, "rb").read()
        if d[:4] != MAGIC:
            continue
        n += 1
        name = os.path.basename(f)
        try:
            m = decode_full(d, strict=True, opcount=opcount)
            problems = []
            if m["size"] != len(d):
                problems.append("size field %d != %d" % (m["size"], len(d)))
            if m["data_end"] != len(d):
                problems.append("layout end %d != EOF %d"
                                % (m["data_end"], len(d)))
            if m["columns"] != m["w"] * 4:
                problems.append("columns %d != w*4 %d"
                                % (m["columns"], m["w"] * 4))
            px = _compose(m)
            if len(px) != m["w"] * 8 * m["h"]:
                problems.append("pixel count mismatch")
            if problems:
                fails.append((name, "; ".join(problems)))
            else:
                ok += 1
                total_raw += m["raw_bytes"]
                if 0 in m["mask"][m["y"] * STRIDE + m["x"]:]:
                    pass
                if any(m["mask"][(m["y"] + r) * STRIDE + m["x"] + c] == 0
                       for r in range(m["h"]) for c in range(m["w"])):
                    transparent += 1
        except Exception as e:
            fails.append((name, "%s: %s" % (type(e).__name__, e)))
    print("DA1 files      : %d" % n)
    print("fully verified : %d  (%.2f%%)" % (ok, 100.0 * ok / n if n else 0))
    print("failed         : %d" % len(fails))
    for name, why in fails:
        print("   FAIL %-16s %s" % (name, why))
    print("decompressed   : %d bytes total (sum of w*h*4)" % total_raw)
    print("with transparent pixels: %d" % transparent)
    print("distinct opcodes seen  : %d / 256   (total %d)"
          % (len(opcount), sum(opcount.values())))
    return 0 if not fails else 1


def _sibling_palette(path):
    """Overlay patches (flags 0x4F00) carry no palette: they reuse whatever the
    previously drawn base image installed.  Guess the base by stripping the
    usual suffixes, e.g. 1010B_M.GDT / 1010B.GDT -> 1010.GDT."""
    d, base = os.path.split(path)
    stem, ext = os.path.splitext(base)
    for suf in ("_M", "_B", "BB", "B", "C", "_2", "_3"):
        while stem.endswith(suf) and len(stem) > len(suf):
            cand = os.path.join(d, stem[:-len(suf)] + ext)
            if os.path.isfile(cand):
                try:
                    h = parse_header(open(cand, "rb").read())
                    if h["palette_raw"]:
                        return h["palette_raw"], os.path.basename(cand)
                except Da1Error:
                    pass
            stem = stem[:-len(suf)]
    return None, None


def _cmd_png(args):
    from PIL import Image
    outdir = args[0]
    os.makedirs(outdir, exist_ok=True)
    for f in _iter_files(args[1:]):
        d = open(f, "rb").read()
        if d[:4] != MAGIC:
            continue
        m = decode_full(d)
        px = _compose(m)
        w, h = m["w"] * 8, m["h"]
        raw = m["palette_raw"]
        note = "pal"
        if raw is None:
            raw, src = _sibling_palette(f)
            note = ("pal<%s" % src) if raw else "grey"
        pal = palette_rgb(raw, "GRB")
        img = Image.new("RGBA", (w, h))
        if pal:
            lut = [pal[i] for i in range(16)]
        else:
            lut = [(i * 17,) * 3 for i in range(16)]     # greyscale fallback
        am = alpha_mask(m)
        img.putdata([(lut[v][0], lut[v][1], lut[v][2], am[i])
                     for i, v in enumerate(px)])
        out = os.path.join(outdir, os.path.basename(f).replace(".", "_") + ".png")
        img.save(out)
        print(out, "%dx%d" % (w, h), note)


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    cmd = argv[1]
    if cmd == "info":
        return _cmd_info(argv[2:]) or 0
    if cmd == "verify":
        return _cmd_verify(argv[2:])
    if cmd == "png":
        return _cmd_png(argv[2:]) or 0
    print("unknown command", cmd)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
