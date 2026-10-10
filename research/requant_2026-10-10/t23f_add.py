# t23f:上線版「加」的確切定義 → 統計(給 tooltip)+「類似的股票也能用嗎?」(低/高波動、AI/非 AI、四段)
#   ①上升趨勢(前一天):收盤 > 200 日線、50 日線 > 200 日線、200 日線比 20 天前高
#   ②RSI14 收盤跌破 40(前一天 > 40)或 第一次碰布林下緣(前 10 天最低都在下緣上)
#   ③QQQ 收盤 < 20 日線。同一段只標第一天(前 10 根成立過就不標)。隔天開盤買。
#   另查:前 10/20 天內有「出」時的「加」(會不會互相打架)。
from t23_dip import *
from t10lib import _pm
SUB4=[("2009-07-01","2013-12-31"),("2014-01-01","2018-12-31"),("2019-01-01","2022-12-31"),("2023-01-01","2026-12-31")]
PER=[("2009–17",("2009-07-01","2017-12-31")),("2018–26",("2018-01-01","2026-12-31")),("近兩年",("2024-10-01","2026-12-31"))]
rsi40=(R14<=40)&(R14.shift(1)>40); lob=(L<=lo)&above_n(L,lo,10)
RAW_ALL=(rsi40|lob)&UT                                  # 不看大盤
ADD=first(RAW_ALL&qdip,10); ONLY=first(RAW_ALL&~qdip,10)
CHU=X.astype(bool)                                      # 出(t1x_cands:漲多跌破20日線 × 資金偏緊)
u20=(FR[20]>0).values.astype(float); val=~np.isnan(FR[20].values); O1v=O.shift(-1).values; Cv=C.values; n=len(dates)
Lmin20=L[::-1].rolling(20,min_periods=20).min()[::-1].shift(-1).values
VQv=VQ.values; AIv=AIc.values
def sbase(a,b,mask=None):
    pm=_pm(a,b); ok=UT.values&pm[:,None]&val
    if mask is not None: ok&=mask
    I,J=np.nonzero(ok); cnt=np.bincount(J,minlength=len(cols)); sm=np.bincount(J,weights=u20[I,J],minlength=len(cols))
    bs=np.full(len(cols),np.nan); bs[cnt>=40]=sm[cnt>=40]/cnt[cnt>=40]; return bs
def row(nm,S,mask,per_list=PER):
    line=f"  {nm:22s}"
    for per,(a,b) in per_list:
        pm=_pm(a,b); M=S.values&pm[:,None]&val&(mask if mask is not None else True); I,J=np.nonzero(M)
        if len(I)<15: line+=f" | {per} n={len(I)}"; continue
        bs=sbase(a,b,mask); d=u20[I,J]-bs[J]
        line+=f" | {per} {u20[I,J].mean()*100:.0f}%(平常 {np.nanmean(bs[J])*100:.0f}%,{np.nanmean(d)*100:+.1f},n{len(I)})"
    print(line,flush=True)
GROUPS={"全部":None,"低波動(像 TSM)":VQv<=0.5,"高波動":VQv>0.5,"AI/半導體":AIv,"非 AI":~AIv}
print("### 上線版「加」(大盤也跌)vs 只有個股跌 —— 隔天開盤買,20 天後比買價高(括號=同一檔上升趨勢裡隨便一天)")
for g,m in GROUPS.items():
    print(f"[{g}]"); row("加(大盤也跌)",ADD,m); row("對照:只有個股跌",ONLY,m)
print("\n### 四段期間(全部 / 低波動)")
for g in ("全部","低波動(像 TSM)"):
    row(f"加 · {g}",ADD,GROUPS[g],[(f"四段{k+1}",ab) for k,ab in enumerate(SUB4)])
print("\n### 第二筆掛多低?(2018–26,隔天開盤買一半,另一半掛低 X%,20 天內沒成交就第 20 天收盤補)")
a,b=PER[1][1]; pm=_pm(a,b)
for g,m in GROUPS.items():
    M=ADD.values&pm[:,None]&val&(m if m is not None else True); I,J=np.nonzero(M); p1=O1v[I,J]; lw=Lmin20[I,J]; C20=Cv[np.minimum(I+20,n-1),J]
    dd=lw/p1-1; q=np.nanpercentile(dd,[50,25])
    s=f"  {g:12s} n={len(I):4d} 之後最多再跌:一半 ≤{-q[0]*100:.1f}%、1/4 ≥{-q[1]*100:.1f}%"
    for X_ in (0.03,0.05,0.08,0.10):
        lim=p1*(1-X_); got=lw<=lim; avg=(p1+np.where(got,lim,C20))/2
        s+=f" | 掛低{int(X_*100)}%:成交 {np.nanmean(got)*100:.0f}% 平均成本 {np.nanmean(avg/p1-1)*100:+.1f}%"
    print(s,flush=True)
print("\n### 前面剛出過「出」的「加」(會不會打架)—— 2009–26 全部")
a,b=("2009-07-01","2026-12-31"); pm=_pm(a,b); bs=sbase(a,b)
for k in (10,20):
    rc=anyN(CHU,k).shift(1).fillna(False).astype(bool).values
    for tag,mm in (("前面有出",rc),("前面沒有出",~rc)):
        M=ADD.values&pm[:,None]&val&mm; I,J=np.nonzero(M); d=u20[I,J]-bs[J]
        print(f"  前 {k} 天{tag}:n={len(I)} 20 天後較高 {u20[I,J].mean()*100:.0f}%(同股平常 {np.nanmean(bs[J])*100:.0f}%,{np.nanmean(d)*100:+.1f})")
print("\n### 每檔每年幾次(上升趨勢的股票,2018–26)")
a,b=PER[1][1]; pm=_pm(a,b); yrs=(UT.values&pm[:,None]&val).sum()/252
print(f"  加:{(ADD.values&pm[:,None]&val).sum()/yrs:.2f} 次 / 檔 / 上升趨勢年")
print("\n### TSM、NVDA、AAPL、MU、AVGO、LITE 2024 年後的「加」(隔天開盤買)")
for sym in ("TSM","NVDA","AAPL","MU","AVGO","LITE","META","MSFT"):
    if sym not in cols: continue
    j=cols.index(sym); rows=[]
    for t in np.flatnonzero(ADD[sym].values):
        if dates[t]<pd.Timestamp("2024-01-01") or t+1>=n: continue
        P=O1v[t,j]; f=lambda h: f"{(Cv[t+h,j]/P-1)*100:+5.1f}%" if t+h<n else "  –  "
        rows.append(f"{dates[t].date()} 開{P:8.2f} 20天{f(20)} 40天{f(40)} 最多再跌{(np.nanmin(L.values[t+1:t+21,j])/P-1)*100:+.1f}%")
    print(f"  ■ {sym}({len(rows)} 次)"); [print("     "+r) for r in rows]
