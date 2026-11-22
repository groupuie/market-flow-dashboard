#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""x10 揭曉網頁(一頁可以翻:每張 = 匿名圖 → 你也可以先猜 → Claude 鎖定的判斷 → 翻開答案)
用法:python3 -I x10_page.py OUT.html      (讀同資料夾的 show.json、null.json、info.json、q01..q10.png)"""
import base64, html, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__)); OUT = sys.argv[1]
S = json.load(open(os.path.join(HERE, "show.json"))); NUL = json.load(open(os.path.join(HERE, "null.json"))); INFO = json.load(open(os.path.join(HERE, "info.json")))
E = html.escape

NOTE = {
    1: "隔天(7/5)就跳空大跌 −5.2%,第 1 天就同時碰到下面兩條線:買方「低點還沒到」對、賣方「高點還沒到」錯。第 8 天最低 −7.1%,之後反彈到第 31 天的 +9.8%,60 天後又跌回 −6.7%。",
    2: "20 天內一路往下:第 7 天跌破洗盤線(買方對、賣方錯),第 19 天最低 −9.1%。之後一路漲,第 56 天 +26.5%,60 天後 +22.3%。這張就是「先洗一段、再漲一大段」—— 真正的低點在第 19 天附近。",
    3: "20 天內在 −7% 到 +5% 之間來回,第 18 天才碰到洗盤線(買方對);賣方兩條線都沒碰到(平)。之後繼續往下,60 天後 −23.2%(60 天內最低 −24.7%)。",
    4: "幾乎沒有回檔(20 天內最低只有 −0.1%),第 9 天就漲一段:那天其實就是買點,我說「低點還沒到」錯了;賣方「高點還沒到」對。第 23 天小拉回 −2.3% 之後一路大漲,60 天後 +48.8%。",
    5: "第 2 天就跌破洗盤線(買方對),第 3 天碰到 −2 個波動(賣方錯),第 7 天 −7.4%。反彈之後又破底,第 46 天(2018-12-26)最低 −17.4%,60 天後 −7.7%。",
    6: "只在第 2 天小跌 −1.7%,之後一路往上:第 9 天碰到被軋線(賣方對),第 13 天漲一段 —— 我說「加碼點還沒到」錯了,那天其實可以加碼。60 天後 +12.6%。",
    7: "隔天(4/3,美國前一天收盤後宣布大規模關稅)跳空大跌,第 1 天就碰到下面兩條線:買方對、賣方錯。第 3 天(4/7)最低 −15.3%,4/9 單日 +10.5%;20 天後回到 +0.6%,60 天後 +12.9%。",
    8: "第 5 天(4/10)先跌到 −7.9%(買方對、賣方錯),之後慢慢爬回,20 天後 +4.6%;第 24 天(5/7)單日 +20%,60 天後 +86.1%。10 張裡最像「洗盤後起漲」的一張 —— 但從圖上看不出洗完會漲這麼多。",
    9: "第 3 天碰到被軋線(賣方對)、第 7 天漲一段(+2 個波動 ≈ +3.6%),「買點」對。不過之後在 −4.5% 到 +6.6% 之間來回,60 天後 +4.0%:有漲,但不是大段。",
    10: "我說「買點」,但第 3 天就跌破洗盤線(買方錯),第 4 天碰到 −2 個波動(賣方也錯),第 18 天最低 −9.5%。之後回到原位附近,60 天後 +2.6%。",
}
OUTC = {("buy", "先漲一段"): "先漲一段(第 {d} 天碰到 +2 個波動)", ("buy", "先跌一段"): "先跌一段(第 {d} 天碰到洗盤線 −1.5)",
        ("sell", "先跌一段"): "先跌一段(第 {d} 天碰到 −2 個波動)", ("sell", "先漲一段"): "先漲一段(第 {d} 天碰到被軋線 +1.5)"}
ICON = {"對": "✓", "錯": "✗", "平": "–"}; CLS = {"對": "good", "錯": "bad", "平": "tie"}


def pct(x):
    return f"{x:+.1f}%".replace("-", "−")


def outc(side, r):
    return "20 天內兩條線都沒碰到" if r[0] == "都沒到" else OUTC[(side, r[0])].format(d=r[1])


def badge(g):
    return f'<span class="badge {CLS[g]}"><i aria-hidden="true">{ICON[g]}</i>{g}</span>'


def img64(p):
    return "data:image/png;base64," + base64.b64encode(open(p, "rb").read()).decode()


LEGEND = """<div class="legend" aria-label="圖例">
 <span><svg width="30" height="10" aria-hidden="true"><line x1="1" y1="5" x2="29" y2="5" class="k-buy"/></svg>買方兩條線:上 = 漲一段(+2 個波動)、下 = 洗盤(−1.5)</span>
 <span><svg width="30" height="10" aria-hidden="true"><line x1="1" y1="5" x2="29" y2="5" class="k-sell"/></svg>賣方兩條線:上 = 被軋(+1.5)、下 = 跌一段(−2)</span>
 <span><svg width="14" height="14" aria-hidden="true"><circle cx="7" cy="7" r="5" class="m-buy"/></svg>買方先碰到的線</span>
 <span><svg width="14" height="14" aria-hidden="true"><path d="M7 1 L13 7 L7 13 L1 7 Z" class="m-sell"/></svg>賣方先碰到的線</span>
 <span><svg width="22" height="12" aria-hidden="true"><rect x="0" y="0" width="22" height="12" class="k-band"/></svg>之後 20 個交易日(算對錯的範圍)</span>
 <span><svg width="22" height="14" aria-hidden="true"><rect x="3" y="2" width="5" height="10" class="k-up"/><rect x="13" y="2" width="5" height="10" class="k-dn"/></svg>K 線:空心 = 收漲、實心 = 收跌(那天收盤 = 100)</span>
</div>"""

cards = []
for s in S:
    n = s["n"]; c = s["call"]; g = s["grade"]; hb, hs = s["hit"]["buy"], s["hit"]["sell"]
    rec = c["認得"]; rec_html = "不認得" if rec == "不認得" else E(rec)
    lv = s["lines"]
    def hitd(h):
        return "—" if h is None else f"第 {h['day']} 天({s['dates'][h['day'] + 59]})"
    cards.append(f"""
<section class="page card" id="p{n}" data-n="{n}" aria-label="第 {n} 張">
 <div class="card-head"><h2>第 {n} 張</h2><span class="pill">日均波動 {INFO[str(n)]['日均波動%']:.1f}%</span></div>
 <figure class="q">
  <button class="zoom" type="button" data-zoom="{n}" aria-label="放大第 {n} 張圖"><img src="{img64(os.path.join(HERE, f'q{n:02d}.png'))}" alt="第 {n} 張匿名日 K 圖(最近 126 根)" width="1000" height="620"></button>
  <figcaption>最右邊那根 = 那天收盤。紅漲綠跌;橘 20 日線、藍 50 日線、紫 200 日線;灰虛線 = 大盤(QQQ)同期;下面是成交量 ÷ 20 日均量。點圖可以放大。</figcaption>
 </figure>
 <div class="guess" role="group" aria-label="你也猜猜看">
  <p class="guess-t">你也猜猜看(可以略過)</p>
  <div class="g-row"><span class="g-side">買方</span><button type="button" class="g" data-n="{n}" data-side="buy" data-v="買點">買點</button><button type="button" class="g" data-n="{n}" data-side="buy" data-v="還要再等">還要再等</button></div>
  <div class="g-row"><span class="g-side">賣方</span><button type="button" class="g" data-n="{n}" data-side="sell" data-v="賣點">賣點</button><button type="button" class="g" data-n="{n}" data-side="sell" data-v="還要再等">還要再等</button></div>
 </div>
 <div class="claude">
  <div class="cover"><button type="button" class="btn ghost show-call" data-n="{n}">看 Claude 怎麼判</button><small>10/20 判完就鎖定,之後才看答案</small></div>
  <div class="call-body">
   <p class="call-t">Claude 的判斷(揭曉前已鎖定)</p>
   <div class="call"><span class="side">買方</span><div><strong>{E(c['買方'])}</strong><span class="conf">把握 {c['買方把握']}%</span><p>{E(c['買方理由'])}</p></div></div>
   <div class="call"><span class="side">賣方</span><div><strong>{E(c['賣方'])}</strong><span class="conf">把握 {c['賣方把握']}%</span><p>{E(c['賣方理由'])}</p></div></div>
   <p class="recog">判斷時認得是哪一檔、哪一天嗎:{rec_html}</p>
  </div>
 </div>
 <button type="button" class="btn primary reveal" data-n="{n}">翻開答案</button>
 <div class="answer">
  <h3 class="ans-title"><span class="sym">{E(s['sym'])}</span> {E(s['name'])} <span class="date">{s['date']}</span></h3>
  <div class="chart" data-n="{n}" tabindex="0" role="img" aria-label="{E(s['sym'])} {s['date']} 前後各約 60 個交易日的走勢,詳細數字在下方"></div>
  {LEGEND}
  <div class="verdicts">
   <div class="v"><span class="side">買方</span><div>我說「{E(c['買方'])}」→ {outc('buy', s['res']['buy'])}</div>{badge(g['buy'])}</div>
   <div class="v"><span class="side">賣方</span><div>我說「{E(c['賣方'])}」→ {outc('sell', s['res']['sell'])}</div>{badge(g['sell'])}</div>
   <div class="v you" data-n="{n}" hidden></div>
  </div>
  <p class="nums"><span>20 天後 <b>{pct(s['ret20'])}</b></span><span>60 天後 <b>{pct(s['ret60'])}</b></span><span>20 天內最高 {pct(s['hi20'][1])}(第 {s['hi20'][0]} 天)</span><span>最低 {pct(s['lo20'][1])}(第 {s['lo20'][0]} 天)</span></p>
  <p class="note">{E(NOTE[n])}</p>
  <details class="table-view"><summary>看數字</summary>
   <table><tbody>
    <tr><th>那天收盤</th><td>{s['close']:.2f}(還原權值,和當時報價可能不同)</td></tr>
    <tr><th>日均波動</th><td>{s['atr']:.2f}%</td></tr>
    <tr><th>買方:漲一段 / 洗盤</th><td>{lv['buy_up']:.2f}({pct(lv['buy_up'] - 100)})/ {lv['buy_dn']:.2f}({pct(lv['buy_dn'] - 100)})</td></tr>
    <tr><th>賣方:被軋 / 跌一段</th><td>{lv['sell_up']:.2f}({pct(lv['sell_up'] - 100)})/ {lv['sell_dn']:.2f}({pct(lv['sell_dn'] - 100)})</td></tr>
    <tr><th>先碰到</th><td>買方 {hitd(hb)};賣方 {hitd(hs)}</td></tr>
    <tr><th>60 天內最高 / 最低</th><td>{pct(s['hi60'][1])}(第 {s['hi60'][0]} 天)/ {pct(s['lo60'][1])}(第 {s['lo60'][0]} 天)</td></tr>
    <tr><th>20 / 60 個交易日後</th><td>{s['end20']} {pct(s['ret20'])} / {s['end60']} {pct(s['ret60'])}</td></tr>
   </tbody></table>
  </details>
 </div>
</section>""")

# 總結頁
sc = {"buy": {"對": 0, "錯": 0, "平": 0}, "sell": {"對": 0, "錯": 0, "平": 0}}
for s in S:
    for side in sc:
        sc[side][s["grade"][side]] += 1
tot = sc["buy"]["對"] + sc["sell"]["對"]; N0 = NUL["我的答案"]
assert tot == N0["合計"]["實際"] == 10
rows = "".join(f"""
  <li><a href="#p{s['n']}" data-go="{s['n'] - 1}"><span class="r-n">{s['n']}</span><span class="r-main"><span class="r-head"><b>{E(s['sym'])}</b> {s['date']}<span class="r-ret">20 天 {pct(s['ret20'])} · 60 天 {pct(s['ret60'])}</span></span>
   <span class="r-line"><span class="side">買</span>{E(s['call']['買方'].replace('還要再等,', '再等:'))} → {s['res']['buy'][0]} {badge(s['grade']['buy'])}</span>
   <span class="r-line"><span class="side">賣</span>{E(s['call']['賣方'].replace('還要再等,', '再等:'))} → {s['res']['sell'][0]} {badge(s['grade']['sell'])}</span></span></a></li>""" for s in S)
lo90, hi90 = N0["合計"]["90% 範圍"]
summary = f"""
<section class="page summary" id="p11" aria-label="總結">
 <div class="card-head"><h2>總結</h2><span class="pill">會看到全部答案</span></div>
 <p class="headline">20 句對 {tot} 句 —— 跟「圖沒有資訊」時差不多</p>
 <div class="tiles">
  <div class="tile"><span class="t-label">Claude 這次</span><span class="t-val">{tot} / 20 句</span><span class="t-sub">買方 {sc['buy']['對']} 對 {sc['buy']['錯']} 錯;賣方 {sc['sell']['對']} 對 {sc['sell']['錯']} 錯 {sc['sell']['平']} 平</span></div>
  <div class="tile"><span class="t-label">圖沒有資訊時,照我這樣答</span><span class="t-val">平均 {N0['合計']['平均']:.1f} 句</span><span class="t-sub">90% 的時候落在 {lo90}–{hi90} 句</span></div>
  <div class="tile"><span class="t-label">每張都說「兩邊都還要再等」</span><span class="t-val">{NUL['每張都說「兩邊都還要再等」在這 10 張的成績']} 句</span><span class="t-sub">等於每張都說「先不動」</span></div>
 </div>
 <div class="you-score" id="you-score" hidden></div>
 <h3>學到什麼</h3>
 <ol class="learn">
  <li><b>「兩邊都還要再等」= 先不動。</b>10 張有 8 張我這樣說。買方押「先跌」、賣方押「先漲」,方向相反,所以常常一句對、一句錯。這 8 張裡有 6 張接下來 20 天真的先跌,所以買方看起來很準(加上第 9 張共 7 / 10);但同樣這幾張,賣方押的「先漲」就錯了(3 / 10)—— 加起來就是一半。</li>
  <li><b>我只說了 2 次「買點」</b>(第 9 張 XEL 對、第 10 張 LRCX 錯),一次「賣點」都沒說。我給自己的把握只有 50–66%:我自己也覺得接近擲銅板。</li>
  <li><b>「洗盤後起漲」真的有:</b>第 2 張 ADP、第 8 張 FTNT 都是 20 天內先跌、之後大漲(60 天後 +22%、+86%)。但第 3 張 TER、第 5 張 HON 一樣先跌,之後是跌更多(−23%、−8%)。從圖上我分不出這兩種。</li>
  <li><b>有 3 張我認出大概的年份:</b>第 1、2、10 張,從大盤那條灰線看出像 2022 年中、2020 年 8 月、2023 年 2 月。我說沒有拿來用,但沒辦法完全排除;不算這 3 張,14 句對 8 句,「圖沒有資訊」時平均也有約 7.6 句。</li>
  <li><b>10 張太少。</b>就算真的有一點盤感,也要幾百張才看得出來。這次的結果和之前幾百張的大測試一致:只看價格圖,看不出接下來往哪邊。</li>
 </ol>
 <h3>10 張一覽</h3>
 <ol class="rows">{rows}
 </ol>
 <h3>怎麼確定我沒有先偷看答案</h3>
 <ul class="proof">
  <li>10/20 先把程式、對錯的定義、10 張匿名圖、抽樣結果的指紋放上 GitHub(commit <code>7d6d995</code>);抽到哪一檔、哪一天先不公開</li>
  <li>Claude(<code>claude-opus-5-5</code>)只看圖判完,答案鎖定:<code>answers.json</code> 的 SHA-256 <code>946a74f7…</code>(commit <code>b726a85</code>),之後才算對錯</li>
  <li>揭曉時 <code>hidden.json</code>(股票與日期)的 SHA-256 = <code>cf0acef7…</code>,和事先公開的一樣</li>
  <li>抽樣:固定種子 20261020,從 2016-10-20 起、之後還有 60 個交易日資料的個股日子(218,073 個)均勻抽,10 張不同股票</li>
  <li>GitHub 分支 <code>claude/intuition-practice-2026-10-15</code>,資料夾 <code>research/x10_2026-10-20/</code></li>
 </ul>
 <p class="fine">以上是練習與研究紀錄,不是投資建議。</p>
 <p><button type="button" class="btn ghost" id="reset">清掉我的猜測、重新翻</button></p>
</section>"""

DATA = {"cards": [{k: s[k] for k in ("n", "sym", "date", "ohlc", "dates", "x0", "lines", "res", "hit", "grade")} for s in S]}
data_json = json.dumps(DATA, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")

CSS = r"""
:root{color-scheme:light;--page:#f9f9f7;--card:#ffffff;--ink:#0b0b0b;--ink-2:#52514e;--ink-3:#898781;--grid:#e1e0d9;--axis:#c3c2b7;--border:rgba(11,11,11,.10);--wash:rgba(11,11,11,.05);--chip:#efeee9;--buy:#eb6834;--sell:#2a78d6;--accent:#2a78d6;--good:#0ca30c;--bad:#d03b3b;--tie:#fab219;--good-bg:rgba(12,163,12,.10);--bad-bg:rgba(208,59,59,.10);--tie-bg:rgba(250,178,25,.18);--shadow:0 1px 2px rgba(0,0,0,.04),0 6px 20px rgba(0,0,0,.05)}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;--page:#0d0d0d;--card:#1a1a19;--ink:#f0efec;--ink-2:#c3c2b7;--ink-3:#898781;--grid:#2c2c2a;--axis:#383835;--border:rgba(255,255,255,.10);--wash:rgba(255,255,255,.06);--chip:#262624;--buy:#d95926;--sell:#3987e5;--accent:#3987e5;--good-bg:rgba(12,163,12,.18);--bad-bg:rgba(208,59,59,.20);--tie-bg:rgba(250,178,25,.16);--shadow:none}}
:root[data-theme="dark"]{color-scheme:dark;--page:#0d0d0d;--card:#1a1a19;--ink:#f0efec;--ink-2:#c3c2b7;--ink-3:#898781;--grid:#2c2c2a;--axis:#383835;--border:rgba(255,255,255,.10);--wash:rgba(255,255,255,.06);--chip:#262624;--buy:#d95926;--sell:#3987e5;--accent:#3987e5;--good-bg:rgba(12,163,12,.18);--bad-bg:rgba(208,59,59,.20);--tie-bg:rgba(250,178,25,.16);--shadow:none}
*{box-sizing:border-box}
[hidden]{display:none!important}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--page);color:var(--ink);font:16px/1.65 system-ui,-apple-system,"Segoe UI","PingFang TC","Noto Sans TC","Microsoft JhengHei",sans-serif}
.wrap{max-width:860px;margin:0 auto;padding:24px max(16px,env(safe-area-inset-right,0px)) 40px max(16px,env(safe-area-inset-left,0px))}
h1{font-size:26px;line-height:1.3;margin:0 0 6px}
h2{font-size:20px;margin:0}
h3{font-size:17px;margin:22px 0 8px}
p{margin:8px 0}
code{font:13px/1.4 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;background:var(--chip);padding:1px 5px;border-radius:5px;word-break:break-all}
.lead{color:var(--ink-2);margin:6px 0 10px}
.rules{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:10px 14px;margin:14px 0}
.rules summary{cursor:pointer;font-weight:600}
.rules ul{margin:8px 0 4px;padding-left:20px;color:var(--ink-2)}
.rules li{margin:4px 0}
.toolbar{display:flex;flex-wrap:wrap;gap:10px 16px;align-items:center;justify-content:space-between;margin:16px 0 12px}
.chips{display:flex;flex-wrap:wrap;gap:6px}
.chip{min-width:34px;height:34px;padding:0 10px;border-radius:17px;border:1px solid var(--border);background:var(--card);color:var(--ink);font:inherit;font-size:14px;cursor:pointer;position:relative}
.chip[aria-current="true"]{background:var(--ink);color:var(--card);border-color:var(--ink)}
.chip.seen::after{content:"";position:absolute;top:3px;right:3px;width:6px;height:6px;border-radius:3px;background:var(--accent)}
.modes{display:inline-flex;border:1px solid var(--border);border-radius:10px;overflow:hidden;background:var(--card)}
.modes button{font:inherit;font-size:14px;padding:6px 12px;border:0;background:transparent;color:var(--ink-2);cursor:pointer}
.modes button[aria-pressed="true"]{background:var(--chip);color:var(--ink);font-weight:600}
.page{background:var(--card);border:1px solid var(--border);border-radius:16px;box-shadow:var(--shadow);padding:18px 18px 20px;margin:0 0 16px}
.card-head{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:10px}
.pill{font-size:13px;color:var(--ink-2);background:var(--chip);border-radius:999px;padding:2px 10px;white-space:nowrap}
.q{margin:0}
.zoom{display:block;width:100%;padding:6px;border:1px solid var(--border);border-radius:10px;background:#fff;cursor:zoom-in}
.zoom img{display:block;width:100%;height:auto}
.q figcaption{font-size:13px;color:var(--ink-3);margin-top:6px}
.guess{margin:14px 0 6px;padding:10px 12px;border:1px dashed var(--axis);border-radius:12px}
.guess-t{margin:0 0 6px;font-size:14px;color:var(--ink-2)}
.g-row{display:flex;align-items:center;gap:8px;margin:6px 0}
.g-side,.side{flex:none;font-size:13px;font-weight:600;color:var(--ink-2);background:var(--chip);border-radius:6px;padding:1px 7px}
.g{font:inherit;font-size:14px;padding:6px 12px;border-radius:9px;border:1px solid var(--border);background:var(--card);color:var(--ink);cursor:pointer;min-height:36px}
.g[aria-pressed="true"]{border-color:var(--ink);background:var(--chip);font-weight:600}
.claude{position:relative;margin:12px 0}
.call-t{font-size:14px;color:var(--ink-2);margin:0 0 6px}
.call{display:flex;gap:10px;align-items:flex-start;padding:8px 0;border-top:1px solid var(--border)}
.call strong{font-size:16px}
.conf{margin-left:8px;font-size:13px;color:var(--ink-3);white-space:nowrap}
.call p{margin:2px 0 0;font-size:14px;color:var(--ink-2)}
.recog{font-size:13px;color:var(--ink-3);margin:6px 0 0}
.cover{display:none}
.js .claude:not(.on) .call-body{filter:blur(7px);opacity:.55;pointer-events:none;user-select:none}
.js .claude:not(.on) .cover{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;position:absolute;inset:0;z-index:1;text-align:center}
.cover small{color:var(--ink-2);font-size:13px}
.btn{font:inherit;font-size:15px;border-radius:10px;padding:9px 16px;cursor:pointer;border:1px solid transparent;min-height:42px}
.btn.primary{background:var(--accent);color:#fff;width:100%;font-weight:600}
.btn.ghost{background:var(--card);color:var(--ink);border-color:var(--axis)}
.reveal{display:none}
.js .reveal{display:block}
.js .page.open .reveal,.js #app.mode-all .reveal{display:none}
.js .answer{display:none}
.js .page.open .answer,.js #app.mode-all .answer{display:block}
.answer{margin-top:12px;animation:fadein .35s ease}
@keyframes fadein{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
.ans-title{font-size:18px;margin:4px 0 10px}
.ans-title .sym{background:var(--ink);color:var(--card);border-radius:6px;padding:0 7px;margin-right:4px}
.ans-title .date{color:var(--ink-2);font-weight:500;margin-left:4px}
.chart{position:relative;width:100%;outline:none;border-radius:8px}
.chart:focus-visible{box-shadow:0 0 0 2px var(--accent)}
.chart svg{display:block;width:100%;touch-action:pan-y}
.tip{position:absolute;top:6px;pointer-events:none;background:var(--card);border:1px solid var(--border);border-radius:8px;padding:6px 9px;font-size:12px;line-height:1.45;box-shadow:var(--shadow);white-space:nowrap;z-index:2}
.tip .t1{color:var(--ink-3)}
.tip .t2{font-size:14px;font-weight:600;color:var(--ink)}
.tip .t3{color:var(--ink-2)}
.legend{display:flex;flex-wrap:wrap;gap:4px 14px;font-size:12px;color:var(--ink-2);margin:8px 0 4px}
.legend span{display:inline-flex;align-items:center;gap:6px}
.k-buy{stroke:var(--buy);stroke-width:2;stroke-dasharray:7 4}
.k-sell{stroke:var(--sell);stroke-width:2;stroke-dasharray:2 3}
.m-buy{fill:var(--buy);stroke:var(--card);stroke-width:2}
.m-sell{fill:var(--sell);stroke:var(--card);stroke-width:2}
.k-band{fill:var(--wash);stroke:var(--axis);stroke-width:.5}
.k-up{fill:var(--card);stroke:var(--ink-2);stroke-width:1}
.k-dn{fill:var(--ink-2);stroke:var(--ink-2);stroke-width:1}
.c-wick{stroke:var(--ink-2);stroke-width:1}
.c-up{fill:var(--card);stroke:var(--ink-2);stroke-width:1}
.c-up-thin{fill:var(--ink-3);stroke:none}
.c-dn{fill:var(--ink-2);stroke:none}
.pre{opacity:.5}
.g-line{stroke:var(--grid);stroke-width:1}
.g-base{stroke:var(--axis);stroke-width:1}
.a-text{fill:var(--ink-3);font-size:11px;font-variant-numeric:tabular-nums}
.a-text.b{fill:var(--ink-2);font-weight:600}
.band{fill:var(--wash)}
.today{stroke:var(--ink-3);stroke-width:1;stroke-dasharray:2 3}
.lv-buy{stroke:var(--buy);stroke-width:2;stroke-dasharray:7 4;fill:none}
.lv-sell{stroke:var(--sell);stroke-width:2;stroke-dasharray:2 3;fill:none}
.cross{stroke:var(--ink-3);stroke-width:1}
.verdicts{margin:10px 0}
.v{display:flex;align-items:flex-start;gap:10px;padding:8px 0;border-top:1px solid var(--border);font-size:15px}
.v>div{flex:1;min-width:0}
.badge{flex:none;display:inline-flex;align-items:center;gap:5px;font-size:14px;font-weight:600;color:var(--ink);border-radius:999px;padding:1px 10px 1px 3px;white-space:nowrap}
.badge i{font-style:normal;display:inline-grid;place-items:center;width:18px;height:18px;border-radius:9px;color:#fff;font-size:12px}
.badge.good{background:var(--good-bg)}.badge.good i{background:var(--good)}
.badge.bad{background:var(--bad-bg)}.badge.bad i{background:var(--bad)}
.badge.tie{background:var(--tie-bg)}.badge.tie i{background:var(--tie);color:#0b0b0b}
.v.you{color:var(--ink-2)}
.nums{display:flex;flex-wrap:wrap;gap:2px 14px;font-size:14px;color:var(--ink-2)}
.nums b{color:var(--ink)}
.note{font-size:15px;background:var(--chip);border-radius:10px;padding:10px 12px}
.table-view{margin-top:8px;font-size:14px}
.table-view summary{cursor:pointer;color:var(--ink-2)}
.table-view table{border-collapse:collapse;width:100%;margin-top:6px}
.table-view th,.table-view td{text-align:left;padding:5px 6px;border-top:1px solid var(--border);vertical-align:top;font-variant-numeric:tabular-nums}
.table-view th{color:var(--ink-2);font-weight:500;white-space:nowrap;width:1%}
.headline{font-size:20px;font-weight:700;margin:4px 0 12px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px}
.tile{border:1px solid var(--border);border-radius:12px;padding:12px;display:flex;flex-direction:column;gap:2px}
.t-label{font-size:13px;color:var(--ink-2)}
.t-val{font-size:24px;font-weight:600}
.t-sub{font-size:13px;color:var(--ink-3)}
.you-score{margin-top:10px;border:1px solid var(--accent);border-radius:12px;padding:10px 12px;font-size:15px}
.learn{padding-left:22px}.learn li{margin:8px 0}
.rows{list-style:none;padding:0;margin:0}
.rows a{display:flex;gap:10px;padding:10px 4px;border-top:1px solid var(--border);color:inherit;text-decoration:none}
.rows a:hover{background:var(--wash)}
.r-n{flex:none;width:24px;height:24px;border-radius:12px;background:var(--chip);display:grid;place-items:center;font-size:13px;font-weight:600}
.r-main{flex:1;min-width:0;display:flex;flex-direction:column;gap:3px}
.r-head{font-size:15px}
.r-ret{float:right;font-size:13px;color:var(--ink-2)}
.r-line{font-size:14px;color:var(--ink-2);display:flex;align-items:center;gap:6px;flex-wrap:wrap}
.proof{padding-left:20px;color:var(--ink-2);font-size:14px}.proof li{margin:6px 0}
.fine{font-size:13px;color:var(--ink-3)}
.pager{display:none}
.js #app.mode-one .pager{display:flex;position:sticky;bottom:0;z-index:5;align-items:center;justify-content:space-between;gap:10px;padding:10px 0 calc(10px + env(safe-area-inset-bottom,0px));background:linear-gradient(to bottom,transparent,var(--page) 30%)}
.pager .btn{min-width:108px}
.pager .btn:disabled{opacity:.35;cursor:default}
.pg{color:var(--ink-2);font-size:14px;font-variant-numeric:tabular-nums}
.js #app.mode-one .page{display:none}
.js #app.mode-one .page.active{display:block;animation:fadein .25s ease}
.lightbox{position:fixed;inset:0;z-index:50;background:rgba(0,0,0,.88);display:none;overflow:auto;-webkit-overflow-scrolling:touch}
.lightbox.on{display:block}
.lightbox img{display:block;width:min(1000px,max(100%,760px));max-width:none;height:auto;margin:56px auto 24px;background:#fff}
.lightbox .x{position:fixed;top:max(10px,env(safe-area-inset-top,0px));right:max(12px,env(safe-area-inset-right,0px));z-index:51;background:#fff;color:#0b0b0b;border:0;border-radius:20px;padding:6px 14px;font:inherit;font-size:15px;cursor:pointer}
@media (max-width:560px){.pager .btn{min-width:92px;min-height:38px;padding:6px 12px}h1{font-size:22px}.page{padding:14px 14px 16px;border-radius:14px}.headline{font-size:18px}.t-val{font-size:21px}.r-ret{float:none;display:block}}
@media (prefers-reduced-motion:reduce){.answer,.js #app.mode-one .page.active{animation:none}}
"""

JS = r"""
(function(){
var D=JSON.parse(document.getElementById('x10-data').textContent),C={};D.cards.forEach(function(c){C[c.n]=c});
var app=document.getElementById('app'),pages=[].slice.call(app.querySelectorAll('.page')),KEY='x10-blind-2026-10-20';
var st={mode:'one',idx:0,guess:{},shown:{},open:{}};
try{var s0=JSON.parse(localStorage.getItem(KEY)||'null');if(s0&&typeof s0==='object'){for(var k in st){if(s0[k]!==undefined)st[k]=s0[k]}}}catch(e){}
if(typeof st.idx!=='number'||st.idx<0||st.idx>=pages.length)st.idx=0;
function save(){try{localStorage.setItem(KEY,JSON.stringify(st))}catch(e){}}
var G={buy:{'買點':{'先漲一段':'對','先跌一段':'錯','都沒到':'平'},'還要再等':{'先漲一段':'錯','先跌一段':'對','都沒到':'平'}},
       sell:{'賣點':{'先跌一段':'對','先漲一段':'錯','都沒到':'平'},'還要再等':{'先跌一段':'錯','先漲一段':'對','都沒到':'平'}}};
function grade(side,call,c){return G[side][call][c.res[side][0]]}
var ICON={'對':'✓','錯':'✗','平':'–'},CLS={'對':'good','錯':'bad','平':'tie'};
function badge(g){var b=document.createElement('span');b.className='badge '+CLS[g];var i=document.createElement('i');i.setAttribute('aria-hidden','true');i.textContent=ICON[g];b.appendChild(i);b.appendChild(document.createTextNode(g));return b}
var chips=document.getElementById('chips');
pages.forEach(function(p,i){var b=document.createElement('button');b.type='button';b.className='chip';b.textContent=i<10?String(i+1):'總結';b.setAttribute('aria-label',i<10?'第 '+(i+1)+' 張':'總結');b.addEventListener('click',function(){go(i,true)});chips.appendChild(b)});
var chipEls=[].slice.call(chips.children);
function isOpen(n){return st.mode==='all'||!!st.open[n]}
function isShown(n){var g=st.guess[n]||{};return st.mode==='all'||!!st.shown[n]||!!st.open[n]||!!(g.buy&&g.sell)}
function sync(){
  app.classList.toggle('mode-one',st.mode==='one');app.classList.toggle('mode-all',st.mode==='all');
  [].forEach.call(document.querySelectorAll('.modes button'),function(b){b.setAttribute('aria-pressed',String(b.dataset.mode===st.mode))});
  pages.forEach(function(p,i){
    p.classList.toggle('active',i===st.idx);
    var n=+p.dataset.n;chipEls[i].setAttribute('aria-current',String(st.mode==='one'&&i===st.idx));
    if(!n)return;
    p.classList.toggle('open',isOpen(n));p.querySelector('.claude').classList.toggle('on',isShown(n));
    chipEls[i].classList.toggle('seen',!!st.open[n]);
    var g=st.guess[n]||{};
    [].forEach.call(p.querySelectorAll('.g'),function(b){b.setAttribute('aria-pressed',String(g[b.dataset.side]===b.dataset.v))});
    var y=p.querySelector('.v.you');y.textContent='';
    if(g.buy||g.sell){var lab=document.createElement('span');lab.className='side';lab.textContent='你';y.appendChild(lab);var d=document.createElement('div');
      var parts=[];['buy','sell'].forEach(function(sd){if(g[sd]){parts.push([sd,g[sd]])}});
      parts.forEach(function(pp,j){var t=document.createElement('span');t.textContent=(pp[0]==='buy'?'買方「':'賣方「')+pp[1]+'」 ';d.appendChild(t);d.appendChild(badge(grade(pp[0],pp[1],C[n])));if(j<parts.length-1)d.appendChild(document.createTextNode('  '))});
      y.appendChild(d);y.hidden=false}else{y.hidden=true}
  });
  var pg=document.getElementById('pg');pg.textContent=(st.idx+1)+' / '+pages.length;
  document.getElementById('prev').disabled=st.idx===0;document.getElementById('next').disabled=st.idx===pages.length-1;
  document.getElementById('next').textContent=st.idx===pages.length-2?'看總結 ›':'下一張 ›';
  youScore();drawVisible();
}
function youScore(){
  var box=document.getElementById('you-score'),cnt={buy:{'對':0,'錯':0,'平':0},sell:{'對':0,'錯':0,'平':0}},cl={'對':0,'錯':0,'平':0},m=0,ns=0;
  for(var n in st.guess){var g=st.guess[n],c=C[n];if(!c)continue;var any=false;
    ['buy','sell'].forEach(function(sd){if(g[sd]){any=true;m++;cnt[sd][grade(sd,g[sd],c)]++;cl[c.grade[sd]]++}});if(any)ns++}
  if(!m){box.hidden=true;return}
  var yr=cnt.buy['對']+cnt.sell['對'];
  box.textContent='你猜了 '+ns+' 張、'+m+' 句:對 '+yr+' 句(買方 '+cnt.buy['對']+' 對 '+cnt.buy['錯']+' 錯 '+cnt.buy['平']+' 平;賣方 '+cnt.sell['對']+' 對 '+cnt.sell['錯']+' 錯 '+cnt.sell['平']+' 平)。同樣這幾句,Claude 對 '+cl['對']+' 句。';
  box.hidden=false
}
function go(i,scroll){if(i<0||i>=pages.length)return;st.idx=i;save();if(st.mode==='all'){pages[i].scrollIntoView({behavior:'smooth',block:'start'})}else{sync();if(scroll!==false){var top=document.getElementById('deck').getBoundingClientRect().top+window.scrollY-8;if(window.scrollY>top)window.scrollTo({top:top})}}}
document.getElementById('prev').addEventListener('click',function(){go(st.idx-1)});
document.getElementById('next').addEventListener('click',function(){go(st.idx+1)});
[].forEach.call(document.querySelectorAll('.modes button'),function(b){b.addEventListener('click',function(){st.mode=b.dataset.mode;save();sync()})});
app.addEventListener('click',function(e){
  var t=e.target.closest('button,a[data-go]');if(!t)return;
  if(t.classList.contains('g')){var n=t.dataset.n;st.guess[n]=st.guess[n]||{};st.guess[n][t.dataset.side]=t.dataset.v;save();sync()}
  else if(t.classList.contains('show-call')){st.shown[t.dataset.n]=true;save();sync()}
  else if(t.classList.contains('reveal')){st.open[t.dataset.n]=true;st.shown[t.dataset.n]=true;save();sync()}
  else if(t.dataset.go!==undefined){e.preventDefault();go(+t.dataset.go)}
  else if(t.id==='reset'){st.guess={};st.shown={};st.open={};st.idx=0;save();sync();window.scrollTo({top:0})}
  else if(t.dataset.zoom){var lb=document.getElementById('lightbox');document.getElementById('lb-img').src=t.querySelector('img').src;lb.classList.add('on');lb.scrollTop=0;document.getElementById('lb-x').focus()}
});
var lb=document.getElementById('lightbox');
function closeLb(){lb.classList.remove('on')}
document.getElementById('lb-x').addEventListener('click',closeLb);
lb.addEventListener('click',function(e){if(e.target===lb)closeLb()});
document.addEventListener('keydown',function(e){
  if(lb.classList.contains('on')){if(e.key==='Escape')closeLb();return}
  if(st.mode!=='one'||e.altKey||e.ctrlKey||e.metaKey)return;
  var a=document.activeElement;if(a&&(a.closest&&a.closest('.chart')))return;
  if(e.key==='ArrowRight'){go(st.idx+1)}else if(e.key==='ArrowLeft'){go(st.idx-1)}
});
var tx=null,ty=0;
var deck=document.getElementById('deck');
deck.addEventListener('touchstart',function(e){if(e.touches.length!==1||e.target.closest('.chart,.lightbox,button,a,summary')){tx=null;return}tx=e.touches[0].clientX;ty=e.touches[0].clientY},{passive:true});
deck.addEventListener('touchend',function(e){if(tx===null||st.mode!=='one')return;var t=e.changedTouches[0],dx=t.clientX-tx,dy=t.clientY-ty;tx=null;if(Math.abs(dx)>60&&Math.abs(dx)>1.6*Math.abs(dy)){go(st.idx+(dx<0?1:-1))}},{passive:true});
var NS='http://www.w3.org/2000/svg';
function el(tag,at,par){var e=document.createElementNS(NS,tag);for(var k in at)e.setAttribute(k,at[k]);if(par)par.appendChild(e);return e}
function niceStep(r){var p=Math.pow(10,Math.floor(Math.log10(r))),c=[1,2,2.5,5,10];for(var i=0;i<c.length;i++){if(c[i]*p>=r)return c[i]*p}return 10*p}
function dayLab(t){return t>0?'第 '+t+' 天':(t===0?'那天(收盤 = 100)':'前 '+(-t)+' 天')}
function fmt(v){return v.toFixed(1)}
function pctS(v){var x=v-100;return (x>=0?'+':'−')+Math.abs(x).toFixed(1)+'%'}
function draw(host){
  var c=C[host.dataset.n],W=host.clientWidth;if(!W)return;if(host._w===W)return;host._w=W;host.textContent='';
  var H=Math.round(Math.max(220,Math.min(380,W*0.56))),m={l:34,r:8,t:12,b:24},n=c.ohlc.length,x0=c.x0,pw=W-m.l-m.r,ph=H-m.t-m.b;
  function xd(t){return m.l+((t-x0)+0.5)/n*pw}
  var lo=Infinity,hi=-Infinity;c.ohlc.forEach(function(b){if(b[2]<lo)lo=b[2];if(b[1]>hi)hi=b[1]});
  lo=Math.min(lo,c.lines.sell_dn);hi=Math.max(hi,c.lines.buy_up);var pad=(hi-lo)*0.06;lo-=pad;hi+=pad;
  function ys(v){return m.t+(hi-v)/(hi-lo)*ph}
  var svg=el('svg',{viewBox:'0 0 '+W+' '+H,width:W,height:H,'aria-hidden':'true'},host);
  el('rect',{x:xd(0.5),y:m.t,width:xd(20.5)-xd(0.5),height:ph,class:'band'},svg);
  var stp=niceStep((hi-lo)/6);
  for(var v=Math.ceil(lo/stp)*stp;v<=hi+1e-9;v+=stp){var yy=ys(v),is100=Math.abs(v-100)<1e-6;el('line',{x1:m.l,x2:W-m.r,y1:yy,y2:yy,class:is100?'g-base':'g-line'},svg);var tl=el('text',{x:m.l-5,y:yy+4,'text-anchor':'end',class:'a-text'+(is100?' b':'')},svg);tl.textContent=(stp<1?v.toFixed(1):Math.round(v))}
  [-40,-20,0,20,40,60].forEach(function(t){var x=xd(t),tt=el('text',{x:Math.min(Math.max(x,m.l+8),W-m.r-8),y:H-6,'text-anchor':t===60?'end':'middle',class:'a-text'+(t===0?' b':'')},svg);tt.textContent=t===0?'那天':(t>0?'+'+t:'−'+Math.abs(t))});
  el('line',{x1:xd(0.5),x2:xd(0.5),y1:m.t,y2:H-m.b,class:'today'},svg);
  var bw=Math.max(1,pw/n*0.64),thin=bw<3;
  c.ohlc.forEach(function(b,k){var t=x0+k,x=xd(t),o=b[0],h=b[1],l=b[2],cl=b[3],up=cl>=o;
    var pre=t<=0?' pre':'';el('line',{x1:x,x2:x,y1:ys(h),y2:ys(l),class:'c-wick'+pre},svg);
    var y1=ys(Math.max(o,cl)),hh=Math.max(1,Math.abs(ys(o)-ys(cl)));
    el('rect',{x:x-bw/2,y:y1,width:bw,height:hh,class:(up?(thin?'c-up-thin':'c-up'):'c-dn')+pre},svg)});
  [['buy_up','lv-buy'],['buy_dn','lv-buy'],['sell_up','lv-sell'],['sell_dn','lv-sell']].forEach(function(a){var y=ys(c.lines[a[0]]);el('line',{x1:xd(0.5),x2:xd(20.5),y1:y,y2:y,class:a[1]},svg)});
  if(c.hit.sell){var sx=xd(c.hit.sell.day),sy=ys(c.hit.sell.lev);el('path',{d:'M'+sx+' '+(sy-6)+' L'+(sx+6)+' '+sy+' L'+sx+' '+(sy+6)+' L'+(sx-6)+' '+sy+' Z',class:'m-sell'},svg)}
  if(c.hit.buy){el('circle',{cx:xd(c.hit.buy.day),cy:ys(c.hit.buy.lev),r:5,class:'m-buy'},svg)}
  if(xd(20.5)-xd(0.5)>=70){var bt=el('text',{x:(xd(0.5)+xd(20.5))/2,y:m.t+12,'text-anchor':'middle',class:'a-text'},svg);bt.textContent='之後 20 天'}
  var cross=el('line',{x1:0,x2:0,y1:m.t,y2:H-m.b,class:'cross',visibility:'hidden'},svg);
  var tip=document.createElement('div');tip.className='tip';tip.hidden=true;host.appendChild(tip);
  var cur=null;
  function show(k){k=Math.max(0,Math.min(n-1,k));cur=k;var t=x0+k,x=xd(t),b=c.ohlc[k];cross.setAttribute('x1',x);cross.setAttribute('x2',x);cross.setAttribute('visibility','visible');
    tip.textContent='';var a=document.createElement('div');a.className='t1';a.textContent=c.dates[k]+' · '+dayLab(t);var b2=document.createElement('div');b2.className='t2';b2.textContent='收 '+fmt(b[3])+'('+pctS(b[3])+')';var b3=document.createElement('div');b3.className='t3';b3.textContent='開 '+fmt(b[0])+' · 高 '+fmt(b[1])+' · 低 '+fmt(b[2]);tip.appendChild(a);tip.appendChild(b2);tip.appendChild(b3);tip.hidden=false;
    var tw=tip.offsetWidth,left=x+12;if(left+tw>W)left=x-12-tw;if(left<0)left=0;tip.style.left=left+'px'}
  function hide(){cross.setAttribute('visibility','hidden');tip.hidden=true;cur=null}
  function kAt(ev){var r=svg.getBoundingClientRect(),px=(ev.clientX-r.left)*(W/r.width);return Math.round((px-m.l)/pw*n-0.5)}
  svg.addEventListener('pointermove',function(ev){show(kAt(ev))});svg.addEventListener('pointerdown',function(ev){show(kAt(ev))});svg.addEventListener('pointerleave',hide);
  host.onfocus=function(){show(cur===null?-x0:cur)};host.onblur=hide;
  host.onkeydown=function(ev){if(ev.key==='ArrowRight'||ev.key==='ArrowLeft'){ev.preventDefault();ev.stopPropagation();show((cur===null?-x0:cur)+(ev.key==='ArrowRight'?1:-1))}else if(ev.key==='Escape'){host.blur()}};
}
function drawVisible(){[].forEach.call(document.querySelectorAll('.chart'),function(h){if(h.offsetParent!==null)draw(h)})}
if(window.ResizeObserver){var ro=new ResizeObserver(function(es){es.forEach(function(e){if(e.target.offsetParent!==null)draw(e.target)})});[].forEach.call(document.querySelectorAll('.chart'),function(h){ro.observe(h)})}
else{window.addEventListener('resize',drawVisible)}
sync();
})();
"""

BODY = f"""<title>十張 K 線盲判</title>
<meta name="claude:viewport-fit-sides" content="cover">
<script>document.documentElement.classList.add('js')</script>
<style>{CSS}</style>
<div id="app" class="wrap mode-one">
 <header>
  <h1>十張 K 線盲判</h1>
  <p class="lead">隨機抽過去 10 年某支股票某一天的日 K,我判斷那天是不是買點、賣點;不是的話就說「還要再等」。10 張我都先判完、把答案鎖起來(雜湊值放上 GitHub),之後才去看後來的走勢。</p>
  <p class="lead">玩法:每張先看圖(你也可以自己先猜)→ 看我怎麼判 → 翻開答案。左右滑或按下面的按鈕換張。</p>
 </header>
 <details class="rules"><summary>對錯怎麼算</summary>
  <ul>
   <li>尺 = 這檔股票自己的「日均波動」(前 20 天每天平均的高低差;這 10 張在 1.7%–4.5% 之間)。看之後 20 個交易日(大約一個月)</li>
   <li><b>買方</b>:先漲到 +2 個波動 = 漲一段;先跌到 −1.5 個波動 = 先跌(洗盤)。我說「買點」→ 要先漲一段才算對;說「還要再等(低點或加碼點還沒到)」→ 要先跌才算對</li>
   <li><b>賣方</b>:先跌到 −2 個波動 = 跌一段;先漲到 +1.5 個波動 = 被軋。我說「賣點」→ 要先跌一段才算對;說「還要再等,高點還沒到」→ 要先漲才算對</li>
   <li>20 天內兩條線都沒碰到 = 平。同一天兩條都碰到:買方算先跌、賣方算先漲(對「買點 / 賣點」比較嚴格)</li>
   <li>過去 10 年隨便一天(抽 2 萬天):買方 先漲 46% / 先跌 48% / 都沒到 6%;賣方 先跌 34% / 先漲 61% / 都沒到 5%。賣方的「被軋」線比較近,股票長期也偏漲,所以「高點還沒到」本來就比較常對</li>
  </ul>
 </details>
 <div class="toolbar">
  <div class="chips" id="chips" aria-label="跳到某一張"></div>
  <div class="modes" role="group" aria-label="顯示方式"><button type="button" data-mode="one" aria-pressed="true">一張一張翻</button><button type="button" data-mode="all" aria-pressed="false">全部攤開</button></div>
 </div>
 <main id="deck">{''.join(cards)}{summary}
 </main>
 <nav class="pager" aria-label="換張"><button type="button" class="btn ghost" id="prev">‹ 上一張</button><span class="pg" id="pg">1 / 11</span><button type="button" class="btn ghost" id="next">下一張 ›</button></nav>
</div>
<div class="lightbox" id="lightbox" role="dialog" aria-label="放大的圖"><button type="button" class="x" id="lb-x">關閉</button><img id="lb-img" alt="放大的匿名日 K 圖"></div>
<script type="application/json" id="x10-data">{data_json}</script>
<script>{JS}</script>
"""
open(OUT, "w").write(BODY)
print("寫好", OUT, round(len(BODY) / 1e6, 2), "MB")
