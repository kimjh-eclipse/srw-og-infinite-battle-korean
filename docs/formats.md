# 파일 포맷 명세

## 계층 구조

```
ISO (복호화 리덤프, PS3VOLUME)
└ PS3_GAME/USRDIR/
   ├ EBOOT.BIN            SELF (암호화) — UI/시스템 텍스트
   ├ ps3_game_cpk.sdat    NPD v4 SDAT → CPK (게임 데이터/폰트)
   └ ps3_stream.cpk       CPK (BGM/보이스/영상, 텍스트 없음)
```

설치하면 위 파일이 `dev_hdd0/game/BLJS10248/USRDIR/`(+`cache/`)로 복사된다.

## SDAT → CPK

`ps3_game_cpk.sdat`는 NPD v4 SDAT. 복호화하면 CRI **CPK**(평문 `@UTF` 테이블)가
나온다. 상세 암복호는 [SDAT 암호화](sdat.md) 참조.

CPK TOC(`@UTF`) 컬럼: `DirName`, `FileName`, `FileSize`, `ExtractSize`, `FileOffset`(u48),
`ID`, `UserString`. 파일은 0x800 정렬. `ExtractSize > FileSize`면 **CRILAYLA** 압축.
총 1,640개 파일.

## FPK 컨테이너

CPK 내부 UI/모델 자원은 다시 FPK로 묶여 있다.

```
+0x00  "FPK\0"
+0x04  u32 count
+0x08  u32 entry_off  (= 0x10)
+0x0C  u32 data_off
엔트리(0x50):
  char name[0x40]
  u32  offset       (data_off 상대)
  u32  size
  u32  padded_size  (0x10 정렬)
  u32  zero
```
`ui_dummy.*` 패딩 엔트리가 섞여 있다. 폰트(PGF/GTF)는 `ui/out_game`의 7개 FPK에 수록.

## CSVBv4.3 (텍스트 테이블)

미션·유닛·기체·파츠·기술명, 시스템 문구, ADV 대사가 담긴 주 텍스트 포맷(BE).

```
0x00  "CSVBv4.3"
0x08  u32 ntables
0x0C  u32 colreg_off     컬럼 타입 영역(u32/컬럼)
0x10  u32 strbase_off    문자열 풀 시작
0x14  u32 str_end        사용 풀 끝(절대)
0x18  u32 extra_off      후행 섹션(ADV 바이트코드 등) 시작
0x1C  u32 zero
0x20  테이블 디렉토리(0x28/개):
      char name[0x10]; u32 unk, nrows, rowsize, ncols, coloff, rowsoff(절대)
```
컬럼 크기: `0x06`=1B, `0x05`/`0x1C`=2B, 나머지(`0x02`,`0x03`=float,`0x07`,`0x0A`,
`0x19`=해시,`0x1B`=문자열오프셋)=4B. 문자열은 **UTF-8**(널종료), 오프셋은 strbase 상대.
`mm01.advcmd`만 후행 `extra` 섹션(ADV 바이트코드)에 대사 오프셋을 담는다 →
[텍스트 삽입 기법](text-injection.md).

## 사전 (v1.0.6)

`dictionary/character.cbin`·`glossary.gbin`·`robot.rbin`. 고정 슬롯 구조.

```
0x00  "v1.0.6"
0x20  u32 count
0x74~ 엔트리(고정 stride):
      character/robot: 0x10F8  (name 0x80 + text 0x1000 + 2필드 0x20)
      glossary:        0x10B4  (name 0x80 + text 0x1000)
```
텍스트 UTF-8. 슬롯 여유가 커서 제자리 교체 가능.
