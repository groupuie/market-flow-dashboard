# d2:v19 新版補充檢查(只跑新版;資料用 d1 同一份快照)
#   - 點自選「美光科技」→ K線標題換成「MU 美光科技 · 100日」,ⓘ 圖例跟著標題列
#   - 週K:圖例寫「量化記號只在日K顯示」;切回日K
#   - Astra 打開:標題有 Astra 色鍵、圖例有 Astra 那一行
#   - 副圖換 MACD:圖例左欄是「MACD」
#   - 現金池 ⓘ:表格格式、MMF 停更註記
#   - 「⋯ 其他欄位」打開時的樣子(截圖),關掉回三欄
#   - 0 頁面錯誤
import asyncio, json, os, sys, importlib.util
HERE = os.path.dirname(os.path.abspath(__file__))
T32 = os.path.join(os.path.dirname(HERE), "requant_2026-10-10", "t32_refresh_test.py")
spec = importlib.util.spec_from_file_location("t32", T32); t32 = importlib.util.module_from_spec(spec); spec.loader.exec_module(t32)
from playwright.async_api import async_playwright

ST = r"""()=>{const txt=h=>String(h||'').replace(/<[^>]+>/g,'').replace(/\s+/g,' ').trim();
  const ck=document.getElementById('cockpit'),an=((ck&&ck.layout)||{}).annotations||[];
  const a0=ck&&ck.querySelector('.annotation[data-index="0"]'),ra=a0?a0.getBoundingClientRect():null,lb=document.getElementById('ckLegBtn'),rb=lb?lb.getBoundingClientRect():null;
  const p=document.getElementById('stripPop');
  return {sym:CHIP_SYM,title:an[0]?txt(an[0].text):'',y8:an.find(a=>a.yref==='y8 domain')?txt(an.find(a=>a.yref==='y8 domain').text):'',
    legend:txt(window.__ckLegend||''),btnShown:!!(lb&&lb.style.display!=='none'&&rb&&rb.width>0),dy:(ra&&rb)?Math.round((rb.top+rb.height/2)-(ra.top+ra.height/2)):null,
    pop:p?{shown:p.style.display!=='none',txt:p.innerText.replace(/\s+/g,' ').slice(0,700)}:null,cls:document.documentElement.className};}"""


async def main(new, snap):
    out = {}
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--ignore-certificate-errors", "--proxy-server=" + os.environ.get("HTTPS_PROXY", ""), "--proxy-bypass-list=127.0.0.1;localhost"])
        site = t32.Site(new, 9031); r = t32.Router(snap, {}, "old")
        ctx = await b.new_context(ignore_https_errors=True, service_workers="block", viewport={"width": 1920, "height": 1080})
        await ctx.add_init_script(t32.INIT_JS)
        for h in t32.GIST_HOSTS:
            await ctx.route(f"https://{h}/**", r.handle)
        pg = await ctx.new_page(); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)[:300]))
        await pg.goto("http://127.0.0.1:9031/index.html", wait_until="domcontentloaded", timeout=120000)
        for _ in range(150):
            if await pg.evaluate("()=>!!document.querySelector('#cockpit .plot-container')&&typeof DATA!=='undefined'&&!!DATA&&!DATA._partial"):
                break
            await pg.wait_for_timeout(1000)
        await pg.wait_for_timeout(6000)
        out["start"] = await pg.evaluate(ST)
        await pg.click('#wlBody .wlRow[data-wl="MU"]')
        for _ in range(40):
            await pg.wait_for_timeout(500)
            if await pg.evaluate("()=>CHIP_SYM==='MU'&&(document.getElementById('cockpit').dataset.sig||'').startsWith('MU:')"):
                break
        await pg.wait_for_timeout(2500)
        out["mu"] = await pg.evaluate(ST)
        await pg.click('#chipRange .tab:has-text("週K")'); await pg.wait_for_timeout(4000)
        out["weekly"] = await pg.evaluate(ST)
        await pg.click('#chipRange .tab:has-text("日K")'); await pg.wait_for_timeout(4000)
        await pg.click('.cidxchipA')
        for _ in range(40):
            await pg.wait_for_timeout(500)
            if await pg.evaluate("()=>CHIP_ASTRA&&/=Astra/.test(String(((document.getElementById('cockpit').layout||{}).annotations||[{}])[0].text||''))"):
                break
        await pg.wait_for_timeout(2500)
        out["astra"] = await pg.evaluate(ST)
        await pg.screenshot(path=os.path.join(HERE, "d2_astra_on.png"))
        await pg.click('.cidxchipA'); await pg.wait_for_timeout(3000)
        await pg.select_option('.cidxind', 'macd'); await pg.wait_for_timeout(3500)
        out["macd"] = await pg.evaluate(ST)
        await pg.select_option('.cidxind', 'rv'); await pg.wait_for_timeout(3000)
        await pg.click('#cpInfoBtn'); await pg.wait_for_timeout(800)
        out["cpinfo"] = await pg.evaluate(ST)
        await pg.screenshot(path=os.path.join(HERE, "d2_cpinfo.png"))
        await pg.keyboard.press("Escape"); await pg.wait_for_timeout(400)
        await pg.click('#wsxMoreBtn'); await pg.wait_for_timeout(3500)
        out["others"] = await pg.evaluate(ST)
        await pg.screenshot(path=os.path.join(HERE, "d2_others_open.png"))
        await pg.click('#wsxMoreBtn'); await pg.wait_for_timeout(3000)
        out["others_closed"] = await pg.evaluate(ST)
        out["errors"] = errs
        await ctx.close(); site.close(); await b.close()
    json.dump(out, open(os.path.join(HERE, "d2_new_only.json"), "w"), ensure_ascii=False, indent=1)
    L = [f"錯誤 {out['errors']}"]
    for k in ("start", "mu", "weekly", "astra", "macd", "cpinfo", "others", "others_closed"):
        v = out[k]
        L.append(f"{k}: {v['sym']} 標題「{v['title']}」 副圖二「{v['y8']}」 鈕={v['btnShown']} 鈕與標題中線差 {v['dy']}px class={v['cls']}")
        if k in ("weekly", "astra", "macd"):
            L.append(f"   圖例:{v['legend'][:600]}")
        if k == "cpinfo":
            L.append(f"   現金池 ⓘ:{v['pop']}")
    txt = "\n".join(L); open(os.path.join(HERE, "d2_new_only.log"), "w").write(txt + "\n"); print(txt)


if __name__ == "__main__":
    asyncio.run(main(*sys.argv[1:3]))
