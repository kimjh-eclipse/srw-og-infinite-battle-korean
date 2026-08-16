"""Package the Korean patch as an xdelta against the original ISO.
Produces release/SRW_IB_KR_<ver>/ with the patch, xdelta.exe, and docs.
Run tools/build.py iso <patched.iso> first (SDAT + fSELF spliced)."""
import os, sys, shutil, hashlib, subprocess

WORK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.abspath(os.path.join(WORK, '..'))
ORIG = os.path.join(BASE, 'Super Robot Taisen OG - Infinite Battle (Japan)_ORIGIN.iso')
XDELTA = r'C:\Emul\Switch\패치유틸.xdeltaUI\xdelta.exe'

def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()

def main(ver):
    patched = os.path.join(BASE, f'SRW_IB_KR_{ver}.iso')
    if not os.path.exists(patched):
        sys.exit(f'patched ISO not found: {patched}\n  run: py tools/build.py iso "{patched}"')
    rel = os.path.join(WORK, 'release', f'SRW_IB_KR_{ver}')
    os.makedirs(os.path.join(rel, 'patch'), exist_ok=True)
    xd = os.path.join(rel, 'patch', 'SRW_IB_KR.xdelta')
    print('creating xdelta (this reads both ISOs)...')
    subprocess.run([XDELTA, '-e', '-9', '-f', '-s', ORIG, patched, xd], check=True)
    shutil.copy(XDELTA, os.path.join(rel, 'xdelta.exe'))

    readme = f"""========================================================================
 슈퍼로봇대전 OG INFINITE BATTLE 한국어 패치  ({ver})
========================================================================

■ 적용 대상
  슈퍼로봇대전 OG 인피니트 배틀 일본판 (BLJS10248), 복호화된 ISO
  원본 게임은 본인이 직접 준비해야 합니다. 이 배포물엔 게임 파일이 없습니다.

■ 적용 방법 (xdelta)
  1. RPCS3를 완전히 종료하고 ISO 마운트를 해제합니다.
  2. patch\\apply.bat 를 실행하거나, 명령창에서:
       xdelta.exe -d -s "원본.iso" patch\\SRW_IB_KR.xdelta "SRW_IB_KR.iso"
  3. 생성된 SRW_IB_KR.iso 를 RPCS3에 등록해 실행합니다.

■ 중요: 이미 설치(인스톨)한 적이 있다면
  RPCS3가 게임 데이터를 HDD에 캐시로 설치해 둡니다. 패치 ISO의 새 데이터가
  다시 설치되도록, 아래 폴더가 있으면 그 폴더만 삭제하세요:
     dev_hdd0\\game\\BLJS10248
  삭제 후 패치 ISO로 실행하면 한국어 데이터가 새로 설치됩니다.

■ 패치 내용
  - 전체 텍스트 한국어화: 미션/대사/유닛·기체·파츠·기술명, 도감(캐릭터·기체·용어)
  - 시스템/UI 한국어화: 타이틀 메뉴, 인스톨, 난이도, 옵션 등 (EBOOT)
  - 한글 폰트(맑은 고딕 Bold) 내장

■ 알려진 점
  - RPCS3 전용으로 검증했습니다.
  - 화면이 깨져 보이면 게임을 지우고 SPU 캐시를 지운 뒤 다시 실행하세요.
"""
    open(os.path.join(rel, 'README_설치.txt'), 'w', encoding='utf-8').write(readme)
    open(os.path.join(rel, 'patch', 'apply.bat'), 'w', encoding='utf-8').write(
        '@echo off\r\nset /p ISO=원본 ISO 경로를 입력하세요: \r\n'
        '"%~dp0..\\xdelta.exe" -d -s "%ISO%" "%~dp0SRW_IB_KR.xdelta" "%~dp0..\\SRW_IB_KR.iso"\r\n'
        'echo 완료: SRW_IB_KR.iso\r\npause\r\n')

    sums = os.path.join(rel, 'SHA256SUMS.txt')
    with open(sums, 'w', encoding='utf-8') as f:
        f.write(f'# SRW OG Infinite Battle 한국어 패치 {ver}\n\n')
        f.write(f'원본 ISO  {sha256(ORIG)}\n')
        f.write(f'패치 ISO  {sha256(patched)}\n')
        f.write(f'xdelta    {sha256(xd)}\n')
    print('release ->', rel)
    print('  xdelta:', f'{os.path.getsize(xd):,} bytes')

if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'v1.0')
