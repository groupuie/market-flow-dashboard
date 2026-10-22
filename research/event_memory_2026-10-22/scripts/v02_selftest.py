#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""契約 v0.2 的合成自測(只用假資料;不讀任何真實行情、不呼叫任何模型)。
它只檢查「契約的規則寫成參考程式之後前後一致」,**不代表方法有效**;正式程式之後要通過同一組測試。
測:FL3_A60 v0.2(§3)與准入(§2b)、反應日與 usable_from(§2、§4,給定日曆)、C0 抽卡(§4,含測試向量)、P1 的封存順序(§4)、
    H1 → H1b 固定順序與方向門檻、Holm(§5)、機率精度(§5)、配對恆等式(§5)、證據等級(§7)、兩個 v0.2 schema。
用法:python3 -I v02_selftest.py   → 印出每一項結果;全部通過才回傳 0"""
import hashlib, json, os, random, sys

OK = []


def check(name, cond):
    OK.append((name, bool(cond))); print(("通過 " if cond else "失敗 ") + name)


# ---------- §2b / §3:FL3_A60 v0.2 ----------
def bar(o, h, l, c, close_time="16:00", **flags):
    return {"o": o, "h": h, "l": l, "c": c, "close_time": close_time, "o_imp": flags.get("o_imp", False), "h_imp": flags.get("h_imp", False),
            "l_imp": flags.get("l_imp", False), "c_imp": flags.get("c_imp", False), "no_trade": flags.get("no_trade", False)}


def atr60(bars, t):
    w = bars[t - 59: t + 1]
    if t < 60 or len(w) < 60 or any(b is None or b["no_trade"] or b["h_imp"] or b["l_imp"] or b["c_imp"] for b in w) or bars[t - 60] is None:
        return None
    tr = [max(b["h"], p["c"]) - min(b["l"], p["c"]) for p, b in zip(bars[t - 60: t], w)]
    return sum(tr) / 60


def fl3_v02(bars, t):
    """回傳 (狀態, y, 發動日, 成熟時間)。准入不看結果:t+1 … t+3 三根都要合格(§2b 第 3 條)"""
    A = atr60(bars, t)
    if A is None:
        return "feature_missing", None, None, None
    if t + 1 >= len(bars) or bars[t + 1] is None or bars[t + 1]["o_imp"] or bars[t + 1]["no_trade"] or not bars[t + 1]["o"] > 0:
        return "entry_missing", None, None, None
    win = bars[t + 1: t + 4]
    if len(win) < 3 or any(b is None or b["no_trade"] or b["l_imp"] or b["c_imp"] for b in win):
        return "label_unresolved", None, None, None
    e = bars[t + 1]["o"]
    for j, b in enumerate(win, 1):
        if b["l"] <= e - A:
            return "scored", 0, None, win[2]["close_time"]
        if b["c"] >= e + A:
            return "scored", 1, j, win[2]["close_time"]
    return "scored", 0, None, win[2]["close_time"]


base = [bar(100, 101, 99, 100) for _ in range(61)]            # TR = 2 → ATR60 = 2;t = 60
t = 60
s = base + [bar(100, 101, 99.5, 100.5), bar(100.5, 103, 100, 102.5), bar(102, 103, 101, 102)]
check("FL3:第 2 天收盤 ≥ e + A → 1,發動日 2", fl3_v02(s, t)[:3] == ("scored", 1, 2))
s = base + [bar(100, 103, 97.5, 102.5), bar(102, 103, 101, 102), bar(102, 103, 101, 102)]
check("FL3:同一天先跌破 e − A 又收在 e + A 之上 → 0(停損優先)", fl3_v02(s, t)[:2] == ("scored", 0))
s = base + [bar(100, 101, 99.5, 100.5, o_imp=True), bar(100.5, 103, 100, 102.5), bar(102, 103, 101, 102)]
check("FL3:進場日開盤是補值 → entry_missing(不計分)", fl3_v02(s, t)[0] == "entry_missing")
s = base + [bar(100, 103, 99.5, 102.5), bar(102, 103, 101, 102), bar(102, 102, 102, 102, no_trade=True)]
check("FL3:第 1 天已發動但第 3 天沒交易 → label_unresolved(准入不看結果)", fl3_v02(s, t)[0] == "label_unresolved")
s = base + [bar(100, 101, 99, 100.5), bar(100.5, 101.5, 99.5, 101), bar(101, 101.5, 100, 101, close_time="13:00")]
check("FL3:三天都沒碰到 → 0;第 3 天提早收盤 → 成熟時間 13:00", fl3_v02(s, t) == ("scored", 0, None, "13:00"))
s = [dict(b) for b in base]; s[30]["h_imp"] = True; s += [bar(100, 101, 99.5, 100.5), bar(100.5, 103, 100, 102.5), bar(102, 103, 101, 102)]
check("FL3:ATR60 窗內有補值的高價 → feature_missing", fl3_v02(s, t)[0] == "feature_missing")


# ---------- §4:C0 抽卡 ----------
def h(*parts):
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def eligible(pool, decision_time, current_acc):
    seen, out = set(), []
    for c in sorted(pool, key=lambda c: c["case_id"]):
        if c["usable_from"] <= decision_time and c["accession"] != current_acc and c["accession"] not in seen:
            seen.add(c["accession"]); out.append(c)
    return out


def c0_cards(event_acc, pool, decision_time, k, salt):
    """契約 §4:以當前事件為單位;freeze_salt 凍結時才知道"""
    el = eligible(pool, decision_time, event_acc)
    pick = sorted(el, key=lambda c: h(event_acc, "C0", salt, c["case_id"]))[:k]
    return sorted(pick, key=lambda c: c["usable_from"], reverse=True)


rnd = random.Random(7)
pool = [{"case_id": f"X{i:03d}_{i % 37}", "accession": f"acc{i % 150}", "usable_from": f"2025-{1 + i % 12:02d}-{1 + i % 28:02d}"} for i in range(200)]
pool.append({"case_id": "CUR_d0", "accession": "accCUR", "usable_from": "2025-01-01"})
dt, cur = "2025-09-30", "accCUR"
c_cards = eligible(pool, dt, cur)[:3]                          # 假裝 C 拿到 3 張
SALT = "test-salt-not-a-real-freeze"
c0 = c0_cards(cur, pool, dt, len(c_cards), SALT)
check("C0:張數和 C 一樣(k = 3)", len(c0) == len(c_cards) == 3)
check("C0:全部 usable_from ≤ 決定時間、沒有當前事件、accession 不重複",
      all(c["usable_from"] <= dt and c["accession"] != cur for c in c0) and len({c["accession"] for c in c0}) == len(c0))
check("C0:重算結果相同、和卡池順序無關(不靠亂數產生器)", c0 == c0_cards(cur, list(reversed(pool)), dt, 3, SALT))
check("C0:同一事件 d0 與 d4(卡池相同時)拿到同一組卡", c0_cards(cur, pool, dt, 3, SALT) == c0_cards(cur, pool, dt, 3, SALT))
check("C0:換 freeze_salt 就換一組(凍結前算不出來)", [c["case_id"] for c in c0] != [c["case_id"] for c in c0_cards(cur, pool, dt, 3, "another-salt")])
VEC = [c["case_id"] for c in c0_cards("acc-VECTOR", [{"case_id": f"V{i}", "accession": f"v{i}", "usable_from": "2025-01-01"} for i in range(10)], "2025-12-31", 3, "salt-VECTOR")]
print("   C0 測試向量(事件 acc-VECTOR、salt-VECTOR、卡 V0–V9、取 3 張):", VEC)
check("C0:測試向量 = ['V3', 'V1', 'V5'](換語言實作要得到同一串;usable_from 相同時照雜湊順序)", VEC == ["V3", "V1", "V5"])
check("C0:排序依 usable_from 由新到舊", [c["usable_from"] for c in c0] == sorted([c["usable_from"] for c in c0], reverse=True))
check("C0:m = 0 → 0 張", c0_cards(cur, pool, dt, 0, SALT) == [])
tiny = [{"case_id": f"T{i}", "accession": f"t{i}", "usable_from": "2025-03-01"} for i in range(3)]
check("C0:不刻意避開 C 的卡(卡池只有 3 張時,C0 和 C 完全重疊 3 張)",
      len({c["case_id"] for c in c0_cards(cur, tiny, dt, 3, SALT)} & {c["case_id"] for c in eligible(tiny, dt, cur)}) == 3)


# ---------- §2、§4:反應日、usable_from(給定日曆;正式版用 NYSE 官方日曆) ----------
CAL = [("2025-11-25", "16:00"), ("2025-11-26", "16:00"), ("2025-11-28", "13:00"), ("2025-12-01", "16:00"), ("2025-12-02", "16:00")]   # 11-27 休市、11-28 提早收盤


def reaction_day(avail_date, avail_hhmm):
    """第一個 close_time 晚於 available_at 的交易日(時間都是美東)"""
    for d, ct in CAL:
        if (d, ct) > (avail_date, avail_hhmm):
            return d
    return None


def usable_from(matured_date):
    ix = [d for d, _ in CAL].index(matured_date)
    return CAL[ix + 1]


check("日曆:盤前公布(08:00)→ 當天是反應日", reaction_day("2025-11-25", "08:00") == "2025-11-25")
check("日曆:盤後公布(16:05)→ 下一個交易日", reaction_day("2025-11-25", "16:05") == "2025-11-26")
check("日曆:提早收盤日 13:30 公布 → 已經收盤,算下一個交易日(不是 16:00)", reaction_day("2025-11-28", "13:30") == "2025-12-01")
check("日曆:休市日(11-27)公布 → 下一個交易日", reaction_day("2025-11-27", "10:00") == "2025-11-28")
check("usable_from:成熟日的下一個交易日收盤(跳過休市、帶提早收盤時間)", usable_from("2025-11-26") == ("2025-11-28", "13:00"))


# ---------- §4:P1 封存順序 ----------
def p1_order_ok(log):
    """log = [(時間, 事件)];第一回合的指紋一定要比第二回合早寫入"""
    t_seal = min(t for t, e in log if e == "seal_first_turn"); t_second = min(t for t, e in log if e == "send_second_turn")
    return t_seal < t_second


check("P1:先寫第一回合指紋、再送第二回合 → 合格", p1_order_ok([(1, "first_answer"), (2, "seal_first_turn"), (3, "send_second_turn")]))
check("P1:第二回合先送、指紋後寫 → 不合格", not p1_order_ok([(1, "first_answer"), (3, "seal_first_turn"), (2, "send_second_turn")]))


# ---------- §5:固定順序與方向門檻 ----------
def claim(d1, p1, d2=None, p2=None, a=0.05):
    if p1 < a and d1 < 0:
        return "加卡後變差(停止)"
    if not (p1 < a and d1 > 0):
        return "H1 未過"
    if p2 is not None and p2 < a and d2 > 0:
        return "選卡政策有增量"
    return "加卡流程有效"


check("門檻:H1 過、H1b 過 → 選卡政策有增量", claim(0.006, 0.01, 0.004, 0.02) == "選卡政策有增量")
check("門檻:H1 過、H1b 不顯著 → 只說加卡流程有效", claim(0.006, 0.01, 0.001, 0.40) == "加卡流程有效")
check("門檻:H1 顯著但方向相反 → 停止(就算 H1b 顯著也不看)", claim(-0.006, 0.01, 0.004, 0.001) == "加卡後變差(停止)")
check("門檻:H1 不顯著 → 不檢 H1b", claim(0.006, 0.20, 0.004, 0.001) == "H1 未過")
check("門檻:H1b 顯著但 C0 比較好 → 不算增量", claim(0.006, 0.01, -0.004, 0.01) == "加卡流程有效")

# ---------- §5:Holm ----------
def holm(ps, a=0.05):
    order = sorted(range(len(ps)), key=lambda i: ps[i]); rej = [False] * len(ps)
    for rank, i in enumerate(order):
        if ps[i] <= a / (len(ps) - rank):
            rej[i] = True
        else:
            break
    return rej


check("Holm:6 個 p = [0.001, 0.009, 0.012, 0.04, 0.2, 0.5] → 拒絕前三個(0.012 ≤ 0.05 / 4)", holm([0.001, 0.009, 0.012, 0.04, 0.2, 0.5]) == [True, True, True, False, False, False])
check("Holm:一停就停(0.02 > 0.05 / 3 之後,0.03、0.04 也不拒絕)", holm([0.03, 0.001, 0.02, 0.04]) == [False, True, False, False])

# ---------- §5:精度 ----------
b_full, b_2dp = (1 - 0.5049) ** 2, (1 - round(0.5049, 2)) ** 2
check("精度:p = 0.5049、y = 1 → Brier 0.24512401;兩位小數 0.25(差 0.00487599)",
      abs(b_full - 0.24512401) < 1e-12 and abs(b_2dp - 0.25) < 1e-12 and abs(b_2dp - b_full - 0.00487599) < 1e-12)
from decimal import Decimal, ROUND_HALF_UP
q2 = lambda x: float(Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
check("精度:BLEND = 平均後照同一規則到兩位(0.53、0.60 → 0.565 → 0.57)", q2((0.53 + 0.60) / 2) == 0.57)
check("精度:0.005 進位(0.125 → 0.13,不是銀行家捨入的 0.12)", q2(0.125) == 0.13 and round(0.125, 2) == 0.12)

# ---------- §5:配對恆等式;同樣的 RMS,平均改善可正可負可為 0 ----------
ok = True
for _ in range(10000):
    pb, pcx, y = rnd.random(), rnd.random(), rnd.randint(0, 1)
    ok &= abs(((pb - y) ** 2 - (pcx - y) ** 2) - (pb - pcx) * (pb + pcx - 2 * y)) < 1e-12
check("恆等式:(p_B−y)² − (p_C−y)² = (p_B−p_C)(p_B+p_C−2y)(1 萬列隨機)", ok)
D = lambda pb, pcx, y: (pb - y) ** 2 - (pcx - y) ** 2
m_pos = sum(D(0.4, 0.6, 1) for _ in range(10)) / 10; m_neg = sum(D(0.4, 0.6, 0) for _ in range(10)) / 10
m_0 = (sum(D(0.4, 0.6, 1) for _ in range(5)) + sum(D(0.4, 0.6, 0) for _ in range(5))) / 10
check("恆等式:機率差固定 0.2(RMS 0.2),平均改善 +0.20 / −0.20 / 0 都可能",
      abs(m_pos - 0.2) < 1e-12 and abs(m_neg + 0.2) < 1e-12 and abs(m_0) < 1e-12)


# ---------- §7:證據等級 ----------
def level(pack_sealed, answer_sealed, next_open, matured):
    """時間 = 決定日收盤後幾小時;None = 沒封存"""
    if pack_sealed is not None and answer_sealed is not None and pack_sealed < next_open and answer_sealed < next_open:
        return "即時封存"
    if pack_sealed is not None and pack_sealed < matured:
        return "封包回放"
    return "不合格"


NEXT_OPEN, MATURED = 17.5, 3 * 24.0                          # 隔天 09:30 ET;約 t+3 收盤
check("等級:資料包與回答都在隔天開盤前推上 → 即時封存", level(5, 7, NEXT_OPEN, MATURED) == "即時封存")
check("等級:資料包先封、回答在成熟後 → 封包回放", level(5, 120, NEXT_OPEN, MATURED) == "封包回放")
check("等級:回答在開盤後、成熟前才推 → 封包回放(不是即時)", level(5, 30, NEXT_OPEN, MATURED) == "封包回放")
check("等級:資料包在成熟後才封 → 不合格", level(90, 91, NEXT_OPEN, MATURED) == "不合格")

# ---------- schema v0.2:本身合法 + 條件必填 ----------
try:
    import jsonschema
    HERE = os.path.dirname(os.path.abspath(__file__))
    DS = json.load(open(os.path.join(HERE, "..", "decision_schema_v0.2.json"))); CS = json.load(open(os.path.join(HERE, "..", "case_schema_v0.2.json")))
    V = jsonschema.Draft202012Validator
    V.check_schema(DS); V.check_schema(CS); check("schema:decision / case v0.2 符合 JSON Schema 2020-12", True)
    sha = "0" * 64
    rec = {"schema_version": "0.2", "row_id": "MSFT_0001_d0", "case_id": "MSFT_0001", "sym": "MSFT", "k": 0, "decision_at": "2025-07-30T20:00:00Z",
           "group": "C0", "model": "claude-opus-5-5", "packet_sha256": sha, "p_launch": 0.31, "action": "wait", "judged_at": "2025-07-30T21:00:00Z",
           "issuer_cik": "789019", "security_id": "MSFT@1986-03-13", "information_available_time": "2025-07-30T20:06:00Z", "score_status": "scored",
           "evidence_level": "開發", "used_cards": ["X1", "X2"], "same_issuer_cards": 0, "same_security_cards": 0, "card_overlap_with_C": 1,
           "hypothesis_id": "trend_context", "invalidation": "跌破反應日低點", "reason": "趨勢延續但波動偏低", "agent_id": "agent-test-0001"}
    ok_ = lambda r: V(DS).is_valid(r)
    check("schema:完整的 C0 紀錄合法", ok_(rec))
    check("schema:C0 少了 card_overlap_with_C → 不合法", not ok_({k: v for k, v in rec.items() if k != "card_overlap_with_C"}))
    p1 = dict(rec, group="P1"); [p1.pop(k) for k in ("card_overlap_with_C",)]
    check("schema:P1 沒有第一回合指紋 → 不合法", not ok_(dict(p1, p_R_shown=0.4, r_reliability_card_sha256=sha)))
    check("schema:P1 欄位齊全 → 合法", ok_(dict(p1, p_R_shown=0.4, r_reliability_card_sha256=sha, sealed_first_turn_sha256=sha)))
    check("schema:action = abandon 沒寫 skip_reason → 不合法", not ok_(dict(rec, action="abandon")))
    check("schema:封包回放沒寫 sealed_commit → 不合法", not ok_(dict(rec, evidence_level="封包回放")))
except ImportError:
    print("(沒有 jsonschema 套件,略過 schema 檢查)")

n_ok = sum(1 for _, c in OK if c)
print(f"\n合計 {n_ok} / {len(OK)} 項通過")
sys.exit(0 if n_ok == len(OK) else 1)
