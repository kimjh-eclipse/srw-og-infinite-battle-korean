# Rebake a custom PGF+GTF font pair: drop kana/CJK, keep ASCII/symbols/fullwidth,
# add KS X 1001 (2350) Hangul rendered from a TTF. Atlas repacked, records UCS2-sorted.
#
# PGF header (32B, BE): [+0 u32=5][+4 u16 first_code][+6 u16 glyph_count]
#   [+8 "FGP"][+12.. metrics: cellW,cellH,ascent,... unknown but per-font constant]
#   [+16 u16 tex_w][+18 u16 tex_h?]  -> we keep header, patch count/tex fields.
# Glyph record (16B, BE): u32 code(utf8-bytes-as-int) u16 ucs2 u8 w h xo yo adv pad u16 u v
import struct, sys, os
from PIL import Image, ImageFont

def parse_pgf(data):
    hdr = bytearray(data[:32])
    count = struct.unpack('>H', data[6:8])[0]
    recs = []
    for i in range(count):
        r = data[32+i*16:32+(i+1)*16]
        code, ucs2 = struct.unpack('>IH', r[0:6])
        w,h,xo,yo,adv,pad = r[6],r[7],r[8],r[9],r[10],r[11]
        u,v = struct.unpack('>HH', r[12:16])
        recs.append(dict(code=code,ucs2=ucs2,w=w,h=h,xo=xo,yo=yo,adv=adv,pad=pad,u=u,v=v))
    return hdr, recs

def load_gtf(path):
    d = open(path,'rb').read()
    ver, fsize, ntex = struct.unpack('>III', d[:12])
    tid, toff, tsize = struct.unpack('>III', d[12:24])
    fmt = d[24]
    w,h = struct.unpack('>HH', d[24+8:24+12])
    pitch = struct.unpack('>I', d[24+16:24+20])[0]
    hdr = d[:0x80]
    pix = d[0x80:0x80+w*h] if pitch else d[0x80:0x80+tsize]
    return hdr, fmt, w, h, pitch, bytearray(pix), tsize

def build_gtf(gtf_hdr_template, w, h, pix):
    # Atlas is kept at the original texture dimensions, so every header field
    # (fsize/toff/tsize/w/h/pitch/fmt) already matches. Reuse the header verbatim
    # and only swap the pixel payload. (An earlier version rewrote these fields and
    # corrupted the texture-data offset — do not reintroduce that.)
    assert len(pix) == w * h, (len(pix), w, h)
    ow, oh = struct.unpack('>HH', gtf_hdr_template[24+8:24+12])
    assert (ow, oh) == (w, h), f'atlas {w}x{h} != original {ow}x{oh}'
    return bytes(gtf_hdr_template) + bytes(pix)

def ks2350():
    # KS X 1001 wanseong Hangul lives in EUC-KR lead 0xB0-0xC8, tail 0xA1-0xFE.
    # (cp949 maps this exact region identically to KS X 1001 -> precisely 2350.)
    out = []
    for lead in range(0xB0, 0xC9):
        for tail in range(0xA1, 0xFF):
            try:
                ch = bytes([lead, tail]).decode('euc_kr')
            except UnicodeDecodeError:
                continue
            if 0xAC00 <= ord(ch) <= 0xD7A3:
                out.append(ch)
    return out

def rebake(pgf_path, gtf_path, ttf_path, px, out_pgf, out_gtf, preview=None):
    pdata = open(pgf_path,'rb').read()
    hdr, recs = parse_pgf(pdata)
    gtf_hdr, fmt, TW, TH, pitch, opix, tsize = load_gtf(gtf_path)
    src = Image.frombytes('L', (TW, TH), bytes(opix))

    # Characters actually used by the Korean text — always keep a glyph for these,
    # even if they fall in the kana/kanji ranges we otherwise drop (・ middle dot,
    # 改 and a few kanji kept in names, etc.).
    import json as _json
    used_path = os.path.join(os.path.dirname(pgf_path).rsplit('fpk_ingame', 1)[0], 'used_chars.json')
    try:
        used = set(_json.load(open(used_path, encoding='utf-8')))
    except FileNotFoundError:
        used = set()

    def is_kana(u): return 0x3040 <= u <= 0x30FF
    def is_cjk(u):  return 0x4E00 <= u <= 0x9FFF or 0x3400 <= u <= 0x4DBF
    # Fullwidth digits/letters used in body text (０-９ Ａ-Ｚ ａ-ｚ) are re-rendered in
    # the same Bold face as Hangul so mixed lines look uniform. Halfwidth ASCII digits
    # stay original (HUD/HP/damage rely on their fixed design & alignment).
    def is_fw_alnum(u):
        return (0xFF10 <= u <= 0xFF19) or (0xFF21 <= u <= 0xFF3A) or (0xFF41 <= u <= 0xFF5A)
    keep = [r for r in recs
            if (r['ucs2'] in used and not is_fw_alnum(r['ucs2']))
            or not (is_kana(r['ucs2']) or is_cjk(r['ucs2']) or is_fw_alnum(r['ucs2']))]
    fw_alnum_codes = sorted(r['ucs2'] for r in recs if is_fw_alnum(r['ucs2']))

    # crop kept glyph pixels
    for r in keep:
        r['img'] = src.crop((r['u'], r['v'], r['u']+r['w'], r['v']+r['h'])) if r['w'] and r['h'] else None

    # render Hangul. Match the original full-width metrics so Korean sits on the same
    # baseline and cell as the Japanese it replaces.
    #   FW_ADV   : advance width of original full-width glyphs (kanji/kana) = 20
    #   FW_YO    : baseline->top (ascent) of original full-width glyphs      = 17
    # We anchor every Hangul glyph to FW_YO (fixed baseline) and center it in FW_ADV,
    # so glyphs with/without a final consonant no longer look ragged.
    # Measure the original full-width metrics (kanji/kana) so Korean drops onto the
    # exact same baseline and cell. Use the most common advance and its glyphs' yo.
    from collections import Counter
    all_recs = [dict(zip('code ucs2 w h xo yo adv pad u v'.split(),
                struct.unpack('>IHBBBBBBHH', pdata[32+i*16:32+(i+1)*16])))
                for i in range(struct.unpack('>H', pdata[6:8])[0])]
    fw_adv = Counter(r['adv'] for r in all_recs).most_common(1)[0][0]
    fw_yo = Counter(r['yo'] for r in all_recs if r['adv'] == fw_adv).most_common(1)[0][0]
    print(f'  original full-width: adv={fw_adv} yo={fw_yo}')

    font = ImageFont.truetype(ttf_path, px)
    ascent, descent = font.getmetrics()
    # The game draws each glyph with its top at (baseline - yo), so yo must be the
    # glyph's true ascent (top->baseline). Using a constant made every glyph TOP-align,
    # which left the BASELINE ragged. We use the real per-glyph ascent (keeps the
    # baseline flat) and shift the whole set so the typical Hangul baseline lands on
    # the original full-width baseline (fw_yo).
    tops = []
    for ch in '가나다라마바사아자하강한글모드뷁':
        bb = font.getmask(ch, mode='L').getbbox()
        if bb:
            tops.append(bb[1])
    typ_t = sorted(tops)[len(tops) // 2]
    shift = (ascent - typ_t) - fw_yo
    hangul = []
    # Only the Hangul syllables actually used by the translation (keeps the atlas small
    # -> fits the texture, and the whole SDAT within the original size for ISO splice).
    # Fall back to full KS X 1001 if no usage data yet.
    used_hangul = [chr(c) for c in sorted(used) if 0xAC00 <= c <= 0xD7A3]
    if not used_hangul:
        used_hangul = ks2350()
    render_chars = used_hangul + [chr(u) for u in fw_alnum_codes]
    for ch in render_chars:
        u = ord(ch)
        mask = font.getmask(ch, mode='L')
        bbox = mask.getbbox()
        if bbox is None:
            w = h = 0; img = None; xo = 0; yo = fw_yo
        else:
            l, t, rr, b = bbox
            gi = Image.new('L', mask.size, 0); gi.frombytes(bytes(mask))
            img = gi.crop((l, t, rr, b))
            w, h = rr - l, b - t
            xo = max(0, (fw_adv - w) // 2)     # center within the full-width cell
            yo = (ascent - t) - shift          # real baseline, aligned to original
        hangul.append(dict(code=int.from_bytes(ch.encode('utf-8'), 'big'), ucs2=u,
                           w=w, h=h, xo=xo, yo=yo, adv=fw_adv, pad=0, img=img))

    allg = sorted(keep + hangul, key=lambda r: r['ucs2'])

    # pack into atlas: same width TW, grow height as needed, 1px gaps
    pad = 1
    x = pad; y = pad; rowh = 0; packed_h = 0
    for r in allg:
        if r['w'] == 0:
            r['u'] = r['v'] = 0; continue
        if x + r['w'] + pad > TW:
            x = pad; y += rowh + pad; rowh = 0
        r['u'] = x; r['v'] = y
        x += r['w'] + pad
        rowh = max(rowh, r['h'])
        packed_h = max(packed_h, y + r['h'] + pad)
    # Keep the atlas EXACTLY the original texture size. The game normalizes glyph
    # UVs against the declared texture dimensions (PGF+16/+18 = TW/TH), so shrinking
    # the atlas while leaving those dims — or changing them — misaligns every glyph.
    if packed_h > TH:
        raise ValueError(f'packed {packed_h} exceeds original texture height {TH}')
    new_h = TH
    atlas = Image.new('L', (TW, new_h), 0)
    for r in allg:
        if r.get('img') is not None:
            atlas.paste(r['img'], (r['u'], r['v']))

    # write pgf
    nhdr = bytearray(hdr)
    struct.pack_into('>H', nhdr, 6, len(allg))
    struct.pack_into('>H', nhdr, 4, allg[0]['ucs2'])
    # patch tex height fields in pgf header if present (offset 18 seen as tex_h-ish); keep width
    struct.pack_into('>H', nhdr, 16, TW)
    body = bytearray()
    for r in allg:
        body += struct.pack('>IHBBBBBBHH', r['code'], r['ucs2'], r['w'], r['h'],
                            r['xo'], r['yo'], r['adv'], r['pad'], r['u'], r['v'])
    open(out_pgf,'wb').write(bytes(nhdr)+bytes(body))
    open(out_gtf,'wb').write(build_gtf(gtf_hdr, TW, new_h, atlas.tobytes()))
    if preview:
        atlas.crop((0,0,TW,min(new_h,900))).save(preview)
    print(f'{os.path.basename(pgf_path)}: kept {len(keep)} + hangul {len(hangul)} = {len(allg)} glyphs; atlas {TW}x{new_h} (orig {TW}x{TH})')

# Only the two full CJK fonts need Hangul; nakamaru14/sogei are 302-glyph ASCII+symbol
# sub-fonts (no kanji) and are shipped unchanged.
FONTS = {  # name: pixel size for Hangul (tuned so ink height ~ original full-width 19-20px)
    'default':    22,
    'nakamaru16': 20,
}

if __name__ == '__main__':
    only = sys.argv[1] if len(sys.argv) > 1 else None
    os.makedirs('font_out', exist_ok=True)
    ttf = r'C:\Windows\Fonts\malgunbd.ttf'    # 맑은 고딕 Bold — matches the bold JP font
    for name, px in FONTS.items():
        if only and only != name: continue
        src_pgf, src_gtf = f'fpk_ingame/{name}.pgf', f'fpk_ingame/{name}.gtf'
        if not os.path.exists(src_pgf): continue
        rebake(src_pgf, src_gtf, ttf, px,
               f'font_out/{name}.pgf', f'font_out/{name}.gtf',
               f'font_out/preview_{name}.png')
