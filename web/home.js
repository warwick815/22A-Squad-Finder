'use strict';
// Home page: the community record band, the hero season label and card artwork.
(function(){
  const big=n=>n>=1e6?(n/1e6).toFixed(n>=1e7?0:1)+'M':n>=1e4?Math.round(n/1e3)+'K':Math.round(n).toLocaleString('en-GB');
  function record(){
    const d=typeof data!=='undefined'?data:null;
    const set=(k,v)=>{const el=document.querySelector(`[data-record="${k}"]`);if(el)el.textContent=v;};
    if(!d||!Array.isArray(d.players)){set('members','—');return;}
    const sum=k=>d.players.reduce((n,p)=>n+(Number.isFinite(p.stats?.[k])?p.stats[k]:0),0);
    set('members',d.players.length);set('kills',big(sum('kills')));set('hours',big(sum('hoursPlayed')));
    set('wins',big(sum('wins')));set('teamKills',big(sum('teamKills')));set('season',d.season||1);
    const note=document.getElementById('record-note');if(note)note.textContent='Lifetime totals across '+d.players.length+' linked members. Updated with every stats snapshot.';
    const season=document.getElementById('hero-season');if(season)season.textContent='Season '+(d.season||1)+' / in progress';
  }
  function art(){
    const v=typeof artVersion==='function'?artVersion():'';
    document.querySelectorAll('img[data-art-src]').forEach(img=>{img.src=img.dataset.artSrc+v;img.removeAttribute('data-art-src');});
  }
  const before=window.hqRender;
  window.hqRender=function(){before?.();record();};
  const start=()=>{art();record();};
  document.readyState==='loading'?document.addEventListener('DOMContentLoaded',start):start();
})();
