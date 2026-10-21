'use strict';
// Site chrome: the live strip above the header and the dismissible announcement.
(function(){
  const $=id=>document.getElementById(id);
  // Fantasy rounds always lock at 18:00 UK time, so the countdown needs no data.
  function fantasyLock(){
    const parts=Object.fromEntries(new Intl.DateTimeFormat('en-GB',{timeZone:'Europe/London',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(new Date()).map(p=>[p.type,p.value]));
    let left=18*60-(Number(parts.hour)*60+Number(parts.minute));if(left<=0)left+=1440;
    return Math.floor(left/60)+'h '+String(left%60).padStart(2,'0')+'m';
  }
  function live(){
    const f=$('live-fantasy');if(f)f.textContent=fantasyLock();
    // `data` is a top-level let in app.js: shared between scripts, but not on window.
    const d=typeof data!=='undefined'?data:null;
    if(d&&Array.isArray(d.players)){
      const linked=d.players.filter(p=>p.linked!==false).length;
      $('live-members').textContent=linked+' members linked';
      const s=$('live-season');if(s){s.textContent='Season '+(d.season||1);s.hidden=false;}
    }
  }
  const before=window.hqRender;
  window.hqRender=function(){before?.();live();};
  setInterval(live,30000);
  // Announcement: once dismissed it stays hidden until its text changes.
  function announce(){
    const bar=$('announce');if(!bar)return;
    const key='22a-announce:'+bar.querySelector('.announce-text').textContent.trim().slice(0,80);
    try{if(localStorage.getItem(key)==='hidden')bar.hidden=true;}catch{}
    $('announce-close')?.addEventListener('click',()=>{bar.hidden=true;try{localStorage.setItem(key,'hidden');}catch{}});
  }
  // Opening a link like /#club makes the browser jump to that section, hiding the
  // live strip and announcement; start every page at the top instead.
  if('scrollRestoration' in history)history.scrollRestoration='manual';
  const top=()=>window.scrollTo({top:0,behavior:'instant'});
  window.addEventListener('load',()=>{top();setTimeout(top,60);setTimeout(top,400);});
  document.readyState==='loading'?document.addEventListener('DOMContentLoaded',()=>{announce();live();}):(announce(),live());
})();
