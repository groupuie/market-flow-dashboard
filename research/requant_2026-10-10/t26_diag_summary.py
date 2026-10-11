# t26 摘要:把 t26_diag_5.json / t26_diag_universe.json / t26_diag_coverage.json 整理成可讀的 log(t26_diag_summary.log)
#   ① 五檔:每種記號的「核心觸發日」與擋下的條件(qmDiagSummary 的分類)
#   ② TSM 2026-06-03、2026-10-05:七種記號逐條件
#   ③ 圖層:250 日圖實際畫出的根數/日期範圍、期間內有算出但沒畫到的記號
#   ④ 全追蹤宇宙(同一期間):同樣分類的加總、涵蓋清單
# 這些是「次數」,不是勝率。
import json, os, collections
HERE = os.path.dirname(os.path.abspath(__file__))
F = json.load(open(os.path.join(HERE, "t26_diag_5.json"), encoding="utf-8"))
U = json.load(open(os.path.join(HERE, "t26_diag_universe.json"), encoding="utf-8"))
CV = json.load(open(os.path.join(HERE, "t26_diag_coverage.json"), encoding="utf-8"))
FROM, TO, WIN = "2025-10-10", "2026-10-09", 250
MARKS = ["頂K", "減碼", "出", "抄底", "加", "熱", "買"]
def chart_start(n):   # 與 index.html cockpitRows + renderCockpit 相同:日K ≥260 根時 rows 從第 252 根起(暖機),再取最後 250 根
    i0 = 252 if n >= 260 else 5
    return max(i0, n - WIN)
def fmt_cnt(d): return "、".join(f"{k} {v}" for k, v in sorted(d.items(), key=lambda kv: (not kv[0].startswith("標出"), kv[0].startswith("(另)"), -kv[1])))
print(f"BUILD {U['build']} | 最後已收盤日 {U['lastDone']} | 期間 {FROM} ~ {TO}")
print("\n① 五檔 核心觸發日 → 標出 / 擋在哪一道(次數,不是勝率)")
for s, r in F.items():
    print(f"\n{s}(日K {r['bars']} 根 {r['first']}~{r['last']};⑦資金流 {r['fmDays']} 天;出/抄底冷卻重播與網頁事件一致={r['replayMatches']})")
    for m in MARKS:
        if m in r["summary"]: print(f"  {m}:{fmt_cnt(r['summary'][m])}")
    ev = collections.Counter(e["w"] for e in r["events"])
    print("  期間內事件:" + "、".join(f"{k} {v}" for k, v in ev.items()))
print("\n② TSM 兩天逐條件(true=通過,false=擋下,null=資料不足)")
t = F["TSM"]
for d in ("2026-06-03", "2026-10-05"):
    row = next(x for x in t["rows"] if x["d"] == d)
    print(f"\nTSM {d}")
    for m in MARKS: print(f"  {m}:" + json.dumps(row[m], ensure_ascii=False))
print("\n③ 圖層(CHIP_WIN=250;cockpitRows 在日K ≥260 根時前 252 根當暖機不畫)")
for s, r in F.items():
    c = r["chart"]; n = r["bars"]; st = chart_start(n)
    drawn = set(c["marks"]); ev = [(e["w"], e["d"]) for e in r["events"]]
    hidden = [f"{w} {d}" for w, d in ev if f"{w}|{d[5:]}" not in drawn]
    print(f"  {s}:圖上 {c['n']} 根({c['x0']}→{c['x1']};推算起點 index {st}),畫出 {len(drawn)} 個字;期間事件 {len(ev)} 個;沒畫到:{'、'.join(hidden) if hidden else '無'}")
print("\n④ 全追蹤宇宙(同一期間)")
cand = CV["candidates"]; bars = CV["bars"]; rows = U["rows"]
miss = {s: bars.get(s) for s in cand if s not in rows}
print(f"  候選 {len(cand)} 檔(chipSyms {CV['allChipSyms']} 檔去掉槓桿/反向 ETF);有診斷 {len(rows)} 檔;沒進 {len(miss)} 檔:")
print("   網頁沒有日K:" + "、".join(s for s, v in miss.items() if v == "none"))
print("   日K 不到 70 根:" + "、".join(f"{s}({v})" for s, v in miss.items() if isinstance(v, int)))
print(f"  冷卻重播與網頁事件不一致:{[s for s, r in rows.items() if not r.get('replayMatches')] or '無'}")
tot = collections.defaultdict(collections.Counter)
for s, r in rows.items():
    for m, d in r["summary"].items(): tot[m].update(d)
for m in MARKS:
    if m in tot: print(f"  {m}:{fmt_cnt(tot[m])}")
evc = collections.Counter(e["w"] for r in rows.values() for e in r["events"])
print("  期間內事件:" + "、".join(f"{k} {v}" for k, v in evc.most_common()))
trunc = []; hid = collections.Counter(); hid_sym = {}; edge = collections.Counter()
for s, r in rows.items():
    n = r["bars"]; st = chart_start(n)
    if n - st < WIN: trunc.append((s, n, n - st))
    for e in r["events"]:
        if e["j"] >= st: continue
        if e["j"] >= n - WIN:   # 本來在 250 根視窗內,卻因為暖機(前 252 根不畫)而看不到 → 圖層造成的「漏標」
            hid[e["w"]] += 1; hid_sym[s] = hid_sym.get(s, 0) + 1
        else: edge[e["w"]] += 1   # 2025-10-10 那一根:診斷期間 251 個交易日,比 250 根的圖多 1 天,不算漏畫
print(f"  250 日圖畫不滿 250 根的:{len(trunc)} 檔 " + "、".join(f"{s}({k} 根/日K {n})" for s, n, k in sorted(trunc, key=lambda x: x[2])))
print(f"  因暖機看不到(本來在 250 根視窗內)的事件:{sum(hid.values())} 個,{len(hid_sym)} 檔 {hid_sym};依種類 {dict(hid)}")
print(f"  (另)期間第一天 2025-10-10 的事件 {sum(edge.values())} 個:診斷期間 251 天、圖 250 根,本來就不在圖上,不算漏畫;依種類 {dict(edge)}")
