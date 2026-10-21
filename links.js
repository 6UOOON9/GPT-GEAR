// Published paper and code repository.
window.PROJECT_LINKS = {
  arxiv: "https://arxiv.org/abs/2610.28259",
  code: "https://github.com/6UOOON9/GPT-GEAR"
};

document.querySelectorAll('[data-project-link]').forEach(link => {
  const url = window.PROJECT_LINKS[link.dataset.projectLink]?.trim();
  if (!url) return;
  try {
    const parsed = new URL(url);
    if (parsed.protocol !== 'https:' && parsed.protocol !== 'http:') return;
    link.href = parsed.href;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.removeAttribute('aria-disabled');
    link.removeAttribute('tabindex');
    link.title = link.dataset.projectLink === 'arxiv' ? 'Read on arXiv' : 'View code on GitHub';
  } catch { /* Leave the placeholder inactive until a valid URL is provided. */ }
});
