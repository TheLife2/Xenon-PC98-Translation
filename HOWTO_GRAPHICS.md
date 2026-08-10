# 그래픽 안의 글자 번역하기

XENON 의 그림은 `.GDT` / `.ADT` 파일이고, **DA1** 이라는 형식으로 압축돼 있다.
이 형식은 공개 문서가 없어서(GARbro·Susie 플러그인·datacrystal 모두 미지원)
게임 실행 파일 `AGS.EXE` 의 디코더를 읽어 직접 복원했다.

지금은 **디코더 · 인코더 · 이미지 주입**이 모두 갖춰져 있어서,
그림판이나 포토샵으로 PNG 를 고치면 그대로 게임에 들어간다.

```
gfx/raw/*.GDT  ──디코드──▶  gfx/png/*.png  ──사람이 편집──▶  edited.png
                                                                │
out/xenon_ko.hdi  ◀──주입──  gfx/edit/*.GDT  ◀──인코드────────┘
```

---

## 0. 준비 — 한 번만

```bash
py tools/gfx_extract.py
```

디스크 이미지에서 그림 210개와 `AGS.EXE` 를 꺼내 `gfx/raw/` 에 놓고,
헤더 요약을 `gfx/INDEX.tsv` 로 남긴다.

```bash
py tools/da1.py png gfx/png gfx/raw
py tools/gfx_sheet.py
```

전부 PNG 로 풀고(`gfx/png/`), 25장씩 묶은 대지를 `gfx/sheet_NN.png` 로 만든다.
**어느 그림에 글자가 있는지는 이 대지를 눈으로 훑어 찾는다.**

---

## 1. 무엇을 고쳐야 하나

그림 210개를 전부 확인한 결과는 이렇다.

| 분류 | 개수 | 내용 |
|---|---|---|
| DA1 형식 | 203 | 이 문서의 대상 |
| DA1 아님 | 7 | `XEN.GDT` `0100B.ADT` `FA03/FA08/FA09.ADT` `MEG05.ADT` `RA03.ADT` |
| **일본어가 들어간 그림** | **1** | **`XENON2.GDT`** — 엔딩 타이틀 |

2026-08-10 에 203장 전부를 시각 전수 조사했다(상세: [gfx/TEXT_SURVEY_20260810.md](gfx/TEXT_SURVEY_20260810.md)).
타이틀 로고·메뉴·스태프 롤은 원래부터 영어라 손댈 것이 없고, **일본어가 있는 그림은 4장**이다.

| 파일 | 내용 | 상태 |
|---|---|---|
| `XENON2.GDT` | 肉奴隷 / トレイシーの憂鬱 | **한국어판 반영 완료** (`gfx_xenon2_ko.py`) |
| `1020.GDT` / `1020_3.GDT` | 안내판 「受付 →」→「접수 →」 (컬러/흑백) | **반영 완료** (`gfx_signs_ko.py`) |
| `1030.GDT` | 안내판 「← 第2○」→「← 제2진…」 | **반영 완료** (`gfx_signs_ko.py`) |
| `1010.GDT` | 책등 서명 (배경 소품, 도트 한계) | 우선순위 낮음 — 미반영 |

네 장 모두 배경 비의존(단독형)이라 이 파이프라인으로 고칠 수 있다.
단 `.ADT` 6개 안의 서브 이미지 89장(word 모드 - 미구현 코덱)은 아직 못 열어 봤다 — 조사 문서 참조.

아래는 **그림을 고치고 싶을 때**의 절차다.

---

## 2. 고치기 — 3단계

### 1단계 · PNG 로 꺼낸다

```bash
py tools/da1enc.py topng gfx/raw/XENON2.GDT work.png
```

`gfx/png/` 에 이미 풀어 둔 것을 써도 된다(파일명이 `XENON2_GDT.png` 처럼 점이 밑줄이 된다).

### 2단계 · PNG 를 고친다

아무 그림 도구나 쓴다. **지켜야 할 것은 셋뿐이다.**

| 규칙 | 이유 |
|---|---|
| **크기를 바꾸지 마라** | 게임이 헤더의 `x/y/w/h` 대로 화면에 그린다. 크기가 달라지면 주입이 거부된다 |
| **팔레트 16색 안에서 그려라** | PC-98 은 한 그림에 16색이다. 벗어난 색은 가장 가까운 팔레트 색으로 끌려간다 |
| **투명한 곳은 투명하게 두어라** | 알파 0 인 픽셀은 "안 그린다"는 뜻이다. 칠해 버리면 배경을 덮는다 |

팔레트는 인코더가 원본에서 그대로 가져오므로 **팔레트 자체는 바꿀 수 없다.**
안티에일리어싱을 쓰면 중간색이 16색으로 스냅되면서 지저분해진다 —
글자는 **경계를 또렷하게** 그리는 편이 낫다.

원본 글자를 지우고 그 자리에 새 글자를 넣는 작업은 `tools/gfx_xenon2_ko.py` 가
자동으로 한다. 다른 그림에도 그대로 응용할 수 있다(§5).

### 3단계 · 다시 DA1 로 만든다

```bash
py tools/da1enc.py frompng gfx/raw/XENON2.GDT work.png gfx/edit/XENON2.GDT
```

* **원본 파일을 반드시 첫 인자로 준다.** 팔레트·좌표·플래그·평면별 투명도를 여기서 물려받는다.
* 결과는 `gfx/edit/` 에 둔다. **빌드가 이 폴더만 본다.**
* 인코더는 쓰고 나서 자기 디코더로 다시 풀어 **의도한 픽셀과 정확히 같은지 확인**하고
  `verify : re-decode MATCHES the intended image exactly` 를 찍는다. 이 줄이 없으면 실패다.

출력에 이런 줄이 섞여 나오는 것은 정상이다.

```
idx 12 #DD6655 <- 37 px (furthest source #CF90A0, dist 87.1)
```

"PNG 의 이 색들을 팔레트 12번으로 몰았다"는 보고다. `dist` 가 크면 원하는 색이
팔레트에 없다는 뜻이니, 그 색을 쓰지 말고 팔레트 안의 색으로 다시 그려라.

---

## 3. 빌드에 태우기

```bash
py tools/build.py
```

**7단계 「편집한 그래픽 반영」** 이 `gfx/edit/*.GDT` 를 `out/xenon_ko.hdi` 에 써 넣는다.
폴더가 비어 있으면 아무것도 하지 않으므로, 그래픽을 안 건드릴 때도 그냥 돌리면 된다.

```
=== 7. 편집한 그래픽 반영 ==========================================
  XENON2.GDT: 8632 -> 7354 (-1278B)  368x96 @(128,268)
  반영 1개, 빈 클러스터 338 -> 339
```

넣기 전에 넷을 확인하고, 하나라도 어긋나면 **넣지 않고 거부한다.**

1. 매직이 `DA1\0` 인가
2. 헤더의 크기 필드가 실제 파일 크기와 같은가
3. 우리 디코더로 풀리는가
4. `x / y / w / h` 가 원본과 같은가 — 다르면 게임이 엉뚱한 자리에 그린다

### 되읽어 확인

```bash
py tools/gfx_check.py --png XENON2.GDT
```

디스크 이미지에서 **다시 읽어** `gfx/edit` 의 것과 같은지, 그리고 실제로 디코드되는지 본다.
`--png` 를 주면 디스크에서 읽은 바이트를 그림으로 풀어 `gfx/png/XENON2_HDI.png` 로 남긴다.
**게임이 보게 될 것과 같은 그림이다.**

```bash
py tools/gfx_check.py --all
```

이미지 안의 그림 210개를 전부 디코드해 본다. 정상 결과는 **성공 203 / 실패 7** 이고,
실패 7건은 §1 의 「DA1 아님」 목록과 일치해야 한다. 다른 파일이 실패하면 이미지가 깨진 것이다.

### 실행

```bash
py tools/build.py --run
```

또는 자동 스크린샷까지:

```bash
py tools/kotest.py 30
```

`XENON2.GDT` 는 엔딩 화면이라 실제로 보려면 끝까지 진행해야 한다.
`gfx_check.py --png` 가 게임이 읽을 바이트를 그대로 풀어 보여주므로,
화면 확인은 그것으로 갈음해도 된다.

---

## 4. 조심할 것

### 배경에 기대는 그림 44개

DA1 에는 **이미 화면에 그려져 있는 것을 복사해 오는** 명령이 있다.
그걸 쓰는 그림은 자기 혼자서는 완전한 그림이 되지 못한다.

```bash
py tools/da1enc.py bgdeps gfx/raw
```

```
standalone (no VRAM dependency) : 159
depend on what is already on screen: 44
```

**159개는 안전하다.** 44개는 "특정 배경 위에 겹쳐 그리는 차분(差分)" 이라서,
PNG 로 풀면 참조해 온 부분이 검게 비고 다시 인코딩해도 그 값을 복원할 수 없다.
**이 44개는 고치지 마라.** `XENON2.GDT` 는 159개 쪽(안전)이다.

굳이 손대야 한다면 `frompng --flat` 으로 네 평면을 모두 쓰게 만들 수 있지만,
그러면 합성 방식이 달라져 원래 겹쳐 보이던 배경이 가려진다.

### 파일이 커지면

인코더는 대개 원본보다 작게 만든다(203개 전체 재인코딩 시 **×0.986**).
그래도 커지는 경우, 빈 클러스터가 **약 338개(1.3 MB)** 있으므로 여유는 충분하다.
`build.py` 가 늘어난 클러스터 수를 찍어 준다.

### 원본을 덮어쓰지 마라

`gfx/raw/` 는 **원본 보관소**다. 편집본은 반드시 `gfx/edit/` 에 둔다.
`gfx/raw/` 가 있어야 `gfx_build.py` 가 좌표·크기를 대조할 수 있다.

---

## 4½. 글꼴 고르기 — 눈대중이 아니라 수치로

원본 「トレイシーの憂鬱」는 **획 두께 대비가 큰 서체**다(세로 런렝스 변동계수 1.07 —
균일한 고딕은 0.3~0.6). 후보 글꼴을 같은 지표로 재서 순위를 매기는 도구가 있다.

```bash
py tools/gfx_font_survey.py                  # 설치 글꼴 전수: 잉크비율·획 두께 분포로 순위
py tools/gfx_font_survey.py --dir D:\fonts   # 내려받은 글꼴 폴더 추가
py tools/gfx_preview_fonts.py --n 8          # 상위 후보를 실제 배경 위에 나란히
py tools/gfx_preview_fonts.py --n 4 --quant  # 16색 양자화까지 거친 모습으로
```

* 가변 폰트(`NotoSerifKR-VF.ttf` 등)는 **명명 인스턴스(웨이트)마다 따로** 측정한다.
  기본 웨이트로만 재면 ExtraLight 가 걸려 순위가 왜곡된다 — 실제로 그랬다.
* 산출물: `gfx/font_survey/report.tsv`(순위표), `sheet.png`(실루엣 대지),
  `preview.png`(배경 합성 대지), `preview_quant.png`(양자화 대지)

### ⚠ 라이선스 — 순위 1등을 그냥 쓰면 안 된다

거리 1~4위(궁서·아미·궁서체·HY궁서)는 전부 **한양정보통신 저작**(Windows 번들)이라
배포하는 패치 이미지에 구워 넣기에 부적합하다. 그래서 기본값은 순위 최상위권 중
유일한 SIL OFL 라이선스인 **Noto Serif KR Medium**(거리 5위, 1위와 0.07 차)이다.

무료로 더 시도할 만한 것(내려받아 `--dir` 로 재면 된다): 본명조/Noto Serif KR Heavy,
마루 부리(네이버), 검은고딕 Black Han Sans(윗줄용), G마켓 산스 Bold. 전부 OFL.
쿠키런체(게임 사용 금지 조항)·롯데리아체(성인물 금지 조항)는 라이선스가 막는다.

## 5. `gfx_xenon2_ko.py` — 글자 갈아끼우기 자동화

「원본 글자를 지우고 같은 자리에 한글을 그린다」를 자동으로 한다.
다른 그림에 쓰려면 이 파일을 복사해 위쪽 상수만 고치면 된다.

```python
SRC     = .../gfx/raw/XENON2.GDT      # 원본
PNG     = .../gfx/png/XENON2_GDT.png  # 풀어 둔 PNG
OUT_GDT = .../gfx/edit/XENON2.GDT     # 결과

BOX_TOP = (96, 4, 272, 26)     # 글자가 들어갈 상자 (x1, y1, x2, y2)
BOX_BOT = (4, 28, 364, 92)

KO_TOP = "육 노 예"
KO_BOT = "트레이시의 우울"
```

동작은 셋으로 나뉜다.

1. **글자색 판정** — 밝기 합이 620 이상인 팔레트 색을 글자로 본다(원본 글자는 흰색 계열).
   연분홍 #FF99EE 도 이 기준에 걸리지만 실측 결과 **글자 헤일로가 아니라 배경 광선의
   일부**다(해당 픽셀의 92%가 글자와 비접촉). 지워도 배경 복원이 다시 채우므로 무해하다.
2. **글자 지우기** — 지운 자리를 가장자리부터 안쪽으로 8방향 평균으로 반복해 메운다.
   좌우로만 늘리면 배경이 곡선 그라데이션이라 **가로 줄무늬가 남는다.**
   결과는 `gfx/png/XENON2_clean.png` 로 확인할 수 있다.
3. **한글 그리기** — 상자에 들어가는 가장 큰 크기를 자동으로 골라 그리되, 남는 폭을
   자간으로 고르게 나눠 **원본처럼 좌우를 꽉 채운다**(`spread`). 글꼴은
   `--font <ttf> --weight <인스턴스>` / `--top-font --top-weight` 로 바꿀 수 있다.

```bash
py tools/gfx_xenon2_ko.py            # 미리보기 PNG 만
py tools/gfx_xenon2_ko.py --write    # gfx/edit/XENON2.GDT 까지
```

```
  글자색으로 판정: [(255, 255, 255), (255, 153, 238)]
  지운 글자 픽셀: 6459
  글꼴 크기: 위 22px / 아래 49px
verify   : re-decode MATCHES the intended image exactly
  XENON2.GDT 8632 -> 7354 바이트 (0.852배)
```

미리보기로 만드는 PNG 는 셋이다.

| 파일 | 내용 |
|---|---|
| `gfx/png/XENON2_GDT.png` | 원본 |
| `gfx/png/XENON2_clean.png` | 글자만 지운 것 — **배경 복원이 잘 됐는지 여기서 본다** |
| `gfx/png/XENON2_KO.png` | 한글을 얹은 최종본 |

---

## 6. 형식 메모 (고칠 일은 없지만 알아 둘 것)

`DA1` 은 도쿠마쇼텐 인터미디어의 **ANNEX 라이브러리**(아나자와, 1987–91) 형식이다.
LZSS 가 아니다 — **세로 방향 런렝스 + 평면 간 참조 + 니블 디더 확장**을 섞은
256갈래 점프 테이블 방식이다.

```
 0..3   "DA1\0"
 4..7   u32  파일 크기
 8      u8   x  (바이트 단위 = 8픽셀)
 9      u8   w  (바이트 단위)
10..11  u16  y
12..13  u16  h
14..15  u16  플래그  (bit15 팔레트 있음, bit14 코덱 선택)
[16..39]     팔레트 24바이트 (GRB 4:4:4) — bit15 일 때만
             u16[4] 평면별 스트림 길이
             평면 4개 스트림 (B / R / G / I 순)
```

검증 현황 — 203개 전부에 대해

* 디코드 **203/203**, 컬럼 38,364개가 정확히 `h` 행씩 전진
* 평면 스트림 812개가 정확히 소진
* 256가지 opcode 전부 실제로 등장
* 디코드 → 인코드 → 디코드 **왕복 일치 203/203**

---

## 7. 명령 요약

```bash
py tools/gfx_extract.py                                   # 디스크에서 그림 꺼내기
py tools/da1.py png gfx/png gfx/raw                       # 전부 PNG 로
py tools/gfx_sheet.py                                     # 대지로 묶어 훑어보기
py tools/da1.py verify gfx/raw                            # 디코더 자체 검증
py tools/da1enc.py roundtrip gfx/raw                      # 인코더 왕복 검증
py tools/da1enc.py bgdeps gfx/raw                         # 배경 의존 목록
py tools/da1enc.py topng   <원본.GDT> <out.png>           # 한 장만 PNG 로
py tools/da1enc.py frompng <원본.GDT> <편집.png> <out.GDT> # PNG -> DA1
py tools/gfx_font_survey.py                               # 글꼴 후보 수치 비교
py tools/gfx_preview_fonts.py --n 8                       # 상위 후보 배경 합성 미리보기
py tools/gfx_xenon2_ko.py --write                         # 엔딩 타이틀 한국어판
py tools/build.py                                         # 빌드 (7단계에서 반영)
py tools/gfx_check.py --png XENON2.GDT                    # 이미지에서 되읽어 확인
py tools/gfx_check.py --all                               # 전체 디코드 점검
py tools/build.py --run                                   # 에뮬레이터로 실행
```
