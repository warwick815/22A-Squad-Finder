'use strict';
// Keep the existing reviewed-trade flow; arrange its panels into a trading workspace.
let terminalPlayer=null,terminalRange=7;
const renderExchangePanels=renderExchange;
renderExchange=function(){
 renderExchangePanels();
 const root=$('exchange-content');if(!exchangeData||!root.querySelector('.exchange-grid'))return;
 const oldGrid=root.querySelector('.exchange-grid'),accounts=root.querySelector('.market-account-grid');
 const market=oldGrid.children[0],order=oldGrid.children[1];
 const portfolio=Array.from(root.children).find(el=>el.tagName==='ARTICLE'&&!el.classList.contains('exchange-hero'));
 const workspace=document.createElement('div');workspace.className='trading-workspace';
 const left=document.createElement('div');left.className='terminal-watchlist';
 const centre=document.createElement('div');centre.className='terminal-centre';
 const right=document.createElement('div');right.className='terminal-sidebar';
 const chart=document.createElement('article');chart.className='panel terminal-chart';chart.id='terminal-chart';
 left.append(market);centre.append(accounts,chart);right.append(order);if(portfolio){right.append(portfolio);portfolio.innerHTML=terminalPortfolio(exchangeData);portfolio.querySelectorAll('[data-holding-player]').forEach(b=>b.addEventListener('click',()=>selectTerminalPlayer(b.dataset.holdingPlayer)));}
 workspace.append(left,centre,right);oldGrid.replaceWith(workspace);
 market.querySelector('h2').textContent='Market watch';
 root.querySelector('.exchange-hero h2').textContent='Player Exchange';
 const selected=exchangeData.market.find(p=>p.id===terminalPlayer)||exchangeData.market.find(p=>p.id!==data.me.id)||exchangeData.market[0];
 if(selected)selectTerminalPlayer(selected.id);else chart.innerHTML='<h2>Market chart</h2><p class="empty">Linked players will appear here once available.</p>';
 $('trade-target')?.addEventListener('change',e=>selectTerminalPlayer(e.target.value));
};
const openMarketHistory=showPriceHistory;
showPriceHistory=function(id){if($('terminal-chart'))selectTerminalPlayer(id);else openMarketHistory(id);};
function selectTerminalPlayer(id){
 const p=exchangeData.market.find(p=>p.id===id)||(exchangeData.own_stock?.id===id?exchangeData.own_stock:null);if(!p)return;
 terminalPlayer=id;drawTerminalChart(p);
 document.querySelectorAll('[data-price-player]').forEach(el=>{el.closest('tr')?.classList.toggle('market-selected',el.dataset.pricePlayer===id);el.setAttribute('aria-pressed',String(el.dataset.pricePlayer===id));});
 const target=$('trade-target');if(target&&Array.from(target.options).some(o=>o.value===id)){target.value=id;tradeEstimate();}
}
function terminalSeries(p,days){const cut=Date.now()/1000-days*86400;return (p.market?.price_history||[]).filter(v=>Number.isFinite(v.at)&&Number.isFinite(v.price)&&v.at>=cut).sort((a,b)=>a.at-b.at).filter((v,i,a)=>!i||v.at!==a[i-1].at);}
function terminalGraph(points){
 if(points.length<2)return '<div class="terminal-chart-empty"><span>Price history is building</span><p>Two recorded observations are needed. Refresh after the next hourly snapshot.</p></div>';
 const first=points[0],last=points.at(-1),low=Math.min(...points.map(p=>p.price)),high=Math.max(...points.map(p=>p.price)),padding=Math.max(2,(high-low)*.15),bottom=low-padding,top=high+padding;
 const x=p=>20+(p.at-first.at)/(last.at-first.at)*680,y=p=>320-(p.price-bottom)/(top-bottom)*285;
 let grid='',lines='';for(let i=0;i<5;i++){const value=bottom+(top-bottom)*i/4,yy=320-i*285/4;grid+=`<line x1="20" x2="700" y1="${yy}" y2="${yy}" class="chart-grid"/><text x="712" y="${yy+4}">$${fmt(value,1)}</text>`;}
 for(let i=1;i<points.length;i++){const a=points[i-1],b=points[i];if(b.at-a.at<=7200)lines+=`<line x1="${x(a)}" y1="${y(a)}" x2="${x(b)}" y2="${y(b)}" class="${b.price>=a.price?'chart-rise':'chart-fall'}"/>`;}
 const ticks=[first,points[Math.floor(points.length/2)],last];
 return `<svg viewBox="0 0 800 370" role="img" aria-label="Recorded share prices, from ${fmt(first.price)} to ${fmt(last.price)} dollars"><g>${grid}</g>${lines}${points.map(p=>`<circle cx="${x(p)}" cy="${y(p)}" r="3" class="chart-observation"><title>${esc(new Date(p.at*1000).toLocaleString('en-GB'))} · $${fmt(p.price)}</title></circle>`).join('')}${ticks.map((p,i)=>`<text x="${x(p)}" y="355" text-anchor="${i===0?'start':i===2?'end':'middle'}">${esc(new Date(p.at*1000).toLocaleString('en-GB',{day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'}))}</text>`).join('')}</svg>`;
}
function drawTerminalChart(p){
 const points=terminalSeries(p,terminalRange),delta=points.length>1?points.at(-1).price-points[0].price:null;
 $('terminal-chart').innerHTML=`<div class="terminal-chart-header"><div><span class="eyebrow">${p.id===data.me.id?'YOUR LISTING':'PLAYER / SHARE PRICE'}</span><h2>${esc(p.name)}</h2></div><div class="terminal-quote"><strong>$${fmt(p.price)}</strong><span class="${delta<0?'bad':'good'}">${delta===null?'Awaiting history':`${delta>=0?'+':'−'}$${fmt(Math.abs(delta))} (${fmt(delta/points[0].price*100,2)}%)`}</span></div></div><div class="terminal-chart-controls"><span class="pill ${p.tradable?'':'warning'}">${p.tradable?'Trading open':'Trading paused'}</span><div role="group" aria-label="Price history range">${[1,7,30].map(d=>`<button class="small secondary ${terminalRange===d?'active':''}" data-terminal-range="${d}" aria-pressed="${terminalRange===d}">${d===1?'24H':d+'D'}</button>`).join('')}</div></div><div class="terminal-plot">${terminalGraph(points)}</div><div class="terminal-chart-foot"><span>SEASON ELO <b>${fmt(p.rating,1)}</b></span><span>HELD <b>${fmt(p.supply?.owned||0)} / ${p.supply?.cap||500}</b></span><span>AVAILABLE <b>${fmt(p.supply?.remaining??500)}</b></span></div><p class="fine">Recorded hourly prices · gaps indicate missing observations · change is across this range’s recorded observations.</p>${p.id===data.me.id?'<p class="fine">Viewing your own stock. The order ticket remains on another player; self-trading is disabled.</p>':''}<details><summary>Recorded prices</summary><div class="price-records"><table><thead><tr><th>Time</th><th>Price</th></tr></thead><tbody>${points.slice().reverse().map(p=>`<tr><td>${esc(new Date(p.at*1000).toLocaleString('en-GB'))}</td><td>$${fmt(p.price)}</td></tr>`).join('')||'<tr><td colspan="2">No observations in this range.</td></tr>'}</tbody></table></div></details>`;
 $('terminal-chart').querySelectorAll('[data-terminal-range]').forEach(button=>button.addEventListener('click',()=>{terminalRange=Number(button.dataset.terminalRange);drawTerminalChart(p);}));
}

function terminalPortfolio(x){const priced=x.portfolio.filter(p=>p.net!=null),total=priced.reduce((n,p)=>n+p.net,0),profit=priced.reduce((n,p)=>n+p.profit,0);return `<span class="eyebrow">MY PORTFOLIO</span><h2>Held positions</h2><div class="terminal-portfolio-value">$${fmt(total)}<small>Estimated sale value · after fees</small></div><p class="${profit<0?'bad':'good'}">${profit>=0?'+':'−'}$${fmt(Math.abs(profit))} unrealised</p>${priced.length<x.portfolio.length?'<p class="fine">Unpriced positions excluded from value.</p>':''}<div class="terminal-positions">${x.portfolio.map(p=>`<div class="terminal-position"><button class="price-history-link" data-holding-player="${esc(p.id)}" ${x.market.some(m=>m.id===p.id)?'':'disabled'}>${esc(p.name)}</button><div><span>${fmt(p.quantity)} shares · cost $${fmt(p.cost)}</span><strong>${p.net==null?'Unpriced':'$'+fmt(p.net)}</strong></div><progress max="${Math.max(1,total)}" value="${p.net||0}" aria-label="Share of priced portfolio value"></progress><small class="${p.profit<0?'bad':'good'}">${p.profit==null?'Value unavailable':(p.profit>=0?'+':'−')+'$'+fmt(Math.abs(p.profit))} · ${p.tradable?'Open':'Frozen'}</small></div>`).join('')||'<p class="fine">No positions yet. Select a player to review your first order.</p>'}</div><p class="fine">Indicative value, not a guaranteed payout. Portfolio gains count toward daily ELO only when realised.</p>`;}
const renderTerminalMarket=renderMarket;
renderMarket=function(){renderTerminalMarket();document.querySelectorAll('[data-price-player]').forEach(el=>{el.closest('tr')?.classList.toggle('market-selected',el.dataset.pricePlayer===terminalPlayer);el.setAttribute('aria-pressed',String(el.dataset.pricePlayer===terminalPlayer));});};
