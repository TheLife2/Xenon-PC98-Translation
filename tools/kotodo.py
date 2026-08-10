"""미번역으로 남은 줄을 사람 번역자용 작업 파일로 뽑는다.

    py tools/kotodo.py                    장면(연속 구간) 단위  -> translation/todo/
    py tools/kotodo.py --single [폴더]    한 줄에 파일 하나     -> 기본 'translation/새 폴더'
    py tools/kotodo.py --collect [폴더]   채워진 파일을 모아 overrides.txt 에 덧붙인다

에이전트가 내용을 이유로 건너뛴 줄(성적 강압·미성년으로 읽히는 묘사 등)이 대부분이다.

작업 파일은 '//일본어' 다음 줄에 한국어를 적는 형식이다.
채운 뒤 --collect 하거나, 그 내용을 translation/overrides.txt 에 이어 붙이면 반영된다.
"""
import os
import sys
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kocfg as C
from koscript import key_of

TODO = os.path.join(C.ROOT, "translation", "todo")


SINGLE = os.path.join(C.ROOT, "translation", "새 폴더")


def load_en():
    en = {}
    p = os.path.join(C.TL_REPO, "script-japanese-with-translation.txt")
    lines = open(p, encoding="utf-8").read().split("\n")
    i = 0
    while i < len(lines):
        if lines[i].rstrip("\r").startswith("//"):
            en[lines[i].rstrip("\r")[2:]] = lines[i + 1].rstrip("\r") if i + 1 < len(lines) else ""
            i += 2
        else:
            i += 1
    return en


def collect_todo():
    """미번역 줄을 (스크립트, 키) 로, 스크립트 등장 순서대로."""
    kmap = dict(C.load_pairs())
    out = []
    seen = set()
    for name in C.SCRIPT_NAMES:
        data = open(os.path.join(C.SCRIPTS_CC, name + ".U.CC"), "rb").read()
        for _, _, s, e in C.iter_blocks(data):
            k = key_of(data[s:e])
            if k in kmap and not kmap[k].strip() and k not in seen:
                seen.add(k)
                out.append((name, k))
    return out


def single(dest, header=False):
    """한 줄에 파일 하나.

    기본은 참고용 영문과 일본어 원문 두 줄만 남긴다.

        #EN <영문 참조>
        //<일본어 원문>

    '#EN' 과 '//' 두 글자짜리 표지는 남긴다. --collect 가 이걸로 두 줄을 구분하고,
    번역을 '//' 줄 다음에 붙여 되돌리기 때문이다. 표지를 지우면 병합이 불가능해진다.
    --with-header 를 주면 안내 주석이 붙은 예전 형식으로 만든다.
    """
    en = load_en()
    items = collect_todo()
    os.makedirs(dest, exist_ok=True)
    for f in os.listdir(dest):
        fp = os.path.join(dest, f)
        if os.path.isfile(fp):
            os.remove(fp)

    idx = []
    no_en = 0
    for n, (name, k) in enumerate(items, 1):
        fn = f"{n:04d}_{name}.txt"
        with open(os.path.join(dest, fn), "w", encoding="utf-8", newline="\n") as f:
            if header:
                f.write(f"# {n:04d} / {len(items)}   스크립트 {name}\n")
                f.write("# 아래 '//' 줄이 일본어 원문이다. 그 다음 빈 줄에 한국어를 적는다.\n")
                f.write("# '//' 줄과 '#' 줄은 고치지 않는다. 규칙은 translation/TRANSLATE_GUIDE.md\n")
                f.write("#\n")
            if en.get(k):
                f.write("#EN " + en[k] + "\n")
            else:
                no_en += 1
            f.write("//" + k + "\n")
            if header:
                f.write("\n")
        idx.append((fn, name, k))
    if no_en:
        print(f"  (영문 참조가 없는 줄 {no_en}개는 일본어 원문만 들어 있습니다)")

    with open(os.path.join(dest, "_INDEX.tsv"), "w", encoding="utf-8", newline="\n") as f:
        f.write("파일\t스크립트\t일본어\n")
        for fn, name, k in idx:
            f.write(f"{fn}\t{name}\t{k}\n")

    print(f"미번역 {len(items)}줄 -> 파일 {len(items)}개")
    print(f"  {dest}")
    print(f"  목록: _INDEX.tsv")
    for fn, name, k in idx[:6]:
        print(f"    {fn:22s} {k[:46]}")
    print(f"    ...")
    return len(items)


def sync_todo(src=None, dst=None):
    """낱개 파일(새 폴더)에 채워진 번역을 장면 단위 파일(todo)로 옮긴다.

    todo 파일은 줄 단위로 다시 쓴다. '//' 줄 바로 다음 줄만 채우고
    주석·원문·빈 줄 구조는 그대로 둔다.
    """
    from kobatch import read_units
    src = src or SINGLE
    dst = dst or TODO

    # 1) 낱개 파일에서 {일본어: 한국어}
    got = {}
    empty = 0
    for fn in sorted(os.listdir(src)):
        if not fn.endswith(".txt") or fn.startswith("_"):
            continue
        for _, jp, ko in read_units(os.path.join(src, fn)):
            if ko.strip():
                got[jp] = ko
            else:
                empty += 1
    print(f"낱개 파일: 번역 {len(got)}줄 / 미작성 {empty}줄")

    # 2) todo 파일을 줄 단위로 다시 쓴다
    filled = already = missing = 0
    changed_files = 0
    for fn in sorted(os.listdir(dst)):
        if not fn.startswith("TODO_") or not fn.endswith(".txt"):
            continue
        path = os.path.join(dst, fn)
        lines = open(path, encoding="utf-8").read().split("\n")
        out = []
        i = 0
        touched = False
        while i < len(lines):
            line = lines[i].rstrip("\r")
            out.append(line)
            if line.startswith("//"):
                jp = line[2:]
                nxt = lines[i + 1].rstrip("\r") if i + 1 < len(lines) else None
                has_slot = nxt is not None and not nxt.startswith(("//", "#"))
                cur = nxt if has_slot else ""
                if cur.strip():
                    already += 1
                    out.append(cur)
                elif jp in got:
                    out.append(got[jp])
                    filled += 1
                    touched = True
                else:
                    out.append("")
                    missing += 1
                i += 2 if has_slot else 1
                continue
            i += 1
        if touched:
            open(path, "w", encoding="utf-8", newline="\n").write("\n".join(out))
            changed_files += 1

    print(f"todo 반영: {filled}줄 채움 / 이미 채워져 있던 {already}줄 / "
          f"아직 비어 있는 {missing}줄")
    print(f"  수정된 파일 {changed_files}개  ({dst})")
    return filled, missing


def collect(src):
    """채워진 낱개 파일을 모아 overrides.txt 뒤에 덧붙인다."""
    from kobatch import read_units
    done = []
    empty = 0
    for fn in sorted(os.listdir(src)):
        if not fn.endswith(".txt") or fn.startswith("_"):
            continue
        us = read_units(os.path.join(src, fn))
        for _, jp, ko in us:
            if ko.strip():
                done.append((fn, jp, ko))
            else:
                empty += 1
    if not done:
        print(f"채워진 줄이 없습니다 (빈 파일 {empty}개). {src}")
        return 0
    # 덧붙이면 여러 번 돌릴 때 중복되고, 뒤에 붙은 옛 값이 앞선 수정을 덮는다.
    # 자기 블록만 통째로 갈아 끼운다.
    path = os.path.join(C.ROOT, "translation", "overrides.txt")
    MARK = "# 7) 미번역분 수기 번역 (kotodo.py --collect)"
    cur = open(path, encoding="utf-8").read()
    cut = cur.find(MARK)
    head = cur[:cut] if cut >= 0 else cur.rstrip("\n") + "\n\n"
    block = (MARK + "\n"
             "#    translation/새 폴더 의 낱개 파일을 모은 것. 그 폴더가 원본이다.\n"
             "# ============================================================\n")
    for fn, jp, ko in done:
        block += f"# {fn}\n//{jp}\n{ko}\n"
    open(path, "w", encoding="utf-8", newline="\n").write(head + block)
    print(f"{len(done)}줄을 overrides.txt 에 반영했습니다 (남은 빈 파일 {empty}개)")
    print("  이어서:  py tools/kobatch.py merge  ->  py tools/build.py")
    return len(done)


def main():
    pairs = C.load_pairs()
    kmap = dict(pairs)

    # 영문 참조
    en = {}
    p = os.path.join(C.TL_REPO, "script-japanese-with-translation.txt")
    lines = open(p, encoding="utf-8").read().split("\n")
    i = 0
    while i < len(lines):
        if lines[i].rstrip("\r").startswith("//"):
            en[lines[i].rstrip("\r")[2:]] = lines[i + 1].rstrip("\r") if i + 1 < len(lines) else ""
            i += 2
        else:
            i += 1

    # 스크립트 파일 안에서의 등장 순서대로, 미번역 줄을 연속 구간으로 묶는다
    runs = []            # (스크립트, [키...])
    seen_key = set()
    for name in C.SCRIPT_NAMES:
        data = open(os.path.join(C.SCRIPTS_CC, name + ".U.CC"), "rb").read()
        cur = []
        for _, _, s, e in C.iter_blocks(data):
            k = key_of(data[s:e])
            todo = k in kmap and not kmap[k].strip()
            if todo and k not in seen_key:
                cur.append(k)
                seen_key.add(k)
            elif cur:
                runs.append((name, cur))
                cur = []
        if cur:
            runs.append((name, cur))

    os.makedirs(TODO, exist_ok=True)
    for f in os.listdir(TODO):
        os.remove(os.path.join(TODO, f))

    runs = [r for r in runs if r[1]]
    runs.sort(key=lambda r: -len(r[1]))
    total = sum(len(r[1]) for r in runs)

    idx = []
    for n, (name, keys) in enumerate(runs):
        fn = f"TODO_{n:03d}_{name}.txt"
        with open(os.path.join(TODO, fn), "w", encoding="utf-8", newline="\n") as f:
            f.write(f"# {name} 의 미번역 연속 구간 - {len(keys)}줄\n")
            f.write("# '//' 줄 다음의 빈 줄에 한국어를 적는다.\n")
            f.write("# 다 채운 뒤 이 파일 내용을 translation/overrides.txt 뒤에 붙이면 반영된다.\n")
            f.write("# 규칙은 translation/TRANSLATE_GUIDE.md 를 따른다.\n\n")
            for k in keys:
                if en.get(k):
                    f.write("#EN " + en[k] + "\n")
                f.write("//" + k + "\n\n")
        idx.append((fn, name, len(keys), keys[0][:56]))

    per = collections.Counter(name for name, _ in runs)
    per_lines = collections.Counter()
    for name, keys in runs:
        per_lines[name] += len(keys)

    with open(os.path.join(TODO, "INDEX.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("# 미번역 목록\n\n")
        f.write(f"번역 워크플로우가 내용을 이유로 건너뛴 줄이다. 총 **{total}줄** / "
                f"연속 구간 **{len(runs)}개**.\n\n")
        f.write("사유는 대부분 두 가지다.\n\n")
        f.write("1. 등장인물이 미성년으로 읽히는 성적 묘사 (작중 나이 미명시 + 미성숙 신체 강조)\n")
        f.write("2. 비동의·강압 성행위 묘사 (명시적 거부가 반복되는 장면)\n\n")
        f.write("게임은 그대로 동작한다. 해당 블록은 원문 바이트가 유지되어 화면에 일본어로 나온다.\n\n")
        f.write("## 스크립트별\n\n| 스크립트 | 미번역 줄 | 구간 |\n|---|---|---|\n")
        for name, cnt in per_lines.most_common():
            f.write(f"| {name} | {cnt} | {per[name]} |\n")
        f.write("\n## 구간별 작업 파일\n\n| 파일 | 스크립트 | 줄 | 첫 줄 |\n|---|---|---|---|\n")
        for fn, name, cnt, head in idx:
            f.write(f"| `{fn}` | {name} | {cnt} | {head} |\n")

    print(f"미번역 {total}줄 / 연속 구간 {len(runs)}개")
    print(f"  {TODO}")
    for fn, name, cnt, _ in idx[:12]:
        print(f"    {fn:28s} {cnt:4d}줄")
    if len(idx) > 12:
        print(f"    ... 외 {len(idx)-12}개 파일")


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--single" in args:
        i = args.index("--single")
        dest = args[i + 1] if len(args) > i + 1 and not args[i + 1].startswith("--") else SINGLE
        single(dest, header="--with-header" in args)
    elif "--sync-todo" in args:
        sync_todo()
    elif "--collect" in args:
        i = args.index("--collect")
        src = args[i + 1] if len(args) > i + 1 and not args[i + 1].startswith("--") else SINGLE
        collect(src)
    else:
        main()
