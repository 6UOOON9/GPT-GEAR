'use strict';
/* Every success metric starts at zero and grows vertically on viewport entry. */
window.SuccessMotion = (() => {
  const states = new WeakMap();
  const triggerGroups = new WeakMap();
  const groupTriggers = new WeakMap();
  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
  function paint(group, progress) {
    group.dataset.animationProgress = progress.toFixed(4);
    group.querySelectorAll('[data-rate-fill]').forEach(bar => {
      bar.style.height = `${Number(bar.dataset.rateFill) * progress}%`;
      bar.style.opacity = '1';
    });
    group.querySelectorAll('[data-rate-count]').forEach(counter => {
      const raw = counter.dataset.rateCount;
      const digits = raw.includes('.') ? raw.split('.')[1].length : 0;
      counter.textContent = progress === 0 ? '0' : (Number(raw) * progress).toFixed(digits);
    });
  }
  function reset(group) {
    const state = states.get(group);
    if (state) cancelAnimationFrame(state.frame);
    states.set(group, { frame: 0, started: false });
    group.dataset.animationState = 'waiting';
    paint(group, 0);
  }
  function start(group) {
    const state = states.get(group);
    if (!state || state.started) return;
    state.started = true;
    group.dataset.animationState = 'growing';
    const duration = reducedMotion.matches ? 180 : 1900;
    // A short zero hold makes the baseline visible before growth begins.
    const begin = performance.now() + 140;
    const frame = now => {
      if (!group.isConnected) return;
      const t = Math.min(1, Math.max(0, (now - begin) / duration));
      const eased = t * t * (3 - 2 * t);
      paint(group, eased);
      if (t < 1) state.frame = requestAnimationFrame(frame);
      else group.dataset.animationState = 'complete';
    };
    state.frame = requestAnimationFrame(frame);
  }
  const observer = new IntersectionObserver(entries => {
    for (const entry of entries) {
      const group = triggerGroups.get(entry.target);
      if (!group) continue;
      if (entry.isIntersecting && entry.intersectionRatio >= .25) start(group);
      else if (!entry.isIntersecting) reset(group);
    }
  }, { threshold: [0, .25], rootMargin: '-72px 0px -24px 0px' });
  function observe(root) {
    root.querySelectorAll('[data-rate-group]').forEach(group => {
      if (states.has(group)) return;
      reset(group);
      const trigger = group.querySelector('.rate-column, .benchmark-stage, .task-bars') || group;
      triggerGroups.set(trigger, group);
      groupTriggers.set(group, trigger);
      observer.observe(trigger);
    });
  }
  function dispose(root) {
    root.querySelectorAll('[data-rate-group]').forEach(group => {
      const trigger = groupTriggers.get(group);
      if (trigger) { observer.unobserve(trigger); triggerGroups.delete(trigger); }
      groupTriggers.delete(group);
      const state = states.get(group);
      if (state) cancelAnimationFrame(state.frame);
      states.delete(group);
    });
  }
  function column(target, extra='') {
    return `<div class="rate-column ${extra}" aria-hidden="true"><span class="axis-top">100%</span><div class="rate-fill" data-rate-fill="${target}" style="height:0%"></div><span class="axis-zero">0</span></div>`;
  }
  document.querySelectorAll('.stat-card').forEach(card => {
    const counter = card.querySelector('[data-rate-count]');
    card.dataset.rateGroup = '';
    card.setAttribute('aria-label', `${card.querySelector('.stat-label').textContent}: ${counter.dataset.rateCount}% success`);
    card.querySelector('.stat-number').insertAdjacentHTML('afterend', column(counter.dataset.rateCount));
  });
  document.querySelectorAll('.mini-result').forEach(result => {
    result.dataset.rateGroup = '';
    const counters = result.querySelectorAll('[data-rate-count]');
    result.insertAdjacentHTML('beforeend', column(counters[0].dataset.rateCount,'before') + column(counters[1].dataset.rateCount,'after'));
  });
  document.querySelectorAll('.success-comparison > div, .geo-summary > div').forEach(metric => {
    const counter = metric.querySelector('[data-rate-count]');
    if (!counter) return;
    metric.dataset.rateGroup = '';
    counter.parentElement.insertAdjacentHTML('afterend', column(counter.dataset.rateCount));
  });
  observe(document);
  return { observe, dispose };
})();
