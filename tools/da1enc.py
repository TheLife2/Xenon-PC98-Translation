#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DA1 (ANNEX library) graphics *encoder* -- companion to tools/da1.py.

Produces byte-mode DA1 streams that tools/da1.py (and, by construction, the
original AGS.EXE interpreter at CS:0x38EA) decode back to exactly the pixels
that went in.

Design notes / invariants honoured (decoder_report.md section 5):
  * no opcode is ever emitted with count == 0  (the ASM handler would loop
    65536 times);  counts 1..15 / 1..31 always use the short form.
  * every column advances exactly h rows; multi-row opcodes (2-row / 4-row)
    are only used when they fit inside the remaining rows.
  * planes are emitted column-major in plane order 0,1,2,3 so that the
    cross-plane opcodes (40-9F, FB, FC<80, FE>=40) only ever read planes that
    the decoder has already produced for the *same* column.
  * back-references (A0-EF, 40-9F, FB, FC, FE) never leave the sprite
    rectangle AND never read a cell this encoder did not itself write, so the
    stored values never silently depend on what is already on screen.
  * flags / palette / x / y are carried over verbatim from the source file by
    encode_like(), so overlay patches keep working.  encode_like() also
    reproduces the original's *per-plane* transparency by default -- see
    analyse() and the `bgdeps` command for why that matters.

Known limit: 37 of the 203 XENON files are diffs against a specific base
image -- they write cells whose value they copied from a cell they never wrote,
i.e. from the screen underneath.  That value is not present in the decoded
pixels (da1.py renders it as 0), so no encoder fed only pixels can reproduce
it.  `py da1enc.py bgdeps <dir>` lists exactly which files those are.

Public API
----------
    encode(pixels, w_px, h, x, y, palette=None, alpha=None, flags=None,
           plane_skip=None, stats=None)                                -> bytes
    encode_like(orig_bytes, pixels, alpha=None, keep_plane_skip=True)  -> bytes
    analyse(orig_bytes)          -> (written[p][c][r], known[p][c][r])
    plane_row_masks(orig_bytes)  -> written[p][c][r]
    pack_palette(rgb16)                                                -> bytes(24)

`pixels` : bytes/bytearray/list of w_px*h 4-bit colour indices (row major).
`alpha`  : optional, same length, 0 == transparent.  Transparency has 8-pixel
           (one VRAM byte) granularity: a byte is skipped only when all 8 of
           its pixels are transparent.

CLI
---
    py da1enc.py roundtrip <dir-or-files>...        # decode->encode->decode
    py da1enc.py reencode  <outdir> <files>...      # write re-encoded GDTs
    py da1enc.py bgdeps    <dir-or-files>...        # who depends on the screen
    py da1enc.py frompng   [--flat] <orig.GDT> <edit.png> <out.GDT>
    py da1enc.py topng     <orig.GDT> <out.png>     # convenience (via da1.py)
"""

import glob
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import da1                                                   # noqa: E402
from da1 import Da1Error, MAGIC, STRIDE, VRAM_H               # noqa: E402


# ------------------------------------------------------------------ palette

def pack_palette(rgb16):
    """[(r,g,b)] * 16  ->  24 raw bytes (12-bit GRB, high nibble first)."""
    if len(rgb16) != 16:
        raise Da1Error("palette must have exactly 16 entries")
    nib = []
    for (r, g, b) in rgb16:                 # component order on disk is G,R,B
        nib.append((g >> 4) & 0x0F)
        nib.append((r >> 4) & 0x0F)
        nib.append((b >> 4) & 0x0F)
    out = bytearray(24)
    for k in range(24):
        out[k] = (nib[2 * k] << 4) | nib[2 * k + 1]
    return bytes(out)


def _ror8(v, n):
    return ((v >> n) | (v << (8 - n))) & 0xFF


# --------------------------------------------------- per-plane write masks

def analyse(data):
    """Structural taint analysis of an existing DA1 stream.

    Returns (written, known), both indexed [plane][column][row]:

      written[p][c][r]  the file stores something in this plane cell
                        (False == opcode F9 skipped it, so on a real PC-98 the
                        cell keeps whatever the previous screen had)
      known[p][c][r]    the stored value is fully determined by the file
                        itself.  False means the value was copied from a cell
                        the file never wrote, i.e. it is inherited from the
                        screen underneath -- the overlay is a *diff* against a
                        specific base image, not a standalone picture.

    Only opcode lengths and dataflow are needed, so no pixel values are built.
    This is what makes it possible to say honestly which files an encoder
    working from decoded pixels cannot reproduce bit-for-bit.
    """
    m = da1.parse_header(data)
    if not m["byte_mode"]:
        raise Da1Error("word-mode stream not supported")
    w, h = m["w"], m["h"]
    cur = [s[0] for s in m["streams"]]
    written = [[None] * w for _ in range(4)]
    known = [[None] * w for _ in range(4)]

    for c in range(w):
        for pi in range(4):
            si = cur[pi]
            wrow = [False] * h
            krow = [False] * h
            written[pi][c] = wrow
            known[pi][c] = krow
            r = 0

            def src_known(rr, dc, dr, plane):
                """Is the cell this opcode reads a value the file wrote?"""
                cc = c + dc
                rr2 = rr + dr
                if cc < 0 or cc >= w or rr2 < 0 or rr2 >= h:
                    return False          # outside the sprite: screen content
                kk = known[plane][cc]
                ww = written[plane][cc]
                if kk is None or ww is None:
                    return False          # column not produced yet
                return ww[rr2] and kk[rr2]

            while True:
                op = data[si]
                si += 1
                if op == 0xFF:
                    break

                nrow = 0
                write = True
                mode = None               # None == value is self-contained

                if op < 0x40:                       # 00-3F constant runs
                    n = op & 0x1F
                    if n == 0:
                        n = data[si]; si += 1
                    nrow = n
                elif op < 0xA0:                     # 40-9F copy plane 0/1/2
                    n = op & 0x1F
                    if n == 0:
                        n = data[si]; si += 1
                    nrow = n
                    mode = ("plane", (op >> 5) - 2)
                elif op < 0xF0:                     # A0-EF same-plane back-ref
                    n = op & 0x0F
                    if n == 0:
                        n = data[si]; si += 1
                    nrow = n
                    mode = ("self", ((0, -16), (0, -8), (0, -4), (0, -2),
                                     (-2, 0))[(op >> 4) - 0x0A])
                elif op < 0xF9:                     # F0-F8 literal
                    n = data[si] if op == 0xF0 else op - 0xF0
                    if op == 0xF0:
                        si += 1
                    si += n
                    nrow = n
                elif op == 0xF9:                    # skip
                    nrow = data[si]; si += 1
                    write = False
                elif op == 0xFA:
                    nrow = data[si]; si += 2
                elif op == 0xFB:
                    k = data[si]; si += 1
                    nrow = k & 0x7F
                    mode = ("plane", 0 if k < 0x80 else 1)
                elif op == 0xFC:
                    k = data[si]; si += 1
                    if k < 0x80:
                        nrow = k & 0x7F
                        mode = ("plane", 2)
                    else:
                        nrow = 2 * (k & 0x7F); si += 1
                elif op == 0xFD:
                    k = data[si]; si += 1
                    if k < 0x80:
                        nrow = 2 * k; si += 2
                    elif k < 0xC0:
                        nrow = 4 * (k & 0x3F); si += 1
                    else:
                        nrow = 4 * (k & 0x3F); si += 2
                else:                               # 0xFE
                    k = data[si]; si += 1
                    if k < 0x40:
                        nrow = 4 * k; si += 4
                    else:
                        nrow = k & 0x3F
                        mode = ("and", {0x40: (0, 1), 0x80: (0, 2),
                                        0xC0: (1, 2)}[k & 0xC0])

                if write:
                    for t in range(r, r + nrow):
                        if t >= h:
                            break
                        wrow[t] = True
                        if mode is None:
                            krow[t] = True
                        elif mode[0] == "plane":
                            krow[t] = src_known(t, 0, 0, mode[1])
                        elif mode[0] == "self":
                            krow[t] = src_known(t, mode[1][0], mode[1][1], pi)
                        else:
                            krow[t] = (src_known(t, 0, 0, mode[1][0])
                                       and src_known(t, 0, 0, mode[1][1]))
                r += nrow

            if r != h:
                raise Da1Error("column %d plane %d advanced %d rows, want %d"
                               % (c, pi, r, h))
            cur[pi] = si

    for pi in range(4):
        if cur[pi] != m["streams"][pi][1]:
            raise Da1Error("plane %d stream not exhausted" % pi)
    return written, known


def plane_row_masks(data):
    """wr[plane][column][row] -- see analyse()."""
    return analyse(data)[0]


# ------------------------------------------------------------- column coder

def _enc_column(vals, skp, h, pi, cur, curskp, p2v, p2s):
    """Encode one byte-column of one plane.

    vals   : list of h byte values for this plane/column
    skp    : list of h booleans, True == this plane skips the row (opcode F9)
    pi     : plane index 0..3 (decides which cross-plane sources are legal)
    cur    : list of 4 value-lists for *this* column (only [j] j < pi valid)
    curskp : list of 4 skip-lists for this column -- a cross-plane opcode may
             only read a row the source plane actually wrote
    p2v    : value list of the same plane two byte-columns left, or None
    p2s    : matching skip list, or None
    """
    out = bytearray()
    lit = bytearray()

    def flush():
        if not lit:
            return
        p = 0
        n = len(lit)
        while p < n:
            k = n - p
            if k <= 8:
                out.append(0xF0 + k)
                out.extend(lit[p:p + k])
                p += k
            else:
                if k > 255:
                    k = 255
                out.append(0xF0)
                out.append(k)
                out.extend(lit[p:p + k])
                p += k
        del lit[:]

    i = 0
    while i < h:

        # ---- transparent run -> F9
        if skp[i]:
            flush()
            j = i
            while j < h and skp[j]:
                j += 1
            n = j - i
            while n:
                k = 255 if n > 255 else n
                out.append(0xF9)
                out.append(k)
                n -= k
            i = j
            continue

        # end of the current opaque segment: multi-row ops must not cross it
        e = i
        while e < h and not skp[e]:
            e += 1

        best_gain = 0
        best_len = 0
        best_blob = None

        def offer(L, blob):
            nonlocal best_gain, best_len, best_blob
            if L <= 0:
                return
            g = L - len(blob)
            if g >= 1 and (g > best_gain or (g == best_gain and L > best_len)):
                best_gain = g
                best_len = L
                best_blob = blob

        v0 = vals[i]

        # ---- constant run: 00 / FF / FA
        t = i
        while t < e and vals[t] == v0:
            t += 1
        rl = t - i
        if rl > 1:
            n = 255 if rl > 255 else rl
            if v0 == 0x00:
                offer(n, bytes((n,)) if n <= 31 else bytes((0x00, n)))
            elif v0 == 0xFF:
                offer(n, bytes((0x20 | n,)) if n <= 31 else bytes((0x20, n)))
            else:
                offer(n, bytes((0xFA, n, v0)))

        # ---- cross-plane copy / NOT  (only planes already decoded, and only
        #      rows that source plane actually wrote)
        for j in range(pi if pi < 3 else 3):
            src = cur[j]
            ssk = curskp[j]
            t = i
            while t < e and not ssk[t] and vals[t] == src[t]:
                t += 1
            L = t - i
            if L:
                n = 255 if L > 255 else L
                base = 0x40 + 0x20 * j
                offer(n, bytes((base | n,)) if n <= 31 else bytes((base, n)))
            t = i
            while t < e and not ssk[t] and vals[t] == src[t] ^ 0xFF:
                t += 1
            L = t - i
            if L:
                n = 127 if L > 127 else L
                if j == 0:
                    offer(n, bytes((0xFB, n)))
                elif j == 1:
                    offer(n, bytes((0xFB, 0x80 | n)))
                else:
                    offer(n, bytes((0xFC, n)))

        # ---- AND of two already-decoded planes (FE, k >= 0x40)
        for (a, b, kb) in ((0, 1, 0x40), (0, 2, 0x80), (1, 2, 0xC0)):
            if b < pi:
                pa = cur[a]
                pb = cur[b]
                ska = curskp[a]
                skb = curskp[b]
                t = i
                while (t < e and not ska[t] and not skb[t]
                       and vals[t] == (pa[t] & pb[t])):
                    t += 1
                L = t - i
                if L:
                    n = 63 if L > 63 else L
                    offer(n, bytes((0xFE, kb | n)))

        # ---- same-plane back-reference, N rows up (A0/B0/C0/D0)
        for (d, base) in ((16, 0xA0), (8, 0xB0), (4, 0xC0), (2, 0xD0)):
            if i >= d:
                t = i
                while t < e and not skp[t - d] and vals[t] == vals[t - d]:
                    t += 1
                L = t - i
                if L:
                    n = 255 if L > 255 else L
                    offer(n, bytes((base | n,)) if n <= 15
                          else bytes((base, n)))

        # ---- same-plane back-reference, two byte-columns left (E0)
        if p2v is not None:
            t = i
            while t < e and not p2s[t] and vals[t] == p2v[t]:
                t += 1
            L = t - i
            if L:
                n = 255 if L > 255 else L
                offer(n, bytes((0xE0 | n,)) if n <= 15 else bytes((0xE0, n)))

        # ---- 2-row period (FC mesh / FD literal pair)
        if i + 1 < e:
            b0 = vals[i]
            b1 = vals[i + 1]
            n = 0
            t = i
            while t + 1 < e and vals[t] == b0 and vals[t + 1] == b1:
                n += 1
                t += 2
            if n:
                if n > 127:
                    n = 127
                if b0 % 0x11 == 0 and b1 % 0x11 == 0:
                    offer(2 * n, bytes((0xFC, 0x80 | n,
                                        ((b1 // 0x11) << 4) | (b0 // 0x11))))
                offer(2 * n, bytes((0xFD, n, b0, b1)))

        # ---- 4-row period (FD mesh forms / FE literal quad)
        if i + 3 < e:
            c0 = vals[i]
            c1 = vals[i + 1]
            c2 = vals[i + 2]
            c3 = vals[i + 3]
            n = 0
            t = i
            while (t + 3 < e and vals[t] == c0 and vals[t + 1] == c1
                   and vals[t + 2] == c2 and vals[t + 3] == c3):
                n += 1
                t += 4
            if n:
                if n > 63:
                    n = 63
                mesh01 = (c0 % 0x11 == 0 and c1 % 0x11 == 0)
                if mesh01 and c2 == _ror8(c0, 2) and c3 == _ror8(c1, 2):
                    offer(4 * n, bytes((0xFD, 0x80 | n,
                                        ((c1 // 0x11) << 4) | (c0 // 0x11))))
                if mesh01 and c2 % 0x11 == 0 and c3 % 0x11 == 0:
                    offer(4 * n, bytes((0xFD, 0xC0 | n,
                                        ((c1 // 0x11) << 4) | (c0 // 0x11),
                                        ((c3 // 0x11) << 4) | (c2 // 0x11))))
                offer(4 * n, bytes((0xFE, n, c0, c1, c2, c3)))

        if best_blob is not None:
            flush()
            out.extend(best_blob)
            i += best_len
        else:
            lit.append(vals[i])
            i += 1

    flush()
    out.append(0xFF)                      # end of column
    return out


# ------------------------------------------------------------------ encoder

def _split_planes(pixels, alpha, w, h, plane_skip=None):
    """pixels (4-bit indices) -> cols[c][plane][row], skips[c][plane][row].

    `plane_skip`, when given, is wr-style per-plane write masks from
    plane_row_masks() (True == written).  A plane is only allowed to skip a
    row when the value it would have written is 0 -- otherwise the skip would
    lose real pixel data, so it is promoted to a write.  The number of such
    promotions is returned.
    """
    w_px = w * 8
    cols = [[[0] * h for _ in range(4)] for _ in range(w)]
    skips = [[[False] * h for _ in range(4)] for _ in range(w)]
    promoted = 0
    for row in range(h):
        base = row * w_px
        for c in range(w):
            o = base + c * 8
            b = [0, 0, 0, 0]
            for k in range(8):
                v = pixels[o + k] & 0x0F
                if v:
                    bit = 1 << (7 - k)
                    if v & 1:
                        b[0] |= bit
                    if v & 2:
                        b[1] |= bit
                    if v & 4:
                        b[2] |= bit
                    if v & 8:
                        b[3] |= bit

            opaque = True
            if alpha is not None:
                opaque = False
                for k in range(8):
                    if alpha[o + k]:
                        opaque = True
                        break
            if not opaque:
                for pi in range(4):
                    skips[c][pi][row] = True
                continue

            for pi in range(4):
                if (plane_skip is not None
                        and not plane_skip[pi][c][row]):
                    if b[pi] == 0:
                        skips[c][pi][row] = True
                        continue
                    promoted += 1
                cols[c][pi][row] = b[pi]
    return cols, skips, promoted


def encode(pixels, w_px, h, x, y, palette=None, alpha=None, flags=None,
           plane_skip=None, stats=None):
    """Build a complete DA1 file.  Returns bytes.

    plane_skip : optional per-plane write mask (see plane_row_masks) used to
                 reproduce an original file's per-plane transparency exactly.
                 Leave None for hand-edited art -- then every opaque byte-cell
                 is written in all four planes, which makes the result
                 independent of whatever is already on screen.
    """
    if w_px % 8:
        raise Da1Error("w_px must be a multiple of 8 (got %d)" % w_px)
    w = w_px // 8
    if not (1 <= w <= 80) or not (1 <= h <= VRAM_H):
        raise Da1Error("bad geometry %dx%d" % (w_px, h))
    if x + w > STRIDE or y + h > VRAM_H:
        raise Da1Error("rectangle x=%d w=%d y=%d h=%d leaves 80x400 VRAM"
                       % (x, w, y, h))
    if len(pixels) != w_px * h:
        raise Da1Error("pixels length %d != %d" % (len(pixels), w_px * h))
    if alpha is not None and len(alpha) != w_px * h:
        raise Da1Error("alpha length %d != %d" % (len(alpha), w_px * h))

    pal24 = None
    if palette is not None:
        if isinstance(palette, (bytes, bytearray)) and len(palette) == 24:
            pal24 = bytes(palette)
        else:
            pal24 = pack_palette(list(palette))

    if flags is None:
        flags = 0xCF00 if pal24 is not None else 0x4F00
    else:
        if pal24 is not None:
            flags |= 0x8000
        else:
            flags &= ~0x8000
        if not (flags & 0x4000):
            raise Da1Error("only byte-mode (flags bit14) is implemented")

    cols, skips, promoted = _split_planes(pixels, alpha, w, h, plane_skip)
    if stats is not None:
        stats["promoted"] = promoted

    streams = [bytearray(), bytearray(), bytearray(), bytearray()]
    for c in range(w):
        cur = cols[c]
        curskp = skips[c]
        for pi in range(4):
            if c >= 2:
                p2v = cols[c - 2][pi]
                p2s = skips[c - 2][pi]
            else:
                p2v = p2s = None
            streams[pi].extend(
                _enc_column(cur[pi], curskp[pi], h, pi, cur, curskp, p2v, p2s))

    for pi in range(4):
        if len(streams[pi]) > 0xFFFF:
            raise Da1Error("plane %d stream is %d bytes, u16 size field "
                           "overflows" % (pi, len(streams[pi])))

    body = bytearray()
    body += struct.pack("<4H", *[len(s) for s in streams])
    for s in streams:
        body += s

    total = 16 + (24 if pal24 is not None else 0) + len(body)
    out = bytearray()
    out += MAGIC
    out += struct.pack("<I", total)
    out.append(x & 0xFF)
    out.append(w & 0xFF)
    out += struct.pack("<HHH", y, h, flags & 0xFFFF)
    if pal24 is not None:
        out += pal24
    out += body
    assert len(out) == total
    return bytes(out)


def encode_like(orig, pixels, alpha=None, keep_plane_skip=True, stats=None):
    """Re-encode with x/y/flags/palette taken verbatim from an existing file.

    keep_plane_skip=True (default) also reproduces the original's *per-plane*
    transparency, so the result composites over an existing screen exactly the
    way the original did.  Pass False when the pixels were hand-edited and you
    want a fully self-contained sprite.
    """
    m = da1.parse_header(orig)
    ps = plane_row_masks(orig) if keep_plane_skip else None
    return encode(pixels, m["w"] * 8, m["h"], m["x"], m["y"],
                  palette=m["palette_raw"], alpha=alpha, flags=m["flags"],
                  plane_skip=ps, stats=stats)


# ------------------------------------------------------------------ helpers

def decoded_pixels(data):
    """(pixels, alpha) exactly as tools/da1.py sees them."""
    m = da1.decode_full(data)
    return da1._compose(m), da1.alpha_mask(m)


def _iter_files(args):
    for a in args:
        if os.path.isdir(a):
            for f in sorted(glob.glob(os.path.join(a, "*"))):
                if os.path.isfile(f):
                    yield f
        else:
            for f in sorted(glob.glob(a)):
                yield f


# ---------------------------------------------------------------------- CLI

def _cmd_roundtrip(args):
    n = ok = 0
    fails = []
    src_total = enc_total = 0
    src_clu = enc_clu = 0
    worst = []
    for f in _iter_files(args):
        d = open(f, "rb").read()
        if d[:4] != MAGIC:
            continue
        n += 1
        name = os.path.basename(f)
        try:
            px, am = decoded_pixels(d)
            enc = encode_like(d, px, am)
            px2, am2 = decoded_pixels(enc)
            if px2 != px:
                bad = sum(1 for a, b in zip(px, px2) if a != b)
                fails.append((name, "%d/%d pixels differ" % (bad, len(px))))
            elif am2 != am:
                bad = sum(1 for a, b in zip(am, am2) if a != b)
                fails.append((name, "%d/%d alpha differ" % (bad, len(am))))
            else:
                ok += 1
            src_total += len(d)
            enc_total += len(enc)
            src_clu += -(-len(d) // 4096)
            enc_clu += -(-len(enc) // 4096)
            worst.append((len(enc) / len(d), name, len(d), len(enc)))
        except Exception as ex:
            fails.append((name, "%s: %s" % (type(ex).__name__, ex)))
    print("DA1 files        : %d" % n)
    print("round-trip exact : %d  (%.2f%%)" % (ok, 100.0 * ok / n if n else 0))
    print("failed           : %d" % len(fails))
    for name, why in fails:
        print("   FAIL %-16s %s" % (name, why))
    if src_total:
        print("original total   : %d bytes" % src_total)
        print("re-encoded total : %d bytes  (x%.3f)"
              % (enc_total, enc_total / src_total))
        print("clusters (4096B) : %d -> %d  (delta %+d = %+.2f MB)"
              % (src_clu, enc_clu, enc_clu - src_clu,
                 (enc_clu - src_clu) * 4096 / 1048576.0))
    worst.sort(reverse=True)
    print("worst ratios:")
    for r, name, a, b in worst[:10]:
        print("   %-16s %7d -> %7d  x%.2f" % (name, a, b, r))
    return 0 if not fails else 1


def _cmd_reencode(args):
    outdir = args[0]
    os.makedirs(outdir, exist_ok=True)
    for f in _iter_files(args[1:]):
        d = open(f, "rb").read()
        if d[:4] != MAGIC:
            continue
        px, am = decoded_pixels(d)
        enc = encode_like(d, px, am)
        out = os.path.join(outdir, os.path.basename(f))
        open(out, "wb").write(enc)
        print("%-16s %7d -> %7d  x%.2f"
              % (os.path.basename(f), len(d), len(enc), len(enc) / len(d)))
    return 0


GREY16 = [(i * 17, i * 17, i * 17) for i in range(16)]


def _cmd_bgdeps(args):
    """Which files are standalone pictures and which are diffs against a base?"""
    n = 0
    clean = 0
    rows = []
    for f in _iter_files(args):
        d = open(f, "rb").read()
        if d[:4] != MAGIC:
            continue
        n += 1
        m = da1.parse_header(d)
        wr, kn = analyse(d)
        w, h = m["w"], m["h"]
        skipped = partial = inherited = 0
        for c in range(w):
            for r in range(h):
                nw = 0
                for pi in range(4):
                    if wr[pi][c][r]:
                        nw += 1
                        if not kn[pi][c][r]:
                            inherited += 1
                if nw == 0:
                    skipped += 1
                elif nw < 4:
                    partial += 1
        if not skipped and not partial and not inherited:
            clean += 1
        else:
            rows.append((os.path.basename(f), w * h, skipped, partial,
                         inherited))
    print("DA1 files                         : %d" % n)
    print("standalone (no VRAM dependency)   : %d" % clean)
    print("depend on what is already on screen: %d" % len(rows))
    print()
    print("%-16s %8s %10s %9s %10s"
          % ("file", "cells", "all-skip", "part-skip", "inherited"))
    rows.sort(key=lambda t: -(t[3] + t[4]))
    for a, cells, sk, pa, inh in rows:
        print("%-16s %8d %10d %9d %10d" % (a, cells, sk, pa, inh))
    print()
    print("all-skip  : byte-cell no plane writes -> pure transparency, fine")
    print("part-skip : some planes written, some not -> colour depends on the")
    print("            picture underneath")
    print("inherited : a WRITTEN plane cell whose value was copied from a cell")
    print("            the file never wrote -> the value itself comes from the")
    print("            screen underneath.  An encoder fed only decoded pixels")
    print("            cannot reproduce these; da1.py renders them as 0.")
    return 0


def _resolve_palette(path, m):
    """-> (16 rgb tuples, human note).  Falls back to the 16-step grey ramp
    used by da1.py's png command so that palette-less overlay patches still
    survive a PNG round-trip (index i renders as #ii)."""
    raw = m["palette_raw"]
    note = "own palette"
    if raw is None:
        raw, src = da1._sibling_palette(path)
        note = ("borrowed from %s" % src) if raw else None
    if raw is None:
        return list(GREY16), ("no palette in file and no sibling base image "
                              "found -- using the 16-step grey ramp "
                              "(index i renders as grey i*17)")
    return da1.palette_rgb(raw, "GRB"), note


def _cmd_frompng(args):
    from PIL import Image
    flat = False
    if "--flat" in args:
        flat = True
        args = [a for a in args if a != "--flat"]
    if len(args) != 3:
        print("usage: frompng [--flat] <orig.GDT> <edit.png> <out.GDT>")
        return 2
    src, pngp, dst = args
    d = open(src, "rb").read()
    if d[:4] != MAGIC:
        print("%s is not a DA1 file" % src)
        return 2
    m = da1.parse_header(d)
    w_px, h = m["w"] * 8, m["h"]

    pal, note = _resolve_palette(src, m)
    print("geometry : %dx%d at byte-col %d, line %d   flags=%04X"
          % (w_px, h, m["x"], m["y"], m["flags"]))
    print("palette  : %s" % note)

    alias = {}
    for i, c in enumerate(pal):
        alias.setdefault(c, []).append(i)
    dups = [v for v in alias.values() if len(v) > 1]
    if dups:
        print("NOTE     : this palette has duplicate RGB entries %s -- those "
              "indices are indistinguishable in an RGB PNG and all collapse "
              "to the lowest one." % "; ".join("=".join(map(str, v))
                                               for v in dups))

    img = Image.open(pngp).convert("RGBA")
    if img.size != (w_px, h):
        print("ERROR: PNG is %dx%d but the original sprite is %dx%d. "
              "Resize it first." % (img.size[0], img.size[1], w_px, h))
        return 2

    exact = {}
    for i, c in enumerate(pal):
        exact.setdefault(c, i)

    raw_rgba = img.tobytes()                 # 4 bytes per pixel, RGBA
    px = bytearray(w_px * h)
    am = bytearray(w_px * h)
    approx = 0
    approx_colours = {}
    cache = {}
    for i in range(w_px * h):
        r, g, b, a = raw_rgba[4 * i:4 * i + 4]
        if a == 0:
            am[i] = 0
            px[i] = 0
            continue
        am[i] = 255
        key = (r, g, b)
        idx = exact.get(key)
        if idx is None:
            idx = cache.get(key)
            if idx is None:
                best = 0
                bd = 1 << 30
                for j, (pr, pg, pb) in enumerate(pal):
                    dd = (pr - r) ** 2 + (pg - g) ** 2 + (pb - b) ** 2
                    if dd < bd:
                        bd = dd
                        best = j
                idx = best
                cache[key] = idx
            approx += 1
            approx_colours[key] = approx_colours.get(key, 0) + 1
        px[i] = idx

    if approx:
        nop = sum(1 for v in am if v)
        print("WARNING: %d of %d opaque pixels (%.2f%%) use colours that are "
              "NOT in the 16-colour palette; each was snapped to the nearest "
              "entry." % (approx, nop, 100.0 * approx / nop if nop else 0))
        print("         %d distinct off-palette colours." % len(approx_colours))
        per_idx = {}
        worst = {}
        for k, v in approx_colours.items():
            j = cache[k]
            dd = sum((pal[j][t] - k[t]) ** 2 for t in range(3))
            per_idx[j] = per_idx.get(j, 0) + v
            if j not in worst or dd > worst[j][0]:
                worst[j] = (dd, k)
        print("         snapped to:")
        for j in sorted(per_idx, key=lambda a: -per_idx[a]):
            dd, k = worst[j]
            print("           idx %2d #%02X%02X%02X  <- %7d px   "
                  "(furthest source #%02X%02X%02X, dist %.1f)"
                  % (j, pal[j][0], pal[j][1], pal[j][2], per_idx[j],
                     k[0], k[1], k[2], dd ** 0.5))
    else:
        print("colours  : all opaque pixels matched the palette exactly")

    # DA1 transparency is 8-pixel granular: snap the alpha to whole byte-cells
    # up front so that what we encode is exactly what we later verify against.
    partial = 0
    forced = 0
    for row in range(h):
        for c in range(m["w"]):
            o = row * w_px + c * 8
            s = sum(1 for k in range(8) if am[o + k])
            if s == 0 or s == 8:
                continue
            partial += 1
            forced += 8 - s
            for k in range(8):
                am[o + k] = 255                # cell becomes fully opaque
    if partial:
        print("WARNING: %d byte-cells mix opaque and transparent pixels. "
              "DA1 transparency has 8-pixel granularity, so those cells are "
              "stored fully OPAQUE" % partial)
        print("         -- %d formerly transparent pixels inside them are "
              "written as palette index 0." % forced)

    # per-plane transparency of the original
    wr = plane_row_masks(d)
    npart = sum(1 for c in range(m["w"]) for r in range(h)
                if 0 < sum(1 for pi in range(4) if wr[pi][c][r]) < 4)
    if npart:
        print("NOTE     : the original writes only SOME planes in %d byte-cells "
              "(it composites against what is already on screen)." % npart)
        print("           %s" % ("--flat given: those cells will be written in "
                                 "all four planes, making the sprite "
                                 "self-contained but changing how it "
                                 "composites." if flat else
                                 "keeping that per-plane transparency; pass "
                                 "--flat to write all four planes instead."))

    stats = {}
    enc = encode_like(d, bytes(px), bytes(am),
                      keep_plane_skip=not flat, stats=stats)
    if stats.get("promoted"):
        print("NOTE     : %d plane-cells the original skipped now carry "
              "non-zero edited data and were promoted to real writes."
              % stats["promoted"])
    open(dst, "wb").write(enc)
    px2, am2 = decoded_pixels(enc)
    bad_a = sum(1 for i in range(len(am)) if am2[i] != am[i])
    bad_p = sum(1 for i in range(len(px)) if am[i] and px2[i] != px[i])
    print("wrote %s : %d bytes (source %d, x%.2f)"
          % (dst, len(enc), len(d), len(enc) / len(d)))
    if bad_a == 0 and bad_p == 0:
        print("verify   : re-decode MATCHES the intended image exactly")
        return 0
    print("verify   : re-decode DIFFERS -- %d alpha, %d opaque pixels"
          % (bad_a, bad_p))
    return 1


def _cmd_topng(args):
    if len(args) != 2:
        print("usage: topng <orig.GDT> <out.png>")
        return 2
    from PIL import Image
    src, dst = args
    d = open(src, "rb").read()
    m = da1.decode_full(d)
    px = da1._compose(m)
    am = da1.alpha_mask(m)
    pal, note = _resolve_palette(src, m)
    buf = bytearray(len(px) * 4)
    for i, v in enumerate(px):
        c = pal[v]
        buf[4 * i] = c[0]
        buf[4 * i + 1] = c[1]
        buf[4 * i + 2] = c[2]
        buf[4 * i + 3] = am[i]
    img = Image.frombytes("RGBA", (m["w"] * 8, m["h"]), bytes(buf))
    img.save(dst)
    print("wrote %s  %dx%d  (%s)" % (dst, m["w"] * 8, m["h"], note))
    return 0


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    cmd = argv[1]
    if cmd == "roundtrip":
        return _cmd_roundtrip(argv[2:])
    if cmd == "reencode":
        return _cmd_reencode(argv[2:])
    if cmd == "bgdeps":
        return _cmd_bgdeps(argv[2:])
    if cmd == "frompng":
        return _cmd_frompng(argv[2:])
    if cmd == "topng":
        return _cmd_topng(argv[2:])
    print("unknown command", cmd)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
