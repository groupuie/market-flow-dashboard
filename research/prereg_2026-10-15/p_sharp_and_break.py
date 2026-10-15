# Claude 2026-10-15 預先登記 P1 / P2 的分析程式(見 PREREG.md;這支在下載樣本外資料之前就 commit 凍結)
#   P1 急跌後的買點:網站買點(▲底 ∪ △回)裡,訊號那天收盤比 6 根前低 ≥ 15% 的「急跌後買點」,扣成本平均報酬是否比其他買點低
#   P2 破線(減碼提醒):上升趨勢(20 日線 > 50 日線)中第一次收盤跌破 20 日線,之後 20 天的報酬是否比一般上升趨勢日低
#   用法:python3 -I p_sharp_and_break.py <資料夾(manifest.json + adjusted/*.json)> <名單檔> <SPY 檔> <輸出 json> [--quick]
import json, os, sys, math, random, statistics as st
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..', '..')
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import astra_data as AD, astra_trades as AT
import numpy as np

A0, A1 = '2010-01-01', '2026-07-31'
COST = 0.001
SHARP = -0.15; SHARP_LB = 6          # P1:C[i] / C[i−6] − 1 ≤ −15%
H = 20; H2 = 10                      # P2:之後 20(主)/ 10(次)根
COOL = 5                             # P2 破線冷卻(同網站其他記號)
BLOCK, DRAWS, SEED = 21, 2000, 20261015
LO_P, HI_P = 1.25, 98.75             # 兩個假設 → 每個用 97.5% 區間(Bonferroni)


def sma(C, w):
    out = [None] * len(C); s = 0.0
    for i, c in enumerate(C):
        s += c
        if i >= w: s -= C[i - w]
        if i >= w - 1: out[i] = s / w
    return out


def load(D, sym, man):
    b = json.load(open(os.path.join(D, man[sym]['adjustedFile'])))['bars']
    return [[x[0], AD.rp(x[1]), AD.rp(x[2]), AD.rp(x[3]), AD.rp(x[4]), x[5]] for x in b]


def run(D, syms, spy_dates):
    man = json.load(open(os.path.join(D, 'manifest.json')))['symbols']
    P1, P2b, P2u, skipped = [], [], [], {}
    for s in syms:
        if s not in man: skipped[s] = '沒有資料'; continue
        pb = load(D, s, man)
        if len(pb) < 60: skipped[s] = '不到 60 根'; continue
        W = AD.sw_series(pb); n = W['n']; Dt = W['D']; O = [x[1] for x in pb]; C = [x[4] for x in pb]
        sty = AT.style_of(s); tops = set(W['top'])
        # ---- P1
        for i, k in AT.buy_points(W):
            if not (A0 <= Dt[i] <= A1) or i < SHARP_LB or i + 1 >= n: continue
            d, why = AT.exit_of(W, O, i, sty, tops)
            if d is None or d + 1 >= n: continue
            r = AT.ret(O, i + 1, d + 1, COST)
            P1.append((Dt[i], C[i] / C[i - SHARP_LB] - 1 <= SHARP, r, why, k, s))
        # ---- P2
        s20, s50 = sma(C, 20), sma(C, 50); last = -10 ** 9
        for t in range(50, n):
            if s20[t] is None or s50[t] is None or s20[t - 1] is None: continue
            up = s20[t] > s50[t]
            brk = up and C[t] < s20[t] and C[t - 1] >= s20[t - 1] and t - last > COOL
            if brk: last = t
            if not (A0 <= Dt[t] <= A1) or t + H >= n: continue
            if up:
                f20 = C[t + H] / O[t + 1] - 1; f10 = C[t + H2] / O[t + 1] - 1
                P2u.append((Dt[t], f20, f10))
                if brk: P2b.append((Dt[t], f20, f10, s))
    return P1, P2b, P2u, skipped


def day_agg(events, val, days):
    idx = {d: i for i, d in enumerate(days)}; s = np.zeros(len(days)); c = np.zeros(len(days))
    for e in events:
        i = idx.get(e[0])
        if i is None: continue
        s[i] += val(e); c[i] += 1
    return s, c


def block_boot(days, groups, stat, draws=DRAWS, seed=SEED, block=BLOCK):
    """連續 block 個交易日的移動區塊重抽(整個交易日曆;沒事件的日子也在);groups = {name: (sum_by_day, count_by_day)}"""
    n = len(days); rng = np.random.default_rng(seed); nb = math.ceil(n / block); starts = np.arange(0, n - block + 1)
    out = []
    for _ in range(draws):
        st_ = rng.choice(starts, size=nb, replace=True)
        pick = (st_[:, None] + np.arange(block)[None, :]).ravel()[:n]
        agg = {k: (v[0][pick].sum(), v[1][pick].sum()) for k, v in groups.items()}
        x = stat(agg)
        if x is not None: out.append(x)
    out = np.array(out)
    return {'lo': float(np.percentile(out, LO_P)), 'hi': float(np.percentile(out, HI_P)), 'draws': int(len(out))}


def desc(rs):
    rs = sorted(rs)
    if not rs: return {'n': 0}
    return {'n': len(rs), 'mean': 100 * st.mean(rs), 'median': 100 * st.median(rs), 'win': 100 * sum(r > 0 for r in rs) / len(rs),
            'p05': 100 * rs[int(.05 * len(rs))]}


def analyze(P1, P2b, P2u, days):
    out = {}
    sh = [e for e in P1 if e[1]]; ns = [e for e in P1 if not e[1]]
    out['P1'] = {'sharp': {**desc([e[2] for e in sh]), 'stop_rate': 100 * sum(e[3] == '停損' for e in sh) / max(1, len(sh))},
                 'other': {**desc([e[2] for e in ns]), 'stop_rate': 100 * sum(e[3] == '停損' for e in ns) / max(1, len(ns))},
                 'sharp_bot_only': desc([e[2] for e in sh if e[4] == '底'])}
    g = {'sh': day_agg(sh, lambda e: e[2], days), 'ns': day_agg(ns, lambda e: e[2], days)}
    out['P1']['diff_mean_pp'] = out['P1']['sharp'].get('mean', float('nan')) - out['P1']['other'].get('mean', float('nan'))
    out['P1']['ci97_5'] = block_boot(days, g, lambda a: (a['sh'][0] / a['sh'][1] - a['ns'][0] / a['ns'][1]) * 100 if a['sh'][1] and a['ns'][1] else None)
    out['P1']['pass'] = out['P1']['ci97_5']['hi'] < 0
    out['P2'] = {'break': {**desc([e[1] for e in P2b]), 'p_le_-10': 100 * sum(e[1] <= -0.10 for e in P2b) / max(1, len(P2b)), 'f10': desc([e[2] for e in P2b])},
                 'uptrend_days': {**desc([e[1] for e in P2u]), 'p_le_-10': 100 * sum(e[1] <= -0.10 for e in P2u) / max(1, len(P2u)), 'f10': desc([e[2] for e in P2u])}}
    g2 = {'b': day_agg(P2b, lambda e: e[1], days), 'u': day_agg(P2u, lambda e: e[1], days)}
    out['P2']['diff_mean_pp'] = out['P2']['break'].get('mean', float('nan')) - out['P2']['uptrend_days'].get('mean', float('nan'))
    out['P2']['ci97_5'] = block_boot(days, g2, lambda a: (a['b'][0] / a['b'][1] - a['u'][0] / a['u'][1]) * 100 if a['b'][1] and a['u'][1] else None)
    out['P2']['pass'] = out['P2']['ci97_5']['hi'] < 0
    return out


if __name__ == '__main__':
    D, ULIST, SPYF, OUT = sys.argv[1:5]; quick = '--quick' in sys.argv
    syms = [s.strip() for s in open(ULIST) if s.strip() and not s.startswith('#')]
    if quick: syms = syms[:3]
    spy = [x[0] for x in json.load(open(SPYF))['bars']]
    days = [d for d in spy if A0 <= d <= A1]
    P1, P2b, P2u, skipped = run(D, syms, days)
    res = analyze(P1, P2b, P2u, days)
    res['meta'] = {'data_dir_manifest_sha256': __import__('hashlib').sha256(open(os.path.join(D, 'manifest.json'), 'rb').read()).hexdigest(),
                   'universe_file': os.path.basename(ULIST), 'n_symbols': len(syms), 'skipped': skipped, 'quick': quick,
                   'rules': {'sharp': f'C[i]/C[i-{SHARP_LB}]-1 <= {SHARP}', 'break': 'SMA20>SMA50 且 C<SMA20 且 前一天 C>=SMA20,冷卻 5',
                             'exit': '乙(SPY/QQQ 丙)', 'cost': COST, 'H': H, 'block': BLOCK, 'draws': DRAWS, 'seed': SEED, 'ci': [LO_P, HI_P]}}
    json.dump(res, open(OUT, 'w'), ensure_ascii=False, indent=1)
    print(json.dumps({'P1_pass': res['P1']['pass'], 'P2_pass': res['P2']['pass'], 'n_P1': len(P1), 'n_P2b': len(P2b)} if not quick else {'quick_ok': True, 'n_P1': len(P1), 'n_P2b': len(P2b), 'n_P2u': len(P2u)}, ensure_ascii=False))
