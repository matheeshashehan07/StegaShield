const { chromium } = require('../../frontend/node_modules/playwright');
const path = require('path');
const { pathToFileURL } = require('url');
(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const page = await browser.newPage({ viewport: { width: 1100, height: 1000 } });
  await page.goto(pathToFileURL(path.join(__dirname, 'StegaShield_Group60_Progress_Report.html')).href);
  await page.evaluate(() => document.fonts.ready);
  await page.pdf({ path: path.join(__dirname, 'StegaShield_Group60_Progress_Report.pdf'), format: 'A4', printBackground: true,
    displayHeaderFooter: true, headerTemplate: '<span></span>',
    footerTemplate: '<div style="font:8px Arial;color:#58716d;width:100%;padding:0 45px;display:flex;justify-content:space-between"><span>STEGASHIELD | GROUP 60 | PROGRESS REVIEW</span><span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>',
    preferCSSPageSize: true });
  await page.screenshot({ path: path.join(__dirname, 'report-cover.png') });
  await browser.close();
  console.log('PDF exported');
})();
