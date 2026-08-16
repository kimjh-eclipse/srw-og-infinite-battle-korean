"""Fast iteration: drop the built SDAT straight into the RPCS3 HDD install cache,
padded to the original size and with the original mtime restored (the game checks
file mtime, not content hash). No re-install needed.

Usage: py tools/deploy_cache.py [restore]
"""
import os, sys, shutil, struct

WORK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILT = os.path.join(WORK, 'build_ps3_game_cpk.sdat')
CACHE = (r'C:\Emul\PS3\rpcs3-v0.0.27-14986-db7f84f9_win64'
         r'\dev_hdd0\game\BLJS10248\USRDIR\cache\ps3_game_cpk.sdat')
BAK = CACHE + '.orig'

def deploy():
    if not os.path.exists(CACHE):
        sys.exit(f'cache not found (install the game once first):\n  {CACHE}')
    if not os.path.exists(BAK):
        shutil.copy2(CACHE, BAK)          # copy2 preserves mtime
        print(f'backed up original -> {BAK}')
    orig_size = os.path.getsize(BAK)
    orig_stat = os.stat(BAK)
    built = open(BUILT, 'rb').read()
    allow_larger = len(sys.argv) > 1 and sys.argv[1] == 'force'
    if len(built) > orig_size and not allow_larger:
        sys.exit(f'built SDAT larger than original ({len(built)} > {orig_size}); '
                 f'pass "force" to deploy anyway (cache only — ISO splice still needs <=)')
    with open(CACHE, 'wb') as f:
        f.write(built)
        if len(built) < orig_size:
            f.write(b'\0' * (orig_size - len(built)))
    os.utime(CACHE, (orig_stat.st_atime, orig_stat.st_mtime))   # restore mtime
    note = '' if len(built) <= orig_size else f' (LARGER than orig by {len(built)-orig_size:,})'
    print(f'deployed {len(built):,}B{note}; mtime restored')

def restore():
    if not os.path.exists(BAK):
        sys.exit('no backup to restore')
    st = os.stat(BAK)
    shutil.copyfile(BAK, CACHE)
    os.utime(CACHE, (st.st_atime, st.st_mtime))
    print('original cache restored')

if __name__ == '__main__':
    (restore if len(sys.argv) > 1 and sys.argv[1] == 'restore' else deploy)()
