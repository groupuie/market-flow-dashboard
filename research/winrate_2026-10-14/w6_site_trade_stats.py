# Claude 2026-10-14:網站「買 / 賣」(v2.4 I1 + I2;一次一筆)的歷史成績 → index.html SW_TS(滑過那一行)
#   規則 = scripts/astra_trades.py(= index.html swTradesJS);訊號 = scripts/astra_data.py sw_series(= swSeriesJS)
#   價格 = Claude 10/13 Yahoo 快照、照網站四捨五入(rp);全期歷史(2004 起)算訊號;統計訊號日 2010-01-01 ~ 2026-07-31、已賣出的筆
#   分組同網站:idx = SPY/QQQ(丙)、mag = 七巨頭、ndx = Nasdaq-100 扣七巨頭、all = 追蹤股 266 檔(後三組 = 乙);槓桿 1/2/3 倍 = 每日合成(不含費用)
#   另附「不分一次一筆」的每個買點(per-signal)數字,和 W5 對照
#   用法:python3 -I w6_site_trade_stats.py <Claude 10/13 快照資料夾>  → w6_result.json
import json, os, sys, statistics as st
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..', '..')
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import astra_data as AD, astra_trades as AT
D = sys.argv[1]
man = json.load(open(f'{D}/manifest.json'))['symbols']
uni = [s.strip() for s in open(os.path.join(HERE, '..', 'astra_v0.5.0_2026-10-13', 'universe_266.txt')) if s.strip() and not s.startswith('#')]
html = open(os.path.join(ROOT, 'index.html'), encoding='utf-8').read()
def jsset(name):
    a = html.index('const ' + name + '=new Set([') + len('const ' + name + '=new Set([')
    return set(x.strip().strip("'") for x in html[a:html.index('])', a)].split(','))
MAG, NDX = jsset('SW_MAG'), jsset('SW_NDX')
def grp(s): return 'idx' if s in AT.IDX else 'mag' if s in MAG else 'ndx' if s in NDX else 'all'
A0, A1 = '2010-01-01', '2026-07-31'
RG = json.load(open(os.path.join(HERE, '..', 'expectancy_2026-10-14', 'regime_2026-10-14.json')))   # 大盤恐慌(強)只有 2021-03-17 起
SC = dict(zip(RG['d'], RG['sc']))
acc = {}   # (group, lev, cost, mode) -> [(ret, hold, why)]
def add(key, v): acc.setdefault(key, []).append(v)
for s in uni + ['SPY', 'QQQ']:
    b = json.load(open(f"{D}/{man[s]['adjustedFile']}"))['bars']
    pb = [[x[0], AD.rp(x[1]), AD.rp(x[2]), AD.rp(x[3]), AD.rp(x[4]), x[5]] for x in b]
    W = AD.sw_series(pb); O = [x[1] for x in pb]; C = [x[4] for x in pb]; Dt = W['D']; n = W['n']
    sty = AT.style_of(s); tops = set(W['top'])
    series = {1: (O, C), 2: AT.lev_open_close(O, C, 2)}
    if s in AT.IDX: series[3] = AT.lev_open_close(O, C, 3)   # 3 倍只給指數(TQQQ、SPXL、UPRO)
    gs = [grp(s)] + (['all'] if grp(s) in ('mag', 'ndx') else [])   # all = 全部 266(含七巨頭、NDX)
    path = AT.trades(W, O, sty)
    sig = [{'i': i, 'k': k, 'e': i + 1} for i, k in AT.buy_points(W)]
    for t in sig:
        d, why = AT.exit_of(W, O, t['i'], sty, tops); t.update(d=d, why=why, x=None if d is None else d + 1)
    for mode, TT in (('path', path), ('sig', sig)):
        for t in TT:
            if t['x'] is None or t['x'] >= n or not (A0 <= Dt[t['i']] <= A1): continue
            for L, (o, c) in series.items():
                for cost in (0.0, 0.001):
                    r = AT.ret(o, t['e'], t['x'], cost)
                    if r is None: continue   # 合成槓桿已歸零
                    for g in gs: add((g, L, cost, mode), (r, t['x'] - t['e'], t['why']))
                    sc = SC.get(Dt[t['i']])
                    if sc is not None and L == 1 and cost == 0.0:   # 強 / 一般(2021-03 起,只做 1 倍、成本 0)
                        for g in gs: add((g, L, cost, mode + ('_strong' if sc >= 2 else '_calm')), (r, t['x'] - t['e'], t['why']))
def summ(v):
    rs = sorted(x[0] for x in v); w = [x for x in rs if x > 0]; l = [x for x in rs if x <= 0]
    wh = {}
    for x in v: wh[x[2]] = wh.get(x[2], 0) + 1
    return {'n': len(rs), 'w': round(100 * len(w) / len(rs), 1), 'aw': round(100 * st.mean(w), 1) if w else None,
            'al': round(100 * st.mean(l), 1) if l else None, 'ev': round(100 * st.mean(rs), 2), 'mx': round(100 * rs[0], 1),
            'p05': round(100 * rs[int(0.05 * len(rs))], 1), 'hd': round(st.mean(x[1] for x in v), 1),
            'why': {k: round(100 * c / len(v), 1) for k, c in sorted(wh.items())}}
out = {'note': '網站買/賣(一次一筆)與每個買點的歷史成績;訊號日 2010-01-01~2026-07-31;成本 0 與每邊 0.1%;槓桿 = 每日合成、不含費用;_strong/_calm = 2021-03-17 起依 regime.json(sc ≥ 2 = 強)',
       'rules': {'idx': '丙:第一個頂 / 40 根', 'mag|ndx|all': '乙:第一個頂 / 收盤 ≤ 買價 −8% / 20 根'}, 'stats': {}}
for (g, L, cost, mode), v in sorted(acc.items()):
    out['stats'][f'{mode}|{g}|{L}x|c{cost}'] = summ(v)
json.dump(out, open(os.path.join(HERE, 'w6_result.json'), 'w'), ensure_ascii=False, indent=1)
for k, v in out['stats'].items():
    if '|c0.0' in k or '1x|c0.001' in k: print(k, v)
