import struct
f = open('ps3_game_cpk.sdat.unedat','rb')
hdr = f.read(16)
utf_size = struct.unpack('<Q', hdr[8:16])[0]
utf = f.read(utf_size)
# parse @UTF just enough to find TocOffset, ContentOffset, Align
def read_utf(data):
    assert data[:4]==b'@UTF'
    tsz = struct.unpack('>I', data[4:8])[0]
    base=8
    rows_off,str_off,data_off = struct.unpack('>III', data[base:base+12])
    ncol,rowlen = struct.unpack('>HH', data[base+16:base+20])
    nrows = struct.unpack('>I', data[base+20:base+24])[0]
    return ncol, nrows, rowlen
print('CPK @UTF:', read_utf(utf))
# TOC
def find_toc():
    # header row fields we already know from extractor: TocOffset=0x800, ContentOffset=0x16800
    f.seek(0x800); th=f.read(16); tsz=struct.unpack('<Q', th[8:16])[0]
    toc=f.read(tsz)
    ncol,nrows,rowlen = read_utf(toc)
    print('TOC @UTF cols',ncol,'rows',nrows,'rowlen',rowlen,'size',hex(tsz))
    # dump column defs
    base=8
    rows_off,str_off,data_off = struct.unpack('>III', toc[base:base+12])
    ncol,rowlen = struct.unpack('>HH', toc[base+16:base+20])
    p=base+24
    def cstr(off):
        e=toc.index(b'\0', str_off+8+off); return toc[str_off+8+off:e].decode()
    cols=[]
    for _ in range(ncol):
        flags=toc[p]; p+=1
        noff=struct.unpack('>I',toc[p:p+4])[0]; p+=4
        storage=flags&0xF0; typ=flags&0x0F
        sz=[1,1,2,2,4,4,8,8,4,4,0,0][typ] if typ<12 else 0
        if storage in (0x30,0x70): p+=sz
        cols.append((cstr(noff), hex(flags), typ))
    for c in cols: print('  col', c)
find_toc()
