# Rebuild ps3_game_cpk (plaintext CPK) with a set of replacement files.
# Strategy: keep TOC @UTF structure intact (row count, strings, columns unchanged);
# only rewrite per-row FileSize/ExtractSize/FileOffset numeric fields, then relay out
# the content region. Non-replaced files keep their original (possibly CRILAYLA) blob;
# replaced files are stored UNCOMPRESSED (ExtractSize == FileSize).
import struct, sys, os, json

ALIGN = 0x800

def read_utf_meta(data):
    assert data[:4] == b'@UTF'
    tsz = struct.unpack('>I', data[4:8])[0]
    base = 8
    rows_off, str_off, data_off = struct.unpack('>III', data[base:base+12])
    ncol, rowlen = struct.unpack('>HH', data[base+16:base+20])
    nrows = struct.unpack('>I', data[base+20:base+24])[0]
    return dict(tsz=tsz, rows_off=base+rows_off, str_off=base+str_off,
                data_off=base+data_off, ncol=ncol, rowlen=rowlen, nrows=nrows)

def cstr(data, str_off, off):
    e = data.index(b'\0', str_off+off)
    return data[str_off+off:e].decode('utf-8', 'replace')

def parse_cols(data, m):
    p = 8 + 24
    cols = []
    for _ in range(m['ncol']):
        flags = data[p]; p += 1
        noff = struct.unpack('>I', data[p:p+4])[0]; p += 4
        name = cstr(data, m['str_off'], noff)
        storage = flags & 0xF0; typ = flags & 0x0F
        sz = [1,1,2,2,4,4,8,8,4,4,4,8][typ]
        const = None
        if storage in (0x30, 0x70):
            const = data[p:p+sz]; p += sz
        cols.append(dict(name=name, flags=flags, storage=storage, typ=typ, sz=sz, const=const))
    return cols

def field_layout(cols):
    """byte offset of each per-row column within a row."""
    off = 0
    lay = {}
    for c in cols:
        if c['storage'] == 0x50:
            lay[c['name']] = (off, c['sz'], c['typ'])
            off += c['sz']
    return lay

def rebuild(cpk_path, repl, out_path, compress=False):
    d = open(cpk_path, 'rb').read()
    assert d[:4] == b'CPK '
    cpk_utf_size = struct.unpack('<Q', d[8:16])[0]
    cpk_utf = d[16:16+cpk_utf_size]
    cm = read_utf_meta(cpk_utf)
    ccols = parse_cols(cpk_utf, cm)
    # header row values
    hdr = {}
    off = 0
    clay = field_layout(ccols)
    for c in ccols:
        if c['storage'] in (0x30, 0x70):
            hdr[c['name']] = c['const']
    def rowval(cols, meta, utf, rowidx, name):
        lay = field_layout(cols)
        o, sz, typ = lay[name]
        p = meta['rows_off'] + rowidx*meta['rowlen'] + o
        raw = utf[p:p+sz]
        return raw
    def as_int(raw):
        return int.from_bytes(raw, 'big')
    TocOffset = as_int(rowval(ccols, cm, cpk_utf, 0, 'TocOffset'))
    ContentOffset = as_int(rowval(ccols, cm, cpk_utf, 0, 'ContentOffset'))
    base = min(TocOffset, ContentOffset)

    toc_hdr = d[TocOffset:TocOffset+16]
    assert toc_hdr[:4] == b'TOC '
    toc_utf_size = struct.unpack('<Q', toc_hdr[8:16])[0]
    toc_utf = bytearray(d[TocOffset+16:TocOffset+16+toc_utf_size])
    tm = read_utf_meta(toc_utf)
    tcols = parse_cols(toc_utf, tm)
    tlay = field_layout(tcols)

    # gather rows
    rows = []
    for i in range(tm['nrows']):
        rbase = tm['rows_off'] + i*tm['rowlen']
        def gv(name):
            o, sz, typ = tlay[name]
            return int.from_bytes(toc_utf[rbase+o:rbase+o+sz], 'big')
        def gs(name):
            o, sz, typ = tlay[name]
            soff = int.from_bytes(toc_utf[rbase+o:rbase+o+sz], 'big')
            return cstr(toc_utf, tm['str_off'], soff)
        dirn = gs('DirName'); fn = gs('FileName')
        path = (dirn + '/' + fn) if dirn else fn
        rows.append(dict(i=i, rbase=rbase, path=path,
                         fsize=gv('FileSize'), esize=gv('ExtractSize'),
                         foff=gv('FileOffset')))

    # build new content
    content = bytearray()
    cur = ContentOffset
    for r in rows:
        if r['path'] in repl:
            v = repl[r['path']]
            # value is either raw bytes, or (stored_blob, extract_size) for pre-compressed
            if isinstance(v, tuple):
                blob, esize = v
            else:
                blob, esize = v, len(v)
            fsize = len(blob)
        else:
            src = base + r['foff']
            blob = d[src:src+r['fsize']]
            fsize = r['fsize']; esize = r['esize']
        # align file start to ALIGN
        if cur % ALIGN:
            padlen = ALIGN - (cur % ALIGN)
            content += b'\0'*padlen
            cur += padlen
        r['new_foff'] = cur - base
        r['new_fsize'] = fsize; r['new_esize'] = esize
        content += blob
        cur += fsize
        # patch TOC numeric fields
        for name, val in (('FileSize', fsize), ('ExtractSize', esize), ('FileOffset', r['new_foff'])):
            o, sz, typ = tlay[name]
            toc_utf[r['rbase']+o:r['rbase']+o+sz] = val.to_bytes(sz, 'big')

    # reassemble: [0 .. TocOffset) header | TOC(updated) | pad to ContentOffset | content
    out = bytearray()
    out += d[:TocOffset]
    new_toc = toc_hdr + bytes(toc_utf)
    # original toc block was padded to ContentOffset; keep same region size
    out += new_toc
    # pad from (TocOffset+len(new_toc)) up to ContentOffset
    here = TocOffset + len(new_toc)
    assert here <= ContentOffset, (hex(here), hex(ContentOffset))
    out += d[here:ContentOffset]  # original padding bytes (usually zeros / ETOC?) -- keep
    assert len(out) == ContentOffset, (hex(len(out)), hex(ContentOffset))
    out += content
    open(out_path, 'wb').write(bytes(out))
    print(f'rebuilt {out_path}: {len(rows)} files, {len(repl)} replaced, size {len(out):#x} (orig {len(d):#x})')

if __name__ == '__main__':
    # smoke test: rebuild with zero replacements, compare content region parses
    cpk = sys.argv[1] if len(sys.argv) > 1 else 'ps3_game_cpk.sdat.unedat'
    rebuild(cpk, {}, 'cpk_rebuilt_test.bin')
