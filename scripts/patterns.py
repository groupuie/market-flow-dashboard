#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
型態辨識引擎鏡像 — ZigZag + 古典型態 + 蠟燭型態(純 stdlib;2026-08-01 P4)
**純規則、非生成式**:ZigZag(depth/deviation/backstep)產生交替轉折序列,再以硬規則比對
頭肩頂/逆頭肩、雙重頂/底、三角(對稱/上升/下降)、楔形、旗形、杯柄;每條驗證條件寫進 why[]。
與 webapp/index.html 的 zigzag()/classicPatterns()/candlePatterns() 同演算法同參數。

輸出(寫入 computed_tech.patterns):
  [{type,state:"forming"|"confirmed",dir,pivots:[{d,px,role}],neckline?/edges?,target?,
    broken_d?,why:[...],score,asof}]
狀態語意:forming=結構成形但未破頸線/邊線;confirmed=已突破;invalidated(創新極值)不輸出。
用法(獨立測試):python3 patterns.py --kline-dir data --symbols NOW,MU [--win 200]
"""
import json, os, math, argparse

TL_WIN = 200      # 鏡像駕駛艙預設視窗
LEAD   = 252      # cockpitRows 前置根數

def _jround(x):
    return int(math.floor(x + 0.5))

# ---------------- 4A ZigZag ----------------
def zigzag(R, opt=None):
    """百分比反轉主迴圈 + depth/backstep 後處理(移除小擺動→同型鄰居合併取極值,保證交替且保序)"""
    opt = opt or {}
    N = len(R)
    if N < 20: return []
    atr = 0.0; cnt = 0
    for a in range(max(1, N - 14), N):
        atr += max(R[a]["h"] - R[a]["l"], abs(R[a]["h"] - R[a-1]["c"]), abs(R[a]["l"] - R[a-1]["c"]))
        cnt += 1
    atr = atr / cnt if cnt else 0.0
    px = R[N-1]["c"]
    # 最小擺動幅度=1.5×ATR14/價,夾在 3%–8%(高波動期不設上限會抹平所有結構;實測 MU/SNDK)
    dev = opt.get("dev", max(0.03, min(0.08, 1.5 * atr / max(px, 1e-9))))
    depth = opt.get("depth", 5)
    backstep = opt.get("backstep", 3)
    min_sep = max(depth, backstep)
    piv = []; direction = 0; ext_i = 0; ext_p = R[0]["c"]
    for i in range(1, N):
        if direction == 0:
            if (R[i]["h"] - ext_p) / ext_p >= dev: direction = 1; ext_p = R[i]["h"]; ext_i = i
            elif (ext_p - R[i]["l"]) / ext_p >= dev: direction = -1; ext_p = R[i]["l"]; ext_i = i
        elif direction == 1:
            if R[i]["h"] > ext_p: ext_p = R[i]["h"]; ext_i = i
            elif (ext_p - R[i]["l"]) / ext_p >= dev:
                piv.append({"i": ext_i, "d": R[ext_i]["d"], "px": ext_p, "t": "H"})
                direction = -1; ext_p = R[i]["l"]; ext_i = i
        else:
            if R[i]["l"] < ext_p: ext_p = R[i]["l"]; ext_i = i
            elif (R[i]["h"] - ext_p) / ext_p >= dev:
                piv.append({"i": ext_i, "d": R[ext_i]["d"], "px": ext_p, "t": "L"})
                direction = 1; ext_p = R[i]["h"]; ext_i = i
    if direction != 0:
        piv.append({"i": ext_i, "d": R[ext_i]["d"], "px": ext_p, "t": "H" if direction == 1 else "L", "tent": True})

    def merge_same(arr, k):
        if k < 0 or k + 1 >= len(arr) or arr[k]["t"] != arr[k+1]["t"]: return False
        if arr[k]["t"] == "H": keep = k if arr[k]["px"] >= arr[k+1]["px"] else k + 1
        else: keep = k if arr[k]["px"] <= arr[k+1]["px"] else k + 1
        arr.pop(k + 1 if keep == k else k); return True

    guard = 0
    while guard < 400:
        guard += 1
        bad = -1
        for k2 in range(1, len(piv)):
            if piv[k2]["i"] - piv[k2-1]["i"] < min_sep: bad = k2; break
        if bad < 0 or len(piv) <= 3: break
        piv.pop(bad); merge_same(piv, bad - 1)
    guard = 0
    while guard < 400:   # 保序安全網
        guard += 1
        inv = -1
        for k3 in range(1, len(piv)):
            if piv[k3]["t"] == "L" and piv[k3]["px"] >= piv[k3-1]["px"]: inv = k3; break
            if piv[k3]["t"] == "H" and piv[k3]["px"] <= piv[k3-1]["px"]: inv = k3; break
        if inv < 0 or len(piv) <= 3: break
        piv.pop(inv); merge_same(piv, inv - 1)
    return piv

# ---------------- 4B 古典型態 ----------------
def _pf(x): return ("+" if x >= 0 else "") + "%.1f%%" % (x * 100)

def classic_patterns(R, piv, opt=None):
    opt = opt or {}
    N = len(R); out = []
    HEAD_MIN = opt.get("headMin", 0.03)
    SH_TOL = opt.get("shoulderTol", 0.15)
    DT_TOL = opt.get("dtTol", 0.03)
    DT_RETR = opt.get("dtRetr", 0.05)
    MAXAGE = opt.get("maxAge", max(40, _jround(N * 0.6)))
    def line_at(p1, p2, k):
        return p1["px"] + (p2["px"] - p1["px"]) * (k - p1["i"]) / max(1, (p2["i"] - p1["i"]))

    # 頭肩頂 / 逆頭肩
    for s in range(0, max(0, len(piv) - 4)):
        P = piv[s:s+5]
        top = P[0]["t"] == "H"
        if not (P[0]["t"] == P[2]["t"] == P[4]["t"]): continue
        LS, T1, H, T2, RS = P
        why = []; ok = True
        hs1 = (H["px"]/LS["px"] - 1) if top else (LS["px"]/H["px"] - 1)
        hs2 = (H["px"]/RS["px"] - 1) if top else (RS["px"]/H["px"] - 1)
        why.append("頭" + ("高於" if top else "低於") + "左肩 " + _pf(hs1) + "(需≥%g%%)" % (HEAD_MIN*100))
        why.append("頭" + ("高於" if top else "低於") + "右肩 " + _pf(hs2) + "(需≥%g%%)" % (HEAD_MIN*100))
        if not (hs1 >= HEAD_MIN and hs2 >= HEAD_MIN): ok = False
        shd = abs(LS["px"] - RS["px"]) / max(LS["px"], RS["px"])
        why.append("雙肩高度差 " + _pf(shd) + "(需≤%g%%)" % (SH_TOL*100))
        if shd > SH_TOL: ok = False
        nslope = abs(T2["px"]/T1["px"] - 1)
        why.append("頸線兩點落差 " + _pf(nslope) + "(需≤35%,過陡=退化型態)")
        if nslope > 0.35: ok = False
        mid = min(T1["px"], T2["px"]) if top else max(T1["px"], T2["px"])
        depth = (H["px"]/mid - 1) if top else (mid/H["px"] - 1)
        why.append("頸線至頭深度 " + _pf(depth) + "(需≥%g%%)" % (HEAD_MIN*100))
        if depth < HEAD_MIN: ok = False
        if not ok: continue
        if N - 1 - RS["i"] > MAXAGE: continue
        state = "forming"; brk_d = None; brk_i = None; inval = False
        for k in range(RS["i"] + 1, N):
            ny = line_at(T1, T2, k)
            if top and R[k]["h"] > H["px"]: inval = True; break
            if (not top) and R[k]["l"] < H["px"]: inval = True; break
            if top and R[k]["c"] < ny * 0.999: state = "confirmed"; brk_d = R[k]["d"]; brk_i = k; break
            if (not top) and R[k]["c"] > ny * 1.001: state = "confirmed"; brk_d = R[k]["d"]; brk_i = k; break
        if inval: continue
        why.append(("右肩後" + ("跌破" if top else "突破") + "頸線 " + str(brk_d) + " → confirmed") if state == "confirmed"
                   else ("右肩後尚未" + ("跌破" if top else "突破") + "頸線 → forming(未確認)"))
        neck_rs = line_at(T1, T2, RS["i"])
        tgt = (neck_rs - (H["px"] - line_at(T1, T2, H["i"]))) if top else (neck_rs + (line_at(T1, T2, H["i"]) - H["px"]))
        out.append({"type": "頭肩頂" if top else "逆頭肩", "dir": -1 if top else 1, "state": state,
            "pivots": [{"d": LS["d"], "px": round(LS["px"], 3), "role": "左肩", "i": LS["i"]},
                       {"d": T1["d"], "px": round(T1["px"], 3), "role": "谷1" if top else "峰1", "i": T1["i"]},
                       {"d": H["d"], "px": round(H["px"], 3), "role": "頭", "i": H["i"]},
                       {"d": T2["d"], "px": round(T2["px"], 3), "role": "谷2" if top else "峰2", "i": T2["i"]},
                       {"d": RS["d"], "px": round(RS["px"], 3), "role": "右肩", "i": RS["i"]}],
            "neckline": {"x1_d": T1["d"], "y1": round(T1["px"], 3), "x2_d": T2["d"], "y2": round(T2["px"], 3),
                         "i1": T1["i"], "i2": T2["i"]},
            "target": round(tgt, 3), "broken_d": brk_d, "brkI": brk_i, "why": why,
            "score": round(3 + (1.5 if state == "confirmed" else 0) + min(1, (hs1+hs2)/0.2) - shd/SH_TOL + 1.5*(RS["i"]/(N-1)), 2),
            "lastI": RS["i"]})

    # 雙重頂 / 雙重底
    for s2 in range(0, max(0, len(piv) - 2)):
        A, M, B = piv[s2], piv[s2+1], piv[s2+2]
        if A["t"] != B["t"]: continue
        top2 = A["t"] == "H"
        diff = abs(A["px"] - B["px"]) / max(A["px"], B["px"])
        retr = (max(A["px"], B["px"])/M["px"] - 1) if top2 else (M["px"]/min(A["px"], B["px"]) - 1)
        why2 = ["兩" + ("頂" if top2 else "底") + "差 " + _pf(diff) + "(需≤%g%%)" % (DT_TOL*100),
                "中間回撤 " + _pf(retr) + "(需≥%g%%)" % (DT_RETR*100)]
        if diff > DT_TOL or retr < DT_RETR: continue
        if N - 1 - B["i"] > MAXAGE: continue
        st2 = "forming"; bd2 = None; bi2 = None; iv2 = False
        for k2 in range(B["i"] + 1, N):
            if top2 and R[k2]["h"] > max(A["px"], B["px"]) * 1.01: iv2 = True; break
            if (not top2) and R[k2]["l"] < min(A["px"], B["px"]) * 0.99: iv2 = True; break
            if top2 and R[k2]["c"] < M["px"]: st2 = "confirmed"; bd2 = R[k2]["d"]; bi2 = k2; break
            if (not top2) and R[k2]["c"] > M["px"]: st2 = "confirmed"; bd2 = R[k2]["d"]; bi2 = k2; break
        if iv2: continue
        why2.append(("頸線(%.2f)" % M["px"] + ("跌破" if top2 else "突破") + " " + str(bd2) + " → confirmed") if st2 == "confirmed"
                    else ("頸線尚未" + ("跌破" if top2 else "突破") + " → forming"))
        tgt2 = (M["px"] - (max(A["px"], B["px"]) - M["px"])) if top2 else (M["px"] + (M["px"] - min(A["px"], B["px"])))
        out.append({"type": "雙重頂" if top2 else "雙重底", "dir": -1 if top2 else 1, "state": st2,
            "pivots": [{"d": A["d"], "px": round(A["px"], 3), "role": "頂1" if top2 else "底1", "i": A["i"]},
                       {"d": M["d"], "px": round(M["px"], 3), "role": "頸線", "i": M["i"]},
                       {"d": B["d"], "px": round(B["px"], 3), "role": "頂2" if top2 else "底2", "i": B["i"]}],
            "neckline": {"x1_d": A["d"], "y1": round(M["px"], 3), "x2_d": B["d"], "y2": round(M["px"], 3),
                         "i1": A["i"], "i2": B["i"]},
            "target": round(tgt2, 3), "broken_d": bd2, "brkI": bi2, "why": why2,
            "score": round(2.6 + (1.5 if st2 == "confirmed" else 0) + (DT_TOL-diff)/DT_TOL + 1.5*(B["i"]/(N-1)), 2),
            "lastI": B["i"]})

    # 三角收斂 / 楔形 / 旗形(2026-08-01 強化;與 index.html 逐字一致)
    # 舊版只看末端 4 轉折且需恰好 2 高 2 低,實盤 5–7 轉折的收斂三角整個漏掉。
    # 新版對「末端 3 個結束位置 × 視窗 4–7 轉折」逐一評分取最佳,並加兩道品質閘:
    #   ① apex(兩邊線交會)須落在右緣附近;② 區間內收盤被兩邊線夾住的比例 ≥85%。
    if len(piv) >= 4:
        bestT = None
        e = len(piv) - 1
        while e >= 3 and e >= len(piv) - 3:
            for k in range(4, 8):
                if e - k + 1 < 0: continue
                seg = piv[e-k+1:e+1]
                Hs = [p for p in seg if p["t"] == "H"]; Ls = [p for p in seg if p["t"] == "L"]
                if len(Hs) < 2 or len(Ls) < 2: continue
                H0, H1, L0, L1 = Hs[0], Hs[-1], Ls[0], Ls[-1]
                if H1["i"] <= H0["i"] or L1["i"] <= L0["i"]: continue
                su = (H1["px"]-H0["px"]) / (H1["i"]-H0["i"]) / H0["px"]
                sl = (L1["px"]-L0["px"]) / (L1["i"]-L0["i"]) / L0["px"]
                i0 = min(H0["i"], L0["i"]); i1 = max(H1["i"], L1["i"])
                if i1 - i0 < 8: continue
                def up_at(q, H0=H0, H1=H1): return H0["px"] + (H1["px"]-H0["px"]) * (q-H0["i"]) / (H1["i"]-H0["i"])
                def lo_at(q, L0=L0, L1=L1): return L0["px"] + (L1["px"]-L0["px"]) * (q-L0["i"]) / (L1["i"]-L0["i"])
                w0 = (up_at(i0)-lo_at(i0)) / max(lo_at(i0), 1e-9)
                w1 = (up_at(i1)-lo_at(i1)) / max(lo_at(i1), 1e-9)
                if not (w0 > 0 and w1 > 0): continue
                conv = w1 < w0 * 0.75; FLAT = 0.0006
                ptype = None; dir3 = 0
                if su < -FLAT and sl > FLAT and conv: ptype = "對稱三角"; dir3 = 0
                elif abs(su) <= FLAT and sl > FLAT and conv: ptype = "上升三角"; dir3 = 1
                elif su < -FLAT and abs(sl) <= FLAT and conv: ptype = "下降三角"; dir3 = -1
                elif su > FLAT and sl > FLAT and su < sl and conv: ptype = "上升楔形"; dir3 = -1
                elif su < -FLAT and sl < -FLAT and su < sl and conv: ptype = "下降楔形"; dir3 = 1
                elif abs(su-sl) < FLAT*0.8 and abs(su) > FLAT and (i1-i0) <= 40:
                    ptype = "下降旗形" if su < 0 else "上升旗形"; dir3 = 1 if su < 0 else -1
                if not ptype: continue
                if N - 1 - i1 > MAXAGE: continue
                apex_ok = True; apex_i = None
                if conv:
                    dsl = (su*H0["px"]) - (sl*L0["px"])
                    num = (lo_at(i1) - up_at(i1))
                    apex_i = None if abs(dsl) < 1e-12 else (i1 + num/dsl)
                    apex_ok = (apex_i is not None and apex_i >= i1-2 and apex_i <= i1 + 2*(i1-i0))
                if not apex_ok: continue
                in_c = 0; tot_c = 0
                for q2 in range(i0, i1+1):
                    u2 = up_at(q2); d2 = lo_at(q2); tot_c += 1
                    if R[q2]["c"] <= u2*1.015 and R[q2]["c"] >= d2*0.985: in_c += 1
                contain = (in_c/tot_c) if tot_c else 0.0
                if contain < 0.85: continue
                st3 = "forming"; bd3 = None; bi3 = None; dir_b = dir3
                for k3 in range(i1+1, N):
                    if R[k3]["c"] > up_at(k3)*1.01: st3 = "confirmed"; bd3 = R[k3]["d"]; bi3 = k3; dir_b = 1; break
                    if R[k3]["c"] < lo_at(k3)*0.99: st3 = "confirmed"; bd3 = R[k3]["d"]; bi3 = k3; dir_b = -1; break
                sc3 = (2.4 + (1.5 if st3 == "confirmed" else 0) + (0.6 if conv else 0) + 1.5*(i1/(N-1))
                       + 0.8*(contain-0.85)/0.15 + 0.15*(len(seg)-4))
                cand = {"type": ptype, "dir": dir_b, "state": st3,
                    "pivots": [{"d": p["d"], "px": round(p["px"], 3), "role": "高" if p["t"] == "H" else "低", "i": p["i"]} for p in seg],
                    "edges": {"up": {"i1": H0["i"], "y1": round(H0["px"], 3), "i2": H1["i"], "y2": round(H1["px"], 3)},
                              "lo": {"i1": L0["i"], "y1": round(L0["px"], 3), "i2": L1["i"], "y2": round(L1["px"], 3)}},
                    "target": None, "broken_d": bd3, "brkI": bi3,
                    "why": ["上邊線斜率 %.3f%%/根、下邊線 %.3f%%/根(%d高%d低)" % (su*100, sl*100, len(Hs), len(Ls)),
                            "通道寬度 %.1f%% → %.1f%%" % (w0*100, w1*100) + ("(收斂 %d%%)" % round((1-w1/w0)*100) if conv else "(平行)"),
                            "夾住率 %d%%(需≥85%%:收盤落在兩邊線內)" % round(contain*100)
                              + ((" · 收斂交點約在 %d 根後" % round(apex_i-i1)) if apex_i is not None else ""),
                            ("收盤" + ("向上" if dir_b > 0 else "向下") + "突破邊線 " + str(bd3) + " → confirmed")
                              if st3 == "confirmed" else "尚未突破邊線 → forming"],
                    "score": round(sc3, 2), "lastI": i1}
                if bestT is None or cand["score"] > bestT["score"]: bestT = cand
            e -= 1
        if bestT: out.append(bestT)

    # 杯柄
    for s4 in range(0, max(0, len(piv) - 2)):
        L1, C, R1 = piv[s4], piv[s4+1], piv[s4+2]
        if not (L1["t"] == "H" and C["t"] == "L" and R1["t"] == "H"): continue
        rim = abs(L1["px"] - R1["px"]) / max(L1["px"], R1["px"])
        dep = (max(L1["px"], R1["px"]) / C["px"] - 1)
        dur = R1["i"] - L1["i"]
        if rim > 0.05 or dep < 0.15 or dur < 30: continue
        h_lo = None; h_end = None
        for k4 in range(R1["i"] + 1, N):
            if h_lo is None or R[k4]["l"] < h_lo: h_lo = R[k4]["l"]
            h_end = k4
            if R[k4]["c"] > R1["px"]: break
        if h_lo is None: continue
        h_dep = (R1["px"] / h_lo - 1); h_dur = h_end - R1["i"]
        why4 = ["雙緣高度差 " + _pf(rim) + "(需≤5%)",
                "杯深 " + _pf(dep) + "(需≥15%)、杯長 " + str(dur) + " 根(需≥30)",
                "柄回檔 " + _pf(h_dep) + "(需≤杯深1/3=" + _pf(dep/3) + ")、柄長 " + str(h_dur) + " 根"]
        if h_dep > dep/3 or h_dur > dur/3: continue
        if N - 1 - R1["i"] > MAXAGE: continue
        st4 = "forming"; bd4 = None; bi4 = None
        for k5 in range(R1["i"] + 1, N):
            if R[k5]["c"] > R1["px"]: st4 = "confirmed"; bd4 = R[k5]["d"]; bi4 = k5; break
        why4.append(("突破右緣 " + str(bd4) + " → confirmed") if st4 == "confirmed" else "尚未突破右緣 → forming")
        out.append({"type": "杯柄", "dir": 1, "state": st4,
            "pivots": [{"d": L1["d"], "px": round(L1["px"], 3), "role": "左緣", "i": L1["i"]},
                       {"d": C["d"], "px": round(C["px"], 3), "role": "杯底", "i": C["i"]},
                       {"d": R1["d"], "px": round(R1["px"], 3), "role": "右緣", "i": R1["i"]}],
            "neckline": {"x1_d": L1["d"], "y1": round(R1["px"], 3), "x2_d": R1["d"], "y2": round(R1["px"], 3),
                         "i1": L1["i"], "i2": R1["i"]},
            "target": round(R1["px"] * (1 + dep), 3), "broken_d": bd4, "brkI": bi4, "why": why4,
            "score": round(2.8 + (1.5 if st4 == "confirmed" else 0) + min(1, dep/0.3) + 1.5*(R1["i"]/(N-1)), 2),
            "lastI": R1["i"]})

    # ===== VCP 波動收縮型態(Minervini;2026-08-01 新增;與 index.html 逐字一致)=====
    # ⚠ 型態辨識非預測:VCP 只描述「供給收縮」的形狀,不保證突破,不構成買賣建議。
    if N >= 40 and len(piv) >= 3:
        base_start = max(0, N - min(140, N))
        CT = []
        for v0 in range(0, len(piv)-1):
            HH = piv[v0]; LL = piv[v0+1]
            if HH["t"] != "H" or LL["t"] != "L": continue
            if LL["i"] < base_start or HH["i"] < base_start: continue
            if not (HH["px"] > 0): continue
            CT.append({"hi": HH, "lo": LL, "depth": (HH["px"]-LL["px"])/HH["px"]})
        if len(CT) >= 2:
            CT = CT[-4:]
            why5 = []; ok5 = True
            why5.append("基底內 %d 次回檔:%s" % (len(CT), " → ".join("%.1f%%" % (c["depth"]*100) for c in CT)))
            for v1 in range(1, len(CT)):
                if not (CT[v1]["depth"] <= CT[v1-1]["depth"]*0.80):
                    ok5 = False
                    why5.append("第 %d 次回檔 %.1f%% 未收斂到前次 80%% 以內 → 不成立" % (v1+1, CT[v1]["depth"]*100))
                    break
            if ok5: why5.append("每次回檔皆 ≤ 前次 80%(逐次收縮)✓")
            last_d = CT[-1]["depth"]
            why5.append("末次回檔 %.1f%%(需≤15%%)" % (last_d*100))
            if last_d > 0.15: ok5 = False
            his = [c["hi"]["px"] for c in CT]
            h_max = max(his); h_min = min(his)
            why5.append("基底頂部齊平度 %d%%(需≥88%%:高點不逐級崩落)" % round((h_min/h_max)*100))
            if h_min < h_max*0.88: ok5 = False
            def avg_v(i0, i1):
                sv = 0.0; cv = 0
                for q in range(max(0, i0), min(N-1, i1)+1):
                    sv += (R[q].get("v") or 0); cv += 1
                return (sv/cv) if cv else 0.0
            vA = avg_v(CT[0]["hi"]["i"], CT[0]["lo"]["i"]); vB = avg_v(CT[-1]["hi"]["i"], CT[-1]["lo"]["i"])
            vr = (vB/vA) if vA > 0 else 1.0
            why5.append("末次回檔均量 / 首次均量 = %d%%(需≤85%%:量縮)" % round(vr*100))
            if not (vA > 0 and vr <= 0.85): ok5 = False
            pivot_px = h_max; last_c = R[N-1]["c"]; gap = (pivot_px-last_c)/pivot_px
            why5.append("現價距基底高 %.1f%%(需≤8%%)" % (gap*100))
            if not (gap <= 0.08): ok5 = False
            if ok5:
                st5 = "forming"; bd5 = None; bi5 = None
                for k5 in range(CT[-1]["lo"]["i"]+1, N):
                    if R[k5]["c"] > pivot_px*1.001: st5 = "confirmed"; bd5 = R[k5]["d"]; bi5 = k5; break
                why5.append(("收盤越過樞紐 %.2f 於 %s → confirmed" % (pivot_px, bd5)) if st5 == "confirmed"
                            else ("尚未越過樞紐 %.2f → forming(型態非預測,突破與否未知)" % pivot_px))
                pvs = []
                for ci, c in enumerate(CT):
                    pvs.append({"d": c["hi"]["d"], "px": round(c["hi"]["px"], 3),
                                "role": "基底高" if ci == 0 else ("反彈高%d" % (ci+1)), "i": c["hi"]["i"]})
                    pvs.append({"d": c["lo"]["d"], "px": round(c["lo"]["px"], 3),
                                "role": "收縮低%d" % (ci+1), "i": c["lo"]["i"]})
                out.append({"type": "VCP 波動收縮", "dir": 1, "state": st5, "pivots": pvs,
                    "neckline": {"x1_d": CT[0]["hi"]["d"], "y1": round(pivot_px, 3),
                                 "x2_d": R[N-1]["d"], "y2": round(pivot_px, 3),
                                 "i1": CT[0]["hi"]["i"], "i2": N-1},
                    "necklineLabel": "樞紐買點 %.2f(停損參考 %.2f)" % (pivot_px, CT[-1]["lo"]["px"]),
                    "target": None, "broken_d": bd5, "brkI": bi5, "why": why5,
                    "score": round(3.0 + (1.5 if st5 == "confirmed" else 0) + 0.5*len(CT)
                                   + 1.2*(1-last_d/0.15) + 0.6*(1-vr), 2),
                    "lastI": CT[-1]["lo"]["i"]})

    out.sort(key=lambda x: -x["score"])
    seen = set(); res = []
    for p in out:
        if len(res) >= 4: break
        key = p["type"] + ":" + p["state"]
        if key in seen: continue
        seen.add(key); res.append(p)
    return res

# ---------------- 4C 蠟燭型態(約 30 種;純規則) ----------------
def candle_patterns(R):
    N = len(R); out = []
    if N < 6: return out
    rng = [R[i]["h"] - R[i]["l"] for i in range(N)]
    body = [abs(R[i]["c"] - R[i]["o"]) for i in range(N)]
    def avg(arr, i, n):
        s = 0.0; c = 0
        for k in range(max(0, i-n), i): s += arr[k]; c += 1
        return s/c if c else 0.0
    def up(i): return R[i]["c"] >= R[i]["o"]
    def upper(i): return R[i]["h"] - max(R[i]["o"], R[i]["c"])
    def lower(i): return min(R[i]["o"], R[i]["c"]) - R[i]["l"]
    def trend_dn(i, n=5): return i >= n and R[i-1]["c"] < R[i-n]["c"]
    def trend_up(i, n=5): return i >= n and R[i-1]["c"] > R[i-n]["c"]
    def add(i, name, d, why): out.append({"i": i, "d": R[i]["d"], "name": name, "dir": d, "why": why})
    for i in range(3, N):
        ar = avg(rng, i, 14) or 1e-9; ab = avg(body, i, 14) or 1e-9
        b = body[i]; r = rng[i] or 1e-9; u = upper(i); lo = lower(i)
        if b <= r*0.1:
            if lo >= r*0.6 and u <= r*0.1: add(i, "蜻蜓十字", 1, "實體≤10%全距、下影≥60%")
            elif u >= r*0.6 and lo <= r*0.1: add(i, "墓碑十字", -1, "實體≤10%全距、上影≥60%")
            else: add(i, "十字星", 0, "實體≤10%全距(多空拉鋸)")
        elif b >= r*0.9:
            add(i, "光頭光腳陽線" if up(i) else "光頭光腳陰線", 1 if up(i) else -1, "實體≥90%全距、幾無影線")
        elif lo >= b*2 and u <= b*0.5 and r >= ar*0.6:
            if trend_dn(i): add(i, "錘子線", 1, "下影≥2倍實體、上影短、出現於跌勢")
            elif trend_up(i): add(i, "吊人線", -1, "下影≥2倍實體、出現於漲勢")
        elif u >= b*2 and lo <= b*0.5 and r >= ar*0.6:
            if trend_up(i): add(i, "流星線", -1, "上影≥2倍實體、上影短、出現於漲勢")
            elif trend_dn(i): add(i, "倒錘子", 1, "上影≥2倍實體、出現於跌勢")
        elif b <= ab*0.4 and u >= b and lo >= b:
            add(i, "紡錘線", 0, "小實體、上下影皆長(猶豫)")
        p = i - 1
        if up(i) and not up(p) and R[i]["c"] >= R[p]["o"] and R[i]["o"] <= R[p]["c"] and b > body[p]:
            add(i, "看漲吞噬", 1, "陽線實體完全吞噬前根陰線實體")
        if not up(i) and up(p) and R[i]["c"] <= R[p]["o"] and R[i]["o"] >= R[p]["c"] and b > body[p]:
            add(i, "看跌吞噬", -1, "陰線實體完全吞噬前根陽線實體")
        if body[p] > ab and b < body[p]*0.6 and max(R[i]["o"], R[i]["c"]) < max(R[p]["o"], R[p]["c"]) and min(R[i]["o"], R[i]["c"]) > min(R[p]["o"], R[p]["c"]):
            if b <= r*0.1: add(i, "十字孕線", -1 if up(p) else 1, "小十字完全落在前根長實體內")
            else: add(i, "看跌孕線" if up(p) else "看漲孕線", -1 if up(p) else 1, "小實體完全落在前根長實體內")
        if up(i) and not up(p) and R[i]["o"] < R[p]["l"] and R[i]["c"] > (R[p]["o"]+R[p]["c"])/2 and R[i]["c"] < R[p]["o"]:
            add(i, "曙光初現", 1, "跳空低開、收復前陰線一半以上")
        if not up(i) and up(p) and R[i]["o"] > R[p]["h"] and R[i]["c"] < (R[p]["o"]+R[p]["c"])/2 and R[i]["c"] > R[p]["o"]:
            add(i, "烏雲蓋頂", -1, "跳空高開、回吐前陽線一半以上")
        if abs(R[i]["h"] - R[p]["h"]) <= ar*0.05 and trend_up(i): add(i, "鑷頂", -1, "連兩根等高(壓力確認)")
        if abs(R[i]["l"] - R[p]["l"]) <= ar*0.05 and trend_dn(i): add(i, "鑷底", 1, "連兩根等低(支撐確認)")
        if up(i) and not up(p) and R[i]["o"] > R[p]["o"] and body[p] > ab and b > ab: add(i, "看漲反衝", 1, "跳空反向開出、雙長實體")
        if not up(i) and up(p) and R[i]["o"] < R[p]["o"] and body[p] > ab and b > ab: add(i, "看跌反衝", -1, "跳空反向開出、雙長實體")
        q1 = i - 2
        if i >= 2:
            if (not up(q1)) and body[q1] > ab and body[p] <= body[q1]*0.5 and up(i) and R[i]["c"] > (R[q1]["o"]+R[q1]["c"])/2:
                add(i, "晨星", 1, "長陰→小實體(星)→長陽收復一半以上")
            if up(q1) and body[q1] > ab and body[p] <= body[q1]*0.5 and (not up(i)) and R[i]["c"] < (R[q1]["o"]+R[q1]["c"])/2:
                add(i, "夜星", -1, "長陽→小實體(星)→長陰回吐一半以上")
            if up(q1) and up(p) and up(i) and R[i]["c"] > R[p]["c"] and R[p]["c"] > R[q1]["c"] and body[q1] > ab*0.6 and body[p] > ab*0.6 and b > ab*0.6:
                add(i, "紅三兵", 1, "連三根長陽、收盤逐日走高")
            if (not up(q1)) and (not up(p)) and (not up(i)) and R[i]["c"] < R[p]["c"] and R[p]["c"] < R[q1]["c"] and body[q1] > ab*0.6 and body[p] > ab*0.6 and b > ab*0.6:
                add(i, "黑三兵", -1, "連三根長陰、收盤逐日走低")
            if (not up(q1)) and up(p) and up(i) and R[p]["c"] < R[q1]["o"] and R[p]["o"] > R[q1]["c"] and R[i]["c"] > R[q1]["o"]:
                add(i, "三內部上升", 1, "孕線後第三根確認向上")
            if up(q1) and (not up(p)) and (not up(i)) and R[p]["c"] > R[q1]["o"] and R[p]["o"] < R[q1]["c"] and R[i]["c"] < R[q1]["o"]:
                add(i, "三內部下降", -1, "孕線後第三根確認向下")
            if (not up(q1)) and up(p) and up(i) and R[p]["c"] > R[q1]["o"] and R[p]["o"] < R[q1]["c"] and R[i]["c"] > R[p]["c"]:
                add(i, "三外部上升", 1, "吞噬後第三根續強")
            if up(q1) and (not up(p)) and (not up(i)) and R[p]["c"] < R[q1]["o"] and R[p]["o"] > R[q1]["c"] and R[i]["c"] < R[p]["c"]:
                add(i, "三外部下降", -1, "吞噬後第三根續弱")
            if (not up(q1)) and body[p] <= rng[p]*0.15 and R[p]["h"] < R[q1]["l"] and up(i) and R[i]["o"] > R[p]["h"]:
                add(i, "棄嬰底", 1, "十字星上下皆跳空(罕見強訊號)")
            if up(q1) and body[p] <= rng[p]*0.15 and R[p]["l"] > R[q1]["h"] and (not up(i)) and R[i]["o"] < R[p]["l"]:
                add(i, "棄嬰頂", -1, "十字星上下皆跳空(罕見強訊號)")
        if i >= 4:
            f = i - 4
            if up(f) and body[f] > ab and (not up(f+1)) and (not up(f+2)) and (not up(f+3)) and \
               max(R[f+1]["h"], R[f+2]["h"], R[f+3]["h"]) < R[f]["h"] and min(R[f+1]["l"], R[f+2]["l"], R[f+3]["l"]) > R[f]["l"] and \
               up(i) and R[i]["c"] > R[f]["c"]:
                add(i, "上升三法", 1, "長陽後三小陰整理、第五根創新高")
            if (not up(f)) and body[f] > ab and up(f+1) and up(f+2) and up(f+3) and \
               min(R[f+1]["l"], R[f+2]["l"], R[f+3]["l"]) > R[f]["l"] and max(R[f+1]["h"], R[f+2]["h"], R[f+3]["h"]) < R[f]["h"] and \
               (not up(i)) and R[i]["c"] < R[f]["c"]:
                add(i, "下降三法", -1, "長陰後三小陽反彈、第五根創新低")
    return out

# ---------------- 對外:寫入 computed_tech.patterns ----------------
def patterns_for(bars, win=TL_WIN):
    """bars=gist kline 原始陣列 → 型態清單(鏡像駕駛艙視窗;歷史不足回 None,呼叫端 fail-open)"""
    rows = bars[LEAD:] if len(bars) > LEAD else []
    if len(rows) < 50: return None
    seg = rows[-min(win, len(rows)):]
    R = [{"d": b[0], "o": float(b[1]), "h": float(b[2]), "l": float(b[3]), "c": float(b[4]),
          "v": float(b[5] or 0)} for b in seg]
    piv = zigzag(R)
    pats = classic_patterns(R, piv)
    asof = R[-1]["d"]
    out = []
    for p in pats:
        e = {"type": p["type"], "state": p["state"], "dir": p["dir"],
             "pivots": [{"d": x["d"], "px": x["px"], "role": x["role"]} for x in p["pivots"]],
             "why": p["why"], "score": p["score"], "asof": asof}
        if p.get("neckline"):
            e["neckline"] = {k: p["neckline"][k] for k in ("x1_d", "y1", "x2_d", "y2")}
        if p.get("edges"): e["edges"] = p["edges"]
        if p.get("target") is not None: e["target"] = p["target"]
        if p.get("broken_d"): e["broken_d"] = p["broken_d"]
        out.append(e)
    # 近 10 根內的蠟燭型態(供判讀引用;完整清單前端自算)
    cd = candle_patterns(R)
    recent = [{"d": c["d"], "name": c["name"], "dir": c["dir"]} for c in cd if c["i"] >= len(R) - 10]
    return {"list": out, "candles_10d": recent[-8:], "n_pivots": len(piv), "asof": asof}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="NOW,MU,NVDA,SNDK,WDC,SPY")
    ap.add_argument("--kline-dir", default="data")
    ap.add_argument("--win", type=int, default=TL_WIN)
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    OUT = {}
    for sym in [s.strip().upper() for s in a.symbols.split(",") if s.strip()]:
        p = os.path.join(a.kline_dir, "kline_%s.json" % sym)
        if not os.path.exists(p): print("%s: 無 kline 檔" % sym); continue
        bars = json.load(open(p))["bars"]
        res = patterns_for(bars, a.win)
        OUT[sym] = res
        print("\n== %s win=%d 轉折=%s" % (sym, a.win, (res or {}).get("n_pivots")))
        for e in (res or {}).get("list", []):
            print("  ★ %s[%s] score=%s %s" % (e["type"], e["state"], e["score"],
                  " ".join(x["role"] + "@" + x["d"][5:] for x in e["pivots"])))
            for w in e["why"]: print("      · " + w)
        if res and res["candles_10d"]:
            print("   近10日蠟燭:", " | ".join(c["d"][5:] + " " + c["name"] for c in res["candles_10d"]))
    if a.json:
        json.dump(OUT, open(a.json, "w"), ensure_ascii=False)
        print("\njson ->", a.json)

if __name__ == "__main__":
    main()
