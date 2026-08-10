# 실행 방법

## 준비물 — 두 개가 세트다

```
out\xenon_ko.hdi     7,315,456 바이트    게임 디스크 이미지
out\font.tmp           524,350 바이트    한글 글리프가 들어간 폰트 시트
```

**폰트 파일이 없으면 한글이 안 나온다.** 게임은 PC-98의 폰트 ROM에서 글자를 가져다
쓰는데, Shift-JIS에는 한글이 없어서 비어 있는 JIS 구(区)에 한글 글리프를 그려 넣었다.
그 글리프가 `font.tmp` 안에 있다. 이미지 파일 하나만 들고 가면 그 자리가 빈칸으로 나온다.

Anex86를 쓸 사람을 위해 같은 내용의 `out\anex86.bmp` 도 함께 만들어 둔다(포맷 동일).

---

## 가장 빠른 길 — 이미 준비된 폴더가 있다

```
out\run\
    np2.exe          에뮬레이터
    np2.ini          설정 (이미 맞춰져 있다)
    xenon_ko.hdi     게임
    font.tmp         폰트
```

`out\run\np2.exe` 를 **더블클릭**하면 끝이다. 30~40초쯤 뒤 타이틀 화면이 뜬다.

빌드할 때마다 이 폴더를 새로 채우려면:

```bash
py tools/build.py --run
```

---

## 직접 구성하는 경우

### 1. 에뮬레이터

**`np2.exe` (Neko Project II, PC-9801)** 를 쓴다.

```
C:\thelife\pc98\np2fmgen\extracted\np2fmgen_260802\np2fmgen\np2.exe
```

> ⚠️ **`np21.exe` 는 안 된다.** PC-9821 + IDE 에뮬레이션이라 이 Anex86 형식(SASI) 이미지를
> 인식하지 못하고 「システムディスクをセットしてください」에서 멈춘다.
> 같은 폴더의 `np2nt.exe` · `np2sx.exe` 도 기종이 달라 권장하지 않는다.

### 2. 폴더 하나에 모으기

에뮬레이터는 **자기가 있는 폴더에서 `font.tmp` 를 찾는다.** 그래서 한곳에 두는 게 편하다.

```
아무폴더\
    np2.exe
    font.tmp        <- out\font.tmp 복사
    xenon_ko.hdi    <- out\xenon_ko.hdi 복사
```

### 3. 하드디스크 연결

`np2.exe` 를 실행하고 메뉴에서:

```
Harddisk  →  HDD #1  →  Open...  →  xenon_ko.hdi 선택
```

그다음 **`Emulate → Reset`**.

`np2.ini` 를 직접 쓰는 방법도 있다(에뮬레이터와 같은 폴더에 둔다).

```ini
[NekoProjectII]
pc_model=VX
clk_base=2457600
clk_mult=4
ExMemory=1
fontfile=
HDD1FILE=C:\경로\xenon_ko.hdi
```

`fontfile=` 은 **비워 둔다.** 비어 있으면 같은 폴더의 `font.tmp` 를 쓴다.
여기에 다른 폰트 경로를 적으면 한글이 깨진다.

### 4. Anex86 를 쓸 경우

```
C:\thelife\pc98\Anex86\extracted\anex86.exe
```

`out\anex86.bmp` 를 Anex86 폴더에 넣고 폰트로 지정한다.
이 이미지의 원래 형식이 Anex86 HDI 라 궁합은 좋지만, 테스트는 `np2.exe` 로만 했다.

---

## 게임 조작

| 키 | 동작 |
|---|---|
| **Enter** | 대사 진행 · 선택 확정 |
| **↑ ↓** | 선택지 이동 |
| Esc | 메뉴 (게임에 따라) |

에뮬레이터 쪽:

| 키 | 동작 |
|---|---|
| **TAB** | 빨리 감기 (토글) |
| Alt+Enter | 전체 화면 |

부팅은 `AUTOEXEC.BAT` 가 자동으로 처리한다.

```
pmd /m10 /v0 /e4 /F /k     사운드 드라이버
ags                        게임 본체
```

---

## 잘 안 될 때

| 증상 | 원인 |
|---|---|
| **한글이 빈칸·깨진 글자로 나옴** | `font.tmp` 가 에뮬레이터 폴더에 없거나, `np2.ini` 의 `fontfile=` 에 다른 폰트가 지정돼 있다 |
| **「システムディスクをセットしてください」** | HDD가 안 붙었다. `np21.exe` 를 쓰고 있지 않은지 확인 |
| **검은 화면이 오래 지속** | 정상이다. 부팅에 25~40초, 인트로 전환 구간에도 검은 화면이 몇 초씩 있다 |
| **소리가 안 남** | `np2.ini` 의 `SNDboard` 설정. 게임 자체는 PMD 드라이버로 FM 음원을 쓴다 |

---

## 세이브 데이터

세이브는 디스크 이미지 안에 쓰인다. 원본을 보존하려면 **`xenon_ko.hdi` 를 복사해서** 쓰는 편이 좋다.

`Xenon-PC98-Translation/saves/` 에 영문판 프로젝트가 남긴 루트별 세이브 파일이 있다.
`XEN.GDT`(1바이트, `7F`면 전체 클리어)를 넣으면 특전이 열린다.

---

## 배포할 때

`xenon_ko.hdi` 와 `font.tmp` 를 **반드시 함께** 넣는다. 폰트가 에뮬레이터 쪽 파일이라
이미지만으로는 한글이 나오지 않는다.

실기 PC-98이나 폰트를 바꿀 수 없는 환경에서는 동작하지 않는다.
자세한 배경은 [`README.md`](README.md) 「왜 폰트 시트가 필요한가」 참조.
