# Claude 診斷用(2026-10-14;不改 Astra 任何檔案):
#   和 Astra experiment.py 完全相同,只把「算訊號用的價格」先照網站方式四捨五入(≥1 元 3 位小數、<1 元 5 位),
#   買賣成交價、ATR、帳戶都仍用未四捨五入的還原價。
#   用法:把這個檔放在 Astra v0.5.0 研究資料夾的副本裡(要有 freeze.json 原件),執行 python3 run_rounded.py <資料夾>
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import data_tools
_orig = data_tools.signals
def _rounded(bars, mode='research'):
    return _orig([[x[0], *(round(v, 3 if v >= 1 else 5) for v in x[1:5]), x[5]] for x in bars], mode)
data_tools.signals = _rounded
import experiment
sys.argv = ['experiment.py', '--data-dir', sys.argv[1]]
experiment.main()
