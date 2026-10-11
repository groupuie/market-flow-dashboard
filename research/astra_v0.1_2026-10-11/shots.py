# 截圖:新版網頁(本機伺服器)— 桌機 1440 / 手機 390;Astra 開 + 📊量化(預設開)
#   用法:python3 shots.py <index.html> <輸出資料夾> [SYM:WIN ...]
import asyncio, os, subprocess, sys, time, tempfile, shutil
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
HTML, OUTD = sys.argv[1], sys.argv[2]; PAIRS = sys.argv[3:] or ["MU:100", "TSM:250"]
os.makedirs(OUTD, exist_ok=True)

async def main():
    www = tempfile.mkdtemp(prefix="astra_shot_"); shutil.copy(HTML, os.path.join(www, "index.html"))
    os.symlink(os.path.join(REPO, "data"), os.path.join(www, "data"))
    for f in ("astra-flow.js", "astra-dashboard-adapter.js"): shutil.copy(os.path.join(REPO, f), os.path.join(www, f))
    srv = subprocess.Popen([sys.executable, "-m", "http.server", "8821", "--bind", "127.0.0.1"], cwd=www, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); time.sleep(1)
    try:
        async with async_playwright() as p:
            b = await p.chromium.launch(args=["--proxy-server=" + os.environ.get("HTTPS_PROXY", ""), "--proxy-bypass-list=127.0.0.1;localhost"])
            for tag, vw, vh in (("desk", 1440, 1000), ("mob", 390, 844)):
                ctx = await b.new_context(viewport={"width": vw, "height": vh}, service_workers="block", device_scale_factor=2 if tag == "mob" else 1)
                pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
                await pg.goto("http://127.0.0.1:8821/index.html", wait_until="domcontentloaded", timeout=180000)
                for _ in range(180):
                    if await pg.evaluate("()=>!!document.querySelector('#cockpit .plot-container')&&typeof FCL!=='undefined'&&!!FCL"): break
                    await pg.wait_for_timeout(1000)
                for pair in PAIRS:
                    s, w = pair.split(":")
                    await pg.evaluate("([s,w])=>{CHIP_SYM=s;CHIP_WIN=+w;CHIP_PD='d';CHIP_ASTRA=true;ensureChipK(s);document.getElementById('cockpit').dataset.sig='';renderChips();}", [s, w])
                    for _ in range(40):
                        await pg.wait_for_timeout(500)
                        if await pg.evaluate("(s)=>!!(CHIPK[s]&&CHIPK[s].bars&&CHIPK.SPY&&CHIPK.SPY.bars)", s): break
                    await pg.wait_for_timeout(1500)
                    await pg.evaluate("()=>{document.getElementById('cockpit').dataset.sig='';renderChips();}"); await pg.wait_for_timeout(1500)
                    el = await pg.query_selector("#wsxChartP")
                    await el.scroll_into_view_if_needed()
                    await el.screenshot(path=os.path.join(OUTD, f"{tag}_{s}_{w}.png"))
                print(tag, "errors:", errs[:5])
                await ctx.close()
            await b.close()
    finally:
        srv.terminate(); shutil.rmtree(www, ignore_errors=True)
asyncio.run(main())
