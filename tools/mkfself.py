"""Build a fake SELF (fSELF) wrapping a decrypted PPC64 ELF, with zlib-compressed
segments so it fits the original EBOOT.BIN slot. Ported from Flat_z's make_fself
(PS3Py/fself.py) with per-segment compression added.

RPCS3 treats magic 'SCE\\0' + flags(attribute)=0x8000 as a fake self and reconstructs
the ELF from the copied ehdr/phdr/shdr + the (optionally compressed) segment data
listed in the section-info table. No metadata/signatures are validated for fake self.
"""
import struct, sys, zlib

def align_up(n, a): return (n + a - 1) & ~(a - 1)

# --- Flat_z constants ---
SELF_MAGIC = 0x53434500
DIGEST_MAGICBITS = bytes((0x62,0x7c,0xb1,0x80,0x8a,0xb9,0x38,0xe3,0x2c,0x8c,
                          0x09,0x17,0x08,0x72,0x6a,0x57,0x9e,0x25,0x86,0xe4))

SELF_HDR = 0x68   # SelfHeader
APPINFO  = 0x18
EHDR     = 0x40
PHDR     = 0x38
SINFO    = 0x20   # phdrOffset (section info)
DSUB     = 0x10   # DigestSubHeader
DT2      = 0x40   # DigestType2

def make(elf_path, out_path, compress=True):
    elf = open(elf_path, 'rb').read()
    assert elf[:4] == b'\x7fELF'
    e_phoff = struct.unpack('>Q', elf[0x20:0x28])[0]
    e_shoff = struct.unpack('>Q', elf[0x28:0x30])[0]
    e_phentsize, e_phnum = struct.unpack('>HH', elf[0x36:0x3A])
    e_shentsize, e_shnum = struct.unpack('>HH', elf[0x3C:0x40])
    ehdr = elf[:EHDR]
    phdrs = [elf[e_phoff+i*e_phentsize:e_phoff+(i+1)*e_phentsize] for i in range(e_phnum)]

    # header layout (mirror fself.py)
    ai_off   = align_up(SELF_HDR, 0x10)
    elf_off  = align_up(ai_off + APPINFO, 0x10)      # copied ehdr
    phdr_off = elf_off + EHDR                         # copied phdrs
    si_off   = align_up(phdr_off + PHDR*e_phnum, 0x10)
    dig_off  = align_up(si_off + SINFO*e_phnum, 0x10)
    dig_size = DSUB + DT2
    endhdr   = dig_off + dig_size
    data_off = align_up(endhdr, 0x80)

    # compress/copy each segment, build section-info
    blob = bytearray()
    sinfo = []
    for ph in phdrs:
        p_type  = struct.unpack('>I', ph[0:4])[0]
        p_off   = struct.unpack('>Q', ph[8:16])[0]
        p_filesz= struct.unpack('>Q', ph[32:40])[0]
        while len(blob) % 0x10:
            blob.append(0)
        pos = data_off + len(blob)
        if p_filesz:
            raw = elf[p_off:p_off+p_filesz]
            if compress:
                c = zlib.compress(raw, 9)
                if len(c) < len(raw):
                    blob += c
                    sinfo.append((pos, len(c), 2, p_type))   # compressed=2
                else:
                    blob += raw
                    sinfo.append((pos, len(raw), 1, p_type))
            else:
                blob += raw
                sinfo.append((pos, len(raw), 1, p_type))
        else:
            sinfo.append((pos, 0, 1, p_type))
    # shdr copied plaintext after segments
    while len(blob) % 0x10:
        blob.append(0)
    shdr_pos = data_off + len(blob)
    if e_shnum:
        blob += elf[e_shoff:e_shoff+e_shentsize*e_shnum]

    headerSize = data_off
    meta = endhdr - 0x10

    out = bytearray(data_off)
    # SelfHeader (BE): magic,headerVer,flags,type,meta,headerSize,encryptedSize,
    #   unknown,AppInfo,elf,phdr,shdr,phdrOffsets,sceversion,digest,digestSize
    # SelfHeader (BE): magic u32@0, headerVer u32@4, flags u16@8, type u16@0xA,
    #   meta u32@0xC, then 11 u64 from @0x10:
    #   headerSize, encryptedSize, unknown, AppInfo, elf, phdr, shdr,
    #   phdrOffsets, sceversion, digest, digestSize
    struct.pack_into('>IIHHI', out, 0, SELF_MAGIC, 2, 0x8000, 1, meta)
    struct.pack_into('>QQQQQQQQQQQ', out, 0x10,
                     headerSize, len(elf), 3, ai_off, elf_off, phdr_off,
                     shdr_pos, si_off, 0, dig_off, dig_size)
    # AppInfo
    struct.pack_into('>QIIQ', out, ai_off, 0x1010000001000003, 0x1000002, 0x4,
                     0x0001000000000000)
    # copied ehdr + phdrs
    out[elf_off:elf_off+EHDR] = ehdr
    for i, ph in enumerate(phdrs):
        out[phdr_off+i*PHDR:phdr_off+(i+1)*PHDR] = ph
    # section-info
    for i, (off, size, comp, ptype) in enumerate(sinfo):
        base = si_off + i*SINFO
        struct.pack_into('>QQIIII', out, base, off, size, comp, 0, 0,
                         2 if ptype == 1 else 0)
    # digest (type 2)
    struct.pack_into('>IIQ', out, dig_off, 2, 0x40, 0)
    out[dig_off+DSUB:dig_off+DSUB+0x14] = DIGEST_MAGICBITS
    # (digest[0x14:] left zero)

    out += blob
    open(out_path, 'wb').write(bytes(out))
    print(f'fSELF {len(out):,} bytes (elf {len(elf):,}, slot check vs 2,859,944)')
    return len(out)

if __name__ == '__main__':
    make(sys.argv[1], sys.argv[2], compress='--raw' not in sys.argv)
