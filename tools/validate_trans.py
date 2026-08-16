"""Validate the jp->ko translation dictionary before insertion:
  - control codes / format specifiers / tags preserved (same multiset)
  - no untranslated leftovers (ko still fully Japanese)
  - coverage vs the pool
"""
import json, os, re, glob, sys

WORK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TOKEN = re.compile(r'@i\(\d+\)|%[0-9]*[disuxX]|\[\$?[^\]]*\]|<[^>]+>|\\n|\n|　')
JP = re.compile(r'[぀-ヿ一-鿴]')

def tokens(s):
    from collections import Counter
    return Counter(TOKEN.findall(s))

def main():
    tl = {}
    for f in sorted(glob.glob(os.path.join(WORK, 'trans', 'out_*.json'))):
        tl.update(json.load(open(f, encoding='utf-8')))
    pool = json.load(open(os.path.join(WORK, 'translate_pool.json'), encoding='utf-8'))
    pool_jp = {e['jp'] for e in pool}

    issues = {'token': [], 'untranslated': [], 'empty': []}
    for jp, ko in tl.items():
        if not ko.strip():
            issues['empty'].append(jp); continue
        tj, tk = tokens(jp), tokens(ko)
        if tj != tk:
            issues['token'].append((jp, ko, dict(tj - tk), dict(tk - tj)))
        # ko still entirely Japanese with no Hangul = likely untranslated
        if JP.search(ko) and not re.search(r'[가-힣]', ko) and len(ko) > 3:
            issues['untranslated'].append((jp, ko))

    missing = [e['jp'] for e in pool if e['jp'] not in tl]
    print(f'translated: {len(tl)} / pool {len(pool_jp)}  (missing {len(missing)})')
    print(f'token mismatch: {len(issues["token"])}')
    print(f'untranslated(한글없음): {len(issues["untranslated"])}')
    print(f'empty: {len(issues["empty"])}')
    for jp, ko, miss, extra in issues['token'][:25]:
        print(f'  TOKEN {jp[:30]!r} -> {ko[:30]!r}  missing={miss} extra={extra}')
    for jp, ko in issues['untranslated'][:15]:
        print(f'  UNTRANS {jp[:30]!r} -> {ko[:30]!r}')
    if missing[:15]:
        print('  MISSING sample:', [m[:20] for m in missing[:15]])
    json.dump({'missing': missing,
               'token': [(a, b) for a, b, _, _ in issues['token']],
               'untranslated': issues['untranslated']},
              open(os.path.join(WORK, 'trans', '_validate_report.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)

if __name__ == '__main__':
    main()
