# Collect every character that appears in the final Korean text (translations +
# EBOOT), so the font rebake can guarantee a glyph for each. Output: used_chars.json
import json, glob, os

WORK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
used = set()
for f in glob.glob(os.path.join(WORK, 'trans', 'out_*.json')):
    for v in json.load(open(f, encoding='utf-8')).values():
        used.update(v)
for v in json.load(open(os.path.join(WORK, 'eboot_ko_full.json'), encoding='utf-8')).values():
    used.update(v)
used.discard('\n')
codes = sorted(ord(c) for c in used)
json.dump(codes, open(os.path.join(WORK, 'used_chars.json'), 'w', encoding='utf-8'))
print(f'used chars: {len(codes)}')
