'use strict';
// Dog tags: 10 / 20 / 30 kills on the same player earns a bronze / silver / gold tag
// stamped with that player's name. Drawn as SVG so names are crisp at any size.
const dogtagMetal={
  bronze:['#e2a56b','#a5662f','#5e3416','#f3c69a'],
  silver:['#f1f3f5','#aab1b8','#5d646b','#ffffff'],
  gold:['#ffe28a','#d4a32a','#7a5512','#fff3c4'],
  none:['#5a625b','#3a413b','#202621','#7c857d']};
let dogtagSeq=0;
function dogtagSVG(d){
  const t=d.tier||'none',[hi,mid,lo,shine]=dogtagMetal[t],id='dt'+(++dogtagSeq);
  const name=String(d.victim||'Unknown').replace(/^\[[^\]]*\]\s*/,'').toUpperCase().slice(0,18);
  const clan=(String(d.victim||'').match(/^\[([^\]]*)\]/)||[])[1];
  const size=name.length>13?13:name.length>10?15:17;
  return `<svg class="dogtag-svg" viewBox="0 0 220 120" role="img" aria-label="${esc(t==='none'?'Dog tag in progress':t+' dog tag')} for ${esc(d.victim)}">
  <defs><linearGradient id="${id}g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="${hi}"/><stop offset=".45" stop-color="${mid}"/><stop offset="1" stop-color="${lo}"/></linearGradient>
  <linearGradient id="${id}s" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${shine}" stop-opacity=".55"/><stop offset=".35" stop-color="${shine}" stop-opacity="0"/></linearGradient>
  <filter id="${id}e"><feOffset dy="1"/><feGaussianBlur stdDeviation=".4"/><feComposite in2="SourceAlpha" operator="arithmetic" k2="-1" k3="1" result="i"/><feFlood flood-color="#000" flood-opacity=".55"/><feComposite in2="i" operator="in"/><feComposite in2="SourceGraphic" operator="over"/></filter></defs>
  <path d="M30 6H190Q214 6 214 30V90Q214 114 190 114H30Q6 114 6 90V72Q16 66 16 60Q16 54 6 48V30Q6 6 30 6Z" fill="url(#${id}g)" stroke="${lo}" stroke-width="2"/>
  <path d="M30 6H190Q214 6 214 30V90Q214 114 190 114H30Q6 114 6 90V72Q16 66 16 60Q16 54 6 48V30Q6 6 30 6Z" fill="url(#${id}s)"/>
  <path d="M34 14H186Q206 14 206 32V88Q206 106 186 106H34Q22 106 18 96" fill="none" stroke="${lo}" stroke-opacity=".45" stroke-width="1.5"/>
  <circle cx="196" cy="60" r="7" fill="#0b0e0c" stroke="${lo}" stroke-width="2"/>
  <g filter="url(#${id}e)" fill="${lo}" font-family="JetBrains Mono, ui-monospace, monospace" font-weight="600">
    <text x="30" y="40" font-size="${size}" letter-spacing="1">${esc(name)}</text>
    <text x="30" y="60" font-size="11" letter-spacing="1.5">${esc(clan?'['+clan+']':'NO CLAN')} · ${esc(String(d.kills))} KILLS</text>
    <text x="30" y="78" font-size="11" letter-spacing="1.5">${d.headshots?esc(String(d.headshots))+' HEADSHOTS':'TF21 SERVERS'}</text>
    <text x="30" y="96" font-size="10" letter-spacing="2">22A WARDOGS · ${esc(t==='none'?d.kills+'/'+d.next:t.toUpperCase())}</text>
  </g></svg>`;
}
function dogtagCard(d){
  const progress=d.next?Math.round(100*d.kills/d.next):100;
  return `<figure class="dogtag ${d.tier?'tier-'+d.tier:'is-progress'}">${dogtagSVG(d)}<figcaption>
    <strong>${esc(d.victim)}</strong><span>${d.tier?esc(d.tier[0].toUpperCase()+d.tier.slice(1))+' tag':'In progress'} · ${fmt(d.kills)} kills</span>
    ${d.next?`<span class="dogtag-bar" title="${fmt(d.kills)} / ${d.next} kills"><i data-w="${progress}"></i></span><small>${d.next-d.kills} more for ${d.next===10?'bronze':d.next===20?'silver':'gold'}</small>`:'<small>Maxed out</small>'}
  </figcaption></figure>`;
}
function dogtagPanel(p,owner){
  const tags=p.dogtags||[],earned=tags.filter(d=>d.tier),c=p.combat;
  const count=t=>earned.filter(d=>d.tier===t).length;
  if(!c&&!tags.length)return `<article class="panel dogtags-empty"><span class="eyebrow">TF21 kill feed</span><h2>No dog tags <em>yet.</em></h2><p>Kill the same player 10 times on a TF21 server to take their bronze tag. 20 kills makes it silver, 30 makes it gold.</p></article>`;
  return `<article class="panel dogtags-panel"><div class="section-head"><div><span class="eyebrow">TF21 kill feed / collected</span><h2>${owner?'Your':'Their'} dog <em>tags.</em></h2></div>
    <div class="dogtag-counts"><span class="tier-gold"><b>${count('gold')}</b>Gold</span><span class="tier-silver"><b>${count('silver')}</b>Silver</span><span class="tier-bronze"><b>${count('bronze')}</b>Bronze</span></div></div>
    <p class="fine">10 kills on the same player takes their bronze tag, 20 silver, 30 gold. Team kills never count. Tags are permanent.</p>
    ${tags.length?`<div class="dogtag-grid">${tags.map(dogtagCard).join('')}</div>`:'<p class="empty">No tags yet. The first one comes at 10 kills on the same player.</p>'}</article>
  ${c?`<article class="panel combat-card"><div class="section-head"><div><span class="eyebrow">TF21 kill feed / combat record</span><h2>The <em>details.</em></h2></div></div>
    <div class="combat-grid">
      <div><span>Nemesis</span><strong>${c.nemesis?esc(c.nemesis.name):'—'}</strong><small>${c.nemesis?'Killed '+(owner?'you':'them')+' '+fmt(c.nemesis.count)+' times':'Nobody has killed '+(owner?'you':'them')+' 3+ times'}</small></div>
      <div><span>Favourite victim</span><strong>${c.favourite?esc(c.favourite.name):'—'}</strong><small>${c.favourite?fmt(c.favourite.count)+' kills':'No kills yet'}</small></div>
      <div><span>Longest kill</span><strong>${c.longest?fmt(c.longest.m,0)+' m':'—'}</strong><small>${c.longest?esc(c.longest.weapon)+' on '+esc(c.longest.victim):''}</small></div>
      <div><span>Headshots</span><strong>${fmt(c.headshots)}</strong><small>${c.kills?fmt(100*c.headshots/c.kills,0)+'% of kills':''}</small></div>
      <div><span>Grenade / mine</span><strong>${fmt(c.grenade)} / ${fmt(c.explosive)}</strong><small>Grenade and Claymore kills</small></div>
      <div><span>Vehicle kills</span><strong>${fmt(c.vehicle)}</strong><small>With vehicle weapons</small></div>
      <div><span>Payback</span><strong>${fmt(c.revenge)}</strong><small>Kills on ${owner?'your':'their'} nemesis</small></div>
      <div><span>Friendly fire</span><strong>${fmt(c.team_kills)}</strong><small><a href="#shame">Hall of shame →</a></small></div>
    </div></article>`:''}`;
}
