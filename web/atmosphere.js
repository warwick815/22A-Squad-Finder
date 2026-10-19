'use strict';
// Home-page radar and the battlefield backdrop's embers, both drawn on canvas.
// One "Pause motion" button stops both; reduced-motion users get still frames.
(function(){
  const reduced=matchMedia('(prefers-reduced-motion: reduce)');
  let paused=false;try{paused=localStorage.getItem('22a-motion-paused')==='1';}catch{}
  const still=()=>paused||reduced.matches||document.hidden;
  const loops=[];
  function loop(draw){let last=0,raf=0;const frame=t=>{raf=0;const dt=Math.min(.05,last?(t-last)/1000:0);last=t;draw(dt);if(!still())raf=requestAnimationFrame(frame);};
    const api={start(){if(!raf){last=0;raf=requestAnimationFrame(frame);}},once(){draw(0);}};loops.push(api);return api;}
  function sync(){const button=document.getElementById('motion-toggle');document.body.classList.toggle('motion-paused',still());
    if(button){button.textContent=reduced.matches?'Motion reduced':paused?'Resume motion':'Pause motion';button.disabled=reduced.matches;button.setAttribute('aria-pressed',String(paused||reduced.matches));}
    loops.forEach(l=>still()?l.once():l.start());}
  function fit(canvas){const r=canvas.getBoundingClientRect(),dpr=Math.min(2,window.devicePixelRatio||1),w=Math.max(1,Math.round(r.width*dpr)),h=Math.max(1,Math.round(r.height*dpr));
    if(canvas.width!==w||canvas.height!==h){canvas.width=w;canvas.height=h;}return {w,h,dpr};}

  // --- Radar ---------------------------------------------------------------
  function radar(canvas){
    const ctx=canvas.getContext('2d');if(!ctx)return;
    const TURN=4.5;                // seconds per sweep
    const kinds=[['hostile','#ff5a4f'],['hostile','#ff5a4f'],['hostile','#ff5a4f'],['friendly','#a6e35a'],['friendly','#a6e35a'],['unknown','#f2b84b'],['unknown','#f2b84b']];
    let sweep=Math.random()*Math.PI*2,serial=1;
    const spawn=(kind,colour,edge)=>{
      const a=Math.random()*Math.PI*2,d=edge?1.02:.25+Math.random()*.7,heading=edge?a+Math.PI+(Math.random()-.5)*1.2:Math.random()*Math.PI*2;
      return {kind,colour,x:Math.cos(a)*d,y:Math.sin(a)*d,vx:Math.cos(heading),vy:Math.sin(heading),speed:.012+Math.random()*.03,turn:(Math.random()-.5)*.25,id:String(serial++).padStart(3,'0'),paints:[]};};
    const tracks=kinds.map(([k,c])=>spawn(k,c,false));
    const bearing=(x,y)=>(Math.atan2(y,x)+Math.PI*2)%(Math.PI*2);
    return loop(dt=>{
      if(!canvas.offsetParent)return; // home page not showing
      const {w,h,dpr}=fit(canvas),R=Math.min(w,h)/2-8*dpr,cx=w/2,cy=h/2,prev=sweep;
      if(R<20)return;
      sweep=(sweep+dt*Math.PI*2/TURN)%(Math.PI*2);
      // Move contacts; anything leaving the scope is replaced by a new track at the edge.
      for(let i=0;i<tracks.length;i++){const t=tracks[i];
        const ang=Math.atan2(t.vy,t.vx)+t.turn*dt;t.vx=Math.cos(ang);t.vy=Math.sin(ang);
        t.x+=t.vx*t.speed*dt;t.y+=t.vy*t.speed*dt;
        if(Math.hypot(t.x,t.y)>1.05)tracks[i]=spawn(t.kind,t.colour,true);}
      // Paint contacts the beam crossed this frame.
      const crossed=b=>dt&&(prev<=sweep?b>prev&&b<=sweep:b>prev||b<=sweep);
      for(const t of tracks)if(crossed(bearing(t.x,t.y))||!t.paints.length&&!dt){t.paints.push({x:t.x,y:t.y,at:performance.now()});if(t.paints.length>5)t.paints.shift();}
      ctx.clearRect(0,0,w,h);
      ctx.save();ctx.beginPath();ctx.arc(cx,cy,R,0,Math.PI*2);ctx.clip();
      const bg=ctx.createRadialGradient(cx,cy,0,cx,cy,R);bg.addColorStop(0,'#0f2414f0');bg.addColorStop(1,'#060d08f5');ctx.fillStyle=bg;ctx.fillRect(0,0,w,h);
      // Grid: range rings, cross-hairs and bearing ticks.
      ctx.strokeStyle='#a6e35a33';ctx.lineWidth=dpr;
      for(let i=1;i<=4;i++){ctx.beginPath();ctx.arc(cx,cy,R*i/4,0,Math.PI*2);ctx.stroke();}
      ctx.beginPath();ctx.moveTo(cx-R,cy);ctx.lineTo(cx+R,cy);ctx.moveTo(cx,cy-R);ctx.lineTo(cx,cy+R);ctx.stroke();
      for(let d=0;d<360;d+=5){const a=d*Math.PI/180-Math.PI/2,inner=R-(d%30?5:11)*dpr;ctx.beginPath();ctx.moveTo(cx+Math.cos(a)*inner,cy+Math.sin(a)*inner);ctx.lineTo(cx+Math.cos(a)*R,cy+Math.sin(a)*R);ctx.stroke();}
      // Beam with a phosphor tail.
      const tail=Math.PI*.55,steps=40;
      for(let i=0;i<steps;i++){const a0=sweep-tail*(i+1)/steps,a1=sweep-tail*i/steps;ctx.beginPath();ctx.moveTo(cx,cy);ctx.arc(cx,cy,R,a0,a1+.01);ctx.closePath();ctx.fillStyle=`rgba(166,227,90,${(.22*(1-i/steps)**2).toFixed(3)})`;ctx.fill();}
      ctx.strokeStyle='#d7ff9e';ctx.lineWidth=2*dpr;ctx.shadowColor='#a6e35a';ctx.shadowBlur=12*dpr;ctx.beginPath();ctx.moveTo(cx,cy);ctx.lineTo(cx+Math.cos(sweep)*R,cy+Math.sin(sweep)*R);ctx.stroke();ctx.shadowBlur=0;
      // Contacts fade over one turn after being painted; older paints form a trail.
      const now=performance.now(),life=TURN*1000;
      ctx.font=`${10*dpr}px ui-monospace,Consolas,monospace`;
      for(const t of tracks){t.paints.forEach((p,i)=>{const age=(now-p.at)/life,fade=Math.max(0,1-age)*(i===t.paints.length-1?1:.35);if(fade<=0)return;
          const x=cx+p.x*R,y=cy+p.y*R,s=(i===t.paints.length-1?4.5:2.5)*dpr;
          ctx.globalAlpha=fade;ctx.fillStyle=t.colour;ctx.shadowColor=t.colour;ctx.shadowBlur=10*dpr;
          ctx.beginPath();if(t.kind==='hostile'){ctx.moveTo(x,y-s);ctx.lineTo(x+s,y);ctx.lineTo(x,y+s);ctx.lineTo(x-s,y);}else if(t.kind==='friendly'){ctx.arc(x,y,s,0,Math.PI*2);}else{ctx.rect(x-s*.8,y-s*.8,s*1.6,s*1.6);}ctx.fill();ctx.shadowBlur=0;
          if(i===t.paints.length-1&&fade>.35){ctx.fillStyle=t.colour;const label=`${t.kind[0].toUpperCase()}-${t.id}`,flip=x>cx+R*.45;ctx.textAlign=flip?'right':'left';ctx.fillText(label,x+(flip?-7:7)*dpr,y-5*dpr);ctx.textAlign='left';
            ctx.strokeStyle=t.colour;ctx.lineWidth=dpr;ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(x+t.vx*14*dpr,y+t.vy*14*dpr);ctx.stroke();}});}
      ctx.globalAlpha=1;ctx.restore();
      ctx.strokeStyle='#a6e35a80';ctx.lineWidth=2*dpr;ctx.beginPath();ctx.arc(cx,cy,R,0,Math.PI*2);ctx.stroke();
      ctx.fillStyle='#a6e35acc';ctx.font=`${9*dpr}px ui-monospace,Consolas,monospace`;ctx.textAlign='center';
      for(const [d,l] of [[0,'000'],[90,'090'],[180,'180'],[270,'270']]){const a=d*Math.PI/180-Math.PI/2,r=R-20*dpr;ctx.fillText(l,cx+Math.cos(a)*r,cy+Math.sin(a)*r+3*dpr);}
      ctx.textAlign='start';
      const read=document.getElementById('radar-readout');
      if(read&&(!dt||Math.floor(now/500)!==Math.floor((now-dt*1000)/500))){const bearingDeg=Math.round(((sweep+Math.PI/2)*180/Math.PI+360)%360);
        read.textContent=`BRG ${String(bearingDeg).padStart(3,'0')}° · TRK ${tracks.length} · HOSTILE ${tracks.filter(t=>t.kind==='hostile').length}`;}
    });
  }

  // --- Embers over the battlefield backdrop -----------------------------------
  function embers(canvas){
    const ctx=canvas.getContext('2d');if(!ctx)return;
    const make=(fresh)=>{const left=Math.random()<.5;return {x:left?Math.random()*.3:.7+Math.random()*.3,y:fresh?1.02:Math.random(),vy:.02+Math.random()*.035,drift:(Math.random()-.5)*.02,wob:Math.random()*6,size:.6+Math.random()*1.8,life:.5+Math.random()*.5};};
    let parts=[];
    return loop(dt=>{
      const {w,h,dpr}=fit(canvas),want=w<700*dpr?26:60;
      while(parts.length<want)parts.push(make(false));if(parts.length>want)parts.length=want;
      ctx.clearRect(0,0,w,h);ctx.globalCompositeOperation='lighter';
      for(let i=0;i<parts.length;i++){const p=parts[i];
        p.y-=p.vy*dt;p.wob+=dt*1.5;p.x+=(p.drift+Math.sin(p.wob)*.006)*dt;
        if(p.y<-.05)parts[i]=make(true);
        const fade=Math.min(1,(1.02-p.y)*4)*Math.min(1,p.y*1.6)*p.life,flick=.75+.25*Math.sin(p.wob*5),x=p.x*w,y=p.y*h,s=p.size*dpr;
        const g=ctx.createRadialGradient(x,y,0,x,y,s*5);g.addColorStop(0,`rgba(255,214,150,${(.95*fade*flick).toFixed(3)})`);g.addColorStop(.25,`rgba(250,120,45,${(.45*fade*flick).toFixed(3)})`);g.addColorStop(1,'rgba(250,90,30,0)');
        ctx.fillStyle=g;ctx.fillRect(x-s*5,y-s*5,s*10,s*10);}
      ctx.globalCompositeOperation='source-over';
    });
  }

  function init(){
    const scope=document.getElementById('radar-scope');if(scope)radar(scope);
    const ember=document.getElementById('ember-canvas');if(ember)embers(ember);
    document.getElementById('motion-toggle')?.addEventListener('click',()=>{paused=!paused;try{localStorage.setItem('22a-motion-paused',paused?'1':'0');}catch{}sync();});
    reduced.addEventListener('change',sync);document.addEventListener('visibilitychange',sync);
    let resize=0;window.addEventListener('resize',()=>{cancelAnimationFrame(resize);resize=requestAnimationFrame(()=>{if(still())loops.forEach(l=>l.once());});});
    sync();
  }
  document.readyState==='loading'?document.addEventListener('DOMContentLoaded',init):init();
})();
