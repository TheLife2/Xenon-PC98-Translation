"""HDI(Anex86 하드디스크 이미지) 안의 FAT12 파일 교체.

원본 도구는 DiskExplorer(editdisk.exe) 로 사람이 드래그&드롭하는 방식이라 자동화가
안 됐다. 여기서는 직접 FAT12 를 다룬다. 파일이 커져 클러스터가 더 필요하면
빈 클러스터를 새로 할당한다(원본 이미지 여유 공간 약 1.37 MB).

  HDI 헤더 4096바이트 + 디스크 이미지
  파티션 : FAT12, 1024 B/섹터, 4 섹터/클러스터 = 4096 B/클러스터
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

HDI_HEADER = 4096
FREE, EOC = 0x000, 0xFFF


class Fat12:
    def __init__(self, path):
        self.raw = bytearray(open(path, "rb").read())
        base = None
        for o in range(HDI_HEADER, len(self.raw), 512):
            if self.raw[o + 0x36:o + 0x3B] in (b"FAT12", b"FAT16"):
                base = o
                break
        if base is None:
            raise ValueError("FAT 부트섹터를 못 찾았습니다")
        self.base = base
        r = self.raw
        self.bps = struct.unpack_from("<H", r, base + 0x0B)[0]
        self.spc = r[base + 0x0D]
        resv = struct.unpack_from("<H", r, base + 0x0E)[0]
        self.nfat = r[base + 0x10]
        self.nroot = struct.unpack_from("<H", r, base + 0x11)[0]
        self.spf = struct.unpack_from("<H", r, base + 0x16)[0]
        total = (struct.unpack_from("<H", r, base + 0x13)[0]
                 or struct.unpack_from("<I", r, base + 0x20)[0])
        self.fat_off = base + resv * self.bps
        self.root_off = self.fat_off + self.nfat * self.spf * self.bps
        self.data_off = self.root_off + self.nroot * 32
        self.csize = self.spc * self.bps
        self.nclusters = (total - (self.data_off - base) // self.bps) // self.spc + 2

    # ------------------------------------------------------------- FAT ----
    def get(self, cl):
        i = self.fat_off + cl + (cl >> 1)
        v = self.raw[i] | (self.raw[i + 1] << 8)
        return (v >> 4) if (cl & 1) else (v & 0x0FFF)

    def set(self, cl, val):
        for f in range(self.nfat):
            b = self.fat_off + f * self.spf * self.bps + cl + (cl >> 1)
            v = self.raw[b] | (self.raw[b + 1] << 8)
            v = ((val << 4) | (v & 0x000F)) if (cl & 1) else ((v & 0xF000) | val)
            self.raw[b] = v & 0xFF
            self.raw[b + 1] = (v >> 8) & 0xFF

    def chain(self, start):
        out, cl = [], start
        while 2 <= cl < 0xFF8 and len(out) < self.nclusters + 8:
            out.append(cl)
            cl = self.get(cl)
        return out

    def free_clusters(self):
        return [c for c in range(2, self.nclusters) if self.get(c) == FREE]

    # ---------------------------------------------------------- 디렉터리 ----
    def entries(self):
        out = []
        for i in range(self.nroot):
            o = self.root_off + i * 32
            if self.raw[o] == 0:
                break
            if self.raw[o] == 0xE5 or self.raw[o + 0x0B] & 0x18:
                continue
            nm = self.raw[o:o + 8].decode("ascii", "replace").rstrip()
            ex = self.raw[o + 8:o + 11].decode("ascii", "replace").rstrip()
            out.append((nm + ("." + ex if ex else ""),
                        struct.unpack_from("<I", self.raw, o + 0x1C)[0],
                        struct.unpack_from("<H", self.raw, o + 0x1A)[0], o))
        return out

    def _find(self, name):
        for n, size, clu, o in self.entries():
            if n.upper() == name.upper():
                return size, clu, o
        raise KeyError(name)

    def read(self, name):
        size, clu, _ = self._find(name)
        b = bytearray()
        for cl in self.chain(clu):
            off = self.data_off + (cl - 2) * self.csize
            b += self.raw[off:off + self.csize]
        return bytes(b[:size])

    def write(self, name, data):
        _size, clu, o = self._find(name)
        chain = self.chain(clu)
        need = max(1, (len(data) + self.csize - 1) // self.csize)
        if need > len(chain):
            spare = self.free_clusters()
            if len(spare) < need - len(chain):
                raise OSError(f"{name}: 빈 클러스터 부족 "
                              f"({need-len(chain)} 필요, {len(spare)} 남음)")
            chain += spare[:need - len(chain)]
        for i in range(need):
            off = self.data_off + (chain[i] - 2) * self.csize
            chunk = data[i * self.csize:(i + 1) * self.csize].ljust(self.csize, b"\x00")
            self.raw[off:off + self.csize] = chunk
            self.set(chain[i], chain[i + 1] if i + 1 < need else EOC)
        for cl in chain[need:]:
            self.set(cl, FREE)
        struct.pack_into("<I", self.raw, o + 0x1C, len(data))
        struct.pack_into("<H", self.raw, o + 0x1A, chain[0])
        return need, len(chain)

    def save(self, path):
        open(path, "wb").write(bytes(self.raw))


if __name__ == "__main__":
    import kocfg as C
    fs = Fat12(C.BASE_HDI)
    print(f"클러스터 {fs.csize}B, 총 {fs.nclusters-2}개, 빈 클러스터 {len(fs.free_clusters())}개 "
          f"({len(fs.free_clusters())*fs.csize/1024:.0f} KB)")
    print(f"파일 {len(fs.entries())}개")
