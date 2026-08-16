# Merge manual EBOOT translations (eboot_ko.json, reviewed) with the auto ones from
# the workflow (out_*.json). Manual wins. Output -> eboot_ko_full.json.
import json, glob, os

WORK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
manual = json.load(open(os.path.join(WORK, 'eboot_ko.json'), encoding='utf-8'))
auto = {}
for f in sorted(glob.glob(os.path.join(WORK, 'trans', 'out_*.json'))):
    auto.update(json.load(open(f, encoding='utf-8')))

REPL = {'·': '・', '®': '', 'Ⓡ': 'R', '™': ''}
def fix(s):
    for a_, b_ in REPL.items():
        s = s.replace(a_, b_)
    return s

strings = json.load(open(os.path.join(WORK, 'eboot_strings.json'), encoding='utf-8'))
full = {}
m = a = 0
for e in strings:
    jp = e['jp']
    if jp in manual:
        full[jp] = fix(manual[jp]); m += 1
    elif jp in auto and auto[jp] != jp:
        full[jp] = fix(auto[jp]); a += 1
json.dump(full, open(os.path.join(WORK, 'eboot_ko_full.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print(f'EBOOT merged: {len(full)} (manual {m}, auto {a}) -> eboot_ko_full.json')
