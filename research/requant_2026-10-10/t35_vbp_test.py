# t35:VbP 改版驗收(2026-10-12 使用者:「vbp 做成跟 TrendSpider 一樣:不壓縮K線圖、右側半透明灰、比較細、在K線圖下一層」)
#   舊版 8f8e00c(BUILD 02:45Z)vs 新版;本機伺服器、固定回應(t32 快照);桌機 1920 寬 + 手機 390 寬
#   ① VbP 關:13 檔 × 100 日,traces / shapes / annotations 新舊版完全相同(改版不能動到任何沒開 VbP 的畫面)
#   ② VbP 開:traces(K棒、所有訊號層)新舊版完全相同;x 軸 domain 舊版 [0,0.845] → 新版 [0,1](不壓縮);
#      VbP shapes 全部 xref paper、x1=1(貼右緣)、layer below、只有兩種顏色(灰 / POC 琥珀);箱數 = vbpRows;POC 標籤 1 個
#   ③ 縮放重分箱:relayout xaxis.range 到後半段 → VbP shapes 換成可視範圍的分箱、POC 標籤跟著動、其他 shapes 原封不動
#   用法:python3 t35_vbp_test.py <舊版 index.html> <新版 index.html> <快照資料夾>
import asyncio, json, os, sys, importlib.util
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("t32", os.path.join(HERE, "t32_refresh_test.py")); t32 = importlib.util.module_from_spec(spec); spec.loader.exec_module(t32)
from playwright.async_api import async_playwright
SYMS = t32.SYMS13
CAP = r"""()=>{const el=document.getElementById('cockpit');const L=el.layout||{};const T=el.data||[];
  const A=v=>v==null?null:Array.from(v).map(z=>z==null?null:(typeof z==='number'?+z.toFixed(6):String(z)));
  const traces=T.map(t=>({name:t.name||'',type:t.type||'',x:A(t.x),y:A(t.y),o:A(t.open),h:A(t.high),l:A(t.low),c:A(t.close),text:Array.isArray(t.text)?A(t.text):(t.text==null?null:String(t.text))}));
  const sh=(L.shapes||[]).map(s=>JSON.stringify(s)); const an=(L.annotations||[]).map(a=>JSON.stringify(a));
  const vb=(L.shapes||[]).filter(s=>s.xref==='paper'&&s.yref==='y'&&s.layer==='below'&&s.x1===1&&s.type==='rect');
  const cols={};vb.forEach(s=>{cols[s.fillcolor]=(cols[s.fillcolor]||0)+1;});
  const poc=(L.annotations||[]).filter(a=>/^POC /.test(a.text||'')).map(a=>({text:a.text,x:+a.x.toFixed(4),y:+a.y.toFixed(4)}));
  return {build:BUILD,sym:CHIP_SYM,vbpOn:CHIP_VBP,xdom:L.xaxis&&L.xaxis.domain,traces:traces,shapes:sh,ann:an,
    vbp:{n:vb.length,cols:cols,maxW:+Math.max(0,...vb.map(s=>1-s.x0)).toFixed(4),minH:+Math.min(1e9,...vb.map(s=>s.y1-s.y0)).toFixed(4)},poc:poc,
    NB:(el._vbp||{}).NB,otherShapes:sh.filter(s=>!(JSON.parse(s).x1===1&&JSON.parse(s).yref==='y'&&JSON.parse(s).layer==='below'))};}"""


async def run(browser, site, snap, tag, mobile, out):
    r = t32.Router(snap, {}, "old")
    kw = dict(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, device_scale_factor=2) if mobile else dict(viewport={"width": 1920, "height": 1080})
    ctx = await browser.new_context(ignore_https_errors=True, service_workers="block", **kw)
    await ctx.add_init_script(t32.INIT_JS)
    for h in t32.GIST_HOSTS:
        await ctx.route(f"https://{h}/**", r.handle)
    pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.goto(f"http://127.0.0.1:{site.port}/index.html", wait_until="domcontentloaded", timeout=120000)
    for _ in range(180):
        if await pg.evaluate("()=>!!document.querySelector('#cockpit .plot-container')&&typeof FCL!=='undefined'&&!!FCL&&!!EXTDF&&Object.keys(chipDaily()).length>=250"): break
        await pg.wait_for_timeout(1000)
    res = {"off": {}, "on": {}, "zoom": {}}
    try:
        await pg.evaluate("()=>{CHIP_WIN=100;CHIP_VBP=false;renderChips();}"); await pg.wait_for_timeout(1500)
        for s in SYMS:
            await t32.select_sym(pg, s); await pg.evaluate("()=>{CHIP_WIN=100;renderChips();}"); await pg.wait_for_timeout(2000)
            res["off"][s] = await pg.evaluate(CAP)
        await pg.click(".cidxchip3"); await pg.wait_for_timeout(2000)   # 像使用者一樣按 VbP 鈕
        for s in SYMS:
            await t32.select_sym(pg, s); await pg.evaluate("()=>{CHIP_WIN=100;renderChips();}"); await pg.wait_for_timeout(2000)
            res["on"][s] = await pg.evaluate(CAP)
        # ③ 縮放:看最後 40 根
        await t32.select_sym(pg, "NVDA"); await pg.evaluate("()=>{CHIP_WIN=100;renderChips();}"); await pg.wait_for_timeout(2000)
        before = await pg.evaluate(CAP)
        await pg.evaluate("()=>{Plotly.relayout('cockpit',{'xaxis.range':[59.5,99.5]});}"); await pg.wait_for_timeout(5000)   # 四個瀏覽器同時跑,重分箱(160ms 去抖 + relayout)要多等
        after = await pg.evaluate(CAP)
        res["zoom"] = {"before": before, "after": after}
        out[tag] = {"res": res, "errors": errs[:5]}
    finally:
        await ctx.close()


def same(a, b):
    return a == b


def report(out):
    for dev in ("desktop", "mobile"):
        O, N = out["old_" + dev]["res"], out["new_" + dev]["res"]
        print(f"[{dev}] 舊版 BUILD {O['off']['SPY']['build']} / 新版 BUILD {N['off']['SPY']['build']};錯誤 舊 {out['old_'+dev]['errors']} 新 {out['new_'+dev]['errors']}")
        k1 = sum(O["off"][s]["traces"] == N["off"][s]["traces"] and O["off"][s]["shapes"] == N["off"][s]["shapes"] and O["off"][s]["ann"] == N["off"][s]["ann"] for s in SYMS)
        print(f"  ① VbP 關:traces+shapes+annotations 新舊版完全相同 {k1}/13")
        k2 = sum(O["on"][s]["traces"] == N["on"][s]["traces"] for s in SYMS)
        norm = lambda L: [json.dumps({k: (1 if k == "x1" and v > 0.8 else v) for k, v in json.loads(x).items()}, sort_keys=True) for x in L if not (json.loads(x).get("yref") == "y" and json.loads(x).get("layer") == "below" and json.loads(x).get("type") == "rect")]
        k2b = sum(norm(O["on"][s]["shapes"]) == norm(N["on"][s]["shapes"]) for s in SYMS)   # 舊版非 VbP 的 shapes 右端在 0.845(壓縮),新版 1 → 只比這個以外的部分
        print(f"  ② VbP 開:traces 新舊版完全相同 {k2}/13;非 VbP 的 shapes(把右端 0.845→1 視為相同後)相同 {k2b}/13")
        for s in ("SPY", "NVDA", "MU"):
            o, n = O["on"][s], N["on"][s]
            print(f"     {s}: x domain 舊 {o['xdom']} → 新 {n['xdom']} | VbP 柱 舊 {o['vbp']['n']}(最寬 {o['vbp']['maxW']}) → 新 {n['vbp']['n']}(最寬 {n['vbp']['maxW']}, 箱數 {n['NB']}, 顏色 {n['vbp']['cols']}) | POC 舊 {o['poc']} → 新 {n['poc']}")
        z = N["zoom"]
        print(f"  ③ 縮放到後 40 根(NVDA 新版):VbP 柱 {z['before']['vbp']['n']} → {z['after']['vbp']['n']};POC {z['before']['poc']} → {z['after']['poc']};非 VbP shapes 不變 = {z['before']['otherShapes']==z['after']['otherShapes']};traces 不變 = {z['before']['traces']==z['after']['traces']}")


async def main(old_file, new_file, snap):
    out = {}
    sites = {"old": t32.Site(old_file, 8841), "new": t32.Site(new_file, 8842)}
    try:
        async with async_playwright() as p:
            b = await p.chromium.launch(args=["--ignore-certificate-errors", "--proxy-server=" + os.environ.get("HTTPS_PROXY", ""), "--proxy-bypass-list=127.0.0.1;localhost"])
            await asyncio.gather(run(b, sites["old"], snap, "old_desktop", False, out), run(b, sites["new"], snap, "new_desktop", False, out),
                                 run(b, sites["old"], snap, "old_mobile", True, out), run(b, sites["new"], snap, "new_mobile", True, out))
            await b.close()
    finally:
        for s in sites.values():
            s.close()
    slim = {k: {"errors": v["errors"], "res": {m: ({s: {kk: vv for kk, vv in c.items() if kk not in ("traces", "shapes", "ann", "otherShapes")} | {"tracesSha": __import__("hashlib").sha256(json.dumps(c["traces"], sort_keys=True).encode()).hexdigest()[:16]} for s, c in d.items()} if m != "zoom" else {kk: {k3: v3 for k3, v3 in vv.items() if k3 not in ("traces", "shapes", "ann", "otherShapes")} for kk, vv in d.items()}) for m, d in v["res"].items()}} for k, v in out.items()}
    report(out)
    json.dump(slim, open(os.path.join(HERE, "t35_vbp_test.json"), "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], sys.argv[2], sys.argv[3]))
