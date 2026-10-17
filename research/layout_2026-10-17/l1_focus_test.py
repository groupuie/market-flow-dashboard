# l1:v17 精簡版面驗收(2026-10-17 使用者:「這些欄位我都想隱藏…我會看的只有K線還有現金池」)
#   舊版 = 第一個參數、新版 = 第二個參數;本機伺服器;gist/raw 檔用固定快照重播(第一次跑時從網路錄下,之後重播)
#   ① 桌機 1920×1080、1440×900、手機 390×844:新版預設(精簡)哪些欄位看得到 / 看不到;K線、現金池圖還在;0 錯誤
#   ② 新版按「⊞ 完整版面」→ 每個欄位的看得到/看不到 與 舊版完全相同;重新整理後記住(localStorage mfd_focus)
#   ③ 新舊版K線 traces(資料)完全相同(只差寬高)
#   ④ 警示鈕:快照 A(Mac 剛恢復、報價卡住)→「⚠ 報價暫用雲端備援」;快照 C(Mac 離線、備援也舊、盤中)→「⚠ 資料偏舊 …」
#   用法:python3 l1_focus_test.py <舊版 index.html> <新版 index.html> <即時快照資料夾(會錄)> <快照根目錄(內含 snapA/snapC)>
import asyncio, json, os, sys, hashlib, importlib.util, datetime as dt
HERE = os.path.dirname(os.path.abspath(__file__))
T32 = os.path.join(os.path.dirname(HERE), "requant_2026-10-10", "t32_refresh_test.py")
spec = importlib.util.spec_from_file_location("t32", T32); t32 = importlib.util.module_from_spec(spec); spec.loader.exec_module(t32)
from playwright.async_api import async_playwright
IDS = ["header", "wsxLeft", "winCard", "destCard", "wsxCenter", "wsxChartP", "cockpit", "wsxInfoRow", "wsxA", "wsxB", "wsxRail", "wsxTop", "wsxFocusBtn", "wsxWarn", "footnote"]
VIS = r"""(ids)=>{const q=id=>id==='header'?document.querySelector('header'):(id==='footnote'?document.querySelector('.wrap>.note'):document.getElementById(id));
  const o={};ids.forEach(id=>{const e=q(id);if(!e){o[id]=null;return;}const r=e.getBoundingClientRect(),s=getComputedStyle(e);
    o[id]={vis:!!(r.width>0&&r.height>0&&s.display!=='none'&&s.visibility!=='hidden'),x:Math.round(r.left),y:Math.round(r.top+scrollY),w:Math.round(r.width),h:Math.round(r.height)};});
  const ck=document.getElementById('cockpit'),T=(ck&&ck.data)||[];
  const A=v=>v==null?null:Array.from(v).map(z=>z==null?null:(typeof z==='number'?+z.toFixed(6):String(z)));
  const tr=JSON.stringify(T.map(t=>({n:t.name||'',x:A(t.x),y:A(t.y),c:A(t.close)})));
  const dest=document.getElementById('dest');
  return {vis:o,focus:document.documentElement.classList.contains('wsxFocus'),btn:(document.getElementById('wsxFocusBtn')||{}).textContent||null,
    warn:(()=>{const w=document.getElementById('wsxWarn');return w&&w.style.display!=='none'?{txt:w.textContent,cls:w.className,title:w.title}:null;})(),
    tr:tr,ckH:ck?ck.getBoundingClientRect().height:0,ckW:ck?ck.getBoundingClientRect().width:0,dest:!!(dest&&dest.data&&dest.getBoundingClientRect().width>0),
    docH:document.documentElement.scrollHeight,docW:document.documentElement.scrollWidth,ls:(()=>{try{return localStorage.getItem('mfd_focus');}catch(_){return 'x';}})()};}"""
VIEWS = {"d1920": dict(viewport={"width": 1920, "height": 1080}), "d1440": dict(viewport={"width": 1440, "height": 900}),
         "m390": dict(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, device_scale_factor=2)}


async def open_pg(b, page_file, port, snap, view, when=None):
    site = t32.Site(page_file, port)
    r = t32.Router(snap, {}, "old")
    ctx = await b.new_context(ignore_https_errors=True, service_workers="block", **VIEWS[view])
    await ctx.add_init_script(t32.INIT_JS)
    if when:
        off = int((dt.datetime.fromisoformat(when.replace("Z", "+00:00")).timestamp() - dt.datetime.now(dt.timezone.utc).timestamp()) * 1000)
        await ctx.add_init_script("window.__t32.setOff(%d);" % off)
    for h in t32.GIST_HOSTS:
        await ctx.route(f"https://{h}/**", r.handle)
    pg = await ctx.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
    await pg.goto(f"http://127.0.0.1:{port}/index.html", wait_until="domcontentloaded", timeout=120000)
    for _ in range(150):
        if await pg.evaluate("()=>!!document.querySelector('#cockpit .plot-container')&&typeof DATA!=='undefined'&&!!DATA&&!DATA._partial"): break
        await pg.wait_for_timeout(1000)
    await pg.wait_for_timeout(5000)
    return site, ctx, pg, errs


async def layout_case(b, old_file, new_file, snap, view, port, out):
    res = {}
    for tag, f in (("old", old_file), ("new", new_file)):
        site, ctx, pg, errs = await open_pg(b, f, port + (0 if tag == "old" else 1), snap, view)
        try:
            res[tag] = await pg.evaluate(VIS, IDS)
            await pg.screenshot(path=os.path.join(HERE, f"l1_{view}_{tag}.png"))
            if tag == "new":
                await pg.click("#wsxFocusBtn"); await pg.wait_for_timeout(2500)
                res["new_full"] = await pg.evaluate(VIS, IDS)
                await pg.screenshot(path=os.path.join(HERE, f"l1_{view}_new_full.png"))
                await pg.reload(wait_until="domcontentloaded")
                for _ in range(120):
                    if await pg.evaluate("()=>!!document.querySelector('#cockpit .plot-container')&&typeof DATA!=='undefined'&&!!DATA&&!DATA._partial"): break
                    await pg.wait_for_timeout(1000)
                await pg.wait_for_timeout(4000)
                res["new_full_reload"] = await pg.evaluate(VIS, IDS)
                await pg.click("#wsxFocusBtn"); await pg.wait_for_timeout(2500)
                res["new_back"] = await pg.evaluate(VIS, IDS)
            res[tag + "_errors"] = errs[:5]
        finally:
            await ctx.close(); site.close()
    out[view] = res


async def warn_case(b, new_file, snap, when, port, tag, out):
    site, ctx, pg, errs = await open_pg(b, new_file, port, snap, "d1920", when)
    try:
        r = await pg.evaluate(VIS, IDS)
        await pg.click("#wsxWarn") if r["warn"] else None
        await pg.wait_for_timeout(600)
        r2 = await pg.evaluate("()=>{const w=document.getElementById('wsxWarn');return w?w.textContent:null;}")
        out["warn_" + tag] = {"warn": r["warn"], "expanded": r2, "errors": errs[:5]}
        await pg.screenshot(path=os.path.join(HERE, f"l1_warn_{tag}.png"), clip={"x": 0, "y": 0, "width": 1920, "height": 140})
    finally:
        await ctx.close(); site.close()


def summarize(out):
    def vis(d): return {k: (v["vis"] if v else None) for k, v in d["vis"].items()}
    for view in VIEWS:
        R = out[view]; o, n, nf, nr, nb = R["old"], R["new"], R["new_full"], R["new_full_reload"], R["new_back"]
        print(f"=== {view}:錯誤 舊 {R['old_errors']} 新 {R['new_errors']}")
        print("  新版預設(精簡):看得到 =", [k for k, v in vis(n).items() if v], "| 看不到 =", [k for k, v in vis(n).items() if v is False])
        print(f"  K線 寬×高 舊 {o['ckW']:.0f}×{o['ckH']:.0f} → 新 {n['ckW']:.0f}×{n['ckH']:.0f};現金池圖 舊 {o['dest']} 新 {n['dest']};按鈕「{n['btn']}」;focus={n['focus']}")
        same_full = {k: (vis(o)[k], vis(nf)[k]) for k in IDS if k not in ("wsxFocusBtn", "wsxWarn") and vis(o)[k] != vis(nf)[k]}
        print("  按「完整版面」後與舊版不同的欄位 =", same_full or "無(完全相同)", f"| 按鈕「{nf['btn']}」 localStorage={nf['ls']}")
        print("  重新整理後記住完整版面 =", (not nr["focus"]) and vis(nr) == vis(nf), "| 再按回精簡 =", nb["focus"] and vis(nb) == vis(n), f"localStorage={nb['ls']}")
        print("  K線資料 traces 新舊相同 =", hashlib.sha256(o["tr"].encode()).hexdigest() == hashlib.sha256(n["tr"].encode()).hexdigest(),
              "| 完整版面時也相同 =", hashlib.sha256(o["tr"].encode()).hexdigest() == hashlib.sha256(nf["tr"].encode()).hexdigest())
    for k in ("warn_A", "warn_C"):
        print(k, out[k])


async def main(old_file, new_file, live_snap, root):
    out = {}
    os.makedirs(live_snap, exist_ok=True)
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--ignore-certificate-errors", "--proxy-server=" + os.environ.get("HTTPS_PROXY", ""), "--proxy-bypass-list=127.0.0.1;localhost"])
        port = 8871
        for view in VIEWS:
            await layout_case(b, old_file, new_file, live_snap, view, port, out); port += 2
        await warn_case(b, new_file, os.path.join(root, "snapA"), "2026-10-15T23:50:00Z", port, "A", out); port += 1
        await warn_case(b, new_file, os.path.join(root, "snapC"), "2026-10-15T19:00:00Z", port, "C", out)
        await b.close()
    out["_files"] = {k: {"path": f, "sha256": hashlib.sha256(open(f, "rb").read()).hexdigest()} for k, f in (("old", old_file), ("new", new_file))}
    slim = json.loads(json.dumps(out))
    for v in VIEWS:
        for k in ("old", "new", "new_full", "new_full_reload", "new_back"):
            slim[v][k]["tr_sha"] = hashlib.sha256(slim[v][k].pop("tr").encode()).hexdigest()[:16]
    json.dump(slim, open(os.path.join(HERE, "l1_focus_test.json"), "w"), ensure_ascii=False, indent=1)
    summarize(out)


if __name__ == "__main__":
    asyncio.run(main(*sys.argv[1:5]))
