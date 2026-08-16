# dictionary v1.0.6 (character.cbin / glossary.gbin / robot.rbin)
# 0x00 "v1.0.6", 0x20 u32 count, entries from 0x74.
# entry: name[0x80], text[0x1000], then per-file extra fields; stride per file.
import struct, sys, os, json

LAYOUT = {
    'character.cbin': {'stride': 0x10F8, 'fields': [('name', 0x0, 0x80), ('text', 0x80, 0x1000),
                                                    ('kana', 0x1080, 0x20), ('cv', 0x10A0, 0x20)]},
    'glossary.gbin':  {'stride': 0x10B4, 'fields': [('name', 0x0, 0x80), ('text', 0x80, 0x1000)]},
    'robot.rbin':     {'stride': 0x10F8, 'fields': [('name', 0x0, 0x80), ('text', 0x80, 0x1000),
                                                    ('height', 0x1080, 0x20), ('weight', 0x10A0, 0x20)]},
}

def rd(d, off, size):
    seg = d[off:off+size]
    return seg.split(b'\0')[0].decode('utf-8')

def dump(path):
    d = open(path, 'rb').read()
    assert d[:6] == b'v1.0.6'
    lay = LAYOUT[os.path.basename(path)]
    count = struct.unpack('>I', d[0x20:0x24])[0]
    out = []
    for i in range(count):
        base = 0x74 + i * lay['stride']
        ent = {'index': i}
        for fname, foff, fsize in lay['fields']:
            ent[fname] = rd(d, base + foff, fsize)
        out.append(ent)
    return out

def insert(path, entries, out_path):
    d = bytearray(open(path, 'rb').read())
    lay = LAYOUT[os.path.basename(path)]
    count = struct.unpack('>I', d[0x20:0x24])[0]
    for ent in entries:
        i = ent['index']
        assert i < count
        base = 0x74 + i * lay['stride']
        for fname, foff, fsize in lay['fields']:
            if fname not in ent: continue
            b = ent[fname].encode('utf-8')
            if len(b) >= fsize:
                raise ValueError(f'{fname}[{i}] too long: {len(b)} >= {fsize}')
            d[base+foff:base+foff+fsize] = b + b'\0' * (fsize - len(b))
    open(out_path, 'wb').write(bytes(d))

if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'dump':
        src, dst = sys.argv[2], sys.argv[3]
        json.dump(dump(src), open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(len(dump(src)), 'entries')
    elif cmd == 'insert':
        src, jsonf, dst = sys.argv[2], sys.argv[3], sys.argv[4]
        insert(src, json.load(open(jsonf, encoding='utf-8')), dst)
        print('written', dst)
