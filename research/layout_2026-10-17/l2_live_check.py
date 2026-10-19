# l2:上線後線上複驗(BUILD 2026-10-17T12:50Z):桌機 1920、1440、手機 390 新開頁面 → 預設精簡、該藏的都藏、K線/現金池在、0 錯誤、0 個 HTTP≥400
import asyncio, os, json
from playwright.async_api import async_playwright
URL = "https://groupuie.github.io/market-flow-dashboard/?v=focus1017"
HERE = os.path.dirname(os.path.abspath(__file__))
IDS = ["header", "wsxLeft", "winCard", "destCard", "wsxCenter", "cockpit", "wsxInfoRow", "wsxA", "wsxB", "wsxRail", "wsxFocusBtn", "wsxWarn", "footnote"]
JS = r"""(ids)=>{const q=id=>id==='header'?document.querySelector('header'):(id==='footnote'?document.querySelector('.wrap>.note'):document.getElementById(id));
 const o={};ids.forEach(id=>{const e=q(id);if(!e){o[id]=null;return;}const r=e.getBoundingClientRect(),s=getComputedStyle(e);o[id]=!!(r.width>0&&r.height>0&&s.display!=='none'&&s.visibility!=='hidden');});
 const ck=document.getElementById('cockpit').getBoundingClientRect();
 return {build:BUILD,focus:document.documentElement.classList.contains('wsxFocus'),vis:o,ck:[Math.round(ck.width),Math.round(ck.height)],btn:document.getElementById('wsxFocusBtn').textContent,
   pills:document.getElementById('wsxPills').innerText.replace(/\s+/g,' '),warn:(document.getElementById('wsxWarn').style.display!=='none')?document.getElementById('wsxWarn').textContent:''};}"""
async def main():
    out = {}
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--ignore-certificate-errors", "--proxy-server=" + os.environ.get("HTTPS_PROXY", "")])
        for tag, kw in (("d1920", dict(viewport={"width": 1920, "height": 1080})), ("d1440", dict(viewport={"width": 1440, "height": 900})),
                        ("m390", dict(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, device_scale_factor=2))):
            ctx = await b.new_context(ignore_https_errors=True, service_workers="block", **kw); pg = await ctx.new_page(); errs = []; bad = []
            pg.on("pageerror", lambda e: errs.append(str(e)[:150])); pg.on("response", lambda r: bad.append((r.status, r.url[:120])) if r.status >= 400 else None)
            await pg.goto(URL, wait_until="domcontentloaded", timeout=120000)
            for _ in range(90):
                if await pg.evaluate("()=>!!document.querySelector('#cockpit .plot-container')&&typeof DATA!=='undefined'&&!!DATA&&!DATA._partial"): break
                await pg.wait_for_timeout(1000)
            await pg.wait_for_timeout(5000)
            r = await pg.evaluate(JS, IDS); r["errors"] = errs[:5]; r["bad"] = bad[:5]; out[tag] = r
            await pg.screenshot(path=os.path.join(HERE, f"l2_{tag}_live.png"))
            await ctx.close()
        await b.close()
    json.dump(out, open(os.path.join(HERE, "l2_live_check.json"), "w"), ensure_ascii=False, indent=1)
    for k, v in out.items():
        print(k, "BUILD", v["build"], "focus", v["focus"], "K線", v["ck"], "| 看得到", [i for i, x in v["vis"].items() if x], "| 錯誤", v["errors"], "| ≥400", v["bad"], "| 鈕", v["btn"], "| 列", v["pills"], "| 警示", v["warn"])
asyncio.run(main())
