'use strict';
// Clips page: Medal clips members post in the Discord clips channel.
let clipsData=null,clipsLoading=false,clipsSort='new',clipsRange='all',clipsWho='',clipsPlaying='';
function clipsDemo(){const now=Date.now(),names=data.players.map(p=>({id:p.id,name:p.name,avatar:p.avatar}));
  return {enabled:true,staff:true,clips:['Clutch defuse on the last tick','Tank kill from 400m','Medic revive train','Absolute chaos at the bridge','Wrong grenade, right result','Sniper duel'].map((t,i)=>({id:'c'+i,url:'https://medal.tv/',medal:null,title:t,thumb:'',player:null,posted:new Date(now-i*9*3600e3).toISOString(),votes:[7,12,3,9,1,5][i],hidden:i===5,author:names[i%names.length]}))};}
async function loadClips(){if(!data||clipsLoading)return;clipsLoading=true;
  try{clipsData=demo?clipsDemo():await api('/api/clips');renderClips();}
  catch(e){$('clips-content').className='panel empty';$('clips-content').textContent=e.message;}
  finally{clipsLoading=false;}}
function clipsAgo(iso){const s=(Date.now()-Date.parse(iso))/1000;return s<3600?Math.max(1,Math.round(s/60))+'m ago':s<86400?Math.round(s/3600)+'h ago':s<604800?Math.round(s/86400)+'d ago':new Date(iso).toLocaleDateString('en-GB',{day:'numeric',month:'short'});}
function clipsPlayer(c){return c.player||(c.medal?'https://medal.tv/clip/'+encodeURIComponent(c.medal):null);}
function renderClips(){
  const host=$('clips-content'),d=clipsData;if(!d)return;host.className='';
  if(!d.enabled){host.innerHTML='<div class="panel empty">Clips are not switched on yet. Staff: see CLIPS-SETUP.md.</div>';return;}
  const people=[...new Map(d.clips.map(c=>[c.author.id,c.author])).values()].sort((a,b)=>a.name.localeCompare(b.name));
  const week=Date.now()-7*864e5;
  let list=d.clips.filter(c=>(clipsRange==='all'||Date.parse(c.posted)>=week)&&(!clipsWho||c.author.id===clipsWho));
  if(clipsSort==='top')list=[...list].sort((a,b)=>b.votes-a.votes||Date.parse(b.posted)-Date.parse(a.posted));
  host.innerHTML=`<div class="clips-bar"><div class="fx-tabs">${[['new','Newest'],['top','Top clips']].map(([k,l])=>`<button type="button" data-clips-sort="${k}" aria-selected="${clipsSort===k}">${l}</button>`).join('')}${[['all','All time'],['week','This week']].map(([k,l])=>`<button type="button" data-clips-range="${k}" aria-selected="${clipsRange===k}">${l}</button>`).join('')}</div>
    <select id="clips-who" aria-label="Filter by member"><option value="">Everyone</option>${people.map(p=>`<option value="${esc(p.id)}" ${p.id===clipsWho?'selected':''}>${esc(p.name)}</option>`).join('')}</select></div>
  ${list.length?`<div class="clips-grid">${list.map(c=>{const playing=clipsPlaying===c.id&&clipsPlayer(c);return `<article class="clip ${c.hidden?'is-hidden':''}">
    <div class="clip-media">${playing?`<iframe src="${esc(clipsPlayer(c))}" title="${esc(c.title||'Medal clip')}" allow="autoplay; fullscreen" allowfullscreen loading="lazy"></iframe>`:`<button type="button" class="clip-thumb" data-clip-play="${esc(c.id)}" aria-label="Play ${esc(c.title||'clip')}">${c.thumb?`<img src="${esc(c.thumb)}" alt="" loading="lazy" referrerpolicy="no-referrer">`:'<span class="clip-noimg">MEDAL</span>'}<span class="clip-play" aria-hidden="true">▶</span></button>`}</div>
    <div class="clip-info"><strong title="${esc(c.title||'')}">${esc(c.title||'Medal clip')}</strong>
      <div class="clip-meta">${fantasyAvatar(c.author)}<span>${esc(c.author.name)} · ${esc(clipsAgo(c.posted))}</span>${c.votes?`<span class="clip-votes" title="🔥 and 👍 reactions in Discord">🔥 ${fmt(c.votes)}</span>`:''}</div>
      <div class="clip-links"><a href="${esc(c.url)}" target="_blank" rel="noopener">Open on Medal ↗</a>${d.staff?`<button type="button" class="linkish" data-clip-hide="${esc(c.id)}" data-hidden="${c.hidden}">${c.hidden?'Show on website':'Hide'}</button>`:''}${c.hidden?'<span class="pill warning">Hidden</span>':''}</div></div></article>`;}).join('')}</div>`:`<div class="panel empty">${d.clips.length?'No clips match these filters.':'No clips yet. Post a Medal link in the 🎬clips🎬 channel on Discord and it will appear here.'}</div>`}`;
}
document.addEventListener('click',async e=>{
  if(e.target.closest('[data-clips-refresh]')){loadClips();return;}
  const t=e.target.closest('[data-clips-sort],[data-clips-range],[data-clip-play],[data-clip-hide]');if(!t||!clipsData)return;
  if(t.dataset.clipsSort){clipsSort=t.dataset.clipsSort;renderClips();return;}
  if(t.dataset.clipsRange){clipsRange=t.dataset.clipsRange;renderClips();return;}
  if(t.dataset.clipPlay){const c=clipsData.clips.find(c=>c.id===t.dataset.clipPlay);if(c&&!clipsPlayer(c)){window.open(c.url,'_blank','noopener');return;}clipsPlaying=t.dataset.clipPlay;renderClips();return;}
  if(t.dataset.clipHide){const hide=t.dataset.hidden!=='true';try{if(demo){notify('Design preview only.');return;}const r=await api('/api/clips',{action:hide?'hide':'show',id:t.dataset.clipHide});notify(r.message);await loadClips();}catch(err){notify(err.message);}}
});
document.addEventListener('change',e=>{if(e.target.id==='clips-who'){clipsWho=e.target.value;renderClips();}});
const clipsOriginalHQ=window.hqRender;
window.hqRender=function(){clipsOriginalHQ?.();if(location.hash==='#clips')loadClips();};
window.addEventListener('hashchange',()=>{if(location.hash==='#clips'){clipsPlaying='';loadClips();}});
