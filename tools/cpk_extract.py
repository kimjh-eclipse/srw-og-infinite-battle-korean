# CRI CPK extractor (TOC-based) + CRILAYLA decompression
import sys, os, struct

def read_utf(data):
    assert data[:4] == b'@UTF', f"not UTF: {data[:4]}"
    table_size = struct.unpack('>I', data[4:8])[0]
    base = 8
    rows_off, str_off, data_off, name_off = struct.unpack('>IIII', data[base:base+16])
    ncol, rowlen = struct.unpack('>HH', data[base+16:base+20])
    nrows = struct.unpack('>I', data[base+20:base+24])[0]
    rows_off += base; str_off += base; data_off += base
    def cstr(off):
        end = data.index(b'\0', str_off+off)
        return data[str_off+off:end].decode('utf-8', 'replace')
    cols = []
    p = base + 24
    for _ in range(ncol):
        flags = data[p]; p += 1
        noff = struct.unpack('>I', data[p:p+4])[0]; p += 4
        name = cstr(noff)
        const = None
        storage = flags & 0xF0
        typ = flags & 0x0F
        if storage == 0x30 or storage == 0x70:  # constant
            const, sz = read_val(data, p, typ, str_off, data_off, cstr)
            p += sz
        cols.append((name, flags, const))
    rows = []
    for r in range(nrows):
        rp = rows_off + r * rowlen
        row = {}
        for name, flags, const in cols:
            storage = flags & 0xF0
            typ = flags & 0x0F
            if storage == 0x50:  # per-row
                v, sz = read_val(data, rp, typ, str_off, data_off, cstr)
                rp += sz
                row[name] = v
            elif storage in (0x30, 0x70):
                row[name] = const
            else:
                row[name] = None
        rows.append(row)
    return rows

def read_val(data, p, typ, str_off, data_off, cstr):
    if typ in (0, 1): return data[p], 1
    if typ in (2, 3): return struct.unpack('>H', data[p:p+2])[0], 2
    if typ in (4, 5): return struct.unpack('>I', data[p:p+4])[0], 4
    if typ in (6, 7): return struct.unpack('>Q', data[p:p+8])[0], 8
    if typ == 8: return struct.unpack('>f', data[p:p+4])[0], 4
    if typ == 0xA:
        off = struct.unpack('>I', data[p:p+4])[0]
        return cstr(off), 4
    if typ == 0xB:
        off, sz = struct.unpack('>II', data[p:p+8])
        return (data_off+off, sz), 8
    raise ValueError(f"type {typ}")

def crilayla_decompress(src):
    assert src[:8] == b'CRILAYLA'
    usize, coff = struct.unpack('<II', src[8:16])
    prefix = src[16+coff:16+coff+0x100]
    comp = src[16:16+coff]
    out = bytearray(0x100 + usize)
    out[0:0x100] = prefix
    opos = 0x100 + usize
    bitpos = 0
    dpos = len(comp) - 1
    def getbits(n):
        nonlocal bitpos, dpos
        v = 0
        for _ in range(n):
            v <<= 1
            v |= (comp[dpos] >> (7 - bitpos)) & 1
            bitpos += 1
            if bitpos == 8:
                bitpos = 0; dpos -= 1
        return v
    while opos > 0x100:
        if getbits(1):
            offset = getbits(13) + 3
            refc = 3
            lvl = 0
            sizes = [2, 3, 5]
            while True:
                bits = sizes[lvl] if lvl < 3 else 8
                v = getbits(bits)
                refc += v
                if v != (1 << bits) - 1:
                    break
                lvl += 1
            for _ in range(refc):
                out[opos-1] = out[opos-1+offset]
                opos -= 1
        else:
            out[opos-1] = getbits(8)
            opos -= 1
    return bytes(out)

def main():
    cpk_path, out_dir = sys.argv[1], sys.argv[2]
    list_only = len(sys.argv) > 3 and sys.argv[3] == '--list'
    f = open(cpk_path, 'rb')
    hdr = f.read(16)
    assert hdr[:4] == b'CPK '
    utf_size = struct.unpack('<Q', hdr[8:16])[0]
    f.seek(16)
    header_rows = read_utf(f.read(utf_size))
    h = header_rows[0]
    toc_off = h.get('TocOffset'); content_off = h.get('ContentOffset')
    print(f"TocOffset={toc_off:#x} ContentOffset={content_off:#x} Files={h.get('Files')}")
    base = min(toc_off, content_off)
    f.seek(toc_off)
    toc_hdr = f.read(16)
    assert toc_hdr[:4] == b'TOC ', toc_hdr[:4]
    toc_size = struct.unpack('<Q', toc_hdr[8:16])[0]
    rows = read_utf(f.read(toc_size))
    print(f"{len(rows)} entries")
    for row in rows:
        name = (row.get('DirName') or '')
        fn = row['FileName']
        path = f"{name}/{fn}" if name else fn
        fsize = row['FileSize']; esize = row.get('ExtractSize') or fsize
        off = base + row['FileOffset']
        if list_only:
            print(f"{path}\t{fsize}\t{esize}\t{off:#x}")
            continue
        f.seek(off)
        blob = f.read(fsize)
        if esize > fsize and blob[:8] == b'CRILAYLA':
            blob = crilayla_decompress(blob)
        dest = os.path.join(out_dir, name.replace('/', os.sep), fn)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, 'wb') as o:
            o.write(blob)
    print("done")

if __name__ == '__main__':
    main()
