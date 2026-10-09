import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
from evalx import *
L=load_long(); set_dateidx(L)
star=(L.BOT>=3); dia=(L.TOP>=3)
for per in ("IS","OOS"):
    print("=====",per)
    for nm,sig,side in (("★抄底 BOT>=3",star,"bot"),("◆減碼 TOP>=3",dia,"top"),("all days (bot)",L.r1.notna(),"bot")):
        for ep in (True,False):
            r=stats(L,sig,per,side,ep=ep); show(nm+(" [ep]" if ep else " [all]"),r)
    print("★ ep f20 CI:",cluster_ci(L,star,per,"f20","bot"), " ◆ ep CI:",cluster_ci(L,dia,per,"f20","top"))
