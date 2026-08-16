# Stage a small Korean text change for the in-game PoC.
import sys, os, json
sys.path.insert(0, 'tools')
import csvb

SRC = r'extracted\level_design\paramater_mission.prm'
DST = r'build_stage\level_design\paramater_mission.prm'

rows = csvb.dump(SRC)
# mission titles/briefings live in the 'misn' table; show current values around row 0
for r in rows[:12]:
    print(r['table'], r['row'], r['col'], repr(r['text']))

# Translate the first few mission strings to Korean as a visibility test.
trans = {}
KO = {
    '初回ミッション入場': '첫 미션 입장',
    '「ビギニング バーニングＰＴ」': '「비기닝 버닝ＰＴ」',
    '敵の戦力値を０にしてください。': '적의 전력치를 ０으로 만드세요.',
    '敵の戦力値は通常の２／３になっています。': '적의 전력치는 평소의 ２／３입니다.',
    '「巨大なる盾」': '「거대한 방패」',
    '「ツイン・バード」': '「트윈 버드」',
}
n = 0
for r in rows:
    if r['text'] in KO:
        trans[(r['table'], r['row'], r['col'])] = KO[r['text']]
        n += 1
print('staged replacements:', n)
os.makedirs(os.path.dirname(DST), exist_ok=True)
csvb.rebuild(SRC, trans, DST)
print('wrote', DST, os.path.getsize(DST), 'bytes (orig', os.path.getsize(SRC), ')')
# verify
back = {(x['table'], x['row'], x['col']): x['text'] for x in csvb.dump(DST)}
ok = all(back[k] == v for k, v in trans.items())
print('verify:', 'PASS' if ok else 'FAIL')
