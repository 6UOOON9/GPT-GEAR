'use strict';
const media=(window.MEDIA||[]).filter(m=>m.group!=='libero-geomotion'||m.geoFeatured);
const $=s=>document.querySelector(s);
const escapeHTML=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const groupNames={real_world:'Real robot',analysis:'Capability analysis',ablation:'Ablation', 'libero-geomotion':'LIBERO-GeoMotion'};
const geoTasks=window.GEOMOTION_TASKS||[];
const geoTaskById=Object.fromEntries(geoTasks.map(t=>[t.id,t]));
const categoryNames={generalization:'Generalization',memory:'Memory',precision:'Precision','task_understanding':'Task understanding','long-horizon':'Long-horizon','high-order operation':'High-order operations'};
function titleFor(m){if(m.geoTask)return m.title;const s=m.source.toLowerCase();if(m.group==='real_world'){if(s.includes('mango'))return 'Constrained mango grasping';if(s.includes('insertion'))return 'Block-in-cup insertion';if(s.includes('pouring'))return 'Pouring into a drawer';if(s.includes('shelf'))return 'Shelf rearrangement';}if(m.group==='libero-geomotion'){if(s.includes('bar'))return 'Pass an elongated object through a narrow opening';if(s.includes('book'))return 'Place a book into a narrow slot';if(s.includes('mango'))return 'Grasp a mango beside an obstacle';if(s.includes('pudding'))return 'Store a package in a drawer';}return m.title;}
function detailFor(m){if(m.geoTask)return geoTaskById[m.geoTask]?.name||'LIBERO-GeoMotion';if(m.group==='real_world')return 'ROKAE HELIOS';if(m.group==='analysis')return categoryNames[m.category]||m.category;return groupNames[m.group];}
function card(m){return `<article class="video-card"><button class="video-thumb" data-play="${m.id}" aria-label="Play ${escapeHTML(titleFor(m))}, ${m.condition?(m.condition==='icl'?'with ICL':'without ICL'):m.outcome}"><img src="${m.poster}" alt="${escapeHTML(titleFor(m))}" loading="lazy" width="640" height="360"><span class="video-badge ${m.outcome}">${m.condition?(m.condition==='icl'?'WITH ICL':'WITHOUT ICL'):m.outcome==='reference'?'REFERENCE DEMO':m.outcome==='success'?'✓ SUCCESS':m.outcome==='failure'?'× FAILURE':'MODEL EXECUTION'}</span><span class="play-circle" aria-hidden="true">▷</span></button><div class="video-info"><h4>${escapeHTML(titleFor(m))}</h4><p><span>${escapeHTML(detailFor(m))}</span><span>${Math.floor(m.duration/60)}:${String(Math.floor(m.duration%60)).padStart(2,'0')}</span></p></div></article>`;}
const featuredSources=['real_world/mango_grasping_03_success_20x.mp4','real_world/Block-in-cup_insertion_04_success_20x.mp4','real_world/pouring_into_a_drawer_success_20x.mp4','real_world/shelf_exchange_02_success_20x.mp4'];
const featured=featuredSources.map(s=>media.find(m=>m.source===s)).filter(Boolean);
$('#hero-strip').innerHTML=featured.map((m,i)=>`<button class="hero-tile" data-play="${m.id}" aria-label="Play ${escapeHTML(titleFor(m))}"><img src="${m.poster}" alt="${escapeHTML(titleFor(m))}" width="640" height="400"><span class="play-circle" aria-hidden="true">▷</span><span class="tile-caption">${['Mango grasping','Precise insertion','Pouring into a drawer','Shelf rearrangement'][i]}<span class="tile-num">0${i+1} ↗</span></span></button>`).join('');
const benchmarks=[['LIBERO-Plus',83.5,40,10],['RoboTwin 2.0',76,50,10],['UniVTAC',72.5,8,20],['RoboDojo',26.92,42,10],['RoboCasa GR1',18.96,24,20]];
$('#benchmark-chart').innerHTML=benchmarks.map(([name,rate,tasks,trials])=>`<div class="benchmark-column" data-rate-group aria-label="${name}: ${rate}% success"><div class="benchmark-stage"><span class="axis-top">100%</span><div class="benchmark-bar" data-rate-fill="${rate}" style="height:0%"><strong><b data-rate-count="${rate.toFixed(rate===26.92||rate===18.96?2:1)}">0</b><small>%</small></strong></div><span class="axis-zero">0</span></div><div class="benchmark-name">${name}<small>${tasks} tasks × ${trials} trials</small></div></div>`).join('');
SuccessMotion.observe($('#benchmark-chart'));
const realTasks=[['Pick-and-place',100,100],['Mango grasping',0,60],['Block-in-cup insertion',40,80],['Pouring into a drawer',40,100],['Shelf rearrangement',20,60]];
function renderRealChart(mode='both'){
 SuccessMotion.dispose($('#real-chart'));
 $('#real-chart').innerHTML=realTasks.map(([task,z,i])=>`<div class="task-item" data-rate-group><div class="task-bars">${mode!=='icl'?`<div class="task-bar zero" data-rate-fill="${z}" style="height:0%" aria-label="Zero-shot ${z}%"><span><b data-rate-count="${z}">0</b>%</span></div>`:''}${mode!=='zero'?`<div class="task-bar icl" data-rate-fill="${i}" style="height:0%" aria-label="One-example ICL ${i}%"><span><b data-rate-count="${i}">0</b>%</span></div>`:''}<span class="axis-zero">0</span></div><p class="task-label">${task}</p><p class="task-count">${mode==='both'?`${z/20}/5 → ${i/20}/5 successes`:`${(mode==='zero'?z:i)/20}/5 successes`}</p></div>`).join('');
 SuccessMotion.observe($('#real-chart'));
}
renderRealChart();
document.querySelectorAll('[data-condition]').forEach(b=>b.addEventListener('click',()=>{document.querySelectorAll('[data-condition]').forEach(x=>{x.classList.toggle('active',x===b);x.setAttribute('aria-pressed',String(x===b));});renderRealChart(b.dataset.condition);}));
const realMedia=media.filter(m=>m.group==='real_world').sort((a,b)=>(a.outcome==='success'?0:1)-(b.outcome==='success'?0:1)||a.source.localeCompare(b.source));
let realOutcome='all';
function realTaskFor(m){const name=m.source.toLowerCase();if(name.includes('insertion'))return 'insertion';if(name.includes('mango'))return 'mango';if(name.includes('pouring'))return 'pouring';if(name.includes('shelf'))return 'shelf';return 'other';}
function renderReal(){
 const task=$('#real-task').value;
 const taskMedia=realMedia.filter(m=>task==='all'||realTaskFor(m)===task);
 const filtered=taskMedia.filter(m=>realOutcome==='all'||m.outcome===realOutcome);
 $('#real-videos').innerHTML=filtered.length?filtered.map(card).join(''):'<p class="empty">No videos for this task and outcome.</p>';
 $('#real-filters [data-real="all"] span').textContent=taskMedia.length;
}
renderReal();
$('#real-task').addEventListener('change',renderReal);
document.querySelectorAll('[data-real]').forEach(b=>b.addEventListener('click',()=>{realOutcome=b.dataset.real;document.querySelectorAll('[data-real]').forEach(x=>{x.classList.toggle('active',x===b);x.setAttribute('aria-pressed',String(x===b));});renderReal();}));
let geoTask=geoTasks[0].id;
const geoOptions=geoTasks.map(t=>`<option value="${t.id}">${escapeHTML(t.name)}</option>`).join('');
$('#geo-task').innerHTML=geoOptions;

const geoOrder=(a,b)=>(a.outcome==='reference'?0:1)-(b.outcome==='reference'?0:1);
function geoGallery(items){
 const refs=items.filter(m=>m.outcome==='reference').slice(0,2);
 const runs=items.filter(m=>m.condition).sort((a,b)=>(a.condition==='no_icl'?0:1)-(b.condition==='no_icl'?0:1));
 return (refs.length?`<section class="geo-video-group"><h3>Reference demonstrations</h3><div class="video-grid geo-pair">${refs.map(card).join('')}</div></section>`:'')+(runs.length?`<section class="geo-video-group geo-comparison"><h3>Without ICL / With ICL</h3><div class="video-grid geo-pair">${runs.map(card).join('')}</div></section>`:'');
}
function renderGeoTask(){
 const task=geoTaskById[geoTask];
 $('#geo-task').value=geoTask;
 $('#geo-videos').innerHTML=geoGallery(media.filter(m=>m.geoTask===geoTask));
 $('#geo-task-title').textContent=task.name;
 $('#geo-task-description').textContent=task.description;
 $('#geo-task-source').textContent=`Paper §6.1 · Figure 16(${task.panel}) ↗`;
}
renderGeoTask();
let limit=12;
const abilityCategory=$('#ability-category');
const tactilePairs=[
 {name:'Place a bottle on the shelf',rgb:'2ecc7d355189',tactile:'f50136ef2812',baseline:'678a8c9c66be'},
 {name:'Insert HDMI',rgb:'fbc8503a6725',tactile:'86d5137afd46',baseline:'624420b6a32b'}
];
function tactileCard(pair){
 const rgb=media.find(m=>m.id===pair.rgb),tactile=media.find(m=>m.id===pair.tactile);
 const unequal=Math.abs(rgb.duration-tactile.duration)>.1;
 return `<article class="tactile-demo" data-paired-player><div class="tactile-heading"><h3>${escapeHTML(pair.name)}</h3><button class="text-link" data-play="${pair.baseline}">RGB-only baseline ↗</button></div><div class="paired-views"><figure><figcaption>Robot view</figcaption><video data-pair-video muted playsinline preload="metadata" src="${rgb.video}" poster="${rgb.poster}" aria-label="${escapeHTML(pair.name)} robot view"></video></figure><figure><figcaption>Tactile view</figcaption><video data-pair-video muted playsinline preload="metadata" src="${tactile.video}" poster="${tactile.poster}" aria-label="${escapeHTML(pair.name)} tactile view"></video></figure></div><div class="paired-controls"><button data-pair-toggle aria-label="Play both videos">Play both</button><button data-pair-replay aria-label="Replay both videos">Replay</button><input data-pair-seek type="range" min="0" max="${Math.max(rgb.duration,tactile.duration)}" value="0" step="0.01" aria-label="${escapeHTML(pair.name)} shared timeline"><output data-pair-time>0.0 / ${Math.max(rgb.duration,tactile.duration).toFixed(1)} s</output></div>${unequal?'<p class="pair-timing-note">Different recording lengths: RGB 1.95 s, tactile 13.35 s. Shared playback; the shorter video holds its final frame.</p>':''}</article>`;
}
function renderLibrary(){
 PairedPlayback.dispose($('#library-videos'));
 const query=$('#search').value.trim().toLowerCase(),tactile=abilityCategory.value==='tactile_understanding';
 $('#library-videos').classList.toggle('tactile-library',tactile);
 if(tactile){
  const pairs=tactilePairs.filter(p=>p.name.toLowerCase().includes(query));
  $('#library-videos').innerHTML=pairs.length?pairs.map(tactileCard).join(''):'<p class="empty">No matching demos.</p>';
  $('#load-more').hidden=true;PairedPlayback.mount($('#library-videos'));return;
 }
 const filtered=media.filter(m=>m.group==='analysis'&&m.category===abilityCategory.value&&`${titleFor(m)} ${m.source}`.toLowerCase().includes(query));
 $('#library-videos').innerHTML=filtered.length?filtered.slice(0,limit).map(card).join(''):'<p class="empty">No matching demos.</p>';
 $('#load-more').hidden=limit>=filtered.length;
}
$('#geo-task').addEventListener('change',()=>{geoTask=$('#geo-task').value;renderGeoTask();});
abilityCategory.addEventListener('change',()=>{limit=12;$('#search').value='';renderLibrary();});
$('#search').addEventListener('input',()=>{limit=12;renderLibrary();});
$('#load-more').addEventListener('click',()=>{limit+=12;renderLibrary();});
document.querySelectorAll('[data-ability-jump]').forEach(a=>a.addEventListener('click',()=>{abilityCategory.value=a.dataset.abilityJump;$('#search').value='';limit=12;renderLibrary();}));
renderLibrary();
const dialog=$('#video-dialog'),video=$('#dialog-video');let previousTrigger=null;
document.addEventListener('click',e=>{const trigger=e.target.closest('[data-play]');if(!trigger)return;const m=media.find(x=>x.id===trigger.dataset.play);if(!m)return;previousTrigger=trigger;PairedPlayback.pauseAll();$('#dialog-title').textContent=titleFor(m);$('#dialog-meta').textContent=`${detailFor(m)} · ${m.condition?(m.condition==='icl'?'With ICL':'Without ICL'):m.outcome} · ${m.speed}`;$('#dialog-caption').textContent=m.condition?`${m.condition==='icl'?'With ICL':'Without ICL'} execution of the same scene variant shown in the paired comparison. Playback preserves the supplied recording.`:m.outcome==='reference'?'Reference demonstration supplied for LIBERO-GeoMotion. This clip is not labelled as a GPT-6 Astra evaluation rollout. Playback preserves the supplied recording.':m.group==='real_world'?'Recorded real-robot execution. The supplied clip is sped up 20×. Evaluation condition is not specified in the source filename.':`Source: ${m.source}. Playback preserves the supplied recording; no additional speed change is applied.`;video.src=m.video;video.poster=m.poster;dialog.showModal();document.body.style.overflow='hidden';video.play().catch(()=>{});});
function closeVideo(){dialog.close();}
$('#close-dialog').addEventListener('click',closeVideo);
dialog.addEventListener('click',e=>{if(e.target===dialog){const r=dialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)closeVideo();}});
dialog.addEventListener('close',()=>{video.pause();video.removeAttribute('src');video.load();document.body.style.overflow='';previousTrigger?.focus();});
$('#copy-citation').addEventListener('click',async()=>{try{await navigator.clipboard.writeText($('#bibtex').textContent);$('#copy-status').textContent='Citation copied.';}catch{$('#copy-status').textContent='Select and copy the citation above.';const r=document.createRange();r.selectNodeContents($('#bibtex'));const s=window.getSelection();s.removeAllRanges();s.addRange(r);}});
