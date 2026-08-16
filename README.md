# SRW OG Infinite Battle — 한국어화 도구

슈퍼로봇대전 OG INFINITE BATTLE (PS3 일본판, BLJS10248)을 한국어화하기 위해
작성한 리버스 엔지니어링 / 리패킹 도구 모음입니다. RPCS3 환경을 대상으로 합니다.

> ⚠️ 이 저장소에는 **게임 파일이 전혀 포함되어 있지 않습니다.** 원본 게임 데이터,
> 복호화된 실행 파일, 번역 텍스트, 패치 바이너리(xdelta/SDAT/EBOOT)는 배포하지
> 않습니다. 여기 있는 것은 **포맷을 다루는 파이썬/C# 도구 소스뿐**이며, 사용하려면
> 본인이 정당하게 소유한 게임에서 직접 데이터를 추출해야 합니다.

## 파이프라인 개요

```
SDAT(NPD) ─복호화→ CPK ─추출→ FPK / CSVB / 사전 / 폰트(PGF·GTF)
                                   │
                          텍스트·폰트 한글화
                                   │
CPK 재빌드 ─CRILAYLA압축→ SDAT 재암호화 → dev_hdd0 배치(패처)
```

## 도구 (tools/)

**컨테이너 / 아카이브**
- `cpk_extract.py`, `cpk_rebuild.py`, `cpk_verify.py`, `cpk_verify_fast.py`, `cpk_probe.py` — CRI CPK 파서/리빌더 (@UTF TOC)
- `fpk.py` — FPK 컨테이너 파서/리빌더
- `crilayla.py` / `CrilaylaFast.cs` — CRILAYLA 압축·해제 (C#은 고속 인코더)
- `CpkFast.cs` — CPK 고속 추출 헬퍼

**암호화**
- `sdat.py` — PS3 SDAT(NPD v4) 복호화·재암호화 (블록 HMAC, CMAC 포함)
- `mkfself.py`, `unfself.py` — fake SELF 생성/해석 (연구용)

**텍스트**
- `csvb.py` — CSVBv4.3 테이블 텍스트 덤프/재삽입 + advcmd(ADV 대사) 임의길이 재삽입
- `dictbin.py` — 사전(v1.0.6 cbin/gbin/rbin) 덤프/삽입
- `eboot_strings.py`, `eboot_patch.py`, `merge_eboot.py`, `fix_eboot_length.py` — EBOOT UI 문자열 추출/패치/길이보정
- `build_pool.py`, `postprocess_trans.py`, `validate_trans.py` — 번역 풀 생성/후처리/검증
- `apply_all.py` — 번역 일괄 삽입

**폰트**
- `font_rebake.py` — PGF+GTF 글리프 아틀라스 재구성 (사용 글자 기반 한글 리베이크)
- `build_used_chars.py` — 실제 사용 문자 수집

**빌드 / 배포**
- `build.py` — fonts → cpk → sdat → iso 파이프라인
- `deploy_cache.py` — RPCS3 dev_hdd0 캐시 배포
- `make_release.py`, `make_patcher_release.py` — 릴리스 패키징
- `iso9660.py` — ISO9660 탐색/레코드 패치
- `SRWIB_Patcher.cs` — 배포용 패처 (RPCS3 dev_hdd0 파일 교체, GUI/CLI)

## 라이선스 / 면책

도구 소스는 상호운용·팬 번역 목적의 리버스 엔지니어링 결과물입니다. 게임의 저작권은
반프레스토/반다이남코에 있으며, 이 저장소는 게임 자산을 포함하거나 배포하지 않습니다.
