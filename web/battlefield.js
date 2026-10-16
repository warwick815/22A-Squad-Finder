'use strict';
const emberButton=document.getElementById('atmosphere-toggle');
if(emberButton){const reduced=matchMedia('(prefers-reduced-motion: reduce)');let paused=false;try{paused=localStorage.getItem('22a-atmosphere-paused')==='1';}catch{}
const update=()=>{document.body.classList.toggle('embers-paused',paused||document.hidden||reduced.matches);emberButton.disabled=reduced.matches;emberButton.textContent=reduced.matches?'Motion reduced':paused?'Resume atmosphere':'Pause atmosphere';emberButton.setAttribute('aria-pressed',String(paused||reduced.matches));};
update();emberButton.addEventListener('click',()=>{paused=!paused;try{localStorage.setItem('22a-atmosphere-paused',paused?'1':'0');}catch{}update();});reduced.addEventListener('change',update);document.addEventListener('visibilitychange',update);}
