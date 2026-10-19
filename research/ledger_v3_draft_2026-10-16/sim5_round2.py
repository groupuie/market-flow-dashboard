#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""盤感測試 v3 草案 3:統計判定層的流程模擬 — **第二輪方法開發**(Claude 2026-10-17;接 sim4)

為什麼有第二輪(如實揭露):sim4 照事先寫好的規則,六個候選(M1/M2 × L 5/10/20)都沒過 —
  稠密 / 稀疏交替、真值 0 的情境,下界 > 真值 是 11/300(L=5)~ 16/300(L=20),超過 3.5% 的門檻;
  診斷:這個情境裡重抽標準差是實際的 0.91–0.98 倍(單筆格子沒有「重複計算」的緩衝、t3 厚尾讓多數視窗低估變異);
  一般合成市場則是 1.3–1.5 倍(乘積權重把每筆自己的雜訊算了約三次 → 偏寬、功效被吃掉)。
  所以這一輪的兩個候選,都是**看過 sim4 之後**才定的;選擇在全新的模擬抽樣上做,最後報告再換一批全新的合成市場。

一、這一輪的選擇規則(**這一段在任何 sim5 結果出來之前寫好並 commit**)
  候選(依序,取第一個 9 個選擇情境全部合格的):
    C3:兩向群集變異數(日期區塊 + 發行人 − 區塊×發行人交集,用同一套正權重重抽估三個分量;負值 → 取兩個單向的較大者)
        區間 = 點估計 ± t(0.975, df) × 標準誤,df = min(日期區塊數, 發行人數) − 1;L = 5
    C1:標準誤 = M1 重抽標準差,其餘同 C3;L = 5
  選擇情境(120 天、各 300 個視窗;全新抽樣:合成市場 synth(21)、厚尾 synth(22)、稀疏 synth(23)、標籤 / 稠密情境 seed 20261711 起):
    合成・擲銅板(0)、固定偏好股票(0)、跟大盤(0)、同意加 1 點(+1)、同意減 1 點(−1)、厚尾擲銅板(0)、稀疏擲銅板(0)、
    稠密/稀疏交替且方向相反(+1 / −1 → 0)、Astra 反例結構(+1 / −1.2 → −0.1 × 成本係數)
  合格標準和 sim4 相同:(a) 下界 > 真值 的比例 點估計 ≤ 3.5% 且 Wilson 95% 下界 ≤ 2.5%;(b) 上界 < 真值 同上;
    (c) 中心:M1 重抽中位數 − 點估計 ÷ 重抽標準差 的平均在 ±0.10 之內
  兩個都不合格 → 不凍結(回報,不挑)。sim4 的 M1 / M2 不再參選(只在報告裡並列當參照)
二、報告(只用選中的方法;再換一批全新的合成市場:synth(31)、厚尾 synth(32)、稀疏 synth(33),標籤 seed 20261712 起;各 200 個視窗)
  情境清單和 sim4 的報告相同(已知真值的合成情境、缺漏、歷史固定庫的壓力測試、功效 δ = 1 / 2 / 3 個百分點 × 120 / 250 天)
  每個視窗存:三種 H2 的判定、單獨 H3、上線候選(交集)、各方法的下界 / 上界
用法:
  python3 -I sim5_round2.py select <repo> <events> <dd> <輸出資料夾>
  python3 -I sim5_round2.py report <repo> <events> <dd> <輸出資料夾> <shard> <nshard>
  python3 -I sim5_round2.py merge  <輸出資料夾>
"""
import importlib.util, json, math, os, sys, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location('sim4', os.path.join(HERE, 'sim4_calibrate.py')); S4 = importlib.util.module_from_spec(spec); spec.loader.exec_module(S4)
V = S4.V
SEED_SEL, SEED_REP = 20261711, 20261712
NSEL, NREP = 300, 200
ORDER = ['C3', 'C1']
SEL = [('syn_random', 'syn21', 'random', 0.43, {}), ('syn_stock', 'syn21', 'stock', 0.43, {}), ('syn_market', 'syn21', 'market', 0.43, {}),
       ('syn_shift_plus1', 'syn21', 'random', 0.43, {'shift': 0.01}), ('syn_shift_minus1', 'syn21', 'random', 0.43, {'shift': -0.01}),
       ('syn_heavy_random', 'syn22', 'random', 0.43, {}), ('syn_sparse_random', 'syn23', 'random', 0.43, {}),
       ('density_null_alt', None, None, None, {'density': (0.010, -0.010, True)}), ('density_astra_alt', None, None, None, {'density': (0.010, -0.012, True)})]
METHODS = ('M1', 'M2', 'C1', 'C3')


def sources(names):
    mk = {'syn21': lambda: S4.Source(*S4.synth(21)), 'syn22': lambda: S4.Source(*S4.synth(22, df_idio=2.5)), 'syn23': lambda: S4.Source(*S4.synth(23, q_scale=0.28)),
          'syn31': lambda: S4.Source(*S4.synth(31)), 'syn32': lambda: S4.Source(*S4.synth(32, df_idio=2.5)), 'syn33': lambda: S4.Source(*S4.synth(33, q_scale=0.28)),
          'hist': lambda: S4.Source(*S4.load_hist(EVF, DD))}
    return {n: mk[n]() for n in names}


def run_select():
    t0 = time.time(); cfg = dict(V.SPEC, date_block=5)
    out = {'meta': {'stat_fingerprint': S4.stat_fingerprint(), 'windows': NSEL, 'draws': cfg['draws'], 'seed_labels': SEED_SEL, 'order': ORDER,
                    'rule': __doc__.split('二、')[0].strip()}, 'scen': {}}
    src = sources(['syn21', 'syn22', 'syn23'])
    for k, (name, sname, how, a, kw) in enumerate(SEL):
        rng = np.random.default_rng(SEED_SEL + 100 * k); recs = []
        for rows, c, truth in S4.gen_rows(src.get(sname), how, a, rng, 120, NSEL, **kw):
            s = V.stats(rows, c, cfg); rec = {'truth': truth, 'point': s['h1_pp'], 'paired': s['paired_dates']}
            for m in METHODS:
                h = s['h1_methods'][m]; rec[m] = {'lb': h['lb_pp'], 'ub': h['ub_pp'], 'median': h['median_pp'], 'sd': h['sd_pp'], 'se': h.get('se_pp')}
            rec['C3_fallback'] = s['h1_methods']['C3']['negative_two_way_fallback']; recs.append(rec)
        res = {m: S4.summarize_interval(recs, m) for m in METHODS}
        err = np.array([r['point'] - r['truth'] for r in recs]); res['empirical_sd_pp'] = float(err.std(ddof=1))
        res['mean_se_pp'] = {m: float(np.mean([r[m]['se'] if r[m]['se'] is not None else r[m]['sd'] for r in recs])) for m in METHODS}
        res['C3_fallback_windows'] = int(sum(r['C3_fallback'] for r in recs)); res['records'] = recs
        out['scen'][name] = res
        print('select', name, {m: (res[m]['lb_above_truth']['k'], res[m]['ub_below_truth']['k'], round(res[m]['center_mean_std_units'], 3), res[m]['passes']) for m in METHODS},
              'empSD', round(res['empirical_sd_pp'], 3), 'meanSE', {m: round(v, 3) for m, v in res['mean_se_pp'].items()}, round(time.time() - t0), flush=True)
    chosen = next((m for m in ORDER if all(out['scen'][nm][m]['passes'] for nm, *_ in SEL)), None)
    out['chosen'] = {'method': chosen, 'date_block': 5} if chosen else None
    out['meta']['seconds'] = round(time.time() - t0)
    json.dump(out, open(os.path.join(OUTD, 'sim5_select.json'), 'w'), ensure_ascii=False, indent=1, default=float)
    print('CHOSEN', out['chosen'], flush=True)


def report_scenarios():
    S = []
    for T in (120, 250):
        S += [('syn_random_a43', 'syn31', 'random', 0.43, T, {}, 'known'), ('syn_stock', 'syn31', 'stock', 0.43, T, {}, 'known'),
              ('syn_market', 'syn31', 'market', 0.43, T, {}, 'known'), ('syn_heavy_random', 'syn32', 'random', 0.43, T, {}, 'known'),
              ('density_null_alt', None, None, None, T, {'density': (0.010, -0.010, True)}, 'known'),
              ('syn_missing_mixed', 'syn31', 'random', 0.43, T, {'missing': 'mixed'}, 'missing'),
              ('syn_missing_agree_only', 'syn31', 'random', 0.43, T, {'missing': 'agree_only'}, 'missing'),
              ('hist_random', 'hist', 'random', 0.43, T, {}, 'stress'), ('hist_stock', 'hist', 'stock', 0.43, T, {}, 'stress'),
              ('hist_market', 'hist', 'market', 0.43, T, {}, 'stress')]
        S += [(f'power_delta{d}', 'hist', 'skill', 0.43, T, {'delta': d}, 'power') for d in (1.0, 2.0, 3.0)]
    S += [('syn_random_a25', 'syn31', 'random', 0.25, 120, {}, 'known'), ('syn_random_a70', 'syn31', 'random', 0.70, 120, {}, 'known'),
          ('syn_sparse_random', 'syn33', 'random', 0.43, 120, {}, 'known'),
          ('density_astra_alt', None, None, None, 120, {'density': (0.010, -0.012, True)}, 'known'),
          ('density_random_mix', None, None, None, 120, {'density': (0.010, -0.010, False)}, 'known'),
          ('syn_shift_plus1', 'syn31', 'random', 0.43, 120, {'shift': 0.01}, 'known'), ('syn_shift_minus1', 'syn31', 'random', 0.43, 120, {'shift': -0.01}, 'known')]
    return S


def window_record(res, truth):
    r = S4.window_record(res, truth); ex = res['excluded_missing'] or {}
    r['lbs'] = {m: ((ex.get('h1_methods') or {}).get(m) or {}).get('lb_pp') for m in METHODS}
    r['ubs'] = {m: ((ex.get('h1_methods') or {}).get(m) or {}).get('ub_pp') for m in METHODS}
    return r


def run_report(shard, nshard):
    t0 = time.time(); sel = json.load(open(os.path.join(OUTD, 'sim5_select.json')))
    if not sel['chosen']: raise SystemExit('第二輪選擇規則沒有選出方法 → 不跑報告')
    cfg = dict(V.SPEC, h1_method=sel['chosen']['method'], date_block=5, h2_mode=None)
    scen = report_scenarios(); need = sorted({x[1] for k, x in enumerate(scen) if k % nshard == shard and x[1]}); src = sources(need)
    out = {'meta': {'stat_fingerprint': S4.stat_fingerprint(), 'cfg': {k: cfg[k] for k in ('h1_method', 'date_block', 'draws', 'seed')}, 'shard': [shard, nshard]}, 'scen': {}}
    for k, (name, sname, how, a, T, kw, kind) in enumerate(scen):
        if k % nshard != shard: continue
        key = f'{name}|T{T}'; rng = np.random.default_rng(SEED_REP + 1000 * k); recs = []
        kw = dict(kw); miss = kw.pop('missing', None); delta = kw.pop('delta', None); kappa = 0.0
        if delta is not None: kappa = S4.calibrate_kappa(src['hist'].evs, delta, a, SEED_REP + int(delta * 10))
        for rows, c, truth in S4.gen_rows(src.get(sname), how, a, rng, T, NREP, kappa=kappa, **kw):
            mrows = []
            if miss:
                q01 = np.percentile([r[4] for r in rows], 1); keep = []
                for r in rows:
                    if r[4] <= q01 and rng.random() < 0.3 and (miss != 'agree_only' or r[3] == 'agree'): mrows.append(r[:4])
                    else: keep.append(r)
                rows = keep
            recs.append(window_record(V.decide(rows, mrows, c, cfg), truth if kind in ('known', 'missing') else None))
        out['scen'][key] = {'name': name, 'T': T, 'kind': kind, 'labels': how, 'agree_rate': a, 'kappa': kappa if delta else None, 'delta_target_pp': delta, 'missing': miss, 'records': recs}
        print(key, kind, 'PASS none', sum(r['decision']['none'] == 'PASS' for r in recs), 'INSUFF', sum(r['insufficient'] for r in recs), round(time.time() - t0), flush=True)
    out['meta']['seconds'] = round(time.time() - t0)
    json.dump(out, open(os.path.join(OUTD, f'sim5_report_{shard}of{nshard}.json'), 'w'), ensure_ascii=False, indent=1, default=float)


def run_merge():
    sel = json.load(open(os.path.join(OUTD, 'sim5_select.json'))); scen = {}; fps = {sel['meta']['stat_fingerprint']}
    for f in sorted(os.listdir(OUTD)):
        if f.startswith('sim5_report_') and f.endswith('.json'):
            j = json.load(open(os.path.join(OUTD, f))); scen.update(j['scen']); fps.add(j['meta']['stat_fingerprint'])
    assert len(fps) == 1, '選擇與報告用的統計程式不同'
    F = S4.frac; summ = {}
    for key, s in scen.items():
        R = s['records']; n = len(R)
        row = {'name': s['name'], 'T': s['T'], 'kind': s['kind'], 'windows': n, 'missing': s['missing'],
               'mean_point_pp': float(np.mean([r['point'] for r in R if r['point'] is not None])),
               'paired_dates_median': float(np.median([r['paired'] for r in R if r['paired'] is not None])),
               'INSUFFICIENT': F(sum(r['insufficient'] for r in R), n),
               'PASS': {m: F(sum(r['decision'][m] == 'PASS' for r in R), n) for m in V.H2_MODES},
               'H3_alone_excluded': F(sum(r['H3_ex'] for r in R), n),
               'go_live_candidate': {m: F(sum(r['live'][m] for r in R), n) for m in V.H2_MODES},
               'H1_lb_gt0_by_method': {m: F(sum(r['lbs'][m] is not None and r['lbs'][m] > 0 for r in R), n) for m in METHODS}}
        if s['kind'] == 'known':
            row['mean_truth_pp'] = float(np.mean([r['truth'] for r in R]))
            row['lb_above_truth'] = {m: F(sum(r['lbs'][m] is not None and r['lbs'][m] > r['truth'] for r in R), n) for m in METHODS}
            row['ub_below_truth'] = {m: F(sum(r['ubs'][m] is not None and r['ubs'][m] < r['truth'] for r in R), n) for m in METHODS}
        if s['kind'] == 'power':
            row['kappa'] = s['kappa']; row['delta_target_pp'] = s['delta_target_pp']
            g = [r['win_gap_ad_pp'] for r in R if r['win_gap_ad_pp'] is not None]; row['win_gap_agree_minus_disagree_pp_mean'] = float(np.mean(g)) if g else None
        summ[key] = row
    out = {'meta': {'stat_fingerprint': fps.pop(), 'chosen': sel['chosen'], 'windows': NREP, 'draws': V.SPEC['draws'], 'seed_labels': SEED_REP,
                    'scope': '統計判定層的流程模擬(給定已驗收的事件);不含回條、批次驗收、行情重播與正式入口',
                    'units': 'H1 / δ 都是「格子等權」平均差(百分點),不是每筆都多賺 δ;H2 乙是事件加權的勝率差'},
           'selection': {nm: {m: {k: v for k, v in sel['scen'][nm][m].items()} for m in METHODS} | {'empirical_sd_pp': sel['scen'][nm]['empirical_sd_pp'], 'mean_se_pp': sel['scen'][nm]['mean_se_pp']} for nm in sel['scen']},
           'report': summ}
    json.dump(out, open(os.path.join(OUTD, 'sim5_result.json'), 'w'), ensure_ascii=False, indent=1, default=float)
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
