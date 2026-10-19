# Claude 2026-10-17:P1 / P2 補件第 3 輪(回應 Astra v0.7.4 §2.3、附錄二 §三–§四)— 原登記、原程式、原結果、s1 / s2 輸出都不動,只加檢查
#   1. 共同日曆固定讀 manifest 裡 SPY 的 adjustedFile(不再由參數指定),位元組 SHA-256 要等於 manifest 記的;日期清單要嚴格遞增、不重複,記下清單的 SHA-256
#   2. 每檔:檔案裡的日期要嚴格遞增、不重複(凍結的 load() 不會自己排序去重),每一天都要在共同日曆裡(不在的逐一列出)
#   3. P1 每個事件:訊號日 ~ 出場日「實際的日期序列」要等於共同日曆從訊號日到出場日的那一段(逐日比對,不是只比根數);進場 = 共同日曆的下一個交易日
#   4. P2 每個上升日 / 破線事件:t ~ t+20 實際的 21 個日期 = 共同日曆從 t 開始的 21 個交易日
#   5. 和 s2(端點根數檢查)的結果逐筆比:有問題的事件集合要一樣
#   6. 構造反例:少一天 + 重複一天、少一天 + 多一個週六 → s2 的根數檢查會放過,這裡要擋下(只是方法測試,不代表真實資料有這種錯)
#   不在範圍:訊號之前的指標回看期(均線、急跌、冷卻用到的過去 K 線)— 這裡只查持有 / 觀察窗口
#   用法:python3 -I s3_sequence_check.py <資料夾> <名單檔> <原結果 json> <s2 結果 json> <輸出資料夾> <標籤>
import json, os, sys, hashlib
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..', '..')
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import p_sharp_and_break as PB          # 凍結的分析程式,只 import
import astra_data as AD, astra_trades as AT

D, ULIST, ORIG, S2, OUTD, TAG = sys.argv[1:7]
H = lambda b: hashlib.sha256(b).hexdigest()
orig = json.load(open(ORIG)); s2 = json.load(open(S2)); os.makedirs(OUTD, exist_ok=True)
mb = open(os.path.join(D, 'manifest.json'), 'rb').read(); assert H(mb) == orig['meta']['data_dir_manifest_sha256']
man = json.loads(mb)['symbols']
spy = man['SPY']; spy_path = os.path.join(D, spy['adjustedFile']); spy_bytes = open(spy_path, 'rb').read()
want = spy.get('sha256') or spy.get('adjustedSha256'); assert H(spy_bytes) == want, 'SPY 日曆檔的指紋和 manifest 不同'
cal = [x[0] for x in json.loads(spy_bytes)['bars']]
assert cal == sorted(set(cal)), 'SPY 日曆不是嚴格遞增或有重複'
si = {d: k for k, d in enumerate(cal)}
syms = [s.strip() for s in open(ULIST) if s.strip() and not s.startswith('#')]


def window_ok(Dt, a, b):
    """個股第 a ~ b 根的實際日期 = 共同日曆從 Dt[a] 開始的同長度一段(逐日);回傳 (ok, 說明)"""
    if Dt[a] not in si: return False, f'{Dt[a]} 不在共同日曆'
    k = si[Dt[a]]; exp = cal[k:k + (b - a + 1)]; act = Dt[a:b + 1]
    if act == exp: return True, ''
    j = next(q for q in range(min(len(act), len(exp))) if act[q] != exp[q]) if any(x != y for x, y in zip(act, exp)) else min(len(act), len(exp))
    return False, f'第 {j} 天不同:實際 {act[j] if j < len(act) else "—"}、日曆 {exp[j] if j < len(exp) else "—"}'


def window_to(Dt, a, b):
    """P1:訊號日 a ~ 出場日 b 的實際日期 = 共同日曆從 Dt[a] 到 Dt[b] 的那一段(兩端都要在日曆裡)"""
    if Dt[a] not in si or Dt[b] not in si: return False, '端點不在共同日曆'
    exp = cal[si[Dt[a]]:si[Dt[b]] + 1]; act = Dt[a:b + 1]
    return (act == exp), ('' if act == exp else f'實際 {len(act)} 根、日曆 {len(exp)} 天,第一個不同:' +
                          next((f'{x} vs {y}' for x, y in zip(act, exp) if x != y), '長度不同'))


# ---------- 構造反例(方法測試)
fx_cal = ['2026-10-05', '2026-10-06', '2026-10-07', '2026-10-08', '2026-10-09', '2026-10-12', '2026-10-13']
fx = {'complete': fx_cal, 'missing_only': [d for d in fx_cal if d != '2026-10-08'],
      'missing_plus_duplicate': ['2026-10-05', '2026-10-06', '2026-10-07', '2026-10-07', '2026-10-09', '2026-10-12', '2026-10-13'],
      'missing_plus_weekend': ['2026-10-05', '2026-10-06', '2026-10-07', '2026-10-09', '2026-10-10', '2026-10-12', '2026-10-13']}
cal_save, si_save = cal, si
cal = fx_cal; si = {d: k for k, d in enumerate(cal)}
fixtures = {}
for name, dts in fx.items():
    s2_gap = (si.get(dts[-1], -99) - si.get(dts[0], -99)) - (len(dts) - 1)          # s2 的端點根數檢查
    fixtures[name] = {'s2_endpoint_gap': s2_gap, 's2_accepts': s2_gap == 0 and dts[1] == cal[1], 'sequence_check_accepts': window_to(dts, 0, len(dts) - 1)[0]}
assert fixtures['complete']['sequence_check_accepts'] and all(fixtures[k]['s2_accepts'] and not fixtures[k]['sequence_check_accepts'] for k in ('missing_plus_duplicate', 'missing_plus_weekend'))
cal, si = cal_save, si_save

# ---------- 逐檔、逐事件
sym_issues, P1f, P2bf, P2uf = {}, [], [], {'n': 0, 'flagged': 0, 'by_symbol': {}}
nP1 = nP2b = 0
for s in syms:
    if s not in man: continue
    pb = PB.load(D, s, man)
    if len(pb) < 60: continue
    Dt = [x[0] for x in pb]
    iss = {}
    if Dt != sorted(set(Dt)): iss['not_strictly_increasing_or_duplicate'] = sum(1 for a, b in zip(Dt, Dt[1:]) if b <= a)
    off = [d for d in Dt if d not in si]
    if off: iss['dates_not_in_common_calendar'] = off[:20] + (['…'] if len(off) > 20 else [])
    first, last = (si.get(Dt[0]), si.get(Dt[-1]))
    if first is not None and last is not None:
        miss = [d for d in cal[first:last + 1] if d not in set(Dt)]
        if miss: iss['calendar_sessions_missing_inside_range'] = miss[:20] + (['…'] if len(miss) > 20 else [])
    if iss: sym_issues[s] = iss
    W = AD.sw_series(pb); n = W['n']; O = [x[1] for x in pb]; C = [x[4] for x in pb]
    sty = AT.style_of(s); tops = set(W['top'])
    for i, k in AT.buy_points(W):
        if not (PB.A0 <= Dt[i] <= PB.A1) or i < PB.SHARP_LB or i + 1 >= n: continue
        d, why = AT.exit_of(W, O, i, sty, tops)
        if d is None or d + 1 >= n: continue
        nP1 += 1
        ok, note = window_to(Dt, i, d + 1)
        nxt = si.get(Dt[i]) is not None and si[Dt[i]] + 1 < len(cal) and cal[si[Dt[i]] + 1] == Dt[i + 1]
        if not (ok and nxt):
            P1f.append({'date': Dt[i], 'sym': s, 'entry': Dt[i + 1], 'exit': Dt[d + 1], 'entry_is_next_session': nxt, 'sequence_equal': ok, 'note': note,
                        'sharp': C[i] / C[i - PB.SHARP_LB] - 1 <= PB.SHARP, 'ret_net': AT.ret(O, i + 1, d + 1, PB.COST)})
    s20, s50 = PB.sma(C, 20), PB.sma(C, 50); lastb = -10 ** 9
    for t in range(50, n):
        if s20[t] is None or s50[t] is None or s20[t - 1] is None: continue
        up = s20[t] > s50[t]
        brk = up and C[t] < s20[t] and C[t - 1] >= s20[t - 1] and t - lastb > PB.COOL
        if brk: lastb = t
        if not (PB.A0 <= Dt[t] <= PB.A1) or t + PB.H >= n: continue
        if up:
            ok, note = window_ok(Dt, t, t + PB.H); P2uf['n'] += 1
            if not ok: P2uf['flagged'] += 1; P2uf['by_symbol'][s] = P2uf['by_symbol'].get(s, 0) + 1
            if brk:
                nP2b += 1
                if not ok: P2bf.append({'date': Dt[t], 'sym': s, 'note': note})

# ---------- 和 s2 比
s2p1 = {(e['date'], e['sym']) for e in s2['P1_window_issues']['events']}
s3p1 = {(e['date'], e['sym']) for e in P1f}
s2b = {(e['date'], e['sym']) for e in s2['P2_window_issues']['break_events']}
cmp = {'P1_events_same_count': nP1 == s2['P1_window_issues']['n_events'], 'P1_flag_sets_equal': s2p1 == s3p1,
       'P2_break_same_count': nP2b == s2['P2_window_issues']['n_break'], 'P2_break_flag_sets_equal': s2b == {(e['date'], e['sym']) for e in P2bf},
       'P2_uptrend_same_count': P2uf['n'] == s2['P2_window_issues']['n_uptrend'], 'P2_uptrend_flag_counts_equal': P2uf['flagged'] == s2['P2_window_issues']['n_uptrend_flagged']}
out = {'tag': TAG, 'scope': '持有 / 觀察窗口的逐日日期序列;不含訊號之前的指標回看期',
       'common_calendar': {'file': spy['adjustedFile'], 'file_sha256': H(spy_bytes), 'manifest_field': 'sha256' if 'sha256' in spy else 'adjustedSha256',
                           'matches_manifest': True, 'sessions': len(cal), 'first': cal[0], 'last': cal[-1], 'date_list_sha256': H('\n'.join(cal).encode()),
                           'strictly_increasing_unique': True},
       'symbol_date_issues': sym_issues, 'P1': {'n_events': nP1, 'n_flagged': len(P1f), 'events': P1f},
       'P2_break': {'n_events': nP2b, 'n_flagged': len(P2bf), 'events': P2bf[:50]}, 'P2_uptrend': P2uf,
       'compare_with_s2_endpoint_check': cmp, 'constructed_fixtures': fixtures,
       'note': '原判定照 PREREG 不變;這裡只檢查,排除後的敏感度沿用 s2(事件集合相同時數字相同)'}
json.dump(out, open(os.path.join(OUTD, f's3_result_{TAG}.json'), 'w'), ensure_ascii=False, indent=1, default=float)
print(json.dumps({'tag': TAG, 'calendar': out['common_calendar'], 'symbols_with_date_issues': len(sym_issues), 'P1_flagged': len(P1f), 'P2b_flagged': len(P2bf),
                  'P2u_flagged': P2uf['flagged'], 'compare': cmp, 'fixtures': {k: (v['s2_accepts'], v['sequence_check_accepts']) for k, v in fixtures.items()}}, ensure_ascii=False))
