# Patch Japanese UI strings inside the decrypted EBOOT ELF, in place.
# Korean UTF-8 must fit the original NUL-terminated slot; remainder is zero-filled,
# so no ELF offsets change and the file size stays identical.
import json, sys, os

def patch(elf_path, tl_path, out_path, strings_path='eboot_strings.json'):
    d = bytearray(open(elf_path, 'rb').read())
    tl = json.load(open(tl_path, encoding='utf-8'))
    strings = json.load(open(strings_path, encoding='utf-8'))

    by_jp = {}
    for s in strings:
        by_jp.setdefault(s['jp'], []).append(s)

    applied = missing = 0
    toolong = []
    for jp, ko in tl.items():
        ents = by_jp.get(jp)
        if not ents:
            print(f'  [MISS] not found in EBOOT: {jp[:40]!r}')
            missing += 1
            continue
        kb = ko.encode('utf-8')
        for e in ents:
            if len(kb) > e['slot']:
                toolong.append((jp, len(kb), e['slot']))
                continue
            off = e['off']
            d[off:off+e['slot']] = kb + b'\0' * (e['slot'] - len(kb))
            applied += 1
    for jp, need, have in toolong:
        print(f'  [TOO LONG] {need}B > {have}B: {jp[:40]!r}')
    open(out_path, 'wb').write(bytes(d))
    orig = os.path.getsize(elf_path)
    print(f'applied {applied} (unique {len(tl)-missing-len({t[0] for t in toolong})}), '
          f'missing {missing}, too long {len(toolong)}')
    print(f'size {os.path.getsize(out_path):,} (orig {orig:,}) '
          f'{"OK" if os.path.getsize(out_path)==orig else "SIZE CHANGED!"}')
    return len(toolong) == 0

if __name__ == '__main__':
    import os
    tl = 'eboot_ko_full.json' if os.path.exists('eboot_ko_full.json') else 'eboot_ko.json'
    print(f'using {tl}')
    ok = patch('EBOOT.elf', tl, 'EBOOT_KR.elf')
    sys.exit(0 if ok else 1)
