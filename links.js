// Published paper, code repository, and dataset.
window.PROJECT_LINKS = {
  arxiv: "https://arxiv.org/abs/2610.28259",
  code: "https://github.com/6UOOON9/GPT-GEAR",
  dataset: "https://huggingface.co/datasets/uooon/LIBERO-GeoMotion"
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
    link.title = { arxiv: 'Read on arXiv', code: 'View code on GitHub', dataset: 'View LIBERO-GeoMotion on Hugging Face' }[link.dataset.projectLink];
  } catch { /* Leave the placeholder inactive until a valid URL is provided. */ }
});
