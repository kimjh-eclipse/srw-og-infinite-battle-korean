# 빌드 & 배포 파이프라인

## 추출

```
rpcs3 --decrypt ps3_game_cpk.sdat        → .unedat (CPK 평문)   [sdat.py로도 가능]
cpk_extract.py  CPK → extracted/ (1,640 파일, CRILAYLA 해제)
fpk.py          FPK → 내부 파일 (폰트 등)
```

## 텍스트 덤프 & 번역

```
csvb.py dump    CSVB 전체 → text_dump.json
dictbin.py dump 사전 3파일 → dict_*.json
eboot_strings.py EBOOT 문자열 → eboot_strings.json
build_pool.py   고유 문자열 풀 → trans/pool_*.json (용어/문장 분리)
   → 번역 → trans/out_*.json  (jp→ko)
postprocess_trans.py  반각기호 정규화(·→・ 등)
validate_trans.py     제어코드/누락 검증
```

## 폰트 리베이크

```
build_used_chars.py   번역에 쓰인 문자 수집 → used_chars.json
font_rebake.py        PGF/GTF 재구성(used 기반 한글) → font_out/
```

## 재조립

```
apply_all.py     CSVB(자유길이)+advcmd(임의길이)+사전 삽입 → build_stage/
eboot: merge_eboot.py → fix_eboot_length.py → eboot_patch.py → EBOOT_KR.elf
build.py fonts   폰트를 7개 FPK에 주입 → build_stage/
build.py cpk     CPK 재빌드(CRILAYLA 압축, CpkFast/CrilaylaFast.cs) → build_cpk.bin
build.py sdat    SDAT 재암호화(CMAC 위조 포함) → build_ps3_game_cpk.sdat
```

## 배포 (RPCS3 dev_hdd0 패처)

```
make_patcher_release.py:
  패딩 SDAT → xdelta(원본→패치) → 해시 → 패처(SRWIB_Patcher.cs) 상수 갱신·컴파일
  → release/ 조립
```

패처(`SRWIB_Patcher.exe`)는 RPCS3 폴더를 받아 상대경로로 교체한다.

```
dev_hdd0/game/BLJS10248/USRDIR/cache/ps3_game_cpk.sdat  ← sdat.xdelta 적용
dev_hdd0/game/BLJS10248/USRDIR/EBOOT.BIN                ← 복호화+패치 ELF 배치
```

- 원본/결과 SHA 검증, RPCS3 실행 체크, mtime 복원(게임 무결성 검사 대비).
- **원본 백업은 패처 폴더에 저장**(`ps3_game_cpk.sdat.orig`) — dev_hdd0/game/BLJS10248을
  통째로 지우고 재설치해도 복구·재적용 가능.
- 전제: 게임을 한 번 실행해 데이터를 설치(cache 생성)해 둬야 한다.

## 검증 절차

1. 깨끗한 원본에서 `--apply` → 결과 SHA 일치
2. 인게임 부팅 — 타이틀 메뉴/미션 대사/도감/조작 화면에서 별표·누락 점검
3. 별표가 남으면 폰트 글리프 누락(→ used_chars 재수집) 또는 미번역(→ 추출 필터
   보강) 중 하나이므로 원인을 구분해 대응
