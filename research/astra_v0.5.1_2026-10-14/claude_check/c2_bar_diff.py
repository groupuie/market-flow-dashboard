# Claude(2026-10-14):兩份 Astra 格式行情快照逐根比較(只描述)
#   用法:python3 c2_bar_diff.py <資料夾A> <資料夾B> [輸出.json]
#   每檔:哪些日期不同、哪個欄位(開高低收 / 量)、最大相對差;不判斷對錯
import json, sys, os, math
from collections import Counter
A, B = sys.argv[1], sys.argv[2]; OUT = sys.argv[3] if len(sys.argv) > 3 else None
def bars(d, s):
    m = json.load(open(os.path.join(d, 'manifest.json')))['symbols'][s]
    return {b[0]: b[1:] for b in json.load(open(os.path.join(d, m['adjustedFile'])))['bars']}
syms = sorted(json.load(open(os.path.join(A, 'manifest.json')))['symbols'])
res = {}
for s in syms:
    x, y = bars(A, s), bars(B, s)
    dd = sorted(set(x) ^ set(y)); diff = []; mx = 0.0; vol = 0; fields = Counter()
    for d in sorted(set(x) & set(y)):
        a, b = x[d], y[d]
        if a == b: continue
        r = [abs(a[i] - b[i]) / abs(a[i]) for i in range(4)]
        for i, k in enumerate('ohlc'):
            if a[i] != b[i]: fields[k] += 1
        if a[4] != b[4]: fields['v'] += 1; vol += 1
        mx = max(mx, max(r)); diff.append(d)
    res[s] = {'datesOnlyOne': dd, 'nDiff': len(diff), 'first': diff[0] if diff else None, 'last': diff[-1] if diff else None,
              'maxRelPrice': mx, 'fields': dict(fields), 'volumeDiffDates': [d for d in diff if x[d][4] != y[d][4]][-5:]}
same = [s for s in syms if res[s]['nDiff'] == 0 and not res[s]['datesOnlyOne']]
print('完全相同', len(same), '/', len(syms))
bins = Counter()
for s in syms:
    m = res[s]['maxRelPrice']
    bins['價格相同' if m == 0 else '<1e-12' if m < 1e-12 else '<1e-9' if m < 1e-9 else '<1e-6' if m < 1e-6 else '<1e-3' if m < 1e-3 else '>=1e-3'] += 1
print('最大相對價差分布', dict(bins))
vol_only = [s for s in syms if res[s]['nDiff'] and res[s]['maxRelPrice'] == 0]
print('只有成交量不同', len(vol_only), vol_only[:20])
lastd = Counter(res[s]['last'] for s in syms if res[s]['nDiff'])
print('最後一個不同日期的分布', lastd.most_common(8))
firstd = Counter(res[s]['first'] for s in syms if res[s]['nDiff'])
print('第一個不同日期的分布', firstd.most_common(8))
for s in sys.argv[4].split(',') if len(sys.argv) > 4 else []:
    print(s, json.dumps(res[s]))
if OUT: json.dump(res, open(OUT, 'w'), indent=1)
