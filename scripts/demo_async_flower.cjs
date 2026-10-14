// Optional real-browser evidence; Playwright lives outside the monorepo.
const { chromium } = require(process.env.DEV55_PLAYWRIGHT_MODULE);
const path = require('path');

(async () => {
  const [username, password] = process.env.FLOWER_BASIC_AUTH.split(':');
  const browser = await chromium.launch({ headless: true });
  try {
    const context = await browser.newContext({
      httpCredentials: { username, password },
      viewport: { width: 1440, height: 1100 },
    });
    const page = await context.newPage();
    for (const [state, taskId] of [
      ['SUCCESS', process.env.DEV55_SUCCESS_ID],
      ['FAILURE', process.env.DEV55_FAILURE_ID],
    ]) {
      await page.goto(`http://127.0.0.1:15555/task/${taskId}`);
      await page.getByText(state, { exact: true }).first().waitFor();
      await page.screenshot({
        path: path.join(process.env.DEV55_EVIDENCE_DIR, `flower-${state.toLowerCase()}.png`),
        fullPage: true,
      });
    }
  } finally {
    await browser.close();
  }
})().catch(() => { console.error('Flower browser evidence failed'); process.exit(1); });
