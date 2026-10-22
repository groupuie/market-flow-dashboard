# d4:v19 上線後線上複驗(真網址、真資料):1920、1440、手機 390 新開頁面
#   → BUILD 是新的;K線標題短版、「ⓘ 圖例」看得到且對齊標題、預設沒開;現金池欄一排按鈕、ⓘ 在;三欄位置;0 頁面錯誤
import asyncio, os, json, sys
from playwright.async_api import async_playwright
URL = "https://groupuie.github.io/market-flow-dashboard/?v=v19"
HERE = os.path.dirname(os.path.abspath(__file__))
JS = r"""()=>{const txt=h=>String(h||'').replace(/<[^>]+>/g,'').replace(/\s+/g,' ').trim();
  const g=id=>{const e=document.getElementById(id);if(!e)return null;const r=e.getBoundingClientRect(),s=getComputedStyle(e);
   return {vis:!!(r.width>0&&r.height>0&&s.display!=='none'),x:Math.round(r.left),y:Math.round(r.top+scrollY),w:Math.round(r.width),h:Math.round(r.height)};};
  const ck=document.getElementById('cockpit'),an=((ck&&ck.layout)||{}).annotations||[];
  const a0=ck&&ck.querySelector('.annotation[data-index="0"]'),ra=a0?a0.getBoundingClientRect():null,lb=document.getElementById('ckLegBtn'),rb=lb?lb.getBoundingClientRect():null;
  const p=document.getElementById('stripPop');
  return {build:BUILD,cls:document.documentElement.className,title:an[0]?txt(an[0].text):'',sub:an.slice(1,5).map(a=>txt(a.text)),
    leg:g('ckLegBtn'),dy:(ra&&rb)?Math.round((rb.top+rb.height/2)-(ra.top+ra.height/2)):null,popOpen:!!(p&&p.style.display!=='none'),
    wl:g('wsxWL'),center:g('wsxCenter'),cp:g('wsxLeft'),cpInfo:g('cpInfoBtn'),
    btnRows:[...new Set([...document.querySelectorAll('#winbar .tab')].map(t=>Math.round(t.getBoundingClientRect().top)))].length,
    destKey:(((document.getElementById('dest')||{}).layout||{}).annotations||[]).map(a=>txt(a.text)).filter(t=>t.startsWith('【')),
    paper:((ck&&ck.layout)||{}).paper_bgcolor||'',rows:document.querySelectorAll('#wlBody .wlRow').length,
    ts:DATA&&DATA.ts_utc,session:DATA&&DATA.session};}"""


async def main(want):
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
                if await pg.evaluate("()=>!!document.querySelector('#cockpit .plot-container')&&typeof DATA!=='undefined'&&!!DATA&&!DATA._partial&&!!document.querySelector('#dest .plot-container')"): break
                await pg.wait_for_timeout(1000)
            await pg.wait_for_timeout(8000)
            r = await pg.evaluate(JS); r["errors"] = errs[:5]; r["bad"] = bad[:8]
            await pg.screenshot(path=os.path.join(HERE, f"d4_{tag}_live.png"))
            await pg.click("#ckLegBtn"); await pg.wait_for_timeout(700)
            r["legOpens"] = await pg.evaluate("()=>{const p=document.getElementById('stripPop');return !!(p&&p.style.display!=='none'&&/圖例/.test(p.innerText));}")
            await pg.keyboard.press("Escape"); await pg.wait_for_timeout(300)
            out[tag] = r
            await ctx.close()
        await b.close()
    json.dump(out, open(os.path.join(HERE, "d4_live_check.json"), "w"), ensure_ascii=False, indent=1)
    L = []
    for k, v in out.items():
        order = (v["wl"]["x"] < v["center"]["x"] < v["cp"]["x"]) if k != "m390" else (v["center"]["y"] < v["wl"]["y"] < v["cp"]["y"])
        L.append(f"{k}: BUILD {v['build']}({'對' if v['build'] == want else '還不是新版'}) 三欄順序對={order} 標題「{v['title']}」 副圖 {v['sub']}")
        L.append(f"   ⓘ圖例 看得到={bool(v['leg'] and v['leg']['vis'])} 與標題中線差 {v['dy']}px 預設沒開={not v['popOpen']} 點了開={v['legOpens']} | 現金池 ⓘ={bool(v['cpInfo'] and v['cpInfo']['vis'])} 視窗鈕列數={v['btnRows']} 色鍵 {v['destKey']}")
        L.append(f"   圖底 {v['paper']} 自選 {v['rows']} 列 | 行情 {v['ts']} {v['session']} | 錯誤 {v['errors']} | HTTP≥400 {v['bad']}")
    txt = "\n".join(L); open(os.path.join(HERE, "d4_live_check.log"), "w").write(txt + "\n"); print(txt)


asyncio.run(main(sys.argv[1]))
