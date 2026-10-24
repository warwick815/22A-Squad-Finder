'use strict';
// Player profile: a Battlelog-style service record with tabs.
// Replaces the older layered profile decorators with one renderer.
const pfRoleNames={infantry:'Assault',medic:'Medic',recon:'Recon',support:'Support',driver:'Driver',pilot:'Pilot'};
const pfTabs=[['overview','Overview'],['progression','Progression'],['honours','Honours'],['dogtags','Dog tags'],['loadout','Loadout'],['locker','Locker']];
let pfTab='overview';

function pfNum(v,d=0){return fmt(v,d);}
// Small line icons (Battlelog-style) for roles, tabs and stat rows.
const pfIconPaths={
  dogtags:'M7 3h10a4 4 0 0 1 4 4v10a4 4 0 0 1-4 4H7a4 4 0 0 1-4-4v-3a1.5 1.5 0 0 0 0-3V7a4 4 0 0 1 4-4zm9 8a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3zM7 8v1.5h6V8zm0 3v1.5h4V11z',
  assault:'M10 3h4v7h7v4h-7v7h-4v-7H3v-4h7z',
  medic:'M9 3h6v6h6v6h-6v6H9v-6H3V9h6z',
  recon:'M11 2h2v4.1A6 6 0 0 1 17.9 11H22v2h-4.1A6 6 0 0 1 13 17.9V22h-2v-4.1A6 6 0 0 1 6.1 13H2v-2h4.1A6 6 0 0 1 11 6.1zm1 6a4 4 0 1 0 0 8 4 4 0 0 0 0-8z',
  support:'M5 8h3v13H5zm5.5 0h3v13h-3zM16 8h3v13h-3zM5 7l1.5-4L8 7zm5.5 0L12 3l1.5 4zM16 7l1.5-4L19 7z',
  driver:'M12 2a10 10 0 1 1 0 20 10 10 0 0 1 0-20zm0 3a7 7 0 0 0-6.9 6h4.2a3 3 0 0 1 5.4 0h4.2A7 7 0 0 0 12 5zm-1 9.8A3 3 0 0 1 9.2 13H5.1a7 7 0 0 0 5.9 5.9zm2 4.1a7 7 0 0 0 5.9-5.9h-4.1a3 3 0 0 1-1.8 1.8z',
  pilot:'M12 2l2 6 8 4v2l-8-2-1 6 3 2v2l-4-1-4 1v-2l3-2-1-6-8 2v-2l8-4z',
  overview:'M12 4a4 4 0 1 1 0 8 4 4 0 0 1 0-8zm-8 16c0-4 3.6-6 8-6s8 2 8 6z',
  progression:'M3 19h4v-6H3zm7 0h4V9h-4zm7 0h4V4h-4z',
  honours:'M8 2h8l-2 6h-4zm4 7a6.5 6.5 0 1 1 0 13 6.5 6.5 0 0 1 0-13zm0 2.5l1.2 2.5 2.7.4-2 1.9.5 2.7-2.4-1.3-2.4 1.3.5-2.7-2-1.9 2.7-.4z',
  loadout:'M9 3h6v3h6v14H3V6h6zm2 0v3h2V3zM3 11h18v2H3z',
  locker:'M7 10V7a5 5 0 0 1 10 0v3h2v12H5V10zm2 0h6V7a3 3 0 0 0-6 0z',
  chevron:'M12 3l9 8.5-2.8 2.8L12 8.4l-6.2 5.9L3 11.5zm0 7.5l9 8.5-2.8 2.8L12 16l-6.2 5.8L3 19z',
  wrench:'M21 6.5a5 5 0 0 1-6.6 4.7L6.3 19.3a2 2 0 0 1-2.8-2.8l8.1-8.1A5 5 0 0 1 17.5 3l-3 3 .9 2.6 2.6.9z',
  wing:'M2 18c5-1 9-4 12-9l1.5 1.5L22 4c-1 7-5 12-11 14l1 1.5c-3 .8-6.5.8-10-1.5z'};
function pfIcon(name,cls='pf-icon'){const d=pfIconPaths[name]||pfIconPaths.assault;return `<svg class="${cls}" viewBox="0 0 24 24" aria-hidden="true"><path d="${d}"/></svg>`;}
const pfRoleIcon={Assault:'assault',Medic:'medic',Recon:'recon',Support:'support',Driver:'driver',Pilot:'pilot'};
// WARDOGS Tools uses its own role icons; mirror them on the Tools card.
const pfToolsRoles=[['infantry','Assault','chevron'],['medic','Medic','medic'],['recon','Recon','recon'],['support','Support','wrench'],['driver','Driver','driver'],['pilot','Pilot','wing']];
function pfMoney(v){return v==null?'—':'$'+fmt(v);}
function pfTools(p){
  const t=p.tools;if(!t)return '';const v=t.values||{},lv=t.levels||{};
  const rows=[['XP',fmt(v.xp),''],['Cash',pfMoney(v.cash),'money'],['Worth',pfMoney(v.worth),'money'],['Gold',fmt(v.gold),'']];
  if(t.unlocks!=null)rows.push(['Unlocks',fmt(t.unlocks),'']);
  return `<article class="pf-card pf-tools"><h2>WARDOGS Tools</h2><div class="pf-card-body">
    <div class="pf-tools-level"><svg class="pf-tools-emblem" viewBox="0 0 48 56" aria-hidden="true"><path d="M24 2l20 8v18c0 13-9 22-20 26C13 50 4 41 4 28V10z" fill="#1d2620" stroke="#a6e35a" stroke-width="2"/><path d="M14 20l10-6 10 6M14 28l10-6 10 6M14 36l10-6 10 6" fill="none" stroke="#b48af0" stroke-width="3" stroke-linejoin="round"/></svg>
      <div><span class="pf-big">${fmt(v.wardogLevel)}</span><span class="pf-label">Wardog level</span></div></div>
    <table class="pf-table pf-tools-values"><tbody>${rows.map(([k,val,c])=>`<tr><td>${k}</td><td class="${c}">${val}</td></tr>`).join('')}</tbody></table>
    <div class="pf-tools-roles">${pfToolsRoles.map(([key,name,icon])=>`<div class="${lv[key]?'':'is-zero'}" title="${name} level ${fmt(lv[key])}">${pfIcon(icon)}<b>${fmt(lv[key])}</b></div>`).join('')}</div></div>
    <div class="pf-card-foot ${old(t.updated,30)||t.failed?'warning-text':''}">Synced ${esc(age(t.updated)).toLowerCase()}${t.failed?' · latest fetch failed, saved stats shown':''} · <a href="${esc(t.url)}" target="_blank" rel="noopener">Tools profile ↗</a></div></article>`;
}
function pfPatches(p,owner){
  const box=p.locker||{display:[]},shown=(box.display||[]).filter(id=>patchNames[id]);
  return `<article class="pf-card pf-patches"><h2>Morale patches</h2><div class="pf-card-body"><div class="pf-patch-row">${Array.from({length:3},(_,i)=>shown[i]?`<figure>${patchArt(shown[i])}<figcaption>${esc(patchNames[shown[i]])}</figcaption></figure>`:'<div class="pf-patch-empty"><span>＋</span></div>').join('')}</div></div>
    <div class="pf-card-foot">${owner?'Choose patches in your <button type="button" class="linkish" data-pf-tab="locker">Locker</button>':'<button type="button" class="linkish" data-pf-tab="locker">View locker</button>'} · Earn more in <a href="#operations">Operations</a></div></article>`;
}
function pfGauge(value,max,label){
  const f=Number.isFinite(value)?Math.max(0,Math.min(1,value/max)):0,a=Math.PI*(1-f),x=55+38*Math.cos(a),y=56-38*Math.sin(a);
  return `<svg class="pf-gauge" viewBox="0 0 110 62" role="img" aria-label="${esc(label)}"><defs><linearGradient id="pf-g-track" x1="0" x2="1"><stop offset="0" stop-color="#2a332c"/><stop offset="1" stop-color="#3b463c"/></linearGradient></defs><path d="M13 56A42 42 0 0 1 97 56" fill="none" stroke="url(#pf-g-track)" stroke-width="14"/><path class="pf-gauge-fill" d="M13 56A42 42 0 0 1 97 56" fill="none" stroke-width="14" stroke-dasharray="${(132*f).toFixed(1)} 200"/><line x1="55" y1="56" x2="${x.toFixed(1)}" y2="${y.toFixed(1)}" stroke="#eef1ea" stroke-width="3.5" stroke-linecap="round"/><circle cx="55" cy="56" r="5.5" fill="#eef1ea"/></svg>`;
}
function pfDonut(parts){
  const total=parts.reduce((s,p)=>s+(p.value||0),0);if(!total)return '<svg class="pf-donut" viewBox="0 0 42 42" aria-hidden="true"><circle cx="21" cy="21" r="15.9" fill="none" stroke="#2a312b" stroke-width="8"/></svg>';
  let offset=25;const rings=parts.map(p=>{const pct=100*(p.value||0)/total;const ring=`<circle cx="21" cy="21" r="15.9" fill="none" stroke="${p.color}" stroke-width="8" stroke-dasharray="${pct.toFixed(2)} ${(100-pct).toFixed(2)}" stroke-dashoffset="${offset.toFixed(2)}"/>`;offset-=pct;return ring;}).join('');
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
function pfRankTarget(p){
  const d=p.division||{},next=p.next_rank,floor=p.rank_floor||0,target=d.target||next?.points;
  const pct=target?Math.max(0,Math.min(100,100*(p.rating-floor)/Math.max(1,target-floor))):100;
  return {target,pct,label:target?(d.target&&next&&d.target<next.points?'next division':next?.name||'next milestone'):''};
}

function pfHero(p){
  const s=p.stats||{},d=p.division||{},r=pfRankTarget(p);
  const roles=pfRoles(p).slice(0,4),maxRole=Math.max(1,...roles.map(r=>r.value));
  const stars=(roles.length?roles:['Assault','Medic','Recon','Support'].map(name=>({name}))).map(r=>`<div class="pf-star" title="${esc(r.name)}${r.value!=null?' level '+fmt(r.value):''}"><div class="pf-star-box"><i data-h="${r.value?Math.round(100*r.value/maxRole):0}"></i><b>${r.value!=null?fmt(r.value):'—'}</b></div>${pfIcon(pfRoleIcon[r.name]||'assault','pf-star-icon role-'+(pfRoleIcon[r.name]||'assault'))}</div>`).join('');
  return `<div class="pf-hero">
    <div class="pf-rank"><span class="pf-rank-no">${String((p.rank||0)+1).padStart(2,'0')}</span>${rankEmblem(p)}
      <span class="pf-label">Rank ${fmt((p.rank||0)+1)}</span>
      <div class="pf-rank-title">${esc(p.rank_name)}${d.name?' · '+esc(d.name):''}</div>
      <div class="pf-bar"><div class="pf-bar-track"><div class="pf-bar-fill" data-w="${r.pct.toFixed(1)}"></div></div>
      <div class="pf-bar-meta"><span><b>${fmt(p.rating,1)}</b> / ${r.target?fmt(r.target):'max'}</span><span>${r.target?fmt(Math.max(0,r.target-p.rating),1)+' until '+esc(r.label):'Top rank'}</span></div></div>
    </div>
    <div class="pf-time">
      <div class="pf-time-top"><div><span class="pf-label">Time played</span><span class="pf-big">${s.hoursPlayed!=null?fmt(s.hoursPlayed,0)+'H':'—'}</span><span class="pf-note">${fmt(s.wins)} wins · ${fmt(s.losses)} losses</span></div>${pfDonut([{label:'Wins',value:s.wins,color:'#a6e35a'},{label:'Losses',value:s.losses,color:'#b48af0'}])}</div>
      <div><span class="pf-label">Service stars</span><div class="pf-stars">${stars}</div></div>
    </div>
    <div class="pf-figure">${soldierVisual(p)}<button type="button" class="pf-stage" data-pf-tab="progression" title="See equipment progression"><span class="pf-stage-pips">${[0,1,2].map(i=>`<i class="${i<=soldierStage(p)?'on':''}"></i>`).join('')}</span>${esc(soldierStages[soldierStage(p)])}</button></div>
    <div class="pf-gauges">
      <div><span class="pf-label">Kills / hour</span>${pfGauge(s.killsPerHour,30,'Kills per hour')}<span class="pf-big">${fmt(s.killsPerHour,1)}</span><small>${fmt(s.hoursPlayed,0)}h played</small></div>
      <div><span class="pf-label">W/L ratio</span>${pfGauge(s.winRate,100,'Win rate')}<span class="pf-big">${s.losses?fmt(s.wins/s.losses,2):'—'}</span><small>${s.winRate!=null?fmt(s.winRate,0)+'% · ':''}${fmt(s.wins)} wins</small></div>
      <div><span class="pf-label">Season ELO</span><span class="pf-big">${fmt(p.rating,1)}</span><small>${p.position?'#'+fmt(p.position)+' in standings':'Season '+fmt(data.season||1)}</small></div>
      <div><span class="pf-label">K/D ratio</span><span class="pf-big">${fmt(s.kd,2)}</span><small>${fmt(s.kills)} kills</small></div>
    </div>
  </div>`;
}

function pfOverview(p,owner){
  const s=p.stats||{},roles=pfRoles(p);
  const medals=p.medals||[],earned=medals.filter(m=>m.earned),next=pfNextMedal(p),t=p.tools,r=pfRankTarget(p);
  const roleList=roles.length?`<ol class="pf-ranked">${roles.slice(0,5).map((r,i)=>`<li><span class="n">${i+1}</span>${pfIcon(pfRoleIcon[r.name]||'assault','pf-role-art')}<div><strong>${esc(r.name)}</strong><small>Level ${fmt(r.value)}</small></div></li>`).join('')}</ol>`
    :`<p class="pf-note">No WARDOGS Tools profile linked yet. Connect it from the Discord Player Hub to show role levels.</p><ol class="pf-ranked">${(p.preferences?.classes||[]).map((c,i)=>`<li><span class="n">${i+1}</span>${pfIcon(pfRoleIcon[c]||'assault','pf-role-art')}<div><strong>${esc(c)}</strong><small>Preferred role</small></div></li>`).join('')}</ol>`;
  const rows=[['assault','Kills',s.kills],['recon','Deaths',s.deaths],['honours','Wins',s.wins],['locker','Losses',s.losses],['medic','Team kills',s.teamKills],['support','Suicides',s.suicides],['progression','Hours played',s.hoursPlayed,1],['loadout','Game cash earned',s.cashEarned]];
  return pfHero(p)+`<div class="pf-cols">
    <div><article class="pf-card"><h2>Top roles</h2><div class="pf-card-body">${roleList}</div>
      <div class="pf-card-foot">${t?`Wardog level <b>${fmt(t.values?.wardogLevel)}</b> · View <a href="${esc(t.url)}" target="_blank" rel="noopener">Tools profile ↗</a>`:'<a href="https://wardogs.tools/account" target="_blank" rel="noopener">Open WARDOGS Tools ↗</a>'}</div></article>
    ${pfPatches(p,owner)}</div>
    <div>
    <article class="pf-card"><h2>Honours &amp; progression</h2><div class="pf-card-body pf-split">
      <div><span class="pf-label">Ribbons</span><span class="pf-big">${earned.length} / ${medals.length}</span><span class="pf-label pf-gap">Next ribbon</span>
        <div class="pf-unlock">${next?`${medalArtwork(next)}<div class="pf-unlock-bar"><i data-w="${Math.round(100*Math.min(1,next.value/next.target))}"></i></div><small>${esc(next.name)} · ${fmt(Math.min(next.value,next.target))} / ${fmt(next.target)}</small>`:'<small>All available ribbons awarded</small>'}</div></div>
      <div><span class="pf-label">Rank</span><span class="pf-big">${fmt((p.rank||0)+1)} / 7</span><span class="pf-label pf-gap">Next rank</span>
        <div class="pf-unlock">${p.next_rank?`<span class="pf-unlock-rank">${esc(p.next_rank.name)}</span><div class="pf-unlock-bar"><i data-w="${r.pct.toFixed(1)}"></i></div><small>${fmt(Math.max(0,(r.target||0)-p.rating),1)} pts until ${esc(r.label)}</small>`:'<small>Top rank reached</small>'}</div></div>
    </div><div class="pf-card-foot">View all <button type="button" class="linkish" data-pf-tab="honours">Honours</button> or <button type="button" class="linkish" data-pf-tab="progression">Progression</button></div></article>
    <article class="pf-card"><h2>Latest awards</h2><div class="pf-card-body">${ribbonRack(earned.slice(-3).reverse(),{empty:'No ribbons awarded yet. Your first comes with your Steam link.'})}</div>
      <div class="pf-card-foot">View all <button type="button" class="linkish" data-pf-tab="honours">Ribbons</button></div></article>
    </div>
    <div>${pfTools(p)}<article class="pf-card"><h2>Service record</h2><div class="pf-card-body"><table class="pf-table"><tbody>
      ${rows.map(([icon,k,v,dp])=>`<tr><td>${pfIcon(icon,'pf-row-icon')}${k}</td><td>${fmt(v,dp||0)}</td></tr>`).join('')}
      <tr class="total"><td>Season ELO</td><td>${fmt(p.rating,1)}</td></tr></tbody></table></div>
      <div class="pf-card-foot ${old(p.stats_updated)?'warning-text':''}">Game data ${esc(age(p.stats_updated)).toLowerCase()}. Lifetime totals${p.tf21?', WarDogs UK + TF21 servers':''}.</div>${p.tf21?`<div class="pf-card-foot pf-tf21"><b>TF21 servers</b> ${fmt(p.tf21.kills)} kills · ${fmt(p.tf21.wins)} wins · K/D ${fmt(p.tf21.kd??(p.tf21.deaths?p.tf21.kills/p.tf21.deaths:null),2)}${p.tf21.online?' · <span class="pf-live">● On TF21 now</span>':''}${p.tf21.note?`<small>${esc(p.tf21.note)}</small>`:''}</div>`:''}</article></div>
  </div>`;
}

// Combat rating: six parts, one number, blended into ELO as a multiplier on kills and wins.
function combatPanel(p){
  const s=p.skill;if(!s)return `<article class="panel combat-panel"><span class="eyebrow">Combat rating</span><h2>Six parts. <em>One number.</em></h2><p class="fine">Shown once there is enough game data to compare against every WarDogs UK player.</p></article>`;
  const pct=v=>v==null?'—':'Top '+Math.max(1,Math.round(100*(1-v)))+'%';
  const mult=s.multiplier,sign=mult>=1?'good':'bad';
  return `<article class="panel combat-panel">
    <div class="combat-head"><div><span class="eyebrow">Combat rating / blended into ELO</span><h2>Six parts. <em>One number.</em></h2>
      <p>Each part is where you sit among ${fmt(s.compared)} WarDogs UK players, from 0 to 100%. The rating is 1,000 plus up to 2,000 points by weight, scaled by confidence: hours ÷ (hours + 1). It sets how much your kills and wins are worth in ELO, from x${(1-s.spread).toFixed(2)} to x${(1+s.spread).toFixed(2)}. Deaths and losses always cost the same.</p></div>
      <div class="combat-score"><b>${fmt(s.rating)}</b><span>Top ${s.top}%</span><strong class="${sign}">x${mult.toFixed(2)} ELO</strong><small>Confidence ${Math.round(100*s.confidence)}%</small></div></div>
    <div class="combat-weights" aria-hidden="true">${s.guide.map(g=>`<div class="cw-${g.key}" data-w="${g.weight}"><b>${esc(g.name)}</b><small>${g.weight}%</small></div>`).join('')}</div>
    <div class="combat-parts">${s.guide.map(g=>{const v=s.parts[g.key],pts=v==null?null:Math.round(2000*g.weight/100*v*s.confidence);
      return `<div class="combat-part cw-${g.key}"><div class="cp-head"><i aria-hidden="true"></i><strong>${esc(g.name)}</strong><span>${pct(v)}</span></div>
        <small class="cp-max">Up to ${fmt(20*g.weight)} points${pts!=null?` · you score ${fmt(pts)}`:''}</small>
        <div class="cp-bar" role="progressbar" aria-label="${esc(g.name)} percentile" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${v==null?0:Math.round(100*v)}"><span data-w="${v==null?50:(100*v).toFixed(1)}"></span></div>
        <p>${esc(g.detail)}${v==null?' No data yet, so it counts as average.':''}</p></div>`;}).join('')}</div></article>`;
}

function pfProgression(p,owner){
  return `${combatPanel(p)}${owner?`<article class="panel"><div class="section-head"><h2>Rating over time</h2><div class="periods" role="group" aria-label="Chart period"><button data-period="7">7 days</button><button data-period="30">30 days</button><button data-period="season">Season</button></div></div><div id="rating-chart"></div><div id="rating-breakdown"></div></article>`:''}
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
  ${data.scoring?`<article class="panel"><h2>How rating works</h2><div class="score-guide">${Object.entries(data.scoring).map(([k,v])=>`<span>${esc(labels[k]||k)} <strong class="${v>=0?'good':'bad'}">${v>0?'+':''}${v}</strong></span>`).join('')}</div><p class="fine">Kills and wins are multiplied by your combat rating (x0.80 to x1.20, average x1.00); deaths and losses always cost the amounts shown. Approved future gains: +2 per Wardog level and +1 per role level. Everyone starts a new season at Private; ratings cannot fall below zero.</p></article>`:''}
  </div></div>`;
}

function pfLocker(p,owner){
  const box=p.locker||{earned:{},display:[]};
  return `<article class="panel service-locker"><div class="section-head"><h2>Service locker</h2>${typeof confidenceBadge==='function'?confidenceBadge(p):''}</div>
  <div class="locker-slots">${Array.from({length:3},(_,i)=>box.display[i]?`<figure>${patchArt(box.display[i])}<figcaption>${esc(patchNames[box.display[i]])}</figcaption></figure>`:'<div class="locker-empty"><span>＋</span><small>PATCH SLOT</small></div>').join('')}</div>
  ${owner?`<details><summary>Choose displayed patches (up to three)</summary><form id="locker-form"><div class="locker-choices">${Object.entries(patchNames).map(([id,name])=>`<label class="${box.earned[id]?'':'locked'}">${patchArt(id)}<span><input type="checkbox" name="patch" value="${id}" ${box.display.includes(id)?'checked':''} ${box.earned[id]?'':'disabled'}>${esc(name)}</span><small>${box.earned[id]?'Earned':'Locked · '+esc(podiumPatches[id]||'complete its operation')}</small></label>`).join('')}</div><button type="submit">Save display</button><p id="locker-status" role="status" class="fine"></p></form></details>`:''}
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
  host.innerHTML=`<div class="pf-head">${pfAvatar(p)}<div class="pf-tag">${p.badge?`<img src="${esc(p.badge)}" alt="">`:''}<span>SOLDIER<b>22A · UK</b></span></div><div><h1>${esc(p.name)}</h1><div class="pf-sub">${esc(p.rank_name)} · ${esc(p.division?.name||'Bronze')} · Season ${fmt(data.season||1)}${p.tools?.values?.wardogLevel!=null?' · Wardog '+fmt(p.tools.values.wardogLevel):''} <span class="pill ${p.status!=='Active'?'warning':''}">${esc(p.status)}</span></div></div>
    <div class="pf-actions">${owner?'<button class="small ghost" id="share-profile">Share to Discord</button>':`<button class="small" data-compare="${esc(p.id)}">Compare with me</button><a class="button small ghost" href="#profile">My profile</a>`}<button class="small ghost" data-pf-refresh>Refresh ↻</button></div></div>
    <nav class="pf-tabs" role="tablist" aria-label="Profile sections">${pfTabs.map(([k,l])=>`<button role="tab" data-pf-tab="${k}" aria-selected="false">${pfIcon(k)}${l}</button>`).join('')}</nav>
    <div class="pf-panel" data-pf-panel="overview">${pfOverview(p,owner)}</div>
    <div class="pf-panel" data-pf-panel="progression" hidden>${pfProgression(p,owner)}</div>
    <div class="pf-panel" data-pf-panel="honours" hidden></div>
    <div class="pf-panel" data-pf-panel="loadout" hidden>${pfLoadout(p,owner)}</div>
    <div class="pf-panel" data-pf-panel="dogtags" hidden>${typeof dogtagPanel==='function'?dogtagPanel(p,owner):''}</div>
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
