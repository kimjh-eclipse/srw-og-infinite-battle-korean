# CSVBv4.3 parser/dumper/rebuilder
# Layout (all BE):
#   0x00 magic "CSVBv4.3"
#   0x08 u32 ntables
#   0x0C u32 colreg_off   (column-type region, u32 per column, per-table at entry.coloff)
#   0x10 u32 strbase_off  (string pool base)
#   0x14 u32 str_end      (absolute end of used string pool)
#   0x18 u32 extra_off    (absolute offset of trailing section; == str_end if none/gap)
#   0x1C u32 zero
#   0x20 table dir: ntables * 0x28 { char name[0x10]; u32 unk; u32 nrows; u32 rowsize;
#                                    u32 ncols; u32 coloff; u32 rowsoff(abs) }
# Column types: 2-byte: 0x05, 0x1C ; 4-byte others. 0x1B = string offset (rel strbase).
import struct, sys, os, json

SIZE2 = {0x05, 0x1C}
SIZE1 = {0x06}

def col_size(t):
    if t in SIZE1: return 1
    return 2 if t in SIZE2 else 4

class Table:
    pass

def parse(path):
    d = open(path, 'rb').read()
    assert d[:8] == b'CSVBv4.3', d[:8]
    ntab, colreg, strbase, strend, extra, zero = struct.unpack('>6I', d[8:32])
    tables = []
    for t in range(ntab):
        off = 0x20 + t * 0x28
        tb = Table()
        tb.name = d[off:off+0x10].split(b'\0')[0].decode()
        (tb.unk, tb.nrows, tb.rowsize, tb.ncols, tb.coloff, tb.rowsoff) = struct.unpack('>6I', d[off+0x10:off+0x28])
        tb.types = struct.unpack('>%dI' % tb.ncols, d[colreg+tb.coloff*1 if False else colreg+tb.coloff : colreg+tb.coloff+4*tb.ncols])
        # sanity: sum of col sizes == rowsize
        s = sum(col_size(x) for x in tb.types)
        assert s == tb.rowsize, (path, tb.name, s, tb.rowsize)
        tables.append(tb)
    return d, ntab, colreg, strbase, strend, extra, tables

def read_str(d, strbase, off):
    p = strbase + off
    e = d.index(b'\0', p)
    return d[p:e].decode('utf-8')

def dump(path):
    d, ntab, colreg, strbase, strend, extra, tables = parse(path)
    out = []
    for tb in tables:
        for r in range(tb.nrows):
            p = tb.rowsoff + r * tb.rowsize
            for ci, t in enumerate(tb.types):
                sz = col_size(t)
                if t == 0x1B:
                    off = struct.unpack('>I', d[p:p+4])[0]
                    if off != 0xFFFFFFFF:
                        s = read_str(d, strbase, off)
                        if s:
                            out.append({'table': tb.name, 'row': r, 'col': ci, 'text': s})
                p += sz
    return out

def rebuild(path, trans, out_path):
    """trans: dict (table,row,col)->new text.
    Safe policy: original string pool is preserved byte-for-byte (all old offsets
    stay valid for any hidden referrers, e.g. advcmd bytecode). Translated strings
    are appended after the original pool and only row cells (type 0x1B) re-point.
    """
    d, ntab, colreg, strbase, strend, extra, tables = parse(path)
    d = bytearray(d)
    pool = bytearray(d[strbase:strend])    # original pool preserved
    memo = {}
    def intern(s):
        if s in memo: return memo[s]
        off = len(pool)
        pool.extend(s.encode('utf-8') + b'\0')
        memo[s] = off
        return off
    for tb in tables:
        for r in range(tb.nrows):
            p = tb.rowsoff + r * tb.rowsize
            for ci, t in enumerate(tb.types):
                sz = col_size(t)
                if t == 0x1B:
                    off = struct.unpack('>I', bytes(d[p:p+4]))[0]
                    if off != 0xFFFFFFFF:
                        s = trans.get((tb.name, r, ci))
                        if s is not None:
                            struct.pack_into('>I', d, p, intern(s))
                p += sz
    # align pool to 4
    while len(pool) % 4: pool.append(0)
    new_strend = strbase + len(pool)
    gap = bytes(d[strend:extra])           # preserved gap (zeros / '011B' filler)
    tail = bytes(d[extra:])                # trailing section (bytecode etc.)
    new_extra = new_strend + len(gap)
    out = bytearray(d[:strbase]) + pool + gap + tail
    struct.pack_into('>I', out, 0x14, new_strend)
    struct.pack_into('>I', out, 0x18, new_extra)
    open(out_path, 'wb').write(bytes(out))

def rebuild_advcmd(path, trans, out_path):
    """mm01.advcmd: dialogue strings are referenced by u32 offsets (relative to strbase)
    embedded in the trailing bytecode section. Append translated strings to the pool and
    repoint those offset fields -> arbitrary-length translation, no in-place limit.
    trans: {jp_text: ko_text}."""
    d = open(path, 'rb').read()
    ntab, colreg, strbase, strend, extra, zero = struct.unpack('>6I', d[8:32])
    # map pool offset -> original string
    starts = {}
    p = strbase
    while p < strend:
        e = d.index(b'\0', p)
        try:
            starts[p - strbase] = d[p:e].decode('utf-8')
        except UnicodeDecodeError:
            pass
        p = e + 1
    pool = bytearray(d[strbase:strend])   # preserve original pool (row/other refs stay valid)
    memo = {}
    def intern(s):
        if s in memo:
            return memo[s]
        off = len(pool)
        pool.extend(s.encode('utf-8') + b'\0')
        memo[s] = off
        return off
    out = bytearray(d)
    # scan bytecode section for u32 fields that point at a translatable dialogue string
    p = extra
    n = 0
    while p + 4 <= len(d):
        v = struct.unpack('>I', out[p:p+4])[0]
        s = starts.get(v)
        if s:
            ko = trans.get(s)
            if ko and ko != s:
                struct.pack_into('>I', out, p, intern(ko))
                n += 1
        p += 4
    while len(pool) % 4:
        pool.append(0)
    new_strend = strbase + len(pool)
    gap = bytes(d[strend:extra])
    tail = bytes(out[extra:])
    new_extra = new_strend + len(gap)
    res = bytearray(out[:strbase]) + pool + gap + tail
    struct.pack_into('>I', res, 0x14, new_strend)
    struct.pack_into('>I', res, 0x18, new_extra)
    open(out_path, 'wb').write(bytes(res))
    return n

def patch_inplace(path, replacements, out_path):
    """For bytecode-referenced strings (advcmd): overwrite string bytes in place.
    replacements: dict old_text -> new_text. New UTF-8 must fit in old slot."""
    d = bytearray(open(path, 'rb').read())
    ntab, colreg, strbase, strend, extra, zero = struct.unpack('>6I', d[8:32])
    p = strbase
    n = 0
    while p < strend:
        e = d.index(b'\0', p)
        try: s = d[p:e].decode('utf-8')
        except UnicodeDecodeError: s = None
        if s is not None and s in replacements:
            nb = replacements[s].encode('utf-8')
            if len(nb) > e - p:
                raise ValueError(f'too long: {s!r} -> {replacements[s]!r} ({len(nb)} > {e-p})')
            d[p:e] = nb + b'\0' * (e - p - len(nb))
            n += 1
        p = e + 1
    open(out_path, 'wb').write(bytes(d))
    return n

if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'dump':
        root, outjson = sys.argv[2], sys.argv[3]
        result = {}
        total = 0
        for dirpath, _, files in os.walk(root):
            for fn in files:
                p = os.path.join(dirpath, fn)
                with open(p, 'rb') as f:
                    if f.read(8) != b'CSVBv4.3': continue
                rel = os.path.relpath(p, root).replace('\\', '/')
                try:
                    rows = dump(p)
                except Exception as ex:
                    print('FAIL', rel, ex); continue
                if rows:
                    result[rel] = rows
                    total += len(rows)
        json.dump(result, open(outjson, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('files:', len(result), 'strings:', total)
    elif cmd == 'roundtrip':
        # rebuild with no changes; verify strings identical and structure parses
        src = sys.argv[2]
        import tempfile
        tmp = src + '.rt'
        rebuild(src, {}, tmp)
        a, b = dump(src), dump(tmp)
        assert a == b, 'string mismatch'
        print('roundtrip OK', src, os.path.getsize(src), '->', os.path.getsize(tmp))
        os.remove(tmp)
