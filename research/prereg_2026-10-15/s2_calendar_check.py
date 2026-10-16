# Claude 2026-10-16:P1 / P2 補件第 2 輪(回應 Astra v0.7.3 §2.2、附錄三 §2–§4)— 原結果不動,只加檢查與描述
#   1. 逐檔核對:adjusted/<股票>.json 的位元組 SHA-256 = manifest 裡記的(c345 'sha256' / d266 'adjustedSha256')
#   2. 共同日曆(SPY 交易日)完整窗口檢查:
#        P1:進場日 = 訊號日之後的下一個 SPY 交易日;訊號日 ~ 出場日之間個股沒有缺任何一個 SPY 交易日
#        P2:t ~ t+20 之間個股沒有缺日(t+1 開盤、t+10 / t+20 收盤都是 SPY 的第 1 / 10 / 20 個交易日)
#   3. 只描述:排除有問題的事件後的 P1 / P2 區間;P2 上升趨勢日去掉 FOX、NWS 後的每日彙總(讓去重後的 P2 區間可以獨立重算)
#   用法:python3 -I s2_calendar_check.py <資料夾> <名單檔> <SPY 檔> <原結果 json> <輸出資料夾> <標籤>
import json, os, sys, gzip, csv, hashlib, statistics as st
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..', '..')
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import p_sharp_and_break as PB          # 凍結的分析程式(98c59ba),只 import
import astra_data as AD, astra_trades as AT

D, ULIST, SPYF, ORIG, OUTD, TAG = sys.argv[1:7]
orig = json.load(open(ORIG)); os.makedirs(OUTD, exist_ok=True)
manf = json.load(open(os.path.join(D, 'manifest.json'))); man = manf['symbols']
assert hashlib.sha256(open(os.path.join(D, 'manifest.json'), 'rb').read()).hexdigest() == orig['meta']['data_dir_manifest_sha256']
syms = [s.strip() for s in open(ULIST) if s.strip() and not s.startswith('#')]
spy_all = [x[0] for x in json.load(open(SPYF))['bars']]; si = {d: k for k, d in enumerate(spy_all)}
days = [d for d in spy_all if PB.A0 <= d <= PB.A1]

# ---------- 1. 逐檔指紋
filesha = {'checked': 0, 'mismatch': [], 'field': None}
for s, v in man.items():
    f = os.path.join(D, v['adjustedFile']); want = v.get('sha256') or v.get('adjustedSha256')
    filesha['field'] = 'sha256' if 'sha256' in v else 'adjustedSha256'
    got = hashlib.sha256(open(f, 'rb').read()).hexdigest(); filesha['checked'] += 1
    if got != want: filesha['mismatch'].append(s)

# ---------- 2. 逐事件(同 PB.run 的迴圈,多記窗口檢查與股票)
P1, P2b, P2u = [], [], []
flags_p1, flags_p2b = [], []
for s in syms:
    if s not in man: continue
    pb = PB.load(D, s, man)
    if len(pb) < 60: continue
    W = AD.sw_series(pb); n = W['n']; Dt = W['D']; O = [x[1] for x in pb]; C = [x[4] for x in pb]
    sty = AT.style_of(s); tops = set(W['top'])
    def gap(a, b):   # 個股第 a 根 ~ 第 b 根之間,SPY 有幾個交易日不在個股裡
        return (si[Dt[b]] - si[Dt[a]]) - (b - a)
    for i, k in AT.buy_points(W):
        if not (PB.A0 <= Dt[i] <= PB.A1) or i < PB.SHARP_LB or i + 1 >= n: continue
        d, why = AT.exit_of(W, O, i, sty, tops)
        if d is None or d + 1 >= n: continue
        r = AT.ret(O, i + 1, d + 1, PB.COST); sharp = C[i] / C[i - PB.SHARP_LB] - 1 <= PB.SHARP
        next_ok = si[Dt[i]] + 1 < len(spy_all) and spy_all[si[Dt[i]] + 1] == Dt[i + 1]
        g = gap(i, d + 1)
        P1.append((Dt[i], sharp, r, why, k, s, next_ok and g == 0))
        if not (next_ok and g == 0):
            flags_p1.append({'date': Dt[i], 'sym': s, 'sharp': sharp, 'entry': Dt[i + 1], 'spy_next_session': spy_all[si[Dt[i]] + 1], 'exit': Dt[d + 1],
                             'missing_sessions_in_window': g, 'ret_net': r, 'exit_reason': why})
    s20, s50 = PB.sma(C, 20), PB.sma(C, 50); last = -10 ** 9
    for t in range(50, n):
        if s20[t] is None or s50[t] is None or s20[t - 1] is None: continue
        up = s20[t] > s50[t]
        brk = up and C[t] < s20[t] and C[t - 1] >= s20[t - 1] and t - last > PB.COOL
        if brk: last = t
        if not (PB.A0 <= Dt[t] <= PB.A1) or t + PB.H >= n: continue
        if up:
            f20 = C[t + PB.H] / O[t + 1] - 1; f10 = C[t + PB.H2] / O[t + 1] - 1; ok = gap(t, t + PB.H) == 0
            P2u.append((Dt[t], f20, f10, s, ok))
            if brk:
                P2b.append((Dt[t], f20, f10, s, ok))
                if not ok: flags_p2b.append({'date': Dt[t], 'sym': s, 'missing_sessions_in_window': gap(t, t + PB.H), 'fwd20': f20})

# 和凍結程式的結果逐項核對(同一組事件)
res0 = PB.analyze([e[:6] for e in P1], [e[:4] for e in P2b], [e[:3] for e in P2u], days)
same = {k: json.dumps(res0[k], sort_keys=True) == json.dumps(orig[k], sort_keys=True) for k in ('P1', 'P2')}
assert all(same.values()), same

# ---------- 3. 只描述:排除窗口有問題的事件
q1 = [e[:6] for e in P1 if e[6]]; qb = [e[:4] for e in P2b if e[4]]; qu = [e[:3] for e in P2u if e[4]]
r_ex = PB.analyze(q1, qb, qu, days)
# P2 上升趨勢日去掉 FOX、NWS(和 s1 的發行人去重同一個規則)的每日彙總
DROP = {'FOX', 'NWS'}
gu_dedup = PB.day_agg([e for e in P2u if e[3] not in DROP], lambda e: e[1], days)
gb_dedup = PB.day_agg([e for e in P2b if e[3] not in DROP], lambda e: e[1], days)
with gzip.open(os.path.join(OUTD, f'p2_daily_dedup_{TAG}.csv.gz'), 'wt', newline='') as f:
    w = csv.writer(f); w.writerow(['date', 'p2_break_dedup_sum', 'p2_break_dedup_n', 'p2_uptrend_dedup_sum', 'p2_uptrend_dedup_n'])
    for i, d in enumerate(days): w.writerow([d, repr(float(gb_dedup[0][i])), int(gb_dedup[1][i]), repr(float(gu_dedup[0][i])), int(gu_dedup[1][i])])
ci_dedup = PB.block_boot(days, {'b': gb_dedup, 'u': gu_dedup}, lambda a: (a['b'][0] / a['b'][1] - a['u'][0] / a['u'][1]) * 100 if a['b'][1] and a['u'][1] else None)
# P2 上升趨勢日的「股票 × 年」彙總(不放 83 萬列逐筆;可核對每檔的筆數與總和)
agg = {}
for e in P2u:
    k = (e[3], e[0][:4]); a = agg.setdefault(k, [0, 0.0, 0]); a[0] += 1; a[1] += e[1]; a[2] += int(not e[4])
with gzip.open(os.path.join(OUTD, f'p2_uptrend_by_symbol_year_{TAG}.csv.gz'), 'wt', newline='') as f:
    w = csv.writer(f); w.writerow(['sym', 'year', 'n', 'fwd20_sum_gross_no_cost', 'n_window_gap'])
    for (s, y), a in sorted(agg.items()): w.writerow([s, y, a[0], repr(a[1]), a[2]])

out = {'tag': TAG, 'original_result_reproduced': same,
       'per_file_sha256': {**filesha, 'all_match': not filesha['mismatch']},
       'manifest_last_dates': sorted({v.get('last') or (v.get('qa') or {}).get('lastDate') for v in man.values()}),
       'common_calendar': {'source': os.path.basename(SPYF), 'first': spy_all[0], 'last': spy_all[-1], 'sessions': len(spy_all)},
       'P1_window_issues': {'n_events': len(P1), 'n_flagged': len(flags_p1), 'events': flags_p1},
       'P2_window_issues': {'n_break': len(P2b), 'n_break_flagged': len(flags_p2b), 'break_events': flags_p2b[:50],
                            'n_uptrend': len(P2u), 'n_uptrend_flagged': sum(not e[4] for e in P2u),
                            'uptrend_flagged_by_symbol': {s: sum(1 for e in P2u if e[3] == s and not e[4]) for s in sorted({e[3] for e in P2u if not e[4]})}},
       'sensitivity_excluding_window_issues_descriptive_only': {'P1': {k: r_ex['P1'][k] for k in ('diff_mean_pp', 'ci97_5')}, 'P1_n_other': r_ex['P1']['other']['n'], 'P1_n_sharp': r_ex['P1']['sharp']['n'],
                                                               'P2': {k: r_ex['P2'][k] for k in ('diff_mean_pp', 'ci97_5')}, 'P2_n_break': r_ex['P2']['break']['n'], 'P2_n_uptrend': r_ex['P2']['uptrend_days']['n']},
       'P2_issuer_dedup_drop_FOX_NWS': {'diff_mean_pp': 100 * (gb_dedup[0].sum() / gb_dedup[1].sum() - gu_dedup[0].sum() / gu_dedup[1].sum()), 'ci97_5': ci_dedup,
                                        'n_break': int(gb_dedup[1].sum()), 'n_uptrend': int(gu_dedup[1].sum()), 'daily_file': f'p2_daily_dedup_{TAG}.csv.gz'},
       'cost_note': 'P2 是未扣成本;兩組每筆都減同一個固定報酬成本時差值不變;若照 P1 的方式(進價 ×1.001、出價 ×0.999)則差值乘上 0.999/1.001',
       'P2_diff_if_multiplicative_cost_pp': orig['P2']['diff_mean_pp'] * 0.999 / 1.001,
       'note': '原判定照 PREREG 不變;這裡的排除與去重都只是描述'}
json.dump(out, open(os.path.join(OUTD, f's2_result_{TAG}.json'), 'w'), ensure_ascii=False, indent=1, default=float)
print(json.dumps({k: out[k] for k in ('tag', 'original_result_reproduced', 'manifest_last_dates')}, ensure_ascii=False),
      json.dumps({'file_sha_all_match': out['per_file_sha256']['all_match'], 'checked': filesha['checked'], 'P1_flagged': len(flags_p1), 'P2b_flagged': len(flags_p2b),
                  'P2u_flagged': out['P2_window_issues']['n_uptrend_flagged'], 'sens': out['sensitivity_excluding_window_issues_descriptive_only'],
                  'p2_dedup': {k: out['P2_issuer_dedup_drop_FOX_NWS'][k] for k in ('diff_mean_pp', 'ci97_5')}}, ensure_ascii=False, default=float))
