// Optional browser regression tests: node scripts/test_features.cjs
// Requires Playwright and a local server on 8765; never opens a payment URL.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
(async () => {
  const browser = await chromium.launch({headless:true, executablePath:process.env.CHROMIUM_PATH || '/usr/bin/chromium', args:['--no-sandbox']});
  const url = 'http://127.0.0.1:8765/2026/10/19/unity-ecs-cache-archetype-chunk/';
  for (const width of [1280, 390, 320]) {
    const page = await browser.newPage({viewport:{width,height:900}});
    const requests = [];
    page.on('request', request => { if (!request.url().startsWith('http://127.0.0.1:8765')) requests.push(request.url()); });
    await page.route('https://busuanzi.ibruce.info/**', route=>route.abort());
    await page.goto(url);
    assert.equal(await page.locator('#article-views').isVisible(), false);
    assert.equal(await page.locator('#busuanzi_value_page_pv').textContent(), '');
    const summary = page.locator('.donation-panel>summary');
    await summary.click();
    assert.equal(await page.locator('.donation-content').isVisible(), true);
    for (const image of await page.locator('.donation-codes img').all()) {
      await image.scrollIntoViewIfNeeded();
      await image.evaluate(img=>img.decode());
      assert.ok(await image.evaluate(img=>img.naturalWidth>1000));
    }
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth), `${width}px horizontal overflow`);
    await page.locator('.donation-close').click();
    assert.equal(await page.locator('.donation-content').isVisible(), false);
    assert.equal(await summary.evaluate(el=>el===document.activeElement), true);
    await summary.press('Enter');
    await summary.press('Escape');
    assert.equal(await page.locator('.donation-panel').getAttribute('open'), null);
    assert.equal(await summary.evaluate(el=>el===document.activeElement), true);
    await summary.click();
    await page.locator('.article-support').screenshot({path:`/tmp/donation-${width}.png`});
    // Simulated responses only exercise UI; they never reach the public site.
    await page.locator('#busuanzi_value_page_pv').evaluate(el=>el.textContent='42');
    await page.waitForFunction(()=>!document.querySelector('#article-views').hidden);
    await page.locator('#busuanzi_value_page_pv').evaluate(el=>el.textContent='bad data');
    await page.waitForFunction(()=>document.querySelector('#article-views').hidden);
    assert.deepEqual(requests, ['https://busuanzi.ibruce.info/busuanzi/2.3/busuanzi.pure.mini.js']);
    await page.goto('http://127.0.0.1:8765/');
    assert.equal(await page.locator('#article-views').count(),0);
    await page.close();
  }
  const page = await browser.newPage({javaScriptEnabled:false,viewport:{width:390,height:900}});
  await page.goto(url); await page.locator('.donation-panel>summary').click();
  assert.equal(await page.locator('.donation-content').isVisible(),true);
  assert.equal(await page.locator('.donation-close').isVisible(),false);
  await page.close(); await browser.close();
  console.log('PASS: desktop/mobile, original images, no overflow, blocked counter, numeric response, invalid response, repeat open/close, Escape, focus restoration and no-JS fallback.');
})().catch(error=>{console.error(error);process.exit(1)});
