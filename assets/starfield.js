/* Replay is visual history only. It never changes saved learning progress. */
(() => {
  const universe = document.querySelector('.universe');
  const replay = document.querySelector('#replay-stars');
  const status = document.querySelector('#replay-status');
  if (!universe || !replay || !status) return;
  replay.hidden = false;
  let timer;
  replay.addEventListener('click', () => {
    clearTimeout(timer);
    universe.classList.remove('is-replaying');
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      status.textContent = '已显示所有完成记录。已按减少动态效果设置跳过动画；学习进度没有改变。';
      return;
    }
    void universe.offsetWidth;
    universe.classList.add('is-replaying');
    status.textContent = '正在重放已完成记录的点亮过程，学习进度没有改变。';
    timer = setTimeout(() => {
      universe.classList.remove('is-replaying');
      status.textContent = '点亮过程重放完毕。' + universe.querySelectorAll('.is-lit').length + ' 篇完成记录已显示，正在探索的主题仍未点亮。';
    }, 4200);
  });
})();
