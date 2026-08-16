# Reconstruct the ELF from an fSELF the way RPCS3's MakeElf does: copy ehdr/phdr/shdr
# from the header, then place each (decompressed) segment at its phdr.offset. If this
# reproduces the original ELF, the fSELF structure is correct.
import struct, zlib, sys

def unpack(self_path):
    d = open(self_path, 'rb').read()
    assert d[:4] == b'SCE\0', d[:4]
    (headerSize, encSize, unk, ai, elf_o, phdr_o, shdr_o, si_o,
     scev, dig, digsz) = struct.unpack('>QQQQQQQQQQQ', d[0x10:0x68])
    ehdr = d[elf_o:elf_o+0x40]
    phoff = struct.unpack('>Q', ehdr[0x20:0x28])[0]
    shoff = struct.unpack('>Q', ehdr[0x28:0x30])[0]
    phentsize, phnum = struct.unpack('>HH', ehdr[0x36:0x3A])
    shentsize, shnum = struct.unpack('>HH', ehdr[0x3C:0x40])
    out = bytearray(encSize)
    out[:0x40] = ehdr
    for i in range(phnum):
        out[phoff+i*phentsize:phoff+(i+1)*phentsize] = d[phdr_o+i*phentsize:phdr_o+(i+1)*phentsize]
    for i in range(phnum):
        off, size, comp = struct.unpack('>QQI', d[si_o+i*0x20:si_o+i*0x20+20])
        ph = d[phdr_o+i*phentsize:phdr_o+(i+1)*phentsize]
        p_off = struct.unpack('>Q', ph[8:16])[0]
        p_filesz = struct.unpack('>Q', ph[32:40])[0]
        if p_filesz == 0:
            continue
        seg = d[off:off+size]
        if comp == 2:
            seg = zlib.decompress(seg)
        out[p_off:p_off+p_filesz] = seg
    if shnum:
        out[shoff:shoff+shentsize*shnum] = d[shdr_o:shdr_o+shentsize*shnum]
    return bytes(out)

if __name__ == '__main__':
    rebuilt = unpack(sys.argv[1] if len(sys.argv) > 1 else 'EBOOT_KR.self')
    orig = open('EBOOT_KR.elf', 'rb').read()
    print(f'rebuilt {len(rebuilt):,}  orig {len(orig):,}')
    if rebuilt == orig:
        print('FSELF ROUNDTRIP: PASS (byte-identical)')
    else:
        n = sum(1 for a, b in zip(rebuilt, orig) if a != b)
        first = next((i for i, (a, b) in enumerate(zip(rebuilt, orig)) if a != b), -1)
        print(f'FSELF ROUNDTRIP: differs in {n} bytes, first at {first:#x}')
