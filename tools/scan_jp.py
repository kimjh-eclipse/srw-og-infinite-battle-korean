import os, re, sys

root = sys.argv[1]
pat = re.compile(rb'(?:[\xe3][\x81-\x83][\x80-\xbf]|[\xe4-\xe9][\x80-\xbf][\x80-\xbf]){4,}')
results = []
for dirpath, _, files in os.walk(root):
    for fn in files:
        p = os.path.join(dirpath, fn)
        try:
            data = open(p, 'rb').read()
        except OSError:
            continue
        total = sum(len(m) for m in pat.findall(data))
        if total > 100:
            results.append((total, os.path.relpath(p, root)))
results.sort(reverse=True)
for t, p in results[:80]:
    print(f"{t}\t{p}")
print(f"-- {len(results)} files with JP text --")
