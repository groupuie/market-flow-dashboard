# d5:現金池欄「佔位字殘留」修正驗收(線上 1440 實測看到:「場內資金線累積中(每次採集自動加點)」壓在微調滑桿上)
#   成因(舊版就有):資料還沒到時 renderPoolTide / renderDest 用 innerHTML 放佔位字;資料到了直接 Plotly.react,佔位字沒清 → 留在圖下面。
#   修法:佔位改走 chartMsg(先 purge),畫圖前 freshPlot(沒有圖時先清空)。
#   這裡在頁面上照順序重現:① 場內資金只剩 1 點 → 佔位字;② 資料恢復 → 重畫;看佔位字還在不在、圖在不在。dest 同理(空資料 → 恢復)。
#   舊版、新版都跑一次。
import asyncio, os, sys, json, importlib.util
HERE = os.path.dirname(os.path.abspath(__file__))
T32 = os.path.join(os.path.dirname(HERE), "requant_2026-10-10", "t32_refresh_test.py")
spec = importlib.util.spec_from_file_location("t32", T32); t32 = importlib.util.module_from_spec(spec); spec.loader.exec_module(t32)
from playwright.async_api import async_playwright

SEQ = r"""async ()=>{const sl=ms=>new Promise(r=>setTimeout(r,ms));const o={};
  const pt=document.getElementById('pooltide'),de=document.getElementById('dest');
  const H=DATA.flow_history; DATA.flow_history=H.slice(-1); renderPoolTide(); await sl(300);
  o.pt_placeholder=!!pt.querySelector('.miss');
  DATA.flow_history=H; renderPoolTide(); await sl(800);
  o.pt_after={miss:!!pt.querySelector('.miss'),plot:!!pt.querySelector('.plot-container'),traces:(pt.data||[]).length};
  renderDest({}); await sl(300);
  o.dest_placeholder=!!de.querySelector('.miss');
  render(); await sl(1500);
  o.dest_after={miss:!!de.querySelector('.miss'),plot:!!de.querySelector('.plot-container'),traces:(de.data||[]).length,ddBound:de._ddBound||0};
  // 點長條(plotly_click)下鑽還有效:直接觸發 Plotly 的 click 事件
  try{de.emit('plotly_click',{points:[{y:'半導體'}]});}catch(e){o.emitErr=String(e);}
  await sl(500);
  o.drill_by_bar=document.querySelectorAll('#destDrill .ddsym').length;
  return o;}"""


async def main(old, new, snap):
    R = {}
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--ignore-certificate-errors", "--proxy-server=" + os.environ.get("HTTPS_PROXY", ""), "--proxy-bypass-list=127.0.0.1;localhost"])
        port = 9051
        for tag, f in (("old", old), ("new", new)):
            site = t32.Site(f, port); r = t32.Router(snap, {}, "old")
            ctx = await b.new_context(ignore_https_errors=True, service_workers="block", viewport={"width": 1440, "height": 900})
            await ctx.add_init_script(t32.INIT_JS)
            for h in t32.GIST_HOSTS: await ctx.route(f"https://{h}/**", r.handle)
            pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
            await pg.goto(f"http://127.0.0.1:{port}/index.html", wait_until="domcontentloaded", timeout=120000)
            for _ in range(120):
                if await pg.evaluate("()=>!!document.querySelector('#cockpit .plot-container')&&!!document.querySelector('#dest .plot-container')&&!!document.querySelector('#pooltide .plot-container')"): break
                await pg.wait_for_timeout(1000)
            await pg.wait_for_timeout(4000)
            R[tag] = await pg.evaluate(SEQ); R[tag]["errors"] = errs
            await pg.screenshot(path=os.path.join(HERE, f"d5_{tag}_after.png"))
            await ctx.close(); site.close(); port += 1
        await b.close()
    json.dump(R, open(os.path.join(HERE, "d5_stray_msg.json"), "w"), ensure_ascii=False, indent=1)
    L = [f"{k}: 場內資金 佔位字出現={v['pt_placeholder']} → 資料恢復後 佔位字還在={v['pt_after']['miss']} 圖在={v['pt_after']['plot']}({v['pt_after']['traces']} 條)"
         f" | 目的地圖 佔位字出現={v['dest_placeholder']} → 恢復後 佔位字還在={v['dest_after']['miss']} 圖在={v['dest_after']['plot']} 點擊監聽={v['dest_after']['ddBound']}"
         f" 點長條下鑽={v['drill_by_bar']} 檔 | 錯誤 {v['errors']} {v.get('emitErr','')}" for k, v in R.items()]
    txt = "\n".join(L); open(os.path.join(HERE, "d5_stray_msg.log"), "w").write(txt + "\n"); print(txt)


asyncio.run(main(*sys.argv[1:4]))
