"""Minimal ISO9660 reader/patcher: locate a file's directory record so its extent
and size can be repointed (used to swap in a larger EBOOT)."""
import struct, sys

SECTOR = 2048

def both16(b): return struct.unpack('<H', b[:2])[0]
def both32(b): return struct.unpack('<I', b[:4])[0]

class Iso:
    def __init__(self, path, mode='rb'):
        self.f = open(path, mode)
        self.path = path
        self.pvd_lba = None
        for lba in range(16, 32):
            self.f.seek(lba * SECTOR)
            d = self.f.read(SECTOR)
            if d[0] == 1 and d[1:6] == b'CD001':
                self.pvd = d
                self.pvd_lba = lba
                break
        else:
            raise ValueError('no PVD')
        self.volume_space_size = both32(self.pvd[80:88])
        self.root = self.pvd[156:156+34]

    def read_dir(self, lba, size):
        self.f.seek(lba * SECTOR)
        return self.f.read(size)

    def parse_dir(self, data, base_lba):
        """yield (name, lba, size, record_abs_offset)"""
        pos = 0
        while pos < len(data):
            ln = data[pos]
            if ln == 0:
                # advance to next sector boundary
                nxt = (pos // SECTOR + 1) * SECTOR
                if nxt >= len(data):
                    break
                pos = nxt
                continue
            rec = data[pos:pos+ln]
            ext_lba = both32(rec[2:10])
            ext_len = both32(rec[10:18])
            flags = rec[25]
            nlen = rec[32]
            name = rec[33:33+nlen]
            if name == b'\x00':   name_s = '.'
            elif name == b'\x01': name_s = '..'
            else: name_s = name.decode('ascii', 'replace').split(';')[0]
            yield (name_s, ext_lba, ext_len, flags, base_lba * SECTOR + pos)
            pos += ln

    def find(self, path):
        """path like 'PS3_GAME/USRDIR/EBOOT.BIN' -> (lba, size, record_offset)"""
        cur_lba = both32(self.root[2:10])
        cur_len = both32(self.root[10:18])
        parts = path.strip('/').split('/')
        for idx, part in enumerate(parts):
            data = self.read_dir(cur_lba, cur_len)
            for name, lba, size, flags, rec_off in self.parse_dir(data, cur_lba):
                if name.upper() == part.upper():
                    if idx == len(parts) - 1:
                        return lba, size, rec_off
                    cur_lba, cur_len = lba, size
                    break
            else:
                raise FileNotFoundError(path)
        raise FileNotFoundError(path)

    def listdir(self, path=''):
        if path:
            lba, size, _ = self.find(path)
        else:
            lba, size = both32(self.root[2:10]), both32(self.root[10:18])
        return [(n, l, s, f) for n, l, s, f, _ in self.parse_dir(self.read_dir(lba, size), lba)]

    def close(self):
        self.f.close()

def patch_record(path, rec_off, new_lba, new_size):
    with open(path, 'r+b') as f:
        f.seek(rec_off + 2)
        f.write(struct.pack('<I', new_lba) + struct.pack('>I', new_lba))
        f.seek(rec_off + 10)
        f.write(struct.pack('<I', new_size) + struct.pack('>I', new_size))

if __name__ == '__main__':
    iso = Iso(sys.argv[1])
    print(f'PVD lba={iso.pvd_lba} volume_space_size={iso.volume_space_size} sectors '
          f'({iso.volume_space_size*SECTOR:,} bytes); file is '
          f'{__import__("os").path.getsize(sys.argv[1]):,} bytes')
    for p in ('', 'PS3_GAME', 'PS3_GAME/USRDIR', 'PS3_UPDATE'):
        try:
            print(f'--- /{p}')
            for n, l, s, fl in iso.listdir(p):
                if n in ('.', '..'): continue
                kind = 'DIR ' if fl & 2 else 'FILE'
                print(f'  {kind} {n:24s} lba={l:>9} size={s:>12,} end_lba={l + (s+2047)//2048}')
        except Exception as e:
            print('  ', e)
