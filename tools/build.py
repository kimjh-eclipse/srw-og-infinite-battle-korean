"""Full patch build: fonts + translated text -> FPK -> CPK -> SDAT -> ISO splice.

Usage:
  py tools/build.py fonts          # inject rebaked fonts into the 7 ui/out_game FPKs
  py tools/build.py cpk            # rebuild CPK with all staged replacements
  py tools/build.py sdat           # encrypt rebuilt CPK to SDAT
  py tools/build.py iso <out.iso>  # splice SDAT into a copy of the ISO
  py tools/build.py all <out.iso>
Staged replacements live in build_stage/<cpk path>.
"""
import os, sys, struct, shutil, json
sys.path.insert(0, os.path.dirname(__file__))
import fpk as FPK
import cpk_rebuild as CR
import sdat as SDAT

WORK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAGE = os.path.join(WORK, 'build_stage')
EXTRACTED = os.path.join(WORK, 'extracted')
UNEDAT = os.path.join(WORK, 'ps3_game_cpk.sdat.unedat')
ORIG_SDAT = os.path.join(WORK, 'ps3_game_cpk.sdat')
OUT_CPK = os.path.join(WORK, 'build_cpk.bin')
OUT_SDAT = os.path.join(WORK, 'build_ps3_game_cpk.sdat')

FONT_FPKS = ['ui/out_game/ingame.fpk', 'ui/out_game/mapmode.fpk',
             'ui/out_game/outgame_mcnsel.fpk', 'ui/out_game/outgame_result.fpk',
             'ui/out_game/outgame_talk.fpk', 'ui/out_game/outgame_test.fpk',
             'ui/out_game/outgame_title.fpk']
FONT_NAMES = ['default', 'nakamaru16']   # nakamaru14/sogei unchanged (no kanji)

def stage_path(rel):
    p = os.path.join(STAGE, rel.replace('/', os.sep))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    return p

def src_path(rel):
    """Latest version of a CPK member: staged if present, else original."""
    p = os.path.join(STAGE, rel.replace('/', os.sep))
    return p if os.path.exists(p) else os.path.join(EXTRACTED, rel.replace('/', os.sep))

def do_fonts():
    repl = {}
    for n in FONT_NAMES:
        for ext in ('pgf', 'gtf'):
            f = os.path.join(WORK, 'font_out', f'{n}.{ext}')
            if not os.path.exists(f):
                sys.exit(f'missing {f} — run tools/font_rebake.py first')
            repl[f'{n}.{ext}'] = open(f, 'rb').read()
    for rel in FONT_FPKS:
        src = src_path(rel)
        _, _, _, ents = FPK.parse(open(src, 'rb').read())
        names = {e['name'] for e in ents}
        use = {k: v for k, v in repl.items() if k in names}
        out = stage_path(rel)
        size = FPK.rebuild(src, use, out)
        print(f'  {rel}: replaced {sorted(use)} -> {size:,} bytes '
              f'(orig {os.path.getsize(os.path.join(EXTRACTED, rel.replace("/", os.sep))):,})')

def collect_replacements():
    repl = {}
    if not os.path.isdir(STAGE):
        return repl
    for dirpath, _, files in os.walk(STAGE):
        for fn in files:
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, STAGE).replace(os.sep, '/')
            repl[rel] = open(p, 'rb').read()
    return repl

def compress_staged():
    """Pre-compress staged files with the fast C# CRILAYLA encoder (via PowerShell)."""
    import subprocess, tempfile
    cs = os.path.join(os.path.dirname(__file__), 'CrilaylaFast.cs')
    cache = os.path.join(WORK, 'build_cache')
    os.makedirs(cache, exist_ok=True)
    repl = collect_replacements()
    jobs = []
    for rel, blob in repl.items():
        if len(blob) <= 0x100: continue
        src = os.path.join(STAGE, rel.replace('/', os.sep))
        dst = os.path.join(cache, rel.replace('/', '_') + '.cri')
        if not os.path.exists(dst) or os.path.getmtime(dst) < os.path.getmtime(src):
            jobs.append((src, dst))
    if jobs:
        script = ("Add-Type -TypeDefinition (Get-Content '%s' -Raw); " % cs) + '; '.join(
            f"[CrilaylaFast]::CompressFile('{s}','{d}')" for s, d in jobs)
        subprocess.run(['powershell', '-NoProfile', '-Command', script], check=True)
    out = {}
    for rel, blob in repl.items():
        dst = os.path.join(cache, rel.replace('/', '_') + '.cri')
        if os.path.exists(dst) and os.path.getsize(dst) < len(blob):
            out[rel] = ('cri', open(dst, 'rb').read(), len(blob))
        else:
            out[rel] = ('raw', blob, len(blob))
    return out

def do_cpk():
    staged = compress_staged()
    print(f'  staged replacements: {len(staged)}')
    repl = {}
    for rel, (kind, blob, esize) in sorted(staged.items()):
        print(f'    {rel}: {esize:,} -> {len(blob):,} ({kind})')
        repl[rel] = (blob, esize)
    CR.rebuild(UNEDAT, repl, OUT_CPK)

def do_sdat():
    plain = open(OUT_CPK, 'rb').read()
    n = SDAT.encrypt(plain, ORIG_SDAT, OUT_SDAT)
    orig = os.path.getsize(ORIG_SDAT)
    print(f'  SDAT {n:,} bytes (orig {orig:,}, delta {n-orig:+,})')
    if n > orig:
        print('  WARNING: larger than original — ISO splice needs same-or-smaller size')
    return n

def do_iso(out_iso):
    # Always splice onto the pristine dump. The plain-named ISO is the *patched*
    # one in this working set, so _ORIGIN is the authoritative source.
    base = os.path.abspath(os.path.join(WORK, '..'))
    for cand in ('Super Robot Taisen OG - Infinite Battle (Japan)_ORIGIN.iso',
                 'Super Robot Taisen OG - Infinite Battle (Japan).iso'):
        src_iso = os.path.join(base, cand)
        if os.path.exists(src_iso):
            break
    else:
        sys.exit('source ISO not found')
    # refuse to build from an already-patched image
    with open(src_iso, 'rb') as f:
        f.seek(0x302B4000 + 0x88)
        fsz = struct.unpack('>Q', f.read(8))[0]
    if fsz != 0x23B707D0:
        sys.exit(f'{os.path.basename(src_iso)} is not a pristine dump '
                 f'(inner sdat file_size={fsz:#x}); expected 0x23B707D0')
    print(f'  source: {os.path.basename(src_iso)}')
    # locate the sdat payload inside the ISO by scanning for its NPD header + size
    orig = open(ORIG_SDAT, 'rb').read(0x100)
    with open(src_iso, 'rb') as f:
        data = f.read()
    idx = data.find(orig[:0x80])
    if idx < 0:
        sys.exit('could not locate ps3_game_cpk.sdat inside ISO')
    orig_size = os.path.getsize(ORIG_SDAT)
    new = open(OUT_SDAT, 'rb').read()
    if len(new) > orig_size:
        sys.exit(f'new SDAT larger than original ({len(new)} > {orig_size}); shrink payload')
    print(f'  found sdat at {idx:#x}, replacing {orig_size:,} bytes with {len(new):,}')
    shutil.copyfile(src_iso, out_iso)
    with open(out_iso, 'r+b') as f:
        f.seek(idx)
        f.write(new)
        if len(new) < orig_size:
            f.write(b'\0' * (orig_size - len(new)))
    print(f'  wrote {out_iso}')
    # Build the compressed fSELF and splice it into the ORIGINAL EBOOT.BIN slot,
    # so the ISO size and all three filesystems (ISO9660/Joliet/UDF) stay intact.
    import mkfself
    self_path = os.path.join(WORK, 'EBOOT_KR.self')
    mkfself.make(os.path.join(WORK, 'EBOOT_KR.elf'), self_path, compress=True)
    splice_eboot(out_iso, self_path)

def splice_eboot(iso_path, self_path):
    """Overwrite the EBOOT.BIN payload in place with the fSELF. Requires the fSELF to
    be <= the original slot (aligned to 2048). The disc's EBOOT.BIN is located by its
    directory record; the byte payload sits at ext_lba*2048."""
    import iso9660
    SEC = iso9660.SECTOR
    iso = iso9660.Iso(iso_path)
    lba, size, rec_off = iso.find('PS3_GAME/USRDIR/EBOOT.BIN')
    iso.close()
    data = open(self_path, 'rb').read()
    slot = align_slot(size)
    if len(data) > slot:
        sys.exit(f'fSELF {len(data)} exceeds EBOOT slot {slot}')
    with open(iso_path, 'r+b') as f:
        f.seek(lba * SEC)
        f.write(data)
        if len(data) < slot:
            f.write(b'\0' * (slot - len(data)))
    iso9660.patch_record(iso_path, rec_off, lba, len(data))
    print(f'  EBOOT.BIN replaced in place: fSELF {len(data):,} into slot {slot:,} '
          f'(orig {size:,})')

def align_slot(size):
    return (size + 2047) & ~2047

if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd in ('fonts', 'all'): print('[fonts]'); do_fonts()
    if cmd in ('cpk', 'all'):   print('[cpk]');   do_cpk()
    if cmd in ('sdat', 'all'):  print('[sdat]');  do_sdat()
    if cmd in ('iso', 'all'):   print('[iso]');   do_iso(sys.argv[2])
