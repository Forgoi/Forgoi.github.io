'use strict';
document.documentElement.classList.add('js');
for (const button of document.querySelectorAll('.copy-code')) {
  button.addEventListener('click', async () => {
    const code = button.closest('.code-block').querySelector('code').textContent;
    try {
      await navigator.clipboard.writeText(code);
      button.textContent = '已复制';
    } catch {
      button.textContent = '请手动选择复制';
    }
    window.setTimeout(() => { button.textContent = '复制'; }, 2200);
  });
}
const search = document.querySelector('#archive-search');
if (search) {
  const items = [...document.querySelectorAll('[data-search]')];
  const count = document.querySelector('#archive-count');
  const empty = document.querySelector('#empty-result');
  search.addEventListener('input', () => {
    const query = search.value.trim().toLocaleLowerCase();
    let visible = 0;
    for (const item of items) {
      item.hidden = !item.dataset.search.toLocaleLowerCase().includes(query);
      if (!item.hidden) visible++;
    }
    count.textContent = `${visible} 篇文章`;
    empty.hidden = visible !== 0;
  });
}

// A missing/blocked counter stays hidden. Never substitute a fabricated count.
const viewCount = document.querySelector('#busuanzi_value_page_pv');
const views = document.querySelector('#article-views');
if (viewCount && views) {
  const updateViews = () => {
    views.hidden = !/^\d+$/.test(viewCount.textContent.trim());
  };
  new MutationObserver(updateViews).observe(viewCount, {childList: true, characterData: true, subtree: true});
  updateViews();
}
// Native details works without JavaScript; enhancement adds Escape and close.
const donation = document.querySelector('#donation-panel');
if (donation) {
  const close = donation.querySelector('.donation-close');
  const summary = donation.querySelector('summary');
  const dismiss = () => {
    donation.open = false;
    summary.focus({preventScroll: true});
    summary.scrollIntoView({block: 'nearest'});
  };
  close.hidden = false;
  close.addEventListener('click', dismiss);
  donation.addEventListener('keydown', event => {
    if (event.key === 'Escape' && donation.open) {
      event.preventDefault();
      dismiss();
    }
  });
}
