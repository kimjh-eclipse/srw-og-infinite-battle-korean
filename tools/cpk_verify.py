# Verify a rebuilt CPK extracts byte-identical files vs the original.
import sys, struct, hashlib
sys.path.insert(0, 'tools')
import cpk_extract as CE

def toc_rows(path):
    f = open(path, 'rb')
    hdr = f.read(16)
    utf_size = struct.unpack('<Q', hdr[8:16])[0]
    f.seek(16)
    h = CE.read_utf(f.read(utf_size))[0]
    toc_off, content_off = h['TocOffset'], h['ContentOffset']
    base = min(toc_off, content_off)
    f.seek(toc_off)
    th = f.read(16)
    tsz = struct.unpack('<Q', th[8:16])[0]
    rows = CE.read_utf(f.read(tsz))
    out = []
    for r in rows:
        dn = r.get('DirName') or ''
        p = f'{dn}/{r["FileName"]}' if dn else r['FileName']
        out.append((p, r['FileSize'], r.get('ExtractSize') or r['FileSize'], base + r['FileOffset']))
    return f, out

fa, ra = toc_rows(sys.argv[1])
fb, rb = toc_rows(sys.argv[2])
assert len(ra) == len(rb), (len(ra), len(rb))
bad = 0
for (pa, sa, ea, oa), (pb, sb, eb, ob) in zip(ra, rb):
    assert pa == pb, (pa, pb)
    fa.seek(oa); da = fa.read(sa)
    fb.seek(ob); db = fb.read(sb)
    if ea > sa and da[:8] == b'CRILAYLA': da = CE.crilayla_decompress(da)
    if eb > sb and db[:8] == b'CRILAYLA': db = CE.crilayla_decompress(db)
    if da != db:
        print('MISMATCH', pa, len(da), len(db)); bad += 1
        if bad > 5: break
print('files', len(ra), 'mismatches', bad)
