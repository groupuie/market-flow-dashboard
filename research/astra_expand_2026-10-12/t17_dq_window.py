# t17:擴大範圍日K 的資料條(複驗時發現:收盤後到每天自動更新之間會誤報紅色「未更新」)
#   axDqWait:美東 lastDone 當天 16:00–23:00 → true;其他時間 → false
#   HUBS(不在追蹤清單):等更新的時間 → 灰字「還沒進來」;超過 → 紅字「未更新」;資料跟上 → 一般說明(紅字會被換掉)
#   用法:python3 t17_dq_window.py <index.html> <輸出.json>
import asyncio, json, os, sys
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "research", "swing_tune_2026-10-12"))
import t13_astra_merge_test as T
HTML, OUT = sys.argv[1], sys.argv[2]

async def main():
    res = {}
    async with async_playwright() as p:
        br = await p.chromium.launch(args=["--proxy-server=" + os.environ.get("HTTPS_PROXY", ""), "--proxy-bypass-list=127.0.0.1;localhost"])
        srv, www = T.start_server(HTML, 8896)
        try:
            ctx, pg, errs, _ = await T.open_page(br, 8896)
            res["wait"] = await pg.evaluate("""()=>{const t=(iso)=>axDqWait('2026-10-09',new Date(iso));
              return {et20:t('2026-10-10T00:00:00Z'), et1559:t('2026-10-09T19:59:00Z'), et1600:t('2026-10-09T20:00:00Z'), et2259:t('2026-10-10T02:59:00Z'), et2300:t('2026-10-10T03:00:00Z'), nextday10:t('2026-10-10T14:00:00Z')};}""")
            await T.show(pg, "HUBS", 100, "d", False)
            dq = "()=>{const e=document.getElementById('dqstrip');return {shown:e.style.display!=='none',txt:e.innerText,btn:!!document.getElementById('chipFreeBtn')};}"
            res["normal"] = await pg.evaluate(dq)
            await pg.evaluate("()=>{window.__tld=tjLastDone;tjLastDone=()=>'2026-10-12';axDqWait=()=>true;document.getElementById('cockpit').dataset.sig='';renderChips();}")
            await pg.wait_for_timeout(1500); res["waiting"] = await pg.evaluate(dq)
            await pg.evaluate("()=>{axDqWait=()=>false;document.getElementById('cockpit').dataset.sig='';renderChips();}")
            await pg.wait_for_timeout(1500); res["late"] = await pg.evaluate(dq)
            await pg.evaluate("()=>{tjLastDone=window.__tld;document.getElementById('cockpit').dataset.sig='';renderChips();}")
            await pg.wait_for_timeout(1500); res["back"] = await pg.evaluate(dq)
            res["errors"] = [e for e in errs if "Failed to load resource" not in e]
            await ctx.close()
        finally:
            srv.terminate()
        await br.close()
    W = res["wait"]
    res["ok"] = (W == {"et20": True, "et1559": False, "et1600": True, "et2259": True, "et2300": False, "nextday10": False}
                 and "不在追蹤清單" in res["normal"]["txt"] and res["normal"]["btn"]
                 and "還沒進來" in res["waiting"]["txt"] and "未更新" not in res["waiting"]["txt"] and res["waiting"]["btn"]
                 and "日K資料未更新" in res["late"]["txt"]
                 and "不在追蹤清單" in res["back"]["txt"] and "未更新" not in res["back"]["txt"] and not res["errors"])
    json.dump(res, open(OUT, "w"), ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False, indent=1)); print("OK" if res["ok"] else "NOT OK")

asyncio.run(main())
