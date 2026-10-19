'use strict';
window.PairedPlayback=(()=>{
 const players=new Map();
 function mount(root){
  root.querySelectorAll('[data-paired-player]').forEach(el=>{
   const videos=[...el.querySelectorAll('[data-pair-video]')],toggle=el.querySelector('[data-pair-toggle]'),replay=el.querySelector('[data-pair-replay]'),seek=el.querySelector('[data-pair-seek]'),time=el.querySelector('[data-pair-time]');
   let master=videos[0],duration=Number(seek.max),frame=0,playing=false,disposed=false,generation=0;
   const listeners=[];
   function on(target,event,fn){target.addEventListener(event,fn);listeners.push(()=>target.removeEventListener(event,fn));}
   function update(){const t=Math.min(duration,master.currentTime||0);seek.value=t;time.textContent=`${t.toFixed(1)} / ${duration.toFixed(1)} s`;toggle.textContent=playing?'Pause both':'Play both';toggle.setAttribute('aria-label',toggle.textContent);}
   function pause(){generation++;playing=false;cancelAnimationFrame(frame);videos.forEach(v=>v.pause());update();}
   function align(t){videos.forEach(v=>{if(v.readyState>0){const target=Math.min(t,Math.max(0,v.duration-.001));if(Math.abs(v.currentTime-target)>.12)v.currentTime=target;}});}
   function tick(){if(!playing||disposed)return;const t=master.currentTime;videos.forEach(v=>{if(v===master||v.readyState===0)return;const target=Math.min(t,Math.max(0,v.duration-.001));if(Math.abs(v.currentTime-target)>.12)v.currentTime=target;});update();frame=requestAnimationFrame(tick);}
   async function play(){
    if(playing||disposed)return;
    if(master.ended||master.currentTime>=duration-.03){videos.forEach(v=>{if(v.readyState>0)v.currentTime=0;});seek.value=0;}
    const ticket=++generation;playing=true;update();
    try{await Promise.all(videos.filter(v=>!Number.isFinite(v.duration)||master.currentTime<v.duration-.03).map(v=>v.play()));if(disposed||!playing||ticket!==generation)return;frame=requestAnimationFrame(tick);}catch{if(ticket===generation){pause();toggle.textContent='Retry playback';}}
   }
   function metadata(){if(videos.every(v=>Number.isFinite(v.duration))){master=videos.reduce((a,b)=>a.duration>=b.duration?a:b);duration=master.duration;seek.max=duration;update();}}
   videos.forEach(v=>{
    on(v,'loadedmetadata',metadata);
    on(v,'ended',()=>{if(v===master)pause();});
    on(v,'error',()=>{pause();toggle.textContent='Video unavailable';});
   });
   on(toggle,'click',()=>playing?pause():play());
   on(replay,'click',()=>{pause();videos.forEach(v=>{if(v.readyState>0)v.currentTime=0;});update();play();});
   on(seek,'input',()=>{const t=Number(seek.value);align(t);if(master.readyState>0)master.currentTime=Math.min(t,master.duration);if(playing)videos.forEach(v=>{if(t<v.duration-.03&&v.paused)v.play().catch(()=>pause());});update();});
   players.set(el,{pause,dispose(){disposed=true;pause();listeners.forEach(fn=>fn());videos.forEach(v=>{v.removeAttribute('src');v.load();});}});
   metadata();update();
  });
 }
 function dispose(root){for(const [el,player] of players)if(root.contains(el)){player.dispose();players.delete(el);}}
 return {mount,dispose,pauseAll(){players.forEach(p=>p.pause());}};
})();
