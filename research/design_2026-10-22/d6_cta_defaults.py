# d6(2026-10-28 使用者:「K線圖 重新加回 CTA 三線的按鈕;預設顯示 量化 + astra + CTA + VbP + 布林」)
#   新版預設:五個圖層都開、圖上有 短/中/長 三條線(沒有 動63D)、CTA 鈕亮、標題有 CTA 數值、圖例有 CTA 一行;
#   按 CTA 鈕 → 三線消失、再按回來;把 CTA/Astra/VbP/布林 關掉後的 trace 與舊版(10/23 線上)預設完全相同;0 錯誤
import asyncio, json, os, sys, importlib.util
HERE = os.path.dirname(os.path.abspath(__file__))
T32 = os.path.join(os.path.dirname(HERE), "requant_2026-10-10", "t32_refresh_test.py")
spec = importlib.util.spec_from_file_location("t32", T32); t32 = importlib.util.module_from_spec(spec); spec.loader.exec_module(t32)
from playwright.async_api import async_playwright
TR = r"""()=>{const T=(document.getElementById('cockpit').data)||[];const A=v=>v==null?null:Array.from(v).map(z=>z==null?null:(typeof z==='number'?+z.toFixed(6):String(z)));
  return JSON.stringify(T.map(t=>({n:t.name||'',m:t.meta||'',x:A(t.x),y:A(t.y),c:A(t.close)})));}"""
ST = r"""()=>{const txt=h=>String(h||'').replace(/<[^>]+>/g,'').replace(/\s+/g,' ').trim();const ck=document.getElementById('cockpit');
  const names=(ck.data||[]).map(t=>t.name||'');const an=((ck.layout||{}).annotations||[]);
  const chip=document.querySelector('.cidxchipC');
  return {flags:{q:CHIP_Q,astra:CHIP_ASTRA,cta:CHIP_CTA,vbp:CHIP_VBP,bb:CHIP_BB},cta:names.filter(n=>/50D|100D|200D|63D/.test(n)),
    bb:names.filter(n=>false).length+(ck.data||[]).filter(t=>t.meta==='bb').length,vbp:((ck.layout||{}).shapes||[]).length,
    astra:names.filter(n=>/Astra|astra|sw/i.test(n)).length,title:an[0]?txt(an[0].text):'',chipOn:chip?!/opacity/.test(chip.getAttribute('style')||''):null,
    legendCTA:/CTA/.test(window.__ckLegend||''),astraStrip:(()=>{const e=document.getElementById('astrastrip');return !!(e&&e.style.display!=='none');})()};}"""
async def ready(pg):
    for _ in range(150):
        if await pg.evaluate("()=>!!document.querySelector('#cockpit .plot-container')&&typeof DATA!=='undefined'&&!!DATA&&!DATA._partial"): break
        await pg.wait_for_timeout(1000)
    await pg.wait_for_timeout(7000)
async def run(b, f, port, snap, new, out):
    site = t32.Site(f, port); r = t32.Router(snap, {}, "old")
    ctx = await b.new_context(ignore_https_errors=True, service_workers="block", viewport={"width": 1920, "height": 1080})
    await ctx.add_init_script(t32.INIT_JS)
    for h in t32.GIST_HOSTS: await ctx.route(f"https://{h}/**", r.handle)
    pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
    await pg.goto(f"http://127.0.0.1:{port}/index.html", wait_until="domcontentloaded", timeout=120000); await ready(pg)
    o = {"default": await pg.evaluate(ST), "tr_default": await pg.evaluate(TR)}
    await pg.screenshot(path=os.path.join(HERE, f"d6_{'new' if new else 'old'}_default.png"))
    if new:
        await pg.click(".cidxchipC"); await pg.wait_for_timeout(3500); o["cta_off"] = await pg.evaluate(ST)
        await pg.click(".cidxchipC"); await pg.wait_for_timeout(3500); o["cta_on"] = await pg.evaluate(ST)
        for sel in (".cidxchipC", ".cidxchipA", ".cidxchip3", ".cidxchipB"):
            await pg.click(sel); await pg.wait_for_timeout(2500)
        await pg.wait_for_timeout(3000); o["stripped"] = await pg.evaluate(ST); o["tr_stripped"] = await pg.evaluate(TR)
    o["errors"] = errs; await ctx.close(); site.close(); out["new" if new else "old"] = o
async def main(old, new, snap):
    out = {}
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--ignore-certificate-errors", "--proxy-server=" + os.environ.get("HTTPS_PROXY", ""), "--proxy-bypass-list=127.0.0.1;localhost"])
        await run(b, old, 9061, snap, False, out); await run(b, new, 9062, snap, True, out); await b.close()
    json.dump({k: {kk: vv for kk, vv in v.items() if not kk.startswith("tr_")} for k, v in out.items()}, open(os.path.join(HERE, "d6_cta_defaults.json"), "w"), ensure_ascii=False, indent=1)
    n, o = out["new"], out["old"]
    L = [f"錯誤 舊 {o['errors']} 新 {n['errors']}", f"舊版預設 {o['default']}", f"新版預設 {n['default']}",
         f"按 CTA 關 → 線 {n['cta_off']['cta']} 鈕亮={n['cta_off']['chipOn']} 標題「{n['cta_off']['title']}」",
         f"再按開 → 線 {n['cta_on']['cta']} 鈕亮={n['cta_on']['chipOn']}",
         f"四層關掉後 flags {n['stripped']['flags']} | trace 與舊版預設相同 = {n['tr_stripped'] == o['tr_default']}"]
    txt = "\n".join(L); open(os.path.join(HERE, "d6_cta_defaults.log"), "w").write(txt + "\n"); print(txt)
asyncio.run(main(*sys.argv[1:4]))
