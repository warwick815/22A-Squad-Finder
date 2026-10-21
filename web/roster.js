'use strict';
// Members (the roster, filed by rank) and the Leaderboards hub.
(function(){
  const $=id=>document.getElementById(id);
  const RANKS=['Private','Lance Corporal','Corporal','Sergeant','Staff Sergeant','Warrant Officer Class 2','Warrant Officer Class 1'];
  const BADGES=['pte','lcpl','cpl','sgt','ssgt','wo2','wo1'];
  let query='',rankFilter='all';
  const roster=()=>{const d=typeof data!=='undefined'?data:null;return d&&Array.isArray(d.players)?d:null;};
  const teamOf=p=>{const t=(p.preferences?.teams||[])[0]||'';const key=t.toLowerCase().includes('valkyra')?'red':t.toLowerCase().includes('manticore')?'green':t.toLowerCase().includes('lonestar')?'blue':'';return {key,name:t.replace(/^[^\w]+/,'').replace(/\s*\(.*\)/,'')};};
  const short=n=>String(n||'').replace(/^\[[^\]]*\]\s*/,'');

  // --- Members ---------------------------------------------------------------
  function memberCard(p,n){
    const team=teamOf(p),role=(p.preferences?.classes||[])[0];
    const ribbons=(p.medals||[]).filter(m=>m.earned).slice(-4).reverse();
    const patches=((p.locker||{}).display||[]).filter(id=>typeof patchNames!=='undefined'&&patchNames[id]);
    return `<button type="button" class="file-card ${team.key?'team-'+team.key:''}" data-player="${esc(p.id)}" aria-label="Open ${esc(p.name)}'s file">
      <span class="file-tab">22A / ${String(n).padStart(3,'0')}</span>
      <span class="file-avatar">${p.avatar?`<img src="${esc(p.avatar)}" alt="" loading="lazy" referrerpolicy="no-referrer">`:`<b>${esc(short(p.name).slice(0,1).toUpperCase())}</b>`}</span>
      <span class="file-main">
        <strong class="file-name">${esc(short(p.name))}</strong>
        <span class="file-tags"><span class="file-tag rank">${esc(p.rank_name||'Unranked')}${p.division?.name?' · '+esc(p.division.name):''}</span>${team.name?`<span class="file-tag team">${esc(team.name)}</span>`:''}${role?`<span class="file-tag">${esc(role)}</span>`:''}${p.status&&p.status!=='Active'?`<span class="file-tag warn">${esc(p.status)}</span>`:''}</span>
        <span class="file-honours">${patches.map(id=>`<img src="/assets/patches/${id}.webp${typeof artVersion==='function'?artVersion():''}" alt="${esc(patchNames[id])}" title="${esc(patchNames[id])}" loading="lazy">`).join('')}${ribbons.map(m=>`<span class="file-ribbon" title="${esc(m.name)}">${medalArtwork(m)}</span>`).join('')}${!patches.length&&!ribbons.length?'<small>No honours yet</small>':''}</span>
      </span>
      <span class="file-score"><b>${fmt(p.rating,1)}</b><small>ELO${p.position?' · #'+p.position:''}</small></span>
      <span class="file-open" aria-hidden="true">Open file →</span>
    </button>`;
  }
  function renderMembers(){
    const host=$('members-content'),d=roster();if(!host)return;
    if(!d){host.className='panel empty';host.textContent='Sign in to see the roster.';return;}
    const q=query.toLowerCase();
    const groups=RANKS.map((name,rank)=>({name,rank,list:d.players.filter(p=>p.rank===rank).sort((a,b)=>b.rating-a.rating)})).reverse();
    const shown=groups.filter(g=>g.list.length&&(rankFilter==='all'||String(g.rank)===rankFilter)).map(g=>({...g,list:g.list.filter(p=>!q||p.name.toLowerCase().includes(q))})).filter(g=>g.list.length);
    const patchCount=d.players.reduce((n,p)=>n+Object.keys(p.locker?.earned||{}).length,0);
    host.className='roster';
    host.innerHTML=`<div class="roster-head"><div><span class="eyebrow">01 / The roster</span><h2>Who's on <em>the books.</em></h2></div>
      <div class="roster-stats"><div><b>${d.players.length}</b><span>On the books</span></div><div><b>${groups.filter(g=>g.list.length).length}</b><span>Ranks filled</span></div><div><b>${patchCount}</b><span>Patches earned</span></div></div></div>
      <div class="roster-tools"><label class="roster-search"><span aria-hidden="true">⌕</span><input type="search" id="roster-search" placeholder="Search the roster…" value="${esc(query)}" aria-label="Search the roster"></label>
      <div class="roster-chips"><button type="button" data-rank-filter="all" aria-pressed="${rankFilter==='all'}">Everyone <b>${d.players.length}</b></button>${groups.filter(g=>g.list.length).map(g=>`<button type="button" data-rank-filter="${g.rank}" aria-pressed="${rankFilter===String(g.rank)}">${esc(g.name)} <b>${g.list.length}</b></button>`).join('')}</div></div>
      ${shown.map(g=>`<section class="rank-group"><div class="rank-group-head"><span class="rank-no">${String(g.rank+1).padStart(2,'0')}</span><img src="/badges/${BADGES[g.rank]}.png" alt=""><h3>${esc(g.name)}</h3><span class="rank-count">${g.list.length} ${g.list.length===1?'file':'files'}</span></div>
        <div class="file-grid">${g.list.map((p,i)=>memberCard(p,i+1)).join('')}</div></section>`).join('')||'<p class="empty">Nobody matches that search.</p>'}`;
  }

  // --- Leaderboards hub ------------------------------------------------------
  const boards=[
    {key:'rating',title:'Season ELO',scope:'This season',desc:'The main event. Climb this one and you climb the ranks.',value:p=>p.rating,fmt:v=>fmt(v,1)},
    {key:'kills',title:'Total kills',scope:'All time',desc:'Who has put the most rounds where they count.',value:p=>p.stats?.kills,fmt:v=>fmt(v)},
    {key:'kd',title:'Kill / death ratio',scope:'All time',desc:'Staying alive while the other lot do not.',value:p=>p.stats?.kd,fmt:v=>fmt(v,2)},
    {key:'wins',title:'Match wins',scope:'All time',desc:'Rounds won. The only stat the squad really cares about.',value:p=>p.stats?.wins,fmt:v=>fmt(v)},
    {key:'hoursPlayed',title:'Time in the field',scope:'All time',desc:'The ones who just cannot put it down.',value:p=>p.stats?.hoursPlayed,fmt:v=>fmt(v)+'h'},
    {key:'killsPerHour',title:'Kills per hour',scope:'All time',desc:'Pace, not patience. Kills for every hour played.',value:p=>p.stats?.killsPerHour,fmt:v=>fmt(v,1)},
    {key:'fantasy',title:'Fantasy Squad',scope:'This season',desc:'The best pickers. Daily squads, season totals.',href:'#club'},
    {key:'honours',title:'Hall of fame',scope:'Past seasons',desc:'Every season podium, kept forever.',href:'#honours'}];
  function top3(d,b){
    if(!b.value)return '';
    const rows=d.players.filter(p=>Number.isFinite(b.value(p))).sort((x,y)=>b.value(y)-b.value(x)).slice(0,3);
    return rows.length?`<ol class="board-top">${rows.map((p,i)=>`<li><span>${i+1}</span>${esc(short(p.name))}<b>${b.fmt(b.value(p))}</b></li>`).join('')}</ol>`:'<p class="board-empty">No data yet</p>';
  }
  function renderBoards(){
    const host=$('leaderboards-content'),d=roster();if(!host)return;
    if(!d){host.className='panel empty';host.textContent='Sign in to see the boards.';return;}
    host.className='boards';
    host.innerHTML=`<div class="roster-head"><div><span class="eyebrow">01 / The rankings</span><h2>Who's setting <em>the pace.</em></h2></div><p class="boards-intro">Pick a board. Equal scores share a place, and every name links to the member behind it.</p></div>
      <div class="board-grid">${boards.map((b,i)=>`<a class="board-card" href="${b.href||'#standings'}" ${b.href?'':`data-board="${b.key}"`}>
        <span class="board-no">${String(i+1).padStart(2,'0')}</span><span class="board-kicker">🏆 Rankings</span>
        <span class="board-scope">${esc(b.scope)}</span><strong>${esc(b.title)}</strong><span class="board-desc">${esc(b.desc)}</span>${top3(d,b)}
        <span class="board-foot">${b.href?'Open':'See the full board'}<span aria-hidden="true">→</span></span></a>`).join('')}</div>`;
  }

  document.addEventListener('click',e=>{
    const chip=e.target.closest('[data-rank-filter]');if(chip){rankFilter=chip.dataset.rankFilter;renderMembers();return;}
    const board=e.target.closest('[data-board]');
    if(board){const select=$('ranking');if(select){select.value=board.dataset.board;setTimeout(()=>select.dispatchEvent(new Event('change')),0);}}
  });
  document.addEventListener('input',e=>{if(e.target.id==='roster-search'){query=e.target.value;const pos=e.target.selectionStart;renderMembers();const box=$('roster-search');box.focus();box.setSelectionRange(pos,pos);}});
  const art=()=>document.querySelectorAll('img[data-art-src]').forEach(img=>{img.src=img.dataset.artSrc+(typeof artVersion==='function'?artVersion():'');img.removeAttribute('data-art-src');});
  const before=window.hqRender;
  window.hqRender=function(){before?.();renderMembers();renderBoards();};
  const start=()=>{art();renderMembers();renderBoards();};
  document.readyState==='loading'?document.addEventListener('DOMContentLoaded',start):start();
})();
