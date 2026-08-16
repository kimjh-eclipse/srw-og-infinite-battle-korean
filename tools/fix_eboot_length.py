# Shorten EBOOT translations that overflow their slot. Japanese full-width chars and
# Hangul are both 3 bytes, so equal glyph counts fit; the overflow is almost always an
# added space or a longer verb ending. Apply space-strip + UI-term normalization, keep
# the shortest candidate that fits, and only leave truly un-shrinkable ones (rare).
import json, os, re

WORK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
full = json.load(open(os.path.join(WORK, 'eboot_ko_full.json'), encoding='utf-8'))
manual = set(json.load(open(os.path.join(WORK, 'eboot_ko.json'), encoding='utf-8')).keys())
slots = {e['jp']: e['slot'] for e in
         json.load(open(os.path.join(WORK, 'eboot_strings.json'), encoding='utf-8'))}

def blen(s): return len(s.encode('utf-8'))

# UI term normalization (game-conventional, shorter) — applied only when needed.
TERMS = [
    ('돌아갑니다', '뒤로'), ('돌아가기', '뒤로'), ('돌아간다', '뒤로'),
    ('되돌리기', '되돌림'), ('되돌립니다', '되돌림'),
    ('커서 이동', '커서이동'), ('길게 누르기', '길게누름'),
    ('하시겠습니까', '하시겠습니까'),
    ('실시합니다', '합니다'), ('재개합니다', '재개'),
    ('변경합니다', '변경'), ('설정합니다', '설정'),
    ('표시 내용 변경', '표시변경'),
]

# Per-string overrides where the Japanese is too short for a literal Korean.
EXTRA = {
    '残数': '잔량', '外す': '해제', '赤い枠': '적색', '赤枠': '적색', '青枠': '청색',
    '次へ': '다음', '元に戻す': '원래대로', '初期状態に戻す': '초기상태로',
    '機体選択に戻る': '기체선택으로', '工事中です': '공사중',
    '出撃しますか？': '출격?', '途中経過をセーブしますか？': '진행상황저장?',
    '１．敵軍の戦力値を０にする': '1.적 전력０으로', 'イベントは初期済みです。\n': '이벤트 초기화됨\n',
    '%s%s長押し': '%s%s길게', '@i(0)素早く下上': '@i(0)빠르게상하',
}

def candidates(ko, jp=None):
    if jp in EXTRA:
        yield EXTRA[jp]
    yield ko
    yield ko.replace(' ', '')                       # drop ASCII spaces (keep 　 separators)
    s = ko
    for a, b in TERMS:
        s = s.replace(a, b)
    yield s
    yield s.replace(' ', '')

fixed = still = 0
report = []
for jp, ko in list(full.items()):
    slot = slots.get(jp)
    if slot is None or blen(ko) <= slot:
        continue
    if jp in manual:                     # respect hand-reviewed strings
        continue
    best = None
    for c in candidates(ko, jp):
        if blen(c) <= slot:
            best = c; break
    if best and best != ko:
        full[jp] = best; fixed += 1
    else:
        still += 1
        report.append((jp, ko, slot, blen(ko)))

json.dump(full, open(os.path.join(WORK, 'eboot_ko_full.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print(f'fixed {fixed}, still-too-long {still}')
# categorize remaining: debug logs vs real UI
def is_debug(jp):
    bad = ['失敗','エラー','コマンド','pFifo','FIFO','スレッド','マトリクス','ノード',
           '描画','確保','不正','処理','メモリ','初期化','ハンドル','バッファ','影']
    return any(b in jp for b in bad)
ui_remain = [r for r in report if not is_debug(r[0])]
print(f'  remaining UI (non-debug): {len(ui_remain)}')
for jp, ko, sl, nl in ui_remain[:30]:
    print(f'  {sl}<{nl}  {jp!r} -> {ko!r}')
