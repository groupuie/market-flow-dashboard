# ◆減碼(TOP≥3)/ ★抄底(BOT≥3)深入重驗:哪些情境、哪個期限、哪個成分有用
import sys; sys.path.insert(0,"."); from qlib import *
F=FE; sc=F["sc"].astype("float64"); rv=F["rvpos"].astype("float64"); tds=F["tds"].astype("float64"); tdb=F["tdb"].astype("float64")
volr5=F["volr5"].astype("float64"); volr=F["volr"].astype("float64")
TOPc={"sc=100":sc==100,"RV≥90":rv>=90,"TD賣9":tds>=9,"量5≥1.5":volr5>=1.5}
BOTc={"TD買9":tdb>=9,"RV≥80":rv>=80,"殺量竭盡":(volr>=1.75)&(C<C.shift(5)),"sc<66":sc<66}
TOP=sum(v.astype(int) for v in TOPc.values()).where(sc.notna()); BOT=sum(v.astype(int) for v in BOTc.values()).where(sc.notna())
dia=(TOP>=3); star=(BOT>=3)
dia1=cool(dia,20); star1=cool(star,20)
def line(tag,sig,side,hs=(5,10,20,40),entry="open"):
    s=f"{tag:30s}"
    for per in ("p1","p2"):
        s+=f" | {per}"
        for h in hs:
            r=evaluate(sig,side,per,h,vmatch=(h==20 and side=='top'),entry=entry)
            s+=f" {h}d {r['hit']-r['base']:+4.1f}/{r['mean']-r['bmean']:+5.2f}"
            if h==20 and side=="top": s+=f" 跌≥10%:{r['risk']:.0f}vs{r['risk_base']:.0f}"
            if h==20 and side=="bot": s+=f" 再跌≥10%:{r['risk']:.0f}"
        s+=f" n={r['n']}"
    print(s,flush=True)
print("格式:期限 命中差(百分點)/平均報酬差(%)  — p1=2009-17, p2=2018-26")
print("=== ◆減碼(賣出方向:命中=之後下跌)");line("◆ 每天",dia,"top");line("◆ 首日(冷卻20)",dia1,"top")
print("=== ★抄底(買進方向:命中=之後上漲)");line("★ 每天",star,"bot");line("★ 首日(冷卻20)",star1,"bot")
print("=== 2024-10→2026-07(當初 298檔×2年 的期間)")
for tag,sig,side in (("◆首日",dia1,"top"),("★首日",star1,"bot")):
    for h in (10,20):
        r=evaluate(sig,side,("2024-10-01","2026-07-31"),h,vmatch=(side=="top"))
        print(f"  {tag} {h}日: n={r['n']} 命中 {r['hit']:.1f}% vs {r['base']:.1f}%  平均 {r['mean']:+.2f}% vs {r['bmean']:+.2f}%"+(f"  跌≥10% {r['risk']:.0f}% vs 同波動 {r['risk_base']:.0f}%" if side=='top' else f"  再跌≥10% {r['risk']:.0f}%"),flush=True)
print("=== 情境:全球資金");
for lo,hi,nm in ((0,0.35,"氣候≤35%"),(0.35,0.65,"35–65%"),(0.65,1.01,"≥65%")):
    m=(CL>=lo)&(CL<hi); line("◆首日 "+nm,dia1&m,"top"); line("★首日 "+nm,star1&m,"bot")
print("=== 情境:長期趨勢(200日線上/下)")
up200=C>C.rolling(200).mean()
line("◆首日 200日線上",dia1&up200,"top");line("◆首日 200日線下",dia1&~up200,"top")
line("★首日 200日線上(漲勢中回檔)",star1&up200,"bot");line("★首日 200日線下(跌勢中)",star1&~up200,"bot")
print("=== AI/半導體子集")
ai=[c for c in cols if c in AI]
for tag,sig,side in (("◆首日 AI",dia1,"top"),("★首日 AI",star1,"bot")):
    s=f"{tag:30s}"
    for per in ("p1","p2"):
        r=evaluate(sig,side,per,20,cs=ai,vmatch=False); s+=f" | {per} 20d {r['hit']-r['base']:+4.1f}/{r['mean']-r['bmean']:+5.2f} n={r['n']}"
    print(s,flush=True)
print("=== 單一成分(首日,冷卻20)")
for k,v in TOPc.items(): line("◆成分 "+k,cool(v.where(sc.notna(),False),20),"top",hs=(10,20))
for k,v in BOTc.items(): line("★成分 "+k,cool(v.where(sc.notna(),False),20),"bot",hs=(10,20))
print("=== 4 個全中")
line("◆ TOP=4",cool(TOP>=4,20),"top"); line("★ BOT=4",cool(BOT>=4,20),"bot")
print("=== 確認版:◆後3天內收盤跌破◆那天低點 / ★後3天內收盤站上★那天高點(確認日進場)")
dL=L.where(dia1).ffill(limit=3); dconf=cool((C<dL.shift(1))&dia1.rolling(4).max().shift(1).fillna(0).astype(bool),20)
sH=H.where(star1).ffill(limit=3); sconf=cool((C>sH.shift(1))&star1.rolling(4).max().shift(1).fillna(0).astype(bool),20)
line("◆ → 3天內跌破低點",dconf,"top"); line("★ → 3天內站上高點",sconf,"bot")
print("=== 四段期間 20日命中差:◆首日",sub4(dia1,"top",20)," ★首日",sub4(star1,"bot",20))
