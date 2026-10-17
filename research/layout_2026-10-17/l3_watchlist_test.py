# l3:v18 自選清單 | K線 | 現金池 驗收(2026-10-17 使用者 5 點)
#   1. 預設網頁點開就進入完整版面        → 每次打開(含重新整理、收起之後再重新整理)都是 自選 | K線 | 現金池 三欄全開
#   2. 常看的股票留在上面、每個人自己的紀錄 → K線上方「常看」= 這台裝置看過的次數(localStorage mfd_freq);換股就記;右鍵可移除
#   3. 富途牛牛式自選清單在左邊           → 名稱/US+代號/最新價/漲跌額/漲跌幅;加入(輸入框、☆ 加自選)、刪除、置頂、拖曳、排序;點一列 K線換股
#   4. 現金池移到最右邊                   → 桌機 x 座標:自選 < K線 < 現金池
#   5. 兩邊可收起,全收只剩K線            → 收起後K線變寬;「◧ 只看K線」/「⊞ 完整版面」
#   另:舊版(v17)與新版的K線資料(traces)完全相同;自選清單的價格/漲跌與資料檔逐檔對帳;0 頁面錯誤
#   用法:python3 l3_watchlist_test.py <舊版 index.html> <新版 index.html> <快照資料夾(gist/raw 錄一次之後重播)>
import asyncio, json, os, sys, hashlib, importlib.util
HERE = os.path.dirname(os.path.abspath(__file__))
T32 = os.path.join(os.path.dirname(HERE), "requant_2026-10-10", "t32_refresh_test.py")
spec = importlib.util.spec_from_file_location("t32", T32); t32 = importlib.util.module_from_spec(spec); spec.loader.exec_module(t32)
from playwright.async_api import async_playwright

VIEWS = {"d1920": dict(viewport={"width": 1920, "height": 1080}), "d1440": dict(viewport={"width": 1440, "height": 900}),
         "m390": dict(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, device_scale_factor=2)}
IDS = ["wsxWL", "wlPane", "wsxCenter", "cockpit", "wsxLeft", "wsxCpHead", "winCard", "destCard", "wsxA", "wsxB", "wsxRail", "wsxInfoRow",
       "wsxTop", "wsxQuick", "wsxFocusBtn", "wsxMoreBtn", "wlStar", "wsxChartP"]
CAP = r"""(ids)=>{const o={};const vis=e=>{if(!e)return null;const r=e.getBoundingClientRect(),s=getComputedStyle(e);
    return {vis:!!(r.width>0&&r.height>0&&s.display!=='none'&&s.visibility!=='hidden'),x:Math.round(r.left),y:Math.round(r.top+scrollY),w:Math.round(r.width),h:Math.round(r.height)};};
  ids.forEach(id=>o[id]=vis(document.getElementById(id)));
  o.header=vis(document.querySelector('header'));
  o.stripW=vis(document.querySelector('#wsxWL .wsxStrip'));o.stripL=vis(document.querySelector('#wsxLeft .wsxStrip'));
  const qk=document.getElementById('wsxQuick'),qt=qk?qk.getBoundingClientRect().top:0;
  const chips=[...document.querySelectorAll('#wsxQuick .wsxChip')].map(c=>({s:c.textContent,on:c.classList.contains('on'),shown:c.getBoundingClientRect().top-qt<18&&c.getBoundingClientRect().width>0}));
  const rows=[...document.querySelectorAll('#wlBody .wlRow')].map(r=>({s:r.getAttribute('data-wl'),on:r.classList.contains('on'),
    n:(r.querySelector('.wlNm .n')||{}).textContent,c:(r.querySelector('.wlNm .c')||{}).textContent,
    px:((r.querySelector('.wlPx')||{}).childNodes[0]||{}).textContent,tg:(r.querySelector('.wlPx .tg')||{}).textContent||'',
    ch:(r.querySelector('.wlCh')||{}).textContent,pc:(r.querySelector('.wlPc .pill')||{}).textContent,
    cls:(r.querySelector('.wlPc .pill')||{className:''}).className.replace('pill','').trim(),title:r.title||'',drag:r.getAttribute('draggable')}));
  const ck=document.getElementById('cockpit'),T=(ck&&ck.data)||[];
  const A=v=>v==null?null:Array.from(v).map(z=>z==null?null:(typeof z==='number'?+z.toFixed(6):String(z)));
  const tr=JSON.stringify(T.map(t=>({n:t.name||'',x:A(t.x),y:A(t.y),c:A(t.close)})));
  const ls=k=>{try{return localStorage.getItem(k);}catch(_){return 'x';}};
  const dest=document.getElementById('dest');
  return {vis:o,cls:document.documentElement.className,sym:CHIP_SYM,sig:ck?(ck.dataset.sig||'').split(':')[0]:'',chips:chips,rows:rows,
    grid:getComputedStyle(document.getElementById('wsxGrid')).gridTemplateColumns,tr:tr,
    ckW:ck?Math.round(ck.getBoundingClientRect().width):0,ckH:ck?Math.round(ck.getBoundingClientRect().height):0,
    dest:!!(dest&&dest.data&&dest.getBoundingClientRect().width>0),destW:dest?Math.round(dest.getBoundingClientRect().width):0,
    btn:(document.getElementById('wsxFocusBtn')||{}).textContent,more:(document.getElementById('wsxMoreBtn')||{}).textContent,
    star:(document.getElementById('wlStar')||{}).textContent,count:(document.getElementById('wlCount')||{}).textContent,
    hdr:[...document.querySelectorAll('#wlHdr span')].map(s=>s.textContent+(s.classList.contains('s1')?'▼':s.classList.contains('s2')?'▲':'')),
    foot:(document.getElementById('wlFoot')||{}).textContent,
    ls:{wl:ls('mfd_wl'),freq:ls('mfd_freq'),sort:ls('mfd_wl_sort'),cols:ls('wsxCols'),focus:ls('mfd_focus')},
    docW:document.documentElement.scrollWidth,docH:document.documentElement.scrollHeight,scrollY:Math.round(scrollY)};}"""


def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()[:16]


async def open_pg(b, page_file, port, snap, view, ctx=None):
    site = t32.Site(page_file, port)
    r = t32.Router(snap, {}, "old")
    if ctx is None:
        ctx = await b.new_context(ignore_https_errors=True, service_workers="block", **VIEWS[view])
        await ctx.add_init_script(t32.INIT_JS)
        for h in t32.GIST_HOSTS:
            await ctx.route(f"https://{h}/**", r.handle)
    pg = await ctx.new_page(); errs = []; bad = []
    pg.on("pageerror", lambda e: errs.append(str(e)[:300]))
    pg.on("response", lambda rs: bad.append(f"{rs.status} {rs.url.split('?')[0][-70:]}") if rs.status >= 400 else None)
    await pg.goto(f"http://127.0.0.1:{port}/index.html", wait_until="domcontentloaded", timeout=120000)
    await ready(pg)
    return site, ctx, pg, errs, bad


async def ready(pg, extra=5000):
    for _ in range(150):
        if await pg.evaluate("()=>!!document.querySelector('#cockpit .plot-container')&&typeof DATA!=='undefined'&&!!DATA&&!DATA._partial"):
            break
        await pg.wait_for_timeout(1000)
    await pg.wait_for_timeout(extra)


async def wait_sym(pg, s, extra=2500):
    for _ in range(60):
        if await pg.evaluate("s=>CHIP_SYM===s&&((document.getElementById('cockpit').dataset.sig||'').split(':')[0]===s)&&!!document.querySelector('#cockpit .plot-container')", s):
            break
        await pg.wait_for_timeout(500)
    await pg.wait_for_timeout(extra)


async def cap(pg):
    return await pg.evaluate(CAP, IDS)


async def shot(pg, name, full=False):
    await pg.screenshot(path=os.path.join(HERE, f"l3_{name}.png"), full_page=full)


async def desk1920(b, old_file, new_file, snap, out):
    R = {}
    # 舊版(v17)預設畫面:NVDA K線資料當對照
    site, ctx, pg, errs, bad = await open_pg(b, old_file, 8951, snap, "d1920")
    try:
        R["old"] = await cap(pg)
        await pg.fill("#chipInput", "MU"); await pg.press("#chipInput", "Enter"); await wait_sym(pg, "MU")
        R["old_MU"] = await cap(pg)
        R["old_err"] = errs[:5]
    finally:
        await ctx.close(); site.close()
    site, ctx, pg, errs, bad = await open_pg(b, new_file, 8952, snap, "d1920")
    try:
        R["new"] = await cap(pg); await shot(pg, "d1920_default")
        # ③ 點自選列 → K線換股
        await pg.click('#wlBody [data-wl="MU"]'); await wait_sym(pg, "MU")
        R["click_MU"] = await cap(pg)
        # ③ 加入:有當日K的(ALAB)、只有日K的(A)、資料範圍外的(ZZZZQ);AMD 用建議清單第一個
        for s in ("ALAB", "A", "ZZZZQ"):
            await pg.fill("#wlIn", s); await pg.wait_for_timeout(300); await pg.press("#wlIn", "Enter"); await pg.wait_for_timeout(400)
        await pg.fill("#wlIn", "美國超微"); await pg.wait_for_timeout(400)
        R["sug_cn"] = await pg.evaluate("()=>[...document.querySelectorAll('#wlSug .it')].map(e=>e.textContent)")
        await pg.press("#wlIn", "Enter"); await pg.wait_for_timeout(9000)   # 等 ALAB/A 的日K(一次 2 檔、等主K線)
        R["added"] = await cap(pg); await shot(pg, "d1920_added")
        # 點剛加入的 ALAB → K線用自選預先抓好的日K
        await pg.click('#wlBody [data-wl="ALAB"]'); await wait_sym(pg, "ALAB")
        R["click_ALAB"] = await cap(pg)
        # ↓ 鍵換下一檔
        await pg.focus("#wlBody"); await pg.keyboard.press("ArrowDown"); await pg.wait_for_timeout(500)
        R["arrow"] = await pg.evaluate("()=>CHIP_SYM")
        # ⑤ 收起自選 → 收起現金池 → 只看K線 → 完整版面
        await pg.click('#wlPane .wsxPanBtn[data-pan="w"]'); await pg.wait_for_timeout(1500)
        R["wl_off"] = await cap(pg); await shot(pg, "d1920_wl_off")
        await pg.click('#wsxWL .wsxStrip'); await pg.wait_for_timeout(1500)
        R["wl_on"] = await cap(pg)
        await pg.click('#wsxCpHead .wsxPanBtn[data-pan="l"]'); await pg.wait_for_timeout(1500)
        R["cp_off"] = await cap(pg)
        await pg.click('#wsxLeft .wsxStrip'); await pg.wait_for_timeout(1500)
        R["cp_on"] = await cap(pg)
        await pg.click("#wsxFocusBtn"); await pg.wait_for_timeout(1800)
        R["k_only"] = await cap(pg); await shot(pg, "d1920_k_only")
        await pg.click("#wsxFocusBtn"); await pg.wait_for_timeout(1800)
        R["full_again"] = await cap(pg)
        # 排序:漲跌幅 ▼ → ▲ → 自訂
        await pg.click('#wlHdr [data-wlsort="pc"]'); await pg.wait_for_timeout(400); R["sort1"] = await cap(pg)
        await pg.click('#wlHdr [data-wlsort="pc"]'); await pg.wait_for_timeout(400); R["sort2"] = await cap(pg)
        await pg.click('#wlHdr [data-wlsort="pc"]'); await pg.wait_for_timeout(400); R["sort0"] = await cap(pg)
        # 拖曳排序:QQQ 拖到最上面
        await pg.drag_and_drop('#wlBody [data-wl="QQQ"]', '#wlBody .wlRow:first-child', target_position={"x": 60, "y": 4})
        await pg.wait_for_timeout(600); R["dragged"] = await cap(pg)
        # 編輯:刪 ZZZZQ、置頂 WDC
        await pg.click("#wlEditBtn"); await pg.wait_for_timeout(300)
        R["edit"] = await cap(pg); await shot(pg, "d1920_edit")
        await pg.click('#wlBody [data-wldel="ZZZZQ"]'); await pg.wait_for_timeout(300)
        await pg.click('#wlBody [data-wltop="WDC"]'); await pg.wait_for_timeout(300)
        await pg.click("#wlEditBtn"); await pg.wait_for_timeout(300)
        R["edited"] = await cap(pg)
        # 右鍵:自選列選單、常看移除
        await pg.click('#wlBody [data-wl="SNDK"]', button="right"); await pg.wait_for_timeout(300)
        R["menu_row"] = await pg.evaluate("()=>{const m=document.getElementById('wlMenu');return m&&m.style.display==='block'?m.innerText:null;}")
        await pg.keyboard.press("Escape"); await pg.wait_for_timeout(200)
        await pg.click('#wsxQuick [data-wsxsym="SMH"]', button="right"); await pg.wait_for_timeout(300)
        R["menu_chip"] = await pg.evaluate("()=>{const m=document.getElementById('wlMenu');return m&&m.style.display==='block'?m.innerText:null;}")
        await pg.click('#wlMenu [data-m="qhide"]'); await pg.wait_for_timeout(500)
        R["chip_hidden"] = await cap(pg)
        # ☆ 加自選:K線換到不在清單的 INTC → 按 ☆
        await pg.fill("#chipInput", "INTC"); await pg.press("#chipInput", "Enter"); await wait_sym(pg, "INTC", 1500)
        R["star_before"] = await pg.evaluate("()=>document.getElementById('wlStar').textContent")
        await pg.click("#wlStar"); await pg.wait_for_timeout(500)
        R["star_after"] = await cap(pg)
        # 分隔線拖曳:自選 +60、現金池 +50(往左拉)
        sw = await pg.evaluate("()=>{const r=document.querySelector('#wsxGrid>.wsxSplit[data-ws=\"W\"]').getBoundingClientRect();return [r.left+r.width/2,r.top+200];}")
        await pg.mouse.move(sw[0], sw[1]); await pg.mouse.down(); await pg.mouse.move(sw[0] + 60, sw[1], steps=6); await pg.mouse.up(); await pg.wait_for_timeout(600)
        sl = await pg.evaluate("()=>{const r=document.querySelector('#wsxGrid>.wsxSplit[data-ws=\"L\"]').getBoundingClientRect();return [r.left+r.width/2,r.top+200];}")
        await pg.mouse.move(sl[0], sl[1]); await pg.mouse.down(); await pg.mouse.move(sl[0] - 50, sl[1], steps=6); await pg.mouse.up(); await pg.wait_for_timeout(800)
        R["resized"] = await cap(pg)
        # 其他欄位(1920 放得下 → 不自動收)
        await pg.click("#wsxMoreBtn"); await pg.wait_for_timeout(2500)
        R["others"] = await cap(pg); await shot(pg, "d1920_others")
        await pg.click("#wsxMoreBtn"); await pg.wait_for_timeout(1800)
        R["others_off"] = await cap(pg)
        # ① 收起 → 重新整理 → 仍是完整版面;清單/常看/欄寬都留著
        await pg.click("#wsxFocusBtn"); await pg.wait_for_timeout(800)
        await pg.reload(wait_until="domcontentloaded"); await ready(pg)
        R["reload"] = await cap(pg); await shot(pg, "d1920_reload")
        R["errors"] = errs[:8]; R["bad"] = bad[:20]
    finally:
        await ctx.close(); site.close()
    out["d1920"] = R


async def desk1440(b, old_file, new_file, snap, out):
    R = {}
    site, ctx, pg, errs, bad = await open_pg(b, old_file, 8953, snap, "d1440")
    try:
        R["old"] = await cap(pg)
    finally:
        await ctx.close(); site.close()
    site, ctx, pg, errs, bad = await open_pg(b, new_file, 8954, snap, "d1440")
    try:
        R["new"] = await cap(pg); await shot(pg, "d1440_default")
        await pg.click("#wsxMoreBtn"); await pg.wait_for_timeout(2500)
        R["others"] = await cap(pg); await shot(pg, "d1440_others")
        await pg.click("#wsxMoreBtn"); await pg.wait_for_timeout(1800)
        R["others_off"] = await cap(pg)
        R["errors"] = errs[:8]; R["bad"] = bad[:20]
    finally:
        await ctx.close(); site.close()
    out["d1440"] = R


async def mobile(b, old_file, new_file, snap, out):
    R = {}
    site, ctx, pg, errs, bad = await open_pg(b, old_file, 8955, snap, "m390")
    try:
        R["old"] = await cap(pg)
    finally:
        await ctx.close(); site.close()
    site, ctx, pg, errs, bad = await open_pg(b, new_file, 8956, snap, "m390")
    try:
        R["new"] = await cap(pg); await shot(pg, "m390_default", full=True)
        await pg.evaluate("()=>document.getElementById('wsxWL').scrollIntoView()"); await pg.wait_for_timeout(500)
        await shot(pg, "m390_watchlist")
        await pg.tap('#wlBody [data-wl="AVGO"]'); await wait_sym(pg, "AVGO")
        R["tap"] = await cap(pg); await shot(pg, "m390_after_tap")
        await pg.tap('#wlPane .wsxPanBtn[data-pan="w"]'); await pg.wait_for_timeout(800)
        R["wl_off"] = await cap(pg)
        await pg.tap('#wlPane .wsxPanBtn[data-pan="w"]'); await pg.wait_for_timeout(800)
        R["wl_on"] = await cap(pg)
        await pg.tap("#wlEditBtn"); await pg.wait_for_timeout(300)
        R["edit"] = await cap(pg)
        R["errors"] = errs[:8]; R["bad"] = bad[:20]
    finally:
        await ctx.close(); site.close()
    out["m390"] = R


def expect_rows(snap, syms):
    """自選清單逐檔對帳(獨立用 Python 從同一份快照算):① 追蹤清單 last/走勢倒數第二根;② 當日K + 日K檔前一根;③ 只有日K → 最後兩根"""
    md = json.load(open(os.path.join(snap, "market_data.json")))
    out = {}
    for s in syms:
        q = None
        for k in ("stocks", "market", "leveraged", "crypto"):
            if s in (md.get(k) or {}):
                q = md[k][s]; break
        e = {"last": None, "prev": None, "src": None}
        if q:
            e["last"] = q["last"]; sp = q.get("spark") or []
            e["prev"] = sp[-2] if len(sp) >= 2 and abs(sp[-1] - q["last"]) < 1e-6 * max(1, abs(q["last"])) else (q["last"] / (1 + q["chg1d"] / 100) if q.get("chg1d") is not None else None)
            e["src"] = "quote"
        elif s in (md.get("kline_today") or {}):
            kt = md["kline_today"][s]; e["last"] = kt[4]; e["src"] = "kline_today"
            p = os.path.join(snap, f"kline_{s}.json")
            if os.path.exists(p):
                bars = [b for b in json.load(open(p))["bars"] if str(b[0]) < kt[0]]
                e["prev"] = bars[-1][4] if bars else None
        else:
            for p in (os.path.join(snap, f"kline_{s}.json"), os.path.join(snap, f"{s}.json")):
                if os.path.exists(p):
                    bars = json.load(open(p))["bars"]; e["last"] = bars[-1][4]; e["prev"] = bars[-2][4]; e["d"] = bars[-1][0]; e["src"] = os.path.basename(p); break
        if e["last"] is not None and e["prev"]:
            e["chg"] = e["last"] - e["prev"]; e["pct"] = (e["last"] / e["prev"] - 1) * 100
        out[s] = e
    return out


def fmt_num(v):
    a = abs(v); n = 2 if a >= 1 else (3 if a >= 0.1 else 4)
    return f"{a:,.2f}" if a >= 1000 else f"{a:.{n}f}"


def check_rows(rows, exp):
    bad = []
    for r in rows:
        e = exp.get(r["s"])
        if not e or e["last"] is None:
            if r["px"] != "—": bad.append((r["s"], "應為 —", r["px"]))
            continue
        want_px = fmt_num(e["last"])
        if r["px"].replace("-", "") != want_px: bad.append((r["s"], "價", r["px"], want_px))
        if e.get("pct") is not None:
            want_pc = f"{abs(e['pct']):.2f}%"
            if r["pc"].lstrip("+-") != want_pc: bad.append((r["s"], "幅", r["pc"], want_pc))
            want_ch = fmt_num(e["chg"]) if abs(e["chg"]) >= 1000 else f"{abs(e['chg']):.{2 if abs(e['last']) >= 1 else 3 if abs(e['last']) >= .1 else 4}f}"
            if r["ch"].lstrip("+-") != want_ch: bad.append((r["s"], "額", r["ch"], want_ch))
            sgn = "up" if round(e["pct"], 2) > 0 else "dn" if round(e["pct"], 2) < 0 else "fl"
            if r["cls"] != sgn: bad.append((r["s"], "色", r["cls"], sgn))
        if e["src"] not in ("quote", "kline_today") and not r["tg"].startswith("收盤"): bad.append((r["s"], "應標收盤", r["tg"]))
    return bad


def summarize(out, snap):
    L = []
    p = lambda *a: L.append(" ".join(str(x) for x in a))
    D = out["d1920"]; n = D["new"]; v = n["vis"]
    p("=== 桌機 1920 ===  頁面錯誤", D["errors"], "| HTTP≥400", [x for x in D["bad"] if ".gz64" not in x])
    p("① 預設:", "html class =", n["cls"], "| 欄寬", n["grid"])
    p("   看得到:", [k for k in v if v[k] and v[k]["vis"]])
    p("   看不到:", [k for k in v if v[k] and not v[k]["vis"]])
    p("④ 左→右 x:", "自選", v["wsxWL"]["x"], "< K線", v["wsxCenter"]["x"], "< 現金池", v["wsxLeft"]["x"], "=", v["wsxWL"]["x"] < v["wsxCenter"]["x"] < v["wsxLeft"]["x"],
      f"| K線 {D['old']['ckW']}×{D['old']['ckH']}(v17)→ {n['ckW']}×{n['ckH']} | 現金池圖 {n['dest']} 寬 {n['destW']}")
    p("   K線資料新舊相同(NVDA 預設) =", sha(D["old"]["tr"]) == sha(n["tr"]), "| 點自選 MU 與舊版輸入 MU 相同 =", sha(D["old_MU"]["tr"]) == sha(D["click_MU"]["tr"]), "sym", D["click_MU"]["sym"])
    p("③ 預設清單:", [(r["s"], r["n"], r["px"], r["ch"], r["pc"]) for r in n["rows"]])
    exp = expect_rows(snap, [r["s"] for r in D["added"]["rows"]])
    p("   逐檔對帳(加入後):", "不符 =", check_rows(D["added"]["rows"], exp) or "無")
    p("   加入後:", [(r["s"], r["n"], r["px"], r["tg"], r["ch"], r["pc"], r["title"][:30]) for r in D["added"]["rows"]])
    p("   中文搜尋「美國超微」建議 =", D["sug_cn"])
    p("   點 ALAB → K線", D["click_ALAB"]["sym"], D["click_ALAB"]["sig"], "| ↓ 鍵 →", D["arrow"])
    for k in ("wl_off", "wl_on", "cp_off", "cp_on", "k_only", "full_again"):
        x = D[k]
        p(f"⑤ {k:10s} class={x['cls']:<26s} 欄={x['grid']:<34s} K線寬 {x['ckW']} 自選條 {x['vis']['stripW']['vis']} 現金池條 {x['vis']['stripL']['vis']} 鈕「{x['btn']}」")
    for k in ("sort1", "sort2", "sort0"):
        p(f"   排序 {k}: 標題 {D[k]['hdr']} 順序 {[r['s']+' '+r['pc'] for r in D[k]['rows']]}")
    p("   拖曳 QQQ 到最上 →", [r["s"] for r in D["dragged"]["rows"]][:4], "| 編輯欄", D["edit"]["hdr"], "| 刪 ZZZZQ + 置頂 WDC →", [r["s"] for r in D["edited"]["rows"]])
    p("   右鍵(自選列) =", repr(D["menu_row"]), "| 右鍵(常看) =", repr(D["menu_chip"]), "| 移除 SMH 後常看 =", [c["s"] for c in D["chip_hidden"]["chips"]])
    p("   ☆:INTC 按之前「", D["star_before"], "」→ 之後「", D["star_after"]["star"], "」清單第一個 =", D["star_after"]["rows"][0]["s"])
    p("   分隔線拖曳後 wsxCols =", D["resized"]["ls"]["cols"], "| 欄寬", D["resized"]["grid"])
    o = D["others"]
    p("   其他欄位(1920):class", o["cls"], "| 欄", o["grid"], "| 看得到 header/A/B/rail =", [o["vis"][k]["vis"] if o["vis"].get(k) else None for k in ("header", "wsxA", "wsxB", "wsxRail")], "| 鈕", o["more"], "| docW", o["docW"])
    p("   關掉其他欄位 → class", D["others_off"]["cls"], "欄", D["others_off"]["grid"])
    r = D["reload"]
    p("① 收起後重新整理 → class", r["cls"], "| 欄", r["grid"], "| 鈕", r["btn"], "| mfd_focus =", r["ls"]["focus"])
    p("② 重新整理後常看 =", [c["s"] + ("" if c["shown"] else "(放不下)") for c in r["chips"]], "| 清單 =", [x["s"] for x in r["rows"]])
    p("   mfd_freq =", r["ls"]["freq"])
    D2 = out["d1440"]; n2 = D2["new"]
    p("=== 桌機 1440 === 錯誤", D2["errors"], "| HTTP≥400", [x for x in D2["bad"] if ".gz64" not in x])
    p("   預設:欄", n2["grid"], f"| K線 {D2['old']['ckW']}×{D2['old']['ckH']}(v17)→ {n2['ckW']}×{n2['ckH']}", "| 常看放得下", sum(1 for c in n2["chips"] if c["shown"]), "/", len(n2["chips"]),
      "| K線資料新舊相同 =", sha(D2["old"]["tr"]) == sha(n2["tr"]))
    p("   其他欄位:class", D2["others"]["cls"], "欄", D2["others"]["grid"], "docW", D2["others"]["docW"], "→ 關掉:", D2["others_off"]["cls"], D2["others_off"]["grid"])
    M = out["m390"]; m = M["new"]; mv = m["vis"]
    p("=== 手機 390 === 錯誤", M["errors"], "| HTTP≥400", [x for x in M["bad"] if ".gz64" not in x])
    p("   上→下 y:K線", mv["wsxChartP"]["y"], "< 自選", mv["wsxWL"]["y"], "< 現金池", mv["wsxLeft"]["y"], "=", mv["wsxChartP"]["y"] < mv["wsxWL"]["y"] < mv["wsxLeft"]["y"],
      f"| 整頁高 {M['old']['docH']}(v17)→ {m['docH']} | docW {m['docW']} | K線資料新舊相同 =", sha(M["old"]["tr"]) == sha(m["tr"]))
    p("   點 AVGO → K線", M["tap"]["sym"], "| 捲到K線(scrollY)", M["tap"]["scrollY"], "≈ K線 y", M["tap"]["vis"]["wsxChartP"]["y"])
    p("   收起自選(標題列留著):列數", len(M["wl_off"]["rows"]), "清單本體看得到", M["wl_off"]["vis"]["wlPane"]["h"], "→ 展開 列", len(M["wl_on"]["rows"]), "| 編輯模式欄", M["edit"]["hdr"])
    return "\n".join(L)


async def main(old_file, new_file, snap):
    out = {}
    async with async_playwright() as pw:
        b = await pw.chromium.launch(args=["--ignore-certificate-errors", "--proxy-server=" + os.environ.get("HTTPS_PROXY", ""), "--proxy-bypass-list=127.0.0.1;localhost"])
        await desk1920(b, old_file, new_file, snap, out)
        await desk1440(b, old_file, new_file, snap, out)
        await mobile(b, old_file, new_file, snap, out)
        await b.close()
    out["_files"] = {k: {"path": f, "sha256": hashlib.sha256(open(f, "rb").read()).hexdigest()} for k, f in (("old", old_file), ("new", new_file))}
    txt = summarize(out, snap)
    slim = json.loads(json.dumps(out))
    for v in ("d1920", "d1440", "m390"):
        for k, x in slim[v].items():
            if isinstance(x, dict) and "tr" in x:
                x["tr_sha"] = sha(x.pop("tr"))
    json.dump(slim, open(os.path.join(HERE, "l3_watchlist_test.json"), "w"), ensure_ascii=False, indent=1)
    open(os.path.join(HERE, "l3_watchlist_test.log"), "w").write(txt + "\n")
    print(txt)


if __name__ == "__main__":
    asyncio.run(main(*sys.argv[1:4]))
