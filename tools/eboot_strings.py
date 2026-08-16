# Extract NUL-terminated UTF-8 strings containing Japanese from the decrypted EBOOT.
# Strict filter: every character must be plausible UI text (kills code-byte false hits).
import re, json

d = open('EBOOT.elf', 'rb').read()

def plausible(s):
    for ch in s:
        o = ord(ch)
        if ch in '\n\t': continue
        if 0x20 <= o <= 0x7E: continue          # ASCII printable
        if 0x3000 <= o <= 0x30FF: continue      # JP punctuation + kana
        if 0x4E00 <= o <= 0x9FFF: continue      # kanji
        if 0xFF01 <= o <= 0xFF60: continue      # fullwidth forms
        if o in (0xA9, 0xAE, 0x2026, 0x2015, 0x2500, 0x25CF, 0x2192): continue
        return False
    return True

JP = re.compile(r'[぀-ヿ一-鿿]')

out = []
i = 0
n = len(d)
while i < n:
    j = d.find(b'\x00', i)
    if j < 0:
        break
    seg = d[i:j]
    if 4 <= len(seg) <= 2048:
        try:
            s = seg.decode('utf-8')
        except UnicodeDecodeError:
            s = None
        if s and JP.search(s) and plausible(s) and len(JP.findall(s)) >= 2:
            out.append({'off': i, 'slot': len(seg), 'jp': s})
    i = j + 1

print(f'JP strings: {len(out)}, total bytes: {sum(x["slot"] for x in out):,}')
uniq = sorted({x['jp'] for x in out})
print(f'unique: {len(uniq)}')
lo = min(x['off'] for x in out); hi = max(x['off'] for x in out)
print(f'address range: {lo:#x} .. {hi:#x}')
json.dump(out, open('eboot_strings.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

for x in out:
    prev = x['jp'].replace('\n', '\\n')
    print(f'{x["off"]:#010x} {x["slot"]:4d}B  {prev[:78]}')
