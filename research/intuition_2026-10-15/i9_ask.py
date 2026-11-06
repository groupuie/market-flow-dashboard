#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""盤感訓練 I9:問答模式雛形 —「這檔現在可以買嗎?」

用法:python3 i9_ask.py SYMBOL SCRATCH_DIR
輸出(JSON + 幾行白話):
  1. 規則現在說什麼(= 網站 Astra 買 / 賣,一次一筆):今天有沒有買點 / 頂點、是不是持有中、停損價、最晚哪天賣
  2. 下一個「回」買點要什麼價格(收盤 ≤ 近 6 天最低、而且還在 50 / 200 日線上)
  3. 如果今天是買點 / 頂點:經驗庫裡最像的過去 k 次(賺的比例、平均、碰停損)
  4. 風格溫度(高波動股近 20 天 − 低波動股;第 1 輪事後探索,還沒驗證)
  5. 我的盤感成績(練習考第 1 輪):沒有優勢 → 判斷以規則為主,盤感只當參考
只讀公開日K;不改任何正式程式。槓桿指數 ETF 看正股(TQQQ / QLD → QQQ;UPRO / SPXL / SSO → SPY)。
"""
import datetime as dt, gzip, json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "scripts")); sys.path.insert(0, HERE)
import numpy as np
import astra_data as AD, astra_trades as AT, astra_ledger as LG

SYM = sys.argv[1].upper(); S = sys.argv[2]
UL = {"TQQQ": "QQQ", "QLD": "QQQ", "UPRO": "SPY", "SPXL": "SPY", "SSO": "SPY"}
base = UL.get(SYM, SYM)
now = int(time.time()); asof = LG.last_done()


def bars(sym):
    b = AD.yahoo(sym, now - AD.FETCH_DAYS * 86400, now + 86400)
    b = [x for x in b if x[0] <= asof]
    return [[x[0], AD.rp(x[1]), AD.rp(x[2]), AD.rp(x[3]), AD.rp(x[4]), x[5]] for x in b[-AD.KEEP:]]


B = bars(base); SPY = bars("SPY"); QQQ = bars("QQQ")
W = AD.sw_series(B); n = W["n"]; i = n - 1; D = W["D"]; C = W["C"]; O = [x[1] for x in B]
sty = AT.style_of(base); T = AT.trades(W, O, sty); kinds = dict(AT.buy_points(W)); tops = set(W["top"])


def mk(Bx):
    Cx = [x[4] for x in Bx]; j = len(Cx) - 1
    return {"r5": LG.pct(Cx[j], Cx[j - 5]), "r20": LG.pct(Cx[j], Cx[j - 20]), "vs200": LG.pct(Cx[j], sum(Cx[j - 199:j + 1]) / 200)}


mkt = {"SPY": mk(SPY), "QQQ": mk(QQQ)}
out = {"symbol": SYM, "看的是": base, "asof": D[i], "close": C[i], "rule": sty["name"] + ("(頂到了 / 收盤 ≤ 買價 × 0.92 / 第 20 天)" if sty["stop"] else "(第一個頂 / 第 40 天)")}
# 1. 規則現在說什麼
last = T[-1] if T else None
if i in kinds and last and last["i"] == i:
    out["規則"] = f"今天收盤出現「買」({kinds[i]})→ 明天開盤買"
elif last and (last["x"] is None or last["x"] >= n) and last["e"] is not None and last["e"] < n:
    e = last["e"]; held = i - e + 1
    if last["d"] is not None:
        out["規則"] = f"持有中({D[last['i']]} 的買)→ 今天收盤已經出現賣出條件({last['why']}),明天開盤賣"
    else:
        stop = round(O[e] * (1 - sty["stop"]), 2) if sty["stop"] else None
        deadline_k = last["i"] + sty["lim"]
        out["規則"] = (f"持有中({D[last['i']]} 的買,{D[e]} 開盤 {O[e]} 進場,第 {held} 天)→ "
                     + (f"收盤 ≤ {stop} 就賣;" if stop else "") + f"沒碰到就等頂;最晚再 {deadline_k - i} 根收盤後賣")
else:
    prev = [t for t in T if t["x"] is not None and t["x"] < n]
    out["規則"] = "空手:等下一個買" + (f"(上一筆 {D[prev[-1]['i']]} 買、{D[prev[-1]['x']]} 賣,{prev[-1]['why']},{100 * (O[prev[-1]['x']] / O[prev[-1]['e']] - 1):+.1f}%)" if prev else "")
    if i in kinds:
        out["規則"] += f";今天其實有「{kinds[i]}」訊號,但規則一次只做一筆,這個不算"
if i in tops:
    out["今天是頂點"] = "是(▼頂;第 1 輪練習:我對頂點的直覺是反的,這裡只照規則)"
# 2. 下一個「回」的價格
s50 = sum(C[i - 49:i + 1]) / 50; s50p = sum(C[i - 59:i - 9]) / 50; s200 = sum(C[i - 199:i + 1]) / 200
lvl = min(C[i - 5:i + 1]); lb2 = max([k for k in W["b2"] if k <= i], default=-10 ** 9)
holding = bool(last and (last["x"] is None or last["x"] >= n))
if i - lb2 <= AD.COOL:
    out["下一個「回」"] = f"冷卻中:上一個「回」在 {i - lb2} 根前,規則 {AD.COOL} 根內不會再標" + (";而且持有中的買點不會重複算" if holding else "")
elif s50 >= s50p and lvl >= s50 and lvl > s200:
    out["下一個「回」"] = f"明天收盤 ≤ {lvl:.2f}(近 6 天最低),而且仍 ≥ 50 日線 {s50:.2f}、> 200 日線 {s200:.2f}" + (";但現在持有中,新的買點規則不算" if holding else "")
else:
    why = "50 日線沒有往上" if s50 < s50p else ("近 6 天最低已經在 50 日線下面" if lvl < s50 else "在 200 日線下")
    out["下一個「回」"] = f"短期不會出現({why});只能等 ▲底(先超賣,再收盤站上前一天最高)"
# 3. 經驗庫
q = "buy" if i in kinds else ("top" if i in tops else None)
if q:
    import i2_knn as KN
    pk = LG.packet(base, B, W, i, kinds[i] if q == "buy" else "頂", {"SPY": mkt["SPY"], "QQQ": mkt["QQQ"]}, False, sty)
    r = {k: pk.get(k) for k in ("chg1", "gap", "r5", "r20", "r60", "vs50", "vs200", "pos52", "dd52", "vol20_daily", "vr", "days_since_top", "buys_20d")}
    r.update(q=q, type=pk["type"], kind=pk["kind"], SPY_r5=mkt["SPY"]["r5"], SPY_r20=mkt["SPY"]["r20"], SPY_vs200=mkt["SPY"]["vs200"],
             QQQ_r5=mkt["QQQ"]["r5"], QQQ_r20=mkt["QQQ"]["r20"], QQQ_vs200=mkt["QQQ"]["vs200"])
    pool = [x for x in KN.load_bank(S) if x["exit_date"] < D[i] and KN.gkey(x) == KN.gkey(r)]
    a = KN.knn_stats(pool, [r])[0]
    out["經驗庫"] = (f"最像的過去 {a['k']} 次:{'賺' if q == 'buy' else '10 天後有跌'}的比例 {100 * a['hit']:.0f}%(同類平常 {100 * a['base']:.0f}%)、"
                  f"平均 {100 * a['mean']:+.1f}%" + (f"、碰停損 {100 * a['stop']:.0f}%" if (q == "buy" and sty["stop"]) else "") + "(這個經驗庫在練習考第 2 段沒有預測力,只當參考)")
# 4. 風格溫度(用 268 檔的快照;快照不是今天就略過)
try:
    BB = json.load(gzip.open(os.path.join(S, "data", "bars.json.gz")))
    vs, rs = [], []
    for s_, b_ in BB.items():
        b_ = [x for x in b_ if x[0] <= D[i]]
        if len(b_) < 25 or b_[-1][0] != D[i]:
            continue
        c_ = np.array([x[4] for x in b_[-21:]]); lr = np.diff(np.log(c_))
        vs.append(lr.std(ddof=1)); rs.append(c_[-1] / c_[0] - 1)
    vs, rs = np.array(vs), np.array(rs); q1, q2 = np.percentile(vs, [33.3, 66.7])
    t = float(rs[vs >= q2].mean() - rs[vs <= q1].mean())
    out["風格溫度"] = f"{100 * t:+.1f}%(高波動股近 20 天比低波動股{'強' if t > 0 else '弱'};> +3% 時,歷史上高波動股的買點平均報酬較高、但勝率一樣低;事後探索、未驗證)"
except Exception as ex:
    out["風格溫度"] = "略過(快照不是今天)"
# 5. 我的成績
fr = os.path.join(S, "final_results.json")
if os.path.exists(fr):
    F = json.load(open(fr)); a = F["A_blind_P1P2"]["buy"]; t_ = F["A_blind_P1P2"]["top"]
    out["我的盤感成績(練習考第 1 輪)"] = (f"買點 {a['n']} 題:同意的賺 {100 * a['hit_agree']:.0f}%、不同意的賺 {100 * a['hit_disagree']:.0f}%(AUC {a['auc_p']:.2f} ≈ 擲銅板);"
                                     f"頂點 {t_['n']} 題:我說會跌的只跌 {100 * t_['hit_agree']:.0f}%、說不會跌的反而跌 {100 * t_['hit_disagree']:.0f}%(直覺是反的)")
print(json.dumps(out, ensure_ascii=False, indent=1))
