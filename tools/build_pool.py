# Collect every unique Japanese string to translate, with a stable id and source tag.
# Split into "term" (short names -> glossary first) and "text" (sentences).
import json, os, struct, sys, re
sys.path.insert(0, 'tools')
import csvb, dictbin

JP = re.compile(r'[぀-ヿ一-鿿]')
def has_jp(s): return bool(JP.search(s))

pool = {}   # jp -> dict(id, jp, srcs=set, kind)
def add(jp, src):
    if not jp or not has_jp(jp):
        return
    e = pool.get(jp)
    if e is None:
        e = pool[jp] = dict(jp=jp, srcs=[src])
    elif src not in e['srcs']:
        e['srcs'].append(src)

# 1) CSVB row strings
j = json.load(open('text_dump.json', encoding='utf-8'))
for f, rows in j.items():
    for r in rows:
        add(r['text'], 'csvb:' + f)

# 2) mm01.advcmd ADV dialogue
d = open(r'extracted\mission\mm01.advcmd', 'rb').read()
ntab, colreg, strbase, strend, extra, zero = struct.unpack('>6I', d[8:32])
p = strbase
while p < strend:
    e = d.index(b'\0', p)
    try:
        s = d[p:e].decode('utf-8')
        add(s, 'advcmd:mm01')
    except UnicodeDecodeError:
        pass
    p = e + 1

# 3) dictionaries (name/text/cv/height/weight fields)
for f in ['character.cbin', 'glossary.gbin', 'robot.rbin']:
    for ent in dictbin.dump(f'extracted/dictionary/{f}'):
        for k, v in ent.items():
            if isinstance(v, str):
                add(v, 'dict:' + f)

# 4) EBOOT strings (skip ones already translated)
already = set(json.load(open('eboot_ko.json', encoding='utf-8')).keys())
for e in json.load(open('eboot_strings.json', encoding='utf-8')):
    if e['jp'] not in already:
        add(e['jp'], 'eboot')

# classify: term = short, single-line, no % control -> glossary candidates
def is_term(jp):
    return ('\n' not in jp and len(jp) <= 12 and '%' not in jp
            and '@i(' not in jp and '[$' not in jp)

items = []
for i, (jp, e) in enumerate(sorted(pool.items())):
    e['id'] = i
    e['kind'] = 'term' if is_term(jp) else 'text'
    items.append(e)

json.dump(items, open('translate_pool.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=0)
terms = [e for e in items if e['kind'] == 'term']
texts = [e for e in items if e['kind'] == 'text']
print(f'unique strings: {len(items)}')
print(f'  term(용어): {len(terms)}개  {sum(len(e["jp"]) for e in terms):,}자')
print(f'  text(문장): {len(texts)}개  {sum(len(e["jp"]) for e in texts):,}자')

os.makedirs('trans', exist_ok=True)

def dump_chunks(rows, prefix, n_chunks):
    # balance by character count, never splitting a row
    total = sum(len(e['jp']) for e in rows)
    target = total / n_chunks
    chunks = [[] for _ in range(n_chunks)]
    ci = 0; acc = 0
    for e in rows:
        chunks[ci].append({'id': e['id'], 'jp': e['jp']})
        acc += len(e['jp'])
        if acc >= target and ci < n_chunks - 1:
            ci += 1; acc = 0
    for i, c in enumerate(chunks):
        json.dump(c, open(f'trans/{prefix}_{i}.json', 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=0)
    print(f'  {prefix}: {n_chunks} chunks, '
          f'{[len(c) for c in chunks]} items, '
          f'{[sum(len(x["jp"]) for x in c) for c in chunks]} chars')

dump_chunks(terms, 'pool_term', 3)
dump_chunks(texts, 'pool_text', 9)
