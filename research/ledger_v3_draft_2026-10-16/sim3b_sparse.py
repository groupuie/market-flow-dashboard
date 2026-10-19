#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v3 草案 2 模擬的補充(Claude 2026-10-16 晚;回應 Astra v0.7.3 §3.2「模擬要包含 80 配對日門檻附近的稀疏情境」)
函式和 sim3_full.py 相同(這支是複製出來加參數,原檔不改);只差:合成資料每檔每天出現買點的機率乘上 q_scale(0.12 / 0.18 / 0.25 / 0.30 / 0.35 / 0.40),
讓 120 天的有配對日期落在 80 附近;貼法 random / stock;日期區塊 L = 5(sim3_full 選定);seed 20261303
用法:python3 -I sim3b_sparse.py <repo> <p1_events_d266.csv.gz> <SPY/QQQ 資料夾> <輸出 json>"""

import csv, gzip, json, math, os, sys, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import v3_verify as V

REPO, EVF, DD, OUT = sys.argv[1:5]; QUICK = '--quick' in sys.argv
NWIN = 30 if QUICK else 200
SEED_SEL, SEED_REP = 20261101, 20261202
man = json.loads(V.Git(REPO).show('origin/astra-ledger', 'engine_manifest.json'))
V.load_engine(V.Git(REPO), man['main_commit'], man['files'])
AD, AT = V.AD, V.AT


def wilson(k, n, z=1.96):
    if n == 0: return (None, None)
    p = k / n; d = 1 + z * z / n; c = p + z * z / (2 * n); h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (100 * (c - h) / d, 100 * (c + h) / d)


# ---------------------------------------------------------------- 歷史資料庫
def load_hist():
    rows = list(csv.DictReader(gzip.open(EVF, 'rt')))
    ev = [(r['date'], 'stock', r['sym'], float(r['ret_net_0.1pct_each_side'])) for r in rows]
    m = json.load(open(os.path.join(DD, 'manifest.json')))['symbols']
    spy = None
    for s in ('SPY', 'QQQ'):
        b = json.load(open(os.path.join(DD, m[s]['adjustedFile'])))['bars']
        pb = [[x[0], AD.rp(x[1]), AD.rp(x[2]), AD.rp(x[3]), AD.rp(x[4]), x[5]] for x in b]
        if s == 'SPY': spy = [x[0] for x in pb]; spyc = [x[4] for x in pb]
        W = AD.sw_series(pb); O = [x[1] for x in pb]; tops = set(W['top'])
        for i, k in AT.buy_points(W):
            if not ('2010-01-01' <= W['D'][i] <= '2026-07-31') or i + 1 >= W['n']: continue
            d, why = AT.exit_of(W, O, i, AT.STY['c'], tops)
            if d is None or d + 1 >= W['n']: continue
            ev.append((W['D'][i], 'idx', s, AT.ret(O, i + 1, d + 1, 0.001)))
    cal = [d for d in spy if '2016-01-01' <= d <= '2026-07-31']
    m20 = {spy[k]: spyc[k] / spyc[k - 20] - 1 for k in range(20, len(spy))}
    return ev, cal, m20


# ---------------------------------------------------------------- 合成資料(已知真值 0)
def synth(seed, n_days=2800, df_idio=3.0, q_scale=1.0):
    rng = np.random.default_rng(seed)
    S = 268; idx = {266: 'SPY', 267: 'QQQ'}
    syms = [f'Z{k:03d}' for k in range(266)] + ['SPY', 'QQQ']
    mkt = rng.standard_t(4, n_days) * 0.011 / math.sqrt(4 / 2)                       # 大盤每天,平均 0
    beta = np.r_[rng.uniform(0.6, 1.8, 266), 1.0, 1.2]
    sd = np.r_[np.full(266, 0.02), 0.002, 0.004]
    idio = rng.standard_t(df_idio, (S, n_days)) * (sd[:, None] / math.sqrt(df_idio / (df_idio - 2)))
    daily = np.clip(beta[:, None] * mkt[None, :] + idio, -0.6, 1.5)
    L = np.cumsum(np.log1p(daily), axis=1)
    q = np.r_[rng.gamma(2.0, 0.045 / 2.0, 266), 0.03, 0.03] * q_scale                           # 每檔每天出現買點的機率(平均每天約 12 筆)
    sig = rng.random((S, n_days)) < q[:, None]
    ev = []; days = [f'D{t:04d}' for t in range(n_days)]
    for s in range(S):
        ts = np.flatnonzero(sig[s, :n_days - 45])
        if s >= 266: h = np.where(rng.random(len(ts)) < 0.4, 40, rng.integers(3, 40, len(ts)))
        else: h = np.where(rng.random(len(ts)) < 0.25, 20, rng.integers(1, 20, len(ts)))
        r = np.expm1(L[s, ts + h] - L[s, ts]) - 0.002
        typ = 'idx' if s >= 266 else 'stock'
        ev += [(days[t], typ, syms[s], float(x)) for t, x in zip(ts, r)]
    m20 = {days[t]: float(np.expm1(np.log1p(mkt[t - 19:t + 1]).sum())) for t in range(20, n_days)}
    return ev, days[60:n_days - 45], m20


# ---------------------------------------------------------------- 貼標籤
def label(evw, how, a, rng, m20=None, kappa=0.0, stock_pref=None):
    n = len(evw)
    if how == 'random': p = np.full(n, a)
    elif how == 'stock': p = np.array([stock_pref[e[2]] for e in evw])
    elif how == 'market': p = np.array([0.6 if (m20.get(e[0], 0) > 0) else 0.25 for e in evw])
    elif how == 'skill':
        # 同一天同類型內的報酬排名(0 ~ 1)
        z = np.zeros(n); grp = {}
        for k, e in enumerate(evw): grp.setdefault((e[0], e[1]), []).append(k)
        rets = np.array([e[3] for e in evw])
        for ks in grp.values():
            if len(ks) > 1:
                o = np.argsort(np.argsort(rets[ks])); z[ks] = o / (len(ks) - 1) - 0.5
        lo = math.log(a / (1 - a)); p = 1 / (1 + np.exp(-(lo + kappa * z)))
    return np.where(rng.random(n) < p, 'agree', 'disagree')


def window_rows(ev_sorted, ev_dates, cal, s0, T):
    c = cal[s0:s0 + T]; lo, hi = np.searchsorted(ev_dates, c[0], 'left'), np.searchsorted(ev_dates, c[-1], 'right')
    return c, ev_sorted[lo:hi]


def run_scen(ev, cal, m20, how, T, seed, cfg, a=0.43, kappa=0.0, missing=None, nwin=NWIN):
    rng = np.random.default_rng(seed); evs = sorted(ev); evd = np.array([e[0] for e in evs])
    syms = sorted({e[2] for e in ev}); pref = {s: (0.7 if rng.random() < 0.5 else 0.2) for s in syms}
    res = {'n': 0, 'H1': 0, 'PASS': {'gap_vs_all_10pp': 0, 'agree_vs_disagree_lb': 0, 'none': 0}, 'INSUFFICIENT': 0, 'H3': 0, 'h1_pp': [], 'win_gap_ad': [], 'agree_share': [], 'paired': []}
    starts = rng.integers(0, len(cal) - T, size=nwin)
    for s0 in starts:
        c, evw = window_rows(evs, evd, cal, int(s0), T)
        if not evw: continue
        lab = label(evw, how, a, rng, m20, kappa, pref)
        rows = [(e[0], e[1], e[2], v, e[3]) for e, v in zip(evw, lab)]
        miss = []
        if missing:   # 不是隨機的缺漏:報酬最差 1% 的事件有 30% 會缺(agree_only = 只缺同意的)
            q01 = np.percentile([r[4] for r in rows], 1); keep = []
            for r in rows:
                if r[4] <= q01 and rng.random() < 0.3 and (missing != 'agree_only' or r[3] == 'agree'): miss.append(r[:4])
                else: keep.append(r)
            rows = keep
        d0 = V.decide(rows, miss, c, dict(cfg, h2_mode='none'))
        ex = d0['excluded_missing']; im = d0['agree_missing_at_minus_100pct'] or ex
        res['n'] += 1; res['h1_pp'].append(ex.get('h1_pp')); res['agree_share'].append(ex.get('agree_share')); res['paired'].append(ex.get('paired_dates'))
        res['win_gap_ad'].append((ex['win_agree_pct'] - ex['win_disagree_pct']) if ex.get('win_agree_pct') is not None and ex.get('win_disagree_pct') is not None else None)
        gates_ok = all(d0['gates'].values()); h1 = ex.get('H1') and im.get('H1')
        res['H1'] += int(bool(ex.get('H1'))); res['INSUFFICIENT'] += int(not gates_ok); res['H3'] += int(bool(ex.get('H3')))
        if gates_ok and h1:
            res['PASS']['none'] += 1
            if ex['win_agree_pct'] - ex['win_all_pct'] >= cfg['win_gap_pp'] and im['win_agree_pct'] - im['win_all_pct'] >= cfg['win_gap_pp']: res['PASS']['gap_vs_all_10pp'] += 1
            if (ex.get('win_gap_ad_lb_pp') or -1) > 0 and (im.get('win_gap_ad_lb_pp') or -1) > 0: res['PASS']['agree_vs_disagree_lb'] += 1
    n = res['n']; f = lambda k: {'k': k, 'pct': 100 * k / max(1, n), 'wilson95': wilson(k, n)}
    clean = lambda v: [x for x in v if x is not None]
    return {'windows': n, 'H1_lb_gt0': f(res['H1']), 'PASS': {m: f(k) for m, k in res['PASS'].items()}, 'INSUFFICIENT': f(res['INSUFFICIENT']), 'H3_lb_gt0': f(res['H3']),
            'h1_pp_mean': float(np.mean(clean(res['h1_pp']))) if clean(res['h1_pp']) else None, 'win_gap_agree_minus_disagree_pp_mean': float(np.mean(clean(res['win_gap_ad']))) if clean(res['win_gap_ad']) else None,
            'agree_share_mean': float(np.mean(clean(res['agree_share']))) if clean(res['agree_share']) else None, 'paired_dates_median': float(np.median(clean(res['paired']))) if clean(res['paired']) else None}


def calibrate_kappa(ev, cal, target_pp, a, seed):
    """在整個歷史庫上找 κ,使「格子等權的同意 − 不同意平均差」約等於 target(3 次貼標籤平均)"""
    rng = np.random.default_rng(seed); evs = sorted(ev)
    def h1(k):
        vals = []
        for _ in range(3):
            lab = label(evs, 'skill', a, rng, kappa=k)
            cells = {}
            for e, v in zip(evs, lab): cells.setdefault((e[0], e[1]), {'agree': [], 'disagree': []})[v].append(e[3])
            d = [np.mean(c['agree']) - np.mean(c['disagree']) for c in cells.values() if c['agree'] and c['disagree']]
            vals.append(100 * np.mean(d))
        return float(np.mean(vals))
    lo, hi = 0.0, 8.0
    for _ in range(14):
        mid = (lo + hi) / 2
        if h1(mid) < target_pp: lo = mid
        else: hi = mid
    return (lo + hi) / 2


if __name__ == '__main__':
    t0 = time.time(); cfg = dict(V.SPEC, date_block=5); out = {'meta': {'windows': NWIN, 'L': 5, 'seed': 20261303}, 'report': {}}
    for qs in (0.12, 0.18, 0.25, 0.30, 0.35, 0.40):
        ev, ca, mm = synth(11, q_scale=qs)
        for k, how in enumerate(('random', 'stock')):
            key = f'synthetic_sparse_q{qs}|{how}|T120'
            out['report'][key] = run_scen(ev, ca, mm, how, 120, 20261303 + k + int(qs * 100), cfg)
            r = out['report'][key]; print(key, 'paired', r['paired_dates_median'], 'H1', r['H1_lb_gt0']['k'], 'PASS', {m: x['k'] for m, x in r['PASS'].items()}, 'INSUF', r['INSUFFICIENT']['pct'], round(time.time() - t0), flush=True)
    json.dump(out, open(OUT, 'w'), ensure_ascii=False, indent=1, default=float)
