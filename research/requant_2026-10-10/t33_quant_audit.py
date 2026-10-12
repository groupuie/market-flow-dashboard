# t33:📊量化 層稽核 —— 10/12 使用者:「順便檢查看看,『量化』有沒有出現失誤的修改」
#   比較 舊版 01b28d2(BUILD 07:45Z,我上一版)與 新版 88d3d24(BUILD 23:18Z,📍短線 v1.0 + 抄底不看資金)
#   13 檔 × 250 日,新開頁面、固定回應(重播 t32 的快照;最近已收盤日仍是 2026-10-09):
#     ① 新版「短線關」vs 舊版:量化記號(字、日期、強/弱、滑過說明)、狀態列、詳情 —— 哪些變了、為什麼
#     ② 新版「短線開」vs「短線關」:量化的字/說明應該完全相同(只有位置不同)
#     ③ 新版狀態列「接下來」那一行是否還寫著舊規則的字(「全球資金不夠寬鬆 → 先不抄底」)
#   用法:python3 t33_quant_audit.py <舊版 index.html> <新版 index.html> <快照資料夾>
import asyncio, json, os, sys, importlib.util
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("t32", os.path.join(HERE, "t32_refresh_test.py")); t32 = importlib.util.module_from_spec(spec); spec.loader.exec_module(t32)
from playwright.async_api import async_playwright

SYMS = t32.SYMS13
CAP = r"""()=>{const el=document.getElementById('cockpit');const T=(el&&el.data)||[];const txt=h=>String(h||'').replace(/<br>/g,' ⏎ ').replace(/<[^>]+>/g,'').replace(/\s+/g,' ').trim();
  const marks=[];T.filter(t=>/^量化/.test(t.name||'')&&t.name!=='量化盤中').forEach(t=>{const col=t.textfont&&t.textfont.color;
    t.y.forEach((v,i)=>{if(v==null||!String(t.text[i]||'').trim())return;const c=Array.isArray(col)?col[i]:col;
      marks.push({w:t.name.slice(2),x:String(t.x[i]),weak:c===QGRAY,text:txt(t.text[i]),hover:txt(t.customdata&&t.customdata[i])});});});
  marks.sort((a,b)=>a.x<b.x?-1:a.x>b.x?1:a.w<b.w?-1:1);
  const q=document.querySelector('#qstrip .sbar'),pop=q?txt(q._pop):'';
  const nextLine=(pop.match(/接下來:[^⏎]*/)||[''])[0], addLine=(pop.match(/加碼[^⏎]*/)||[''])[0];
  const sw=T.filter(t=>/^短線/.test(t.name||'')).length;
  return {build:BUILD,sym:CHIP_SYM,win:CHIP_WIN,sw:(typeof CHIP_SW!=='undefined')?CHIP_SW:null,swTraces:sw,marks:marks,qbar:q?txt(q.innerHTML):'',next:nextLine,add:addLine,pop:pop};}"""


async def run_page(browser, site, snap, tag, sw_off, out):
    r = t32.Router(snap, {}, "old")
    ctx, pg, errs = await t32.open_page(browser, site, r)
    res = {}
    try:
        await pg.evaluate("()=>{CHIP_WIN=250;}")
        if sw_off:
            await pg.click(".cidxchipW")
            for _ in range(20):
                await pg.wait_for_timeout(500)
                if await pg.evaluate("()=>CHIP_SW===false"):
                    break
        for s in SYMS:
            await t32.select_sym(pg, s)
            await pg.evaluate("()=>{CHIP_WIN=250;renderChips();}"); await pg.wait_for_timeout(2500)
            res[s] = await pg.evaluate(CAP)
        out[tag] = {"res": res, "errors": errs[:5]}
    finally:
        await ctx.close()


def key(m):
    return (m["x"], m["w"])


def report(out):
    O, N, NW = out["old"]["res"], out["new_swoff"]["res"], out["new_swon"]["res"]
    print(f"舊版 BUILD {O['SPY']['build']} / 新版 BUILD {N['SPY']['build']};錯誤 舊 {out['old']['errors']} 新(短線關) {out['new_swoff']['errors']} 新(短線開) {out['new_swon']['errors']}")
    print("\n① 新版(短線關)vs 舊版 —— 量化記號差異")
    tot_add = tot_rm = tot_chg = 0
    for s in SYMS:
        o = {key(m): m for m in O[s]["marks"]}; n = {key(m): m for m in N[s]["marks"]}
        added = [n[k] for k in n if k not in o]; removed = [o[k] for k in o if k not in n]
        changed = [(o[k], n[k]) for k in o if k in n and (o[k]["weak"] != n[k]["weak"] or o[k]["text"] != n[k]["text"])]
        hov = [k for k in o if k in n and o[k]["hover"] != n[k]["hover"] and o[k]["weak"] == n[k]["weak"]]
        tot_add += len(added); tot_rm += len(removed); tot_chg += len(changed)
        print(f"  {s}: 舊 {len(o)} 新 {len(n)} 記號 | 新增 {[(m['x'],m['w'],'弱' if m['weak'] else '強/一般') for m in added]} | 消失 {[(m['x'],m['w']) for m in removed]} | 強弱/字變 {[(a['x'],a['w'],a['weak'],b['weak']) for a,b in changed]} | 只有說明文字變 {len(hov)}")
        if O[s]["qbar"] != N[s]["qbar"]:
            print(f"     狀態列變:舊「{O[s]['qbar'][:70]}」→ 新「{N[s]['qbar'][:70]}」")
        if O[s]["next"] != N[s]["next"]:
            print(f"     接下來變:舊「{O[s]['next'][:90]}」→ 新「{N[s]['next'][:90]}」")
        if O[s]["add"] != N[s]["add"]:
            print(f"     加碼行變:舊「{O[s]['add'][:80]}」→ 新「{N[s]['add'][:80]}」")
    print(f"  合計:新增 {tot_add}、消失 {tot_rm}、強弱改變 {tot_chg}")
    print("\n② 新版 短線開 vs 短線關 —— 量化的字/說明/狀態列應相同")
    for s in SYMS:
        a = [(m["x"], m["w"], m["weak"], m["text"], m["hover"]) for m in N[s]["marks"]]
        b = [(m["x"], m["w"], m["weak"], m["text"], m["hover"]) for m in NW[s]["marks"]]
        print(f"  {s}: 記號相同={a==b} 狀態列相同={N[s]['qbar']==NW[s]['qbar']} 詳情相同={N[s]['pop']==NW[s]['pop']} 短線 traces={NW[s]['swTraces']}")
    print("\n③ 新版狀態列「接下來」還提到資金氣候的檔(抄底已不看資金):")
    for s in SYMS:
        nl = NW[s]["next"]
        if "資金" in nl or "抄底" in nl:
            print(f"  {s}: 狀態列「{NW[s]['qbar'][:60]}」| {nl[:120]}")
    print("\n④ 新版 抄底 記號(全部,含強弱與說明):")
    for s in SYMS:
        for m in NW[s]["marks"]:
            if m["w"] == "抄底":
                print(f"  {s} {m['x']} {'弱(灰)' if m['weak'] else '強(綠)'} | {m['hover'][:150]}")


async def main(old_file, new_file, snap):
    out = {}
    sites = {"old": t32.Site(old_file, 8811), "new": t32.Site(new_file, 8812)}
    try:
        async with async_playwright() as p:
            b = await p.chromium.launch(args=["--ignore-certificate-errors", "--proxy-server=" + os.environ.get("HTTPS_PROXY", ""), "--proxy-bypass-list=127.0.0.1;localhost"])
            await asyncio.gather(run_page(b, sites["old"], snap, "old", False, out),
                                 run_page(b, sites["new"], snap, "new_swoff", True, out),
                                 run_page(b, sites["new"], snap, "new_swon", False, out))
            await b.close()
    finally:
        for s in sites.values():
            s.close()
    json.dump(out, open(os.path.join(HERE, "t33_quant_audit.json"), "w"), ensure_ascii=False, indent=1)
    report(out)


if __name__ == "__main__":
    if sys.argv[1] == "report":
        report(json.load(open(os.path.join(HERE, "t33_quant_audit.json"))))
    else:
        asyncio.run(main(sys.argv[1], sys.argv[2], sys.argv[3]))
