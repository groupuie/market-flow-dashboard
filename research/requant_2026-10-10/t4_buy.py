# 「買」(技判手冊 v0.2 三條路徑)— 長歷史只能測「價格部分」(⑦資金流只有幾個月);另補:頂K 拿掉漲多條件
import sys; sys.path.insert(0,"."); from qlib import *
m20=C.rolling(20).mean(); sd=C.rolling(20).std(ddof=0); up=m20+2*sd; lo=m20-2*sd; pb=(C-lo)/(up-lo); bw=(up-lo)/m20
sqz=bw<=bw.rolling(60,min_periods=1).min()
s50=C.rolling(50).mean(); trend=(C>s50)&(s50>s50.shift(10))
def runcount(cond): return cond.astype(int).apply(lambda c: c.groupby((c==0).cumsum()).cumsum())
tdb=runcount(C<C.shift(4)); tds=runcount(C>C.shift(4))
anyN=lambda X,n: X.astype(int).rolling(n,min_periods=1).max().astype(bool)
pT=trend&anyN(tdb>=6,10)&anyN((pb<=0.35)|sqz,10)
pC=(~trend)&((pb<=0.2)|sqz)&anyN(tdb>=9,5)
pD=anyN(tdb>=9,10)&anyN(C<lo,10)&(C>lo)
first=lambda X: X&~X.shift(1).fillna(False).astype(bool)
for nm,s in (("買-趨勢路徑(價格部分)",first(pT)),("買-循環路徑(價格部分)",first(pC)),("買-災後路徑(價格部分)",first(pD)),("買-任一路徑",first(pT)|first(pC)|first(pD))):
    for h in (10,20,40): report(nm,s,"bot",h,boot=300 if h==20 else 0)
    print("   四段期間 20日命中差:",sub4(s,"bot",20),flush=True)
    for lo_,hi_,tag in ((0,0.35,"氣候≤35%"),(0.35,0.65,"中性"),(0.65,1.01,"氣候≥65%")):
        mm=(CL>=lo_)&(CL<hi_); r1=evaluate(s&mm,"bot","p1",20,vmatch=False); r2=evaluate(s&mm,"bot","p2",20,vmatch=False)
        print(f"   {nm} × {tag}: 20日命中差 p1 {r1['hit']-r1['base']:+.1f}(n{r1['n']}) p2 {r2['hit']-r2['base']:+.1f}(n{r2['n']})",flush=True)
print("=== 頂K 拿掉「漲多」條件(只看碰上緣+收盤離高≥5%)",flush=True)
tr=np.maximum(H-L,np.maximum((H-C.shift()).abs(),(L-C.shift()).abs()))
nohot=(H>=up)&(1-C/H>=0.05)
report("碰上緣+離高5%(不管漲多)",nohot,"top",20,boot=300,entry="close"); report("頂K(現行)",topk(),"top",20,boot=300,entry="close")
