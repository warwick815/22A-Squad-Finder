'use strict';
// Fantasy Squad: one daily round, 18:00 to 18:00 UK time. Pick five players
// within the 650-credit budget, choose a captain and optionally play a booster.
let fantasyData=null,fantasyDirty=false,fantasyBusy=false,fantasyLoading=false;
let fxTab='team',fxDraft={players:[],captain:'',booster:''},fxSort='points',fxQuery='',fxRound='',fxOpen=new Set(),fxTimer=0;
const fantasyBoosters={'':'No booster',captain:'Commanding Officer',team:'Full Mobilisation',reinforcements:'Reinforcements'};
const fxBoosterInfo={captain:['×2','Your captain scores double instead of ×1.5.'],team:['×1.5','Every player in your squad scores ×1.5.'],reinforcements:['+1','Pick a sixth player for this round.']};
const fxTabs=[['team','My team'],['live','Live round'],['league','Leaderboard'],['rules','How it works']];

function fantasyTime(t){return new Date(t*1000).toLocaleString('en-GB',{timeZone:'Europe/London',weekday:'short',day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'})+' UK';}
function fantasyAvatar(p,extra=''){return p.avatar?`<img class="fantasy-avatar ${extra}" src="${esc(p.avatar)}" alt="" loading="lazy" referrerpolicy="no-referrer">`:`<span class="fantasy-avatar fantasy-initial ${extra}" aria-hidden="true">${esc((p.name||'?').replace(/\[[^\]]*\]/g,'').trim().slice(0,2).toUpperCase()||'22')}</span>`;}
function fxShortName(n){return String(n||'').replace(/^\[[^\]]*\]\s*/,'');}
function fxCountdown(t){const s=Math.max(0,Math.round(t-Date.now()/1000)),d=Math.floor(s/86400),h=Math.floor(s%86400/3600),m=Math.floor(s%3600/60);return s<=0?'Locked':(d?d+'d ':'')+h+'h '+String(m).padStart(2,'0')+'m';}
function fxPts(v,d=1){return v==null?'—':fmt(v,Number.isInteger(v)?0:d);}
function fxLimit(){return fxDraft.booster==='reinforcements'?6:5;}
function fxPlayer(id){return fantasyData?.players.find(p=>p.id===id);}
function fxCost(){return fxDraft.players.reduce((n,id)=>n+(fxPlayer(id)?.cost||0),0);}
function fxMe(){return data?.me?.id;}

function fxDemo(){
  const now=Date.now()/1000,lock=now+5*3600+12*60,players=data.players.map((p,i)=>({id:p.id,name:p.name,avatar:p.avatar,cost:[180,150,120,95,80,60][i]||70,cost_change:[4,-3,0,6,null,-2][i]??null,season_points:[412.5,301,265,190,144,62][i]??null,picked_pct:[72,55,41,33,18,9][i]??null}));
  const squad=(ids,c,b,pts)=>({id:'m'+ids.join(''),name:data.players[+ids[0]-1]?.name||'Manager',avatar:'',players:ids,captain:c,booster:b,points:pts,covered:ids.length,total_players:ids.length,partial:false,details:ids.map((id,i)=>({id,name:data.players[+id-1]?.name,avatar:'',cost:players[+id-1]?.cost,multiplier:id===c?1.5:1,base_points:[42,18,-6,30,12,8][i],points:[42,18,-6,30,12,8][i]*(id===c?1.5:1),data_status:'Live score'}))});
  return {season:data.season||2,budget:650,linked:true,selection:{id:'demo',start:lock},players,entry:{players:['2','3','4','5','6'],captain:'2',booster:''},needs_resave:false,used:['team'],
    rounds:[{id:'demo-live',start:now-19*3600,end:lock,status:'live',entrants:3,entries:[squad(['1','2','3','4','5'],'1','captain',156),squad(['2','3','4','5','6'],'2','',118),squad(['1','3','4','5','6'],'4','team',97.5)]},
      {id:'demo-done',start:now-43*3600,end:now-19*3600,status:'completed',entrants:2,award:{winners:['1'],points2:60},entries:[squad(['1','2','4','5','6'],'1','',131),squad(['2','3','4','5','6'],'3','',88)]}],
    standings:[{season:data.season||2,rows:data.players.slice(0,5).map((p,i)=>({id:p.id,name:p.name,avatar:p.avatar,points:[812,744,690,512,320][i]}))}]};
}

async function loadFantasy(){
  if(!data||fantasyLoading)return;fantasyLoading=true;
  try{const result=demo?fxDemo():await api('/api/fantasy');if(fantasyDirty&&fantasyData&&fantasyData.selection?.id===result.selection?.id){fantasyData.rounds=result.rounds;fantasyData.standings=result.standings;}else{fantasyData=result;fantasyDirty=false;fxResetDraft();}renderFantasy();}
  catch(e){if(!fantasyData){$('exchange-content').className='panel empty';$('exchange-content').textContent=e.message;}}
  finally{fantasyLoading=false;}
}
function fxResetDraft(){const e=fantasyData?.entry;fxDraft={players:[...(e?.players||[])].filter(fxPlayer),captain:e?.captain||'',booster:e?.booster||''};if(!fxDraft.players.includes(fxDraft.captain))fxDraft.captain='';}

function renderFantasy(){
  const f=fantasyData,host=$('exchange-content');if(!f)return;host.className='fx';
  const season=f.standings.find(s=>s.season===f.season),meRow=season?.rows.findIndex(r=>r.id===fxMe()),last=f.rounds.find(r=>r.status==='completed'),lastMine=last?.entries.find(e=>e.id===fxMe());
  host.innerHTML=`<div class="fx-deadline"><div class="fx-deadline-main"><span class="fx-kicker">${f.selection?'Next round locks':'Selection'}</span><strong id="fx-countdown">${f.selection?fxCountdown(f.selection.start):'Opening soon'}</strong><small>${f.selection?fantasyTime(f.selection.start):'Needs five eligible linked players'}</small></div>
    <div class="fx-deadline-stat"><span class="fx-kicker">Season points</span><strong>${meRow>=0?fxPts(season.rows[meRow].points):'—'}</strong><small>${meRow>=0?'Rank '+(meRow+1)+' of '+season.rows.length:'No completed rounds yet'}</small></div>
    <div class="fx-deadline-stat"><span class="fx-kicker">Last round</span><strong>${lastMine?fxPts(lastMine.points):'—'}</strong><small>${last?(lastMine?'Your score':'You did not enter'):'No completed rounds'}</small></div></div>
  <nav class="fx-tabs" role="tablist">${fxTabs.map(([k,l])=>`<button role="tab" data-fx-tab="${k}" aria-selected="${fxTab===k}">${l}</button>`).join('')}</nav>
  <div id="fx-body"></div>`;
  fxRender();
  clearInterval(fxTimer);if(f.selection)fxTimer=setInterval(()=>{const c=$('fx-countdown');if(!c||!fantasyData?.selection)return clearInterval(fxTimer);c.textContent=fxCountdown(fantasyData.selection.start);},20000);
}
function fxRender(){const b=$('fx-body');if(!b)return;document.querySelectorAll('[data-fx-tab]').forEach(t=>t.setAttribute('aria-selected',String(t.dataset.fxTab===fxTab)));
  b.innerHTML=fxTab==='team'?fxTeam():fxTab==='live'?fxLive():fxTab==='league'?fxLeague():fxRules();
  // Sizes go through the CSSOM because the CSP blocks inline style attributes.
  b.querySelectorAll('[data-w]').forEach(el=>el.style.width=el.dataset.w+'%');}

// --- My team -----------------------------------------------------------------
function fxTeam(){
  const f=fantasyData;if(!f.selection)return '<div class="fx-card fx-empty">Selection opens once at least five eligible members have linked Steam. Check back after the next stats update.</div>';
  const cost=fxCost(),left=f.budget-cost,limit=fxLimit(),n=fxDraft.players.length,ready=n===limit&&left>=0&&fxDraft.captain&&f.linked;
  const status=!f.linked?'Link Steam in Discord to enter':fantasyDirty?'Unsaved changes':f.needs_resave?'Rules changed: re-save your team':f.entry?'Team saved':'No team saved yet';
  const slots=Array.from({length:limit},(_,i)=>{const p=fxPlayer(fxDraft.players[i]);if(!p)return `<button type="button" class="fx-slot fx-slot-empty" data-fx-focus><span>+</span>Add player</button>`;
    const c=p.id===fxDraft.captain;return `<div class="fx-slot ${c?'is-captain':''}"><button type="button" class="fx-x" data-fx-toggle="${esc(p.id)}" aria-label="Remove ${esc(p.name)}">×</button>${fantasyAvatar(p,'fx-slot-avatar')}<strong title="${esc(p.name)}">${esc(fxShortName(p.name))}</strong><span class="fx-slot-cost">${p.cost} cr</span><button type="button" class="fx-c" data-fx-captain="${esc(p.id)}" aria-pressed="${c}" title="${c?'Captain':'Make captain'}">${c?(fxDraft.booster==='captain'?'C ×2':'C ×1.5'):'C'}</button></div>`;}).join('');
  const chips=Object.entries(fxBoosterInfo).map(([k,[tag,info]])=>{const used=f.used.includes(k)&&f.entry?.booster!==k,on=fxDraft.booster===k;return `<button type="button" class="fx-chip ${on?'on':''}" data-fx-booster="${k}" ${used?'disabled':''} aria-pressed="${on}"><b>${tag}</b><span><strong>${fantasyBoosters[k]}</strong><small>${used?'Used this season':info}</small></span></button>`;}).join('');
  return `<div class="fx-card fx-team">
    <div class="fx-team-head"><div><span class="fx-kicker">${status}</span><h2>My team</h2></div>
      <div class="fx-budget"><div class="fx-budget-row"><span>${n} / ${limit} players</span><span class="${left<0?'bad':''}"><b>${left}</b> cr left of ${f.budget}</span></div><div class="fx-budget-bar"><i class="${left<0?'over':''}" data-w="${Math.min(100,100*cost/f.budget).toFixed(1)}"></i></div></div>
      <div class="fx-actions">${fantasyDirty?'<button type="button" class="ghost small" data-fx-undo>Undo</button>':''}<button type="button" id="fx-save" ${ready&&!fantasyBusy?'':'disabled'}>${fantasyBusy?'Saving…':'Save team'}</button></div></div>
    <div class="fx-slots">${slots}</div>
    <p class="fx-hint">${!n?'Pick players from the list below.':!fxDraft.captain&&n?'Tap <b>C</b> on a player to make them captain (×1.5 points).':n<limit?`Add ${limit-n} more player${limit-n>1?'s':''}.`:left<0?'Over budget: swap in a cheaper player.':'Ready. Save before the deadline; you can change it until lock.'}</p>
    <div class="fx-chips"><span class="fx-kicker">Boosters · one per round, each once a season</span><div>${chips}</div></div>
  </div>
  <div class="fx-card fx-pool"><div class="fx-pool-head"><h2>Players</h2><input type="search" id="fx-search" placeholder="Search players" value="${esc(fxQuery)}" aria-label="Search players"><select id="fx-sort" aria-label="Sort players">${[['points','Most points'],['price-high','Price: high to low'],['price-low','Price: low to high'],['picked','Most picked']].map(([k,l])=>`<option value="${k}" ${fxSort===k?'selected':''}>${l}</option>`).join('')}</select></div>
    <div class="fx-row fx-row-head"><span>Player</span><span>Points</span><span>Picked</span><span>Price</span><span></span></div><div id="fx-list">${fxList()}</div>
    <p class="fx-note">Points: season total from completed rounds. Prices are fixed when selection opens.</p></div>`;
}
function fxList(){
  const f=fantasyData,q=fxQuery.toLowerCase(),left=f.budget-fxCost(),full=fxDraft.players.length>=fxLimit();
  const rows=f.players.filter(p=>p.name.toLowerCase().includes(q)).sort((a,b)=>fxSort==='price-high'?b.cost-a.cost:fxSort==='price-low'?a.cost-b.cost:fxSort==='picked'?(b.picked_pct??-1)-(a.picked_pct??-1):(b.season_points??-1e9)-(a.season_points??-1e9));
  return rows.map(p=>{const inTeam=fxDraft.players.includes(p.id),afford=p.cost<=left,blocked=!inTeam&&(full||!afford||!f.linked);
    return `<div class="fx-row ${inTeam?'in-team':''}"><span class="fx-who">${fantasyAvatar(p)}<button type="button" class="player-button" data-player="${esc(p.id)}">${esc(p.name)}</button></span><span>${fxPts(p.season_points)}</span><span>${p.picked_pct==null?'—':fmt(p.picked_pct,0)+'%'}</span><span class="fx-price ${!inTeam&&!afford?'bad':''}">${p.cost}<small class="${p.cost_change>0?'up':p.cost_change<0?'down':''}">${p.cost_change>0?'▲'+p.cost_change:p.cost_change<0?'▼'+Math.abs(p.cost_change):''}</small></span><button type="button" class="fx-add ${inTeam?'remove':''}" data-fx-toggle="${esc(p.id)}" ${blocked?'disabled':''} aria-label="${inTeam?'Remove':'Add'} ${esc(p.name)}" title="${blocked?(full?'Team full':!afford?'Not enough budget':'Link Steam to enter'):''}">${inTeam?'✓':'+'}</button></div>`;}).join('')||'<p class="fx-note">No players match.</p>';
}
function fxChange(fn){fn();fantasyDirty=true;fxRender();}
function fantasyAddPlayer(id){
  if(!fantasyData||!fxPlayer(id)){notify('This player is not available for the next round.');return false;}
  if(fxDraft.players.includes(id))return true;
  if(fxDraft.players.length>=fxLimit()){notify('Your team is full. Remove a player first.');return false;}
  fxDraft.players.push(id);fantasyDirty=true;fxTab='team';return true;
}
async function fxSave(){
  if(fantasyBusy)return;const f=fantasyData;fantasyBusy=true;fxRender();
  try{const body={round:f.selection.id,players:fxDraft.players,captain:fxDraft.captain,booster:fxDraft.booster};
    if(demo){notify('Design preview only: no team saved.');fantasyDirty=false;f.entry={...body};}
    else{const result=await api('/api/fantasy',body);notify(result.message);fantasyDirty=false;await loadFantasy();}}
  catch(e){notify(e.message);}finally{fantasyBusy=false;fxRender();}
}

// --- Live round & leaderboard ---------------------------------------------------
function fxLive(){
  const rounds=fantasyData.rounds.filter(r=>r.start<=Date.now()/1000);if(!rounds.length)return '<div class="fx-card fx-empty">No round has started yet. Squads are revealed at the 18:00 UK lock.</div>';
  const r=rounds.find(r=>r.id===fxRound)||rounds[0],rows=[...r.entries].sort((a,b)=>(b.points??-1e9)-(a.points??-1e9));let pos=0,prev=null;
  const label={live:'Live',completed:'Final','awaiting data':'Finalising',void:'Void',cancelled:'Cancelled'}[r.status]||r.status;
  return `<div class="fx-card"><div class="fx-pool-head"><div><span class="fx-kicker">${fantasyTime(r.start)} → ${fantasyTime(r.end)}</span><h2>Round leaderboard <span class="fx-pill fx-pill-${esc(r.status.replace(' ','-'))}">${esc(label)}</span></h2></div>
    <select id="fx-round" aria-label="Choose round">${rounds.map(x=>`<option value="${esc(x.id)}" ${x.id===r.id?'selected':''}>${esc(fantasyTime(x.start))}</option>`).join('')}</select></div>
    ${r.reason?`<p class="fx-note">${esc(r.reason)}</p>`:''}
    ${rows.map((e,i)=>{if(i===0||e.points!==prev)pos=i+1;prev=e.points;const open=fxOpen.has(e.id);
      return `<div class="fx-entry ${e.id===fxMe()?'is-me':''} ${open?'open':''}"><button type="button" class="fx-entry-row" data-fx-open="${esc(e.id)}" aria-expanded="${open}"><span class="fx-pos">${e.points==null?'–':pos}</span>${fantasyAvatar(e)}<span class="fx-entry-name">${esc(e.name)}${e.booster?`<small>${esc(fantasyBoosters[e.booster])}</small>`:''}</span><span class="fx-entry-pts">${fxPts(e.points)}<small>pts</small></span><span class="fx-chev" aria-hidden="true">›</span></button>
        ${open?`<div class="fx-entry-squad">${(e.details||[]).map(p=>`<div class="fx-entry-player">${fantasyAvatar(p)}<span>${esc(p.name)}${p.id===e.captain?' <b class="fx-cap">C</b>':''}<small>${p.updated?'Updated '+esc(new Date(p.updated*1000).toLocaleTimeString('en-GB',{timeZone:'Europe/London',hour:'2-digit',minute:'2-digit'})):''}${p.tracked_from?' · counted from '+esc(new Date(p.tracked_from*1000).toLocaleTimeString('en-GB',{timeZone:'Europe/London',hour:'2-digit',minute:'2-digit'})):''}</small></span><span class="fx-entry-pts ${p.points<0?'bad':''}">${p.points==null?'No data':fxPts(p.points)}${p.multiplier!==1?`<small>×${p.multiplier}</small>`:''}</span></div>`).join('')}</div>`:''}</div>`;}).join('')||'<p class="fx-note">No teams entered this round.</p>'}
    ${r.award?`<p class="fx-note">${r.award.winners.length?'Round winner earns +'+fmt(r.award.points2/2)+' ELO.':'No positive winning score, so no ELO awarded.'}</p>`:''}</div>`;
}
function fxLeague(){
  const boards=fantasyData.standings,s=boards[0];if(!s||!s.rows.length)return '<div class="fx-card fx-empty">The season leaderboard fills in once the first round is completed.</div>';
  let pos=0,prev=null;
  return `<div class="fx-card"><div class="fx-pool-head"><div><span class="fx-kicker">Season ${s.season}</span><h2>Leaderboard</h2></div><span class="fx-note">Season winner earns +150 ELO</span></div>
    ${s.rows.map((p,i)=>{if(i===0||p.points!==prev)pos=i+1;prev=p.points;return `<div class="fx-entry ${p.id===fxMe()?'is-me':''}"><div class="fx-entry-row"><span class="fx-pos ${pos<=3?'top'+pos:''}">${pos}</span>${fantasyAvatar(p)}<span class="fx-entry-name"><button type="button" class="player-button" data-player="${esc(p.id)}">${esc(p.name)}</button></span><span class="fx-entry-pts">${fxPts(p.points)}<small>pts</small></span></div></div>`;}).join('')}
    ${s.champion?`<p class="fx-note">Season closed. Champion reward: +${fmt(s.champion.points2/2)} ELO.</p>`:''}</div>`;
}
function fxRules(){
  return `<div class="fx-card fx-rules"><h2>How it works</h2>
    <ol class="fx-steps"><li><b>Pick five players</b> within the 650-credit budget. Prices are set from form when selection opens.</li><li><b>Choose a captain.</b> They score ×1.5.</li><li><b>Save before 18:00 UK time.</b> The round then runs for 24 hours, until 18:00 the next day.</li><li><b>Score points</b> from what your players do in game during the round.</li></ol>
    <div class="fx-score">${[['Kill','+5'],['Win','+20'],['Death','−3'],['Loss','−10'],['Team kill','−20']].map(([k,v])=>`<div><span>${k}</span><b class="${v.startsWith('+')?'good':'bad'}">${v}</b></div>`).join('')}</div>
    <h3>Boosters</h3><ul>${Object.entries(fxBoosterInfo).map(([k,[t,i]])=>`<li><b>${fantasyBoosters[k]} (${t})</b>: ${i}</li>`).join('')}<li>One booster per round. Each can be used once a season.</li></ul>
    <h3>Prizes</h3><ul><li>Best score each round: <b>+30 ELO</b> (shared if tied).</li><li>Best season total: <b>+150 ELO</b> (shared if tied).</li></ul>
    <h3>Fair play</h3><ul><li>If a player's stats feed drops out, they score 0 for that round. Everyone else's points still count, and the round settles an hour after it ends.</li><li>Credits are not money and do not touch your wallet.</li></ul></div>`;
}

document.addEventListener('click',e=>{
  if(!$('exchange-content')?.classList.contains('fx'))return;
  const t=e.target.closest('[data-fx-tab],[data-fx-toggle],[data-fx-captain],[data-fx-booster],[data-fx-focus],[data-fx-open],[data-fx-undo],#fx-save');if(!t)return;
  if(t.dataset.fxTab){fxTab=t.dataset.fxTab;fxRender();if(fxTab!=='team'&&!fantasyDirty)loadFantasy();return;}
  if(t.id==='fx-save')return fxSave();
  if('fxUndo' in t.dataset){fxResetDraft();fantasyDirty=false;fxRender();return;}
  if('fxFocus' in t.dataset){$('fx-search')?.focus();return;}
  if(t.dataset.fxOpen){fxOpen.has(t.dataset.fxOpen)?fxOpen.delete(t.dataset.fxOpen):fxOpen.add(t.dataset.fxOpen);fxRender();return;}
  if(t.dataset.fxToggle){const id=t.dataset.fxToggle;fxChange(()=>{if(fxDraft.players.includes(id)){fxDraft.players=fxDraft.players.filter(x=>x!==id);if(fxDraft.captain===id)fxDraft.captain='';}else if(fxDraft.players.length<fxLimit()){fxDraft.players.push(id);if(!fxDraft.captain&&fxDraft.players.length===1)fxDraft.captain=id;}});return;}
  if(t.dataset.fxCaptain){fxChange(()=>fxDraft.captain=t.dataset.fxCaptain);return;}
  if('fxBooster' in t.dataset){const k=t.dataset.fxBooster;fxChange(()=>{fxDraft.booster=fxDraft.booster===k?'':k;if(fxDraft.players.length>fxLimit())fxDraft.players.length=fxLimit();if(!fxDraft.players.includes(fxDraft.captain))fxDraft.captain='';});}
});
document.addEventListener('input',e=>{if(e.target.id==='fx-search'){fxQuery=e.target.value;$('fx-list').innerHTML=fxList();}});
document.addEventListener('change',e=>{if(e.target.id==='fx-sort'){fxSort=e.target.value;$('fx-list').innerHTML=fxList();}if(e.target.id==='fx-round'){fxRound=e.target.value;fxRender();}});
window.addEventListener('beforeunload',e=>{if(fantasyDirty&&location.hash.startsWith('#club')){e.preventDefault();e.returnValue='';}});

const fantasyOriginalHQ=window.hqRender;
window.hqRender=function(){fantasyOriginalHQ?.();if(location.hash.startsWith('#club')&&!fantasyBusy)loadFantasy();};
window.addEventListener('hashchange',()=>{if(location.hash.startsWith('#club')&&!fantasyBusy)loadFantasy();});
// Keep live scores fresh while the page is open; a draft in progress is never overwritten.
setInterval(()=>{if(data&&!demo&&!fantasyBusy&&document.visibilityState==='visible'&&location.hash.startsWith('#club')&&fxTab!=='team')loadFantasy();},30000);
