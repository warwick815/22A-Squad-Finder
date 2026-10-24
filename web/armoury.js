'use strict';
// The Armoury: Merits balance, how to earn them, and one booster a day.
(function(){
  const $=id=>document.getElementById(id);
  let arm=null,busy=false,timer=null;
  const icons={boost15:'⚡',boost2:'⚡⚡',flak:'🛡',squad:'🪖'};
  function demoArmoury(){const now=Date.now()/1000;return {season:data.season||2,balance:37,earned:52,earned_today:9,daily_cap:30,used_today:null,
    booster:{name:'1.5x ELO booster',multiplier:1.5,until:now+2280},flak:4,in_squad:true,linked:true,
    items:[{id:'boost15',name:'1.5x ELO booster',cost:15,detail:'Kills and wins earn 1.5x ELO for 1 hour.'},{id:'boost2',name:'2x ELO booster',cost:30,detail:'Kills and wins earn 2x ELO for 30 minutes.'},{id:'flak',name:'Flak jacket',cost:10,detail:'Your next 10 deaths cost no ELO (lasts until used or the season ends).'},{id:'squad',name:'Squad booster',cost:40,detail:'Everyone in your TF21 squad session (you included) earns 1.25x ELO for 1 hour.'}],
    earn:[['First match of the day',2],['Every 25 kills (up to 4 a day)',1],['Taking part in a squad session',3],['Collecting a bounty',5],['An operation you took part in completing',10],['Promotion',5],['Fantasy round 1st / 2nd / 3rd','5 / 3 / 2']],
    log:[{at:now-600,amount:3,reason:'Squad session on UK2'},{at:now-3600,amount:-15,reason:'1.5x ELO booster'},{at:now-4000,amount:2,reason:'First match of the day'},{at:now-90000,amount:5,reason:'Bounty on BritishSam'}]};}
  async function load(){if(typeof data==='undefined'||!data)return;try{arm=demo?demoArmoury():await api('/api/merits');render();}catch(e){$('armoury-content').className='panel empty';$('armoury-content').textContent=e.message;}}
  const left=until=>{const s=Math.max(0,Math.round(until-Date.now()/1000));return `${Math.floor(s/60)}:${String(s%60).padStart(2,'0')}`;};
  const when=ts=>new Date(ts*1000).toLocaleString('en-GB',{weekday:'short',hour:'2-digit',minute:'2-digit'});
  function why(item){
    if(!arm.linked)return 'Link Steam to use the Armoury';
    if(arm.used_today)return `Used today: ${arm.used_today}`;
    if(arm.balance<item.cost)return `Need ${item.cost-arm.balance} more Merits`;
    if(item.id!=='flak'&&arm.booster)return 'A booster is already running';
    if(item.id==='squad'&&!arm.in_squad)return 'Needs a live TF21 squad session';
    return '';
  }
  function render(){
    const host=$('armoury-content'),a=arm;if(!host||!a)return;host.className='armoury';
    host.innerHTML=`<div class="arm-top">
      <article class="panel arm-wallet"><span class="eyebrow">Season ${esc(a.season)} wallet</span><strong class="arm-balance">${fmt(a.balance)}<small>Merits</small></strong>
        <div class="arm-today"><span>Earned today</span><b>${fmt(a.earned_today)} / ${fmt(a.daily_cap)}</b></div><div class="arm-cap" role="progressbar" aria-valuemin="0" aria-valuemax="${a.daily_cap}" aria-valuenow="${a.earned_today}"><i data-w="${(100*a.earned_today/a.daily_cap).toFixed(1)}"></i></div>
        <p class="fine">${fmt(a.earned)} earned this season. Merits reset at the start of every season and can only be earned in game.</p></article>
      <article class="panel arm-status"><span class="eyebrow">Active</span>
        ${a.booster?`<div class="arm-live"><b>${esc(a.booster.name)}</b><span class="arm-timer" data-until="${a.booster.until}">${left(a.booster.until)}</span><small>left · kills and wins earn ${a.booster.multiplier}x ELO</small></div>`:'<p class="arm-idle">No booster running.</p>'}
        ${a.flak?`<p class="arm-flak-note">🛡 Flak jacket: next <b>${fmt(a.flak)}</b> deaths cost no ELO.</p>`:''}
        <p class="fine">${a.used_today?`Today's item: ${esc(a.used_today)}. One Armoury item a day; the next is available after midnight UK time.`:'One Armoury item a day. Boosters run on the clock from the moment you use them, so be in game.'}</p></article></div>
      <div class="roster-head"><div><span class="eyebrow">01 / The shop</span><h2>Spend <em>Merits.</em></h2></div><p class="boards-intro">Boosters multiply the ELO from kills and wins, on top of your combat rating. Deaths and losses never cost more.</p></div>
      <div class="arm-shop">${a.items.map(item=>{const block=why(item);return `<article class="arm-item arm-${esc(item.id)}"><span class="arm-icon" aria-hidden="true">${icons[item.id]||'★'}</span><h3>${esc(item.name)}</h3><p>${esc(item.detail)}</p>
        <div class="arm-buy"><b>${fmt(item.cost)} <small>Merits</small></b><button type="button" class="small" data-arm-buy="${esc(item.id)}" ${block?'disabled':''}>Use</button></div>${block?`<small class="arm-why">${esc(block)}</small>`:''}</article>`;}).join('')}</div>
      <div class="arm-bottom"><article class="panel"><span class="eyebrow">02 / Earn Merits</span><h2>Play. <em>Turn up.</em></h2><table class="arm-earn"><tbody>${a.earn.map(([k,v])=>`<tr><td>${esc(k)}</td><td>+${esc(v)}</td></tr>`).join('')}</tbody></table><p class="fine">Up to ${fmt(a.daily_cap)} Merits a day. Awards appear a few minutes after the stats feeds update.</p></article>
      <article class="panel"><span class="eyebrow">03 / Your log</span><h2>Recent <em>Merits.</em></h2>${a.log.length?`<ul class="arm-log">${a.log.map(l=>`<li><span>${esc(when(l.at))}</span><b>${esc(l.reason)}</b><strong class="${l.amount<0?'bad':'good'}">${l.amount>0?'+':''}${fmt(l.amount)}</strong></li>`).join('')}</ul>`:'<p class="fine">Nothing yet this season. Get in game: your first match of the day is worth 2.</p>'}</article></div>`;
    host.querySelectorAll('[data-w]').forEach(el=>{el.style.width=el.dataset.w+'%';});
    clearInterval(timer);timer=setInterval(()=>{const t=host.querySelector('.arm-timer');if(!t||location.hash!=='#armoury'){clearInterval(timer);return;}t.textContent=left(Number(t.dataset.until));if(Number(t.dataset.until)<=Date.now()/1000){clearInterval(timer);load();}},1000);
  }
  document.addEventListener('click',async e=>{if(e.target.closest('[data-armoury-refresh]')){load();return;}const b=e.target.closest('[data-arm-buy]');if(!b||busy)return;
    const item=arm.items.find(i=>i.id===b.dataset.armBuy);if(!item)return;
    if(!await confirmAction(`Use the ${item.name}?`,`Spend ${item.cost} of your ${arm.balance} Merits. ${item.detail} This is your one Armoury item for today.`))return;
    if(demo){notify('Preview only: no Merits spent.');return;}
    busy=true;b.disabled=true;try{const r=await api('/api/merits',{item:item.id,confirm:true});arm=r;render();notify(r.message);}catch(err){notify(err.message);}finally{busy=false;}});
  const before=window.hqRender;window.hqRender=function(){before?.();if(location.hash==='#armoury')load();};
  window.addEventListener('hashchange',()=>{if(location.hash==='#armoury')load();});
})();
