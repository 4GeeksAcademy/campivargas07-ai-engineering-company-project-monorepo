import { chromium } from 'playwright';
import { readFileSync } from 'fs';
import { resolve } from 'path';

const ROOT = resolve(import.meta.dirname, '..');
const DOCS = resolve(ROOT, 'docs');

async function main() {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });

  // --- Screenshot 1: Web interface with analysis loaded ---
  await page.goto('http://localhost:3000/incidents');
  await page.waitForLoadState('networkidle');

  // Click paste mode via React synthetic event
  await page.evaluate(() => {
    const btn = Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('Pegar'));
    if (btn) btn.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
  });
  await page.waitForTimeout(1000);

  // Fill textarea with CSV
  const csv = readFileSync(resolve(ROOT, 'scripts/incidents-brasaland.csv'), 'utf8');
  await page.fill('textarea', csv);
  await page.waitForTimeout(500);

  // Click Analyze
  await page.evaluate(() => document.querySelector('.primary-button').click());
  await page.waitForTimeout(4000);

  // Take full-page screenshot
  await page.screenshot({ path: resolve(DOCS, 'screenshot-web-analysis.png'), fullPage: true });
  console.log('✅ screenshot-web-analysis.png saved');

  // Take viewport-only screenshot (top section with KPIs)
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(300);
  await page.screenshot({ path: resolve(DOCS, 'screenshot-web-top.png') });
  console.log('✅ screenshot-web-top.png saved');

  await browser.close();
  console.log('Done!');
}

main().catch(err => { console.error(err); process.exit(1); });
