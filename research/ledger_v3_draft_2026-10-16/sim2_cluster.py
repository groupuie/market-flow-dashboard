# Claude 2026-10-16:v3 草案模擬第 2 輪 — 只用「日期區塊」重抽會低估不確定性(sim_power_block.py 的結果),
#   這裡加「以股票為單位」的重抽(Poisson 權重),判定改用兩個下界取小的:min(日期 5 日區塊下界, 股票重抽下界) > 0
#   兩種沒有判斷力的貼法(random / tilt,同 sim_power_block.py);功效用平移模型(每一格同意多 δ 個百分點)
#   用法:python3 -I sim2_cluster.py <p1_events csv.gz> <daily_aggregates csv.gz> <輸出 json>
import csv, gzip, json, sys, hashlib
import numpy as np

EV, CAL, OUT = sys.argv[1:4]
SEED = 20261016; DRAWS = 500
CONF = ((60, 300), (120, 300), (250, 200)); DELTAS = (0.5, 1.0, 1.5, 2.0, 3.0)
START_FROM = '2016-01-01'
cal = [r['date'] for r in csv.DictReader(gzip.open(CAL, 'rt'))]; di = {d: i for i, d in enumerate(cal)}
rows = list(csv.DictReader(gzip.open(EV, 'rt')))
ed = np.array([di[r['date']] for r in rows]); er = np.array([float(r['ret_net_0.1pct_each_side']) for r in rows]) * 100
syms = sorted({r['sym'] for r in rows}); si = {s: k for k, s in enumerate(syms)}; es = np.array([si[r['sym']] for r in rows])
o = np.argsort(ed, kind='stable'); ed, er, es = ed[o], er[o], es[o]
day_lo = np.searchsorted(ed, np.arange(len(cal))); day_hi = np.searchsorted(ed, np.arange(len(cal)), side='right')
c0 = di[min(d for d in cal if d >= START_FROM)]
rng = np.random.default_rng(SEED)


def window(s0, T):
    a, b = day_lo[s0], day_hi[s0 + T - 1]
    return ed[a:b] - s0, er[a:b], es[a:b], a, b


def cell_diffs(dd, rr, lab, T, w=None):
    """每天的格內差;w = 每筆的權重(None = 1)。回傳 (T,) 或 (D, T)"""
    M = np.zeros((len(dd), T)); M[np.arange(len(dd)), dd] = 1.0
    if w is None: w = np.ones((1, len(dd)))
    A = lab.astype(float); Dm = 1.0 - A
    Sa = (w * (rr * A)) @ M; Na = (w * A) @ M; Sd = (w * (rr * Dm)) @ M; Nd = (w * Dm) @ M
    with np.errstate(invalid='ignore', divide='ignore'):
        x = np.where((Na > 0) & (Nd > 0), Sa / Na - Sd / Nd, np.nan)
    return x


def date_block_lb(x, block, rng):
    T = len(x); s = np.nan_to_num(x); c = (~np.isnan(x)).astype(float)
    nb = int(np.ceil(T / block)); starts = np.arange(0, T - block + 1)
    st_ = rng.choice(starts, size=(DRAWS, nb)); pick = (st_[:, :, None] + np.arange(block)[None, None, :]).reshape(DRAWS, -1)[:, :T]
    num = s[pick].sum(1); den = c[pick].sum(1); v = num[den > 0] / den[den > 0]
    return np.percentile(v, 2.5)


def stock_lb(dd, rr, ss, lab, T, rng):
    us, inv = np.unique(ss, return_inverse=True)
    W = rng.poisson(1.0, size=(DRAWS, len(us))).astype(float)[:, inv]
    X = cell_diffs(dd, rr, lab, T, W)
    v = np.nanmean(X, axis=1); v = v[~np.isnan(v)]
    return np.percentile(v, 2.5)


def tilt(seed):
    h = np.array([int(hashlib.sha256(f'{seed}:{s}'.encode()).hexdigest(), 16) % 2 == 0 for s in syms])
    return h


full_d, full_r, full_s, _, _ = window(c0, len(cal) - c0)
res = {'meta': {'events_file': EV.split('/')[-1], 'window_start_from': START_FROM, 'draws': DRAWS, 'seed': SEED, 'configs': CONF,
                'rule': 'LB_min = min(日期 5 日區塊下界, 股票 Poisson 重抽下界);判定 = LB_min > 0', 'note': '歷史買點 + 沒有判斷力的貼法;不是任何人的判讀成績'}, 'by_T': {}}
for T, NW in CONF:
    starts = rng.integers(c0, len(cal) - T, size=NW)
    acc = {sc: {m: [] for m in ('d1', 'd5', 'st', 'min5')} for sc in ('random', 'tilt')}; truth = []; paired = []
    for w, s0 in enumerate(starts):
        dd, rr, ss, a, b = window(s0, T)
        for sc in ('random', 'tilt'):
            if sc == 'random':
                lab = rng.random(len(rr)) < 0.5; mu = 0.0
            else:
                part = tilt(SEED * 1000 + T * 10 + w); lab = part[ss]
                xf = cell_diffs(full_d, full_r, part[full_s], len(cal) - c0)[0]; mu = float(np.nanmean(xf))
            x = cell_diffs(dd, rr, lab, T)[0]
            if np.isnan(x).all(): continue
            est = np.nanmean(x)
            if sc == 'random': paired.append(int((~np.isnan(x)).sum()))
            else: truth.append(mu)
            l1 = date_block_lb(x, 1, rng); l5 = date_block_lb(x, 5, rng); ls = stock_lb(dd, rr, ss, lab, T, rng)
            for m, v in (('d1', l1), ('d5', l5), ('st', ls), ('min5', min(l5, ls))):
                acc[sc][m].append(v - mu)   # 下界 − 真值(> 0 = 假陽性 / 沒蓋到)
    out = {'windows': NW, 'paired_days_median': float(np.median(paired)), 'tilt_truth_sd_pp': float(np.std(truth)), 'methods': {}}
    for m in ('d1', 'd5', 'st', 'min5'):
        r_ = np.array(acc['random'][m]); t_ = np.array(acc['tilt'][m])
        out['methods'][m] = {'random_false_pos_pct': 100 * float(np.mean(r_ > 0)), 'tilt_lb_above_truth_pct': 100 * float(np.mean(t_ > 0)),
                             'power_by_delta_pp': {str(d): float(np.mean(r_ + d > 0)) for d in DELTAS}}
    res['by_T'][str(T)] = out
    print(T, json.dumps({m: {k: (round(v, 1) if isinstance(v, float) else {kk: round(vv, 2) for kk, vv in v.items()}) for k, v in x.items()} for m, x in out['methods'].items()}, ensure_ascii=False), 'paired', out['paired_days_median'], flush=True)
json.dump(res, open(OUT, 'w'), ensure_ascii=False, indent=1)
