'use strict';
// Field reports: Most Wanted bounty, streak of the week, live squads and after-action reports (TF21).
(function(){
  const $=id=>document.getElementById(id);
  let rep=null,loading=false,deckYear=null;
  function demoReports(){const ps=data.players,now=Date.now()/1000,who=p=>({id:p.id,name:p.name,avatar:p.avatar});
    const sess=(i,ago)=>({server:i%2?'uk1':'uk2',map:i%2?'NorthAmerica':'Kavkazi',start:now-ago-3000,end:now-ago,kills:38-i*5,headshots:9,longest:{m:447.5,weapon:'SV98',name:ps[0].name},weapon:['SV98',11],
      members:ps.slice(0,4-i%2).map((p,j)=>({...who(p),kills:14-j*3,headshots:3-j%3})),top:{...who(ps[0]),kills:14}});
    return {enabled:true,bounty:{week:'2026-W43',name:'[49CO] Princess Pixel',kills:19,set_at:now-2*86400,status:'open'},
      history:[{week:'2026-W42',name:'BritishSam',kills:12,status:'claimed',claimed_by:who(ps[1]),weapon:'AMR 50',distance:312.4,headshot:true},{week:'2026-W41',name:'ImTheTozzy',kills:7,status:'escaped'}],
      streak:{count:13,weapon:'SV98',who:who(ps[0]),at:new Date((now-36000)*1000).toISOString()},live:[{server:'uk2',members:ps.slice(1,4).map(who),kills:12,since:now-1500}],
      sessions:[sess(0,7200),sess(1,90000)],deck:[demoDeck(ps,who)]};}
  // Demo deck: weeks 1–43 of 2026, mostly collected, some escaped, this week's card still open.
  const SUITS={spades:'♠',clubs:'♣',hearts:'♥',diamonds:'♦',black:'★',red:'★'};
  function demoDeck(ps,who){const R=['A','K','Q','J','10','9','8','7','6','5','4','3','2'],S=['spades','clubs','hearts','diamonds'];
    const names=['BritishSam','ImTheTozzy','[49CO] Princess Pixel','Kavkazi Ken','DesertFox','Mr Mortar','TankTom','LoneWolf'];
    const slots=[];let collected=0,escaped=0;
    for(let n=1;n<=54;n++){const face=n===53?['JOKER','black']:n===54?['JOKER','red']:[R[Math.floor((n-1)/4)],S[(n-1)%4]];
      const label=face[0]==='JOKER'?face[1][0].toUpperCase()+face[1].slice(1)+' Joker':({A:'Ace',K:'King',Q:'Queen',J:'Jack'}[face[0]]||face[0])+' of '+face[1][0].toUpperCase()+face[1].slice(1);
      const slot={n,label,face};
      if(n<=43){const status=n===43?'open':n%5===0?'escaped':'claimed';status==='claimed'?collected++:status==='escaped'?escaped++:0;
        Object.assign(slot,{status,name:n===43?'[49CO] Princess Pixel':names[n%names.length],kills:n===43?19:3+n%9,week:'2026-W'+String(n).padStart(2,'0'),claimed_by:status==='claimed'?who(ps[n%4]):null,image:`/api/reports/card/2026/${n}.png?v=demo`});}
      if(n===54)Object.assign(slot,{status:'hunter',name:ps[1].name,count:9,claimed_by:who(ps[1]),image:'/api/reports/card/2026/54.png?v=demo'});
      slots.push(slot);}
    return {year:'2026',slots,collected,escaped};}
  async function load(){if(typeof data==='undefined'||!data||loading)return;loading=true;
    try{rep=demo?demoReports():await api('/api/reports');render();}catch(e){$('reports-content').className='panel empty';$('reports-content').textContent=e.message;}finally{loading=false;}}
  const when=ts=>new Date(ts*1000).toLocaleString('en-GB',{weekday:'short',day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'});
  const person=p=>p?`<span class="shame-who">${typeof fantasyAvatar==='function'?fantasyAvatar(p):''}${p.id?`<button type="button" class="player-button" data-player="${esc(p.id)}">${esc(p.name)}</button>`:esc(p.name)}</span>`:'—';
  function poster(b){
    if(!b)return `<article class="wanted is-empty"><span class="wanted-head">Most Wanted</span><strong>Nobody this week</strong><p>A bounty is posted each Monday on whoever killed 22A members most the week before (3+ kills).</p></article>`;
    const claimed=b.status==='claimed';
    const deck=(rep.deck||[]).find(x=>x.slots.some(s=>s.week===b.week));const slot=deck&&deck.slots.find(s=>s.week===b.week);
    if(slot&&slot.image)return `<article class="wanted has-card ${claimed?'is-claimed':''}"><button type="button" class="wanted-card" data-deck-card="${slot.n}" aria-label="Open the ${esc(slot.label)}"><img src="${esc(slot.image)}" alt="${esc(slot.label)}: ${esc(b.name)}"></button>
      <div class="wanted-text"><span class="wanted-head">This week's card · ${esc(slot.label)}</span><strong class="wanted-name">${esc(b.name)}</strong><span class="wanted-crime">Killed 22A members ${fmt(b.kills)} times last week</span>
      ${claimed?`<p>Collected by ${person(b.claimed_by)}${b.weapon?' with the '+esc(b.weapon):''}${b.distance!=null?' at '+fmt(b.distance,0)+' m':''}${b.headshot?' · headshot':''}.</p>`
        :`<p class="wanted-reward">Reward: the card, the <b>Bounty hunter</b> ribbon and a Discord shout-out</p><p class="fine">First member to kill them on a TF21 server collects it. Runs until Sunday night.</p>`}</div></article>`;
    return `<article class="wanted ${claimed?'is-claimed':''}"><span class="wanted-head">Most Wanted · ${esc(b.week)}</span>
      <strong class="wanted-name">${esc(b.name)}</strong>
      <span class="wanted-crime">Killed 22A members ${fmt(b.kills)} times last week</span>
      ${claimed?`<div class="wanted-stamp">Claimed</div><p>Taken down by ${person(b.claimed_by)}${b.weapon?' with the '+esc(b.weapon):''}${b.distance!=null?' at '+fmt(b.distance,0)+' m':''}${b.headshot?' · headshot':''}.</p>`
        :`<p class="wanted-reward">Reward: <b>Bounty hunter</b> ribbon + a Discord shout-out</p><p class="fine">First member to kill them on a TF21 server claims it. Runs until Sunday night.</p>`}</article>`;
  }
  function render(){
    const host=$('reports-content'),d=rep;if(!host||!d)return;
    if(!d.enabled){host.className='panel empty';host.textContent='The TF21 kill feed has not reported yet. Check back after the next update.';return;}
    host.className='reports';
    host.innerHTML=`<div class="reports-top">${poster(d.bounty)}
      <div class="reports-side">
        <article class="panel streak-card"><span class="eyebrow">Streak of the week</span>${d.streak?`<strong class="streak-no">${fmt(d.streak.count)}</strong><span class="streak-label">kills without dying</span>${person(d.streak.who)}<small>Mostly ${esc(d.streak.weapon)} · ${esc(new Date(d.streak.at).toLocaleDateString('en-GB',{weekday:'short',day:'numeric',month:'short'}))}</small>`:'<p class="empty">No streaks yet this week.</p>'}</article>
        <article class="panel live-squads"><span class="eyebrow">Squads in the field</span>${d.live.length?d.live.map(l=>`<div class="live-squad"><b>${esc(l.server.toUpperCase())}</b><span>${l.members.length} members · ${fmt(l.kills)} kills</span><div>${l.members.map(person).join('')}</div></div>`).join(''):'<p class="fine">No squad active right now. Three or more members getting kills on one TF21 server starts a squad session.</p>'}</article>
      </div></div>
      <div class="roster-head"><div><span class="eyebrow">02 / After-action reports</span><h2>Squad <em>sessions.</em></h2></div><p class="boards-intro">Three or more members getting kills on the same TF21 server. Each one is posted to Discord when it ends.</p></div>
      ${d.sessions.length?`<div class="aar-grid">${d.sessions.map(s=>`<article class="aar"><div class="aar-head"><span>${esc(String(s.server).toUpperCase())}${s.map?' · '+esc(s.map):''}</span><small>${esc(when(s.end))}</small></div>
        <div class="aar-stats"><div><b>${fmt(s.kills)}</b><span>Kills</span></div><div><b>${s.members.length}</b><span>Members</span></div><div><b>${fmt(Math.max(1,Math.round((s.end-s.start)/60)))}m</b><span>Duration</span></div></div>
        <ol class="aar-squad">${s.members.map((m,i)=>`<li>${person(m)}<b>${fmt(m.kills)}</b></li>`).join('')}</ol>
        <div class="aar-foot">${s.longest?`<span>Longest: ${esc(s.longest.name)} · ${fmt(s.longest.m,0)} m</span>`:''}${s.weapon?`<span>Weapon of choice: ${esc(s.weapon[0])}</span>`:''}</div></article>`).join('')}</div>`:'<p class="empty">No squad sessions yet. Get three or more of you on one TF21 server.</p>'}
      ${deckSection(d.deck||[])}
      ${d.history.length?`<div class="roster-head"><div><span class="eyebrow">04 / Past bounties</span><h2>The <em>ledger.</em></h2></div></div>
        <div class="ledger">${d.history.map(b=>`<div class="ledger-row ${b.status}"><span>${esc(b.week)}</span><strong>${esc(b.name)}</strong><span>${fmt(b.kills)} kills on 22A</span><span class="ledger-status">${b.status==='claimed'?'Claimed by '+person(b.claimed_by):'Escaped'}</span></div>`).join('')}</div>`:''}`;
    sizeBars();
  }
  // The deck: one playing card per bounty week, 54 a year, kept forever.
  const suitOf=slot=>SUITS[slot.face[1]]||'';
  const isRed=slot=>['hearts','diamonds','red'].includes(slot.face[1]);
  function deckSection(decks){
    if(!decks.length)return `<div class="roster-head"><div><span class="eyebrow">03 / The deck</span><h2>Most Wanted <em>cards.</em></h2></div><p class="boards-intro">Every weekly bounty becomes a playing card. Collect all 54 before the year is out.</p></div><p class="empty">The first card is dealt when the first bounty is posted.</p>`;
    const deck=decks.find(x=>x.year===deckYear)||decks[0];
    return `<div class="roster-head"><div><span class="eyebrow">03 / The deck</span><h2>Most Wanted <em>cards.</em></h2></div>
      <p class="boards-intro">Every weekly bounty becomes a playing card in that year's deck. Take the target down to collect it. Week 53 is the Black Joker; the Red Joker goes to the year's top bounty hunter.</p></div>
      <div class="deck-bar">${decks.length>1?`<div class="roster-chips">${decks.map(x=>`<button type="button" data-deck-year="${esc(x.year)}" aria-pressed="${x.year===deck.year}">${esc(x.year)}</button>`).join('')}</div>`:''}
        <div class="deck-count"><b>${deck.collected}</b><span>of 54 collected</span></div><div class="deck-count is-escaped"><b>${deck.escaped}</b><span>escaped</span></div>
        <div class="deck-progress" role="progressbar" aria-valuemin="0" aria-valuemax="54" aria-valuenow="${deck.collected}"><i data-w="${(100*deck.collected/54).toFixed(1)}"></i></div></div>
      <div class="deck-grid">${deck.slots.map(slot=>slot.image
        ?`<button type="button" class="deck-card is-${esc(slot.status)}" data-deck-card="${slot.n}" aria-label="${esc(slot.label)}: ${esc(slot.name||'')}, ${esc(slot.status)}"><img src="${esc(slot.image)}" alt="" loading="lazy"></button>`
        :`<div class="deck-card is-back" title="${esc(slot.label)}: not dealt yet"><span class="deck-back"><b class="${isRed(slot)?'is-red':''}">${esc(slot.face[0]==='JOKER'?'★':slot.face[0])}<i>${suitOf(slot)}</i></b><small>${slot.n<=53?'Week '+slot.n:'Top hunter'}</small></span></div>`).join('')}</div>`;
  }
  function openCard(n){
    const deck=(rep.deck||[]).find(x=>x.year===deckYear)||(rep.deck||[])[0];const slot=deck&&deck.slots.find(x=>x.n===n);if(!slot)return;
    let dialog=$('deck-dialog');if(!dialog){dialog=document.createElement('dialog');dialog.id='deck-dialog';dialog.className='deck-dialog';dialog.setAttribute('aria-labelledby','deck-dialog-title');document.body.appendChild(dialog);}
    const how=[slot.weapon,slot.distance!=null?fmt(slot.distance,0)+' m':null,slot.headshot?'headshot':null].filter(Boolean).join(' · ');
    dialog.innerHTML=`<form method="dialog"><button class="secondary small" aria-label="Close card">Close ×</button></form><img src="${esc(slot.image)}" alt="${esc(slot.label)} card for ${esc(slot.name||'')}">
      <div><span class="eyebrow">${esc(deck.year)} deck · ${esc(slot.label)}</span><h2 id="deck-dialog-title">${esc(slot.name||'')}</h2>
      ${slot.status==='hunter'?`<p>Top bounty hunter of ${esc(deck.year)} with ${fmt(slot.count)} cards collected.</p><p>${person(slot.claimed_by)}</p>`
        :`<p>${esc(slot.week||'')} · killed 22A members ${fmt(slot.kills)} times the week before.</p>
      <p>${slot.status==='claimed'?`Collected by ${person(slot.claimed_by)}${how?' · '+esc(how):''}`:slot.status==='escaped'?'Escaped. Nobody took them down that week.':'Still at large. First kill on a TF21 server collects this card.'}</p>`}</div>`;
    dialog.showModal();
  }
  function sizeBars(){document.querySelectorAll('#reports-content [data-w]').forEach(el=>{el.style.width=el.dataset.w+'%';});}
  document.addEventListener('click',e=>{
    const year=e.target.closest('[data-deck-year]');if(year){deckYear=year.dataset.deckYear;render();return;}
    const card=e.target.closest('[data-deck-card]');if(card){openCard(Number(card.dataset.deckCard));return;}
    if(e.target.closest('[data-reports-refresh]'))load();});
  const before=window.hqRender;window.hqRender=function(){before?.();if(location.hash==='#reports')load();};
  window.addEventListener('hashchange',()=>{if(location.hash==='#reports')load();});
})();
