"""XENON PC-98 한국어 번역 파이프라인 - 공통 설정 / 유틸

원본 저장소 두 개는 읽기 전용으로만 참조한다.
  Xenon-PC98-Tools-master        : 원본 스크립트(scripts_cc), 원본 도구, HDI 이미지
  Xenon-PC98-Translation-master  : 일본어 원문 덤프, 영문 번역(참조용)
"""
import os
import re
import json

# ---------------------------------------------------------------- 경로 ----
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # C:\thelife\Xenon-KO
TOOLS_REPO = r"C:\thelife\Xenon-PC98-Tools-master"
TL_REPO = r"C:\thelife\Xenon-PC98-Translation-master"

# 번역 대상 스크립트 (.U.CC). 원본 저장소의 scripts_cc 는 본편 37개뿐이라,
# 이미지 안에만 있는 특수 모드 스크립트(K/L/M)를 합쳐 scripts_src 에 모아 둔다.
# 만드는 것은 tools/prepare_src.py.
SCRIPTS_SRC = os.path.join(ROOT, "scripts_src")
SCRIPTS_CC = SCRIPTS_SRC if os.path.isdir(SCRIPTS_SRC) and os.listdir(SCRIPTS_SRC) \
    else os.path.join(TOOLS_REPO, "scripts_cc")
GAME_DIR = os.path.join(TOOLS_REPO, "game")
BASE_HDI = os.path.join(GAME_DIR, "xenon_j.hdi")           # 일본어 원본 이미지를 베이스로 쓴다
LZSS_EXE = os.path.join(TOOLS_REPO, "tools", "xenon_lzss.exe")
FONT_SRC = os.path.join(TOOLS_REPO, "tools", "np2", "font.tmp")
ANEX_SRC = os.path.join(TOOLS_REPO, "tools", "np2", "anex86.bmp")

TRANSLATION = os.path.join(ROOT, "translation", "_script-korean.txt")
REFERENCE = os.path.join(ROOT, "translation", "reference-jp-en.txt")
TABLE = os.path.join(ROOT, "table", "kotable.json")
MERGE_DIR = os.path.join(ROOT, "scripts_merge")
BUILD_DIR = os.path.join(ROOT, "scripts_build")
STEP_DIR = os.path.join(ROOT, "scripts_steps")
OUT_DIR = os.path.join(ROOT, "out")

for _d in (MERGE_DIR, BUILD_DIR, STEP_DIR, OUT_DIR,
           os.path.dirname(TRANSLATION), os.path.dirname(TABLE)):
    os.makedirs(_d, exist_ok=True)

# 원본 스크립트 37개 (S00 계열 3개 + 본편 34개)
SCRIPT_NAMES = sorted(f[:-5] for f in os.listdir(SCRIPTS_CC) if f.endswith(".U.CC"))

# ------------------------------------------------------- 글리프 슬롯 풀 ----
# NP2kai font/fontpc98.c 의 fontpc98_read() 가 BMP 에서 실제로 읽어 들이는 区 는
#   0x01..0x2F (区1-47) / 0x30..0x55 (区48-85) / 0x58..0x5F (区88-95)
# 이 중 폰트 시트 전수 조사에서 '완전히 비어 있는' 区 만 골랐다.
#   区 9-12  = 반각 폰트가 16x16 공간에 복제된 영역  -> 절대 건드리면 안 됨
#   区 86,87 = 로더가 읽지 않음                      -> 쓸 수 없음
#   区 13    = NEC 특수문자(1)(2)(3)                 -> 유지
FREE_KU = [14, 15, 84, 85, 88, 93, 94]          # 아무것도 희생하지 않는 슬롯 : 658칸
KANJI2_KU = list(range(48, 84))                 # 제2수준한자 : 3,384칸 (한국어판에선 불필요)
SLOT_KU = FREE_KU + KANJI2_KU                   # 총 4,042칸

# 텍스트 블록 한 개의 최대 크기. FD 뒤 길이 바이트가 1바이트이므로 물리적 상한이다.
MAX_BLOCK_BYTES = 255
WARN_BLOCK_BYTES = 220
# 화면 폭 : 640px = 반각 80칼럼. 게임이 자동 줄바꿈하므로 하드 리밋은 아니지만
# 원문(일본어)보다 넓어지면 레이아웃이 깨질 소지가 크다.
SCREEN_COLUMNS = 80


def slots():
    """(区, 点) 슬롯을 할당 순서대로 무한정 내놓는다."""
    for ku in SLOT_KU:
        for ten in range(1, 95):
            yield ku, ten


def ku_ten_to_sjis(ku, ten):
    """JIS 区点 -> Shift-JIS 2바이트."""
    s1 = (ku + 257) // 2 if ku <= 62 else (ku + 385) // 2
    if ku & 1:
        s2 = ten + 63
        if ten >= 64:
            s2 += 1
    else:
        s2 = ten + 158
    return bytes([s1, s2])


# ------------------------------------------------------------ 이스케이프 ----
BS = chr(92)


def unescape(s):
    """xenon_script_extract.cpp 의 표기를 원래 바이트로 되돌린다.

    추출기는 0x0A 를 역슬래시+n 두 글자로, 그 밖의 제어 바이트를 <$NN> 으로 적는다.
    원본 삽입기(xenreplacer.py)에 이 역변환이 없어서 영문판에 '\\n' 이 그대로
    찍히는 버그가 있었다(S00/S00B/S00C 3곳). 여기서는 처음부터 되돌린다.
    """
    s = s.replace(BS + "n", "\n")
    return re.sub(r"<[$]([0-9A-Fa-f]{2})>", lambda m: chr(int(m.group(1), 16)), s)


def escape(s):
    """바이트 -> 덤프 표기 (원문 파일을 만들 때 사용)."""
    out = []
    for ch in s:
        c = ord(ch)
        if ch == "\n":
            out.append(BS + "n")
        elif c < 0x20:
            out.append("<$%02X>" % c)
        else:
            out.append(ch)
    return "".join(out)


# ------------------------------------------------------------- 번역 파일 ----
def load_pairs(path=None):
    """번역 파일을 [(일본어, 한국어)] 로 읽는다.

    형식 :  '#' 로 시작하는 줄은 주석
            '//일본어'  다음 줄이 번역문 (빈 줄이면 미번역)
    반환값의 일본어 키는 unescape 된 상태가 아니다(원본 덤프 표기 그대로).
    """
    path = path or TRANSLATION
    if not os.path.exists(path):
        return []
    lines = open(path, encoding="utf-8").read().split("\n")
    pairs = []
    i = 0
    while i < len(lines):
        l = lines[i].rstrip("\r")
        if l.startswith("//"):
            jp = l[2:]
            ko = ""
            j = i + 1
            while j < len(lines) and lines[j].rstrip("\r").startswith("#"):
                j += 1
            if j < len(lines) and not lines[j].rstrip("\r").startswith("//"):
                ko = lines[j].rstrip("\r")
                i = j + 1
            else:
                i = j
            pairs.append((jp, ko))
        else:
            i += 1
    return pairs


def load_table(path=None):
    path = path or TABLE
    if not os.path.exists(path):
        return {}
    raw = json.load(open(path, encoding="utf-8"))
    return {ch: bytes.fromhex(h) for ch, h in raw["map"].items()}


def save_table(table, path=None):
    path = path or TABLE
    json.dump({"version": 1,
               "note": "syllable -> Shift-JIS bytes. append-only; never reorder.",
               "map": {ch: b.hex() for ch, b in table.items()}},
              open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=0)


# --------------------------------------------------------------- 인코딩 ----
def needs_slot(ch):
    """자체 슬롯이 필요한 글자인가 (Shift-JIS 로 표현 못 하는 글자)."""
    try:
        ch.encode("cp932")
        return False
    except UnicodeEncodeError:
        return True


def encode(text, table, strict=True):
    """번역문 -> 게임이 읽는 바이트열."""
    out = bytearray()
    for ch in text:
        if ch in table:
            out += table[ch]
            continue
        try:
            out += ch.encode("cp932")
        except UnicodeEncodeError:
            if strict:
                raise ValueError(f"슬롯 미할당 문자 {ch!r} (U+{ord(ch):04X})")
            out += b"?"
    return bytes(out)


def display_width(data):
    """바이트열의 화면 폭(반각 칼럼 수). 제어코드는 세지 않는다."""
    w = 0
    i = 0
    while i < len(data):
        c = data[i]
        if c < 0x20:
            i += 2 if c == 0x04 else 1
            continue
        if (0x81 <= c <= 0x9F) or (0xE0 <= c <= 0xFC):
            w += 2
            i += 2
        else:
            w += 1
            i += 1
    return w


# --------------------------------------------------- 스크립트 블록 파서 ----
def iter_blocks(data):
    """.U.CC 안의 텍스트 블록을 (시작오프셋, 길이바이트오프셋, 본문시작, 본문끝) 으로.

    포맷 :  FD <len> <본문 len 바이트> 00
    원본 37개 파일 15,423 블록 전부가 이 규칙에 100% 들어맞는 것을 확인했다.
    """
    i = 0
    n = len(data)
    while i < n - 2:
        if data[i] == 0xFD:
            start = i + 2
            end = data.find(b"\x00", start)
            if end < 0:
                return
            yield i, i + 1, start, end
            i = end + 1
        else:
            i += 1
