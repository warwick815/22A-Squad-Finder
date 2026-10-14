'use strict';
const radarButton=document.getElementById('radar-toggle');
if(radarButton){const hero=radarButton.closest('.crest-hero');let paused=matchMedia('(prefers-reduced-motion: reduce)').matches;const update=()=>{hero.classList.toggle('radar-paused',paused);radarButton.textContent=paused?'Resume radar':'Pause radar';radarButton.setAttribute('aria-pressed',String(paused));};update();radarButton.addEventListener('click',()=>{paused=!paused;update();});}
