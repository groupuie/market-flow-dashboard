// 用 Codex 的 qmTopDiagnostics 重現五檔頂K表與 TSM 兩天(網頁同一份日K 快照)。用法:node t26_topdiag_run.cjs <index.html> <快照資料夾>
const fs=require('fs'),vm=require('vm'),path=require('path');
const {qmTopDiagnostics}=require('./t26_topdiag_codex.js');
const [IDX,SNAP]=process.argv.slice(2);const src=fs.readFileSync(IDX,'utf8');
function fn(name){const m=src.match(new RegExp('^function '+name+'\\([^]*?\\n}','m'));return m[0];}
const ctx=vm.createContext({});
vm.runInContext(src.match(/^const TK_TH=.*?;/m)[0]+'\n'+fn('tkSeriesJS')+'\nthis.tkSeriesJS=tkSeriesJS;this.TK_TH=TK_TH;',ctx);
const out={};
for(const s of ['MU','SNDK','TSM','NVDA','META']){
  const B=JSON.parse(fs.readFileSync(path.join(SNAP,s+'.json'),'utf8')).bars;
  const TK=ctx.tkSeriesJS(B);
  const tr=qmTopDiagnostics(TK,ctx.TK_TH.off);
  const yr=tr.filter(r=>r.date>='2025-10-10'&&r.date<='2026-10-09');
  const ht=yr.filter(r=>r.gates.hot&&r.gates.touch);
  const blockedOff=ht.filter(r=>r.gates.off===false);
  const marked=yr.filter(r=>r.marked);
  // 合取 = 正式頂K(可判斷日)
  const ok=yr.filter(r=>r.ready).every(r=>(r.gates.hot&&r.gates.touch&&r.gates.off)===r.marked);
  out[s]={bars:yr.length,hotTouch:ht.length,blockedOff:blockedOff.length,marked:marked.length,markedDates:marked.map(r=>r.date),conjunctionEqualsOfficial:ok};
  if(s==='TSM')for(const d of ['2026-06-03','2026-10-05']){const r=tr.find(x=>x.date===d);out['TSM_'+d]=r;}
}
console.log(JSON.stringify(out,null,1));
