# Claude 2026-10-16:盤感測試 v3 草案用的模擬(回應 Astra v0.7.2 附錄五:H1 有效日期、區塊長度、功效)
#   資料:research/prereg_2026-10-15/supplement/p1_events_d266.csv.gz(266 檔、2010-01 ~ 2026-07 的每一個網站買點,乙賣法,每邊扣 0.1%)
#         = 盤感測試 v2 的候選集合(每個買點各算一次);SPY / QQQ(丙)每天最多 2 筆、幾乎不會形成「同意 + 不同意」的格子,這裡不納入
#   做法:在歷史上隨機挑一段連續 T 個交易日當「收案期」,幫每個買點貼上「同意 / 不同意」(沒有判斷力的貼法),
#         照 v2 的 H1 算法(同一天、兩邊都有的格子,先算格內平均差,再對格子平均)和日曆上的移動區塊重抽算 95% 區間
#   兩種「沒有判斷力」的貼法:
#     random:每一筆各自擲銅板
#     tilt  :每一檔股票固定一邊(隨機分兩群,整段都一樣)= 一直偏好某些股票但沒有判斷力;
#             這時「真值」是這兩群股票在 2016–2026 全期的 H1(不一定是 0),檢查區間有沒有蓋到它
#   輸出:各 T、各區塊長度的「沒蓋到真值」比例(應該約 5%)、區間半寬、有效配對日數;功效 = 真效果 δ 時下界 > 0 的比例
#   用法:python3 -I sim_power_block.py <p1_events csv.gz> <daily_aggregates csv.gz> <輸出 json>
import csv, gzip, json, sys, hashlib
import numpy as np

EV, CAL, OUT = sys.argv[1:4]
SEED = 20261016; DRAWS = 1000; NWIN = 300
TS = (25, 60, 120); BLOCKS = (1, 5, 10, 20, 40); DELTAS = (0.5, 1.0, 1.5, 2.0, 3.0)
START_FROM = '2016-01-01'   # 266 檔裡很多是後來才上市的;2016 起每天的買點數比較接近現在(約 12 筆)

cal = [r['date'] for r in csv.DictReader(gzip.open(CAL, 'rt'))]
di = {d: i for i, d in enumerate(cal)}
rows = list(csv.DictReader(gzip.open(EV, 'rt')))
ed = np.array([di[r['date']] for r in rows]); er = np.array([float(r['ret_net_0.1pct_each_side']) for r in rows]) * 100   # 百分點
syms = sorted({r['sym'] for r in rows}); si = {s: k for k, s in enumerate(syms)}; es = np.array([si[r['sym']] for r in rows])
o = np.argsort(ed, kind='stable'); ed, er, es = ed[o], er[o], es[o]
day_lo = np.searchsorted(ed, np.arange(len(cal))); day_hi = np.searchsorted(ed, np.arange(len(cal)), side='right')
c0 = di[min(d for d in cal if d >= START_FROM)]
rng = np.random.default_rng(SEED)


def cells(lo_day, T, lab):
    """回傳長度 T 的陣列:每天的格內差(沒有格子 = nan)"""
    out = np.full(T, np.nan)
    for t in range(T):
        a, b = day_lo[lo_day + t], day_hi[lo_day + t]
        if b - a < 2: continue
        L = lab[a:b]; R = er[a:b]
        if L.any() and (~L).any(): out[t] = R[L].mean() - R[~L].mean()
    return out


def boot_ci(x, block, draws, rng):
    """v2 的做法:整段日曆(沒有格子的日子也在)連續 block 天一塊重抽,統計量 = 抽到的格子總和 / 格子數"""
    T = len(x); s = np.nan_to_num(x); c = (~np.isnan(x)).astype(float)
    if block >= T: block = T
    nb = int(np.ceil(T / block)); starts = np.arange(0, T - block + 1)
    st_ = rng.choice(starts, size=(draws, nb)); pick = (st_[:, :, None] + np.arange(block)[None, None, :]).reshape(draws, -1)[:, :T]
    num = s[pick].sum(1); den = c[pick].sum(1); ok = den > 0
    v = num[ok] / den[ok]
    return (np.percentile(v, 2.5), np.percentile(v, 97.5)) if len(v) > 50 else (np.nan, np.nan)


# tilt 的真值:同一個分群在 2016-01 ~ 2026-07 全期的 H1
def tilt_labels(seed):
    h = np.array([int(hashlib.sha256(f'{seed}:{s}'.encode()).hexdigest(), 16) % 2 == 0 for s in syms])
    return h[es]


res = {'meta': {'events_file': EV.split('/')[-1], 'events': int(len(er)), 'calendar_sessions': len(cal), 'window_start_from': START_FROM,
                'windows_per_config': NWIN, 'boot_draws': DRAWS, 'seed': SEED, 'Ts': TS, 'blocks': BLOCKS,
                'note': '只用歷史買點與「沒有判斷力」的貼法;不是任何人的判讀成績'}, 'by_T': {}}
for T in TS:
    starts = rng.integers(c0, len(cal) - T, size=NWIN)
    R = {'random': {b: {'miss': 0, 'lb_pos': 0, 'half': [], 'lb': []} for b in BLOCKS}, 'tilt': {b: {'miss': 0, 'half': []} for b in BLOCKS}, 'paired_days': [], 'events': []}
    for w, s0 in enumerate(starts):
        a, b = day_lo[s0], day_hi[s0 + T - 1]
        R['events'].append(int(b - a))
        lab = rng.random(len(er)) < 0.5
        x = cells(s0, T, lab); R['paired_days'].append(int((~np.isnan(x)).sum()))
        labt = tilt_labels(SEED * 1000 + T * 10 + w)
        xt = cells(s0, T, labt)
        for bl in BLOCKS:
            lo, hi = boot_ci(x, bl, DRAWS, rng)
            if np.isnan(lo): continue
            R['random'][bl]['miss'] += int(lo > 0 or hi < 0); R['random'][bl]['lb_pos'] += int(lo > 0)
            R['random'][bl]['half'].append((hi - lo) / 2); R['random'][bl]['lb'].append(lo)   # 虛無下的下界;真效果 δ(每格整體平移)→ 下界 + δ
        R.setdefault('tilt_x', []).append((xt, labt))
    # tilt:真值要算全期,很花時間 → 每個分群只算一次
    for (xt, labt) in R.pop('tilt_x'):
        full = cells(c0, len(cal) - c0, labt); mu = np.nanmean(full)
        for bl in BLOCKS:
            lo, hi = boot_ci(xt, bl, DRAWS, rng)
            if np.isnan(lo): continue
            R['tilt'][bl]['miss'] += int(not (lo <= mu <= hi)); R['tilt'][bl]['half'].append((hi - lo) / 2)
    out = {'events_median': float(np.median(R['events'])), 'paired_days_median': float(np.median(R['paired_days'])), 'paired_days_p10': float(np.percentile(R['paired_days'], 10)), 'blocks': {}}
    for bl in BLOCKS:
        rr, tt = R['random'][bl], R['tilt'][bl]; n_r = len(rr['half']); n_t = len(tt['half'])
        # 功效:真效果 δ(每一筆同意比不同意多 δ 個百分點)→ 下界 = 點估計 + δ + (下界 − 點估計);點估計在虛無下 ≈ 抽樣誤差
        pw = {}
        if n_r:
            lbs = np.array(rr['lb'])
            for d in DELTAS:
                pw[str(d)] = float(np.mean(lbs + d > 0))   # 每一格都多 δ → 整個區間平移 δ(平移模型的功效)
        out['blocks'][str(bl)] = {'random_miss_pct': 100 * rr['miss'] / max(1, n_r), 'random_lb_pos_pct': 100 * rr['lb_pos'] / max(1, n_r),
                                  'tilt_miss_truth_pct': 100 * tt['miss'] / max(1, n_t), 'half_width_pp_median': float(np.median(rr['half'])) if n_r else None,
                                  'tilt_half_width_pp_median': float(np.median(tt['half'])) if n_t else None, 'power_lb_gt0_by_delta_pp': pw, 'n_windows': n_r}
    res['by_T'][str(T)] = out
    print(T, json.dumps({k: (v if k != 'blocks' else {b: {kk: (round(vv, 1) if isinstance(vv, float) else vv) for kk, vv in x.items() if kk != 'power_lb_gt0_by_delta_pp'} for b, x in v.items()}) for k, v in out.items()}, ensure_ascii=False), flush=True)
json.dump(res, open(OUT, 'w'), ensure_ascii=False, indent=1)
