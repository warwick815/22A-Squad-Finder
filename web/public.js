'use strict';
// Public standings page: read-only data from /api/public, no sign-in.
(function(){
  const $=id=>document.getElementById(id);
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt=(v,d=0)=>v==null||!Number.isFinite(Number(v))?'—':Number(v).toLocaleString('en-GB',{minimumFractionDigits:d,maximumFractionDigits:d});
  const avatar=p=>p.avatar?`<img class="member-avatar" src="${esc(p.avatar)}" alt="" loading="lazy" referrerpolicy="no-referrer">`:`<span class="member-avatar avatar-initial">${esc((p.name||'?').replace(/\[[^\]]*\]\s*/,'').slice(0,1).toUpperCase())}</span>`;
  const medal=['gold','silver','bronze'];
  let shown=25;
  function standings(players){
    if(!players.length)return '<p class="empty">No active members on the board yet.</p>';
    return `<div class="table-wrap"><table class="pub-table"><thead><tr><th>#</th><th>Member</th><th>Rank</th><th class="num">Season ELO</th><th class="num">K/D</th><th class="num">Wins</th></tr></thead><tbody>${players.slice(0,shown).map(p=>`<tr class="${p.position<=3?'podium-'+medal[p.position-1]:''}"><td class="pos">${p.position}</td><td><span class="pub-who">${avatar(p)}${esc(p.name)}</span></td><td><span class="pub-rank"><img src="${esc(p.badge)}" alt="">${esc(p.rank)}${p.division?` <small>${esc(p.division)}</small>`:''}</span></td><td class="num"><b>${fmt(p.rating,1)}</b></td><td class="num">${fmt(p.kd,2)}</td><td class="num">${fmt(p.wins)}</td></tr>`).join('')}</tbody></table></div>${players.length>shown?`<button type="button" class="ghost small" id="pub-more">Show all ${players.length} members</button>`:''}`;
  }
  function honours(archives){
    if(!archives.length)return '<p class="empty">The first season is still being fought. Winners appear here when it closes.</p>';
    return archives.map(a=>`<div class="pub-season"><h3>Season ${fmt(a.season)}</h3><ol class="pub-podium">${a.podium.map((p,i)=>`<li class="${medal[i]}"><span class="pub-place">${i+1}</span>${avatar(p)}<span>${esc(p.name)}<small>${esc(p.rank)}</small></span><b>${fmt(p.rating,1)}</b></li>`).join('')}</ol></div>`).join('');
  }
  function fantasyBoard(rows){
    if(!rows.length)return '<p class="empty">No completed Fantasy rounds this season yet.</p>';
    return `<ol class="pub-podium pub-fantasy">${rows.map((p,i)=>`<li class="${medal[i]||''}"><span class="pub-place">${i+1}</span>${avatar(p)}<span>${esc(p.name)}</span><b>${fmt(p.points,1)} <small>pts</small></b></li>`).join('')}</ol>`;
  }
  async function load(){
    try{
      const r=await fetch('/api/public',{headers:{Accept:'application/json'}});
      const d=await r.json();if(!r.ok)throw new Error(d.error||'Could not load the standings.');
      const stats=$('pub-stats').querySelectorAll('strong');stats[0].textContent=fmt(d.members);stats[1].textContent=fmt(d.season);
      const draw=()=>{$('pub-standings').className='';$('pub-standings').innerHTML=standings(d.players);$('pub-more')?.addEventListener('click',()=>{shown=Infinity;draw();});};
      draw();
      $('pub-honours').className='';$('pub-honours').innerHTML=honours(d.archives);
      $('pub-fantasy').className='';$('pub-fantasy').innerHTML=fantasyBoard(d.fantasy);
      $('pub-updated').textContent=d.updated?'Updated '+new Date(d.updated).toLocaleString('en-GB',{dateStyle:'medium',timeStyle:'short'}):'';
      $('pub-status').textContent='';
    }catch(e){$('pub-status').textContent=e.message;}
  }
  document.readyState==='loading'?document.addEventListener('DOMContentLoaded',load):load();
  setInterval(()=>{if(document.visibilityState==='visible')load();},120000);
})();
