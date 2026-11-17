import {createV6KlineView} from "./kline/v6-kline-view.js?v=cn-residue-cleanup-20261116-2";
import {createTencentKlineController} from "./kline/tencent-kline-controller.js?v=cn-residue-cleanup-20261116-3";
import {createLifecycleScope} from "./shared/lifecycle.js?v=cn-ema-snapshot-20261116-1";
import {createPageLifecycle} from "./shared/page-lifecycle-v6.js?v=cn-ema-snapshot-20261116-1";
import {createSignalTicker} from "./modules/signal-ticker/ticker.js?v=cn-signal-previous-20261117-1";
import {createKlineRotationPause} from "./kline/rotation-pause.js?v=cn-common-systems-20261116-1";
import {createTencentLiveQuotes} from "./quotes/tencent-live-quotes.js?v=cn-live-quotes-20261117-5";
const DATA="./data/",$=id=>document.getElementById(id),lifecycle=createLifecycleScope();
window.__CN_READY__=false;
let pageLifecycle=null,universe=[],signalStocks=[],carouselIndex=0,carouselTimer=null,transitionTimer=null,transitionToken=0,destroyed=false,activeSignalDate="",activeSignalSnapshot=null,signalRefreshToken=0,signalRefreshController=null,dailyRefreshTimer=null,marketRefreshTimer=null,marketRefreshBusy=false,liveQuoteBySymbol=new Map();
const interactionLocks=new Set();let rotationPaused=false,rotationPause=null;
const ROTATION_START_KEY="cn-last-random-start",SIGNAL_SNAPSHOT_KEY="cn-daily-signal-snapshot-v1",SIGNAL_CHECK_KEY="cn-daily-snapshot-checked-v1",logoFrame=$("logo-frame"),timeframeFrame=$("timeframe-frame");
const isHidden=()=>pageLifecycle?pageLifecycle.isSuspended():document.hidden;
const host=$("kline-host"),chart=createV6KlineView({host,onInteractionChange:setInteractionLock});
const controller=createTencentKlineController({frame:{contentWindow:chart},isHidden,onState:s=>{if(s.status==="request-failed")console.warn("[CN Tencent K-line]",s)}});
const ticker=createSignalTicker({container:$("signal-ticker"),track:$("signal-track")});
const liveQuotes=createTencentLiveQuotes();
lifecycle.listen(window,"unhandledrejection",event=>console.error("[VEGAS CN unhandled rejection]",event.reason));
lifecycle.listen(window,"error",event=>console.error("[VEGAS CN runtime error]",event.message,event.filename,event.lineno));
function createNonRepeatingQueue(items){
 const queue=[...items];for(let i=queue.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[queue[i],queue[j]]=[queue[j],queue[i]]}
 let previous="";try{previous=localStorage.getItem(ROTATION_START_KEY)||""}catch(_){}
 const different=queue.findIndex(item=>item.symbol!==previous);if(different>0)queue.push(...queue.splice(0,different));
 try{if(queue.length)localStorage.setItem(ROTATION_START_KEY,queue[0].symbol)}catch(_){}return queue;
}
function chinaCalendarDate(){return new Intl.DateTimeFormat("en-CA",{timeZone:"Asia/Shanghai",year:"numeric",month:"2-digit",day:"2-digit"}).format(new Date())}
function chinaClock(){const parts=new Intl.DateTimeFormat("en-GB",{timeZone:"Asia/Shanghai",year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",hourCycle:"h23"}).formatToParts(new Date());return Object.fromEntries(parts.filter(x=>x.type!=="literal").map(x=>[x.type,Number(x.value)]))}
function chinaMinutesOfDay(){const t=chinaClock();return t.hour*60+t.minute}
function millisecondsUntilDailyRefresh(){const t=chinaClock(),now=Date.UTC(t.year,t.month-1,t.day,t.hour,t.minute),target=Date.UTC(t.year,t.month-1,t.day,16,35);if(!dailyCheckCompleted()&&now>=target)return 1000;return Math.max(1000,target>now?target-now:target+86400000-now)}
function isTodayPublishedSnapshot(summary){if(!summary||typeof summary.generated_at_utc!=="string")return false;const generated=new Date(summary.generated_at_utc);if(!Number.isFinite(generated.getTime()))return false;return new Intl.DateTimeFormat("en-CA",{timeZone:"Asia/Shanghai",year:"numeric",month:"2-digit",day:"2-digit"}).format(generated)===chinaCalendarDate()}
function dailyCheckCompleted(){try{return localStorage.getItem(SIGNAL_CHECK_KEY)===chinaCalendarDate()}catch(_){return false}}
function markDailyCheckCompleted(){try{localStorage.setItem(SIGNAL_CHECK_KEY,chinaCalendarDate())}catch(_){}}
function readSignalSnapshot(){
 try{
  const raw=localStorage.getItem(SIGNAL_SNAPSHOT_KEY);if(!raw)return null;
  const value=JSON.parse(raw);
  if(!value||typeof value.market_date!=="string"||!/^\d{4}-\d{2}-\d{2}$/.test(value.market_date)||value.checked_on!==chinaCalendarDate()||!Array.isArray(value.universe)||!Array.isArray(value.signals)||!Array.isArray(value.previous_signals)){localStorage.removeItem(SIGNAL_SNAPSHOT_KEY);return null}
  const symbols=new Set(value.universe.map(x=>x?.symbol).filter(Boolean));
  if(value.signals.some(x=>!x||x.confirmation_date!==value.market_date||!symbols.has(x.symbol)))return null;
  if(value.previous_signals.some(x=>!x||x.confirmation_date!==value.previous_market_date||!symbols.has(x.symbol)))return null;
  return {market_date:value.market_date,previous_market_date:value.previous_market_date,universe:value.universe,signals:value.signals,previous_signals:value.previous_signals,checked_on:value.checked_on};
 }catch(_){return null}
}
function applySignalSnapshot(snapshot){
 activeSignalDate=snapshot.market_date;activeSignalSnapshot=snapshot;universe=snapshot.universe;
 const next=snapshot.signals;
 signalStocks=createNonRepeatingQueue(next);const activeSymbols=new Set(signalStocks.map(x=>x.symbol));for(const symbol of liveQuoteBySymbol.keys())if(!activeSymbols.has(symbol))liveQuoteBySymbol.delete(symbol);ticker.render(next.length?next:snapshot.previous_signals,next.length?"ready":"previous");
 if(typeof window.setCardOrder==="function"){
  if(!window.setCardOrder(signalStocks.map(x=>x.symbol)))console.error("[CN] card order rejected");
  else $("rolling-cards-frame").classList.add("is-ready");
 }
 if(signalStocks.length)startCarousel(0);else{stopCarousel();clearSelectedStock()}
}
function persistSignalSnapshot(snapshot){
 try{localStorage.setItem(SIGNAL_SNAPSHOT_KEY,JSON.stringify({...snapshot,checked_on:chinaCalendarDate()}))}
 catch(error){console.warn("[CN] daily signal snapshot could not be persisted",error)}
}
function sendFrame(frame,payload){try{frame?.contentWindow?.postMessage(payload,location.origin)}catch(_){}}
function sendLogoTransitionStart(){sendFrame(logoFrame,{type:"VEGAS_LOGO_TRANSITION_START"})}
function cancelLogoTransition(){sendFrame(logoFrame,{type:"VEGAS_LOGO_TRANSITION_CANCEL"})}
function sendLogo(item,market){
 if(!item){sendFrame(logoFrame,{type:"VEGAS_LOGO_CLEAR"});return}
 const code=String(item.code||item.symbol||"").replace(/^(SH|SZ|BJ)/,"");
 sendFrame(logoFrame,{type:"VEGAS_LOGO_SET_SYMBOL",symbol:String(item.symbol||code),name:String(item.name||market?.name||code),code,timeframe:"1D"});
}
function syncFrames(){const item=signalStocks[carouselIndex];sendLogo(item||null,item?universe.find(s=>s.symbol===item.symbol):null)}
function clearSelectedStock(){sendLogo(null);chart.setCandles([]);chart.setVegasEmaCandles([])}
function stopCarousel(){if(carouselTimer!==null)clearTimeout(carouselTimer);if(transitionTimer!==null)clearTimeout(transitionTimer);carouselTimer=transitionTimer=null;transitionToken++;cancelLogoTransition();$("app").classList.remove("is-symbol-transitioning")}
function waitTransition(ms,token){return new Promise(resolve=>{transitionTimer=setTimeout(()=>{transitionTimer=null;resolve(token===transitionToken)},ms)})}
function setInteractionLock(source,active){if(destroyed)return;if(active){interactionLocks.add(source);if(!$("app").classList.contains("is-symbol-transitioning"))stopCarousel();return}interactionLocks.delete(source);if(!interactionLocks.size&&!isHidden()&&signalStocks.length)scheduleNext()}
function setUserRotationPaused(paused){if(rotationPaused===paused)return;rotationPaused=paused;if(paused){if(carouselTimer!==null)clearTimeout(carouselTimer);carouselTimer=null;return}if(!isHidden()&&!interactionLocks.size&&transitionTimer===null&&!$("app").classList.contains("is-symbol-transitioning"))scheduleNext()}
rotationPause=createKlineRotationPause({target:host,onToggle:()=>setUserRotationPaused(!rotationPaused)});
async function transitionToIndex(index,{initial=false}={}){
 if(destroyed||isHidden()||(!initial&&interactionLocks.size)||!signalStocks.length)return;
 if(carouselTimer!==null)clearTimeout(carouselTimer);carouselTimer=null;if(transitionTimer!==null)clearTimeout(transitionTimer);transitionTimer=null;
 const token=++transitionToken;carouselIndex=(index+signalStocks.length)%signalStocks.length;
 const item=signalStocks[carouselIndex],market=universe.find(s=>s.symbol===item.symbol);$("app").classList.add("is-symbol-transitioning");
 if(!initial)sendLogoTransitionStart();
 if(!initial&&!await waitTransition(1500,token))return;
 const loaded=await controller.select(item.symbol,market?.last_date||"");if(destroyed||token!==transitionToken)return;
 const state=controller.state;
 if(!loaded&&!(state.symbol===item.symbol&&state.count>0)){cancelLogoTransition();$("app").classList.remove("is-symbol-transitioning");console.warn("[CN] Tencent chart not ready",item.symbol);scheduleNext();return}
 const liveQuote=liveQuoteBySymbol.get(item.symbol);if(liveQuote?.date===chinaCalendarDate())controller.updateLiveQuote(liveQuote);sendLogo(item,market);$("app").classList.remove("is-symbol-transitioning");
 transitionTimer=setTimeout(()=>{transitionTimer=null;if(token===transitionToken)scheduleNext()},1500);
}
async function refreshCards({force=false}={}){
 if(destroyed||isHidden()||typeof window.updateQuotes!=="function")return false;
 try{
  let rows=window.__CN_CARD_DATA__;
  if(!force&&!Array.isArray(rows)&&window.__CN_CARD_DATA_READY__)rows=await window.__CN_CARD_DATA_READY__;
  if(force||!Array.isArray(rows)){
   const response=await fetch(DATA+"cards.json",{cache:"no-store"});
   if(!response.ok)throw new Error("CN500 cards HTTP "+response.status);
   rows=await response.json();
   window.__CN_CARD_DATA__=rows;
  }
  if(destroyed||isHidden())return false;
  if(!Array.isArray(rows)||rows.length!==500)throw new Error("CN500 cards snapshot must contain exactly 500 rows");
  const seen=new Set();
  for(const row of rows){if(!row||typeof row.symbol!=="string"||!row.symbol||seen.has(row.symbol))throw new Error("CN500 cards snapshot contains an invalid or duplicate symbol");seen.add(row.symbol)}
  window.updateQuotes(rows.map((row,index)=>[index,Number(row.latest_close),Number(row.previous_close)]));
  window.__CN_CARD_SNAPSHOT_AT__=Date.now();
  return true;
 }catch(error){if(!destroyed)console.warn("[CN] card snapshot refresh failed",error);return false}
}
function scheduleNext(){if(destroyed||isHidden()||rotationPaused||interactionLocks.size||signalStocks.length<2||$("app").classList.contains("is-symbol-transitioning"))return;if(carouselTimer!==null)clearTimeout(carouselTimer);carouselTimer=setTimeout(()=>{carouselTimer=null;void transitionToIndex(carouselIndex+1)},7000)}
function startCarousel(index=0){stopCarousel();void transitionToIndex(index,{initial:true})}
async function refreshSignals(){
 if(destroyed||isHidden())return null;
 const token=++signalRefreshToken;signalRefreshController?.abort();
 const request=new AbortController();signalRefreshController=request;
 try{
  const [summary,stocks,today,previous]=await Promise.all(["summary.json","universe.json","signals.json","signals.previous.json"].map(n=>fetch(DATA+n,{cache:"no-store",signal:request.signal}).then(r=>{if(!r.ok)throw new Error("data "+n+" unavailable");return r.json()})));
  if(destroyed||token!==signalRefreshToken)return null;
  if(!summary?.market_date||!/^\d{4}-\d{2}-\d{2}$/.test(summary.market_date)||!Array.isArray(stocks)||!Array.isArray(today)||!Array.isArray(previous)||!summary.previous_market_date)throw new Error("CN market snapshot incomplete");
  const eligible=new Set(stocks.map(x=>x?.symbol).filter(Boolean));
  if(today.some(x=>!x||x.confirmation_date!==summary.market_date||!eligible.has(x.symbol)))throw new Error("CN daily signal snapshot failed validation");
  if(previous.some(x=>!x||x.confirmation_date!==summary.previous_market_date||!eligible.has(x.symbol)))throw new Error("CN previous-session signal snapshot failed validation");
  if(activeSignalDate&&summary.market_date<activeSignalDate)return summary;
  const snapshot={market_date:summary.market_date,previous_market_date:summary.previous_market_date,universe:stocks,signals:today,previous_signals:previous};
  if(activeSignalDate===summary.market_date&&activeSignalSnapshot&&JSON.stringify(snapshot)===JSON.stringify(activeSignalSnapshot))return summary;
  persistSignalSnapshot(snapshot);applySignalSnapshot(snapshot);
  return summary;
 }catch(error){if(error?.name==="AbortError"||destroyed||token!==signalRefreshToken)return null;if(!activeSignalDate)ticker.render([],"unavailable");throw error}
 finally{if(signalRefreshController===request)signalRefreshController=null}
}
async function boot(){
 const saved=readSignalSnapshot();if(saved)applySignalSnapshot(saved);else ticker.render([],"waiting");
 if(!signalStocks.length&&!$("app").classList.contains("is-symbol-transitioning"))sendLogo(null);
 try{await refreshSignals()}catch(error){console.warn("[CN] signal initialization failed",error);if(!activeSignalDate)ticker.render([],"unavailable")}
 if(typeof window.updateQuotes==="function")await refreshCards();window.__CN_READY__=true;startForegroundTimers();void refreshLiveMarket();
}
async function refreshDailySnapshot(){
 if(destroyed||isHidden()||chinaMinutesOfDay()<995||dailyCheckCompleted())return true;
 try{
  const summary=await refreshSignals();
  if(!isTodayPublishedSnapshot(summary)){console.info("[CN] daily scan is not published yet; will check again without starting another scan");return false}
  const cardsUpdated=await refreshCards({force:true});
  if(!cardsUpdated){console.warn("[CN] daily cards are not ready; waiting for the published snapshot");return false}
  await controller.refresh();markDailyCheckCompleted();console.info("[CN] daily market snapshot refreshed",summary.market_date);return true;
 }catch(error){console.warn("[CN] daily market snapshot refresh failed; will retry status check",error);return false}
}
function scheduleDailyCheck(){
 if(destroyed||isHidden()||dailyCheckCompleted())return;
 if(dailyRefreshTimer!==null)clearTimeout(dailyRefreshTimer);
 const minutes=chinaMinutesOfDay();
 if(minutes<995){startForegroundTimers();return}
 if(minutes>=1260){startForegroundTimers();return}
 dailyRefreshTimer=setTimeout(()=>{dailyRefreshTimer=null;void refreshDailySnapshot().then(done=>{if(destroyed||isHidden())return;if(done)startForegroundTimers();else scheduleDailyRetry()})},1000);
}
function scheduleDailyRetry(){
 if(destroyed||isHidden()||dailyCheckCompleted())return;
 if(chinaMinutesOfDay()>=1260){startForegroundTimers();return}
 if(dailyRefreshTimer!==null)clearTimeout(dailyRefreshTimer);
 dailyRefreshTimer=setTimeout(()=>{dailyRefreshTimer=null;void refreshDailySnapshot().then(done=>{if(destroyed||isHidden())return;if(done)startForegroundTimers();else scheduleDailyRetry()})},300000);
}
function stopForegroundTimers(){if(dailyRefreshTimer!==null)clearTimeout(dailyRefreshTimer);if(marketRefreshTimer!==null)clearTimeout(marketRefreshTimer);dailyRefreshTimer=marketRefreshTimer=null}
function isChinaTradingSession(){
 const t=chinaClock(),day=new Date(Date.UTC(t.year,t.month-1,t.day)).getUTCDay(),minutes=t.hour*60+t.minute;
 return day>=1&&day<=5&&((minutes>=570&&minutes<690)||(minutes>=780&&minutes<900));
}
async function refreshLiveMarket(){
 if(destroyed||isHidden()||!isChinaTradingSession()||marketRefreshBusy)return false;
 const symbols=[...new Set(signalStocks.map(item=>item.symbol).filter(Boolean))];
 if(!symbols.length)return false;
 marketRefreshBusy=true;let refreshed=0;
 try{
  for(const symbol of symbols){
   if(destroyed||isHidden()||!isChinaTradingSession())break;
   try{
    const quote=await liveQuotes.read(symbol);
    if(destroyed||isHidden())break;
    if(!quote)continue;
    const datedQuote={...quote,date:chinaCalendarDate()};
    if(!signalStocks.some(item=>item.symbol===symbol))continue;
    liveQuoteBySymbol.set(symbol,datedQuote);refreshed++;
    if(controller.state.symbol===symbol)controller.updateLiveQuote(datedQuote);
   }catch(error){if(!destroyed&&!isHidden())console.warn("[CN] five-minute Tencent signal K-line quote failed",symbol,error)}
  }
  return refreshed>0;
 }finally{marketRefreshBusy=false}
}
function millisecondsUntilNextMarketRefresh(){
 if(isChinaTradingSession())return 300000;
 const t=chinaClock(),now=Date.UTC(t.year,t.month-1,t.day,t.hour,t.minute),base=Date.UTC(t.year,t.month-1,t.day);
 for(let offset=0;offset<8;offset++){
  const day=new Date(base+offset*86400000),weekday=day.getUTCDay();
  if(weekday===0||weekday===6)continue;
  for(const [hour,minute] of [[9,30],[13,0]]){
   const target=Date.UTC(day.getUTCFullYear(),day.getUTCMonth(),day.getUTCDate(),hour,minute);
   if(target>now)return Math.max(1000,target-now);
  }
 }
 return 86400000;
}
function scheduleMarketRefresh(){
 if(destroyed||isHidden())return;
 if(marketRefreshTimer!==null)clearTimeout(marketRefreshTimer);
 marketRefreshTimer=setTimeout(()=>{marketRefreshTimer=null;void refreshLiveMarket().finally(()=>scheduleMarketRefresh())},millisecondsUntilNextMarketRefresh());
}
function startForegroundTimers(){
 if(destroyed||isHidden())return;
 if(dailyRefreshTimer!==null)clearTimeout(dailyRefreshTimer);
 dailyRefreshTimer=setTimeout(()=>{dailyRefreshTimer=null;void refreshDailySnapshot().then(done=>{if(destroyed||isHidden())return;if(done)startForegroundTimers();else scheduleDailyRetry()})},millisecondsUntilDailyRefresh());
 if(marketRefreshTimer===null)scheduleMarketRefresh();
}
function suspendRuntime(){if(destroyed)return;document.documentElement.classList.add("page-hidden");stopCarousel();stopForegroundTimers();signalRefreshToken++;signalRefreshController?.abort();signalRefreshController=null;interactionLocks.clear();controller.suspend();ticker.setPaused(true)}
async function resumeRuntime(){
 if(destroyed||isHidden())return;
 document.documentElement.classList.remove("page-hidden");ticker.setPaused(false);startForegroundTimers();void refreshDailySnapshot();void refreshLiveMarket();
 if(!signalStocks.length){await controller.resume({refresh:false});return}
 carouselIndex=carouselIndex%signalStocks.length;
 const item=signalStocks[carouselIndex],market=universe.find(s=>s.symbol===item.symbol),token=++transitionToken;
 $("app").classList.add("is-symbol-transitioning");sendLogoTransitionStart();
 const loaded=await controller.resume({refresh:true,nextSymbol:item.symbol,expectedLastDate:market?.last_date||""});
 if(destroyed||isHidden()||token!==transitionToken)return;
 const state=controller.state;
 if(!loaded&&!(state.symbol===item.symbol&&state.count>0)){cancelLogoTransition();$("app").classList.remove("is-symbol-transitioning");scheduleNext();return}
 const liveQuote=liveQuoteBySymbol.get(item.symbol);if(liveQuote?.date===chinaCalendarDate())controller.updateLiveQuote(liveQuote);sendLogo(item,market);$("app").classList.remove("is-symbol-transitioning");
 transitionTimer=setTimeout(()=>{transitionTimer=null;if(token===transitionToken)scheduleNext()},1500);
 }

function teardown(){if(destroyed)return;destroyed=true;signalRefreshToken++;signalRefreshController?.abort();signalRefreshController=null;stopCarousel();stopForegroundTimers();interactionLocks.clear();pageLifecycle?.destroy();rotationPause?.destroy();controller.destroy();chart.destroy();ticker.destroy();lifecycle.destroy()}
pageLifecycle=createPageLifecycle({documentRef:document,windowRef:window,onSuspend:suspendRuntime,onResume:resumeRuntime,onPageHideFinal:teardown});
document.documentElement.classList.toggle("page-hidden",isHidden());
lifecycle.listen(logoFrame,"load",()=>{if($("app").classList.contains("is-symbol-transitioning"))sendLogoTransitionStart();else syncFrames()});
if(logoFrame.contentDocument?.readyState==="complete")syncFrames();
lifecycle.listen(window,"vegas-cards-ready",()=>{void refreshCards();if(typeof window.setCardOrder==="function"&&window.setCardOrder(signalStocks.map(x=>x.symbol)))$("rolling-cards-frame").classList.add("is-ready")});
lifecycle.listen(window,"message",event=>{
 if(event.origin!==location.origin)return;
 if(event.source===logoFrame?.contentWindow&&event.data?.type==="VEGAS_LOGO_READY"){if($("app").classList.contains("is-symbol-transitioning")){sendLogoTransitionStart();}else syncFrames();return}
 if(event.source!==window)return;
 if(event.data?.type==="VEGAS_CARD_INTERACTION"&&typeof event.data.active==="boolean"){setInteractionLock("rolling-cards",event.data.active);return}
 if(event.data?.type==="VEGAS_CARD_SELECT"){const symbol=String(event.data.symbol||""),index=signalStocks.findIndex(x=>x.symbol===symbol);if(index>=0)void transitionToIndex(index)}
});
lifecycle.listen(window,"beforeunload",teardown,{once:true});startForegroundTimers();
boot().catch(error=>{if(!activeSignalDate){clearSelectedStock();ticker.render([],"unavailable")}console.error("[CN] initialization failed",error)});
