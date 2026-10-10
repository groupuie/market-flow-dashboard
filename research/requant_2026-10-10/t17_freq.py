# t17:改了之後「標記頻率」與「準確率」會怎樣?—— 現行每種記號,按提案分成 強/一般/弱(灰),看各組數量與準確率;
#      另算提案「新增」與「拿掉/變灰」的數量。期間:後段 2018–26、近兩年 2024-10 起;前段 2009–17 參考。
import sys; sys.path.insert(0,"."); from t1x_cands import *; from t10lib import _sel, _pm
M=samp
qmax=Q.c.rolling(252,min_periods=60).max(); COR=Q.c<=qmax*0.9; VIXH=vix>=20
QB20=Q.c<q20; MAC=OILW|YDROP; BIGDN=ret1<=-0.04; PRETK=anyN(TK.shift(1),20)
PER={"前段2009-17":("2009-07-01","2017-12-31"),"後段2018-26":("2018-01-01","2026-12-31"),"近兩年2024-10起":("2024-10-01","2026-12-31")}
def styrs(a,b): pm=_pm(a,b); return C.loc[pm].notna().values.sum()/252
def grp(d,mk,side,a,b):
    sel=_sel(d,20,(a,b))&mk; f=d.f20.values[sel]; n_all=int(((d.date>=a)&(d.date<=b)).values[mk].sum())
    hit=((f<0) if side=="top" else (f>0)).mean()*100 if len(f) else np.nan
    return n_all,hit,len(f)
def table(title,d,side,groups):
    print(f"\n### {title}")
    for pn,(a,b) in PER.items():
        sy=styrs(a,b); base_=base(side,d.attrs["entry"],20,(a,b))
        tot=grp(d,np.ones(len(d),bool),side,a,b)
        s=f"  {pn}: 全部 {tot[0]:5d} 次(每檔每年 {tot[0]/sy:.2f})準 {tot[1]:4.1f}%(平常 {base_:.1f}%)"
        for gname,mk in groups:
            g=grp(d,mk,side,a,b); share=g[0]/max(1,tot[0])*100
            s+=f" | {gname} {g[0]:4d}({share:3.0f}%)準 {g[1]:4.1f}%" if g[2]>=8 else f" | {gname} {g[0]:4d}({share:3.0f}%)準 —"
        print(s,flush=True)
def extra(title,sig,ent,side,groups=None):
    d=ev(sig,ent)
    for pn,(a,b) in PER.items():
        sy=styrs(a,b); g=grp(d,np.ones(len(d),bool),side,a,b)
        print(f"  {title} {pn}: {g[0]:5d} 次(每檔每年 {g[0]/sy:.2f})準 {g[1]:4.1f}%(平常 {base(side,ent,20,(a,b)):.1f}%)",flush=True)

print("每檔每年 = 次數 ÷ (股票數×年);準 = 20 個交易日後方向對(賣:比較低;買:比較高)")
# 出
d=ev(X,"open"); mac,px=M(MAC,d),M(BIGDN|PRETK,d)
table("出(現行)→ 強=總經或價格任一(最強=兩者都有)、弱=都沒有",d,"top",[("最強",mac&px),("強(任一)",mac|px),("弱(灰)",~(mac|px))])
# 頂K
d=ev(TK,"close"); qb,ai=M(QB20,d),M(AIc,d)
table("頂K(現行)→ 強=大盤QQQ在20日線下;弱=AI股且大盤在線上",d,"top",[("強",qb),("一般",~qb&~ai),("弱(灰)",~qb&ai),("AI且大盤線下",qb&ai)])
# 減碼
d=ev(CF,"close"); qb,y,ai=M(QB20,d),M(YDROP,d),M(AIc,d)
table("減碼(現行)→ 強=QQQ線下或殖利率急降",d,"top",[("強",qb|y),("其他",~(qb|y)),("其中AI",~(qb|y)&ai)])
# 抄底
CD=BUY_BASES["抄底"][0]
d=ev(CD,"open"); c,v,c35=M(COR,d),M(VIXH,d),M(cr>=0.35,d)
table("抄底(現行:資金≥80%)→ 強=大盤回檔≥10%;弱=個股自己跌(沒回檔且VIX<20)",d,"bot",[("強",c),("一般",~c&v),("弱(灰)",~c&~v)])
print("\n### 提案「新增」的記號")
extra("新「出」:頂K破線(資金不緊時)",XR&BIGDN&PRETK&(CL>0.35),"open","top")
DIP=BUY_BASES["深跌站回(不看資金)"][0]
deep15=rel50.rolling(20).min()<=-0.15
extra("新「抄底」:深跌站回 + 大盤回檔≥10% + 資金35–80%",DIP&deep15&pd.DataFrame(np.repeat(COR.reindex(dates).fillna(False).values[:,None],len(cols),axis=1),index=dates,columns=cols)&(CL>=0.35)&(CL<0.80),"open","bot")
