# 解析 SEC Form 4 季度資料集 → 我們 259 檔的「公開市場買進(P)/賣出(S)」逐筆紀錄(以申報日=公開日為準)
import zipfile, json, glob, os, numpy as np, pandas as pd
DL="/tmp/claude-0/-home-claude/d0a676e0-fcd7-5eae-bc26-2609f6d7a033/scratchpad/dl"
OUT="/tmp/claude-0/-home-claude/d0a676e0-fcd7-5eae-bc26-2609f6d7a033/scratchpad/dt/insider_ps.pkl"
meta=json.load(open("/tmp/claude-0/-home-claude/d0a676e0-fcd7-5eae-bc26-2609f6d7a033/scratchpad/dt/meta.json"))
eq=[s for s,v in meta.items() if v.get("type")=="EQUITY"]
tc=json.load(open(DL+"/edgar/ticker_cik.json"))
cik2t={}
for s in eq:
    c=tc.get(s.replace("-",".")) or tc.get(s)
    if c: cik2t[int(c)]=s
print("tickers with CIK:",len(cik2t),"of",len(eq))
rows=[]
for fn in sorted(glob.glob(DL+"/form345/*_form345.zip")):
    z=zipfile.ZipFile(fn)
    rd=lambda n,cols: pd.read_csv(z.open(n),sep="\t",usecols=lambda c: c in cols,dtype=str,on_bad_lines="skip",quoting=3,low_memory=False)
    sub=rd("SUBMISSION.tsv",{"ACCESSION_NUMBER","FILING_DATE","DOCUMENT_TYPE","ISSUERCIK","AFF10B5ONE"})
    if "AFF10B5ONE" not in sub.columns: sub["AFF10B5ONE"]=None
    sub=sub[sub.DOCUMENT_TYPE.isin(["4","4/A"])]
    sub["cik"]=pd.to_numeric(sub.ISSUERCIK,errors="coerce")
    sub=sub[sub.cik.isin(cik2t.keys())]
    acc=set(sub.ACCESSION_NUMBER)
    own=rd("REPORTINGOWNER.tsv",{"ACCESSION_NUMBER","RPTOWNERCIK","RPTOWNER_RELATIONSHIP","RPTOWNER_TITLE"})
    own=own[own.ACCESSION_NUMBER.isin(acc)].drop_duplicates("ACCESSION_NUMBER")
    tr=rd("NONDERIV_TRANS.tsv",{"ACCESSION_NUMBER","TRANS_DATE","TRANS_CODE","TRANS_SHARES","TRANS_PRICEPERSHARE","TRANS_ACQUIRED_DISP_CD","SHRS_OWND_FOLWNG_TRANS","DIRECT_INDIRECT_OWNERSHIP"})
    tr=tr[tr.ACCESSION_NUMBER.isin(acc)&tr.TRANS_CODE.isin(["P","S"])]
    m=tr.merge(sub[["ACCESSION_NUMBER","FILING_DATE","cik","AFF10B5ONE"]],on="ACCESSION_NUMBER").merge(own,on="ACCESSION_NUMBER",how="left")
    rows.append(m); print(os.path.basename(fn),len(sub),len(m),flush=True)
D=pd.concat(rows,ignore_index=True)
D["tk"]=D.cik.map(cik2t)
D["fd"]=pd.to_datetime(D.FILING_DATE,format="%d-%b-%Y",errors="coerce")
D["td"]=pd.to_datetime(D.TRANS_DATE,format="%d-%b-%Y",errors="coerce")
for c,n in (("TRANS_SHARES","sh"),("TRANS_PRICEPERSHARE","px"),("SHRS_OWND_FOLWNG_TRANS","post")): D[n]=pd.to_numeric(D[c],errors="coerce")
D["val"]=D.sh*D.px
rel=D.RPTOWNER_RELATIONSHIP.fillna("")
D["is_dir"]=rel.str.contains("Director",case=False); D["is_off"]=rel.str.contains("Officer",case=False); D["is_10"]=rel.str.contains("TenPercent",case=False)
t=D.RPTOWNER_TITLE.fillna("").str.upper()
D["ceo_cfo"]=t.str.contains("CEO|CHIEF EXECUTIVE|CFO|CHIEF FINANCIAL|PRESIDENT|CHAIRMAN")
D["plan"]=D.AFF10B5ONE.fillna("").str.strip().str.lower().isin(["1","true","y","yes"])
keep=["tk","fd","td","TRANS_CODE","sh","px","val","post","is_dir","is_off","is_10","ceo_cfo","plan","RPTOWNERCIK","DIRECT_INDIRECT_OWNERSHIP","ACCESSION_NUMBER"]
D=D[keep].rename(columns={"TRANS_CODE":"code","RPTOWNERCIK":"owner","DIRECT_INDIRECT_OWNERSHIP":"di","ACCESSION_NUMBER":"acc"})
D=D.dropna(subset=["fd","tk"]).drop_duplicates()
D.to_pickle(OUT)
print("rows",len(D),D.code.value_counts().to_dict(),"tickers",D.tk.nunique(),"range",D.fd.min(),D.fd.max())
print("plan flag share (2023+):",D[D.fd>="2023-04-01"].plan.mean())
