# 截圖:Astra 狀態列「ⓘ 詳情」懸浮窗 + 滑過記號的說明(手機 390)
#   用法:python3 shot_popover.py <index.html 或 https 網址> <輸出資料夾> SYM WIN
import asyncio, os, subprocess, sys, time, tempfile, shutil
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
SRC, OUTD, SYM, WIN = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
os.makedirs(OUTD, exist_ok=True)

async def main():
    srv = www = None
    if SRC.startswith("http"):
        url = SRC
    else:
        www = tempfile.mkdtemp(prefix="astra_pop_"); shutil.copy(SRC, os.path.join(www, "index.html"))
        os.symlink(os.path.join(REPO, "data"), os.path.join(www, "data"))
        for f in ("astra-flow.js", "astra-dashboard-adapter.js"): shutil.copy(os.path.join(REPO, f), os.path.join(www, f))
        srv = subprocess.Popen([sys.executable, "-m", "http.server", "8851", "--bind", "127.0.0.1"], cwd=www, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); time.sleep(1)
        url = "http://127.0.0.1:8851/index.html"
    try:
        async with async_playwright() as p:
            b = await p.chromium.launch(args=["--proxy-server=" + os.environ.get("HTTPS_PROXY", ""), "--proxy-bypass-list=127.0.0.1;localhost"])
            ctx = await b.new_context(viewport={"width": 390, "height": 844}, service_workers="block", device_scale_factor=2)
            pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
            await pg.goto(url, wait_until="domcontentloaded", timeout=180000)
            for _ in range(180):
                if await pg.evaluate("()=>!!document.querySelector('#cockpit .plot-container')&&typeof FCL!=='undefined'&&!!FCL"): break
                await pg.wait_for_timeout(1000)
            # 用真的點擊打開 Astra 按鈕(不是直接改變數)
            await pg.evaluate("([s,w])=>{CHIP_SYM=s;CHIP_WIN=w;CHIP_PD='d';ensureChipK(s);renderChips();}", [SYM, WIN])
            await pg.wait_for_timeout(2500)
            await pg.click("#chipidx .cidxchipA")
            for _ in range(40):
                await pg.wait_for_timeout(500)
                if await pg.evaluate("()=>!!(CHIPK.SPY&&CHIPK.SPY.bars)&&document.getElementById('cockpit').data.some(t=>t.meta==='astra-flow')"): break
            await pg.wait_for_timeout(1500)
            el = await pg.query_selector("#wsxChartP"); await el.scroll_into_view_if_needed()
            await pg.click("#astrastrip .sbib")
            await pg.wait_for_timeout(600)
            await pg.screenshot(path=os.path.join(OUTD, f"popover_{SYM}_{WIN}.png"))
            txt = await pg.evaluate("()=>{const p=document.getElementById('stripPop');return p&&p.style.display!=='none'?p.innerText:'(closed)';}")
            print("POPOVER:\n" + txt)
            await pg.click("#astrastrip .sbib"); await pg.wait_for_timeout(300)
            # 滑過第一個 A進(或 A出)記號
            tip = await pg.evaluate("""()=>{const gd=document.getElementById('cockpit');const t=gd.data.find(t=>t.meta==='astra-flow'&&/ENTRY|EXIT/.test(t.name));
              if(!t)return null;const i=t.x.length-1;const idx=gd.data.indexOf(t);Plotly.Fx.hover(gd,[{curveNumber:idx,pointNumber:i}]);return t.customdata[i];}""")
            await pg.wait_for_timeout(500)
            await el.screenshot(path=os.path.join(OUTD, f"hover_{SYM}_{WIN}.png"))
            print("HOVER:", tip)
            print("chip aria-pressed:", await pg.evaluate("()=>document.querySelector('#chipidx .cidxchipA').getAttribute('aria-pressed')"))
            print("errors:", errs[:5])
            await b.close()
    finally:
        if srv: srv.terminate()
        if www: shutil.rmtree(www, ignore_errors=True)
asyncio.run(main())
