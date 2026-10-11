// t27 補充(只描述):五檔近一年,用網頁同一份日K(codex_v01 快照,BUILD 2026-10-10)與網頁自己的 tkSeriesJS,
// 照 Codex 原式算「額外候選」會多標哪幾天:
//   extraCandidate = i>0 && TK.hot[i] && TK.touch[i] && TK.off[i]<TK_TH.off && TK.atr[i-1]>0 && TK.H[i]-TK.C[i] >= TK.atr[i-1]
// 用法:node t27_five_js.cjs <index.html> <快照資料夾>
const fs = require('fs'), vm = require('vm'), path = require('path');
const [IDX, SNAP] = process.argv.slice(2);
const src = fs.readFileSync(IDX, 'utf8');
const fn = name => src.match(new RegExp('^function ' + name + '\\([^]*?\\n}', 'm'))[0];
const ctx = vm.createContext({});
vm.runInContext(src.match(/^const TK_TH=.*?;/m)[0] + '\n' + fn('tkSeriesJS') + '\nthis.tkSeriesJS=tkSeriesJS;this.TK_TH=TK_TH;', ctx);
const FROM = '2025-10-10', TO = '2026-10-09';
for (const s of ['MU', 'SNDK', 'TSM', 'NVDA', 'META']) {
  const B = JSON.parse(fs.readFileSync(path.join(SNAP, s + '.json'), 'utf8')).bars;
  const TK = ctx.tkSeriesJS(B), TH = ctx.TK_TH; const ex = [], tk = [];
  for (let i = 0; i < TK.n; i++) {
    if (TK.D[i] < FROM || TK.D[i] > TO) continue;
    if (TK.tk[i]) tk.push(TK.D[i]);
    const extraCandidate = i > 0 && TK.hot[i] && TK.touch[i] && TK.off[i] < TH.off && TK.atr[i - 1] > 0 && TK.H[i] - TK.C[i] >= TK.atr[i - 1];
    if (extraCandidate) ex.push(`${TK.D[i]}(離高 ${(TK.off[i] * 100).toFixed(2)}%,高−收 = ${((TK.H[i] - TK.C[i]) / TK.atr[i - 1]).toFixed(2)}×前日ATR,ATR/收 ${(TK.atr[i - 1] / TK.C[i - 1] * 100).toFixed(2)}%)`);
  }
  const atrPct = TK.atr[TK.n - 1] / TK.C[TK.n - 1] * 100;
  console.log(`${s}:頂K ${tk.length} 天;額外候選 ${ex.length} 天${ex.length ? ':' + ex.join('、') : ''};最後一天 ATR/收盤 ${atrPct.toFixed(2)}%`);
}
for (const d of ['2026-06-03', '2026-10-05']) {
  const B = JSON.parse(fs.readFileSync(path.join(SNAP, 'TSM.json'), 'utf8')).bars, TK = ctx.tkSeriesJS(B), i = TK.D.indexOf(d);
  console.log(`TSM ${d}:hot=${TK.hot[i]} touch=${TK.touch[i]} 離高 ${(TK.off[i] * 100).toFixed(2)}% 高−收 = ${((TK.H[i] - TK.C[i]) / TK.atr[i - 1]).toFixed(2)}×前日ATR → 額外候選 ${i > 0 && TK.hot[i] && TK.touch[i] && TK.off[i] < ctx.TK_TH.off && TK.atr[i - 1] > 0 && TK.H[i] - TK.C[i] >= TK.atr[i - 1]}`);
}
