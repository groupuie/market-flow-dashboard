# s2:2026-10-16 總檢查的網頁修正驗收(舊版 0679caa vs 新版;本機伺服器 + 固定回應 + 撥時鐘)
#   三個快照(都是 gist 真實歷史檔;備援檔用 10/15 23:01Z 那份,只改時間戳模擬當時的新舊):
#   A「Mac 剛恢復、全量輪沒跑完」:gist 91f93b2(10/16 07:49 台灣 推的 market_data:ts 很新,報價/期權停在 10/14)+ 備援 23:01Z;時鐘 10/15 23:50Z
#      預期:新版報價改用備援(NVDA 217.23,舊版 221.3)、徽章轉黃、說明列講「全量更新卡住」;QQQ 日K檔停在 10/13 + 快照 10/15 → 新版黃條「少了 10-14」
#   B「正常」:gist 9611817(10/14 18:51Z 盤中,期權 21 分前)+ 備援改成 4 小時前;時鐘 10/14 18:53Z
#      預期:新舊版 DATA 公開區塊、徽章、說明列、K 線圖 traces 全部相同(改版不能動到正常情況)
#   C「Mac 離線、備援也舊」:gist 3c1f8c5(10/15 07:15 台灣 最後一推)+ 備援改成 10/15 16:51Z;時鐘 10/15 19:00Z(美東 15:00 盤中)
#      預期:徽章相同(資料偏舊);新版說明列多一句「Mac 離線 X 小時;雲端備援上次更新在 Y 前(GitHub 排程…)」
#   D「全量輪正常、只是期權用快取 2 小時」:gist 36b494e(10/08 04:09Z,_options_cached=True、期權 137 分前)+ 備援改成 10/08 03:00Z(比期權新);時鐘 10/08 04:10Z
#      預期:新舊版完全相同(有標快取就不拿 _options_ts 判斷 → 不切備援;10/08 那時全量輪每 ~22 分照常完成)
#   用法:python3 s2_page_test.py <舊版 index.html> <新版 index.html> <快照根目錄(內含 snapA/snapB/snapC)>
import asyncio, json, os, sys, hashlib, importlib.util, datetime as dt
HERE = os.path.dirname(os.path.abspath(__file__))
T32 = os.path.join(os.path.dirname(HERE), "requant_2026-10-10", "t32_refresh_test.py")
spec = importlib.util.spec_from_file_location("t32", T32); t32 = importlib.util.module_from_spec(spec); spec.loader.exec_module(t32)
from playwright.async_api import async_playwright
CASES = {"A": "2026-10-15T23:50:00Z", "B": "2026-10-14T18:53:00Z", "C": "2026-10-15T19:00:00Z", "D": "2026-10-08T04:10:00Z"}
SYMS = ["QQQ", "NVDA"]
GLOB = r"""()=>{const s=document.getElementById('status'),u=document.getElementById('updated');
  const h=o=>o==null?null:JSON.stringify(o);
  return {build:BUILD,now:new Date().toISOString(),badge:s.className+' | '+s.textContent,meta:u.textContent,
    macSlow:DATA._macSlow===undefined?null:DATA._macSlow,macSlowAge:DATA._macSlowAge==null?null:Math.round(DATA._macSlowAge),
    macAge:Math.round(DATA._macAge),pubAge:Math.round(DATA._pubAge),session:DATA.session,
    nvda:(DATA.stocks&&DATA.stocks.NVDA||{}).last,qqq:(DATA.market&&DATA.market.QQQ||{}).last,ktQQQ:((DATA.kline_today||{}).QQQ||[])[0],
    pubBlocks:['market','stocks','leveraged','options','fx','rates','rates_live','crypto','commodities','darkpool','dp_daily','cash_pool','kline_today','capital_flow','session','ts_utc'].map(k=>k+':'+(h(DATA[k])||'').length+':'+(h(DATA[k])||'').slice(0,40)).join('|')};}"""
SYMCAP = r"""(s)=>{const el=document.getElementById('cockpit');const T=(el&&el.data)||[];
  const A=v=>v==null?null:Array.from(v).map(z=>z==null?null:(typeof z==='number'?+z.toFixed(6):String(z)));
  const tr=JSON.stringify(T.map(t=>({n:t.name||'',x:A(t.x),y:A(t.y),c:A(t.close),tx:Array.isArray(t.text)?A(t.text):null})));
  const dq=document.getElementById('dqstrip');const cs=T.find(t=>t.type==='candlestick');
  return {sym:s,dq:(dq&&dq.style.display!=='none')?dq.innerText.replace(/\s+/g,' ').trim():'',tr:tr,lastX:cs?A(cs.x).slice(-3):[]};}"""


async def run(browser, page_file, port, snap, when, tag, out, mobile=False):
    site = t32.Site(page_file, port)
    try:
        off = int((dt.datetime.fromisoformat(when.replace("Z", "+00:00")).timestamp() - dt.datetime.now(dt.timezone.utc).timestamp()) * 1000)
        r = t32.Router(snap, {}, "old")
        kw = dict(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, device_scale_factor=2) if mobile else dict(viewport={"width": 1920, "height": 1080})
        ctx = await browser.new_context(ignore_https_errors=True, service_workers="block", **kw)
        await ctx.add_init_script(t32.INIT_JS)
        await ctx.add_init_script("window.__t32.setOff(%d);" % off)
        for h in t32.GIST_HOSTS:
            await ctx.route(f"https://{h}/**", r.handle)
        pg = await ctx.new_page(); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
        await pg.goto(f"http://127.0.0.1:{port}/index.html", wait_until="domcontentloaded", timeout=120000)
        for _ in range(150):
            if await pg.evaluate("()=>!!document.querySelector('#cockpit .plot-container')&&typeof DATA!=='undefined'&&!!DATA&&!DATA._partial"): break
            await pg.wait_for_timeout(1000)
        await pg.wait_for_timeout(3000)
        res = {"glob": await pg.evaluate(GLOB), "syms": {}}
        for s in SYMS:
            await t32.select_sym(pg, s)
            await pg.evaluate("()=>{renderChips();}"); await pg.wait_for_timeout(2500)
            c = await pg.evaluate(SYMCAP, s); c["trHash"] = hashlib.sha256(c.pop("tr").encode()).hexdigest()[:16]
            res["syms"][s] = c
        if mobile:
            await pg.screenshot(path=os.path.join(HERE, f"s2_{tag}.png"))
        res["errors"] = errs
        out[tag] = res
        await ctx.close()
    finally:
        site.close()


async def main(old_file, new_file, root):
    out = {}
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--ignore-certificate-errors", "--proxy-server=" + os.environ.get("HTTPS_PROXY", ""), "--proxy-bypass-list=127.0.0.1;localhost"])
        port = 8861
        for case, when in CASES.items():
            snap = os.path.join(root, "snap" + case)
            await asyncio.gather(run(b, old_file, port, snap, when, case + "_old", out), run(b, new_file, port + 1, snap, when, case + "_new", out))
            port += 2
        await run(b, new_file, port, os.path.join(root, "snapA"), CASES["A"], "A_new_mobile", out, mobile=True)
        await b.close()
    json.dump(out, open(os.path.join(HERE, "s2_page_test.json"), "w"), ensure_ascii=False, indent=1)
    for case in CASES:
        O, N = out[case + "_old"], out[case + "_new"]
        print(f"=== {case}(時鐘 {CASES[case]})錯誤 舊 {O['errors']} 新 {N['errors']}")
        for k in ("badge", "macSlow", "macSlowAge", "macAge", "pubAge", "session", "nvda", "qqq", "ktQQQ"):
            print(f"  {k}: 舊 {O['glob'].get(k)!r} → 新 {N['glob'].get(k)!r}")
        print(f"  meta 舊:{O['glob']['meta']}\n  meta 新:{N['glob']['meta']}")
        print(f"  公開區塊 新舊相同 = {O['glob']['pubBlocks'] == N['glob']['pubBlocks']}")
        for s in SYMS:
            o, n = O["syms"][s], N["syms"][s]
            print(f"  {s}: K線 traces 相同 = {o['trHash'] == n['trHash']}  末三根 {n['lastX']}\n      dq 舊「{o['dq'][:90]}」\n      dq 新「{n['dq'][:150]}」")
    M = out["A_new_mobile"]
    print(f"=== 手機 A 新版:錯誤 {M['errors']};徽章 {M['glob']['badge']};QQQ dq「{M['syms']['QQQ']['dq'][:80]}」")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], sys.argv[2], sys.argv[3]))
