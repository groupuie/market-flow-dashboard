#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""盤感測試 v3 草案 3:**統計判定層的流程模擬**(Claude 2026-10-17;回應 Astra v0.7.4 §3、附錄三)
範圍:給定「已經通過收案驗收的事件」之後,正式 v3_verify.stats() / decide() 的判定(2,000 次重抽、全部門檻、缺漏規則、三種 H2)。
**不含** GitHub 回條、批次驗收、行情重播與正式入口 — 那些在 v3_tests.py / v3_fullflow.py 另外驗。

一、方法與區塊長度的選擇規則(**這一段在任何 sim4 結果出來之前寫好並 commit**)
  候選:(M1, 5) (M1, 10) (M1, 20) (M2, 5) (M2, 10) (M2, 20),依這個順序;取第一個「下面 7 個選擇情境全部合格」的。
  M1 = 正權重雙軸重抽(日期環狀區塊 × 發行人 Exp(1),格內照權重重算);M2 = 同一組權重、發行人方向一階展開。
  選擇情境(120 天、各 300 個視窗、合成市場 synth(7)、標籤 seed 20261701 起):
    合成・擲銅板(真值 0)、合成・固定偏好股票(0)、合成・跟大盤(0)、合成・擲銅板 + 同意加 1 點(+1)、同意減 1 點(−1)、
    稠密/稀疏交替且方向相反(+1 / −1 → 0)、Astra 反例結構(+1 / −1.2 → −0.1 × 成本係數)
  每個情境都要:
    (a) 下界 > 真值 的比例:點估計 ≤ 3.5%,且 Wilson 95% 下界 ≤ 2.5%(= 沒有顯著高於名目的 2.5%)
    (b) 上界 < 真值 的比例:同上(中心沒有偏一邊)
    (c) 中心:每個視窗「重抽中位數 − 點估計」除以重抽標準差,平均在 ±0.10 之內
  六個都不合格 → 不凍結(回報,不挑)。草案 2 的舊方法(git a654145,Poisson + 移動區塊、刪空格)只在 L=5 一起算,當參照、不參選。
二、報告(用選定的方法與 L;**換新的合成市場路徑** synth(11)、厚尾 synth(12)、稀疏 synth(13),標籤 seed 20261702 起;各 200 個視窗)
  已知真值的合成情境 → 「誤判 PASS 比例」(真值 ≤ 0 時)、區間涵蓋率、兩側漏失率
  歷史固定庫(266 檔真實買點 + SPY/QQQ)→ 只叫「壓力測試的 PASS 比例」(真值未知,不叫誤判)
  功效:歷史庫 + 有判斷力的貼法(格子等權平均差 δ = 1 / 2 / 3 個百分點;不是「每筆都多賺 δ」)
  每個視窗的結果都存下來:PASS(三種 H2)、單獨 H3、上線候選(= PASS 且排除缺漏與補值兩版 H3 都過)可以直接取交集
合成報酬的成本改成和正式一樣的乘法:淨報酬 = (1 + 毛報酬) × 0.999 / 1.001 − 1
用法:
  python3 -I sim4_calibrate.py select <repo> <p1_events_d266.csv.gz> <SPY/QQQ 資料夾> <輸出資料夾>
  python3 -I sim4_calibrate.py report <repo> <events> <dd> <輸出資料夾> <shard> <nshard>
  python3 -I sim4_calibrate.py merge  <輸出資料夾>
"""
import ast, csv, gzip, hashlib, importlib.util, json, math, os, subprocess, sys, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import v3_verify as V

K_COST = 0.999 / 1.001
SEED_SEL, SEED_REP = 20261701, 20261702
NSEL, NREP = 300, 200
ORDER = [('M1', 5), ('M1', 10), ('M1', 20), ('M2', 5), ('M2', 10), ('M2', 20)]
STAT_FUNCS = ('draw_weights', 'stats', 'decide', 'h1_point', 'flip_value', 'issuer')


def stat_fingerprint():
    t = ast.parse(open(os.path.join(HERE, 'v3_verify.py'), encoding='utf-8').read())
    nodes = sorted((n for n in t.body if isinstance(n, ast.FunctionDef) and n.name in STAT_FUNCS), key=lambda n: n.name)
    return hashlib.sha256('\n'.join(ast.dump(n, include_attributes=False) for n in nodes).encode()).hexdigest()


def wilson(k, n, z=1.96):
    if n == 0: return (None, None)
    p = k / n; d = 1 + z * z / n; c = p + z * z / (2 * n); h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (100 * (c - h) / d, 100 * (c + h) / d)


def frac(k, n):
    return {'k': int(k), 'n': int(n), 'pct': 100 * k / max(1, n), 'wilson95': wilson(k, n)}


# ---------------------------------------------------------------- 資料
def load_hist(EVF, DD):
    rows = list(csv.DictReader(gzip.open(EVF, 'rt')))
    ev = [(r['date'], 'stock', r['sym'], float(r['ret_net_0.1pct_each_side'])) for r in rows]
    m = json.load(open(os.path.join(DD, 'manifest.json')))['symbols']
    AD, AT = V.AD, V.AT
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


def synth(seed, n_days=2800, df_idio=3.0, q_scale=1.0):
    """合成市場(真值 0):268 檔、大盤 t4 平均 0、個股 t(df)、β 0.6–1.8、持有 1–20 / 3–40 天;乘法成本"""
    rng = np.random.default_rng(seed)
    S = 268; syms = [f'Z{k:03d}' for k in range(266)] + ['SPY', 'QQQ']
    mkt = rng.standard_t(4, n_days) * 0.011 / math.sqrt(4 / 2)
    beta = np.r_[rng.uniform(0.6, 1.8, 266), 1.0, 1.2]; sd = np.r_[np.full(266, 0.02), 0.002, 0.004]
    idio = rng.standard_t(df_idio, (S, n_days)) * (sd[:, None] / math.sqrt(df_idio / (df_idio - 2)))
    daily = np.clip(beta[:, None] * mkt[None, :] + idio, -0.6, 1.5)
    L = np.cumsum(np.log1p(daily), axis=1)
    q = np.r_[rng.gamma(2.0, 0.045 / 2.0, 266), 0.03, 0.03] * q_scale
    sig = rng.random((S, n_days)) < q[:, None]
    ev = []; days = [f'D{t:04d}' for t in range(n_days)]
    for s in range(S):
        tt = np.flatnonzero(sig[s, :n_days - 45])
        if s >= 266: h = np.where(rng.random(len(tt)) < 0.4, 40, rng.integers(3, 40, len(tt)))
        else: h = np.where(rng.random(len(tt)) < 0.25, 20, rng.integers(1, 20, len(tt)))
        r = (1 + np.expm1(L[s, tt + h] - L[s, tt])) * K_COST - 1
        typ = 'idx' if s >= 266 else 'stock'
        ev += [(days[t], typ, syms[s], float(x)) for t, x in zip(tt, r)]
    m20 = {days[t]: float(np.expm1(np.log1p(mkt[t - 19:t + 1]).sum())) for t in range(20, n_days)}
    return ev, days[60:n_days - 45], m20


def density_window(rng, T, eff_dense, eff_sparse, alternate=True):
    """稠密 / 稀疏格子方向相反(Astra v0.7.4 反例的結構,加上雜訊):
    稠密日:同意 30(固定 A0–A29)/ 不同意 30(固定 B0–B29);稀疏日:同意 1 / 不同意 1(從 400 家池子抽,不重複用同一天)
    毛報酬 = 組平均 ± eff / 2 + 發行人效果 N(0, 1%) + 日期共同衝擊 N(0, 2%) + 個別雜訊 t3 × 4%;乘法成本
    真值 = 實際配對格子的 eff 等權平均 × 成本係數"""
    cal = [f'Q{t:03d}' for t in range(T)]
    ueff = {}
    def u(s):
        if s not in ueff: ueff[s] = rng.normal(0, 0.01)
        return ueff[s]
    rows, effs = [], []
    pool = rng.permutation(400)
    for t, d in enumerate(cal):
        dense = (t % 2 == 0) if alternate else (rng.random() < 0.5)
        shock = rng.normal(0, 0.02)
        if dense:
            ag = [f'A{k}' for k in range(30)]; dg = [f'B{k}' for k in range(30)]; e = eff_dense
        else:
            k0 = (2 * t) % 400; ag = [f'P{pool[k0]}']; dg = [f'P{pool[(k0 + 1) % 400]}']; e = eff_sparse
        for s in ag:
            g = e / 2 + u(s) + shock + rng.standard_t(3) * 0.04 / math.sqrt(3)
            rows.append((d, 'stock', s, 'agree', (1 + max(g, -0.95)) * K_COST - 1))
        for s in dg:
            g = -e / 2 + u(s) + shock + rng.standard_t(3) * 0.04 / math.sqrt(3)
            rows.append((d, 'stock', s, 'disagree', (1 + max(g, -0.95)) * K_COST - 1))
        effs.append(e)
    return rows, cal, 100 * K_COST * float(np.mean(effs))


def label(evw, how, a, rng, m20=None, kappa=0.0, stock_pref=None):
    n = len(evw)
    if how == 'random': p = np.full(n, a)
    elif how == 'stock': p = np.array([stock_pref[e[2]] for e in evw])
    elif how == 'market': p = np.array([0.6 if (m20.get(e[0], 0) > 0) else 0.25 for e in evw])
    elif how == 'skill':
        z = np.zeros(n); grp = {}
        for k, e in enumerate(evw): grp.setdefault((e[0], e[1]), []).append(k)
        rets = np.array([e[3] for e in evw])
        for ks in grp.values():
            if len(ks) > 1:
                o = np.argsort(np.argsort(rets[ks])); z[ks] = o / (len(ks) - 1) - 0.5
        lo = math.log(a / (1 - a)); p = 1 / (1 + np.exp(-(lo + kappa * z)))
    return np.where(rng.random(n) < p, 'agree', 'disagree')


def calibrate_kappa(ev, target_pp, a, seed):
    rng = np.random.default_rng(seed); evs = sorted(ev)
    def h1(k):
        vals = []
        for _ in range(3):
            lab = label(evs, 'skill', a, rng, kappa=k)
            vals.append(100 * V.h1_point([(e[0], e[1], e[2], v, e[3]) for e, v in zip(evs, lab)]))
        return float(np.mean(vals))
    lo, hi = 0.0, 8.0
    for _ in range(14):
        mid = (lo + hi) / 2
        if h1(mid) < target_pp: lo = mid
        else: hi = mid
    return (lo + hi) / 2


class Source:
    def __init__(self, ev, cal, m20):
        self.evs = sorted(ev); self.evd = np.array([e[0] for e in self.evs]); self.cal = cal; self.m20 = m20
        self.syms = sorted({e[2] for e in ev})
    def windows(self, rng, T, nwin):
        for s0 in rng.integers(0, len(self.cal) - T, size=nwin):
            c = self.cal[int(s0):int(s0) + T]
            lo, hi = np.searchsorted(self.evd, c[0], 'left'), np.searchsorted(self.evd, c[-1], 'right')
            yield c, self.evs[lo:hi]


def gen_rows(src, how, a, rng, T, nwin, kappa=0.0, shift=0.0, density=None):
    """產生 (rows, cal, truth_pp);density = (eff_dense, eff_sparse, alternate)"""
    if density:
        for _ in range(nwin):
            rows, c, truth = density_window(rng, T, *density); yield rows, c, truth
        return
    pref = {s: (0.7 if rng.random() < 0.5 else 0.2) for s in src.syms}
    for c, evw in src.windows(rng, T, nwin):
        lab = label(evw, how, a, rng, src.m20, kappa, pref)
        rows = [(e[0], e[1], e[2], v, e[3] + (shift if v == 'agree' else 0.0)) for e, v in zip(evw, lab)]
        yield rows, c, (100 * shift if how != 'skill' else None)


# ---------------------------------------------------------------- 選擇
def summarize_interval(recs, method):
    n = len(recs); lowmiss = sum(r[method]['lb'] is not None and r[method]['lb'] > r['truth'] for r in recs)
    highmiss = sum(r[method]['ub'] is not None and r[method]['ub'] < r['truth'] for r in recs)
    cen = [(r[method]['median'] - r['point']) / r[method]['sd'] for r in recs if r[method]['sd']]
    cover = n - lowmiss - highmiss
    out = {'windows': n, 'lb_above_truth': frac(lowmiss, n), 'ub_below_truth': frac(highmiss, n), 'coverage95': frac(cover, n),
           'center_mean_std_units': float(np.mean(cen)) if cen else None, 'mean_point_pp': float(np.mean([r['point'] for r in recs])),
           'mean_truth_pp': float(np.mean([r['truth'] for r in recs])), 'mean_halfwidth_pp': float(np.mean([(r[method]['ub'] - r[method]['lb']) / 2 for r in recs if r[method]['ub'] is not None]))}
    ok_side = lambda f: f['pct'] <= 3.5 and f['wilson95'][0] <= 2.5
    out['passes'] = bool(ok_side(out['lb_above_truth']) and ok_side(out['ub_below_truth']) and out['center_mean_std_units'] is not None and abs(out['center_mean_std_units']) <= 0.10)
    return out


def legacy_stats():
    """草案 2 原樣(git a654145)的 stats,只當參照"""
    b = subprocess.run(['git', '-C', HERE, 'show', 'a654145:research/ledger_v3_draft_2026-10-16/v3_verify.py'], capture_output=True, check=True).stdout
    p = os.path.join(OUTD, '_legacy_draft2.py'); open(p, 'wb').write(b)
    spec = importlib.util.spec_from_file_location('legacy_draft2', p); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    assert hashlib.sha256(b).hexdigest() == 'b3294fbcd8ba1dd21eba5eac9579d4474dcad9c2f8a649f618a7fb6cb3f2b3de'
    return m


SEL = [('syn_random', 'syn7', 'random', 0.43, {}), ('syn_stock', 'syn7', 'stock', 0.43, {}), ('syn_market', 'syn7', 'market', 0.43, {}),
       ('syn_shift_plus1', 'syn7', 'random', 0.43, {'shift': 0.01}), ('syn_shift_minus1', 'syn7', 'random', 0.43, {'shift': -0.01}),
       ('density_null_alt', None, None, None, {'density': (0.010, -0.010, True)}), ('density_astra_alt', None, None, None, {'density': (0.010, -0.012, True)})]


def run_select():
    t0 = time.time(); out = {'meta': {'stat_fingerprint': stat_fingerprint(), 'windows': NSEL, 'draws': V.SPEC['draws'], 'seed_labels': SEED_SEL,
                                      'rule': __doc__.split('二、')[0].strip(), 'order': ORDER}, 'by_L': {}, 'legacy_L5': {}}
    syn7 = Source(*synth(7)); LEG = legacy_stats()
    for L in (5, 10, 20):
        cfg = dict(V.SPEC, date_block=L); res = {}
        for k, (name, src, how, a, kw) in enumerate(SEL):
            rng = np.random.default_rng(SEED_SEL + 100 * k)            # 三個 L 用同一批視窗與標籤(只差重抽)
            recs = []
            for rows, c, truth in gen_rows(syn7, how, a, rng, 120, NSEL, **kw):
                s = V.stats(rows, c, cfg)
                rec = {'truth': truth, 'point': s['h1_pp'], 'paired': s['paired_dates']}
                for m in ('M1', 'M2'):
                    h = s['h1_methods'][m]; rec[m] = {'lb': h['lb_pp'], 'ub': h['ub_pp'], 'median': h['median_pp'], 'sd': h['sd_pp']}
                if L == 5:
                    o = LEG.stats(rows, c, dict(LEG.SPEC, date_block=5))
                    rec['legacy'] = {'lb': o['h1_lb_pp'], 'ub': None, 'median': None, 'sd': None}
                recs.append(rec)
            res[name] = {m: summarize_interval(recs, m) for m in ('M1', 'M2')}
            if L == 5:
                n = len(recs); lm = sum(r['legacy']['lb'] is not None and r['legacy']['lb'] > r['truth'] for r in recs)
                out['legacy_L5'][name] = {'lb_above_truth': frac(lm, n), 'note': '草案 2 原樣(只當參照,不參選)'}
            res[name]['records'] = recs
            print('select L', L, name, {m: (res[name][m]['lb_above_truth']['k'], res[name][m]['ub_below_truth']['k'], round(res[name][m]['center_mean_std_units'], 3), res[name][m]['passes']) for m in ('M1', 'M2')},
                  out['legacy_L5'].get(name, {}).get('lb_above_truth', {}).get('k'), round(time.time() - t0), flush=True)
        out['by_L'][str(L)] = res
    chosen = None
    for m, L in ORDER:
        if all(out['by_L'][str(L)][name][m]['passes'] for name, *_ in SEL): chosen = (m, L); break
    out['chosen'] = {'method': chosen[0], 'date_block': chosen[1]} if chosen else None
    out['meta']['seconds'] = round(time.time() - t0)
    json.dump(out, open(os.path.join(OUTD, 'sim4_select.json'), 'w'), ensure_ascii=False, indent=1, default=float)
    print('CHOSEN', out['chosen'], flush=True)


# ---------------------------------------------------------------- 報告
def report_scenarios():
    S = []
    for T in (120, 250):
        S += [('syn_random_a43', 'syn11', 'random', 0.43, T, {}, 'known'), ('syn_stock', 'syn11', 'stock', 0.43, T, {}, 'known'),
              ('syn_market', 'syn11', 'market', 0.43, T, {}, 'known'), ('syn_heavy_random', 'syn12', 'random', 0.43, T, {}, 'known'),
              ('density_null_alt', None, None, None, T, {'density': (0.010, -0.010, True)}, 'known'),
              ('syn_missing_mixed', 'syn11', 'random', 0.43, T, {'missing': 'mixed'}, 'known'),
              ('syn_missing_agree_only', 'syn11', 'random', 0.43, T, {'missing': 'agree_only'}, 'known'),
              ('hist_random', 'hist', 'random', 0.43, T, {}, 'stress'), ('hist_stock', 'hist', 'stock', 0.43, T, {}, 'stress'),
              ('hist_market', 'hist', 'market', 0.43, T, {}, 'stress')]
        S += [(f'power_delta{d}', 'hist', 'skill', 0.43, T, {'delta': d}, 'power') for d in (1.0, 2.0, 3.0)]
    S += [('syn_random_a25', 'syn11', 'random', 0.25, 120, {}, 'known'), ('syn_random_a70', 'syn11', 'random', 0.70, 120, {}, 'known'),
          ('syn_sparse_random', 'syn13', 'random', 0.43, 120, {}, 'known'),
          ('density_astra_alt', None, None, None, 120, {'density': (0.010, -0.012, True)}, 'known'),
          ('density_random_mix', None, None, None, 120, {'density': (0.010, -0.010, False)}, 'known'),
          ('syn_shift_plus1', 'syn11', 'random', 0.43, 120, {'shift': 0.01}, 'known'), ('syn_shift_minus1', 'syn11', 'random', 0.43, 120, {'shift': -0.01}, 'known')]
    return S


def window_record(res, truth):
    ex = res['excluded_missing'] or {}; im = res['agree_missing_at_minus_100pct'] or ex
    return {'truth': truth, 'point': ex.get('h1_pp'), 'lb': ex.get('h1_lb_pp'), 'ub': ex.get('h1_ub_pp'),
            'm2_lb': ((ex.get('h1_methods') or {}).get('M2') or {}).get('lb_pp'), 'paired': ex.get('paired_dates'), 'n_closed': res['n_closed'],
            'n_missing': res['n_missing'], 'agree_share': ex.get('agree_share'), 'decision': res['decision_by_h2_mode'],
            'H3_ex': bool(ex.get('H3')), 'H3_im': bool(im.get('H3')), 'live': res['go_live_candidate_by_h2_mode'],
            'win_gap_ad_pp': (ex['win_agree_pct'] - ex['win_disagree_pct']) if ex.get('win_agree_pct') is not None and ex.get('win_disagree_pct') is not None else None,
            'insufficient': res['decision_by_h2_mode']['none'] == 'INSUFFICIENT'}


def run_report(shard, nshard):
    t0 = time.time(); sel = json.load(open(os.path.join(OUTD, 'sim4_select.json')))
    if not sel['chosen']: raise SystemExit('選擇規則沒有選出方法 → 不跑報告')
    cfg = dict(V.SPEC, h1_method=sel['chosen']['method'], date_block=sel['chosen']['date_block'], h2_mode=None)
    src = {}
    def get(name):
        if name not in src:
            src[name] = {'syn11': lambda: Source(*synth(11)), 'syn12': lambda: Source(*synth(12, df_idio=2.5)), 'syn13': lambda: Source(*synth(13, q_scale=0.28)),
                         'hist': lambda: Source(*load_hist(EVF, DD))}[name]()
        return src[name]
    out = {'meta': {'stat_fingerprint': stat_fingerprint(), 'cfg': {k: cfg[k] for k in ('h1_method', 'date_block', 'draws', 'seed')}, 'shard': [shard, nshard]}, 'scen': {}}
    for k, (name, sname, how, a, T, kw, kind) in enumerate(report_scenarios()):
        if k % nshard != shard: continue
        key = f'{name}|T{T}'; rng = np.random.default_rng(SEED_REP + 1000 * k); recs = []
        kw = dict(kw); miss = kw.pop('missing', None); delta = kw.pop('delta', None); kappa = 0.0
        if delta is not None: kappa = calibrate_kappa(get('hist').evs, delta, a, SEED_REP + int(delta * 10))
        for rows, c, truth in gen_rows(get(sname) if sname else None, how, a, rng, T, NREP, kappa=kappa, **kw):
            mrows = []
            if miss:   # 不是隨機的缺漏:報酬最差 1% 的事件有 30% 會缺(agree_only = 只缺同意的)
                q01 = np.percentile([r[4] for r in rows], 1); keep = []
                for r in rows:
                    if r[4] <= q01 and rng.random() < 0.3 and (miss != 'agree_only' or r[3] == 'agree'): mrows.append(r[:4])
                    else: keep.append(r)
                rows = keep
            res = V.decide(rows, mrows, c, cfg)
            recs.append(window_record(res, truth if kind == 'known' else None))
        out['scen'][key] = {'name': name, 'T': T, 'kind': kind, 'labels': how, 'agree_rate': a, 'kappa': kappa if delta else None, 'delta_target_pp': delta,
                            'missing': miss, 'records': recs}
        print(key, kind, 'PASS none', sum(r['decision']['none'] == 'PASS' for r in recs), 'INSUFF', sum(r['insufficient'] for r in recs), round(time.time() - t0), flush=True)
    out['meta']['seconds'] = round(time.time() - t0)
    json.dump(out, open(os.path.join(OUTD, f'sim4_report_{shard}of{nshard}.json'), 'w'), ensure_ascii=False, indent=1, default=float)


def run_merge():
    sel = json.load(open(os.path.join(OUTD, 'sim4_select.json'))); scen = {}; fps = {sel['meta']['stat_fingerprint']}
    for f in sorted(os.listdir(OUTD)):
        if f.startswith('sim4_report_') and f.endswith('.json'):
            j = json.load(open(os.path.join(OUTD, f))); scen.update(j['scen']); fps.add(j['meta']['stat_fingerprint'])
    assert len(fps) == 1, '選擇與報告用的統計程式不同'
    summ = {}
    for key, s in scen.items():
        R = s['records']; n = len(R); row = {'name': s['name'], 'T': s['T'], 'kind': s['kind'], 'windows': n, 'missing': s['missing'],
                                               'mean_point_pp': float(np.mean([r['point'] for r in R if r['point'] is not None])),
                                               'paired_dates_median': float(np.median([r['paired'] for r in R if r['paired'] is not None])),
                                               'INSUFFICIENT': frac(sum(r['insufficient'] for r in R), n)}
        row['PASS'] = {m: frac(sum(r['decision'][m] == 'PASS' for r in R), n) for m in V.H2_MODES}
        row['H3_alone_excluded'] = frac(sum(r['H3_ex'] for r in R), n)
        row['go_live_candidate'] = {m: frac(sum(r['live'][m] for r in R), n) for m in V.H2_MODES}
        if s['kind'] == 'known':
            row['mean_truth_pp'] = float(np.mean([r['truth'] for r in R]))
            row['lb_above_truth'] = frac(sum(r['lb'] is not None and r['lb'] > r['truth'] for r in R), n)
            row['ub_below_truth'] = frac(sum(r['ub'] is not None and r['ub'] < r['truth'] for r in R), n)
            row['coverage95'] = frac(sum(r['lb'] is not None and r['ub'] is not None and r['lb'] <= r['truth'] <= r['ub'] for r in R), n)
            row['m2_lb_above_truth'] = frac(sum(r['m2_lb'] is not None and r['m2_lb'] > r['truth'] for r in R), n)
        if s['kind'] == 'power':
            row['kappa'] = s['kappa']; row['delta_target_pp'] = s['delta_target_pp']
            g = [r['win_gap_ad_pp'] for r in R if r['win_gap_ad_pp'] is not None]; row['win_gap_agree_minus_disagree_pp_mean'] = float(np.mean(g)) if g else None
        summ[key] = row
    out = {'meta': {'stat_fingerprint': fps.pop(), 'chosen': sel['chosen'], 'windows': NREP, 'draws': V.SPEC['draws'], 'seed_labels': SEED_REP,
                    'scope': '統計判定層的流程模擬(給定已驗收的事件);不含回條、批次驗收、行情重播與正式入口',
                    'units': 'H1 / δ 都是「格子等權」平均差(百分點),不是每筆都多賺 δ;H2 乙是事件加權的勝率差'},
           'selection_summary': {L: {nm: {m: {k: v for k, v in sel['by_L'][L][nm][m].items()} for m in ('M1', 'M2')} for nm in sel['by_L'][L]} for L in sel['by_L']},
           'legacy_L5': sel['legacy_L5'], 'report': summ}
    json.dump(out, open(os.path.join(OUTD, 'sim4_result.json'), 'w'), ensure_ascii=False, indent=1, default=float)
    print(json.dumps(out['meta'], ensure_ascii=False))


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'merge':
        OUTD = sys.argv[2]; run_merge(); sys.exit()
    REPO, EVF, DD, OUTD = sys.argv[2:6]; os.makedirs(OUTD, exist_ok=True)
    man = json.loads(V.Git(REPO).show('origin/astra-ledger', 'engine_manifest.json'))
    V.load_engine(V.Git(REPO), man['main_commit'], man['files'])
    if cmd == 'select': run_select()
    elif cmd == 'report': run_report(int(sys.argv[6]), int(sys.argv[7]))
