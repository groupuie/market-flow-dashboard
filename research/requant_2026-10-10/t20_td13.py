# t20:使用者問「台積電已經 TD13 了,為何沒有減碼/出」→ TD 賣方連數到 9 / 13(收盤連續高於 4 天前)之後,真的比較會跌嗎?
#     圖上的 13 = setup 一路數到 13(不是 DeMark 的 countdown 13)。另測「數到 ≥13 後中斷那天」(像 TSM 10-08)。
import sys; sys.path.insert(0,"."); from t1x_cands import *; from t10lib import _sel, _pm
up=(C>C.shift(4)).astype(int)
tds=up.groupby((up==0).cumsum()).cumsum() if False else up.apply(lambda c: c.groupby((c==0).cumsum()).cumsum())
prevmax=tds.shift(1)
S9=(tds==9); S13=(tds==13); S20=(tds==20)
BRK13=(tds==0)&(prevmax>=13)          # 數到 ≥13 之後第一天中斷
BRK9=(tds==0)&(prevmax>=9)&(prevmax<13)
def line(lab,sig,ent="open"):
    d=ev(sig,ent); s=f"  {lab:34s}"
    for per in ("p1","p2"):
        r=hit(d,np.ones(len(d),bool),"top",20,per,boot=400); r4=hit(d,np.ones(len(d),bool),"top",40,per,boot=0)
        c=f"[{r['ci'][0]:+.0f},{r['ci'][1]:+.0f}]" if not np.isnan(r['ci'][0]) else ""
        s+=f" | {per} n={r['n']:5d} 20日後較低 {r['hit']:4.1f}%(平常{r['base']:4.1f},差{r['hit']-r['base']:+5.1f}{c}) 40日 {r4['hit']:4.1f}% 均{r['mean']:+5.1f}%"
    s4=[]
    for a,b in SUB4:
        r=hit(d,np.ones(len(d),bool),"top",20,(a,b),boot=0); s4.append("  —" if r["n"]<10 else f"{r['hit']-r['base']:+4.0f}")
    print(s+" | 四段 "+" ".join(s4),flush=True)
print("TD 賣方 setup(收盤連續高於 4 天前)→ 之後 20 個交易日比較低的比例(賣出方向)")
line("數到 9 那天",S9); line("數到 13 那天",S13); line("數到 20 那天",S20)
line("數到 9–12 之後中斷那天",BRK9); line("數到 ≥13 之後中斷那天(像 TSM 10-08)",BRK13)
line("數到 13 那天 × 資金偏緊",S13&(CL<=0.35)); line("數到 ≥13 後中斷 × 資金偏緊",BRK13&(CL<=0.35))
line("數到 ≥13 後中斷 × 前 20 天有頂K",BRK13&anyN(TK.shift(1),20))
