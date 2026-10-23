#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SC1 資料層(v1.0):BEA 投入產出表 → French 49 產業的「誰賣給誰」流量表(只用表格,不碰任何股票報酬)。
用法:python3 -I sc_map.py SCRATCH
  SCRATCH/sc/bea/  = BEA AllTablesIO.zip 解出的兩個 Use 表(Before Redefinitions、生產者價格):
                     IOUse_Before_Redefinitions_PRO_2017_Detail.xlsx(細項 2007 / 2012 / 2017)
                     IOUse_Before_Redefinitions_PRO_1997-2023_Summary.xlsx(摘要 1997 ~ 2023)
  SCRATCH/sc/raw/  = Census 對照表:2017_to_2012_NAICS.xlsx、2012_to_2007_NAICS.xls、2007_to_2002_NAICS.xls、2002_NAICS_to_1987_SIC.xls
  SCRATCH/sc/x/Siccodes49.txt = French 49 產業的 SIC 範圍
  SCRATCH/sc/cbp/cbp12us.txt、cbp17us.txt = Census County Business Patterns 全國檔(2012、2017)
規則(PROTOCOL_SC1 §2):
  ① BEA 產業 → 它列出的 2017 NAICS 代碼(前綴展開成 6 碼);同一 BEA 產業內各 6 碼的權重 = County Business Patterns
     全國就業人數(表的參考年 ≥ 2017 用 CBP 2017,其餘用 CBP 2012;CBP 2012 是 2012 NAICS,換算到 2017 代碼時平分);
     CBP 沒有的代碼用同一 BEA 產業其他代碼的平均;整個 BEA 產業都沒有 CBP 資料 → 等權
  ② 6 碼 2017 NAICS → 2012 → 2007 → 2002 NAICS(每一步對到幾個就平分)
  ③ 2002 NAICS → 1987 SIC:每個 SIC 平分到它對到的所有 2002 NAICS(SIC 當成同樣大小的單位),再在 NAICS 內正規化
  ④ SIC → French 49(Siccodes49 範圍);對不到的(輔助單位、空集合、政府、不在任何範圍)另計「未分類」
  ⑤ A[BEA 產業, 49 產業] = 該 BEA 產業的權重(未分類以外的部分重新正規化成 1);未分類 > 50% 的 BEA 產業不用
  ⑥ 49 產業流量 F = Aᵀ U₀ A,U₀ = Use 表的中間使用(商品 × 產業),去掉同一個 BEA 代碼(對角線);
     商品代碼 = 生產它的 BEA 產業代碼(Before Redefinitions;不用 Make 表換算)
輸出:SCRATCH/sc/out/sc1_map_detail.csv、sc1_map_summary.csv、sc1_flows.npz、sc1_map_qa.json"""
import json, os, re, sys
from collections import defaultdict
import numpy as np, openpyxl, xlrd

ROOT = sys.argv[1]
BEA, RAW, OUT = (os.path.join(ROOT, "sc", x) for x in ("bea", "raw", "out")); os.makedirs(OUT, exist_ok=True)
DET = os.path.join(BEA, "IOUse_Before_Redefinitions_PRO_2017_Detail.xlsx")
SUM = os.path.join(BEA, "IOUse_Before_Redefinitions_PRO_1997-2023_Summary.xlsx")


def norm(c):
    if c is None:
        return ""
    if isinstance(c, float) and c.is_integer():
        c = int(c)
    return str(c).strip()


# ---------------- French 49 ----------------
def siccodes49(fn):
    inds, ranges = [], []
    for line in open(fn, encoding="latin-1").read().splitlines():
        m = re.match(r"^\s*(\d+)\s+(\S+)\s+(.*)$", line)
        if m and not re.match(r"^\s*\d{4}-\d{4}", line):
            inds.append((int(m.group(1)), m.group(2))); continue
        m = re.match(r"^\s*(\d{4})-(\d{4})", line)
        if m:
            ranges.append((int(m.group(1)), int(m.group(2)), inds[-1][0]))
    assert [i for i, _ in inds] == list(range(1, 50)), inds
    return [s for _, s in inds], ranges


FF, RANGES = siccodes49(os.path.join(ROOT, "sc", "x", "Siccodes49.txt"))


def sic_to_ff(sic):
    hit = [k for a, b, k in RANGES if a <= sic <= b]
    assert len(hit) <= 1, (sic, hit)
    return hit[0] if hit else None


# ---------------- NAICS 對照鏈 ----------------
def pairs_xls(fn, start):
    sh = xlrd.open_workbook(fn).sheet_by_index(0); out = []
    for i in range(start, sh.nrows):
        r = sh.row_values(i); out.append((norm(r[0]), norm(r[2])))
    return out


def pairs_xlsx(fn, start):
    ws = openpyxl.load_workbook(fn, read_only=True, data_only=True).worksheets[0]; out = []
    for i, r in enumerate(ws.iter_rows(values_only=True)):
        if i >= start:
            out.append((norm(r[0]), norm(r[2])))
    return out


def to_map(pairs, src_digits=6):
    m = defaultdict(list)
    for a, b in pairs:
        if a.isdigit() and len(a) == src_digits:
            m[a].append(b)
    return m


M17 = to_map(pairs_xlsx(os.path.join(RAW, "2017_to_2012_NAICS.xlsx"), 3))
M12 = to_map(pairs_xls(os.path.join(RAW, "2012_to_2007_NAICS.xls"), 3))
M07 = to_map(pairs_xls(os.path.join(RAW, "2007_to_2002_NAICS.xls"), 3))
M02 = to_map(pairs_xls(os.path.join(RAW, "2002_NAICS_to_1987_SIC.xls"), 1))
N17 = sorted(M17)
QA = {"2017 NAICS 6 碼數": len(N17), "鏈上斷掉": []}


def step(dist, M, label):
    out = defaultdict(float)
    for code, w in dist.items():
        tgt = [t for t in M.get(code, []) if t]
        if not tgt:
            QA["鏈上斷掉"].append((label, code)); out["UNASSIGNED"] += w; continue
        for t in tgt:
            out[t] += w / len(tgt)
    return out


# ③ 每個 SIC 平分到它對到的所有 2002 NAICS
SIC_SPLITS = defaultdict(set)
for n02, sics in M02.items():
    for s in sics:
        if s:
            SIC_SPLITS[s].add(n02)


def naics17_to_ff(n17):
    d = {n17: 1.0}; un = 0.0
    for M, lab in ((M17, "17→12"), (M12, "12→07"), (M07, "07→02")):
        d = step(d, M, lab); un += d.pop("UNASSIGNED", 0.0)
    out = defaultdict(float); out["UNASSIGNED"] = un
    for n02, w in d.items():
        sics = [s for s in M02.get(n02, []) if s]
        if not sics:
            QA["鏈上斷掉"].append(("02→SIC", n02)); out["UNASSIGNED"] += w; continue
        piece = {s: 1.0 / len(SIC_SPLITS[s]) for s in sics}; tot = sum(piece.values())
        for s, v in piece.items():
            k = sic_to_ff(int(s)) if s.isdigit() else None
            out[k if k else "UNASSIGNED"] += w * v / tot
    return dict(out)


FF_OF_N17 = {n: naics17_to_ff(n) for n in N17}


def expand(prefixes):
    codes = set()
    for p in prefixes:
        hit = [n for n in N17 if n.startswith(p)]
        if not hit:
            QA["鏈上斷掉"].append(("前綴展開", p))
        codes.update(hit)
    return sorted(codes)


# ① CBP 就業人數(6 碼、全部法律形式);有範圍旗標(數字被隱藏)的用範圍中點
FLAG_MID = {"A": 10, "B": 60, "C": 175, "E": 375, "F": 750, "G": 1750, "H": 3750, "I": 7500, "J": 17500, "K": 37500, "L": 75000, "M": 150000}


def cbp(fn):
    import csv
    emp = {}
    for x in csv.DictReader(open(fn, encoding="latin-1")):
        n = x["naics"]
        if x["lfo"] == "-" and n.isdigit() and len(n) == 6:
            e = int(x["emp"] or 0)
            emp[n] = float(e if e > 0 else FLAG_MID.get(x["empflag"], 0))
    return emp


CBP17 = cbp(os.path.join(ROOT, "sc", "cbp", "cbp17us.txt"))
_cbp12 = cbp(os.path.join(ROOT, "sc", "cbp", "cbp12us.txt"))
_n12_from = defaultdict(set)
for a, bs in M17.items():
    for b in bs:
        _n12_from[b].add(a)
CBP12 = {}
for a, bs in M17.items():                 # 2012 代碼的人數平分給它對到的 2017 代碼
    v = sum(_cbp12[b] / len(_n12_from[b]) for b in bs if b in _cbp12)
    if any(b in _cbp12 for b in bs):
        CBP12[a] = v
EMP = {"12": CBP12, "17": CBP17}
QA["CBP"] = {"2017 6 碼有人數": len(CBP17), "2012(換到 2017 代碼)有人數": len(CBP12)}


def weights(codes, emp):
    """一組 6 碼 2017 NAICS(就業人數加權)→ 49 產業權重(未分類以外正規化)與未分類比例"""
    if not codes:
        return None, None
    have = [emp[n] for n in codes if n in emp and emp[n] > 0]
    if have:
        fill = sum(have) / len(have); wn = {n: (emp[n] if n in emp and emp[n] > 0 else fill) for n in codes}
    else:
        wn = {n: 1.0 for n in codes}
    tw = sum(wn.values()); acc = defaultdict(float)
    for n in codes:
        for k, w in FF_OF_N17[n].items():
            acc[k] += w * wn[n] / tw
    un = acc.pop("UNASSIGNED", 0.0); tot = sum(acc.values())
    if tot <= 1e-12 or un > 0.5:
        return None, un
    return {k: v / tot for k, v in acc.items() if v > 0}, un


# ---------------- BEA 產業清單 ----------------
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sc_bea_parse import naics_sheet  # noqa: E402

SUMMS, DETS = naics_sheet(DET)
for x in DETS:
    x["n6"] = expand(x["prefixes"])
by_s = defaultdict(set)
for x in DETS:
    by_s[x["summary"]].update(x["n6"])
A = {}                                     # A[("D"|"S", "12"|"17")] = {BEA 代碼: {49 產業: 權重}}
rows_det, rows_sum = [], []


def fmt(w):
    return "" if not w else "; ".join(f"{FF[k - 1]}:{v:.3f}" for k, v in sorted(w.items(), key=lambda z: -z[1]))


for cy in ("12", "17"):
    A[("D", cy)] = {}; A[("S", cy)] = {}
    for x in DETS:
        w, un = weights(x["n6"], EMP[cy])
        if w:
            A[("D", cy)][x["detail"]] = w
        if cy == "17":
            top = max(w, key=w.get) if w else None
            w12, _ = weights(x["n6"], EMP["12"])
            rows_det.append([x["summary"], x["detail"], x["title"], len(x["n6"]), "" if un is None else round(un, 4),
                             "" if not w else FF[top - 1], "" if not w else round(w[top], 4), fmt(w), fmt(w12)])
    for s, title in SUMMS.items():
        codes = sorted(by_s.get(s, [])); w, un = weights(codes, EMP[cy])
        if w:
            A[("S", cy)][s] = w
        if cy == "17":
            top = max(w, key=w.get) if w else None
            w12, _ = weights(codes, EMP["12"])
            rows_sum.append([s, title, len(codes), "" if un is None else round(un, 4), "" if not w else FF[top - 1],
                             "" if not w else round(w[top], 4), fmt(w), fmt(w12)])


def write_csv(fn, hdr, rows):
    import csv
    with open(os.path.join(OUT, fn), "w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f); wr.writerow(hdr); wr.writerows(rows)


write_csv("sc1_map_detail.csv", ["summary", "detail", "title", "naics6_n", "unassigned_share_cbp17", "top_ff49_cbp17", "top_w_cbp17",
                                 "ff49_weights_cbp17", "ff49_weights_cbp12"], rows_det)
write_csv("sc1_map_summary.csv", ["summary", "title", "naics6_n", "unassigned_share_cbp17", "top_ff49_cbp17", "top_w_cbp17",
                                  "ff49_weights_cbp17", "ff49_weights_cbp12"], rows_sum)


# ---------------- Use 表 ----------------
def use_table(ws_rows, code_row, data_row0):
    rows = ws_rows; codes = [norm(c) for c in rows[code_row]]
    # 產業欄 = 第 3 欄起、直到第一個最終需求 / 合計欄
    ind_cols = []
    for j in range(2, len(codes)):
        c = codes[j]
        if c == "" or c.startswith("T0") or re.match(r"^F0|^F1", c):
            break
        ind_cols.append(j)
    out_col = None
    U = {}; comm = []; tco = {}
    # 找「Total Commodity Output」欄(標題列或代碼列)
    for rr in (rows[code_row - 1], rows[code_row], rows[code_row + 1] if code_row + 1 < len(rows) else []):
        for j, c in enumerate(rr):
            if norm(c).lower() in ("total commodity output", "t007"):
                out_col = j
    for r in rows[data_row0:]:
        c = norm(r[0])
        if c == "" or c.startswith("T0") or re.match(r"^V0", c):
            break
        comm.append(c)
        for j in ind_cols:
            v = r[j] if j < len(r) else None
            if isinstance(v, (int, float)) and v != 0:
                U[(c, codes[j])] = float(v)
        if out_col is not None and isinstance(r[out_col], (int, float)):
            tco[c] = float(r[out_col])
    return U, comm, [codes[j] for j in ind_cols], tco


def ff_flows(U, inds, A, tco):
    """F[k,l] = Σ_{c≠j} A[c,k] U[c,j] A[j,l](百萬美元);同時回傳 QA"""
    F = np.zeros((49, 49)); tot = 0.0; kept = 0.0; diag_io = 0.0
    out_ff = np.zeros(49)
    for (c, j), v in U.items():
        tot += v
        if c == j:
            diag_io += v; continue
        a, b = A.get(c), A.get(j)
        if not a or not b:
            continue
        kept += v
        for k, wa in a.items():
            for l, wb in b.items():
                F[k - 1, l - 1] += wa * wb * v
    for c, v in tco.items():
        a = A.get(c)
        if a:
            for k, wa in a.items():
                out_ff[k - 1] += wa * v
    off = F.sum() - np.trace(F)
    qa = {"中間使用合計(百萬)": round(tot), "同一 BEA 代碼(去掉)占比": round(diag_io / tot, 4), "兩端都對到 49 產業占比": round(kept / tot, 4),
          "其中跨 49 產業占比": round(off / tot, 4), "產業欄數": len(inds), "有總產出的商品數": len(tco)}
    return F, out_ff, qa


wb = openpyxl.load_workbook(DET, read_only=True, data_only=True)
flows = {}; QA["表"] = {}
def cbp_year(y):
    return "17" if int(y) >= 2017 else "12"


for y in ("2007", "2012", "2017"):
    rows = list(wb[y].iter_rows(values_only=True))
    U, comm, inds, tco = use_table(rows, 5, 6)
    F, outv, qa = ff_flows(U, inds, A[("D", cbp_year(y))], tco)
    flows[f"D{y}"] = F; flows[f"D{y}_out"] = outv; QA["表"][f"細項 {y}"] = qa | {"商品列數": len(comm), "CBP": "20" + cbp_year(y)}
wb2 = openpyxl.load_workbook(SUM, read_only=True, data_only=True)
for y in wb2.sheetnames:
    rows = list(wb2[y].iter_rows(values_only=True))
    U, comm, inds, tco = use_table(rows, 5, 7)
    F, outv, qa = ff_flows(U, inds, A[("S", cbp_year(y))], tco)
    flows[f"S{y}"] = F; flows[f"S{y}_out"] = outv; QA["表"][f"摘要 {y}"] = qa | {"商品列數": len(comm), "CBP": "20" + cbp_year(y)}
np.savez_compressed(os.path.join(OUT, "sc1_flows.npz"), **flows)

# 49 產業覆蓋:每個 49 產業從幾個 BEA 細項 / 摘要產業拿到權重(權重合計 = 「等值產業數」)
cov = {}
for k in range(1, 50):
    row = {}
    for lv, cy in (("D", "12"), ("D", "17"), ("S", "12"), ("S", "17")):
        m = [w[k] for w in A[(lv, cy)].values() if k in w]
        row[f"{'細項' if lv == 'D' else '摘要'}{cy} 個數 / 等值"] = [len(m), round(sum(m), 2)]
    cov[FF[k - 1]] = row
QA["49 產業覆蓋"] = cov
QA["鏈上斷掉"] = sorted(set(map(tuple, QA["鏈上斷掉"])))
QA["細項產業"] = {"總數": len(DETS), "對到 49 產業(CBP17)": len(A[("D", "17")]), "對到 49 產業(CBP12)": len(A[("D", "12")]),
                 "對不到(CBP17)": [x["detail"] for x in DETS if x["detail"] not in A[("D", "17")]]}
QA["摘要產業"] = {"總數": len(SUMMS), "對到 49 產業(CBP17)": len(A[("S", "17")]), "對不到(CBP17)": [s for s in SUMMS if s not in A[("S", "17")]]}
json.dump(QA, open(os.path.join(OUT, "sc1_map_qa.json"), "w"), ensure_ascii=False, indent=1)
print(json.dumps({k: QA[k] for k in ("2017 NAICS 6 碼數", "細項產業", "摘要產業")}, ensure_ascii=False, indent=1))
print("斷掉:", QA["鏈上斷掉"][:30], len(QA["鏈上斷掉"]))
for k, v in QA["表"].items():
    print(k, v)
