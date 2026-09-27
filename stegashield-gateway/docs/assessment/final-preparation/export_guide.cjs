const { chromium } = require('../../../frontend/node_modules/playwright');
const path = require('path');
const { pathToFileURL } = require('url');
(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  try {
    const page = await browser.newPage();
    const stem = 'StegaShield_Final_Report_and_Viva_Guide';
    await page.goto(pathToFileURL(path.join(__dirname, stem + '.html')).href);
    await page.pdf({ path: path.join(__dirname, stem + '.pdf'), format: 'A4',
      printBackground: true, preferCSSPageSize: true, displayHeaderFooter: true,
      headerTemplate: '<span></span>',
      footerTemplate: '<div style="font:8px Arial;width:100%;margin:0 17mm;color:#58716d">STEGASHIELD · Preparation guide <span style="float:right"><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>' });
    console.log('Generated PDF preparation guide.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exit(1); });
