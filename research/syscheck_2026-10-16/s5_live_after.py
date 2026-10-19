# s5 部署後線上複驗(BUILD 2026-10-16T00:15Z;同 s1 的檢查項目)
#   開正式網站(桌機 1920、手機 390),記錄:BUILD、頁面錯誤、HTTP ≥400、狀態徽章、資料時間、
#   兩個資料源(Mac gist / 雲端備援)各自多舊、核心檔的日K最後幾根(檔內 vs 加上當日快照棒)、紅色「日K資料未更新」條
#   用法:python3 s5_live_after.py > s5_live_after.json
import asyncio, os, json
from playwright.async_api import async_playwright
URL = "https://groupuie.github.io/market-flow-dashboard/"
CAP = r"""(s)=>{const K=CHIPK[s]||{};const b=K.bars||[];const mb=(typeof chipBars==='function'?chipBars(s,'d'):null)||[];
  const dq=document.getElementById('dqstrip');const kt=((DATA&&DATA.kline_today)||{})[s]||null;
  return {sym:s,src:K.src||'',file_last:b.slice(-3).map(x=>[x[0],x[4]]),with_today_last:mb.slice(-3).map(x=>[x[0],+x[4]]),
    kline_today:kt?[kt[0],kt[4]]:null,dq:(dq&&dq.style.display!=='none')?dq.innerText.replace(/\s+/g,' ').slice(0,260):'',
    plot:!!document.querySelector('#cockpit .plot-container')};}"""
GLOB = r"""()=>({build:BUILD,status:(document.getElementById('status')||{}).textContent,statusCls:(document.getElementById('status')||{}).className,
  updated:(document.getElementById('updated')||{}).textContent,ts_utc:DATA&&DATA.ts_utc,trade_date:DATA&&DATA.trade_date,session:DATA&&DATA.session,
  macAgeMin:DATA&&DATA._macAge!=null?Math.round(DATA._macAge):null,pubAgeMin:DATA&&DATA._pubAge!=null?Math.round(DATA._pubAge):null,
  lastDone:(typeof tjLastDone==='function')?tjLastDone():null,errorsInData:(DATA&&DATA.errors||[]).slice(0,5)})"""
async def run(b, tag, kw, syms):
    ctx = await b.new_context(ignore_https_errors=True, service_workers="block", **kw)
    pg = await ctx.new_page(); errs = []; bad = []
    pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
    pg.on("response", lambda r: bad.append((r.status, r.url[:140])) if r.status >= 400 else None)
    await pg.goto(URL + "?v=syscheck1016b", wait_until="domcontentloaded", timeout=120000)
    for _ in range(120):
        if await pg.evaluate("()=>!!document.querySelector('#cockpit .plot-container')&&typeof DATA!=='undefined'&&!!DATA&&!DATA._partial"): break
        await pg.wait_for_timeout(1000)
    await pg.wait_for_timeout(4000)
    g = await pg.evaluate(GLOB); r = {}
    for s in syms:
        await pg.fill("#chipInput", s); await pg.press("#chipInput", "Enter")
        for _ in range(60):
            await pg.wait_for_timeout(500)
            if await pg.evaluate("(s)=>CHIP_SYM===s&&!!(CHIPK[s]&&CHIPK[s].bars)&&(document.getElementById('cockpit').dataset.sig||'').startsWith(s+':')", s): break
        await pg.wait_for_timeout(2500); r[s] = await pg.evaluate(CAP, s)
    shot = f"/home/claude/tracker/research/syscheck_2026-10-16/s5_{tag}.png"
    await pg.screenshot(path=shot, full_page=False)
    await ctx.close()
    return {"global": g, "syms": r, "errors": errs, "bad": bad[:20], "shot": os.path.basename(shot)}
async def main():
    out = {}
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--ignore-certificate-errors", "--proxy-server=" + os.environ.get("HTTPS_PROXY", "")])
        out["desktop"] = await run(b, "desktop", dict(viewport={"width": 1920, "height": 1080}), ["QQQ", "SPY", "NVDA", "MU", "TSM", "AMD"])
        out["mobile"] = await run(b, "mobile", dict(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, device_scale_factor=2), ["QQQ", "NVDA"])
        await b.close()
    print(json.dumps(out, ensure_ascii=False, indent=1))
asyncio.run(main())
