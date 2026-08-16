"""One-shot: pad SDAT -> xdelta -> hashes -> patch patcher hash constants -> compile
-> assemble release/SRW_IB_KR_v1.0. Run after build.py sdat."""
import os, struct, subprocess, hashlib, shutil, re

WORK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XDELTA = r'C:\Emul\Switch\패치유틸.xdeltaUI\xdelta.exe'
CSC = r'C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe'
ORIG_SDAT = os.path.join(WORK, 'ps3_game_cpk.sdat')
BUILD_SDAT = os.path.join(WORK, 'build_ps3_game_cpk.sdat')
EBOOT = os.path.join(WORK, 'EBOOT_KR.elf')
STAGE = os.path.join(WORK, 'release_stage')
PATCHER_DIR = os.path.join(WORK, 'patcher')
REL = os.path.join(WORK, 'release', 'SRW_IB_KR_v1.0')
SDAT_SIZE = 600368256

def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest().upper()

os.makedirs(STAGE, exist_ok=True)
# pad SDAT to original size
tgt = os.path.join(STAGE, 'ps3_game_cpk.sdat')
data = open(BUILD_SDAT, 'rb').read()
with open(tgt, 'wb') as f:
    f.write(data)
    if len(data) < SDAT_SIZE:
        f.write(b'\0' * (SDAT_SIZE - len(data)))
shutil.copy(EBOOT, os.path.join(STAGE, 'EBOOT.BIN'))
print('padded SDAT + EBOOT staged')

# xdelta
xd = os.path.join(STAGE, 'sdat.xdelta')
print('xdelta 생성 중...')
subprocess.run([XDELTA, '-e', '-9', '-f', '-s', ORIG_SDAT, tgt, xd], check=True)

h_sdat = sha(tgt); h_eboot = sha(os.path.join(STAGE, 'EBOOT.BIN'))
h_orig = sha(ORIG_SDAT)
print('SDAT_KO ', h_sdat)
print('EBOOT_KO', h_eboot)
print('xdelta  ', sha(xd), os.path.getsize(xd))

# patch patcher constants
cs = os.path.join(PATCHER_DIR, 'SRWIB_Patcher.cs')
src = open(cs, encoding='utf-8').read()
src = re.sub(r'(SHA_SDAT_ORIG\s*=\s*")[0-9A-Fa-f]+(")', r'\g<1>' + h_orig + r'\2', src)
src = re.sub(r'(SHA_SDAT_KO\s*=\s*")[0-9A-Fa-f]+(")', r'\g<1>' + h_sdat + r'\2', src)
src = re.sub(r'(SHA_EBOOT_KO\s*=\s*")[0-9A-Fa-f]+(")', r'\g<1>' + h_eboot + r'\2', src)
open(cs, 'w', encoding='utf-8').write(src)
print('patcher 상수 갱신')

# compile
exe = os.path.join(PATCHER_DIR, 'SRWIB_Patcher.exe')
subprocess.run([CSC, '/nologo', '/optimize+', '/target:winexe', '/out:' + exe,
                '/reference:System.Windows.Forms.dll', '/reference:System.Drawing.dll', cs], check=True)
print('patcher 컴파일 완료')

# assemble release
os.makedirs(REL, exist_ok=True)
for f in ['sdat.xdelta']:
    shutil.copy(os.path.join(STAGE, f), os.path.join(REL, f))
shutil.copy(os.path.join(STAGE, 'EBOOT.BIN'), os.path.join(REL, 'EBOOT.BIN'))
shutil.copy(exe, os.path.join(REL, 'SRWIB_Patcher.exe'))
shutil.copy(XDELTA, os.path.join(REL, 'xdelta.exe'))
if os.path.exists(os.path.join(PATCHER_DIR, 'README_설치.txt')):
    shutil.copy(os.path.join(PATCHER_DIR, 'README_설치.txt'), os.path.join(REL, 'README_설치.txt'))
# refresh patcher dir payloads too
shutil.copy(os.path.join(STAGE, 'sdat.xdelta'), os.path.join(PATCHER_DIR, 'sdat.xdelta'))
shutil.copy(os.path.join(STAGE, 'EBOOT.BIN'), os.path.join(PATCHER_DIR, 'EBOOT.BIN'))

sums = '# 슈퍼로봇대전 OG 인피니트 배틀 한국어 패치 v1.0 - 파일 해시\n\n'
for f in sorted(os.listdir(REL)):
    if f == 'SHA256SUMS.txt': continue
    sums += '%s  %s\n' % (sha(os.path.join(REL, f)), f)
sums += '\n# 적용 후 게임 파일\nSDAT(패치)  %s\nEBOOT(패치) %s\nSDAT(원본)  %s\n' % (h_sdat, h_eboot, h_orig)
open(os.path.join(REL, 'SHA256SUMS.txt'), 'w', encoding='utf-8').write(sums)
print('release ->', REL)
