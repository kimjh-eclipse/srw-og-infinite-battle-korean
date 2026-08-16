# PS3 SDAT (NPD v4, finalized, uncompressed, FLAG_0x20 interleaved) decrypt/encrypt.
# Verified against RPCS3 unedat.cpp semantics; roundtrip-checked vs rpcs3 --decrypt output.
import struct, os, hmac, hashlib
from Crypto.Cipher import AES
from Crypto.Hash import CMAC

SDAT_KEY   = bytes.fromhex('0D655EF8E674A98AB8505CFA7D012933')
EDAT_KEY_0 = bytes.fromhex('BE959CA8308DEFA2E5E180C63712A9AE')
EDAT_KEY_1 = bytes.fromhex('4CA9C14B01C95309969BEC68AA0BC081')
ZERO16     = b'\0' * 16

def align16(n): return (n + 15) & ~15
def xor16(a, b): return bytes(x ^ y for x, y in zip(a, b))
def ecb_enc(key, blk): return AES.new(key, AES.MODE_ECB).encrypt(blk)
def cbc_dec(key, iv, data): return AES.new(key, AES.MODE_CBC, iv).decrypt(data)
def cbc_enc(key, iv, data): return AES.new(key, AES.MODE_CBC, iv).encrypt(data)

class NPD:
    def __init__(self, buf):
        assert buf[:4] == b'NPD\0', buf[:4]
        self.version, self.license, self.type = struct.unpack('>III', buf[4:16])
        self.content_id = buf[0x10:0x40]
        self.digest     = buf[0x40:0x50]
        self.title_hash = buf[0x50:0x60]
        self.dev_hash   = buf[0x60:0x70]
        self.times      = buf[0x70:0x80]
        self.flags, self.block_size = struct.unpack('>II', buf[0x80:0x88])
        self.file_size  = struct.unpack('>Q', buf[0x88:0x90])[0]
        self.header     = bytes(buf[:0x100])

def derive(dec_key, dev_hash, i, edat_key, double_ecb):
    b_key      = dev_hash[:12] + struct.pack('>I', i)
    key_result = ecb_enc(dec_key, b_key)
    hash_seed  = ecb_enc(dec_key, key_result) if double_ecb else key_result
    key_final  = cbc_dec(edat_key, ZERO16, key_result)
    hash_final = cbc_dec(edat_key, ZERO16, hash_seed) + b'\0' * 4   # 0x14
    return key_final, hash_final

def cmac(key, data):
    return CMAC.new(key, ciphermod=AES).update(data).digest()

FOOTER = b'SDATA 4.0.0.W\0\0\0'

def _params(npd):
    assert npd.flags & 0x01000000, 'not SDAT'
    assert not (npd.flags & 0x00000001), 'compressed SDAT unsupported'
    assert npd.flags & 0x00000020, 'non-interleaved layout unsupported'
    edat_key = EDAT_KEY_1 if npd.version == 4 else EDAT_KEY_0
    double_ecb = bool(npd.flags & 0x00000010)
    return edat_key, double_ecb

def decrypt(path, verify=True):
    buf = open(path, 'rb').read()
    npd = NPD(buf)
    edat_key, double_ecb = _params(npd)
    dec_key = xor16(npd.dev_hash, SDAT_KEY)
    bs = npd.block_size
    nblocks = (npd.file_size + bs - 1) // bs
    out = bytearray()
    for i in range(nblocks):
        meta_off = 0x100 + i * (0x20 + bs)
        data_off = meta_off + 0x20
        meta = buf[meta_off:meta_off+0x20]
        test = bytes(meta[j] ^ meta[j+0x10] for j in range(0x10)) + meta[0x10:0x14]
        length = bs
        if i == nblocks - 1 and npd.file_size % bs:
            length = npd.file_size % bs
        alen = align16(length)
        enc = buf[data_off:data_off+alen]
        key_final, hkey = derive(dec_key, npd.dev_hash, i, edat_key, double_ecb)
        if verify:
            h = hmac.new(hkey, enc, hashlib.sha1).digest()[:0x14]
            assert h == test, f'block {i} hmac mismatch'
        out += cbc_dec(key_final, npd.digest, enc)[:length]
    return bytes(out[:npd.file_size])

def encrypt(plain, template_path, out_path, block_size=None):
    """Re-encrypt `plain` reusing the NPD identity (content_id/digest/dev_hash) of an
    existing SDAT so the game accepts it."""
    tbuf = open(template_path, 'rb').read(0x100)
    npd = NPD(tbuf)
    edat_key, double_ecb = _params(npd)
    dec_key = xor16(npd.dev_hash, SDAT_KEY)
    bs = block_size or npd.block_size
    file_size = len(plain)
    nblocks = (file_size + bs - 1) // bs
    total = 0x100 + nblocks * 0x20 + sum(
        align16(min(bs, file_size - i*bs)) for i in range(nblocks))
    out = bytearray(total)
    out[:0x100] = npd.header
    struct.pack_into('>Q', out, 0x88, file_size)
    struct.pack_into('>II', out, 0x80, npd.flags, bs)
    meta_all = bytearray()
    for i in range(nblocks):
        seg = plain[i*bs:(i+1)*bs]
        alen = align16(len(seg))
        seg = seg + b'\0' * (alen - len(seg))
        key_final, hkey = derive(dec_key, npd.dev_hash, i, edat_key, double_ecb)
        enc = cbc_enc(key_final, npd.digest, seg)
        H = hmac.new(hkey, enc, hashlib.sha1).digest()[:0x14]
        pad2 = H[0x10:0x14] + os.urandom(0x0C)
        meta = bytes(H[j] ^ pad2[j] for j in range(0x10)) + pad2
        meta_off = 0x100 + i * (0x20 + bs)
        data_off = meta_off + 0x20
        out[meta_off:meta_off+0x20] = meta
        out[data_off:data_off+alen] = enc
        meta_all += meta
    # Refresh the two CMACs the loader validates. The key is the file key unwrapped
    # with EDAT_KEY (ENCRYPTED_KEY flag); verified reproducible on the retail file.
    derived = cbc_dec(edat_key, ZERO16, dec_key)
    out[0x90:0xA0] = cmac(derived, bytes(meta_all))   # metadata section hash
    out[0xA0:0xB0] = cmac(derived, bytes(out[0:0xA0]))  # header hash
    out += FOOTER
    open(out_path, 'wb').write(bytes(out))
    return len(out)

if __name__ == '__main__':
    import sys
    cmd = sys.argv[1]
    if cmd == 'info':
        npd = NPD(open(sys.argv[2], 'rb').read(0x100))
        print(f'version={npd.version} license={npd.license} type={npd.type}')
        print(f'flags={npd.flags:#010x} block_size={npd.block_size:#x} file_size={npd.file_size:#x}')
        print(f'digest={npd.digest.hex()}')
        print(f'dev_hash={npd.dev_hash.hex()}')
        print(f'content_id={npd.content_id.rstrip(bytes(1)).decode("ascii","replace")!r}')
        import os as _os
        sz = _os.path.getsize(sys.argv[2])
        bs = npd.block_size
        nb = (npd.file_size + bs - 1)//bs
        expect = 0x100 + nb*0x20 + sum(align16(min(bs, npd.file_size - i*bs)) for i in range(nb))
        print(f'blocks={nb} expected_size={expect:#x} actual={sz:#x} diff={sz-expect}')
    elif cmd == 'decrypt':
        d = decrypt(sys.argv[2])
        open(sys.argv[3], 'wb').write(d)
        print('decrypted', len(d))
    elif cmd == 'encrypt':
        n = encrypt(open(sys.argv[2], 'rb').read(), sys.argv[3], sys.argv[4])
        print('encrypted ->', n)
