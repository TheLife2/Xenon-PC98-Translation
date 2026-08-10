"""번역문 사전 검사. 빌드 전에 반드시 통과시킬 것.

검사 항목과 근거
  [치명] 연속 공백 3개 이상        게임이 크래시한다 (원본 프로젝트 scene_TLs/README.md)
  [치명] 슬롯 미할당 문자          바이트로 인코딩할 방법이 없다
  [치명] 블록 255바이트 초과       FD 뒤 길이 바이트가 1바이트다
  [치명] 제어코드 개수 불일치      <$XX> 를 지우면 표시가 깨진다
  [치명] 고유명사 배타 규약 위반   translation/terms.json 의 같은 group 안에서 다른 표기 사용
                                   (예: 원문 コウジ 인데 번역이 '코지')
  [경고] '…'(U+2026)               PC-98 에서 제대로 안 그려진다. '‥' 또는 '...' 사용
  [경고] '–'(U+2013)               오동작. '-' 또는 '―' 사용
  [경고] 고유명사 누락             원문에 있는 이름이 번역에 없다(의도적 생략일 수 있음)
  [경고] 원문보다 넓은 줄          자동 줄바꿈에 기대게 되어 레이아웃이 흔들린다
  [경고] 220바이트 초과            상한(255)에 근접
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kocfg as C
from koscript import text_to_bytes

TERMS_PATH = os.path.join(C.ROOT, "translation", "terms.json")


def load_terms():
    """[(jp, ko, group)] - 긴 표기를 먼저 보도록 정렬한다(ファルネリア 가 ファル 보다 먼저)."""
    if not os.path.exists(TERMS_PATH):
        return []
    raw = json.load(open(TERMS_PATH, encoding="utf-8"))
    ents = [(e["jp"], e["ko"], e.get("group")) for e in raw["entries"]]
    return sorted(ents, key=lambda e: -len(e[0]))


def load_terminology():
    """[(jp, ko, [금지표기])] - 확정된 일반 용어."""
    if not os.path.exists(TERMS_PATH):
        return []
    raw = json.load(open(TERMS_PATH, encoding="utf-8"))
    return [(e["jp"], e["ko"], e.get("avoid", [])) for e in raw.get("terminology", [])]


def check_terminology(jp, ko, terms, fatal, warn):
    """확정 용어 검사. 폐기된 표기가 남아 있으면 치명, 대응어가 없으면 경고."""
    tag = ko[:44]
    for j, k, avoid in terms:
        if j not in jp:
            continue
        bad = [a for a in avoid if a in ko]
        if bad:
            fatal.append(f"용어 미확정 표기 '{bad[0]}' (→ '{k}'): {tag}")
        elif k not in ko:
            warn.append(f"용어 '{j}' → '{k}' 없음: {tag}")


def check_terms(jp, ko, terms, fatal, warn):
    """고유명사 규약 검사.

    배타 group 은 치명 - 원문이 어느 표기인지에 따라 번역 표기가 정해진다.
    나머지는 경고 - 자연스러운 한국어를 위해 이름을 생략하는 건 흔한 일이다.
    """
    tag = ko[:44]
    seen_groups = {}
    for j, k, g in terms:
        if j in jp and g:
            seen_groups.setdefault(g, []).append((j, k))

    for g, hits in seen_groups.items():
        want = {k for _, k in hits}
        others = {k for j2, k, g2 in terms if g2 == g and k not in want}
        wrong = [o for o in others if o in ko]
        if wrong:
            src = "/".join(j for j, _ in hits)
            fatal.append(f"고유명사 배타 위반: 원문 '{src}' 인데 번역에 '{wrong[0]}' "
                         f"(→ '{'/'.join(sorted(want))}' 이어야 함): {tag}")
        elif not any(w in ko for w in want):
            warn.append(f"고유명사 누락: 원문 '{'/'.join(j for j, _ in hits)}' "
                        f"→ '{'/'.join(sorted(want))}' 없음: {tag}")

    for j, k, g in terms:
        if g or j not in jp:
            continue
        if k not in ko:
            warn.append(f"고유명사 누락: '{j}' → '{k}' 없음: {tag}")

RE_SPACES = re.compile(r" {3,}")
RE_CTRL = re.compile(r"<[$][0-9A-Fa-f]{2}>")
BAD_CHARS = {"…": "… (U+2026)", "–": "– (U+2013)", "—": "— (U+2014)"}


def check(verbose=True):
    pairs = C.load_pairs()
    table = C.load_table()
    terms = load_terms()
    terminology = load_terminology()
    fatal, warn = [], []
    done = 0

    for jp, ko in pairs:
        if not ko.strip():
            continue
        done += 1
        tag = ko[:44]

        check_terms(jp, ko, terms, fatal, warn)
        check_terminology(jp, ko, terminology, fatal, warn)

        # 연속 반각 공백은 원 프로젝트가 '크래시' 로 기록한 항목이다.
        # 다만 원문(M.CC 뮤직 모드)이 스스로 5개 연속을 쓰고 정상 동작하므로,
        # 원문에 이미 같은 길이의 공백이 있는 줄은 검증된 것으로 보고 넘어간다.
        # 번역이 새로 만들어 낸 연속 공백만 잡는다.
        m_ko = RE_SPACES.search(ko)
        if m_ko:
            m_jp = RE_SPACES.search(jp)
            if not m_jp or len(m_ko.group(0)) > len(m_jp.group(0)):
                fatal.append(f"연속 공백 3개 이상 (크래시): {tag}")

        for ch, label in BAD_CHARS.items():
            if ch in ko:
                warn.append(f"{label} 사용: {tag}")

        src_ctrl = RE_CTRL.findall(jp)
        dst_ctrl = RE_CTRL.findall(ko)
        if sorted(src_ctrl) != sorted(dst_ctrl):
            fatal.append(f"제어코드 불일치 {src_ctrl} -> {dst_ctrl}: {tag}")

        missing = [ch for ch in ko if ch not in table and C.needs_slot(ch)]
        if missing:
            fatal.append(f"슬롯 미할당 {''.join(sorted(set(missing)))}: {tag}")
            continue

        try:
            enc = text_to_bytes(ko, table)
            jenc = text_to_bytes(jp, table)
        except ValueError as e:
            fatal.append(f"{e}: {tag}")
            continue

        if len(enc) > C.MAX_BLOCK_BYTES:
            fatal.append(f"블록 {len(enc)}바이트 (상한 {C.MAX_BLOCK_BYTES}): {tag}")
        elif len(enc) > C.WARN_BLOCK_BYTES:
            warn.append(f"블록 {len(enc)}바이트 (상한 근접): {tag}")

        for i, (kl, jl) in enumerate(zip(enc.split(b"\x0a"), jenc.split(b"\x0a"))):
            kw, jw = C.display_width(kl), C.display_width(jl)
            if kw > max(jw, C.SCREEN_COLUMNS):
                warn.append(f"{i+1}번째 줄 {kw}칼럼 > 원문 {jw}칼럼: {tag}")

    if verbose:
        total = len(pairs)
        print(f"번역 진행 {done}/{total} ({100*done/total:.1f}%)" if total else "번역 파일이 비었습니다")
        print(f"치명 {len(fatal)}건 / 경고 {len(warn)}건")
        for m in fatal[:30]:
            print("  [치명]", m)
        if len(fatal) > 30:
            print(f"  ... 외 {len(fatal)-30}건")
        for m in warn[:20]:
            print("  [경고]", m)
        if len(warn) > 20:
            print(f"  ... 외 {len(warn)-20}건")
        if not fatal:
            print("치명적 문제 없음 - 빌드 가능")
    return fatal, warn


if __name__ == "__main__":
    f, _ = check()
    sys.exit(1 if f else 0)
