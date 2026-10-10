# t25 檢查(修正 D 的範圍判斷用):259 檔面板 O/H/L/C 在「第一筆有效 ~ 最後一筆有效」之間有沒有缺值。
# 沒有中間缺值 → 「最遠的期間已完整」就保證較近的期間也完整;wick_trim2、t21*、t22e、t23*、t23e 因此不受修正 D 影響。
import pickle, numpy as np
from qlib import DT
P = pickle.load(open(DT + "/stock.pkl", "rb"))["P"]
for k in "OHLC":
    X = P[k].astype("float64"); v = X.notna()
    gaps = (~v) & (v.cumsum() > 0) & (v[::-1].cumsum()[::-1] > 0)
    print(f"{k}:中間缺值 {int(gaps.values.sum())} 格,有缺值的股票 {int((gaps.sum() > 0).sum())} 檔(共 {X.shape[1]} 檔 × {X.shape[0]} 天)")
