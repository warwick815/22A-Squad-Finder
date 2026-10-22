'use strict';
// Field reports: Most Wanted bounty, streak of the week, live squads and after-action reports (TF21).
(function(){
  const $=id=>document.getElementById(id);
  let rep=null,loading=false;
  function demoReports(){const ps=data.players,now=Date.now()/1000,who=p=>({id:p.id,name:p.name,avatar:p.avatar});
    const sess=(i,ago)=>({server:i%2?'uk1':'uk2',map:i%2?'NorthAmerica':'Kavkazi',start:now-ago-3000,end:now-ago,kills:38-i*5,headshots:9,longest:{m:447.5,weapon:'SV98',name:ps[0].name},weapon:['SV98',11],
      members:ps.slice(0,4-i%2).map((p,j)=>({...who(p),kills:14-j*3,headshots:3-j%3})),top:{...who(ps[0]),kills:14}});
    return {enabled:true,bounty:{week:'2026-W43',name:'[49CO] Princess Pixel',kills:19,set_at:now-2*86400,status:'open'},
      history:[{week:'2026-W42',name:'BritishSam',kills:12,status:'claimed',claimed_by:who(ps[1]),weapon:'AMR 50',distance:312.4,headshot:true},{week:'2026-W41',name:'ImTheTozzy',kills:7,status:'escaped'}],
      streak:{count:13,weapon:'SV98',who:who(ps[0]),at:new Date((now-36000)*1000).toISOString()},live:[{server:'uk2',members:ps.slice(1,4).map(who),kills:12,since:now-1500}],
      sessions:[sess(0,7200),sess(1,90000)]};}
  async function load(){if(typeof data==='undefined'||!data||loading)return;loading=true;
    try{rep=demo?demoReports():await api('/api/reports');render();}catch(e){$('reports-content').className='panel empty';$('reports-content').textContent=e.message;}finally{loading=false;}}
  const when=ts=>new Date(ts*1000).toLocaleString('en-GB',{weekday:'short',day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'});
  const person=p=>p?`<span class="shame-who">${typeof fantasyAvatar==='function'?fantasyAvatar(p):''}${p.id?`<button type="button" class="player-button" data-player="${esc(p.id)}">${esc(p.name)}</button>`:esc(p.name)}</span>`:'—';
  function poster(b){
    if(!b)return `<article class="wanted is-empty"><span class="wanted-head">Most Wanted</span><strong>Nobody this week</strong><p>A bounty is posted each Monday on whoever killed 22A members most the week before (3+ kills).</p></article>`;
    const claimed=b.status==='claimed';
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
      ${d.history.length?`<div class="roster-head"><div><span class="eyebrow">03 / Past bounties</span><h2>The <em>ledger.</em></h2></div></div>
        <div class="ledger">${d.history.map(b=>`<div class="ledger-row ${b.status}"><span>${esc(b.week)}</span><strong>${esc(b.name)}</strong><span>${fmt(b.kills)} kills on 22A</span><span class="ledger-status">${b.status==='claimed'?'Claimed by '+person(b.claimed_by):'Escaped'}</span></div>`).join('')}</div>`:''}`;
  }
  document.addEventListener('click',e=>{if(e.target.closest('[data-reports-refresh]'))load();});
  const before=window.hqRender;window.hqRender=function(){before?.();if(location.hash==='#reports')load();};
  window.addEventListener('hashchange',()=>{if(location.hash==='#reports')load();});
})();
