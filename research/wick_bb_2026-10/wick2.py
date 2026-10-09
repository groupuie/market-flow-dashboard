import numpy as np, pandas as pd, pickle, warnings; warnings.filterwarnings("ignore")
exec(open("wick.py").read().split("sigs={")[0])
s50=C.rolling(50).mean(); ext=C/s50-1
w=touch&(uw>=1/3)
# (b) 隔天確認:訊號日次日收盤 < 訊號日最低 → 以確認日收盤起算
conf=w.shift(1,fill_value=False)&(C<L.shift(1))
nup=(C>C.shift(1)).astype(int); run=nup.groupby((nup==0).cumsum()).cumsum() if False else nup.apply(lambda c:c.groupby((c==0).cumsum()).cumsum())
V2={
 "上影≥1/3 & 拉離50日線≥15%":w&(ext>=0.15),
 "上影≥1/3 & 拉離50日線≥25%":w&(ext>=0.25),
 "上影≥1/3 & 連漲≥5日":w&(run.shift(1)>=5),
 "上影≥1/3 → 次日收破其低點(確認)":conf,
 "上影≥1/3 & 拉離≥15% → 次日收破其低點":(w&(ext>=0.15)).shift(1,fill_value=False)&(C<L.shift(1)),
 "對照:拉離50日線≥15%(任何一天)":(ext>=0.15),
}
for per in ("07-17","18-26"):
    print("=====",per)
    for nm,sg in V2.items(): print(line(nm,ev(sg,per=per,boot_h=5)))
