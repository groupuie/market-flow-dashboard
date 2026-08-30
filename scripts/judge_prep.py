#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""盤後判讀「省 token 前置」(2026-08-09)。

目的:讓每日盤後的 Claude 場次**只讀幾 KB、只寫幾百字**就能更新個股判讀。
所有粗活(抓檔、算觸發、挑名單、擷取事實)都在這支純 stdlib 腳本做完,不花任何 token。

輸出兩個檔:
  digest.md    —— 只含「今天真的需要重寫判讀」的標的,每檔一段精簡事實(約 300–500 字/檔)
  answer.tpl.json —— 待填骨架(欄位=stance/conf/stance_note/plan 的最小集合)

判讀名單來源(依序):
  1) signals.json 內引擎算好的 review.due(機械觸發器:價入entry區/觸停損/達目標/TD9·13完成/
     ⑦與5日反向/gamma翻轉位易手/財報3天內/擠壓≥70首見/CTA線易手或分數翻轉)
  2) 上次判讀距今 >N 天(預設 7)的標的 —— 避免有些標的永遠不被觸發而長期停在舊判讀
  3) 以 --max 上限截斷(預設 8),排序:有觸發者優先、其次最久沒更新者

用法:
  python3 judge_prep.py --signals data/signals.json --out-dir out [--max 8] [--stale-days 7]
"""
import argparse, json, os, sys
from datetime import datetime, timezone

def utcs(): return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

def days_since(s):
    if not s: return 999
    for f in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            d = datetime.strptime(s[:19], f).replace(tzinfo=timezone.utc)
            return (datetime.now(timezone.utc) - d).days
        except Exception:
            continue
    return 999

def g(d, *ks, default=None):
    for k in ks:
        if not isinstance(d, dict): return default
        d = d.get(k)
        if d is None: return default
    return d

def fnum(v, n=2):
    try: return ("%." + str(n) + "f") % float(v)
    except Exception: return "–"

def brief(sym, s):
    """把一檔的 computed 事實壓成人可讀、模型好判斷的精簡段落(不含任何主觀字眼)。"""
    ct = s.get("computed_tech") or {}
    cta = ct.get("cta") or {}
    tg = cta.get("triggers") or {}
    gam = s.get("gamma") or {}
    f7 = s.get("futu7") or {}
    rv = s.get("review") or {}
    L = [f"### {sym}"]
    L.append(f"- 觸發:{'、'.join(rv.get('why') or []) or '(無機械觸發;因判讀老舊列入)'}")
    L.append(f"- 收 {fnum(ct.get('close'))}({ct.get('d','–')}) · 1D {fnum(ct.get('chg1d'),2)}% · 5D {fnum(ct.get('chg5d'),2)}% · 20D {fnum(ct.get('chg20d'),2)}%"
             f" · 距60日高 {fnum(ct.get('off_60d_high_pct'),1)}%")
    L.append(f"- vsEMA20 {fnum(ct.get('vs_ema20_pct'),2)}% · vsEMA50 {fnum(ct.get('vs_ema50_pct'),2)}% · EMA200 {fnum(ct.get('ema200'))}"
             f" · RSI6/12 {fnum(ct.get('rsi6'),1)}/{fnum(ct.get('rsi12'),1)} · 帶寬位階 {fnum(ct.get('boll_bw_pctile'),0)}")
    L.append(f"- 量倍 {fnum(ct.get('vol_pace'),2)}× · 週轉 {fnum((ct.get('turnover_rate') or 0)*100,2)}% · OBV在均上 {ct.get('obv_above_ma')}"
             f" · 背離 RSI{ct.get('rsi_bull_div')}/OBV{ct.get('obv_bull_div')}")
    L.append(f"- 擺盪區間 {fnum(ct.get('swing_lo'))}–{fnum(ct.get('swing_hi'))} · TD setup {ct.get('td_setup_now')} · 買/賣倒數 {ct.get('td_buy_cd')}/{ct.get('td_sell_cd')}")
    if cta:
        t = lambda k: (f"{fnum((tg.get(k) or {}).get('px'))}({fnum((tg.get(k) or {}).get('dist_pct'),1)}%)" if tg.get(k) else "–")
        L.append(f"- CTA 分數 {cta.get('score')} · RV20 {fnum(cta.get('rv20'),1)}(位階 {cta.get('rv_pct')}) · "
                 f"觸發線 MA50 {t('ma50')} MA100 {t('ma100')} MA200 {t('ma200')}")
    if gam:
        L.append(f"- GEX {fnum(gam.get('gex_bn'),2)}Bn · 翻轉 {fnum(gam.get('flip'))} · Call牆 {fnum(gam.get('call_wall'))} · "
                 f"Put牆 {fnum(gam.get('put_wall'))} · MaxPain {fnum(gam.get('max_pain'))} · ATM IV {fnum(gam.get('atm_iv'),1)} · "
                 f"P/C {fnum(gam.get('pc_vol'),2)} · 擠壓 {gam.get('squeeze_score')}")
    if f7:
        L.append(f"- ⑦ 大單淨流:今日 {fnum((f7.get('d1') or 0)/1e6,1)}M · 5日 {fnum(f7.get('d5'),1)}M")
    pl_ = (ct.get("patterns") or {}).get("list") or []
    if pl_:
        L.append("- 型態:" + "、".join([f"{p.get('type')}({p.get('state')},{'多' if p.get('dir',0)>0 else '空'})" for p in pl_[:3]]))
    ins = s.get("insider_90d") or {}
    if ins.get("p_cnt") is not None:
        L.append(f"- 內部人90日:買 {ins.get('p_cnt',0)} 筆 ${fnum((ins.get('p_val') or 0)/1e6,1)}M / 賣 {ins.get('s_cnt',0)} 筆 ${fnum((ins.get('s_val') or 0)/1e6,1)}M")
    if s.get("next_earnings"): L.append(f"- 下次財報:{s.get('next_earnings')}")
    rq = (s.get("computed_fund") or {}).get("rev_q") or []
    if rq:
        last = rq[-1]
        L.append(f"- 最近季營收:{last.get('q')} {fnum((last.get('rev') or 0)/1e9,2)}B · YoY {fnum(last.get('yoy'),1)}%")
    mk = [m for m in (s.get("marks") or []) if not m.get("auto")][-2:]
    if mk: L.append("- 近期人工標記:" + "; ".join([f"{m.get('d','')} {m.get('title','')}" for m in mk]))
    L.append(f"- 現行判讀({days_since(s.get('claude_updated_utc'))} 天前):{s.get('stance','–')} | conf {s.get('conf','–')}")
    note = (s.get("stance_note") or "")[:200]
    if note: L.append(f"  現行敘述:{note}")
    pl = s.get("plan") or {}
    if pl:
        e = (pl.get("entry") or [{}])[0]
        L.append(f"  現行計畫:進 {e.get('px_lo','–')}–{e.get('px_hi','–')} · 停 {g(pl,'stop','px',default='–')} · "
                 f"標 {'/'.join([str(t2.get('px')) for t2 in (pl.get('targets') or [])][:2]) or '–'} · {pl.get('horizon','–')}")
    return "\n".join(L)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--signals", default="data/signals.json")
    ap.add_argument("--out-dir", default="out")
    ap.add_argument("--max", type=int, default=8)
    ap.add_argument("--stale-days", type=int, default=7)
    a = ap.parse_args()

    S = json.load(open(a.signals, encoding="utf-8"))
    syms = S.get("symbols") or {}
    rows = []
    for k, v in syms.items():
        rv = v.get("review") or {}
        stale = days_since(v.get("claude_updated_utc"))
        due = bool(rv.get("due"))
        if due or stale >= a.stale_days:
            rows.append((0 if due else 1, -stale, k))
    rows.sort()
    picked = [k for _, _, k in rows][:a.max]
    dropped = max(0, len(rows) - len(picked))

    os.makedirs(a.out_dir, exist_ok=True)
    dg = [f"# 盤後判讀待辦 · {utcs()} UTC",
          f"引擎資料時間:{S.get('updated_utc','–')} · mode={S.get('mode','–')}",
          f"待判讀 {len(picked)} 檔(機械觸發 {sum(1 for r in rows if r[0]==0)} 檔、判讀老舊 {sum(1 for r in rows if r[0]==1)} 檔"
          + (f";因上限 --max {a.max} 略過 {dropped} 檔,明日順位優先" if dropped else "") + ")",
          "",
          "規則提醒:只依下列 computed 事實寫判讀;不得推估未提供的數字;不寫成投資建議;",
          "判讀=主觀綜合,其勝率貢獻未經證明(留檔供前瞻評分)。無把握就寫「觀望」並說明缺什麼證據。",
          ""]
    for k in picked:
        dg.append(brief(k, syms[k])); dg.append("")
    open(os.path.join(a.out_dir, "digest.md"), "w", encoding="utf-8").write("\n".join(dg))

    tpl = {"asof_utc": utcs(), "symbols": {k: {"stance": "", "conf": 2, "stance_note": "",
            "plan": {"entry": [{"px_lo": None, "px_hi": None, "note": ""}],
                     "stop": {"px": None, "note": ""},
                     "targets": [{"px": None, "note": ""}],
                     "horizon": "", "sizing": ""}} for k in picked}}
    json.dump(tpl, open(os.path.join(a.out_dir, "answer.tpl.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    print(f"待判讀 {len(picked)} 檔:{', '.join(picked) if picked else '(無)'}")
    print(f"digest.md {os.path.getsize(os.path.join(a.out_dir,'digest.md'))} bytes")
    if not picked: print("NOTHING_TO_DO")

if __name__ == "__main__":
    main()
