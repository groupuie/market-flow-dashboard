# t34:狀態列「接下來」那一行(跌深中)改字的驗收 —— 抄底已不看資金氣候,這行原本還寫「全球資金不夠寬鬆 → 先不抄底」
#   ① 13 檔新開頁面(固定回應):舊版 88d3d24 vs 新版 —— 量化記號、狀態列、詳情除了這一行以外要完全相同
#   ② 四個分支都走一次(BKNG 現在正是「跌深中」:近 20 天曾比 50 日線低 18.7%、收盤在 20 日線下):
#      a. 大盤沒回檔 1 成(現況)→ 「→ 抄底(大盤沒回檔 1 成 → 灰色、較弱…)」
#      b. 假裝大盤已回檔 1 成(fcMktOf 回 COR bit)→ 「→ 抄底」
#      c. 假裝前 20 根已站回過(fcSeriesJS anyClim 版回傳 lb = 最後一根)→ 「但前 20 天已經站回過一次」
#      d. 假裝跌幅只有 12%(dip 介於 10–15%)→ 「跌幅未到 15%,站回只算反彈,不標抄底」
#      b–d 是測試用的猴子補丁,只為了走到那個分支;正式畫面的字由 ① 驗。
#   用法:python3 t34_nextline_test.py <舊版 index.html> <新版 index.html> <快照資料夾>
import asyncio, json, os, sys, importlib.util
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("t32", os.path.join(HERE, "t32_refresh_test.py")); t32 = importlib.util.module_from_spec(spec); spec.loader.exec_module(t32)
spec2 = importlib.util.spec_from_file_location("t33", os.path.join(HERE, "t33_quant_audit.py")); t33 = importlib.util.module_from_spec(spec2); spec2.loader.exec_module(t33)
from playwright.async_api import async_playwright
SYMS = t32.SYMS13
RERENDER = "()=>{document.getElementById('cockpit').dataset.sig='';renderChips();}"


async def run(browser, site, snap, tag, out):
    r = t32.Router(snap, {}, "old")
    ctx, pg, errs = await t32.open_page(browser, site, r)
    res = {}
    try:
        await pg.evaluate("()=>{CHIP_WIN=250;}")
        for s in SYMS:
            await t32.select_sym(pg, s)
            await pg.evaluate("()=>{CHIP_WIN=250;renderChips();}"); await pg.wait_for_timeout(2500)
            res[s] = await pg.evaluate(t33.CAP)
        br = {}
        if tag == "new":
            await t32.select_sym(pg, "BKNG")
            br["a_現況"] = (await pg.evaluate(t33.CAP))["next"]
            await pg.evaluate("()=>{window.__f0=fcMktOf;fcMktOf=d=>(window.__f0(d)|QM.COR);}"); await pg.evaluate(RERENDER); await pg.wait_for_timeout(1500)
            br["b_大盤已回檔1成"] = (await pg.evaluate(t33.CAP))["next"]
            await pg.evaluate("()=>{fcMktOf=window.__f0;window.__s0=fcSeriesJS;fcSeriesJS=(B,o)=>{const x=window.__s0(B,o);if(o&&o.anyClim)x.lb=x.n-1;return x;};}"); await pg.evaluate(RERENDER); await pg.wait_for_timeout(1500)
            br["c_前20根站回過"] = (await pg.evaluate(t33.CAP))["next"]
            await pg.evaluate("()=>{fcSeriesJS=(B,o)=>{const x=window.__s0(B,o);if(!(o&&o.anyClim))x.dip[x.n-1]=-0.12;return x;};}"); await pg.evaluate(RERENDER); await pg.wait_for_timeout(1500)
            br["d_跌幅只有12%"] = (await pg.evaluate(t33.CAP))["next"]
            await pg.evaluate("()=>{fcSeriesJS=window.__s0;}")
        out[tag] = {"res": res, "branches": br, "errors": errs[:5]}
    finally:
        await ctx.close()


def report(out):
    O, N = out["old"]["res"], out["new"]["res"]
    print(f"舊版 BUILD {O['SPY']['build']} / 新版 BUILD {N['SPY']['build']};錯誤 舊 {out['old']['errors']} 新 {out['new']['errors']}")
    same_marks = same_bar = same_pop_ex = 0; changed_next = []
    for s in SYMS:
        a = [(m["x"], m["w"], m["weak"], m["text"], m["hover"]) for m in O[s]["marks"]]; b = [(m["x"], m["w"], m["weak"], m["text"], m["hover"]) for m in N[s]["marks"]]
        same_marks += a == b; same_bar += O[s]["qbar"] == N[s]["qbar"]
        po, pn = O[s]["pop"].replace(O[s]["next"], ""), N[s]["pop"].replace(N[s]["next"], "")
        same_pop_ex += po == pn
        if O[s]["next"] != N[s]["next"]:
            changed_next.append((s, O[s]["next"][:110], N[s]["next"][:110]))
    print(f"① 13 檔:量化記號相同 {same_marks}/13、狀態列相同 {same_bar}/13、詳情(扣掉「接下來」那行)相同 {same_pop_ex}/13")
    print(f"   「接下來」有變的檔:{len(changed_next)}")
    for s, o, n in changed_next:
        print(f"   {s}: 舊「{o}」\n         新「{n}」")
    print("② BKNG 四個分支:")
    for k, v in out["new"]["branches"].items():
        print(f"   {k}: {v[:140]}")


async def main(old_file, new_file, snap):
    out = {}
    sites = {"old": t32.Site(old_file, 8821), "new": t32.Site(new_file, 8822)}
    try:
        async with async_playwright() as p:
            b = await p.chromium.launch(args=["--ignore-certificate-errors", "--proxy-server=" + os.environ.get("HTTPS_PROXY", ""), "--proxy-bypass-list=127.0.0.1;localhost"])
            await asyncio.gather(run(b, sites["old"], snap, "old", out), run(b, sites["new"], snap, "new", out))
            await b.close()
    finally:
        for s in sites.values():
            s.close()
    json.dump(out, open(os.path.join(HERE, "t34_nextline_test.json"), "w"), ensure_ascii=False, indent=1)
    report(out)


if __name__ == "__main__":
    if sys.argv[1] == "report":
        report(json.load(open(os.path.join(HERE, "t34_nextline_test.json"))))
    else:
        asyncio.run(main(sys.argv[1], sys.argv[2], sys.argv[3]))
