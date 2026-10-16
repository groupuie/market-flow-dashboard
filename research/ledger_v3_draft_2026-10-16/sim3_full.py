#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""盤感測試 v3 草案 2 的「完整判定流程」模擬(Claude 2026-10-16 晚;回應 Astra v0.7.3 §3.1–3.4、附錄四 §七)

每一個模擬視窗都直接呼叫正式的 v3_verify.decide()(同一個估計量、2,000 次雙軸重抽、所有門檻、缺漏規則),
不是只看 H1 下界。兩種資料:
  A. 合成資料(**已知真值 = 0**):268 檔(266 股 + 2 指數),每天約 12 個買點;報酬 = β × 大盤 + 個股自己的波動(厚尾),
     持有 1–20 天(指數 3–40 天)、彼此重疊;判讀和之後的報酬無關 → 任何 PASS 都是誤判
  B. 歷史資料庫(266 檔 2016-01 ~ 2026-07 的真實買點 + SPY / QQQ;**只是固定歷史庫的壓力測試**,固定偏好那兩種沒有已知真值)
沒有判斷力的貼法:random(每筆擲銅板,同意比例 a)、stock(每檔股票固定偏好:同意機率 0.2 或 0.7)、market(大盤近 20 天漲 → 同意 0.6,跌 → 0.25)
有判斷力(功效):同一天同類型內,報酬排名越前面越容易同意:P(同意) = sigmoid(logit(a) + κ × (排名 − 0.5));κ 對齊「每筆平均多 δ 個百分點」

**選擇規則(正式跑之前定)**:日期區塊長度 L 從 {5, 10, 20} 裡,選「在合成資料的 random / stock / market 三種貼法、120 天、各 300 個視窗下,
H1 下界 > 0 的比例:點估計 ≤ 3.5%,而且 Wilson 95% 下界 ≤ 2.5%(= 沒有顯著高於名目的 2.5%)」的最小 L;都不行就用 20 並標示。
(原本寫「Wilson 上界 ≤ 5%」。30 個視窗的試跑(`sim3_smoke_30windows.json`,全部保存)之後發現:真的誤判率剛好 2.5% 時,
200 個視窗的 Wilson 上界大約 5.7%,原規則幾乎不可能過 → 在正式跑之前改成上面這條。)
選 L 用 seed 20261101;所有正式報告的數字用另一個 seed 20261202 重新跑(避免只挑最好看的一組)。
用法:python3 -I sim3_full.py <repo> <p1_events_d266.csv.gz> <SPY/QQQ 資料夾(manifest + adjusted)> <輸出 json> [--quick]
"""
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
def synth(seed, n_days=2800, df_idio=3.0):
    rng = np.random.default_rng(seed)
    S = 268; idx = {266: 'SPY', 267: 'QQQ'}
    syms = [f'Z{k:03d}' for k in range(266)] + ['SPY', 'QQQ']
    mkt = rng.standard_t(4, n_days) * 0.011 / math.sqrt(4 / 2)                       # 大盤每天,平均 0
    beta = np.r_[rng.uniform(0.6, 1.8, 266), 1.0, 1.2]
    sd = np.r_[np.full(266, 0.02), 0.002, 0.004]
    idio = rng.standard_t(df_idio, (S, n_days)) * (sd[:, None] / math.sqrt(df_idio / (df_idio - 2)))
    daily = np.clip(beta[:, None] * mkt[None, :] + idio, -0.6, 1.5)
    L = np.cumsum(np.log1p(daily), axis=1)
    q = np.r_[rng.gamma(2.0, 0.045 / 2.0, 266), 0.03, 0.03]                           # 每檔每天出現買點的機率(平均每天約 12 筆)
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
    t0 = time.time(); cfg0 = dict(V.SPEC)
    hist_ev, hist_cal, hist_m20 = load_hist()
    syn_ev, syn_cal, syn_m20 = synth(7)
    syn_ev_heavy, _, _ = synth(8, df_idio=2.5)
    OUTJ = {'meta': {'windows_per_scenario': NWIN, 'draws': cfg0['draws'], 'seeds': {'select_L': SEED_SEL, 'report': SEED_REP},
                     'synthetic': '268 檔、2,800 天、大盤 t4 平均 0、個股 t3(重尾情境 t2.5)、β 0.6–1.8、持有 1–20 / 3–40 天、扣 0.2%;判讀和之後報酬無關 → 真值 0',
                     'historical': f'266 檔 + SPY/QQQ 的真實買點,{hist_cal[0]} ~ {hist_cal[-1]},{len(hist_ev)} 筆(含 2010 起,視窗只取 2016 起);只是固定歷史庫的壓力測試',
                     'rule_select_L': '合成 random / stock / market、120 天、各 300 視窗:H1 下界 > 0 的比例點估計 ≤ 3.5% 且 Wilson 95% 下界 ≤ 2.5% 的最小 L(5/10/20);都不行 → 20 並標示(原規則見 docstring,試跑後改)',
                     'decide': 'v3_verify.decide(正式估計量;每個視窗一次,H2 三種模式由同一次結果判斷)'}, 'select_L': {}, 'report': {}}
    # 1. 選 L(seed SEED_SEL;合成資料 120 天)
    chosen = None
    for L in (5, 10, 20):
        cfg = dict(cfg0, date_block=L); r = {}
        for how in ('random', 'stock', 'market'):
            r[how] = run_scen(syn_ev, syn_cal, syn_m20, how, 120, SEED_SEL + L, cfg, nwin=(30 if QUICK else 300))
            print('select', L, how, r[how]['H1_lb_gt0'], round(time.time() - t0), flush=True)
        OUTJ['select_L'][str(L)] = r
        if chosen is None and all(r[h]['H1_lb_gt0']['pct'] <= 3.5 and r[h]['H1_lb_gt0']['wilson95'][0] <= 2.5 for h in r): chosen = L
    OUTJ['chosen_L'] = chosen or 20; OUTJ['chosen_L_note'] = '符合規則' if chosen else '三個都不符合 → 用 20(標示)'
    cfg = dict(cfg0, date_block=OUTJ['chosen_L'])
    # 2. 正式報告(seed SEED_REP)
    scen = []
    for T in (120, 250):
        scen += [('synthetic', 'random', T, 0.43, None), ('synthetic', 'random', T, 0.25, None), ('synthetic', 'random', T, 0.70, None),
                 ('synthetic', 'stock', T, 0.43, None), ('synthetic', 'market', T, 0.43, None), ('synthetic_heavy', 'random', T, 0.43, None),
                 ('synthetic', 'random', T, 0.43, 'mixed'), ('synthetic', 'random', T, 0.43, 'agree_only'),
                 ('historical', 'random', T, 0.43, None), ('historical', 'stock', T, 0.43, None), ('historical', 'market', T, 0.43, None)]
    for k, (src, how, T, a, miss) in enumerate(scen):
        ev, ca, mm = {'synthetic': (syn_ev, syn_cal, syn_m20), 'synthetic_heavy': (syn_ev_heavy, syn_cal, syn_m20), 'historical': (hist_ev, hist_cal, hist_m20)}[src]
        key = f'{src}|{how}|T{T}|a{a}|miss={miss}'
        OUTJ['report'][key] = run_scen(ev, ca, mm, how, T, SEED_REP + k, cfg, a=a, missing=miss)
        print(key, OUTJ['report'][key]['H1_lb_gt0']['pct'], OUTJ['report'][key]['PASS'], round(time.time() - t0), flush=True)
    # 3. 功效:歷史庫 + 有判斷力的貼法
    OUTJ['power'] = {}
    for delta in (1.0, 2.0, 3.0):
        kap = calibrate_kappa(hist_ev, hist_cal, delta, 0.43, SEED_REP)
        for T in (120, 250):
            key = f'historical|skill|delta{delta}|T{T}'
            r = run_scen(hist_ev, hist_cal, hist_m20, 'skill', T, SEED_REP + int(delta * 10) + T, cfg, a=0.43, kappa=kap); r['kappa'] = kap
            OUTJ['power'][key] = r
            print(key, 'kappa', round(kap, 3), r['H1_lb_gt0']['pct'], r['PASS'], r['win_gap_agree_minus_disagree_pp_mean'], round(time.time() - t0), flush=True)
    OUTJ['meta']['seconds'] = round(time.time() - t0)
    json.dump(OUTJ, open(OUT, 'w'), ensure_ascii=False, indent=1, default=float)
