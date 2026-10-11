# t31:QQQ 資料只抓一次的修正 —— 新舊版對照測試(Playwright,本機伺服器,行情照網站從 gist 即時抓)
#   用法:python3 t31_qqqfix_test.py <舊版 index.html> <新版 index.html>
#   ① 一般情況(剛打開網頁):13 檔的圖上量化記號與狀態列,新舊版要完全相同(這次修正不該改任何記號)
#   ② 模擬「網頁收盤前打開、收盤後還開著」:假裝最近已收盤日 = 2026-07-17(MU 正式有「加」的一天),
#      QQQ 與 MU 的日K檔都還停在 07-16、當天那根只在富途快照(kline_today)裡 → 舊版標不出 07-17 的加,新版要標得出
#   ③ 模擬「網頁開了好幾天」:日K檔停在 07-15(少了 07-16)、快照是 07-17,而且是很久以前抓的 → 新版要自己重抓、補齊、標出加
import asyncio, json, os, subprocess, sys, time, tempfile, shutil
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
OLD, NEW = sys.argv[1], sys.argv[2]; PORT = 8796
SYMS = ["SPY", "QQQ", "TSM", "NVDA", "MU", "AMD", "PLTR", "AVGO", "META", "SNDK", "NVDL", "SLB", "BKNG"]
CHART = """()=>{const D=document.getElementById('cockpit').data||[];const marks=[];
  D.filter(t=>/^量化/.test(t.name||'')&&t.name!=='量化盤中').forEach(t=>t.y.forEach((v,i)=>{if(v!=null&&String(t.text[i]||'').trim())marks.push(t.name.slice(2)+'|'+String(t.x[i]));}));
  const q=document.getElementById('qstrip');return {marks:marks.sort(),bar:q?q.innerText.replace(/\\s+/g,' ').trim():''};}"""
SIM = """async ([day, prevFile, longAgo])=>{
  // 假裝最近已收盤日 = day;QQQ、MU 的日K檔只到 prevFile;當天那根放進富途快照(kline_today)
  const fullQ=await (await fetch(DATA_URL.replace('market_data.json','kline_QQQ.json'),{cache:'no-store'})).json();
  const fullM=await (await fetch(DATA_URL.replace('market_data.json','kline_MU.json'),{cache:'no-store'})).json();
  cd=1e9;   // 停掉 20/120 秒輪詢,避免主檔更新蓋掉模擬的快照
  window.tjLastDone=()=>day;
  const qb=fullQ.bars.find(b=>b[0]===day), mb=fullM.bars.find(b=>b[0]===day);
  const keepQ=fullQ.bars.filter(b=>b[0]<=prevFile), keepM=fullM.bars.filter(b=>b[0]<=prevFile);
  QQQK={};keepQ.forEach(b=>{QQQK[b[0]]=b[4];});
  if(typeof QQQK_t!=='undefined')QQQK_t=longAgo?0:Date.now();
  const m={};keepM.forEach(b=>{m[b[0]]=b[4];});CHIPK.MU={close:m,bars:keepM,src:'sim',upd:''};CHIPK.MU_t=longAgo?0:Date.now();delete CHIPK.MU_rr;
  DATA.kline_today=Object.assign({},DATA.kline_today||{},{QQQ:qb.slice(),MU:mb.slice()});
  CHIP_WIN=250;CHIP_SYM='MU';const el=document.getElementById('cockpit');el.dataset.sig='';renderChips();
  return {qqqDay:qb[0],qqqClose:qb[4],muDay:mb[0]};}"""
async def run(page_file, tag, out):
    www = tempfile.mkdtemp(prefix="t31_"); shutil.copy(page_file, os.path.join(www, "index.html")); os.symlink(os.path.join(REPO, "data"), os.path.join(www, "data"))
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(PORT), "--bind", "127.0.0.1"], cwd=www, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); time.sleep(1)
    try:
        async with async_playwright() as p:
            b = await p.chromium.launch(args=["--ignore-certificate-errors", "--proxy-server=" + os.environ.get("HTTPS_PROXY", ""), "--proxy-bypass-list=127.0.0.1;localhost"])
            async def fresh():
                ctx = await b.new_context(viewport={"width": 1400, "height": 1000}, ignore_https_errors=True, service_workers="block")
                pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
                await pg.goto(f"http://127.0.0.1:{PORT}/index.html", wait_until="domcontentloaded", timeout=120000)
                for _ in range(150):
                    if await pg.evaluate("()=>!!document.querySelector('#cockpit .plot-container')&&typeof FCL!=='undefined'&&!!FCL&&!!EXTDF&&Object.keys(chipDaily()).length>=250"): break
                    await pg.wait_for_timeout(1000)
                await pg.evaluate("()=>{try{ensureQQQK();}catch(_){}}")
                for _ in range(40):
                    if await pg.evaluate("()=>!!QQQK"): break
                    await pg.wait_for_timeout(500)
                return ctx, pg, errs
            ctx, pg, errs = await fresh()
            o = {"build": await pg.evaluate("()=>BUILD"), "normal": {}}
            await pg.evaluate("()=>{CHIP_WIN=250;}")
            for s in SYMS:
                await pg.evaluate("(s)=>{CHIP_SYM=s;ensureChipK(s);const u=TK_UL[s];if(u)ensureChipK(u);renderChips();}", s)
                for _ in range(40):
                    await pg.wait_for_timeout(500)
                    if await pg.evaluate("(s)=>{const u=TK_UL[s]||s;return !!(CHIPK[u]&&CHIPK[u].bars)}", s): break
                await pg.wait_for_timeout(2500); await pg.evaluate("()=>{document.getElementById('cockpit').dataset.sig='';renderChips();}"); await pg.wait_for_timeout(1500)
                o["normal"][s] = await pg.evaluate(CHART)
            o["errors_normal"] = errs[:5]; await ctx.close()
            for name, prev, longAgo in (("sim_after_close", "2026-07-16", False), ("sim_open_days", "2026-07-15", True)):
                ctx, pg, errs = await fresh()
                info = await pg.evaluate(SIM, ["2026-07-17", prev, longAgo])
                await pg.wait_for_timeout(6000)   # 給新版背景重抓的時間
                await pg.evaluate("()=>{document.getElementById('cockpit').dataset.sig='';renderChips();}"); await pg.wait_for_timeout(2000)
                r = await pg.evaluate(CHART); r["info"] = info
                r["muLastFileBar"] = await pg.evaluate("()=>CHIPK.MU&&CHIPK.MU.bars?CHIPK.MU.bars[CHIPK.MU.bars.length-1][0]:null")
                r["qqqLast"] = await pg.evaluate("()=>{let l='';for(const d in (QQQK||{}))if(d>l)l=d;return l;}")
                r["has0716"] = await pg.evaluate("()=>(chipBars('MU','d')||[]).some(b=>b[0]==='2026-07-16')")
                r["errors"] = errs[:5]; o[name] = r; await ctx.close()
            await b.close()
    finally:
        srv.terminate(); shutil.rmtree(www, ignore_errors=True)
    out[tag] = o
async def main():
    out = {}
    await run(OLD, "old", out); await run(NEW, "new", out)
    json.dump(out, open(os.path.join(HERE, "t31_qqqfix_test.json"), "w"), ensure_ascii=False, indent=1)
    o, n = out["old"], out["new"]
    print(f"舊版 BUILD {o['build']} / 新版 BUILD {n['build']}")
    same = [s for s in SYMS if o["normal"][s] == n["normal"][s]]
    print(f"① 剛打開網頁:{len(same)}/{len(SYMS)} 檔 圖上記號與狀態列完全相同;不同的:{[s for s in SYMS if s not in same]};頁面錯誤 舊 {o['errors_normal']} 新 {n['errors_normal']}")
    for s in SYMS: print(f"   {s}:{len(n['normal'][s]['marks'])} 個字 | 狀態列:{n['normal'][s]['bar'][:70]}")
    for k, lab in (("sim_after_close", "② 收盤後網頁還開著(日K檔停在前一天)"), ("sim_open_days", "③ 網頁開了好幾天(日K檔少一天)")):
        for tag in ("old", "new"):
            r = out[tag][k]; add = "加|07-17" in r["marks"]
            print(f"{lab} {tag}:07-17 有沒有標「加」= {add};狀態列:{r['bar'][:60]};MU 日K檔最後 {r['muLastFileBar']}、QQQ 日K最後 {r['qqqLast']}、K線有 07-16 = {r['has0716']};錯誤 {r['errors']}")
asyncio.run(main())
