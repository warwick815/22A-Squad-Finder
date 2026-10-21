'use strict';
// Hall of shame: every time a 22A member killed another 22A member on TF21.
(function(){
  const $=id=>document.getElementById(id);
  let shameData=null,shameLoading=false,shameFilter='all';
  function demoShame(){const ps=data.players,now=Date.now(),w=['SV98','M67 frag grenade','AK74','Claymore','M249 SAW','AMR 50'];
    const ev=Array.from({length:9},(_,i)=>{const a=ps[i%ps.length],b=ps[(i*2+1)%ps.length];return {id:i,at:new Date(now-i*5.3*3600e3).toISOString(),weapon:w[i%w.length],team_kill:i%3!==0,headshot:i%4===0,distance:[12.4,38,251.3,7.2,90.5,447.5][i%6],map:i%2?'NorthAmerica':'Kavkazi',server:i%2?'uk1':'uk2',killer:{id:a.id,name:a.name,avatar:a.avatar},victim:{id:b.id,name:b.name,avatar:b.avatar}};});
    const off={};for(const e of ev){const r=off[e.killer.id]??={who:e.killer,friendly:0,blue:0};r[e.team_kill?'friendly':'blue']++;}
    return {enabled:true,events:ev,offenders:Object.values(off).sort((a,b)=>(b.friendly+b.blue)-(a.friendly+a.blue))};}
  async function load(){if(typeof data==='undefined'||!data||shameLoading)return;shameLoading=true;
    try{shameData=demo?demoShame():await api('/api/shame');render();}catch(e){$('shame-content').className='panel empty';$('shame-content').textContent=e.message;}finally{shameLoading=false;}}
  const ago=iso=>{const s=(Date.now()-Date.parse(iso))/1000;return s<3600?Math.max(1,Math.round(s/60))+'m ago':s<86400?Math.round(s/3600)+'h ago':new Date(iso).toLocaleDateString('en-GB',{day:'numeric',month:'short'});};
  const person=p=>`<span class="shame-who">${typeof fantasyAvatar==='function'?fantasyAvatar(p):''}${p.id?`<button type="button" class="player-button" data-player="${esc(p.id)}">${esc(p.name)}</button>`:esc(p.name)}</span>`;
  function render(){
    const host=$('shame-content'),d=shameData;if(!host||!d)return;
    if(!d.enabled){host.className='panel empty';host.textContent='The TF21 kill feed has not reported yet. Check back after the next update.';return;}
    const list=d.events.filter(e=>shameFilter==='all'||(shameFilter==='friendly'?e.team_kill:!e.team_kill));
    const total=d.events.length,friendly=d.events.filter(e=>e.team_kill).length;
    host.className='shame';
    host.innerHTML=`<div class="roster-head"><div><span class="eyebrow">01 / The charge sheet</span><h2>Caught <em>in the act.</em></h2></div>
      <div class="roster-stats"><div><b>${total}</b><span>Incidents</span></div><div><b>${friendly}</b><span>Friendly fire</span></div><div><b>${total-friendly}</b><span>Blue on blue</span></div></div></div>
      <div class="shame-layout"><div>
        <div class="roster-chips shame-chips">${[['all','Everything'],['friendly','Friendly fire'],['blue','Blue on blue']].map(([k,l])=>`<button type="button" data-shame-filter="${k}" aria-pressed="${shameFilter===k}">${l}</button>`).join('')}</div>
        ${list.length?list.map(e=>`<article class="shame-row ${e.team_kill?'is-friendly':'is-blue'}">
          <span class="shame-badge">${e.team_kill?'Friendly fire':'Blue on blue'}</span>
          <div class="shame-line">${person(e.killer)}<span class="shame-weapon">${e.headshot?'<b>⌖</b> ':''}${esc(e.weapon||'Unknown')}</span>${person(e.victim)}</div>
          <div class="shame-meta">${e.distance!=null?fmt(e.distance,0)+' m · ':''}${esc(e.map||'')}${e.server?' · '+esc(e.server.toUpperCase()):''}<span>${esc(ago(e.at))}</span></div>
        </article>`).join(''):'<p class="empty">A clean record. For now.</p>'}
      </div>
      <aside class="panel shame-board"><span class="eyebrow">Worst offenders</span><h2>Repeat <em>offenders.</em></h2>
        ${d.offenders.length?`<ol>${d.offenders.map((r,i)=>`<li><span class="shame-pos">${i+1}</span>${person(r.who)}<b>${r.friendly+r.blue}</b><small>${r.friendly} friendly · ${r.blue} blue on blue</small></li>`).join('')}</ol>`:'<p class="empty">Nobody yet.</p>'}
        <p class="fine">Friendly fire: same team. Blue on blue: 22A members on opposite teams. TF21 servers only.</p></aside></div>`;
  }
  document.addEventListener('click',e=>{const f=e.target.closest('[data-shame-filter]');if(f){shameFilter=f.dataset.shameFilter;render();}if(e.target.closest('[data-shame-refresh]'))load();});
  const before=window.hqRender;window.hqRender=function(){before?.();if(location.hash==='#shame')load();};
  window.addEventListener('hashchange',()=>{if(location.hash==='#shame')load();});
})();
