# Claude 2026-10-14(只描述,不是候選規則):網站 Astra 真正的「買」點(▲底 / △回,Claude 10/13 重跑 episodes)換三種賣法的結果
#   丙 現狀 B0:第一個 ▼頂 隔天開盤賣,40 根內沒有頂就第 40 根賣
#   甲 勝率優先:收盤 ≥ +5% 或 ≤ −15% 隔天開盤賣,最多 60 根
#   乙 不套牢優先:第一個 ▼頂、或收盤 ≤ −8%、或第 20 根,先到先賣(都是隔天開盤)
#   乙40:同乙,但最多 40 根(= 現狀 + −8% 停損)
#   成本每邊 10 bp;IDX2x = SPY/QQQ 每日兩倍合成(不含管理費、融資成本),停利停損算在兩倍價格上
#   用法:python3 -I w5_exit_styles.py <episodes.csv.gz> <astra_v050_data 資料夾>  → w5_result.json
import gzip, csv, json, sys, os, statistics as st
EP, D = sys.argv[1], sys.argv[2]
HERE = os.path.dirname(os.path.abspath(__file__))
m = json.load(open(f'{D}/manifest.json'))['symbols']
C0 = 0.001
cache = {}
def series(s, two_x=False):
    k = (s, two_x)
    if k in cache: return cache[k]
    b = json.load(open(f"{D}/{m[s]['adjustedFile']}"))['bars']
    d = [x[0] for x in b]; o = [x[1] for x in b]; c = [x[4] for x in b]
    if two_x:
        y = [c[0]]
        for i in range(1, len(c)): y.append(y[-1] * (1 + 2 * (c[i] / c[i-1] - 1)))
        yo = [y[0]] + [y[i-1] * (1 + 2 * (o[i] / c[i-1] - 1)) for i in range(1, len(c))]
        o, c = yo, y
    cache[k] = (d, {x: i for i, x in enumerate(d)}, o, c)
    return cache[k]
def net(po, pi): return (po * (1 - C0)) / (pi * (1 + C0)) - 1
def style(o, c, ie, top_exec, kind):
    """return (ret, hold_bars, mae) or None if not enough bars"""
    pe = o[ie]
    if kind == 'C':   # B0 現狀
        je = top_exec
        return net(o[je], pe), je - ie, min(c[ie:je]) / pe - 1 if je > ie else 0.0
    if kind == 'A':   # 甲 +5/-15, 60
        lim, tp, sl, use_top = 60, 0.05, 0.15, False
    elif kind == 'B': # 乙 top / -8% / 20
        lim, tp, sl, use_top = 20, None, 0.08, True
    else:             # 乙40 top / -8% / 40
        lim, tp, sl, use_top = 40, None, 0.08, True
    for j in range(ie, ie + lim):
        if j + 1 >= len(o): return None
        if use_top and top_exec is not None and j + 1 == top_exec: return net(o[j+1], pe), j + 1 - ie, min(c[ie:j+1]) / pe - 1
        if tp is not None and c[j] >= pe * (1 + tp): return net(o[j+1], pe), j + 1 - ie, min(c[ie:j+1]) / pe - 1
        if c[j] <= pe * (1 - sl): return net(o[j+1], pe), j + 1 - ie, min(c[ie:j+1]) / pe - 1
    j = ie + lim
    if j >= len(o): return None
    return net(o[j], pe), lim, min(c[ie:j]) / pe - 1
def summ(tr):
    if not tr: return None
    rs = sorted(t[0] for t in tr); w = [x for x in rs if x > 0]; l = [x for x in rs if x <= 0]
    maes = sorted(t[2] for t in tr)
    return dict(n=len(rs), win=round(100 * len(w) / len(rs), 1),
                avg_win=round(100 * st.mean(w), 2) if w else None, avg_loss=round(100 * st.mean(l), 2) if l else None,
                ev=round(100 * st.mean(rs), 2), p05=round(100 * rs[int(0.05 * len(rs))], 1), worst=round(100 * rs[0], 1),
                hold=round(st.mean(t[1] for t in tr), 1), held_ge40=round(100 * sum(1 for t in tr if t[1] >= 40) / len(rs), 1),
                mae_p05=round(100 * maes[int(0.05 * len(maes))], 1))
uni = [s.strip() for s in open(os.path.join(HERE, '..', 'astra_v0.5.0_2026-10-13', 'universe_266.txt')) if s.strip() and not s.startswith('#')]
GROUPS = {'ALL266': set(uni), 'IDX': {'SPY', 'QQQ'}, 'IDX2x': {'SPY', 'QQQ'}}
PER = {'A': ('2010-01-01', '2017-12-31'), 'B': ('2018-01-01', '2026-07-31')}
acc = {}
with gzip.open(EP, 'rt') as f:
    for r in csv.DictReader(f):
        if r['policy'] != 'B0' or r['cost'] != '0.0': continue
        s = r['symbol']; p = r['period']
        if p not in PER: continue
        ev = json.loads(r['events']); ex_date, _, ex_kind = ev[0]
        for g, mem in GROUPS.items():
            if s not in mem: continue
            d, idx, o, c = series(s, two_x=(g == 'IDX2x'))
            ie = idx[r['entry_date']]; je = idx[ex_date]
            top_exec = je if ex_kind == 'first_top' else None
            for kind in ('C', 'A', 'B', 'B40'):
                t = style(o, c, ie, je if kind == 'C' else top_exec, kind)
                if t: acc.setdefault((g, p, kind), []).append(t)
# any-day baseline for 甲 (signal-independent exits), same symbols and periods
base = {}
for g, mem in GROUPS.items():
    for s in sorted(mem):
        if s not in m: continue
        d, idx, o, c = series(s, two_x=(g == 'IDX2x'))
        for i in range(200, len(d) - 2):
            for p, (a, z) in PER.items():
                if a <= d[i] <= z:
                    t = style(o, c, i + 1, None, 'A')
                    if t: base.setdefault((g, p), []).append(t)
NAMES = {'C': '丙 現狀 B0', 'A': '甲 勝率優先 +5/-15/60', 'B': '乙 不套牢 頂/-8%/20', 'B40': '乙40 頂/-8%/40'}
out = {'note': '描述;episodes = Claude 10/13 重跑 Astra v0.5.0(未四捨五入價格);每個點各算一次,同股票的點會重疊', 'styles': {}, 'anyday_baseline_甲': {}}
for (g, p, k), tr in sorted(acc.items()): out['styles'][f'{g}|{p}|{NAMES[k]}'] = summ(tr)
for (g, p), tr in sorted(base.items()): out['anyday_baseline_甲'][f'{g}|{p}'] = summ(tr)
json.dump(out, open(os.path.join(HERE, 'w5_result.json'), 'w'), ensure_ascii=False, indent=1)
for k, v in out['styles'].items(): print(k, v)
for k, v in out['anyday_baseline_甲'].items(): print('BASE', k, v)
