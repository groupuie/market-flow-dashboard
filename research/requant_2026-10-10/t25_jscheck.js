// t25 對拍(Codex v0.1 修正 B)—— 前端 JS 端:直接從 index.html 抽出 fcClimOf / fcSeriesJS / adSeriesJS / AD_TH 來跑。
// 用法:node t25_jscheck.js <新版 index.html> <舊版 index.html> <資料夾> 代號...
// 資料夾要有 kline_<代號>.json、kline_QQQ.json、flow_climate.json;輸出與 python3 t25_jscheck.py 同格式(sort_keys)。
const fs = require('node:fs'), vm = require('node:vm'), path = require('node:path');
const [newIdx, oldIdx, dir, ...syms] = process.argv.slice(2);
function fn(src, name) { const m = src.match(new RegExp('^function ' + name + '\\([^]*?\\n}', 'm')); if (!m) throw new Error(name); return m[0]; }
function core(file) {
  const src = fs.readFileSync(file, 'utf8'), ctx = vm.createContext({});
  ctx.climate = JSON.parse(fs.readFileSync(path.join(dir, 'flow_climate.json'), 'utf8'));
  const defs = ['AD_TH'].map(n => src.match(new RegExp('^const ' + n + '=.*?;', 'm'))[0]);
  vm.runInContext('var FCL=climate;\n' + defs.join('\n') + '\n' + ['fcClimOf', 'fcSeriesJS', 'adSeriesJS'].map(n => fn(src, n)).join('\n'), ctx);
  return ctx;
}
const A = core(newIdx), O = core(oldIdx);
const q = JSON.parse(fs.readFileSync(path.join(dir, 'kline_QQQ.json'), 'utf8')).bars;
const QM = {}; let s = 0; const cs = q.map(b => +b[4]);
for (let i = 0; i < q.length; i++) { s += cs[i]; if (i >= 20) s -= cs[i - 20]; if (i >= 19) QM[q[i][0]] = cs[i] < s / 20; }
const qd = d => (d in QM) ? QM[d] : null;
const out = {};
for (const sym of syms) {
  const B = JSON.parse(fs.readFileSync(path.join(dir, 'kline_' + sym + '.json'), 'utf8')).bars;
  const chu = new Array(B.length).fill(false);
  A.fcSeriesJS(B).ev.filter(e => e.k === 'trim').forEach(e => { chu[e.i] = true; });
  const res = { chu: B.filter((b, i) => chu[i]).map(b => b[0]) };
  for (const [tag, ctx] of [['new', A], ['old', O]]) {
    const R = ctx.adSeriesJS(B, qd, chu); res[tag] = [];
    for (let i = 0; i < R.n; i++) if (R.sig[i]) res[tag].push(R.D[i] + '|' + (R.rsiX[i] ? 'R' : '') + (R.lbT[i] ? 'L' : ''));
    res[tag + '_raw'] = R.raw.filter(Boolean).length; if (tag === 'new') res.ut = R.ut.filter(Boolean).length;
  }
  out[sym] = res;
}
const sortKeys = o => Array.isArray(o) ? o.map(sortKeys) : (o && typeof o === 'object') ? Object.keys(o).sort().reduce((r, k) => (r[k] = sortKeys(o[k]), r), {}) : o;
console.log(JSON.stringify(sortKeys(out)));
