# Claude(2026-10-14):同一份程式、兩次下載(10/13 15:48 UTC、10/14)× 訊號價格是否四捨五入 → 帳戶結果差多少(只描述)
#   用法:python3 c5_account_stability.py <未四捨五入10/13 accounts.json> <未四捨五入10/14> <四捨五入10/13> <四捨五入10/14> <輸出.json>
import json, sys, statistics
def acc(p): return {(x['symbol'], x['period'], x['policy']): x for x in json.load(open(p))}
lab = ['unrounded_1013', 'unrounded_1014', 'rounded_1013', 'rounded_1014']
V = dict(zip(lab, (acc(p) for p in sys.argv[1:5])))
def med(d, p, per='B'):
    xs = sorted([x for x in d.values() if x['period'] == per and x['policy'] == p and 'ALL' in x['groups']], key=lambda x: (x['mdd'], x['symbol']))
    n = len(xs); return {'n': n, 'medianMddPct': 100 * statistics.median(x['mdd'] for x in xs),
                         'central': [[i + 1, xs[i]['symbol'], 100 * xs[i]['mdd']] for i in (n // 2 - 1, n // 2)]}
out = {'astraOriginalQuoted': {'B0_medianPct': 41.26343064, 'R1_medianPct': 41.00444811, 'ADI_B0_mddPct': 42.01310189,
                               'TXN_B0_mddPct': 41.11008641, 'KKR_B0_mddPct': 41.41677488, 'PWR_B0_mddPct': 23.7376, 'PWR_B0_returnPct': 206.1862},
       'medians_ALL_B': {l: {p: med(V[l], p) for p in ('B0', 'R1', 'E1', 'C50')} for l in lab},
       'stocks_B_B0': {s: {l: {'mddPct': 100 * V[l][(s, 'B', 'B0')]['mdd'], 'returnPct': 100 * V[l][(s, 'B', 'B0')]['return'],
                               'campaigns': V[l][(s, 'B', 'B0')]['campaigns']} for l in lab} for s in ('ADI', 'PWR', 'TJX', 'TXN', 'KKR', 'ENTG')}}
for a, b, name in [('unrounded_1013', 'unrounded_1014', 'unrounded'), ('rounded_1013', 'rounded_1014', 'rounded')]:
    x, y = V[a], V[b]
    out['between_downloads_' + name] = {'accounts': len(x), 'mddChangedOver0.1pp': sum(abs(x[k]['mdd'] - y[k]['mdd']) > .001 for k in x),
        'returnChangedOver1pp': sum(abs(x[k]['return'] - y[k]['return']) > .01 for k in x),
        'maxMddChangePp': 100 * max(abs(x[k]['mdd'] - y[k]['mdd']) for k in x),
        'top5': sorted([[*k, 100 * x[k]['mdd'], 100 * y[k]['mdd']] for k in x], key=lambda r: -abs(r[3] - r[4]))[:5]}
json.dump(out, open(sys.argv[5], 'w'), ensure_ascii=False, indent=1)
for l in lab: print(l, {p: (round(v['medianMddPct'], 6), [c[1] for c in v['central']]) for p, v in out['medians_ALL_B'][l].items()})
print({k: {kk: vv for kk, vv in v.items() if kk != 'top5'} for k, v in out.items() if k.startswith('between')})
