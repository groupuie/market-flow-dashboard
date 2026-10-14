# Claude(2026-10-14):268 檔全部,兩份下載的底/回/頂訊號差幾個;差的那天原始價格是不是「剛好平手」(只描述)
#   用法:python3 c4_flip_census.py <資料夾A> <資料夾B> <輸出.json>
#   平手 = 未還原的原始價格:底 → 今天收盤 == 昨天最高;頂 → 今天收盤 == 昨天最低;回 → 今天收盤 == 前 6 天某天收盤
#   (還原後的價格是 Yahoo 的 adjclose,只有 float32 精度、每次下載差幾個最小單位 → 平手會被隨機拆開)
import json, os, sys, gzip, importlib.util, datetime as dt
from zoneinfo import ZoneInfo
HERE = os.path.dirname(os.path.abspath(__file__))
V = os.path.join(HERE, '..', '..', 'astra_v0.5.0_2026-10-13', 'vendor', 'scripts', 'astra_data.py')
spec = importlib.util.spec_from_file_location('astra_data_pinned', V); ad = importlib.util.module_from_spec(spec); spec.loader.exec_module(ad)
A, B, OUT = sys.argv[1:4]
ROUND = len(sys.argv) > 4 and sys.argv[4] == 'round'   # round = 和網站一樣先四捨五入(≥1 元 3 位小數、<1 元 5 位)再算訊號
def load(d, s):
    m = json.load(open(os.path.join(d, 'manifest.json')))['symbols'][s]
    b = json.load(open(os.path.join(d, m['adjustedFile'])))['bars']
    if ROUND: b = [[x[0], *(round(v, 3 if v >= 1 else 5) for v in x[1:5]), x[5]] for x in b]
    return b
def raw(d, s):
    r = json.loads(gzip.decompress(open(os.path.join(d, 'raw', s + '.json.gz'), 'rb').read()))['chart']['result'][0]
    tz = ZoneInfo(r['meta']['exchangeTimezoneName']); q = r['indicators']['quote'][0]
    D = [dt.datetime.fromtimestamp(t, tz).date().isoformat() for t in r['timestamp']]
    return {D[i]: (q['high'][i], q['low'][i], q['close'][i]) for i in range(len(D))}
syms = sorted(json.load(open(os.path.join(A, 'manifest.json')))['symbols'])
tot = {k: 0 for k in ('bot', 'b2', 'top')}; flips = {k: 0 for k in tot}; tie = {k: 0 for k in tot}; per = {}
for s in syms:
    ra, rb = ad.sw_series(load(A, s)), ad.sw_series(load(B, s)); D = ra['D']; rw = raw(A, s); per[s] = {}
    for k in tot:
        sa, sb = {D[i] for i in ra[k]}, {D[i] for i in rb[k]}
        tot[k] += len(sa); diff = sorted(sa ^ sb); flips[k] += len(diff); per[s][k] = diff
        for d in diff:
            i = D.index(d); p = D[i - 1]
            try:
                h0, l0, c0 = rw[p]; c1 = rw[d][2]
                if k == 'bot' and c1 == h0: tie[k] += 1
                elif k == 'top' and c1 == l0: tie[k] += 1
                elif k == 'b2' and any(rw[D[j]][2] == c1 for j in range(i - 6, i)): tie[k] += 1
            except (KeyError, TypeError): pass
changed = [s for s in syms if any(per[s][k] for k in tot)]
res = {'rounded': ROUND, 'signalsInA': tot, 'datesDifferent': flips, 'differentDatesWithRawTieOnThatDay': tie,
       'symbolsWithAnyDifference': len(changed), 'symbols': len(syms), 'perSymbol': {s: per[s] for s in changed}}
json.dump(res, open(OUT, 'w'), ensure_ascii=False, indent=1)
print(json.dumps({k: v for k, v in res.items() if k != 'perSymbol'}, ensure_ascii=False))
