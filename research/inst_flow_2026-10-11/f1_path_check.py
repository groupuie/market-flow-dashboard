# 回應 Astra v0.4 §2:f1 兩條程式路徑實際影響幾筆(a)開盤缺值用收盤補(b)分組前先要求未來報酬存在。只讀 f1 前半段,不改 f1 結果。
import os, numpy as np, pandas as pd
HERE='/home/claude/market-flow-dashboard/research/inst_flow_2026-10-11'
src=open(os.path.join(HERE,'f1_finra_short.py'),encoding='utf-8').read().split("OUT = {")[0]
ns={'__file__':os.path.join(HERE,'f1_finra_short.py')}; exec(compile(src,'f1_head','exec'),ns)
dates,cols,n,m=ns['dates'],ns['cols'],ns['n'],ns['m']; i_lo,i_hi=ns['i_lo'],ns['i_hi']
# 原始(未補值)開盤
raw={}
for s in cols:
    df=pd.read_pickle(os.path.join(ns['DT'],'yh',s+'.pkl')); df=df[df.index>=ns['START']]
    f=(df['ac']/df['c']).replace([np.inf,-np.inf],np.nan).fillna(1.0); raw[s]=(df['o']*f).reindex(ns['cal'])
RO=pd.DataFrame(raw)[cols].values
bad_open=np.isnan(RO)|(RO<=0)
for h in (10,40):
    q,_,_,_=ns['quint'](ns['SIG']['SVR5'],h)
    grouped=(q>=0)
    ent=np.zeros_like(grouped); ent[:-1]=bad_open[1:]   # 第 t+1 天開盤是補的
    k=int((grouped&ent).sum()); N=int(grouped.sum())
    print(f'h={h}: 分組的股票日 {N};進場開盤(t+1)是用收盤補的 {k} 筆({k/N*100:.3f}%)')
    S=ns['SIG']['SVR5'].values; G=ns['GH'][h].values
    sel=np.zeros(n,bool); sel[i_lo:i_hi+1]=True
    sigok=~np.isnan(S)&sel[:,None]
    miss=sigok&np.isnan(G)
    print(f'   訊號有值但 h={h} 結果缺 → 沒進分組 {int(miss.sum())} 筆 / 訊號有值 {int(sigok.sum())} 筆;涉及 {len(set(np.nonzero(miss)[1]))} 檔;'
          f'日期 {str(dates[np.nonzero(miss)[0].min()].date()) if miss.any() else "-"}~{str(dates[np.nonzero(miss)[0].max()].date()) if miss.any() else "-"}')
    if miss.any():
        js=np.nonzero(miss)[1]; import collections
        print('   最多的檔:',collections.Counter(np.array(cols)[js]).most_common(8))
C=ns['C'].values; O=ns['O'].values
for h in (10,40):
    S=ns['SIG']['SVR5'].values; G=ns['GH'][h].values
    sel=np.zeros(n,bool); sel[i_lo:i_hi+1]=True
    miss=(~np.isnan(S))&sel[:,None]&np.isnan(G)
    has_close=miss&~np.isnan(C)
    I,J=np.nonzero(has_close)
    print(f'h={h}: 結果缺的 {int(miss.sum())} 筆中,訊號日 t 當天有收盤價的 {len(I)} 筆')
    import collections
    print('   ', collections.Counter((cols[j], str(dates[i].date())[:7]) for i,j in zip(I,J)).most_common(12))
