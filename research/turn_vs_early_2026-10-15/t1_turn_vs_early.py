# Claude 2026-10-15(只描述):「跌過頭就買」vs「跌過頭 + 等一根轉向(▲底,網站現行)」
#   起因:使用者問 AI 股連跌一週(BE、NBIS)為什麼 Astra 沒有抄底
#   早買 = 當天出現超賣(RSI2 ≤ 10、收盤 ≤ 布林下緣、九轉買 9 任一),冷卻 5 根(同 ▲底 的冷卻);不等轉向
#   ▲底 = 近 3 天出現過超賣 + 今天收盤 > 昨天最高(網站 sw_series 的 bot)
#   賣法 = 乙(頂到了 / 收盤 ≤ 進場 × 0.92 / 第 20 根),每個買點各算一次,每邊 0.1%;266 檔,訊號日 2010-01 ~ 2026-07
#   另看「急跌」子集:訊號那天收盤比 6 根前低 ≥ 15%(像 BE、NBIS 這週)
#   用法:python3 -I t1_turn_vs_early.py <Claude 10/13 快照資料夾>  → t1_result.json
import json, os, sys, math, statistics as st
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..', '..')
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import astra_data as AD, astra_trades as AT
D = sys.argv[1]; man = json.load(open(f'{D}/manifest.json'))['symbols']
uni = [s.strip() for s in open(os.path.join(HERE, '..', 'astra_v0.5.0_2026-10-13', 'universe_266.txt')) if s.strip() and not s.startswith('#')]
A0, A1, COST = '2010-01-01', '2026-07-31', 0.001
def oversold(C):
    n = len(C); r2 = [None] * n; ag = al = 0.0
    for i in (1, 2):
        d = C[i] - C[i - 1]; ag += max(d, 0); al += max(-d, 0)
    ag /= 2; al /= 2; r2[2] = 100 if al == 0 else 100 - 100 / (1 + ag / al)
    for i in range(3, n):
        d = C[i] - C[i - 1]; ag = (ag + max(d, 0)) / 2; al = (al + max(-d, 0)) / 2; r2[i] = 100 if al == 0 else 100 - 100 / (1 + ag / al)
    lo = [None] * n
    for i in range(19, n):
        m = sum(C[i - 19:i + 1]) / 20; sd = math.sqrt(sum((c - m) ** 2 for c in C[i - 19:i + 1]) / 20); lo[i] = m - 2 * sd
    tb = [0] * n
    for i in range(4, n): tb[i] = tb[i - 1] + 1 if C[i] < C[i - 4] else 0
    return [bool((r2[i] is not None and r2[i] <= 10) or (lo[i] is not None and C[i] <= lo[i]) or tb[i] == 9) for i in range(n)]
acc = {}
def add(k, v): acc.setdefault(k, []).append(v)
for s in uni:
    b = json.load(open(f"{D}/{man[s]['adjustedFile']}"))['bars']
    pb = [[x[0], AD.rp(x[1]), AD.rp(x[2]), AD.rp(x[3]), AD.rp(x[4]), x[5]] for x in b]
    W = AD.sw_series(pb); O = [x[1] for x in pb]; C = [x[4] for x in pb]; Dt = W['D']; n = W['n']; tops = set(W['top'])
    sty = AT.STY['b']; osd = oversold(C)
    early = []; last = -10 ** 9
    for i in range(2, n):
        if osd[i] and i - last > 5: early.append(i); last = i
    for name, idx in (('turn_bot', W['bot']), ('early_oversold', early)):
        for i in idx:
            if not (A0 <= Dt[i] <= A1) or i + 1 >= n: continue
            d, why = AT.exit_of(W, O, i, sty, tops)
            if d is None or d + 1 >= n: continue
            r = AT.ret(O, i + 1, d + 1, COST)
            mae = min(C[i + 1:d + 1] or [O[i + 1]]) / O[i + 1] - 1
            more = min(C[i:i + 11]) / C[i] - 1   # 訊號後 10 天內還會再跌多少(收盤)
            sharp = i >= 6 and C[i] / C[i - 6] - 1 <= -0.15
            for g in (['all'] + (['sharp'] if sharp else [])):
                add((name, g), (r, mae, more, why, s))
def summ(v):
    rs = sorted(x[0] for x in v); w = [x for x in rs if x > 0]; l = [x for x in rs if x < 0]
    wh = {}
    for x in v: wh[x[3]] = wh.get(x[3], 0) + 1
    syms = {}
    for x in v: syms[x[4]] = syms.get(x[4], 0) + x[0]
    top = sorted(syms.items(), key=lambda kv: -kv[1])[:5]
    return {'n': len(rs), 'win': round(100 * len(w) / len(rs), 1), 'mean': round(100 * st.mean(rs), 2), 'median': round(100 * st.median(rs), 2),
            'mean_trim1pct': round(100 * st.mean(rs[int(.01 * len(rs)):len(rs) - int(.01 * len(rs))]), 2),
            'top5_symbols_sum_ret': [(k, round(100 * s_, 0)) for k, s_ in top], 'avg_win': round(100 * st.mean(w), 1), 'avg_loss': round(100 * st.mean(l), 1),
            'p05': round(100 * rs[int(.05 * len(rs))], 1), 'stop_rate': round(100 * wh.get('停損', 0) / len(v), 1),
            'mae_median': round(100 * st.median(x[1] for x in v), 1), 'further_drop_10d_median': round(100 * st.median(x[2] for x in v), 1)}
out = {f'{k[0]}|{k[1]}': summ(v) for k, v in sorted(acc.items())}
json.dump(out, open(os.path.join(HERE, 't1_result.json'), 'w'), ensure_ascii=False, indent=1)
for k, v in out.items(): print(k, v)
