const { chromium } = require('playwright');
const path = require('path');

(async () => {
  const browser = await chromium.launch({ ignoreDefaultArgs: ['--hide-scrollbars'] });
  const page = await browser.newPage({ viewport: { width: 1900, height: 800 } });
  await page.goto('http://localhost:8080/', { waitUntil: 'networkidle' });

  await page.evaluate(() => {
    const section = document.getElementById('tx-transcript-section');
    const log = document.getElementById('tx-transcript-log');
    section.hidden = false;
    for (let i = 0; i < 150; i++) {
      const li = document.createElement('li');
      li.textContent = `${i}. 2026-07-19 15:3${i % 10}:00 UTC — VU2FI PD2FZ JO33`;
      log.appendChild(li);
    }
  });
  await page.waitForTimeout(150);
  await page.screenshot({ path: path.join(__dirname, 'SB-tx-panel.png') });

  await page.evaluate(() => {
    const popup = document.getElementById('decode-filter-popup');
    popup.hidden = false;
    popup.style.top = '60px';
    popup.style.left = '1100px';
    popup.innerHTML = '<div class="decode-filter-popup-title">DXCC — click to filter</div>' +
      Array.from({ length: 60 }, (_, i) =>
        `<label class="decode-filter-popup-row"><input type="checkbox" checked> Country ${i}</label>`
      ).join('');
  });
  await page.waitForTimeout(150);
  await page.screenshot({ path: path.join(__dirname, 'SB-filter-popup.png') });

  await browser.close();
})();
