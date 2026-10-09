import pickle, numpy as np, pandas as pd, time, warnings; warnings.filterwarnings("ignore")
from lib import DT
t0=time.time()
S=pickle.load(open(DT+"/stock.pkl","rb")); M=pd.read_pickle(DT+"/market.pkl"); I=pd.read_pickle(DT+"/idx_targets.pkl")
F,T,P=S["F"],S["T"],S["P"]
C=P["C"]
mask=(C.index>="2006-07-01")
cols={}
for k,v in list(F.items())+list(T.items()):
    cols[k]=v[mask].stack(future_stack=True) if hasattr(v,"stack") else None
L=pd.DataFrame(cols)
L=L[L["sc"].notna() & L["r1"].notna()]
L.index.names=["date","sym"]
print("rows",len(L),"%.0fs"%(time.time()-t0))
# baseline same-stock means over full sample (for excess metrics)
for h in (5,10,20):
    L[f"x{h}"]=L[f"f{h}"]-I[f"SPY_f{h}"].reindex(L.index.get_level_values(0)).values   # excess vs SPY same window
L.to_pickle(DT+"/long.pkl")
print("saved", L.shape, "%.0fs"%(time.time()-t0), "mem %.0fMB"%(L.memory_usage().sum()/1e6))
