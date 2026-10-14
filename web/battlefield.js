'use strict';
const emberButton=document.getElementById('atmosphere-toggle');
if(emberButton){let paused=matchMedia('(prefers-reduced-motion: reduce)').matches;const update=()=>{document.body.classList.toggle('embers-paused',paused);emberButton.textContent=paused?'Resume embers':'Pause embers';emberButton.setAttribute('aria-pressed',String(paused));};update();emberButton.addEventListener('click',()=>{paused=!paused;update();});}
