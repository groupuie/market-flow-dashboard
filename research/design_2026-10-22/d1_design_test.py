# d1:v19 設計優化驗收(2026-10-22 使用者:「K線圖上的說明字精簡,現金池欄精簡,整體視覺統一」)
#   新舊版(舊 = 線上 v18,repo 91a56cf/5453c90 的 index.html)用同一份資料快照重播,桌機 1920、1440、手機 390 各開一次:
#   A. K線資料不變:預設畫面、開 SPY+布林+趨勢線、副圖換 MACD 三種狀態,駕駛艙全部 trace(名稱/x/y/開高低收/字/hover)新舊逐條相同
#      現金池兩張圖(dest、pooltide)的 trace 也新舊相同(只改標題字和邊距)
#   B. 說明字:K線標題只剩「代號 名稱 · 根數」;副圖標籤縮短;完整圖例在「ⓘ 圖例」裡、只列打開的圖層
#   C. ⓘ 只在點擊時開:滑過 1.5 秒不開;點 → 開;再點 / Esc / 點外面 → 關
#   D. 現金池欄:時間視窗只剩一排按鈕(「時間視窗」字、「日檔已累積」、長標題、提示句都藏起來);ⓘ 說明含 MMF 停更註記;
#      視窗鈕照常切換(5日 → 圖上色鍵變「過去 5 日」)、點板塊下鑽照常、收起/展開/只看K線照常
#   E. 0 頁面錯誤;截圖
#   用法:python3 d1_design_test.py <舊版 index.html> <新版 index.html> <快照資料夾(gist/raw 錄一次之後重播)>
import asyncio, json, os, sys, hashlib, importlib.util
HERE = os.path.dirname(os.path.abspath(__file__))
T32 = os.path.join(os.path.dirname(HERE), "requant_2026-10-10", "t32_refresh_test.py")
spec = importlib.util.spec_from_file_location("t32", T32); t32 = importlib.util.module_from_spec(spec); spec.loader.exec_module(t32)
from playwright.async_api import async_playwright

VIEWS = {"d1920": dict(viewport={"width": 1920, "height": 1080}), "d1440": dict(viewport={"width": 1440, "height": 900}),
         "m390": dict(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, device_scale_factor=2)}
TR = r"""(id)=>{const el=document.getElementById(id);const T=(el&&el.data)||[];
  const A=v=>v==null?null:Array.from(v).map(z=>z==null?null:(typeof z==='number'?+z.toFixed(6):String(z)));
  return JSON.stringify(T.map(t=>({n:t.name||'',m:t.meta||'',type:t.type||'',x:A(t.x),y:A(t.y),o:A(t.open),h:A(t.high),l:A(t.low),c:A(t.close),
    tx:Array.isArray(t.text)?A(t.text):(t.text==null?null:String(t.text)),cd:Array.isArray(t.customdata)?t.customdata.map(v=>typeof v==='string'?v:JSON.stringify(v)):null,
    ht:t.hovertemplate==null?null:String(t.hovertemplate),ya:t.yaxis||'',xa:t.xaxis||''})));}"""
INFO = r"""()=>{const txt=h=>String(h||'').replace(/<[^>]+>/g,'').replace(/\s+/g,' ').trim();
  const ck=document.getElementById('cockpit'),L=(ck&&ck.layout)||{},an=(L.annotations||[]);
  const vis=e=>{if(!e)return null;const r=e.getBoundingClientRect(),s=getComputedStyle(e);return {vis:!!(r.width>0&&r.height>0&&s.display!=='none'&&s.visibility!=='hidden'),x:Math.round(r.left),y:Math.round(r.top+scrollY),w:Math.round(r.width),h:Math.round(r.height)};};
  const a0=ck&&ck.querySelector('.annotation[data-index="0"]'),ra=a0?a0.getBoundingClientRect():null;
  const lb=document.getElementById('ckLegBtn'),rb=lb?lb.getBoundingClientRect():null;
  const dest=document.getElementById('dest'),DL=(dest&&dest.layout)||{},pt=document.getElementById('pooltide'),PL=(pt&&pt.layout)||{};
  const pop=document.getElementById('stripPop');
  const cs=e=>e?getComputedStyle(e):null;
  return {sym:CHIP_SYM,title:an[0]?txt(an[0].text):'',sub:an.slice(1,5).map(a=>txt(a.text)),nAnn:an.length,annY:an.map(a=>a.yref==='paper'&&a.y>1?txt(a.text).slice(0,30)+'@'+(+a.y).toFixed(3):null).filter(Boolean),
    margin:L.margin||null,legBtn:vis(lb),legTxt:lb?lb.textContent:'',titleBox:ra?{top:Math.round(ra.top),h:Math.round(ra.height),right:Math.round(ra.right)}:null,legBox:rb?{top:Math.round(rb.top),h:Math.round(rb.height),left:Math.round(rb.left)}:null,
    legend:txt(window.__ckLegend||''),pop:pop?{shown:pop.style.display!=='none',txt:txt(pop.innerHTML).slice(0,900)}:{shown:false,txt:''},
    destAnn:(DL.annotations||[]).map(a=>txt(a.text)).slice(-4),destMargin:DL.margin||null,ptAnn:(PL.annotations||[]).map(a=>txt(a.text)),ptMargin:PL.margin||null,
    ptYTitle:((PL.yaxis||{}).title||{}).text||'',
    win:{winTitleFont:cs(document.querySelector('#winCard h2'))?cs(document.querySelector('#winCard h2')).fontSize:'',winnote:vis(document.getElementById('winnote')),
      winbar:vis(document.getElementById('winbar')),btns:[...document.querySelectorAll('#winbar .tab')].map(t=>({t:t.textContent,y:Math.round(t.getBoundingClientRect().top),on:t.classList.contains('active')})),
      destH2:vis(document.querySelector('#destCard>h2')),hint:vis(document.querySelector('#destDrill .ddhint')),drill:txt((document.getElementById('destDrill')||{}).innerHTML||'').slice(0,120),
      cpInfo:vis(document.getElementById('cpInfoBtn')),offLabel:vis(document.querySelector('#pooloffs>span'))},
    colors:{body:cs(document.body).backgroundColor,chart:cs(document.getElementById('wsxChartP')).backgroundColor,wl:cs(document.getElementById('wlPane')).backgroundColor,
      cp:cs(document.getElementById('wsxCpHead')).backgroundColor,card:cs(document.getElementById('destCard')).backgroundColor,paper:L.paper_bgcolor||'',
      tabA:(()=>{const t=document.querySelector('#chipRange .tab.active');return t?cs(t).backgroundImage+' | '+cs(t).backgroundColor+' | '+cs(t).borderRadius:'';})()},
    cls:document.documentElement.className,ckW:ck?Math.round(ck.getBoundingClientRect().width):0,ckH:ck?Math.round(ck.getBoundingClientRect().height):0,
    docW:document.documentElement.scrollWidth};}"""


def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()[:16]


async def ready(pg, extra=6000):
    for _ in range(150):
        if await pg.evaluate("()=>!!document.querySelector('#cockpit .plot-container')&&typeof DATA!=='undefined'&&!!DATA&&!DATA._partial&&!!document.querySelector('#dest .plot-container')"):
            break
        await pg.wait_for_timeout(1000)
    await pg.wait_for_timeout(extra)


async def settle(pg, ms=3500):
    await pg.wait_for_timeout(ms)


async def traces(pg):
    return {k: await pg.evaluate(TR, k) for k in ("cockpit", "dest", "pooltide")}


async def click_chip(pg, sel):
    await pg.click(sel); await settle(pg)


async def run_view(b, page_file, port, snap, view, is_new, out_dir):
    site = t32.Site(page_file, port); r = t32.Router(snap, {}, "old")
    ctx = await b.new_context(ignore_https_errors=True, service_workers="block", **VIEWS[view])
    await ctx.add_init_script(t32.INIT_JS)
    for h in t32.GIST_HOSTS:
        await ctx.route(f"https://{h}/**", r.handle)
    pg = await ctx.new_page(); errs = []; bad = []
    pg.on("pageerror", lambda e: errs.append(str(e)[:300]))
    pg.on("response", lambda rs: bad.append(f"{rs.status} {rs.url.split('?')[0][-70:]}") if rs.status >= 400 and ".gz64" not in rs.url else None)
    tag = ("new" if is_new else "old") + "_" + view
    res = {"errors": errs, "bad": bad, "steps": {}}
    try:
        await pg.goto(f"http://127.0.0.1:{port}/index.html", wait_until="domcontentloaded", timeout=120000)
        await ready(pg)
        S = res["steps"]
        S["default"] = {"tr": await traces(pg), "info": await pg.evaluate(INFO)}
        await pg.screenshot(path=os.path.join(out_dir, f"d1_{tag}.png"))
        if view == "m390":
            await pg.screenshot(path=os.path.join(out_dir, f"d1_{tag}_full.png"), full_page=True)
        if is_new:
            # C. 滑過不開、點了才開
            lb = pg.locator("#ckLegBtn")
            if not VIEWS[view].get("has_touch"):
                await lb.hover(); await pg.wait_for_timeout(1500)
                S["hover_leg"] = await pg.evaluate("()=>{const p=document.getElementById('stripPop');return !!(p&&p.style.display!=='none');}")
            await lb.click(); await pg.wait_for_timeout(700)
            S["click_leg"] = await pg.evaluate(INFO)
            await pg.screenshot(path=os.path.join(out_dir, f"d1_{tag}_legend.png"))
            await lb.click(); await pg.wait_for_timeout(400)
            S["click_leg_again"] = await pg.evaluate("()=>{const p=document.getElementById('stripPop');return !!(p&&p.style.display!=='none');}")
            await lb.click(); await pg.wait_for_timeout(300); await pg.keyboard.press("Escape"); await pg.wait_for_timeout(300)
            S["esc_closes"] = not await pg.evaluate("()=>{const p=document.getElementById('stripPop');return !!(p&&p.style.display!=='none');}")
            await lb.click(); await pg.wait_for_timeout(300)
            await pg.mouse.click(5, (VIEWS[view]["viewport"]["height"]) - 5); await pg.wait_for_timeout(400)
            S["outside_closes"] = not await pg.evaluate("()=>{const p=document.getElementById('stripPop');return !!(p&&p.style.display!=='none');}")
            # 現金池 ⓘ
            ci = pg.locator("#cpInfoBtn")
            await ci.scroll_into_view_if_needed()
            if not VIEWS[view].get("has_touch"):
                await ci.hover(); await pg.wait_for_timeout(1200)
                S["hover_cp"] = await pg.evaluate("()=>{const p=document.getElementById('stripPop');return !!(p&&p.style.display!=='none');}")
            await ci.click(); await pg.wait_for_timeout(700)
            S["click_cp"] = await pg.evaluate("()=>{const p=document.getElementById('stripPop');return {shown:!!(p&&p.style.display!=='none'),txt:(p?p.innerText:'').replace(/\\s+/g,' ').slice(0,900)};}")
            S["cls_after_cp"] = await pg.evaluate("()=>document.documentElement.className")
            await pg.screenshot(path=os.path.join(out_dir, f"d1_{tag}_cpinfo.png"))
            await ci.click(); await pg.wait_for_timeout(400)
            await pg.evaluate("()=>window.scrollTo(0,0)")
        # D. 視窗鈕:5日 → 即時
        await pg.locator('#winbar .tab[data-w="5"]').scroll_into_view_if_needed()
        await pg.click('#winbar .tab[data-w="5"]'); await settle(pg, 4000)
        S["win5"] = {"tr": await traces(pg), "info": await pg.evaluate(INFO)}
        if view == "d1920":
            await pg.screenshot(path=os.path.join(out_dir, f"d1_{tag}_win5.png"))
        await pg.click('#winbar .tab[data-w="live"]'); await settle(pg, 3000)
        # 板塊下鑽:點 y 軸「半導體」
        try:
            await pg.evaluate("""()=>{const t=[...document.querySelectorAll('#dest .ytick text')].find(e=>e.textContent==='半導體');if(t)t.dispatchEvent(new MouseEvent('click',{bubbles:true}));}""")
            await pg.wait_for_timeout(1200)
            S["drill"] = await pg.evaluate("()=>{const d=document.getElementById('destDrill');return {n:d.querySelectorAll('.ddsym').length,txt:d.innerText.replace(/\\s+/g,' ').slice(0,160)};}")
            await pg.evaluate("()=>{const c=document.querySelector('#destDrill .ddclose');if(c)c.click();}"); await pg.wait_for_timeout(600)
        except Exception as e:
            S["drill"] = {"err": str(e)[:200]}
        await pg.evaluate("()=>window.scrollTo(0,0)")
        # A. 開圖層:SPY 疊加 + 布林 + 趨勢線 → trace 新舊相同、圖例跟著列出
        await click_chip(pg, '.cidxchip[data-k="SPY"]'); await click_chip(pg, '.cidxchipB'); await click_chip(pg, '.cidxchip2')
        await settle(pg, 2500)
        S["layers"] = {"tr": await traces(pg), "info": await pg.evaluate(INFO)}
        if view != "m390":
            await pg.screenshot(path=os.path.join(out_dir, f"d1_{tag}_layers.png"))
        await click_chip(pg, '.cidxchip[data-k="SPY"]'); await click_chip(pg, '.cidxchipB'); await click_chip(pg, '.cidxchip2')
        # 副圖換 MACD
        await pg.select_option('.cidxind', 'macd'); await settle(pg, 3000)
        S["macd"] = {"tr": await traces(pg), "info": await pg.evaluate(INFO)}
        await pg.select_option('.cidxind', 'rv'); await settle(pg, 2500)
        # 全史
        try:
            await pg.click('#chipRange .tab:has-text("全史")'); await settle(pg, 6000)
            S["max"] = {"info": await pg.evaluate(INFO)}
            await pg.click('#chipRange .tab:has-text("100日")'); await settle(pg, 3000)
        except Exception as e:
            S["max"] = {"err": str(e)[:200]}
        # 收起 / 展開(桌機)
        if view != "m390":
            w0 = await pg.evaluate("()=>Math.round(document.getElementById('cockpit').getBoundingClientRect().width)")
            await pg.click('#wsxFocusBtn'); await settle(pg, 2500)
            w1 = await pg.evaluate("()=>Math.round(document.getElementById('cockpit').getBoundingClientRect().width)")
            leg1 = await pg.evaluate(INFO)
            await pg.click('#wsxFocusBtn'); await settle(pg, 2500)
            w2 = await pg.evaluate("()=>Math.round(document.getElementById('cockpit').getBoundingClientRect().width)")
            S["focus"] = {"w0": w0, "kOnly": w1, "back": w2, "legBtn_kOnly": leg1["legBtn"], "titleBox_kOnly": leg1["titleBox"], "legBox_kOnly": leg1["legBox"]}
        S["end"] = {"info": await pg.evaluate(INFO)}
    finally:
        await ctx.close(); site.close()
    return res


async def main(old, new, snap):
    out_dir = HERE; R = {}
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--ignore-certificate-errors", "--proxy-server=" + os.environ.get("HTTPS_PROXY", ""), "--proxy-bypass-list=127.0.0.1;localhost"])
        port = 8991
        for view in VIEWS:
            for is_new, f in ((False, old), (True, new)):
                R[("new" if is_new else "old") + "_" + view] = await run_view(b, f, port, snap, view, is_new, out_dir); port += 1
        await b.close()
    json.dump(R, open(os.path.join(HERE, "d1_design_test.json"), "w"), ensure_ascii=False, indent=1)
    report(R)


def report(R):
    L = []
    for view in VIEWS:
        o, n = R["old_" + view], R["new_" + view]
        L.append(f"=== {view} | 錯誤 舊 {o['errors']} 新 {n['errors']} | HTTP≥400 舊 {o['bad'][:3]} 新 {n['bad'][:3]}")
        for st in ("default", "win5", "layers", "macd"):
            if st in o["steps"] and st in n["steps"]:
                so, sn = o["steps"][st]["tr"], n["steps"][st]["tr"]
                same = {k: so[k] == sn[k] for k in so}
                L.append(f"   {st}: trace 新舊相同 {same} (駕駛艙 {len(json.loads(sn['cockpit']))} 條, sha {sha(sn['cockpit'])})")
        io, inn = o["steps"]["default"]["info"], n["steps"]["default"]["info"]
        L.append(f"   標題 舊「{io['title'][:150]}」")
        L.append(f"   標題 新「{inn['title']}」")
        L.append(f"   副圖 舊 {io['sub']}")
        L.append(f"   副圖 新 {inn['sub']}")
        L.append(f"   邊距 舊 {io['margin']} 新 {inn['margin']} | K線 {io['ckW']}×{io['ckH']} → {inn['ckW']}×{inn['ckH']} | 頁寬 {inn['docW']}")
        L.append(f"   圖例鈕 {inn['legBtn']}「{inn['legTxt']}」 標題框 {inn['titleBox']} 鈕框 {inn['legBox']} | 預設懸浮窗開著={inn['pop']['shown']}")
        L.append(f"   圖例內容:{inn['legend'][:400]}")
        S = n["steps"]
        L.append(f"   滑過不開(圖例)={not S.get('hover_leg', False)} 滑過不開(現金池)={not S.get('hover_cp', False)} | 點了開={S['click_leg']['pop']['shown']} 再點關={not S['click_leg_again']} Esc關={S['esc_closes']} 點外面關={S['outside_closes']}")
        L.append(f"   現金池ⓘ:開={S['click_cp']['shown']} 收起狀態沒變={S['cls_after_cp']==inn['cls']} 內容「{S['click_cp']['txt'][:300]}」")
        L.append(f"   現金池欄 舊:{io['win']}")
        L.append(f"   現金池欄 新:{inn['win']}")
        L.append(f"   dest 色鍵 舊 {io['destAnn']} 邊距 {io['destMargin']}")
        L.append(f"   dest 色鍵 新 {inn['destAnn']} 邊距 {inn['destMargin']}")
        L.append(f"   場內資金 舊 {io['ptAnn']} y軸「{io['ptYTitle']}」 → 新 {inn['ptAnn']} y軸「{inn['ptYTitle']}」")
        L.append(f"   5日 → 新 dest 色鍵 {[a for a in S['win5']['info']['destAnn'] if a.startswith('【')]} 鈕 {[x['t'] for x in S['win5']['info']['win']['btns'] if x['on']]}")
        L.append(f"   下鑽 舊 {o['steps'].get('drill')} 新 {S.get('drill')}")
        L.append(f"   開圖層後 標題「{S['layers']['info']['title']}」 圖例含 SPY={('SPY' in S['layers']['info']['legend'])} 布林={('布林' in S['layers']['info']['legend'])} 趨勢線={('─撐' in S['layers']['info']['legend'])}")
        L.append(f"   MACD 副圖標籤 舊 {o['steps']['macd']['info']['sub'][1]} 新 {S['macd']['info']['sub'][1]} | 圖例第二格「{[x for x in S['macd']['info']['legend'].split('第二格')[1:2]]}」")
        L.append(f"   全史 舊「{o['steps']['max'].get('info',{}).get('title','')}」 新「{S['max'].get('info',{}).get('title','')}」 圖例「{S['max'].get('info',{}).get('legend','')[:160]}」")
        if "focus" in S:
            L.append(f"   只看K線 新 {S['focus']} | 舊 {o['steps'].get('focus',{}).get('w0')}→{o['steps'].get('focus',{}).get('kOnly')}")
        L.append(f"   顏色 舊 {io['colors']}")
        L.append(f"   顏色 新 {inn['colors']}")
    txt = "\n".join(L); open(os.path.join(HERE, "d1_design_test.log"), "w").write(txt + "\n"); print(txt)


if __name__ == "__main__":
    if sys.argv[1:2] == ["report"]:      # 只用已存的 d1_design_test.json 重出 log
        report(json.load(open(os.path.join(HERE, "d1_design_test.json"))))
    else:
        asyncio.run(main(*sys.argv[1:4]))
