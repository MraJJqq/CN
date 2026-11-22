import {chromium,webkit} from "playwright";
const browserType=process.env.CN_BROWSER==="webkit"?webkit:chromium;
const browser=await browserType.launch({headless:true}),page=await browser.newPage({viewport:{width:390,height:844}}),errors=[];
page.on("pageerror",e=>errors.push(e.message));
page.on("console",m=>{if(m.type()==="error")errors.push("console: "+m.text())});
page.on("requestfailed",r=>{const reason=r.failure()?.errorText||"";if(reason!=="net::ERR_ABORTED")errors.push("request failed: "+r.url()+" "+reason)});
try{
 await page.goto("http://127.0.0.1:8765/",{waitUntil:"domcontentloaded"});
 await page.bringToFront();
 await page.waitForFunction(()=>document.visibilityState==="visible",{timeout:10000});
 await page.waitForFunction(()=>typeof window.setCardOrder==="function",{timeout:30000});
 await page.waitForFunction(()=>window.__CN_READY__===true,{timeout:30000});
 await page.waitForFunction(()=>typeof window.__CN_CARD_SNAPSHOT_AT__==="number",{timeout:15000}).catch(async error=>{const state=await page.evaluate(()=>({ready:window.__CN_READY__,cardSnapshotAt:window.__CN_CARD_SNAPSHOT_AT__??null,cardDataReady:typeof window.__CN_CARD_DATA_READY__,cardDataCount:Array.isArray(window.__CN_CARD_DATA__)?window.__CN_CARD_DATA__.length:null,updateQuotes:typeof window.updateQuotes,setCardOrder:typeof window.setCardOrder,signalTrack:document.querySelector("#signal-track")?.textContent||"",scripts:[...document.scripts].map(x=>x.src)}));throw new Error("CN card snapshot initialization timed out: "+JSON.stringify({state,errors})+"; "+error.message)});
 await page.waitForFunction(()=>["#logo-frame","#timeframe-frame","#rolling-cards-frame"].every(s=>{const e=document.querySelector(s);return e?.classList.contains("is-ready")&&Number(getComputedStyle(e).opacity)>=0.99}),{timeout:15000});
 const data=await page.evaluate(async()=>{
  const [summary,universe,signals]=await Promise.all(["summary.json","universe.json","signals.json"].map(async n=>{const r=await fetch("./data/"+n);if(!r.ok)throw new Error(n+" unavailable");return r.json()}));
  const cardsResponse=await fetch("./data/cards.json");if(!cardsResponse.ok)throw new Error("cards.json unavailable");const cards=await cardsResponse.json();
  const activeSignals=signals.filter(x=>x.confirmation_date===summary.market_date&&universe.some(s=>s.symbol===x.symbol));const expected=activeSignals.length;
  const moduleState=Object.fromEntries(["#logo-frame","#timeframe-frame","#rolling-cards-frame"].map(s=>{const e=document.querySelector(s);return[s,{opacity:getComputedStyle(e).opacity,ready:e.classList.contains("is-ready")}]}));
  const visible=Object.values(moduleState).every(x=>Number(x.opacity)>=0.99);
  const symbol=universe[0]?.symbol;if(!symbol)throw new Error("No eligible chart symbol");
  const r=await fetch("./data/charts/"+encodeURIComponent(symbol)+".json.gz");if(!r.ok)throw new Error("Compressed chart missing");
  const chart=await new Response(new Blob([await r.arrayBuffer()]).stream().pipeThrough(new DecompressionStream("gzip"))).json();
  const backgroundState=Object.fromEntries(["html","body","#app"].map(s=>[s,getComputedStyle(document.querySelector(s)).backgroundColor]));
  const transparentState=Object.fromEntries(["#kline-host","#logo-frame","#timeframe-frame","#rolling-cards-frame","#signal-ticker"].map(s=>[s,getComputedStyle(document.querySelector(s)).backgroundColor]));
  return {expected,active:document.querySelectorAll("#vp>.c").length,bars:chart.bars?.length||0,cardSnapshotAt:window.__CN_CARD_SNAPSHOT_AT__||0,allCardSymbols:cards.map(x=>x.symbol),signalSymbols:activeSignals.map(x=>x.symbol),ticker:document.querySelector("#signal-track").textContent.trim(),visible,visibilityState:document.visibilityState,moduleState,backgroundState,transparentState};
 });
 console.log("CN browser diagnostics:",JSON.stringify(data));
 if(data.bars<1||data.active!==data.expected||!data.cardSnapshotAt||!data.ticker||!data.visible)throw new Error("A-share data/card/ticker/module visibility contract failed");
 if(data.backgroundState["#app"]!=="rgb(11, 16, 32)")throw new Error("CN main container background must remain #0B1020: "+JSON.stringify(data.backgroundState));
 if(Object.values(data.transparentState).some(value=>value!=="rgba(0, 0, 0, 0)"))throw new Error("CN module containers must remain transparent: "+JSON.stringify(data.transparentState));
 const logoAssetCheck=await page.evaluate(async()=>{const response=await fetch("./assets/Brand/VEGAS-Logo.svg");if(!response.ok)throw new Error("VEGAS logo SVG unavailable");const source=await response.text();const doc=new DOMParser().parseFromString(source,"image/svg+xml");if(doc.querySelector("parsererror"))throw new Error("VEGAS logo SVG is invalid XML");const background=[...doc.querySelectorAll("rect")].find(e=>Number(e.getAttribute("width"))>=200&&Number(e.getAttribute("height"))>=200&&e.getAttribute("fill")&&e.getAttribute("fill")!=="none");return{hasOpaqueFullCanvasBackground:Boolean(background)}});if(logoAssetCheck.hasOpaqueFullCanvasBackground)throw new Error("VEGAS logo SVG must not contain an opaque full-canvas background rectangle");
 const stress=await page.evaluate(({allCardSymbols,signalSymbols})=>{const start=performance.now();const accepted=window.setCardOrder(allCardSymbols);const elapsed=performance.now()-start;const count=document.querySelectorAll("#vp>.c").length;const restored=window.setCardOrder(signalSymbols);return{accepted,elapsed,count,restored,restoredCount:document.querySelectorAll("#vp>.c").length}},{allCardSymbols:data.allCardSymbols,signalSymbols:data.signalSymbols});
 if(!stress.accepted||stress.count!==500||!stress.restored||stress.restoredCount!==data.expected||stress.elapsed>5000)throw new Error("CN500 500-card stress check failed: "+JSON.stringify(stress));
 console.log("CN CN500 500-card DOM stress:",JSON.stringify(stress));
 for(const v of [{width:390,height:844},{width:844,height:390},{width:320,height:740},{width:768,height:1024},{width:1024,height:768}]){
  await page.setViewportSize(v);await page.waitForTimeout(80);
  const l=await page.evaluate(()=>Object.fromEntries(["#app","#logo-frame","#timeframe-frame","#kline-host","#rolling-cards-frame","#signal-ticker"].map(s=>{const e=document.querySelector(s);if(!e)throw new Error("Required layout element missing: "+s);const r=e.getBoundingClientRect();return[s,{left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:r.width,height:r.height,z:getComputedStyle(e).zIndex}]})));
  for(const s of ["#app","#logo-frame","#kline-host","#rolling-cards-frame"])if(l[s].width<v.width-2||l[s].left< -1||l[s].right>v.width+1)throw new Error("Viewport bounds failed: "+s);
  if(l["#signal-ticker"].width<=0||l["#signal-ticker"].left<0||l["#signal-ticker"].right>v.width+1||l["#signal-ticker"].width>v.width-10)throw new Error("Ticker safe-area bounds failed at "+v.width+"x"+v.height+": "+JSON.stringify(l["#signal-ticker"]));
  const logo=await page.evaluate(()=>{const f=document.querySelector("#logo-frame"),d=f.contentDocument,w=f.clientWidth;const ids=["#logo-brand","#logo-line","#logo-image","#logo-symbol","#logo-code","#logo-countdown"];return {frameWidth:w,items:Object.fromEntries(ids.map(s=>{const e=d?.querySelector(s);if(!e)return[s,null];const r=e.getBoundingClientRect();return[s,{left:r.left,right:r.right,width:r.width,height:r.height,fontSize:getComputedStyle(e).fontSize}]}))}});
  if(!logo.items["#logo-brand"]||logo.items["#logo-brand"].left<0||logo.items["#logo-brand"].right>logo.frameWidth+1)throw new Error("Logo container overflow at "+v.width+"x"+v.height+": "+JSON.stringify(logo));
  for(const s of ["#logo-line","#logo-image","#logo-symbol","#logo-code","#logo-countdown"]){const x=logo.items[s];if(x&&(x.left<0||x.right>logo.frameWidth+1))throw new Error("Logo child overflow "+s+" at "+v.width+"x"+v.height+": "+JSON.stringify(x))}
  const tickerText=await page.evaluate(()=>{const e=document.querySelector("#signal-track .signal-row")||document.querySelector("#signal-track .signal-empty");return e?parseFloat(getComputedStyle(e).fontSize):0});
  if(tickerText<9)throw new Error("Ticker text below 9px at "+v.width+"x"+v.height);
  if(l["#kline-host"].top>1||l["#kline-host"].left>1||l["#kline-host"].right<v.width-1||l["#kline-host"].bottom<v.height-1)throw new Error("Full-screen K-line viewport contract failed");
  if(l["#rolling-cards-frame"].bottom<v.height-1||l["#signal-ticker"].bottom<v.height-1)throw new Error("Bottom overlay alignment failed");
  if(l["#timeframe-frame"].left<0||l["#timeframe-frame"].right>v.width+1||l["#timeframe-frame"].bottom>v.height+1)throw new Error("Timeframe safe-area bounds failed");
 }
 const viewportInteraction=await page.evaluate(async()=>{
  const key="cn-kline-viewport-v1",canvas=document.querySelector("#kline-host>canvas:not([aria-hidden=true])");
  if(!canvas)throw new Error("K-line interaction canvas missing");
  const supports=(doc)=>{
   const visit=rules=>{for(const rule of rules){if(rule.type===12&&/not\s*\(\s*height\s*:\s*100dvh\s*\)/i.test(rule.conditionText||""))return true;if(rule.cssRules&&visit(rule.cssRules))return true;}return false};
   return [...doc.styleSheets].some(sheet=>{try{return visit(sheet.cssRules)}catch(_){return false}});
  };
  const mainFallback=supports(document),frame=document.querySelector("#timeframe-frame"),frameStyle=getComputedStyle(frame),period=frame.contentDocument.querySelector(".tf .period"),periodContainer=frame.contentDocument.querySelector(".tf"),periodContainerStyle=periodContainer?getComputedStyle(periodContainer):null;
  const safeBottom=parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--v6-safe-bottom"))||0,frameRect=frame.getBoundingClientRect();
  const supportsDvh=CSS.supports("height","100dvh");
  const frameFallback=supportsDvh||(frameRect.top<=1&&frameRect.bottom>=innerHeight-safeBottom-2&&frameStyle.clipPath.includes("68.83%"));
  const singlePeriodReady=Boolean(period&&period.textContent.trim()==="1D"&&frame.contentDocument.querySelectorAll(".tf .period").length===1&&frame.contentDocument.querySelectorAll(".tf button").length===0&&periodContainer&&periodContainer.scrollHeight<=periodContainer.clientHeight&&periodContainerStyle.scrollSnapType==="none"&&frameStyle.pointerEvents==="none");
  const fontUrl=new URL("../../fonts/ChakraPetch-Bold.ttf",frame.contentWindow.location.href),fontResponse=await fetch(fontUrl);
  if(!fontResponse.ok)throw new Error("Timeframe Chakra Petch font request failed: "+fontUrl.pathname);
  await frame.contentDocument.fonts.load('700 28px "Chakra Petch"');
  const timeframeFontLoaded=frame.contentDocument.fonts.check('700 28px "Chakra Petch"');
  const logoDocument=document.querySelector("#logo-frame").contentDocument;
  await logoDocument.fonts.load('700 12px "Chakra Petch"');
  const logoFontLoaded=logoDocument.fonts.check('700 12px "Chakra Petch"');
  const read=()=>JSON.parse(localStorage.getItem(key)||"null");
  const send=(type,id,x,y)=>canvas.dispatchEvent(new PointerEvent(type,{bubbles:true,cancelable:true,pointerId:id,pointerType:"touch",clientX:x,clientY:y,button:0,buttons:type==="pointerup"||type==="pointercancel"?0:1}));
  const rect=canvas.getBoundingClientRect(),cx=rect.left+rect.width*.55,cy=rect.top+rect.height*.5;
  const before=read();
  send("pointerdown",71,cx,cy);send("pointermove",71,cx-55,cy);send("pointerup",71,cx-55,cy);
  await new Promise(resolve=>setTimeout(resolve,100));
  const dragged=read();
  const beforePinch=dragged?.barW;
  send("pointerdown",72,cx-45,cy);send("pointerdown",73,cx+45,cy);
  send("pointermove",73,cx+100,cy);send("pointerup",73,cx+100,cy);send("pointerup",72,cx-45,cy);
  const pinched=read();
  send("pointerdown",74,cx,cy);send("pointercancel",74,cx,cy);
  return {mainFallback,frameFallback,supportsDvh,singlePeriodReady,timeframeFontLoaded,logoFontLoaded,fontPath:fontUrl.pathname,dragChanged:Boolean(before&&dragged&&(before.anchorTime!==dragged.anchorTime||before.anchorOffset!==dragged.anchorOffset)),pinchChanged:Boolean(Number.isFinite(beforePinch)&&Number.isFinite(pinched?.barW)&&pinched.barW>beforePinch*1.1),before,dragged,pinched};
 });
 if(!viewportInteraction.mainFallback||!viewportInteraction.frameFallback||!viewportInteraction.singlePeriodReady||!viewportInteraction.timeframeFontLoaded||!viewportInteraction.logoFontLoaded)throw new Error("Fullscreen fallback or residue-free static 1D period contract failed: "+JSON.stringify(viewportInteraction));
 if(!viewportInteraction.dragChanged||!viewportInteraction.pinchChanged)throw new Error("K-line drag/pinch interaction contract failed: "+JSON.stringify(viewportInteraction));
 console.log("CN viewport interaction, static 1D display and Media fonts:",JSON.stringify(viewportInteraction));
 if(errors.length)throw new Error(errors.join(" | "));
 for(let pass=1;pass<=2;pass++){
  await page.reload({waitUntil:"domcontentloaded"});
  await page.waitForFunction(()=>window.__CN_READY__===true&&typeof window.setCardOrder==="function",{timeout:30000});
  await page.waitForFunction(()=>typeof window.__CN_CARD_SNAPSHOT_AT__==="number",{timeout:15000});
  await page.waitForFunction(()=>["#logo-frame","#timeframe-frame","#rolling-cards-frame"].every(s=>document.querySelector(s)?.classList.contains("is-ready")),{timeout:15000});
  const counts=await page.evaluate(()=>({mainCanvas:document.querySelectorAll("#kline-host>canvas").length,overlayCanvas:document.querySelectorAll("#kline-host>canvas[aria-hidden=true]").length,logoFrames:document.querySelectorAll("#logo-frame").length,timeframeFrames:document.querySelectorAll("#timeframe-frame").length,cardNodes:document.querySelectorAll("#vp>.c").length,tickerCycles:document.querySelectorAll("#signal-track>.signal-cycle").length}));
  if(counts.mainCanvas!==2||counts.overlayCanvas!==1||counts.logoFrames!==1||counts.timeframeFrames!==1)throw new Error("Reload left duplicate core module DOM: "+JSON.stringify(counts));
  if(counts.cardNodes!==data.expected)throw new Error("Reload left stale/duplicate card DOM: "+JSON.stringify(counts));
  if(counts.tickerCycles<1)throw new Error("Ticker did not recover after reload");
  console.log("CN reload pass "+pass+":",JSON.stringify(counts));
 }

 const delayedFrameRequests=[];
 const delayFrame=async route=>{delayedFrameRequests.push(route.request().url());await new Promise(resolve=>setTimeout(resolve,1200));await route.continue()};
 await page.route("**/assets/modules/logo/logo.html*",delayFrame);
 await page.route("**/assets/modules/timeframe-switch/index.html*",delayFrame);
 await page.reload({waitUntil:"domcontentloaded"});
 const firstPaintGate=await page.evaluate(()=>({modules:Object.fromEntries(["#logo-frame","#timeframe-frame"].map(s=>{const e=document.querySelector(s);return[s,{ready:e.classList.contains("is-ready"),opacity:Number(getComputedStyle(e).opacity)}]})),backgrounds:Object.fromEntries(["html","body","#app"].map(s=>[s,getComputedStyle(document.querySelector(s)).backgroundColor]))}));
 if(!delayedFrameRequests.some(x=>x.includes("/logo/logo.html"))||!delayedFrameRequests.some(x=>x.includes("/timeframe-switch/index.html")))throw new Error("Delayed iframe load gate was not exercised");
 if(Object.values(firstPaintGate.modules).some(x=>x.ready||x.opacity>0.01))throw new Error("Logo/timeframe iframe became visible before load completed: "+JSON.stringify(firstPaintGate));
 if(firstPaintGate.backgrounds["#app"]!=="rgb(11, 16, 32)")throw new Error("Unified #0B1020 full-screen app background missing during iframe load: "+JSON.stringify(firstPaintGate));
 await page.waitForFunction(()=>["#logo-frame","#timeframe-frame"].every(s=>document.querySelector(s)?.classList.contains("is-ready")),{timeout:15000});
 await page.unroute("**/assets/modules/logo/logo.html*",delayFrame);
 await page.unroute("**/assets/modules/timeframe-switch/index.html*",delayFrame);
 console.log("CN delayed iframe first-paint gate:",JSON.stringify({requests:delayedFrameRequests.length,firstPaintGate}));
 await page.evaluate(()=>{window.dispatchEvent(new PageTransitionEvent("pagehide",{persisted:true}));window.dispatchEvent(new PageTransitionEvent("pageshow",{persisted:true}))});
 await page.waitForFunction(()=>document.documentElement.classList.contains("page-hidden")===false);
 const restored=await page.evaluate(()=>({ticker:document.querySelector("#signal-track").textContent.trim(),canvas:document.querySelectorAll("#kline-host>canvas").length,frames:document.querySelectorAll("#logo-frame,#timeframe-frame,#rolling-cards-frame").length}));
 if(!restored.ticker||restored.canvas!==2||restored.frames!==3)throw new Error("BFCache-style pageshow recovery failed: "+JSON.stringify(restored));
 if(errors.length)throw new Error(errors.join(" | "));
 console.log("CN BFCache-style recovery:",JSON.stringify(restored));
 console.log("CN browser smoke passed: Tencent daily chart, CN500 signal cards, ticker, five viewport layouts, and two reload cycles.");
}finally{await browser.close()}
