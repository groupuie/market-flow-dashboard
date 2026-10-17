# l5:v18(自選 | K線 | 現金池)上線後線上複驗:桌機 1920、1440、手機 390 新開頁面
#   → BUILD 是新的;三欄位置(自選 < K線 < 現金池);自選清單有列、價格不是空的;常看有東西;0 頁面錯誤;HTTP≥400 只允許 .gz64 之外 0 個
import asyncio, os, json, sys
from playwright.async_api import async_playwright
URL = "https://groupuie.github.io/market-flow-dashboard/?v=wl1017"
HERE = os.path.dirname(os.path.abspath(__file__))
JS = r"""()=>{const g=id=>{const e=document.getElementById(id);if(!e)return null;const r=e.getBoundingClientRect(),s=getComputedStyle(e);
   return {vis:!!(r.width>0&&r.height>0&&s.display!=='none'),x:Math.round(r.left),y:Math.round(r.top+scrollY),w:Math.round(r.width),h:Math.round(r.height)};};
 const o={};['wsxWL','wsxCenter','cockpit','wsxLeft','destCard','wsxA','wsxB','wsxRail'].forEach(k=>o[k]=g(k));
 o.header=(()=>{const e=document.querySelector('header');const r=e.getBoundingClientRect();return r.width>0&&r.height>0&&getComputedStyle(e).display!=='none';})();
 return {build:BUILD,cls:document.documentElement.className,el:o,
   rows:[...document.querySelectorAll('#wlBody .wlRow')].map(r=>r.innerText.replace(/\s+/g,' ').trim()),
   chips:[...document.querySelectorAll('#wsxQuick .wsxChip')].map(c=>c.textContent),
   grid:getComputedStyle(document.getElementById('wsxGrid')).gridTemplateColumns,btn:document.getElementById('wsxFocusBtn').textContent,
   more:document.getElementById('wsxMoreBtn').textContent,star:document.getElementById('wlStar').textContent,
   pills:document.getElementById('wsxPills').innerText.replace(/\s+/g,' '),session:DATA&&DATA.session,ts:DATA&&DATA.ts_utc};}"""


async def main(want_build):
    out = {}
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--ignore-certificate-errors", "--proxy-server=" + os.environ.get("HTTPS_PROXY", "")])
        for tag, kw in (("d1920", dict(viewport={"width": 1920, "height": 1080})), ("d1440", dict(viewport={"width": 1440, "height": 900})),
                        ("m390", dict(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, device_scale_factor=2))):
            ctx = await b.new_context(ignore_https_errors=True, service_workers="block", **kw); pg = await ctx.new_page(); errs = []; bad = []
            pg.on("pageerror", lambda e: errs.append(str(e)[:150]))
            pg.on("response", lambda r: bad.append(f"{r.status} {r.url.split('?')[0][-60:]}") if r.status >= 400 and ".gz64" not in r.url else None)
            await pg.goto(URL, wait_until="domcontentloaded", timeout=120000)
            for _ in range(120):
                if await pg.evaluate("()=>!!document.querySelector('#cockpit .plot-container')&&typeof DATA!=='undefined'&&!!DATA&&!DATA._partial"): break
                await pg.wait_for_timeout(1000)
            await pg.wait_for_timeout(9000)
            r = await pg.evaluate(JS); r["errors"] = errs[:5]; r["bad"] = bad[:8]; out[tag] = r
            await pg.screenshot(path=os.path.join(HERE, f"l5_{tag}_live.png"))
            await ctx.close()
        await b.close()
    json.dump(out, open(os.path.join(HERE, "l5_live_check.json"), "w"), ensure_ascii=False, indent=1)
    L = []
    for k, v in out.items():
        e = v["el"]
        order = (e["wsxWL"]["x"] < e["wsxCenter"]["x"] < e["wsxLeft"]["x"]) if k != "m390" else (e["wsxCenter"]["y"] < e["wsxWL"]["y"] < e["wsxLeft"]["y"])
        L.append(f"{k}: BUILD {v['build']}({'對' if v['build'] == want_build else '還不是新版'}) class={v['cls']} 欄={v['grid']} 位置順序正確={order} "
                 f"K線 {e['cockpit']['w']}×{e['cockpit']['h']} 現金池圖寬 {e['destCard']['w']} | 其他欄位藏著={not e['wsxA']['vis'] and not e['wsxB']['vis'] and not e['wsxRail']['vis'] and not e['header']}"
                 f" | 鈕「{v['btn']}」「{v['more']}」「{v['star']}」| 行情 {v['ts']} {v['session']} | 錯誤 {v['errors']} | HTTP≥400 {v['bad']}")
        L.append(f"   自選 {len(v['rows'])} 列:{v['rows'][:4]} … | 常看 {v['chips']}")
    txt = "\n".join(L); open(os.path.join(HERE, "l5_live_check.log"), "w").write(txt + "\n"); print(txt)


asyncio.run(main(sys.argv[1]))
