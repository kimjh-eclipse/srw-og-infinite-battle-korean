# 슈퍼로봇대전 OG INFINITE BATTLE 한국어화 — 기술 문서

PS3 『スーパーロボット大戦OG INFINITE BATTLE』(BLJS10248) 비공식 한국어화 과정에서
역공학으로 규명한 파일 포맷, 폰트 시스템, SDAT 암호화, 텍스트/폰트 주입 기법과
빌드 파이프라인을 정리한다. 실행 환경은 RPCS3.

- 도구 소스: [저장소 루트](https://github.com/kimjh-eclipse/srw-og-infinite-battle-korean)

## 문서 구성

| 문서 | 내용 |
|---|---|
| [파일 포맷 명세](formats.md) | SDAT→CPK→FPK, CSVBv4.3 테이블, v1.0.6 사전 바이너리 레이아웃 |
| [폰트 시스템](fonts.md) | 커스텀 PGF + GTF(8bpp) 글리프 아틀라스, 레코드 구조, 한글 리베이크 |
| [SDAT 암호화](sdat.md) | NPD v4 SDAT 블록 암복호(AES-CBC/HMAC/CMAC), 재암호화 |
| [텍스트 삽입 기법](text-injection.md) | CSVB 문자열 풀, ADV 대사 임의길이 재삽입, 사전, EBOOT UI |
| [빌드 & 배포 파이프라인](pipeline.md) | 추출→번역→재조립→SDAT→RPCS3 dev_hdd0 패처 |

## 배포 방식 요약

RPCS3에 설치된 게임 데이터(`dev_hdd0/game/BLJS10248`)의 SDAT와 EBOOT를 교체하는
패처로 배포한다. ISO의 SDAT는 원본과 크기가 같아 splice가 가능하지만, EBOOT는
RPCS3가 fake SELF에 정식 암호화 메타데이터를 요구하므로 ISO에 넣지 않고 dev_hdd0에
복호화 ELF로 배치한다(RPCS3는 dev_hdd0의 평문 ELF를 그대로 실행).

## 법적 고지

이 문서와 저장소는 **원본 게임에서 추출한 텍스트·이미지·번역 대역 데이터를 포함하지 않는다.**
문서 내 바이너리 오프셋/구조 명세는 상호운용을 위한 사실 정보이며, 패치 적용에는 본인이
합법적으로 소유한 원본이 필요하다. 게임의 저작권은 반프레스토/반다이남코에 있다.
