'use strict';
// Player profile: a Battlelog-style service record with tabs.
// Replaces the older layered profile decorators with one renderer.
const pfRoleNames={infantry:'Assault',medic:'Medic',recon:'Recon',support:'Support',driver:'Driver',pilot:'Pilot'};
const pfTabs=[['overview','Overview'],['progression','Progression'],['honours','Honours'],['loadout','Loadout'],['locker','Locker']];
let pfTab='overview';

function pfNum(v,d=0){return fmt(v,d);}
function pfGauge(value,max,label){
  const f=Number.isFinite(value)?Math.max(0,Math.min(1,value/max)):0,a=Math.PI*(1-f),x=55+42*Math.cos(a),y=56-42*Math.sin(a);
  return `<svg class="pf-gauge" viewBox="0 0 110 62" role="img" aria-label="${esc(label)}"><path d="M13 56A42 42 0 0 1 97 56" fill="none" stroke="#2c342d" stroke-width="12"/><path d="M13 56A42 42 0 0 1 97 56" fill="none" stroke="#a6e35a" stroke-width="12" stroke-dasharray="${(132*f).toFixed(1)} 200"/><line x1="55" y1="56" x2="${x.toFixed(1)}" y2="${y.toFixed(1)}" stroke="#eef1ea" stroke-width="3" stroke-linecap="round"/><circle cx="55" cy="56" r="5" fill="#eef1ea"/></svg>`;
}
function pfDonut(parts){
  const total=parts.reduce((s,p)=>s+(p.value||0),0);if(!total)return '<svg class="pf-donut" viewBox="0 0 42 42" aria-hidden="true"><circle cx="21" cy="21" r="15.9" fill="none" stroke="#2c342d" stroke-width="7"/></svg>';
  let offset=25;const rings=parts.map(p=>{const pct=100*(p.value||0)/total;const ring=`<circle cx="21" cy="21" r="15.9" fill="none" stroke="${p.color}" stroke-width="7" stroke-dasharray="${pct.toFixed(2)} ${(100-pct).toFixed(2)}" stroke-dashoffset="${offset.toFixed(2)}"/>`;offset-=pct;return ring;}).join('');
  return `<svg class="pf-donut" viewBox="0 0 42 42" role="img" aria-label="${esc(parts.map(p=>p.label+' '+fmt(p.value)).join(', '))}">${rings}</svg>`;
}
function pfAvatar(p){return p.avatar?`<img class="pf-avatar" src="${esc(p.avatar)}" alt="">`:`<span class="pf-avatar">${esc((p.name||'?').replace(/^\[[^\]]*\]\s*/,'').slice(0,1).toUpperCase())}</span>`;}
function pfRoles(p){
  const levels=p.tools?.levels||{};
  return Object.entries(levels).filter(([,v])=>Number.isFinite(v)).sort((a,b)=>b[1]-a[1]).map(([k,v])=>({name:pfRoleNames[k]||k,value:v}));
}
function pfNextMedal(p){
  return (p.medals||[]).filter(m=>!m.earned&&m.target>0&&m.value!=null).sort((a,b)=>b.value/b.target-a.value/a.target)[0];
}

function pfHero(p){
  const s=p.stats||{},d=p.division||{},next=p.next_rank;
  const floor=p.rank_floor||0,target=d.target||next?.points;
  const pct=target?Math.max(0,Math.min(100,100*(p.rating-floor)/Math.max(1,target-floor))):100;
  const roles=pfRoles(p).slice(0,4),maxRole=Math.max(1,...roles.map(r=>r.value));
  const stars=(roles.length?roles:[{name:'Assault'},{name:'Medic'},{name:'Recon'},{name:'Support'}]).map(r=>`<div class="pf-star"><div class="pf-star-box"><i data-h="${r.value?Math.round(100*r.value/maxRole):0}"></i></div><b>${r.value!=null?fmt(r.value):'—'}</b>${esc(r.name)}</div>`).join('');
  return `<div class="pf-hero">
    <div class="pf-rank"><span class="pf-label">Rank ${fmt((p.rank||0)+1)} / 7</span>${rankEmblem(p)}
      <div class="pf-rank-title">${esc(p.rank_name)}${d.name?' · '+esc(d.name):''}</div>
      <div class="pf-bar"><div class="pf-bar-track"><div class="pf-bar-fill" data-w="${pct.toFixed(1)}"></div></div>
      <div class="pf-bar-meta"><span><b>${fmt(p.rating,1)}</b> / ${target?fmt(target):'max'}</span><span>${target?fmt(Math.max(0,target-p.rating),1)+' to '+esc(d.target&&next&&d.target<next.points?'next division':next?.name||'next milestone'):'Top rank'}</span></div></div>
    </div>
    <div class="pf-time">
      <div class="pf-time-top"><div><span class="pf-label">Time played</span><span class="pf-big">${s.hoursPlayed!=null?fmt(s.hoursPlayed,0)+'H':'—'}</span><span class="pf-note">${fmt(s.wins)} wins · ${fmt(s.losses)} losses</span></div>${pfDonut([{label:'Wins',value:s.wins,color:'#a6e35a'},{label:'Losses',value:s.losses,color:'#b48af0'}])}</div>
      <div><span class="pf-label">Role levels</span><div class="pf-stars">${stars}</div></div>
    </div>
    <div class="pf-figure">${soldierVisual(p)}</div>
    <div class="pf-gauges">
      <div><span class="pf-label">Kills / hour</span>${pfGauge(s.killsPerHour,30,'Kills per hour')}<span class="pf-big">${fmt(s.killsPerHour,1)}</span><small>${fmt(s.hoursPlayed,0)} hours</small></div>
      <div><span class="pf-label">Win rate</span>${pfGauge(s.winRate,100,'Win rate')}<span class="pf-big">${s.winRate!=null?fmt(s.winRate,0)+'%':'—'}</span><small>${fmt(s.wins)} wins</small></div>
      <div><span class="pf-label">K/D ratio</span><span class="pf-big">${fmt(s.kd,2)}</span><small>${fmt(s.kills)} kills</small></div>
      <div><span class="pf-label">Season ELO</span><span class="pf-big">${fmt(p.rating,1)}</span><small>${p.position?'#'+fmt(p.position)+' in standings':'Season '+fmt(data.season||1)}</small></div>
    </div>
  </div>`;
}

function pfOverview(p){
  const s=p.stats||{},roles=pfRoles(p),maxRole=Math.max(1,...roles.map(r=>r.value));
  const medals=p.medals||[],earned=medals.filter(m=>m.earned),next=pfNextMedal(p),t=p.tools;
  const roleList=roles.length?`<ol class="pf-ranked">${roles.slice(0,6).map((r,i)=>`<li><span class="n">${i+1}</span><div><strong>${esc(r.name)}</strong><div class="bar"><i data-w="${Math.round(100*r.value/maxRole)}"></i></div></div><span class="v">${fmt(r.value)}</span></li>`).join('')}</ol>`
    :`<p class="pf-note">No WARDOGS Tools profile linked yet. Connect it from the Discord Player Hub to show role levels.</p><ol class="pf-ranked">${(p.preferences?.classes||[]).map((c,i)=>`<li><span class="n">${i+1}</span><div><strong>${esc(c)}</strong><small>Preferred role</small></div><span></span></li>`).join('')}</ol>`;
  const rows=[['Kills',s.kills],['Deaths',s.deaths],['Wins',s.wins],['Losses',s.losses],['Team kills',s.teamKills],['Suicides',s.suicides],['Hours played',s.hoursPlayed],['Game cash earned',s.cashEarned]];
  return pfHero(p)+`<div class="pf-cols">
    <article class="pf-card"><h2>Top roles</h2><div class="pf-card-body">${roleList}</div>
      <div class="pf-card-foot">${t?`Wardog level <b>${fmt(t.values?.wardogLevel)}</b> · <a href="${esc(t.url)}" target="_blank" rel="noopener">Tools profile ↗</a>`:'<a href="https://wardogs.tools/account" target="_blank" rel="noopener">Open WARDOGS Tools ↗</a>'}</div></article>
    <article class="pf-card"><h2>Honours &amp; progress</h2><div class="pf-card-body">
      <div class="pf-split"><div><span class="pf-label">Decorations</span><span class="pf-big">${earned.length} / ${medals.length}</span></div><div><span class="pf-label">Rank</span><span class="pf-big">${fmt((p.rank||0)+1)} / 7</span></div></div>
      ${next?`<div class="pf-next">${medalArtwork(next)}<div><span class="pf-label">Next decoration</span><strong>${esc(next.name)}</strong><progress max="${next.target}" value="${Math.min(next.target,next.value)}"></progress><small class="pf-note">${fmt(Math.min(next.value,next.target))} / ${fmt(next.target)}</small></div></div>`:''}
      ${earned.length?`<span class="pf-label pf-gap">Latest awards</span><div class="pf-ribbons">${earned.slice(-3).reverse().map(m=>`<button type="button" class="linkish" data-pf-medal="${esc(m.name)}" title="${esc(m.name)}">${medalArtwork(m)}</button>`).join('')}</div>`:''}
    </div><div class="pf-card-foot"><button type="button" class="linkish" data-pf-tab="honours">View all honours →</button></div></article>
    <article class="pf-card"><h2>Combat record</h2><div class="pf-card-body"><table class="pf-table"><tbody>
      ${rows.map(([k,v])=>`<tr><td>${k}</td><td>${fmt(v,k==='Hours played'?1:0)}</td></tr>`).join('')}
      <tr class="total"><td>Season ELO</td><td>${fmt(p.rating,1)}</td></tr></tbody></table></div>
      <div class="pf-card-foot ${old(p.stats_updated)?'warning-text':''}">Game data ${esc(age(p.stats_updated)).toLowerCase()}. Lifetime totals.</div></article>
  </div>`;
}

function pfProgression(p,owner){
  return `${owner?`<article class="panel"><div class="section-head"><h2>Rating over time</h2><div class="periods" role="group" aria-label="Chart period"><button data-period="7">7 days</button><button data-period="30">30 days</button><button data-period="season">Season</button></div></div><div id="rating-chart"></div><div id="rating-breakdown"></div></article>`:''}
  <article class="panel division-${(p.division?.name||'Bronze').toLowerCase()}"><div class="section-head"><h2>Division progress</h2><span class="pill">${esc(p.rank_name)} · ${esc(p.division?.name||'Bronze')}</span></div>${rankProgress(p)}</article>
  <article class="panel">${dossierGallery(p)}</article>`;
}

function pfLoadout(p,owner){
  const opt=key=>data.options?.find(o=>o.key===key)?.label||key,c=p.specialities||{},pref=p.preferences||{},t=p.tools;
  return `<div class="pf-loadout"><div>${soldierCard(p)}<div class="actions">${owner?'<button class="small" id="customise-soldier">Customise soldier</button>':''}<button class="small ghost" id="preview-soldier">Preview progression</button></div><p class="fine">Equipment evolves at Corporal and Staff Sergeant. Appearance is cosmetic.</p></div>
  <div><article class="panel"><h2>Specialities &amp; preferences</h2><div class="pf-facts">
    <div><span>Primary speciality</span><strong>${esc(c.primary?opt(c.primary):'Not selected')}</strong></div>
    <div><span>Secondary</span><strong>${esc((c.secondary||[]).map(opt).join(', ')||'None')}</strong></div>
    <div><span>Preferred team</span><strong>${esc((pref.teams||[]).join(' / ')||'Not selected')}</strong></div>
    <div><span>Play roles</span><strong>${esc((pref.classes||[]).join(', ')||'Not selected')}</strong></div></div>
    <p class="fine">Manage your team, roles and specialities in Discord.</p></article>
  ${t?`<article class="panel"><div class="section-head"><h2>WARDOGS Tools</h2><a href="${esc(t.url)}" target="_blank" rel="noopener">Public profile ↗</a></div><div class="stats-grid">${[['Level',t.values?.wardogLevel],['XP',t.values?.xp],['Cash',t.values?.cash],['Worth',t.values?.worth],['Gold',t.values?.gold]].map(([k,v])=>`<div class="stat"><span>${k}</span><strong>${fmt(v)}</strong></div>`).join('')}</div><p class="fine ${old(t.updated,30)||t.failed?'warning-text':''}">Synced ${esc(age(t.updated)).toLowerCase()}.${t.failed?' Latest fetch failed; saved stats shown.':''} Member-provided profile.</p></article>`:''}
  ${p.wallet?`<article class="panel wallet-card"><h2>Wallet</h2><div class="stats-grid">${[['Available',p.wallet.available],['Reserved in bets',p.wallet.reserved],['Shares at cost',p.wallet.invested_cost]].map(([k,v])=>`<div class="stat"><span>${k}</span><strong>$${fmt(v)}</strong></div>`).join('')}</div><p class="fine">Virtual dollars only.</p></article>`:''}
  ${data.scoring?`<article class="panel"><h2>How rating works</h2><div class="score-guide">${Object.entries(data.scoring).map(([k,v])=>`<span>${esc(labels[k]||k)} <strong class="${v>=0?'good':'bad'}">${v>0?'+':''}${v}</strong></span>`).join('')}</div><p class="fine">Approved future gains: +2 per Wardog level and +1 per role level. Everyone starts a new season at Private; ratings cannot fall below zero.</p></article>`:''}
  </div></div>`;
}

function pfLocker(p,owner){
  const box=p.locker||{earned:{},display:[]};
  return `<article class="panel service-locker"><div class="section-head"><h2>Service locker</h2>${typeof confidenceBadge==='function'?confidenceBadge(p):''}</div>
  <div class="locker-slots">${Array.from({length:3},(_,i)=>box.display[i]?`<figure>${patchArt(box.display[i])}<figcaption>${esc(patchNames[box.display[i]])}</figcaption></figure>`:'<div class="locker-empty"><span>＋</span><small>PATCH SLOT</small></div>').join('')}</div>
  ${owner?`<details><summary>Choose displayed patches (up to three)</summary><form id="locker-form"><div class="locker-choices">${Object.entries(patchNames).map(([id,name])=>`<label class="${box.earned[id]?'':'locked'}">${patchArt(id)}<span><input type="checkbox" name="patch" value="${id}" ${box.display.includes(id)?'checked':''} ${box.earned[id]?'':'disabled'}>${esc(name)}</span><small>${box.earned[id]?'Earned':'Locked · complete its operation'}</small></label>`).join('')}</div><button type="submit">Save display</button><p id="locker-status" role="status" class="fine"></p></form></details>`:''}
  <p class="fine">Cosmetic only. Earn patches through <a href="#operations">Community Operations</a>.</p></article>`;
}

function pfShow(tab){
  pfTab=pfTabs.some(([k])=>k===tab)?tab:'overview';
  document.querySelectorAll('.pf-tabs [data-pf-tab]').forEach(b=>b.setAttribute('aria-selected',String(b.dataset.pfTab===pfTab)));
  document.querySelectorAll('.pf-panel').forEach(el=>el.hidden=el.dataset.pfPanel!==pfTab);
  if(pfTab==='progression')renderChart?.();
}

renderProfile=function(p){
  const host=$('profile-content');
  if(!p.linked){host.className='panel';host.innerHTML=profile(p);return;}
  chartPlayer=p;
  const owner=p.id===data.me.id;
  host.className='pf';
  host.innerHTML=`<div class="pf-head">${pfAvatar(p)}<div><h1>${esc(p.name)}</h1><div class="pf-sub">${esc(p.rank_name)} · ${esc(p.division?.name||'Bronze')} · Season ${fmt(data.season||1)} <span class="pill ${p.status!=='Active'?'warning':''}">${esc(p.status)}</span></div></div>
    <div class="pf-actions">${owner?'<button class="small ghost" id="share-profile">Share to Discord</button>':`<button class="small" data-compare="${esc(p.id)}">Compare with me</button><a class="button small ghost" href="#profile">My profile</a>`}<button class="small ghost" data-pf-refresh>Refresh ↻</button></div></div>
    <nav class="pf-tabs" role="tablist" aria-label="Profile sections">${pfTabs.map(([k,l])=>`<button role="tab" data-pf-tab="${k}" aria-selected="false">${l}</button>`).join('')}</nav>
    <div class="pf-panel" data-pf-panel="overview">${pfOverview(p)}</div>
    <div class="pf-panel" data-pf-panel="progression" hidden>${pfProgression(p,owner)}</div>
    <div class="pf-panel" data-pf-panel="honours" hidden></div>
    <div class="pf-panel" data-pf-panel="loadout" hidden>${pfLoadout(p,owner)}</div>
    <div class="pf-panel" data-pf-panel="locker" hidden>${pfLocker(p,owner)}</div>`;
  // CSP blocks inline style attributes, so sizes are applied through the CSSOM.
  host.querySelectorAll('[data-w]').forEach(el=>el.style.width=el.dataset.w+'%');
  host.querySelectorAll('[data-h]').forEach(el=>el.style.height=el.dataset.h+'%');
  window.renderMedals?.(p,host.querySelector('[data-pf-panel="honours"]'));
  if(owner){renderChart();window.renderPerformance?.(p);}
  host.querySelectorAll('[data-inspect-rank]').forEach(b=>b.addEventListener('click',()=>inspectRank(Number(b.dataset.inspectRank))));
  $('customise-soldier')?.addEventListener('click',()=>openSoldier(p,true));
  $('preview-soldier')?.addEventListener('click',()=>openSoldier(p,false));
  host.querySelectorAll('[data-pf-medal]').forEach(b=>b.addEventListener('click',()=>{const m=(p.medals||[]).find(m=>m.name===b.dataset.pfMedal);if(m)openMedal(m);}));
  $('locker-form')?.addEventListener('submit',async e=>{e.preventDefault();const patches=[...e.target.querySelectorAll('input:checked')].map(i=>i.value);if(patches.length>3){$('locker-status').textContent='Choose no more than three patches.';return;}try{if(demo){notify('Preview only — no patch display saved.');return;}await api('/api/community',{action:'display',patches});p.locker={...(p.locker||{}),display:patches};data.me.locker=p.locker;renderProfile(p);pfShow('locker');notify('Service locker updated.');}catch(err){$('locker-status').textContent=err.message;}});
  pfShow(pfTab);
};

document.addEventListener('click',e=>{
  const tab=e.target.closest('[data-pf-tab]');if(tab){pfShow(tab.dataset.pfTab);if(!tab.closest('.pf-tabs'))$('profile-content').scrollIntoView({block:'start'});return;}
  if(e.target.closest('[data-pf-refresh]')){selected=null;load();return;}
  if(e.target.closest('.navmenu-list a')){e.target.closest('details')?.removeAttribute('open');}
});
document.addEventListener('click',e=>{const menu=document.querySelector('.navmenu[open]');if(menu&&!menu.contains(e.target))menu.removeAttribute('open');});
