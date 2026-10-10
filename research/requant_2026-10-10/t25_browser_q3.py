import asyncio, os, sys, json, subprocess, time, tempfile, shutil
from playwright.async_api import async_playwright
# Codex v0.1 回歸測試:同一批即時資料、同一個瀏覽器 session,舊版(上線 16:19Z)vs 新版(本地)
#   1) 五檔全部記號(頂K/減碼/出/抄底/買/加/熱)逐日比對(整段歷史 + 圖上 250 根實際畫出的字)
#   2) 新版:狀態列、詳情、盤中暫標、過去日期、強制「買賣同時出現」顯示
REPO = "/home/claude/tracker"; SCR = os.path.dirname(os.path.abspath(__file__))
OLD = "/tmp/claude-0/-home-claude/d0a676e0-fcd7-5eae-bc26-2609f6d7a033/scratchpad/codex_v01/index-before.html"
TOUCH = os.environ.get("TOUCH") == "1"; W = 390 if TOUCH else 1400; H = 844 if TOUCH else 1000; PORT = 8791 if TOUCH else 8790
SYMS = ["MU", "SNDK", "TSM", "NVDA", "META"]
EVJS = """(sym)=>{
  const lastDone=tjLastDone(), sb=chipBars(sym,'d')||[], B=sb.filter(b=>b[0]<=lastDone);
  const D0=chipDaily(), FM={};Object.keys(D0||{}).forEach(dd=>{const e=(D0[dd]||{})[sym];if(e&&e.m!=null&&dd<=lastDone)FM[dd]=+e.m;});
  const T=tjSeriesJS(B,FM), TK=tkSeriesJS(B), FT=FCL?fcSeriesJS(B):null, HT=htSeriesJS(B), E=[];
  for(let j=0;j<TK.n;j++){if(TK.tk[j])E.push({w:'頂K',j:j,d:TK.D[j]}); if(TK.cf[j])E.push({w:'減碼',j:j,d:TK.D[j]});}
  if(FT)FT.ev.forEach(e=>E.push({w:e.k==='trim'?'出':'抄底',j:e.i,d:e.d}));
  const isNew=typeof qmAppendPathBuys==='function';
  if(isNew)qmAppendPathBuys(E,T);
  else for(let j=1;j<T.n;j++){const a=T.passT[j]&&!T.passT[j-1],b=T.passC[j]&&!T.passC[j-1],c=T.passD[j]&&!T.passD[j-1];
        if((a||b||c)&&!E.some(x=>x.w==='抄底'&&Math.abs(x.j-j)<=3))E.push({w:'買',j:j,d:T.D[j],p:a?'T':b?'C':'D'});}
  const QD={};if(QQQK){const ds=Object.keys(QQQK).filter(d=>d<=lastDone).sort();let s0=0;
    ds.forEach((d,i)=>{s0+=+QQQK[d];if(i>=20)s0-=+QQQK[ds[i-20]];if(i>=19)QD[d]=(+QQQK[d])<s0/20;});}
  const qdOf=d=>{if(d in QD)return QD[d];if(QQQK)return null;const v=fcMktOf(d);return (v!=null&&FCL&&FCL._mkd&&d<=FCL._mkd)?!!(v&QM.QB):null;};
  const chuB=new Array(B.length).fill(false);E.forEach(x=>{if(x.w==='出')chuB[x.j]=true;});
  const AD=adSeriesJS(B,qdOf,chuB);for(let j=0;j<AD.n;j++)if(AD.sig[j])E.push({w:'加',j:j,d:AD.D[j]});
  for(let j=0;j<HT.n;j++)if(HT.sig[j])E.push({w:'熱',j:j,d:HT.D[j]});
  // 每根的路徑首日(不管有沒有被抄底去重)+ 該根前後的抄底,用來寫原因
  const pathDays=[];for(let j=1;j<T.n;j++){const a=T.passT[j]&&!T.passT[j-1],b=T.passC[j]&&!T.passC[j-1],c=T.passD[j]&&!T.passD[j-1];if(a||b||c)pathDays.push(T.D[j]);}
  return {isNew,n:B.length,first:B[0]&&B[0][0],last:B.length?B[B.length-1][0]:null,qqqk:!!QQQK,fmDays:Object.keys(FM).length,
          ev:E.map(x=>x.w+'|'+x.d).sort(),pathDays:pathDays};
}"""
TRJS = """()=>{const el=document.getElementById('cockpit');const D=(el&&el.data)||[];const out=[];
  D.filter(t=>/^量化/.test(t.name||'')&&t.name!=='量化盤中').forEach(t=>{t.y.forEach((v,i)=>{if(v!=null&&t.text&&String(t.text[i]||'').trim())out.push(t.name.slice(2)+'|'+String(t.x[i]).slice(0,10));});});
  const q=document.getElementById('qstrip');
  return {sym:CHIP_SYM,win:CHIP_WIN,x0:(D[0]&&D[0].x)?String(D[0].x[0]).slice(0,10):null,marks:out.sort(),bar:q&&q.style.display!=='none'?q.innerText.replace(/\\n/g,' '):'(hidden)'};}"""
POPJS = "()=>{const p=document.getElementById('stripPop');return p&&p.style.display!=='none'?p.innerText:null;}"
async def main():
    root = tempfile.mkdtemp(prefix="q3root_")
    for nm in os.listdir(REPO):
        if nm not in ("out", "research", ".git"): os.symlink(os.path.join(REPO, nm), os.path.join(root, nm))
    shutil.copy(OLD, os.path.join(root, "index_old.html"))
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(PORT), "--bind", "127.0.0.1"], cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1); res = {}
    try:
        async with async_playwright() as p:
            b = await p.chromium.launch(args=["--ignore-certificate-errors", "--proxy-server=" + os.environ.get("HTTPS_PROXY"), "--proxy-bypass-list=127.0.0.1;localhost"])
            for tag, page in (("old", "index_old.html"), ("new", "index.html")):
                if TOUCH and tag == "old": continue
                ctx = await b.new_context(viewport={"width": W, "height": H}, device_scale_factor=2, ignore_https_errors=True, has_touch=TOUCH, is_mobile=TOUCH, service_workers="block")
                pg = await ctx.new_page(); errs = []
                pg.on("pageerror", lambda e: errs.append("PAGEERROR " + str(e)))
                pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
                await pg.goto(f"http://127.0.0.1:{PORT}/{page}", wait_until="domcontentloaded", timeout=120000)
                for _ in range(120):
                    if await pg.evaluate("()=>!!document.querySelector('#cockpit .plot-container')&&typeof FCL!=='undefined'&&!!FCL"): break
                    await pg.wait_for_timeout(1000)
                await pg.evaluate("()=>{try{ensureQQQK();}catch(_){}}")
                for _ in range(30):
                    if await pg.evaluate("()=>!!QQQK"): break
                    await pg.wait_for_timeout(500)
                info = {"BUILD": await pg.evaluate("()=>BUILD"), "lastDone": await pg.evaluate("()=>tjLastDone()"), "sym": {}}
                print(tag, info["BUILD"], "lastDone", info["lastDone"], flush=True)
                await pg.evaluate("()=>{CHIP_WIN=250;}")
                for s in SYMS:
                    await pg.evaluate("(s)=>{CHIP_SYM=s;ensureChipK(s);renderChips();}", s)
                    for _ in range(30):
                        await pg.wait_for_timeout(700)
                        if await pg.evaluate("(s)=>!!(CHIPK[s]&&CHIPK[s].bars)", s): break
                    await pg.wait_for_timeout(2500)
                    ev = await pg.evaluate(EVJS, s); tr = await pg.evaluate(TRJS)
                    info["sym"][s] = {"ev": ev, "tr": tr}
                    if tag == "new":
                        btn = await pg.query_selector("#qstrip .sbib")
                        if TOUCH: await btn.tap()
                        else: await btn.click()
                        await pg.wait_for_timeout(600); info["sym"][s]["pop"] = await pg.evaluate(POPJS)
                        await pg.screenshot(path=os.path.join(SCR, f"q3_{s}_{'m' if TOUCH else 'd'}.png"))
                        if TOUCH: await btn.tap()
                        else: await btn.click()
                        await pg.wait_for_timeout(300)
                    print(" ", s, "bars", ev["n"], ev["first"], "→", ev["last"], "| FM 天數", ev["fmDays"], "| 圖上", len(tr["marks"]), "| 狀態列:", tr["bar"][:160], flush=True)
                if tag == "new":
                    # 強制「買賣同時出現」:暫時把 qmSelectLatestValid 換成回傳衝突(只測畫面,不改規則)
                    await pg.evaluate("()=>{window.__qs=qmSelectLatestValid;qmSelectLatestValid=function(E,v,i){const r=window.__qs(E,v,i);const L=E.filter(x=>x.j<=i);const j=L.length?L[L.length-1].j:i;return {conflict:true,events:[{w:'出',j:j,d:L.length?L[L.length-1].d:'2026-10-09'},{w:'加',j:j,d:L.length?L[L.length-1].d:'2026-10-09'}],selected:null};};CHIP_SYM='TSM';document.getElementById('cockpit').dataset.sig='';renderChips();}")
                    await pg.wait_for_timeout(2500)
                    t = await pg.evaluate(TRJS); btn = await pg.query_selector("#qstrip .sbib")
                    if TOUCH: await btn.tap()
                    else: await btn.click()
                    await pg.wait_for_timeout(600); pop = await pg.evaluate(POPJS)
                    await pg.screenshot(path=os.path.join(SCR, f"q3_conflict_{'m' if TOUCH else 'd'}.png"))
                    if TOUCH: await btn.tap()
                    else: await btn.click()
                    info["conflict"] = {"bar": t["bar"], "pop": pop}
                    print("CONFLICT bar:", t["bar"][:200]); print("CONFLICT pop:", (pop or "(none)").replace("\n", " / ")[:600], flush=True)
                    await pg.evaluate("()=>{qmSelectLatestValid=window.__qs;document.getElementById('cockpit').dataset.sig='';renderChips();}")
                    await pg.wait_for_timeout(1500)
                    # 盤中暫標:假裝 10-09 還在盤中
                    await pg.evaluate("()=>{window.__ld=tjLastDone;window.__sd=snapDate;tjLastDone=()=>'2026-10-08';snapDate=()=>'2026-10-09';CHIP_SYM='MU';document.getElementById('cockpit').dataset.sig='';renderChips();}")
                    await pg.wait_for_timeout(2500); t = await pg.evaluate(TRJS)
                    live = await pg.evaluate("()=>{const D=document.getElementById('cockpit').data||[];const t=D.find(t=>t.name==='量化盤中');return t?t.text.filter(Boolean):[];}")
                    info["intraday"] = {"bar": t["bar"], "live": live}; print("INTRADAY MU:", t["bar"][:200], "| 盤中字:", live, flush=True)
                    # 過去日期:2026-07-17(TSM 07-16 有加)
                    await pg.evaluate("()=>{tjLastDone=()=>'2026-07-17';snapDate=()=>'2026-07-17';CHIP_SYM='TSM';document.getElementById('cockpit').dataset.sig='';renderChips();}")
                    await pg.wait_for_timeout(2500); t = await pg.evaluate(TRJS); info["past"] = {"bar": t["bar"]}; print("PAST TSM 07-17:", t["bar"][:200], flush=True)
                    await pg.evaluate("()=>{tjLastDone=window.__ld;snapDate=window.__sd;document.getElementById('cockpit').dataset.sig='';renderChips();}")
                    await pg.wait_for_timeout(800)
                info["errors"] = errs[:20]; print(tag, "errors:", errs[:10], flush=True)
                res[tag] = info; await ctx.close()
            await b.close()
    finally:
        srv.terminate(); shutil.rmtree(root, ignore_errors=True)
    json.dump(res, open(os.path.join(SCR, f"q3_res_{'m' if TOUCH else 'd'}.json"), "w"), ensure_ascii=False, indent=1)
if __name__ == "__main__": asyncio.run(main())
