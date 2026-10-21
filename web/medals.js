"use strict";
// Decorations are drawn as service ribbons (Battlelog-style ribbon rack).
// Colours follow British Army ribbon conventions; the designs themselves are original.
const ribbonInk={navy:'#1c2752',royal:'#2a5cae',sky:'#7fb2dc',red:'#a8182c',scarlet:'#cf2f2f',white:'#efece2',gold:'#d4a32a',green:'#2c6a37',khaki:'#a8935a',purple:'#5b2d84',black:'#18181a',orange:'#cf6b1f',silver:'#b9bcc0',bronze:'#a5662f'};
// Each design lists the stripes from the left edge to the centre; the right half mirrors it.
const ribbonDesigns={
  linked:{stripes:[['navy',6],['red',3],['white',1],['red',3]]},
  stripes:{stripes:[['green',5],['khaki',3],['white',1],['khaki',4]]},
  nco:{stripes:[['red',4],['gold',2],['red',3],['gold',1],['navy',3]]},
  veteran:{stripes:[['purple',5],['white',2],['purple',3],['white',1],['purple',2]]},
  kills100:{stripes:[['black',4],['scarlet',2],['black',2],['scarlet',5]]},
  kills1000:{stripes:[['black',4],['scarlet',2],['black',2],['scarlet',5]],device:'silver'},
  kills5000:{stripes:[['black',4],['scarlet',2],['black',2],['scarlet',5]],device:'gold'},
  wins10:{stripes:[['navy',3],['white',2],['red',3],['white',2],['royal',3]]},
  wins50:{stripes:[['navy',3],['white',2],['red',3],['white',2],['royal',3]],device:'silver'},
  hours100:{stripes:[['green',6],['gold',2],['green',2],['white',1],['green',2]]},
  club1:{stripes:[['purple',4],['gold',3],['black',2],['gold',4]]},
  club10:{stripes:[['purple',4],['gold',3],['black',2],['gold',4]],device:'silver'},
  club25:{stripes:[['purple',4],['gold',3],['black',2],['gold',4]],device:'gold'},
  sergeant:{stripes:[['red',4],['gold',2],['red',3],['gold',1],['navy',3]],device:'silver'},
  staffsgt:{stripes:[['red',4],['gold',2],['red',3],['gold',1],['navy',3]],device:'gold'},
  warrant:{stripes:[['navy',3],['gold',2],['red',2],['gold',2],['navy',2],['white',1]],device:'gold'},
  veteran2:{stripes:[['purple',5],['white',2],['purple',3],['white',1],['purple',2]],device:'silver'},
  hours250:{stripes:[['green',6],['gold',2],['green',2],['white',1],['green',2]],device:'silver'},
  hours500:{stripes:[['green',6],['gold',2],['green',2],['white',1],['green',2]],device:'gold'},
  kills10000:{stripes:[['black',3],['gold',1],['black',2],['scarlet',2],['black',1],['scarlet',4]],device:'gold'},
  wins100:{stripes:[['navy',3],['white',2],['red',3],['white',2],['royal',3]],device:'gold'},
  wins250:{stripes:[['red',3],['navy',2],['white',1],['navy',2],['red',2],['gold',3]]},
  sharpshooter:{stripes:[['green',4],['black',2],['white',1],['black',2],['green',3]]},
  rapidfire:{stripes:[['orange',3],['black',2],['orange',2],['black',1],['scarlet',4]]},
  cash10m:{stripes:[['khaki',4],['gold',2],['green',3],['gold',1],['green',3]]},
  cash50m:{stripes:[['khaki',4],['gold',2],['green',3],['gold',1],['green',3]],device:'gold'},
  patches3:{stripes:[['khaki',3],['purple',2],['khaki',2],['white',1],['purple',4]]},
  patches6:{stripes:[['khaki',3],['purple',2],['khaki',2],['white',1],['purple',4]],device:'silver'},
  tags1:{stripes:[['black',3],['bronze',2],['black',2],['white',1],['bronze',4]]},
  tags10:{stripes:[['black',3],['bronze',2],['black',2],['white',1],['bronze',4]],device:'bronze'},
  tagsilver:{stripes:[['black',3],['silver',2],['black',2],['white',1],['silver',4]],device:'silver'},
  taggold:{stripes:[['black',3],['gold',2],['black',2],['white',1],['gold',4]],device:'gold'},
  headhunter:{stripes:[['scarlet',3],['black',2],['white',1],['black',2],['scarlet',4]]},
  marksman:{stripes:[['green',3],['khaki',2],['green',2],['white',1],['black',4]]},
  hawkeye:{stripes:[['green',3],['khaki',2],['green',2],['white',1],['black',4]],device:'gold'},
  grenadier:{stripes:[['orange',3],['green',2],['orange',2],['black',1],['green',4]]},
  sapper:{stripes:[['royal',3],['red',2],['royal',2],['khaki',1],['red',4]]},
  crewman:{stripes:[['black',3],['khaki',2],['green',3],['khaki',1],['black',3]]},
  revenge:{stripes:[['purple',3],['black',2],['scarlet',3],['black',1],['purple',3]]}
};
function ribbonDesign(m){
  if(['gold','silver','bronze'].includes(m.metal))return {stripes:[['navy',3],['white',1],['red',4],[m.metal,5]],device:m.metal,star:true};
  if(ribbonDesigns[m.id])return ribbonDesigns[m.id];
  // Unknown awards get a stable design derived from their id.
  const keys=['navy','red','green','purple','royal','khaki','gold','black'];let h=0;for(const c of String(m.id||m.name))h=(h*31+c.charCodeAt(0))>>>0;
  return {stripes:[[keys[h%8],5],['white',1],[keys[(h>>3)%8],4],[keys[(h>>6)%8],3]]};
}
function ribbonSVG(m){
  const d=ribbonDesign(m),half=[];for(const [c,w] of d.stripes)half.push([ribbonInk[c]||c,w]);
  const all=[...half,...[...half].reverse().slice(1)],total=all.reduce((s,[,w])=>s+w,0)||1;
  let x=0;const rects=all.map(([c,w])=>{const width=118*w/total,r=`<rect x="${(1+x).toFixed(2)}" y="1" width="${(width+.4).toFixed(2)}" height="34" fill="${c}"/>`;x+=width;return r;}).join('');
  const dev=d.device?(d.star?`<path d="M60 9.5l2.6 5.3 5.8.8-4.2 4.1 1 5.8-5.2-2.7-5.2 2.7 1-5.8-4.2-4.1 5.8-.8z" fill="${ribbonInk[d.device]}" stroke="#0007" stroke-width=".7"/>`:`<circle cx="60" cy="18" r="5.2" fill="${ribbonInk[d.device]}" stroke="#0008" stroke-width=".7"/><circle cx="60" cy="18" r="2.2" fill="#fff6" />`):'';
  return `<svg class="ribbon-svg" viewBox="0 0 120 36" preserveAspectRatio="none"><rect width="120" height="36" fill="#111"/>${rects}<rect x="1" y="1" width="118" height="34" fill="url(#rb-sheen)"/><rect x="1" y="1" width="118" height="34" fill="url(#rb-weave)" opacity=".35"/>${dev}<rect x=".5" y=".5" width="119" height="35" fill="none" stroke="#000a"/></svg>`;
}
// Shared gradient/pattern definitions, added to the page once.
(function(){const defs=document.createElementNS('http://www.w3.org/2000/svg','svg');defs.setAttribute('width','0');defs.setAttribute('height','0');defs.setAttribute('aria-hidden','true');defs.style.position='absolute';
  defs.innerHTML='<defs><linearGradient id="rb-sheen" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".38"/><stop offset=".22" stop-color="#fff" stop-opacity=".08"/><stop offset=".6" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".4"/></linearGradient><pattern id="rb-weave" width="2" height="2" patternUnits="userSpaceOnUse"><rect width="1" height="2" fill="#000" opacity=".25"/></pattern></defs>';
  const add=()=>document.body.prepend(defs);document.body?add():document.addEventListener('DOMContentLoaded',add);})();
function medalType(m){return ['gold','silver','bronze'].includes(m.metal)?m.metal:m.group==='combat'?'combat':m.group==='club'?'market':'service';}
function medalArtwork(m,extra=''){return `<span class="ribbon ribbon-${medalType(m)} ${m.earned?'':'is-locked'} ${extra}" role="img" aria-label="${esc(m.name)} ribbon">${ribbonSVG(m)}</span>`;}
function ribbonRack(medals,{empty='No ribbons awarded yet.',inspect=true}={}){
  if(!medals.length)return `<p class="pf-note">${esc(empty)}</p>`;
  return `<div class="ribbon-rack">${medals.map(m=>inspect?`<button type="button" class="ribbon-slot" data-pf-medal="${esc(m.name)}" title="${esc(m.name)}">${medalArtwork(m)}</button>`:`<span class="ribbon-slot" title="${esc(m.name)}">${medalArtwork(m)}</span>`).join('')}</div>`;
}
function openMedal(m){let dialog=document.getElementById('medal-detail');if(!dialog){dialog=document.createElement('dialog');dialog.id='medal-detail';dialog.setAttribute('aria-labelledby','medal-detail-title');document.body.appendChild(dialog);}dialog.innerHTML=`<form method="dialog"><button class="secondary small" aria-label="Close ribbon details">Close ×</button></form><div class="medal-detail-art ${m.earned?'':'is-locked'}">${medalArtwork(m)}</div><span class="eyebrow">${esc(m.group)} / ${m.earned?'AWARDED':'NOT YET EARNED'}</span><h2 id="medal-detail-title">${esc(m.name)}</h2><p>${esc(m.detail)}</p><p>${m.earned?'Part of your permanent service record.':m.value==null?'Waiting for source statistics.':fmt(Math.min(m.value,m.target))+' / '+fmt(m.target)+' towards this award.'}</p>${m.earned&&m.first_observed?`<p class="fine">First recognised ${esc(dateLabel(m.first_observed))}</p>`:''}`;dialog.showModal();}
