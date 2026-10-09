import json, urllib.request, urllib.parse, os, pandas as pd
DT="/tmp/claude-0/-home-claude/d0a676e0-fcd7-5eae-bc26-2609f6d7a033/scratchpad/dt"
UA={"User-Agent":"Mozilla/5.0"}
TFF={"ES":"13874A","NQ":"209742","RTY":"239742","ZN":"043602","ZT":"042601","ZF":"044601","ZB":"020601","VX":"1170E1","JY":"097741","SPC":"13874+","NDC":"20974+"}
DIS={"CL":"067651","GC":"088691","SI":"084691","HG":"085692"}
def pull(ds, code, fields):
    rows=[]; off=0
    while True:
        url=f"https://publicreporting.cftc.gov/resource/{ds}.json?"+urllib.parse.urlencode({"$where":f"cftc_contract_market_code='{code}'","$select":",".join(["report_date_as_yyyy_mm_dd"]+fields),"$order":"report_date_as_yyyy_mm_dd","$limit":50000,"$offset":off})
        r=json.load(urllib.request.urlopen(urllib.request.Request(url,headers=UA),timeout=120))
        rows+=r
        if len(r)<50000: break
        off+=50000
    df=pd.DataFrame(rows); df["date"]=pd.to_datetime(df.pop("report_date_as_yyyy_mm_dd")).dt.normalize()
    for f in fields: df[f]=pd.to_numeric(df[f],errors="coerce")
    return df.groupby("date").sum().sort_index()
tf=["open_interest_all","dealer_positions_long_all","dealer_positions_short_all","asset_mgr_positions_long","asset_mgr_positions_short","lev_money_positions_long","lev_money_positions_short","nonrept_positions_long_all","nonrept_positions_short_all"]
df_=["open_interest_all","prod_merc_positions_long","prod_merc_positions_short","swap_positions_long_all","swap__positions_short_all","m_money_positions_long_all","m_money_positions_short_all"]
out={}
for k,c in TFF.items():
    out[k]=pull("gpe5-46if",c,tf); print(k,len(out[k]),out[k].index[0].date(),out[k].index[-1].date())
for k,c in DIS.items():
    out[k]=pull("72hh-3qpy",c,df_); print(k,len(out[k]),out[k].index[0].date(),out[k].index[-1].date())
pd.to_pickle(out,os.path.join(DT,"cot.pkl"))
