# t28 摘要:把 t28_buydiag.json 整理成可讀 log(t28_buydiag.log),逐項對照 Codex v0.3 的數字。次數/條件,不是勝率。
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
R = json.load(open(os.path.join(HERE, "t28_buydiag.json"), encoding="utf-8"))
W = R["window"]
def day(s, d): return next(x for x in W[s]["days"] if x["d"] == d)
def f(x, n=4): return "—" if x is None else (f"{x:.{n}f}" if isinstance(x, float) else str(x))
def yn(x): return {True: "通過", False: "不符", None: "未知"}[x]
print(f"BUILD {R['build']} | 最後已收盤日 {R['lastDone']} | ⑦ 合併後 {R['flowDays'][0]} 天({R['flowDays'][1]}~{R['flowDays'][2]})| 資金氣候到 {R['climateLast']} | 頁面錯誤 {R['errors'] or '無'}")
print("\n① 2026-09-01~10-09 正式事件 vs 研究副本(拿掉近 40 根新高)")
for s, r in W.items():
    o = [e for e in r["eventsOrig"]]; n = [e for e in r["eventsNoHigh"]]
    add = sorted(set(n) - set(o)); rem = sorted(set(o) - set(n))
    print(f"  {s}:日K {r['bars']} 根 {r['first']}~{r['last']},⑦ {r['fmDays']} 天,QQQ 日K到 {r['qqqLast']}")
    print(f"    正式:{', '.join(o) or '無'}")
    print(f"    研究副本:新增 {', '.join(add) or '無'};消失 {', '.join(rem) or '無'}")
print("\n② ⑦ 覆蓋(近 20 根有資料的天數)與 20 日大單淨額")
for s, r in W.items():
    cv = sorted(set(x["cov20"] for x in r["days"])); neg = all((x["f20r"] or 0) < 0 for x in r["days"])
    print(f"  {s}:每天 cov20 ∈ {cv};20 日大單淨額全期為負={neg}(最大 {max(x['f20r'] for x in r['days']):.1f}、最小 {min(x['f20r'] for x in r['days']):.1f} 百萬美元)")
print("\n③ 趨勢買(9/17 SPY vs QQQ)")
for s in ("SPY", "QQQ"):
    x = day(s, "2026-09-17")
    print(f"  {s} 9/17:收 {f(x['close'],3)};50 日線 {f(x['s50'])};10 根前 50 日線 {f(x['s50_10ago'])};收在 50 日線上 {yn(x['close']>x['s50'])};50 日線向上 {yn(x['s50']>x['s50_10ago'])};"
          f"近 10 根 TD買最高 {x['td10max']};低檔/壓縮 {yn(x['lowOrSqz10'])};正資金 {yn(x['posFlow10'])};passT {x['passT']}(前一天 {x['passTprev']})")
x = day("SPY", "2026-09-01"); print(f"  SPY 9/01:passT {x['passT']}、前一天 {x['passTprev']} → 不是路徑第一天;加 {x['sigOrig']}")
def addline(s, d):
    x = day(s, d); p = x["prev"]
    print(f"  {s} {d}:RSI {f(x['rsi'],2)} 跌破40={x['rsiX']} 首次碰下緣={x['lbT']} QQQ<20日線={x['qqqBelow20']} 當日+前10根有出={x['chu10']}")
    print(f"    前一天 {p['d']}:收>200日線 {yn(p['cAbove200'])}、50>200 {yn(p['s50gt200'])}、200日線比20根前高 {yn(p['s200up'])}、50>100 {yn(p['s50gt100'])}、100>200 {yn(p['s100gt200'])}、"
          f"近40根創一年新高 {yn(p['newHighIn40'])}(最近一次新高 {p['lastNewHighEver']})→ 穩健上漲 正式 {x['ut']} / 研究副本 {x['utNoHigh']}")
    print(f"    raw 正式 {x['rawOrig']} / 研究副本 {x['rawNoHigh']};加 正式 {x['sigOrig']} / 研究副本 {x['sigNoHigh']};"
          f"Codex 診斷 加:failed {x['diag']['add']['failed']} unknown {x['diag']['add']['unknown']} 與正式比對 {x['diag']['add']['vs']} / raw {x['diag']['add']['rawVs']}")
    o = x["diag"]["obs"]
    print(f"    量比(近5根均量/再前20根均量){f(o['volume5ToPrevious20'],3)};近10根 TD買最高 {x['td10max']};趨勢買缺 {x['diag']['trend']['failed']};regime {x['reg']}")
print("\n④ 加碼(QQQ 9/14、AMD 9/03 與 10/01、PLTR 9/10、AVGO 9/03、9/14、10/01)")
for s, d in (("QQQ", "2026-09-14"), ("AMD", "2026-09-03"), ("AMD", "2026-10-01"), ("PLTR", "2026-09-10"), ("AVGO", "2026-09-03"), ("AVGO", "2026-09-14"), ("AVGO", "2026-10-01")):
    addline(s, d)
print("\n⑤ Codex qmBuyDay 與正式事件逐日比對(五檔 × 28 天)")
mm = []
for s, r in W.items():
    for x in r["days"]:
        for k in ("trend", "cycle", "disaster"):
            if x["diag"][k]["vs"] == "mismatch": mm.append((s, x["d"], k))
        if x["diag"]["add"]["vs"] == "mismatch" or x["diag"]["add"]["rawVs"] == "mismatch": mm.append((s, x["d"], "add"))
        if x["diag"]["buy"]["reconstructedVsOfficial"] == "mismatch": mm.append((s, x["d"], "buy"))
unk = sum(1 for r in W.values() for x in r["days"] for k in ("trend", "cycle", "disaster") if x["diag"][k]["vs"] == "unknown")
print(f"  mismatch:{mm or '無'};unknown(資料或暖機不足而無法比):{unk} 個 路徑×天")
print("\n⑥ 截斷檢查(只用 ≤ 截斷日的資料重算,截斷日以前的 買/加 與全資料相同)")
for p in R["prefix"]: print(f"  {p['sym']} {p['variant']}:{p['cutDates']} 個截斷日,不一致 {p['mismatches'] or '無'}")
print("\n⑦ 全歷史「加」:正式 vs 研究副本(五檔,2021-10~2026-10)")
for s, r in W.items():
    a, b = set(r["addAllOrig"]), set(r["addAllNoHigh"])
    print(f"  {s}:正式 {len(a)}、研究副本 {len(b)};共同 {len(a & b)}、新增 {len(b - a)}、消失 {len(a - b)} {sorted(a - b) if a - b else ''}")
