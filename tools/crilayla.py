"""CRILAYLA compressor/decompressor.

Format: "CRILAYLA" | u32 uncompressed_size | u32 compressed_size
        | compressed bitstream (written backwards) | 0x100 raw prefix
Decoder consumes the bitstream from its LAST byte backwards, MSB-first within
each byte, and fills the output buffer from the END backwards. The first 0x100
bytes of the original file are stored uncompressed at the tail.

Backref: [1][13-bit offset-3][varlen count] copies from (pos+offset) forward in
memory but the write cursor moves backwards; literal: [0][8-bit byte].
"""
import struct

VLE = (2, 3, 5, 8)

class BitWriterBackward:
    """Accumulates bits MSB-first; output bytes are emitted in reverse order so
    the decoder (reading from the last byte backwards) sees them in order."""
    def __init__(self):
        self.bytes = bytearray()
        self.cur = 0
        self.nbits = 0
    def put(self, value, n):
        for i in range(n - 1, -1, -1):
            self.cur = (self.cur << 1) | ((value >> i) & 1)
            self.nbits += 1
            if self.nbits == 8:
                self.bytes.append(self.cur)
                self.cur = 0
                self.nbits = 0
    def finish(self):
        if self.nbits:
            self.cur <<= (8 - self.nbits)     # pad low bits
            self.bytes.append(self.cur)
            self.nbits = 0
        return bytes(reversed(self.bytes))

def _put_count(bw, count):
    """Variable-length count encoding, mirroring the decoder's escalation."""
    rem = count - 3
    lvl = 0
    while True:
        bits = VLE[lvl] if lvl < 3 else 8
        cap = (1 << bits) - 1
        if rem < cap:
            bw.put(rem, bits)
            return
        bw.put(cap, bits)
        rem -= cap
        if lvl < 3:
            lvl += 1
        # at level>=3 the decoder keeps reading 8-bit chunks while each == 0xFF

def compress(data):
    n = len(data)
    if n <= 0x100:
        raise ValueError('input must exceed 0x100 bytes')
    prefix = data[:0x100]
    body = data[0x100:]
    m = len(body)

    # Build an index of 3-byte sequences for match finding.
    idx = {}
    bw = BitWriterBackward()

    # The decoder walks the output backwards, so we compress `body` from its END
    # to its START; a "backref offset" points to bytes we have already emitted,
    # i.e. bytes at HIGHER addresses in the output.
    pos = m - 1
    MAX_OFF = 8189 + 3          # 13-bit field + 3
    while pos >= 0:
        best_len = 0
        best_off = 0
        if pos + 3 <= m:
            key = bytes(body[pos:pos+3])
            # candidates are positions ahead of us that we've already written
            for cand in idx.get(key, ()):
                off = cand - pos
                if off < 3 or off > MAX_OFF:
                    continue
                # match: out[pos - k] = out[pos - k + off]  for k = 0..len-1
                # walking backwards from pos
                ln = 0
                while (ln < 255 * 4 and pos - ln >= 0 and
                       pos - ln + off < m and
                       body[pos - ln] == body[pos - ln + off]):
                    ln += 1
                if ln > best_len:
                    best_len, best_off = ln, off
                    if ln >= 64:
                        break
        if best_len >= 3:
            bw.put(1, 1)
            bw.put(best_off - 3, 13)
            _put_count(bw, best_len)
            for k in range(best_len):
                p = pos - k
                if p + 3 <= m:
                    idx.setdefault(bytes(body[p:p+3]), []).append(p)
            pos -= best_len
        else:
            bw.put(0, 1)
            bw.put(body[pos], 8)
            if pos + 3 <= m:
                idx.setdefault(bytes(body[pos:pos+3]), []).append(pos)
            pos -= 1

    stream = bw.finish()
    return (b'CRILAYLA' + struct.pack('<II', m, len(stream)) + stream + prefix)

def decompress(src):
    assert src[:8] == b'CRILAYLA'
    usize, coff = struct.unpack('<II', src[8:16])
    prefix = src[16+coff:16+coff+0x100]
    comp = src[16:16+coff]
    out = bytearray(0x100 + usize)
    out[0:0x100] = prefix
    opos = 0x100 + usize
    bitpos = 0
    dpos = len(comp) - 1
    def getbits(nb):
        nonlocal bitpos, dpos
        v = 0
        for _ in range(nb):
            v = (v << 1) | ((comp[dpos] >> (7 - bitpos)) & 1)
            bitpos += 1
            if bitpos == 8:
                bitpos = 0
                dpos -= 1
        return v
    while opos > 0x100:
        if getbits(1):
            offset = getbits(13) + 3
            refc = 3
            lvl = 0
            while True:
                bits = VLE[lvl] if lvl < 3 else 8
                v = getbits(bits)
                refc += v
                if v != (1 << bits) - 1:
                    break
                if lvl < 3:
                    lvl += 1
            for _ in range(refc):
                out[opos-1] = out[opos-1+offset]
                opos -= 1
        else:
            out[opos-1] = getbits(8)
            opos -= 1
    return bytes(out)

if __name__ == '__main__':
    import sys, os, random
    random.seed(1)
    # self-test on real game files
    tests = sys.argv[1:] or [r'extracted\level_design\paramater_mission.prm',
                             r'extracted\dictionary\character.cbin']
    for t in tests:
        d = open(t, 'rb').read()
        c = compress(d)
        b = decompress(c)
        ok = b == d
        print(f'{os.path.basename(t)}: {len(d):,} -> {len(c):,} '
              f'({len(c)*100//len(d)}%) roundtrip {"OK" if ok else "FAIL"}')
