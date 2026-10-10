// 加(adSeriesJS)JS↔pandas 對拍:把 index.html 的「加 = 加碼參考」那段存成 ad.js,kline_<代號>.json 與 kline_QQQ.json(資料 gist)放同資料夾 → node t23h_jscheck.js ad.js
const fs=require('fs');
eval(fs.readFileSync(process.argv[2],'utf8')+'\nglobalThis.adSeriesJS=adSeriesJS;');
const q=JSON.parse(fs.readFileSync(__dirname+'/kline_QQQ.json','utf8')).bars;
const QM={};let s=0;const cs=q.map(b=>+b[4]);
for(let i=0;i<q.length;i++){s+=cs[i];if(i>=20)s-=cs[i-20];if(i>=19)QM[q[i][0]]=cs[i]<s/20;}
const qd=d=>(d in QM)?QM[d]:null;
const out={};
for(const sym of ['TSM','NVDA','AAPL','MU','BE','AVGO','LITE','PLTR']){
  const B=JSON.parse(fs.readFileSync(__dirname+'/kline_'+sym+'.json','utf8')).bars;
  const A=adSeriesJS(B,qd,null);out[sym]=[];
  for(let i=0;i<A.n;i++)if(A.sig[i])out[sym].push(A.D[i]+'|'+(A.rsiX[i]?'R':'')+(A.lbT[i]?'L':''));
  out[sym+'_raw']=A.raw.filter(Boolean).length; out[sym+'_ut']=A.ut.filter(Boolean).length;
  if(sym==='TSM')out.TSM_now={p40:A.p40&&+A.p40.toFixed(2),lo:+A.loNow.toFixed(2),utNext:A.utNext,v20:+A.v20[A.n-1].toFixed(4),rsi:+A.rsi[A.n-1].toFixed(2)};
}
console.log(JSON.stringify(out));
