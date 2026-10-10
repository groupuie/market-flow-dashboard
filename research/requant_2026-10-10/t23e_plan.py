# t23e:把「加碼」做成可照做的步驟 —— 隔天開盤買(使用者在台灣看不到美股收盤)、之後最多再跌多少、
# 第二筆掛低幾 % 會成交、加碼後多久、低波動股(像 TSM)和全部股票比較;同樣看「只有個股跌」對照。
from t23_dip import *
from t10lib import _pm
FRo={h:FR[h].values for h in (10,20,40)}                          # 隔天開盤進場 → 第 h 天收盤(log)
O1v=O.shift(-1).values; Lv=L.values; Cv=C.values; n=len(dates)
# 隔天開盤買之後 20 天內最低(從隔天起算,含隔天)
Lmin20=L[::-1].rolling(20,min_periods=20).min()[::-1].shift(-1).values
Lmin10=L[::-1].rolling(10,min_periods=10).min()[::-1].shift(-1).values
dd20=Lmin20/O1v-1
rsi40=(R14<=40)&(R14.shift(1)>40); lob=(L<=lo)&above_n(L,lo,10)
SIGS={"加碼:RSI14 跌破 40 + 大盤也跌":rsi40&qdip,"加碼:碰布林下緣 + 大盤也跌":lob&qdip,
      "對照:RSI14 跌破 40,只有個股跌":rsi40&~qdip,"對照:碰布林下緣,只有個股跌":lob&~qdip}
LOWV=(VQ<=0.5).values
def baseline(state,a,b,lowv):
    pm=_pm(a,b); ok=state.values&pm[:,None]&~np.isnan(FRo[20])&(LOWV if lowv else True)
    I,J=np.nonzero(ok); y=(FRo[20][I,J]>0).astype(float)
    cnt=np.bincount(J,minlength=len(cols)); sm=np.bincount(J,weights=y,minlength=len(cols)); bs=np.full(len(cols),np.nan)
    bs[cnt>=40]=sm[cnt>=40]/cnt[cnt>=40]; return bs,y.mean()
for stname,state in {"穩健上升":UTS,"上升趨勢":UT}.items():
    for lowv in (False,True):
        print(f"\n######## {stname}{' · 低波動(像 TSM)' if lowv else ' · 全部'}:隔天開盤買")
        for per,(a,b) in {"2009–17":("2009-07-01","2017-12-31"),"2018–26":("2018-01-01","2026-12-31")}.items():
            bs,b20=baseline(state,a,b,lowv); pm=_pm(a,b)
            print(f"  [{per}] 同樣趨勢裡隨便一天隔天開盤買:20 天後較高 {b20*100:.0f}%")
            for nm,s in SIGS.items():
                M=first(s.fillna(False).astype(bool)&state,10).values&pm[:,None]&~np.isnan(FRo[20])&(LOWV if lowv else True)
                I,J=np.nonzero(M)
                if len(I)<20: print(f"    {nm:24s} n={len(I)} 太少"); continue
                u10=(FRo[10][I,J]>0).mean(); u20=(FRo[20][I,J]>0).mean(); m4=~np.isnan(FRo[40][I,J]); u40=(FRo[40][I,J][m4]>0).mean()
                med20=np.median(np.exp(FRo[20][I,J])-1); dd=dd20[I,J]; dd=dd[~np.isnan(dd)]
                q=np.percentile(dd,[50,25,10])        # 中位數、較差的 1/4、較差的 1/10(負數 = 再跌)
                f3=np.mean(dd<=-0.03); f5=np.mean(dd<=-0.05); f8=np.mean(dd<=-0.08)
                # 兩筆加碼:一半隔天開盤、一半掛低 5%(20 天內成交,否則第 20 天收盤補進)→ 平均成本 vs 一次買
                p1=O1v[I,J]; lim=p1*0.95; got=Lmin20[I,J]<=lim; C20=Cv[np.minimum(I+20,n-1),J]
                p2=np.where(got,lim,C20); avg=(p1+p2)/2; save=np.nanmean(avg/p1-1)
                print(f"    {nm:24s} n={len(I):4d} | 20天後較高 {u20*100:.0f}%(同股平常 {np.nanmean(bs[J])*100:.0f}%) 10天 {u10*100:.0f}% 40天 {u40*100:.0f}% | 20天中位數 {med20*100:+.1f}%"
                      f" | 之後 20 天內最多再跌:一半的時候 ≤{-q[0]*100:.1f}%、1/4 的時候 ≥{-q[1]*100:.1f}%、1/10 ≥{-q[2]*100:.1f}% | 再跌 ≥3% {f3*100:.0f}% ≥5% {f5*100:.0f}% ≥8% {f8*100:.0f}%"
                      f" | 一半開盤+一半掛低5%:平均成本 {save*100:+.1f}%(掛單成交 {got.mean()*100:.0f}%)",flush=True)
# TSM:隔天開盤買
print("\n######## TSM(上升趨勢)2023 年後:隔天開盤買")
j=cols.index("TSM")
for nm,s in SIGS.items():
    M=first(s.fillna(False).astype(bool)&UT,10)[cols[j]].values; rows=[]
    for t in np.flatnonzero(M):
        if dates[t]<pd.Timestamp("2023-01-01") or t+1>=n: continue
        P=O1v[t,j]; f=lambda h: f"{(Cv[t+1+h-1,j]/P-1)*100:+5.1f}%" if t+h<n else "  –  "
        d_=(np.nanmin(Lv[t+1:t+21,j])/P-1)*100
        rows.append(f"{dates[t].date()} 訊號 → 隔天開盤 {P:7.2f} | 10天{f(10)} 20天{f(20)} 40天{f(40)} | 之後最多再跌 {d_:+.1f}%")
    print(f"  ■ {nm}({len(rows)} 次)"); [print("     "+r) for r in rows]
