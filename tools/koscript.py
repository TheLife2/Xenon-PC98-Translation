"""텍스트 블록 <-> 사람이 읽는 문자열 변환.

블록 포맷 (원본 37개 파일 15,423 블록에서 100% 검증됨)

    FD <len> <본문 len 바이트> 00

본문에는 Shift-JIS 텍스트와 제어 바이트가 섞여 있다.

    0x04 xx   2바이트 명령 (색/대기 등)
    0x05      1바이트 명령
    0x0A      줄바꿈
    0x0C      1바이트 명령

표기법은 원본 추출기(xenon_script_extract.cpp)와 동일하게 맞췄다.
0x0A 는 역슬래시+n, 그 밖의 제어 바이트는 <$NN>.
"""
import re
from kocfg import BS, encode

CTRL2 = {0x04}                      # 뒤에 피연산자 1바이트가 붙는 제어코드
CTRL1 = {0x05, 0x0C}


def block_to_text(blk: bytes) -> str:
    """블록 본문 -> 표기 문자열."""
    out = []
    i = 0
    n = len(blk)
    while i < n:
        b = blk[i]
        if b in CTRL2 and i + 1 < n:
            out.append("<$%02X><$%02X>" % (b, blk[i + 1]))
            i += 2
        elif b == 0x0A:
            out.append(BS + "n")
            i += 1
        elif b < 0x20:
            out.append("<$%02X>" % b)
            i += 1
        elif (0x81 <= b <= 0x9F) or (0xE0 <= b <= 0xFC):
            out.append(blk[i:i + 2].decode("cp932", "replace"))
            i += 2
        else:
            out.append(blk[i:i + 1].decode("cp932", "replace"))
            i += 1
    return "".join(out)


_TOK = re.compile(r"<[$]([0-9A-Fa-f]{2})>|" + re.escape(BS) + "n")


def text_to_bytes(text: str, table: dict) -> bytes:
    """표기 문자열 -> 블록 본문 바이트."""
    out = bytearray()
    pos = 0
    for m in _TOK.finditer(text):
        if m.start() > pos:
            out += encode(text[pos:m.start()], table)
        out += bytes([int(m.group(1), 16)]) if m.group(1) else b"\x0a"
        pos = m.end()
    if pos < len(text):
        out += encode(text[pos:], table)
    return bytes(out)


def split_affix(blk: bytes):
    """블록을 (선두 제어열, 본문, 말미 제어열) 으로 나눈다.

    번역자에게는 본문만 보여 주고 제어열은 자동으로 보존한다.
    선두/말미의 제어코드는 표시 위치·색·대기 지시라서 번역과 무관하다.
    """
    i = 0
    n = len(blk)
    while i < n:
        b = blk[i]
        if b in CTRL2 and i + 1 < n:
            i += 2
        elif b in CTRL1 or b == 0x0A:
            i += 1
        else:
            break
    head_end = i

    j = n
    while j > head_end:
        if j - 1 > head_end and blk[j - 2] in CTRL2:
            j -= 2
        elif blk[j - 1] in CTRL1 or blk[j - 1] == 0x0A:
            j -= 1
        else:
            break
    return blk[:head_end], blk[head_end:j], blk[j:]


def key_of(blk: bytes) -> str:
    """번역 파일에서 이 블록을 가리키는 키(= 본문 표기 문자열)."""
    return block_to_text(split_affix(blk)[1])
