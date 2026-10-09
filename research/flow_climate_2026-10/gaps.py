import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
from evalx import *
L=load_long(); set_dateidx(L)
gz=L.gap/L.sd60
def run(nm,sig,side):
    for per in ("IS","OOS"):
        r=stats(L,sig,per,side,ep=True); 
        print(f"{nm:52s} {per:3s} n={r['n']:5d} hit10={r['hit10']:.1f}/{r['base10']:.1f} hit20={r['hit20']:.1f}/{r['base20']:.1f} mu20={r['mu20']:+.2f}/{r['bmu20']:+.2f} exs20={r['exs20']:+.2f} xSPY={r['x20']:+.2f} mae={r['mae20']:.1f}")
run("gap-up >=2.5sd & vol>=3x & close>=open", (gz>=2.5)&(L.volr>=3)&(L.ibs>=0.5)&(L.r1>L.gap), "bot")
run("gap-up >=2.5sd & vol>=3x & faded (close<open)", (gz>=2.5)&(L.volr>=3)&(L.r1<L.gap), "top")
run("gap-down <=-2.5sd & vol>=3x & close<=open", (gz<=-2.5)&(L.volr>=3)&(L.r1<=L.gap), "top")
run("gap-down <=-2.5sd & vol>=3x & recovered(close>open)", (gz<=-2.5)&(L.volr>=3)&(L.r1>L.gap), "bot")
run("up day z1>=2.5 & vol>=2.5x (no big gap)", (L.z1>=2.5)&(L.volr>=2.5)&(gz.abs()<1), "bot")
run("down day z1<=-2.5 & vol>=2.5x (no big gap)", (L.z1<=-2.5)&(L.volr>=2.5)&(gz.abs()<1), "top")
run("down day z1<=-2.5 & LOW vol (<1.2x)", (L.z1<=-2.5)&(L.volr<1.2), "bot")
run("5d drop z5<=-2 on low vol (volr5<1.1)", (L.z5<=-2)&(L.volr5<1.1), "bot")
run("5d drop z5<=-2 on high vol (volr5>=1.8)", (L.z5<=-2)&(L.volr5>=1.8), "bot")
run("new 252d high & vol>=2x", (L.dd252>=-0.001)&(L.volr>=2), "bot")
