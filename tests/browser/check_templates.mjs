// Offline browser checks for the per-site templates.
//
// Serves each template with a hostile data.json and asserts, in a real
// Chromium, that scraped strings render as text (never as markup), that the
// Ballard search links and kids location filter still work with the original
// decoded names, and that calendar-date headings do not depend on the
// visitor's timezone. Invoked by tests/integration/test_templates_browser.py.
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');

const ROOT = process.argv[2];
const PAYLOAD = `O'Brien & "quoted" <img src=x onerror="window.injected=true">`;
const PLAIN = `Bob's "Tacos" & Grill`;
const ISO = (d) => `${d}T00:00:00`;

function assert(cond, msg) {
  if (!cond) throw new Error(`ASSERTION FAILED: ${msg}`);
}

function serve(templateDir, data) {
  const html = fs.readFileSync(path.join(templateDir, 'index.html'));
  const server = http.createServer((req, res) => {
    const url = req.url.split('?')[0];
    if (url === '/data.json') {
      res.writeHead(200, { 'content-type': 'application/json' });
      res.end(JSON.stringify(data));
    } else if (url === '/' || url === '/index.html') {
      res.writeHead(200, { 'content-type': 'text/html' });
      res.end(html);
    } else {
      // Favicons, Vercel analytics, etc. are absent offline; 404 like a static host.
      res.writeHead(404);
      res.end();
    }
  });
  return new Promise((resolve) => server.listen(0, '127.0.0.1', () => resolve(server)));
}

async function withPage(browser, server, timezoneId, fn) {
  const context = await browser.newContext({ timezoneId });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  // Fully offline: fonts, analytics, and any other external resource are
  // aborted so the check never waits on the network.
  await page.route('**/*', (route) => {
    const url = new URL(route.request().url());
    return url.hostname === '127.0.0.1' ? route.continue() : route.abort();
  });
  await page.addInitScript(() => {
    window.__opened = [];
    window.open = (url) => { window.__opened.push(url); return null; };
  });
  await page.goto(`http://127.0.0.1:${server.address().port}/`);
  try {
    await fn(page);
    assert(errors.length === 0, `page errors: ${errors.join('; ')}`);
  } finally {
    await context.close();
  }
}

async function assertNoInjection(page) {
  assert((await page.evaluate(() => window.injected)) === undefined, 'onerror handler executed');
  assert((await page.locator('img[src="x"]').count()) === 0, 'injected <img> element was created');
}

const baseData = (extra) => ({
  site_name: 'Test Site',
  timezone: 'America/New_York',
  timezone_note: 'All times ET',
  updated: '2026-09-06T12:00:00+00:00',
  total_events: 2,
  errors: [],
  haiku: null,
  ...extra,
});

const evt = (over) => ({
  date: ISO('2026-09-06'),
  title: PAYLOAD, vendor: PAYLOAD,
  venue: PAYLOAD, location: PAYLOAD, venue_key: 'v1', venue_url: null,
  start_time: '5:00 PM ET', end_time: '9:00 PM ET',
  start_time_raw: '5:00 PM', end_time_raw: '9:00 PM',
  description: PAYLOAD, extraction_method: 'vision',
  ...over,
});

async function checkFoodTrucks(browser) {
  const dir = path.join(ROOT, 'food-trucks');
  const data = baseData({
    events: [evt({}), evt({ title: PLAIN, vendor: PLAIN, venue: PLAIN, location: PLAIN, extraction_method: 'html' })],
    haiku: `${PAYLOAD}\nline two`,
    errors: [PAYLOAD],
  });
  const server = await serve(dir, data);
  try {
    await withPage(browser, server, 'America/Los_Angeles', async (page) => {
      await page.waitForSelector('.truck-item');
      await assertNoInjection(page);
      const text = await page.locator('#schedule').innerText();
      assert(text.includes(PAYLOAD), 'hostile vendor name not rendered as literal text');
      assert(text.includes(PLAIN), 'ordinary vendor name with quotes not rendered');
      assert((await page.locator('.vision-badge').count()) === 1, 'AI badge missing');
      assert((await page.locator('#haiku').innerText()).includes(PAYLOAD), 'haiku not text');
      assert((await page.locator('#errors-note').innerText()).includes(PAYLOAD), 'errors not text');

      // Search links must receive the original decoded name.
      await page.locator('a.truck-name').first().click();
      await page.locator('a.location-link').first().click();
      await page.locator('a.truck-name').nth(1).click();
      const opened = await page.evaluate(() => window.__opened);
      assert(opened.length === 3, `expected 3 window.open calls, got ${opened.length}`);
      assert(opened[0] === 'https://www.google.com/search?q=' + encodeURIComponent(`${PAYLOAD} food truck seattle`), `truck search url wrong: ${opened[0]}`);
      assert(opened[1] === 'https://www.google.com/search?q=' + encodeURIComponent(`${PAYLOAD} brewery seattle`), `brewery search url wrong: ${opened[1]}`);
      assert(opened[2] === 'https://www.google.com/search?q=' + encodeURIComponent(`${PLAIN} food truck seattle`), `plain search url wrong: ${opened[2]}`);
      assert(page.url().endsWith('/'), 'clicking a search link navigated the page');
      await assertNoInjection(page);
    });
  } finally {
    server.close();
  }
}

const DATE_CASES = [
  ['2026-09-06', 'Sunday', 'September 6'],
  ['2026-12-31', 'Thursday', 'December 31'],
  ['2027-01-01', 'Friday', 'January 1'],
];
const TIMEZONES = ['America/Los_Angeles', 'Pacific/Kiritimati', 'Pacific/Honolulu'];

async function checkMusic(browser) {
  const dir = path.join(ROOT, 'music');
  const data = baseData({
    events: DATE_CASES.map(([d]) => evt({ date: ISO(d) })).concat([evt({ title: PLAIN, venue: PLAIN, description: PLAIN })]),
  });
  const server = await serve(dir, data);
  try {
    for (const tz of TIMEZONES) {
      await withPage(browser, server, tz, async (page) => {
        await page.waitForSelector('.event-item');
        await assertNoInjection(page);
        const headings = await page.locator('.day-header').allInnerTexts();
        for (const [, weekday, monthDay] of DATE_CASES) {
          const want = `${monthDay.toUpperCase()} ${weekday.toUpperCase()}`;
          assert(headings.some((h) => h.replace(/\s+/g, ' ').trim() === want), `[${tz}] missing heading "${want}" in ${JSON.stringify(headings)}`);
        }
        const text = await page.locator('#events-container').innerText();
        assert(text.includes(PAYLOAD), `[${tz}] hostile title not rendered as text`);
        assert(text.includes(PLAIN), `[${tz}] plain title not rendered`);
        await page.locator('.event-desc').first().click();
        assert(await page.locator('.event-desc').first().evaluate((el) => el.classList.contains('expanded')), 'description toggle broken');
      });
    }
  } finally {
    server.close();
  }
}

async function checkKids(browser) {
  const dir = path.join(ROOT, 'kids');
  const OTHER = 'Prospect Park';
  const data = baseData({
    events: DATE_CASES.map(([d]) => evt({ date: ISO(d) })).concat([evt({ description: OTHER, title: PLAIN, venue: PLAIN })]),
  });
  const server = await serve(dir, data);
  try {
    for (const tz of TIMEZONES) {
      await withPage(browser, server, tz, async (page) => {
        await page.waitForSelector('.event-item');
        await assertNoInjection(page);
        const headings = await page.locator('.day-header').allInnerTexts();
        for (const [, weekday, monthDay] of DATE_CASES) {
          const want = `${weekday}, ${monthDay}`;
          // innerText reflects CSS text-transform, so compare case-insensitively.
          assert(headings.some((h) => h.trim().toUpperCase() === want.toUpperCase()), `[${tz}] missing heading "${want}" in ${JSON.stringify(headings)}`);
        }
        const text = await page.locator('#events-container').innerText();
        assert(text.includes(PAYLOAD), `[${tz}] hostile location not rendered as text`);
        assert(text.includes(PLAIN), `[${tz}] plain title not rendered`);

        // Enable the location filter on the hostile value.
        await page.locator('.badge').first().click();
        await assertNoInjection(page);
        const active = page.locator('#active-filter-badge');
        assert((await active.innerText()).replace('×', '').trim() === PAYLOAD, 'active filter badge lost the original name');
        assert(await page.locator('#active-filter').evaluate((el) => el.classList.contains('visible')), 'filter bar not shown');
        const hidden = await page.locator('.event-item.hidden').count();
        assert(hidden === 1, `expected 1 hidden event, got ${hidden}`);
        const inlineActive = page.locator('.event-item .badge-active');
        assert((await inlineActive.count()) === DATE_CASES.length, 'inline active badges missing');
        assert((await inlineActive.first().innerText()).replace('×', '').trim() === PAYLOAD, 'inline active badge lost the original name');

        // Clear it again.
        await active.click();
        assert((await page.locator('.event-item.hidden').count()) === 0, 'filter did not clear');
        assert(!(await page.locator('#active-filter').evaluate((el) => el.classList.contains('visible'))), 'filter bar still visible');
        await assertNoInjection(page);
      });
    }
  } finally {
    server.close();
  }
}

const browser = await chromium.launch();
try {
  await checkFoodTrucks(browser);
  console.log('food-trucks: ok');
  await checkMusic(browser);
  console.log('music: ok');
  await checkKids(browser);
  console.log('kids: ok');
} finally {
  await browser.close();
}
