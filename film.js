'use strict';
(() => {
  const film = document.querySelector('#film');
  const video = document.querySelector('#opening-video');
  const toggle = document.querySelector('#film-toggle');
  const start = document.querySelector('#film-start');
  const progress = document.querySelector('#film-progress-fill');
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  const opensWithIntro = !reduced.matches && (!location.hash || location.hash === '#film');
  if (opensWithIntro) {
    history.scrollRestoration = 'manual';
    window.addEventListener('pageshow', () => window.scrollTo({top:0,behavior:'instant'}), {once:true});
  }
  let shouldPlay = !reduced.matches;
  let visible = true;
  const intro = document.querySelector('#brand-intro');
  let introActive = false;
  let revealTimer;
  let finishTimer;
  function finishIntro() {
    clearTimeout(revealTimer);
    clearTimeout(finishTimer);
    introActive = false;
    intro.hidden = true;
    film.classList.remove('intro-running');
    if (intro.contains(document.activeElement)) toggle.focus({preventScroll:true});
    play();
  }
  function startIntro() {
    clearTimeout(revealTimer);
    clearTimeout(finishTimer);
    if (reduced.matches) { finishIntro(); return; }
    introActive = true;
    video.pause();
    video.currentTime = 0;
    intro.hidden = false;
    film.classList.remove('intro-running');
    void intro.offsetWidth;
    film.classList.add('intro-running');
    document.querySelector('#intro-skip').focus({preventScroll:true});
    requestAnimationFrame(() => window.scrollTo({top:film.offsetTop,behavior:'instant'}));
    revealTimer = setTimeout(() => { introActive = false; play(); }, 3350);
    finishTimer = setTimeout(finishIntro, 4650);
  }
  document.querySelector('#intro-skip').addEventListener('click', finishIntro);
  window.addEventListener('hashchange', () => {
    if (location.hash && location.hash !== '#film') finishIntro();
  });
  reduced.addEventListener('change', () => {
    if (reduced.matches) { shouldPlay = false; finishIntro(); video.pause(); }
  });
  function syncControls() {
    toggle.textContent = video.paused ? '▷' : 'Ⅱ';
    toggle.setAttribute('aria-label', video.paused ? 'Play opening film' : 'Pause opening film');
    toggle.title = video.paused ? 'Play' : 'Pause';
    start.hidden = !video.paused;
  }
  async function play() {
    if (introActive || !visible || document.hidden || !shouldPlay) return;
    try { await video.play(); } catch { syncControls(); }
  }
  function updateTime() {
    const duration = Number.isFinite(video.duration) ? video.duration : 20.13;
    progress.style.width = `${duration ? video.currentTime / duration * 100 : 0}%`;
  }
  video.addEventListener('timeupdate', updateTime);
  video.addEventListener('loadedmetadata', updateTime);
  video.addEventListener('play', syncControls);
  video.addEventListener('pause', syncControls);
  video.addEventListener('error', () => {
    document.querySelector('#film-status').textContent = 'The film could not load. You can still scroll to the paper and explore the demos below.';
    syncControls();
  });
  toggle.addEventListener('click', () => {
    shouldPlay = video.paused;
    if (shouldPlay) play(); else video.pause();
  });
  start.addEventListener('click', () => { shouldPlay = true; play(); });
  document.querySelector('#film-replay').addEventListener('click', () => {
    film.scrollIntoView({behavior:'instant',block:'start'});
    video.currentTime = 0;
    shouldPlay = true;
    startIntro();
  });
  document.querySelector('#film-fullscreen').addEventListener('click', async () => {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else if (document.querySelector('#film-stage').requestFullscreen) await document.querySelector('#film-stage').requestFullscreen();
      else if (video.webkitEnterFullscreen) video.webkitEnterFullscreen();
      else document.querySelector('#film-status').textContent = 'Fullscreen is not available in this browser.';
    } catch { document.querySelector('#film-status').textContent = 'Fullscreen is not available in this browser.'; }
  });
  new IntersectionObserver(([entry]) => {
    visible = entry.isIntersecting;
    if (visible) play(); else video.pause();
  }, { threshold: 0 }).observe(document.querySelector('#film-stage'));
  document.addEventListener('visibilitychange', () => { if (document.hidden) video.pause(); else play(); });
  if (reduced.matches) video.pause();
  else if (!location.hash || location.hash === '#film') startIntro();
  else play();
  syncControls();
})();
