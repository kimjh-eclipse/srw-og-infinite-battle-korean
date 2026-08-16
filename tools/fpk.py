# FPK container: "FPK\0", u32 count, u32 entry_off(0x10), u32 data_off
# entry (0x50): char name[0x40]; u32 offset(rel data_off); u32 size; u32 padded_size; u32 zero
import struct, sys, os

def parse(data):
    assert data[:4] == b'FPK\0', data[:4]
    count, entoff, dataoff = struct.unpack('>III', data[4:16])
    ents = []
    for i in range(count):
        e = data[entoff+i*0x50:entoff+(i+1)*0x50]
        name = e[:0x40].split(b'\0')[0].decode('ascii', 'replace')
        off, size, padded, z = struct.unpack('>IIII', e[0x40:0x50])
        ents.append(dict(i=i, name=name, off=off, size=size, padded=padded, z=z))
    return count, entoff, dataoff, ents

def extract(path, outdir):
    data = open(path, 'rb').read()
    count, entoff, dataoff, ents = parse(data)
    os.makedirs(outdir, exist_ok=True)
    for e in ents:
        if 'dummy' in e['name']: continue
        blob = data[dataoff+e['off']:dataoff+e['off']+e['size']]
        dest = os.path.join(outdir, e['name'].replace('\\', '_').replace('/', '_'))
        open(dest, 'wb').write(blob)
    return ents

def rebuild(path, repl, out_path):
    """repl: {inner_name: bytes}. Rewrites entry table offsets/sizes and data region."""
    data = open(path, 'rb').read()
    count, entoff, dataoff, ents = parse(data)
    out = bytearray(data[:dataoff])
    body = bytearray()
    # preserve original per-entry alignment granularity
    for e in ents:
        blob = repl.get(e['name'])
        if blob is None:
            blob = data[dataoff+e['off']:dataoff+e['off']+e['size']]
        size = len(blob)
        # original padded size implies alignment; keep 0x10 alignment as observed
        padded = (size + 0xF) & ~0xF
        off = len(body)
        body += blob + b'\0' * (padded - size)
        base = entoff + e['i']*0x50
        struct.pack_into('>IIII', out, base+0x40, off, size, padded, e['z'])
    out += body
    open(out_path, 'wb').write(bytes(out))
    return len(out)

if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'list':
        data = open(sys.argv[2], 'rb').read()
        count, entoff, dataoff, ents = parse(data)
        print(f'count={count} entoff={entoff:#x} dataoff={dataoff:#x}')
        for e in ents:
            if 'dummy' in e['name']: continue
            print(f"  {e['name']:40s} off={e['off']:#010x} size={e['size']:#010x} padded={e['padded']:#010x}")
    elif cmd == 'extract':
        ents = extract(sys.argv[2], sys.argv[3])
        print(len([e for e in ents if 'dummy' not in e['name']]), 'files ->', sys.argv[3])
    elif cmd == 'roundtrip':
        src = sys.argv[2]
        rebuild(src, {}, src + '.rt')
        a, b = open(src, 'rb').read(), open(src + '.rt', 'rb').read()
        print('roundtrip', 'IDENTICAL' if a == b else f'DIFF ({len(a)} vs {len(b)})')
        os.remove(src + '.rt')
