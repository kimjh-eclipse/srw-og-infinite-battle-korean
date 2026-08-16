# Normalize symbols the translators introduced that have no glyph in the game font:
#   ·(U+00B7 halfwidth) -> ・(U+30FB, the game's fullwidth middle dot, restored to font)
#   ®(U+00AE), Ⓡ(U+24C7) -> removed (registered-mark, not in font)
# Applied in place to trans/out_*.json.
import json, glob, os

WORK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPL = {'경(輕)': '경량', '(輕)': '', '·': '・', '®': '', 'Ⓡ': 'R', '™': ''}

def fix(s):
    for a, b in REPL.items():
        s = s.replace(a, b)
    return s

total = 0
for f in glob.glob(os.path.join(WORK, 'trans', 'out_*.json')):
    d = json.load(open(f, encoding='utf-8'))
    n = 0
    for k in list(d):
        nv = fix(d[k])
        if nv != d[k]:
            d[k] = nv; n += 1
    if n:
        json.dump(d, open(f, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
        total += n
        print(f'{os.path.basename(f)}: {n} fixed')
print(f'total {total} strings normalized')
