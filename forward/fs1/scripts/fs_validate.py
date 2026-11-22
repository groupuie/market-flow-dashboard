#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FS1 資料卡檢查(格式與欄位關係;不核實來源內容)。協定 ../PROTOCOL_FS1.md §5。
用法:python3 -I forward/fs1/scripts/fs_validate.py pending/{t}.card.json   (同資料夾要有 {t}.packet.json)"""
import os, sys, json, math, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fs_common as C

TOP = {"schema", "decision_month", "cutoff_utc", "packet_sha256", "prev_card_sha256", "model", "regime_view", "ranking",
       "exp_excess_3m_pct", "weights", "calls", "claims", "notes", "changes_vs_prev", "searches_used"}
CALL = {"industry", "side", "p_beat_market_3m", "horizon_months", "thesis", "differs_from_consensus", "marginal_buyer",
        "catalysts", "falsifiers", "add_if", "exit_if", "claim_ids"}


def num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def nonempty_str(x):
    return isinstance(x, str) and x.strip() != ""


def validate(card_bytes, packet_bytes, prev_sha):
    E = []
    try:
        c = json.loads(card_bytes.decode("utf-8"))
    except Exception as e:                                   # noqa: BLE001
        return [f"不是合法 JSON:{e}"]
    p = json.loads(packet_bytes.decode("utf-8"))
    if not isinstance(c, dict):
        return ["最外層必須是物件"]
    miss = TOP - set(c); extra = set(c) - TOP
    if miss:
        E.append(f"缺欄位:{sorted(miss)}")
    if extra:
        E.append(f"多出不認得的欄位:{sorted(extra)}")
    if c.get("schema") != "fs1-card-v1":
        E.append("schema 必須是 fs1-card-v1")
    if c.get("decision_month") != p["decision_month"]:
        E.append("decision_month 和資料包不同")
    if c.get("cutoff_utc") != p["cutoff_utc"]:
        E.append("cutoff_utc 必須照抄資料包")
    if c.get("packet_sha256") != C.sha256_bytes(packet_bytes):
        E.append("packet_sha256 和資料包的指紋不同")
    if c.get("prev_card_sha256") != prev_sha:
        E.append(f"prev_card_sha256 必須是 {prev_sha}")
    if not nonempty_str(c.get("model")):
        E.append("model 不能空白")
    if not nonempty_str(c.get("regime_view")):
        E.append("regime_view 不能空白")
    codes = C.CODES; S = set(codes)
    rk = c.get("ranking")
    if not (isinstance(rk, list) and len(rk) == 49 and set(rk) == S):
        E.append("ranking 必須剛好是 49 個產業代號、每個一次")
        rk = None
    ex = c.get("exp_excess_3m_pct")
    if not (isinstance(ex, dict) and set(ex) == S and all(num(v) for v in ex.values())):
        E.append("exp_excess_3m_pct 必須每個產業一個數字")
    elif rk is not None and any(ex[rk[i]] < ex[rk[i + 1]] for i in range(48)):
        E.append("exp_excess_3m_pct 必須照 ranking 由大到小(可以相等)")
    w = c.get("weights")
    if not isinstance(w, dict) or not w:
        E.append("weights 必須是物件")
    else:
        bad = set(w) - S - {"CASH"}
        if bad:
            E.append(f"weights 有不認得的代號:{sorted(bad)}")
        if not all(num(v) and v >= 0 for v in w.values()):
            E.append("weights 每個值必須 ≥ 0")
        elif any(v > C.RULES["max_weight"] + 1e-9 for k, v in w.items() if k != "CASH"):
            E.append(f"單一產業權重不能超過 {C.RULES['max_weight']}")
        elif abs(sum(w.values()) - 1) > 1e-6:
            E.append("weights 加總必須是 1(含 CASH)")
    cl = c.get("claims"); ids = set()
    cutoff = C.parse_time(p["cutoff_utc"])
    if not (isinstance(cl, list) and len(cl) >= C.RULES["min_claims"]):
        E.append(f"claims 至少 {C.RULES['min_claims']} 條")
    else:
        for j, x in enumerate(cl):
            if not isinstance(x, dict) or set(x) != {"id", "text", "source_url", "published", "consensus"}:
                E.append(f"claims[{j}] 欄位必須是 id、text、source_url、published、consensus"); continue
            if not nonempty_str(x["id"]) or x["id"] in ids:
                E.append(f"claims[{j}] id 空白或重複")
            ids.add(x["id"])
            if not nonempty_str(x["text"]) or not nonempty_str(x["consensus"]):
                E.append(f"claims[{j}] text / consensus 不能空白(不知道就寫 unknown)")
            if not (isinstance(x["source_url"], str) and re.match(r"^https?://\S+$", x["source_url"])):
                E.append(f"claims[{j}] source_url 必須是 http(s) 網址")
            try:
                if C.parse_time(x["published"]) > cutoff:
                    E.append(f"claims[{j}] 發布時間晚於截止時間")
            except Exception:                                  # noqa: BLE001
                E.append(f"claims[{j}] published 必須是 YYYY-MM-DD 或 ISO 時間")
    calls = c.get("calls")
    if not isinstance(calls, list):
        E.append("calls 必須是陣列")
    else:
        n_over = n_under = 0; seen = set()
        for j, x in enumerate(calls):
            if not isinstance(x, dict) or set(x) != CALL:
                E.append(f"calls[{j}] 欄位不對(要剛好 {sorted(CALL)})"); continue
            if x["industry"] not in S or x["industry"] in seen:
                E.append(f"calls[{j}] industry 不認得或重複")
            seen.add(x["industry"])
            if rk is not None and x["industry"] in S:
                pos = rk.index(x["industry"])
                if x["side"] == "over" and pos >= C.RULES["top_n"]:
                    E.append(f"calls[{j}] over 必須在 ranking 前 {C.RULES['top_n']} 名")
                if x["side"] == "under" and pos < 49 - C.RULES["top_n"]:
                    E.append(f"calls[{j}] under 必須在 ranking 後 {C.RULES['top_n']} 名")
            if x["side"] == "over":
                n_over += 1
            elif x["side"] == "under":
                n_under += 1
            else:
                E.append(f"calls[{j}] side 必須是 over 或 under")
            if not (num(x["p_beat_market_3m"]) and 0 <= x["p_beat_market_3m"] <= 1):
                E.append(f"calls[{j}] p_beat_market_3m 必須在 0 ~ 1")
            if not (isinstance(x["horizon_months"], int) and not isinstance(x["horizon_months"], bool) and 1 <= x["horizon_months"] <= 6):
                E.append(f"calls[{j}] horizon_months 必須是 1 ~ 6 的整數")
            for k in ("thesis", "differs_from_consensus", "marginal_buyer"):
                if not nonempty_str(x[k]):
                    E.append(f"calls[{j}] {k} 不能空白")
            for k, mn in (("catalysts", 0), ("falsifiers", 1), ("add_if", 0), ("exit_if", 1), ("claim_ids", 1)):
                v = x[k]
                if not (isinstance(v, list) and len(v) >= mn and all(nonempty_str(s) for s in v)):
                    E.append(f"calls[{j}] {k} 至少 {mn} 條文字")
            if isinstance(x["claim_ids"], list) and any(i not in ids for i in x["claim_ids"] if isinstance(i, str)):
                E.append(f"calls[{j}] claim_ids 指到不存在的 claim")
        lo, hi = C.RULES["over_calls"]
        if not lo <= n_over <= hi:
            E.append(f"over calls 要 {lo} ~ {hi} 個")
        lo, hi = C.RULES["under_calls"]
        if not lo <= n_under <= hi:
            E.append(f"under calls 要 {lo} ~ {hi} 個")
    nt = c.get("notes")
    if not (isinstance(nt, dict) and set(nt) == S and all(nonempty_str(v) and len(v) <= C.RULES["note_max_chars"] for v in nt.values())):
        E.append(f"notes 必須每個產業一句(1 ~ {C.RULES['note_max_chars']} 字)")
    if prev_sha is not None and not nonempty_str(c.get("changes_vs_prev")):
        E.append("有上一張卡時,changes_vs_prev 不能空白")
    if prev_sha is None and c.get("changes_vs_prev") not in (None, ""):
        E.append("第一張卡的 changes_vs_prev 要是 null 或空字串")
    su = c.get("searches_used")
    if not (isinstance(su, int) and not isinstance(su, bool) and 0 <= su <= C.RULES["max_searches"]):
        E.append(f"searches_used 必須是 0 ~ {C.RULES['max_searches']} 的整數")
    return E


if __name__ == "__main__":
    cp = sys.argv[1]; pp = cp.replace(".card.json", ".packet.json")
    led = C.read_ledger(); prev = led[-1]["card_sha256"] if led else None
    errs = validate(open(cp, "rb").read(), open(pp, "rb").read(), prev)
    print(json.dumps({"ok": not errs, "errors": errs}, ensure_ascii=False, indent=1))
    sys.exit(0 if not errs else 1)
