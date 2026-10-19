# Claude 2026-10-16:P1 / P2 補件(回應 Astra v0.7.2 §2.2、§2.3、附錄三 §八)
#   1. 用「原始」資料夾(manifest SHA 必須等於結果檔記的那個)重跑凍結的 p_sharp_and_break.py,確認結果逐位相同
#   2. 輸出逐事件表、每日彙總(可以只靠它重算區間)、資料成熟 / 日曆檢查
#   3. 只描述、不改判定:分年、分段、危機期、股票集中度、真正的停損觸發率、發行人去重、較長區塊(42 / 63 / 126)
#   不改 PREREG.md、p_sharp_and_break.py、download_oos.py、scripts/astra_*.py
#   用法:python3 -I s1_supplement.py <資料夾> <名單檔> <SPY 檔> <原結果 json> <輸出資料夾> <標籤>
import json, os, sys, gzip, csv, hashlib, math, statistics as st
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..', '..')
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import p_sharp_and_break as PB          # 凍結的分析程式(98c59ba),只 import、不改
import astra_data as AD, astra_trades as AT
import numpy as np

D, ULIST, SPYF, ORIG, OUTD, TAG = sys.argv[1:7]
os.makedirs(OUTD, exist_ok=True)
sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()
orig = json.load(open(ORIG))
man_sha = sha(os.path.join(D, 'manifest.json'))
assert man_sha == orig['meta']['data_dir_manifest_sha256'], ('資料夾不是原始那份', man_sha)
syms = [s.strip() for s in open(ULIST) if s.strip() and not s.startswith('#')]
spy = [x[0] for x in json.load(open(SPYF))['bars']]
days = [d for d in spy if PB.A0 <= d <= PB.A1]; dayset = set(days); didx = {d: i for i, d in enumerate(days)}; spyset = set(spy)

# ---------- 1. 重跑凍結程式,和原結果比對
P1, P2b, P2u, skipped = PB.run(D, syms, days)
res = PB.analyze(P1, P2b, P2u, days)
same = {k: json.dumps(res[k], sort_keys=True) == json.dumps(orig[k], sort_keys=True) for k in ('P1', 'P2')}
assert all(same.values()), same

# ---------- 2. 逐事件細節(同一個迴圈邏輯,多記進出日、停損價、決定日是否也碰到停損;和 PB.run 的 P1 逐筆比對)
man = json.load(open(os.path.join(D, 'manifest.json')))['symbols']
rows, gaps, no_exit = [], {}, 0
for s in syms:
    if s not in man: continue
    pb = PB.load(D, s, man)
    if len(pb) < 60: continue
    W = AD.sw_series(pb); n = W['n']; Dt = W['D']; O = [x[1] for x in pb]; C = [x[4] for x in pb]
    sty = AT.style_of(s); tops = set(W['top'])
    # 這檔在共同日曆上缺的交易日(只看 A0 ~ 最後一天)
    have = set(Dt); lo = max(Dt[0], PB.A0)
    miss = [d for d in spy if lo <= d <= Dt[-1] and d not in have]
    extra = [d for d in Dt if d >= PB.A0 and d not in spyset]
    if miss or extra: gaps[s] = {'missing_sessions': len(miss), 'first_missing': miss[:3], 'dates_not_in_spy': extra[:3]}
    for i, k in AT.buy_points(W):
        if not (PB.A0 <= Dt[i] <= PB.A1) or i < PB.SHARP_LB or i + 1 >= n: continue
        d, why = AT.exit_of(W, O, i, sty, tops)
        if d is None or d + 1 >= n: no_exit += 1; continue
        r = AT.ret(O, i + 1, d + 1, PB.COST)
        sp = O[i + 1] * (1 - sty['stop']) if sty.get('stop') else None
        rows.append({'date': Dt[i], 'sym': s, 'kind': k, 'sharp': C[i] / C[i - PB.SHARP_LB] - 1 <= PB.SHARP,
                     'entry': Dt[i + 1], 'decision': Dt[d], 'exit': Dt[d + 1], 'why': why,
                     'stop_level_hit_on_decision_day': bool(sp is not None and C[d] <= sp), 'ret_net': r})
assert [(x['date'], x['sharp'], x['ret_net'], x['why'], x['kind'], x['sym']) for x in rows] == [tuple(e) for e in P1], '逐筆和 PB.run 不同'

with gzip.open(os.path.join(OUTD, f'p1_events_{TAG}.csv.gz'), 'wt', newline='') as f:
    w = csv.writer(f); w.writerow(['date', 'sym', 'kind', 'sharp', 'entry_open', 'exit_decision_close', 'exit_open', 'exit_reason', 'stop_level_hit_on_decision_day', 'ret_net_0.1pct_each_side'])
    for x in rows: w.writerow([x['date'], x['sym'], x['kind'], int(x['sharp']), x['entry'], x['decision'], x['exit'], x['why'], int(x['stop_level_hit_on_decision_day']), repr(x['ret_net'])])
with gzip.open(os.path.join(OUTD, f'p2_break_events_{TAG}.csv.gz'), 'wt', newline='') as f:
    w = csv.writer(f); w.writerow(['date', 'sym', 'fwd20_gross_no_cost', 'fwd10_gross_no_cost'])
    for e in P2b: w.writerow([e[0], e[3], repr(e[1]), repr(e[2])])
g = {'p1_sharp': PB.day_agg([e for e in P1 if e[1]], lambda e: e[2], days), 'p1_other': PB.day_agg([e for e in P1 if not e[1]], lambda e: e[2], days),
     'p2_break': PB.day_agg(P2b, lambda e: e[1], days), 'p2_uptrend': PB.day_agg(P2u, lambda e: e[1], days)}
with gzip.open(os.path.join(OUTD, f'daily_aggregates_{TAG}.csv.gz'), 'wt', newline='') as f:
    w = csv.writer(f); w.writerow(['date'] + [f'{k}_{c}' for k in g for c in ('sum', 'n')])
    for i, d in enumerate(days): w.writerow([d] + [x for k in g for x in (repr(float(g[k][0][i])), int(g[k][1][i]))])

# ---------- 3. 檢查與描述
off_cal = {'p1': sum(e[0] not in dayset for e in P1), 'p2_break': sum(e[0] not in dayset for e in P2b), 'p2_uptrend': sum(e[0] not in dayset for e in P2u)}
def desc(v): return PB.desc(v)
sh = [x for x in rows if x['sharp']]; ot = [x for x in rows if not x['sharp']]
def stop_rates(xs):
    n = max(1, len(xs))
    return {'exit_reason_stop_pct': 100 * sum(x['why'] == '停損' for x in xs) / n,
            'stop_level_hit_on_decision_day_pct': 100 * sum(x['stop_level_hit_on_decision_day'] for x in xs) / n,
            'top_and_stop_same_day': sum(x['why'] == '頂' and x['stop_level_hit_on_decision_day'] for x in xs)}
def by_year(xs, val):
    out = {}
    for y in sorted({x[0][:4] if isinstance(x, tuple) else x['date'][:4] for x in xs}):
        v = [val(x) for x in xs if (x[0] if isinstance(x, tuple) else x['date'])[:4] == y]
        out[y] = {'n': len(v), 'mean_pct': 100 * st.mean(v), 'win_pct': 100 * sum(r > 0 for r in v) / len(v)}
    return out
CRISIS = {'2011-08~10': ('2011-08-01', '2011-10-31'), '2015-08~2016-02': ('2015-08-17', '2016-02-29'), '2018-10~12': ('2018-10-01', '2018-12-31'),
          '2020-02~04': ('2020-02-19', '2020-04-30'), '2022-01~10': ('2022-01-01', '2022-10-31'), '2025-02~04': ('2025-02-19', '2025-04-30')}
def crisis(xs, val):
    out = {}
    for k, (a, b) in CRISIS.items():
        v = [val(x) for x in xs if a <= (x[0] if isinstance(x, tuple) else x['date']) <= b]
        out[k] = {'n': len(v), 'mean_pct': 100 * st.mean(v) if v else None}
    return out
def conc(xs):
    from collections import Counter
    dc = Counter(x['date'] for x in xs); sc = Counter(x['sym'] for x in xs)
    blocks = {didx[x['date']] // PB.BLOCK for x in xs}
    top5 = sum(c for _, c in dc.most_common(5))
    return {'n': len(xs), 'distinct_dates': len(dc), 'distinct_symbols': len(sc), 'distinct_21day_blocks': len(blocks), 'top5_dates_share_pct': 100 * top5 / max(1, len(xs)),
            'top_dates': dc.most_common(5), 'top_symbols': sc.most_common(10)}
def boot(groups, a, b, block):
    return PB.block_boot(days, groups, lambda q: (q[a][0] / q[a][1] - q[b][0] / q[b][1]) * 100 if q[a][1] and q[b][1] else None, block=block)
def sub_days(lo, hi):   # 只用某一段日曆(兩段分報用)
    return [d for d in days if lo <= d <= hi]
def boot_on(dsub, ev_a, ev_b, val):
    ga = PB.day_agg(ev_a, val, dsub); gb = PB.day_agg(ev_b, val, dsub)
    ci = PB.block_boot(dsub, {'a': ga, 'b': gb}, lambda q: (q['a'][0] / q['a'][1] - q['b'][0] / q['b'][1]) * 100 if q['a'][1] and q['b'][1] else None)
    va = [val(e) for e in ev_a if dsub[0] <= e[0] <= dsub[-1]]; vb = [val(e) for e in ev_b if dsub[0] <= e[0] <= dsub[-1]]
    return {'n_a': len(va), 'n_b': len(vb), 'diff_pp': 100 * (st.mean(va) - st.mean(vb)) if va and vb else None, 'ci97_5': ci}

p1s = [e for e in P1 if e[1]]; p1o = [e for e in P1 if not e[1]]
sens = {'block_lengths': {}}
for bl in (42, 63, 126):
    sens['block_lengths'][str(bl)] = {'P1': boot({'sh': g['p1_sharp'], 'ns': g['p1_other']}, 'sh', 'ns', bl), 'P2': boot({'b': g['p2_break'], 'u': g['p2_uptrend']}, 'b', 'u', bl)}
# 發行人去重:同一家公司兩種股別只留 A 股(事先固定:留 FOXA、NWSA,去掉 FOX、NWS)
DROP = {'FOX', 'NWS'} & set(syms)
if DROP:
    q1 = [e for e in P1 if e[5] not in DROP]; qb = [e for e in P2b if e[3] not in DROP]
    # P2 上升趨勢日沒有記股票 → 重算那兩檔的上升趨勢日再扣掉
    keep = [s for s in syms if s not in DROP]
    _, _, P2u_k, _ = PB.run(D, keep, days)
    a1 = PB.analyze(q1, qb, P2u_k, days)
    sens['issuer_dedup_drop_' + '_'.join(sorted(DROP))] = {'P1': {k: a1['P1'][k] for k in ('diff_mean_pp', 'ci97_5')}, 'P2': {k: a1['P2'][k] for k in ('diff_mean_pp', 'ci97_5')},
                                                         'n_P1_sharp': a1['P1']['sharp']['n'], 'n_P2_break': a1['P2']['break']['n']}
# P2:破線日 vs「不是破線日」的上升趨勢日(主比較包含破線日本身;這裡只描述)
gu_nb = (g['p2_uptrend'][0] - g['p2_break'][0], g['p2_uptrend'][1] - g['p2_break'][1])
sens['P2_break_vs_nonbreak_uptrend'] = {'diff_pp': 100 * (g['p2_break'][0].sum() / g['p2_break'][1].sum() - gu_nb[0].sum() / gu_nb[1].sum()),
                                        'ci97_5': boot({'b': g['p2_break'], 'u': gu_nb}, 'b', 'u', PB.BLOCK)}
# 兩段分報(只描述;PREREG 沒有寫兩段,不能當判定)
sens['two_periods'] = {k: {'P1': boot_on(sub_days(a, b), p1s, p1o, lambda e: e[2]), 'P2': boot_on(sub_days(a, b), P2b, P2u, lambda e: e[1])}
                       for k, (a, b) in {'2010-2017': ('2010-01-01', '2017-12-31'), '2018-2026-07': ('2018-01-01', '2026-07-31')}.items()}

out = {'tag': TAG, 'reproduced_identical': same, 'data_manifest_sha256': man_sha, 'manifest_created_utc': json.load(open(os.path.join(D, 'manifest.json'))).get('created_utc') or json.load(open(os.path.join(D, 'manifest.json'))).get('createdAt'),
       'calendar': {'source': os.path.basename(SPYF), 'sessions': len(days), 'first': days[0], 'last': days[-1], 'sha256_of_session_list': hashlib.sha256('\n'.join(days).encode()).hexdigest()},
       'dependency_sha256': {f: sha(os.path.join(ROOT, f)) for f in ('scripts/astra_data.py', 'scripts/astra_trades.py', 'research/prereg_2026-10-15/p_sharp_and_break.py', 'research/prereg_2026-10-15/download_oos.py')},
       'checks': {'events_not_on_spy_calendar': off_cal, 'p1_buy_points_without_exit_excluded': no_exit, 'symbols_skipped': skipped,
                  'symbols_with_calendar_gaps': len(gaps), 'gaps_detail_first_20': dict(list(sorted(gaps.items()))[:20])},
       'P1': {'sharp': {**desc([x['ret_net'] for x in sh]), **stop_rates(sh), 'concentration': conc(sh), 'by_year': by_year(sh, lambda x: x['ret_net']), 'crisis_windows': crisis(sh, lambda x: x['ret_net'])},
              'other': {**desc([x['ret_net'] for x in ot]), **stop_rates(ot), 'by_year': by_year(ot, lambda x: x['ret_net'])}},
       'P2': {'break': {'n': len(P2b), 'distinct_dates': len({e[0] for e in P2b}), 'distinct_symbols': len({e[3] for e in P2b}), 'by_year': by_year(P2b, lambda e: e[1]), 'crisis_windows': crisis(P2b, lambda e: e[1]),
                        'cost_note': 'fwd20 = C[t+20]/O[t+1]-1,未扣成本(PREREG 的 P2 公式);兩組都扣同樣成本時差值不變'},
              'uptrend_days': {'n': len(P2u)}},
       'sensitivity_descriptive_only': sens,
       'note': '主判定照 PREREG(21 日區塊、97.5%)不變;這裡全部是描述,不能拿來翻案'}
json.dump(out, open(os.path.join(OUTD, f's1_result_{TAG}.json'), 'w'), ensure_ascii=False, indent=1, default=float)
print(json.dumps({'tag': TAG, 'reproduced': same, 'off_cal': off_cal, 'no_exit': no_exit, 'gaps': len(gaps), 'P1_sharp_stop': stop_rates(sh), 'blocks': {k: {kk: [round(vv['lo'], 3), round(vv['hi'], 3)] for kk, vv in v.items()} for k, v in sens['block_lengths'].items()}}, ensure_ascii=False))
