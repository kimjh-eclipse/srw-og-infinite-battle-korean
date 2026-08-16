"""Apply the full jp->ko translation dictionary to every text container, then stage
the rebuilt files under build_stage/ for build.py.

Sources:
  - trans/out_term_*.json + trans/out_text_*.json  (merged jp->ko)
  - eboot_ko.json  (EBOOT UI, applied separately by eboot_patch.py)

Targets:
  - CSVB *.prm / *.bin  (row strings; free length)   -> build_stage/<path>
  - mm01.advcmd         (ADV dialogue; in-place, length-limited)
  - dictionaries        (fixed slot, length-limited)
  - EBOOT               (handled by eboot_patch.py)
"""
import json, os, sys, glob, struct
sys.path.insert(0, 'tools')
import csvb, dictbin

WORK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAGE = os.path.join(WORK, 'build_stage')
EXTRACTED = os.path.join(WORK, 'extracted')

def load_dict():
    tl = {}
    for f in sorted(glob.glob(os.path.join(WORK, 'trans', 'out_term_*.json'))) + \
             sorted(glob.glob(os.path.join(WORK, 'trans', 'out_text_*.json'))):
        d = json.load(open(f, encoding='utf-8'))
        tl.update(d)
    return tl

def stage_path(rel):
    p = os.path.join(STAGE, rel.replace('/', os.sep))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    return p

def enc_len(s): return len(s.encode('utf-8'))

def apply_csvb(tl, report):
    j = json.load(open(os.path.join(WORK, 'text_dump.json'), encoding='utf-8'))
    for rel, rows in j.items():
        src = os.path.join(EXTRACTED, rel.replace('/', os.sep))
        trans = {}
        for r in rows:
            ko = tl.get(r['text'])
            if ko is not None and ko != r['text']:
                trans[(r['table'], r['row'], r['col'])] = ko
        if not trans:
            continue
        out = stage_path(rel)
        csvb.rebuild(src, trans, out)
        report.append(f'CSVB {rel}: {len(trans)} strings')

def apply_advcmd(tl, report):
    # Arbitrary-length dialogue insertion (pool append + bytecode offset repoint),
    # so translations longer than the original are not skipped.
    rel = 'mission/mm01.advcmd'
    src = os.path.join(EXTRACTED, 'mission', 'mm01.advcmd')
    out = stage_path(rel)
    n = csvb.rebuild_advcmd(src, tl, out)
    report.append(f'advcmd mm01: {n} dialogue offsets repointed (arbitrary length)')

def apply_dict(tl, report):
    for fn in ['character.cbin', 'glossary.gbin', 'robot.rbin']:
        src = os.path.join(EXTRACTED, 'dictionary', fn)
        entries = dictbin.dump(src)
        lay = dictbin.LAYOUT[fn]
        changed = []
        skipped = 0
        for ent in entries:
            new = {'index': ent['index']}
            hit = False
            for fname, foff, fsize in lay['fields']:
                v = ent.get(fname, '')
                ko = tl.get(v)
                if ko and ko != v:
                    if enc_len(ko) < fsize:
                        new[fname] = ko; hit = True
                    else:
                        skipped += 1
            if hit:
                changed.append(new)
        if changed:
            out = stage_path('dictionary/' + fn)
            dictbin.insert(src, changed, out)
            report.append(f'dict {fn}: {len(changed)} entries ({skipped} too-long skipped)')

if __name__ == '__main__':
    tl = load_dict()
    print(f'translation dict: {len(tl)} entries')
    report = []
    apply_csvb(tl, report)
    apply_advcmd(tl, report)
    apply_dict(tl, report)
    for r in report:
        print(' ', r)
    print('staged under build_stage/. Now run: py tools/build.py fonts / cpk / sdat')
