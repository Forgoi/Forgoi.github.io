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
