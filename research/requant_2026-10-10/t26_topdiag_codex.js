// Codex v0.2 第 3 節提供的 qmTopDiagnostics(逐字;只在檔尾加 module.exports 方便 node 執行)
// 只讀取正式 tkSeriesJS 的計算結果，不新增訊號、不改門檻。
function qmTopDiagnostics(TK, offThreshold = 0.05) {
  if (!Number.isFinite(offThreshold) || offThreshold < 0 || offThreshold > 1)
    throw new Error('invalid offThreshold');
  const finite = Number.isFinite;
  const pct = x => finite(x) ? +(100 * x).toFixed(4) : null;
  return TK.D.map((date, i) => {
    const hotGate = TK.hot[i] ? true
      : [TK.r20[i], TK.dA[i], TK.ext[i]].every(finite) ? false : null;
    const ready = hotGate !== null && finite(TK.up[i]) && finite(TK.off[i]);
    const gates = {
      hot: hotGate,
      touch: finite(TK.up[i]) ? !!TK.touch[i] : null,
      off: finite(TK.off[i]) ? TK.off[i] >= offThreshold : null
    };
    return {
      date, index: i, ready, marked: !!TK.tk[i],
      gates,
      blocked: Object.entries(gates).filter(([, v]) => v === false).map(([k]) => k),
      unknown: Object.entries(gates).filter(([, v]) => v === null).map(([k]) => k),
      offPct: pct(TK.off[i]), thresholdPct: pct(offThreshold),
      r20Pct: pct(TK.r20[i]), ext50Pct: pct(TK.ext[i]),
      distanceAtr: finite(TK.dA[i]) ? TK.dA[i] : null,
      high: TK.H[i], close: TK.C[i], upperBand: TK.up[i]
    };
  });
}
module.exports={qmTopDiagnostics};
