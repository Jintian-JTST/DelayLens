/* Real frozen data through API/model/UI. No intercepted successful API payloads. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const puppeteer = require(process.env.PUPPETEER_MODULE || 'puppeteer-core');
const base = process.env.QA_BASE_URL || 'http://127.0.0.1:5183';
const out = path.resolve(process.env.QA_OUTPUT_DIR || '.local/qa/chat-bus29');
const route = 'bus-29-outbound-mornington-crescent-tottenham-court-road';
fs.mkdirSync(out, { recursive: true });
const report = { base, capture_started_utc: new Date().toISOString(), source_revision: process.env.QA_SOURCE_REV || null, mode: 'offline recorded TfL predictions; inferred arrivals; not live', checks: [], runtimeErrors: [], unexpectedHttpErrors: [], externalRequests: [] };
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
function check(name, detail) { report.checks.push({ name, detail, passed: true }); }
(async () => {
  const browser = await puppeteer.launch({
    executablePath: process.env.CHROME_EXECUTABLE,
    headless: true,
    defaultViewport: { width: 1440, height: 1000 },
    args: ['--no-first-run', '--no-default-browser-check'],
  });
  try {
    const page = await browser.newPage();
    const capture = async filename => {
      await page.evaluate(() => window.scrollTo(0, 0));
      await pause(50);
      await page.screenshot({ path: path.join(out, filename), fullPage: true });
    };
    await page.emulateTimezone('Europe/London');
    let curveRequests = 0;
    page.on('pageerror', error => report.runtimeErrors.push(error.message));
    await page.setRequestInterception(true);
    page.on('request', request => {
      const url = new URL(request.url());
      if (['http:', 'https:'].includes(url.protocol) && url.origin !== new URL(base).origin) {
        report.externalRequests.push(url.origin + url.pathname);
        request.abort();
        return;
      }
      if (url.pathname === '/api/departure-curve') curveRequests++;
      request.continue();
    });
    page.on('response', response => {
      const pathname = new URL(response.url()).pathname;
      if (response.status() >= 400 && !(response.status() === 503 && ['/api/live', '/api/stats'].includes(pathname))) {
        report.unexpectedHttpErrors.push({ pathname, status: response.status() });
      }
    });
    await page.goto(base, { waitUntil: 'networkidle2', timeout: 30000 });
    await page.waitForSelector('#route option');
    await page.waitForFunction(() => !document.querySelector('#journey-form button[type=submit]')?.disabled);
    assert.equal(await page.$eval('#route', el => el.value), route);
    await page.select('#timezone', 'utc');
    await page.select('#route', route);
    const field = async (selector, value) => page.$eval(selector, (el, next) => {
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(el, next);
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
    }, value);
    const submit = async deadline => {
      await field('#deadline', deadline);
      const responsePromise = page.waitForResponse(response => new URL(response.url()).pathname === '/api/departure-curve' && response.request().method() === 'POST');
      await page.click('#journey-form button[type=submit]');
      const response = await responsePromise;
      assert.equal(response.status(), 200);
      const request = JSON.parse(response.request().postData());
      const payload = await response.json();
      await page.waitForFunction(() => !document.querySelector('#journey-form button[type=submit]')?.disabled);
      await pause(200);
      return { request, payload };
    };
    const initial = await submit('2026-10-24T16:00');
    fs.writeFileSync(path.join(out, 'deadline-1600-request.json'), JSON.stringify(initial.request, null, 2));
    fs.writeFileSync(path.join(out, 'deadline-1600-response.json'), JSON.stringify(initial.payload, null, 2));
    assert.equal(initial.request.route_id, route);
    assert.equal(initial.request.deadline, '2026-10-24T16:00:00.000Z');
    assert.equal(initial.payload.data_quality.status, 'ok');
    assert.equal(initial.payload.points.length, 91);
    assert(initial.payload.recommended && initial.payload.recommended.p_on_time >= 0.9);
    assert(initial.payload.points.some(point => point.n_trips >= 15));
    assert(initial.payload.points.every(point => point.n_trips >= 5));
    assert(initial.payload.points.find(point => point.depart_at === initial.payload.recommended.depart_at)?.n_trips >= 15);
    assert(await page.$('.curve-svg path'));
    const basis = await page.$eval('.data-basis', el => el.innerText);
    assert(basis.includes('Offline snapshot frozen 24 Oct 16:55 UTC; not live data.'));
    assert(basis.includes('±60 min'));
    assert(!/Interactive demo|Fixture data/.test(await page.$eval('header', el => el.innerText)));
    const advice = await page.$eval('[aria-label="Departure recommendation"]', el => el.innerText);
    assert(advice.includes('Aim to leave by'));
    assert(advice.includes(initial.payload.recommended.depart_at.slice(11, 16)));
    check('真实冻结数据→API→浏览器曲线与建议', { request: initial.request, points: initial.payload.points.length, recommended: initial.payload.recommended, basis, advice });
    await capture('recorded-1440.png');

    const beforeControls = curveRequests;
    await field('#tolerance', '20');
    await pause(150);
    assert.equal(await page.$eval('output[for=tolerance]', el => el.innerText), '20%');
    const flexible = await page.$eval('.recommendation', el => el.innerText);
    await page.$eval('.delay-buttons button:nth-child(2)', el => el.click());
    await pause(100);
    assert((await page.$eval('[aria-label="Departure recommendation"]', el => el.innerText)).includes('If you leave 5 minutes later'));
    await page.click('.checkbox-label input');
    await pause(100);
    assert((await page.$eval('[aria-label="Departure recommendation"]', el => el.innerText)).includes('lower-bound chance'));
    assert.equal(curveRequests, beforeControls);
    check('风险/保守估计/晚5分钟在本地生效', { curveRequestsBefore: beforeControls, curveRequestsAfter: curveRequests, flexible });
    await page.click('.checkbox-label input');
    await field('#tolerance', '10');
    await pause(150);

    for (const width of [390, 320]) {
      await page.setViewport({ width, height: 900 });
      await pause(200);
      const sizes = await page.evaluate(() => ({ viewport: innerWidth, document: document.documentElement.scrollWidth }));
      assert(sizes.document <= sizes.viewport + 1, JSON.stringify(sizes));
      assert(await page.$('.recommendation'));
      const label = await page.$eval('.data-basis', el => el.innerText);
      assert(label.includes('not live data'));
      await capture(`recorded-${width}.png`);
      check(`${width}px真实建议与冻结标签无横向溢出`, sizes);
    }

    await page.setViewport({ width: 1440, height: 1000 });
    const sparse = await submit('2026-10-24T14:30');
    fs.writeFileSync(path.join(out, 'deadline-1430-request.json'), JSON.stringify(sparse.request, null, 2));
    fs.writeFileSync(path.join(out, 'deadline-1430-response.json'), JSON.stringify(sparse.payload, null, 2));
    assert.equal(sparse.payload.recommended, null);
    assert.equal(sparse.payload.data_quality.status, 'low_data');
    assert(sparse.payload.points.every(point => point.n_trips >= 5));
    assert.equal(await page.$('.recommendation'), null);
    assert(await page.$('.advice-caution'));
    assert(await page.$$eval('.delay-buttons button', buttons => buttons.every(button => button.disabled)));
    const sparseAdvice = await page.$eval('[aria-label="Departure recommendation"]', el => el.innerText);
    check('真实低数据时段无建议且what-if禁用', { status: sparse.payload.data_quality.status, points: sparse.payload.points.length, advice: sparseAdvice });
    await capture('low-data-1440.png');
    for (const width of [390, 320]) {
      await page.setViewport({ width, height: 900 });
      await pause(200);
      const sizes = await page.evaluate(() => ({ viewport: innerWidth, document: document.documentElement.scrollWidth }));
      assert(sizes.document <= sizes.viewport + 1, JSON.stringify(sizes));
      await capture(`low-data-${width}.png`);
      check(`${width}px低数据状态无横向溢出`, sizes);
    }
    await page.setViewport({ width: 1440, height: 1000 });
    const calibrationResponse = page.waitForResponse(response => new URL(response.url()).pathname === '/api/calibration');
    await page.click('nav button:nth-child(2)');
    await page.waitForSelector('.method-intro');
    assert.equal((await calibrationResponse).status(), 200);
    const methodology = await page.$eval('.method-intro', el => el.innerText);
    assert(methodology.includes('Record TfL predictions'));
    assert(methodology.includes('Capture TfL predictions over time and infer journey samples.'));
    assert(methodology.includes('not measured'));
    assert(methodology.includes('5–14 usable trips use a 90% Wilson interval'));
    assert(methodology.includes('15 or more use a 90% run-bootstrap interval'));
    assert(methodology.includes('Fewer than 5 usable trips show no probability or advice'));
    assert(methodology.includes('Recommendations require at least 15 usable trips for that departure time'));
    assert(!methodology.includes('Record real arrivals'));
    await capture('methodology-1440.png');
    check('方法页将TfL预测、推断样本与实测到站区分', { methodology });
    await page.setViewport({ width: 320, height: 900 });
    await pause(200);
    const methodSizes = await page.evaluate(() => ({ viewport: innerWidth, document: document.documentElement.scrollWidth }));
    assert(methodSizes.document <= methodSizes.viewport + 1, JSON.stringify(methodSizes));
    await capture('methodology-320.png');
    check('320px方法页无横向溢出', methodSizes);
    assert.equal(report.runtimeErrors.length, 0);
    assert.equal(report.unexpectedHttpErrors.length, 0);
    assert.equal(report.externalRequests.length, 0);
    check('无浏览器异常、意外HTTP失败或外网请求', { runtimeErrors: [], unexpectedHttpErrors: [], externalRequests: [] });
    report.passed = true;
    console.log(JSON.stringify({ passed: true, checks: report.checks.length, output: out }));
  } catch (error) {
    report.passed = false;
    report.failure = { message: error.message, stack: error.stack };
    console.error(error.message);
    process.exitCode = 1;
  } finally {
    report.capture_completed_utc = new Date().toISOString();
    fs.writeFileSync(path.join(out, 'report.json'), JSON.stringify(report, null, 2));
    await browser.close();
  }
})();
