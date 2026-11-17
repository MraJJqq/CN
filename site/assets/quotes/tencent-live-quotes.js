const ENDPOINT="https://qt.gtimg.cn/q=";
function parse(symbol){
 const raw=window["v_"+symbol];if(typeof raw!=="string")return null;
 const f=raw.split("~"),price=Number(f[3]),previousClose=Number(f[4]),open=Number(f[5]);
 if(!(price>0)||!(previousClose>0))return null;
 const high=Number(f[34]),low=Number(f[35]);
 return {symbol,price,previousClose,open:open>0?open:previousClose,high:high>0?high:price,low:low>0?low:price};
}
function loadQuote(symbol){
 return new Promise((resolve,reject)=>{
  const script=document.createElement("script");let settled=false;
  const finish=error=>{if(settled)return;settled=true;clearTimeout(timer);script.onload=script.onerror=null;script.remove();if(error)reject(error);else resolve(parse(symbol))};
  const timer=setTimeout(()=>finish(new Error("Tencent quote request timed out")),15000);
  script.async=true;script.charset="gbk";script.onload=()=>finish(null);script.onerror=()=>finish(new Error("Tencent quote script failed to load"));
  script.src=ENDPOINT+symbol+"&_="+Date.now();document.head.appendChild(script);
 });
}
export function createTencentLiveQuotes(){
 let sequence=0;
 async function read(symbol){
  const token=++sequence;
  if(typeof symbol!=="string"||!/^(sh|sz|bj)\d{6}$/.test(symbol))return null;
  const quote=await loadQuote(symbol);
  return token===sequence?quote:null;
 }
 return Object.freeze({read});
}
