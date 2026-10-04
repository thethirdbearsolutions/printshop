// Drive a `printshop web` page in headless Chromium: Python boots, a slider and the code box re-run
// the design in the page, and an error is shown rather than thrown.
//
//   python -m http.server 8020 --directory SITE &   node tools/pyodide/check_page.cjs [URL]
//
// THREE_DIR / PYODIDE_DIR (an npm install of three@0.170.0 / pyodide@0.29.5) serve the CDN's files
// locally, for machines whose browser cannot reach the CDN.
const { chromium } = require(require('child_process').execSync('npm root -g').toString().trim() + '/playwright');
(async () => {
  const b = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'] });
  const pg = await b.newPage({ viewport: { width: 1200, height: 760 } });
  const three = process.env.THREE_DIR;
  const pyo = process.env.PYODIDE_DIR;
  if (three) await pg.route('https://cdn.jsdelivr.net/npm/three@0.170.0/**', r => r.fulfill({ path: three + r.request().url().split('three@0.170.0/')[1], contentType: 'application/javascript' }));
  if (pyo) await pg.route('https://cdn.jsdelivr.net/npm/pyodide@0.29.5/**', r => {
    const f = r.request().url().split('pyodide@0.29.5/')[1];
    const type = f.endsWith('.wasm') ? 'application/wasm' : f.endsWith('.js') || f.endsWith('.mjs') ? 'application/javascript' : f.endsWith('.json') ? 'application/json' : 'application/octet-stream';
    r.fulfill({ path: pyo + f, contentType: type });
  });
  const errs = []; pg.on('pageerror', e => errs.push(String(e))); pg.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
  const t0 = Date.now();
  await pg.goto(process.argv[2] || 'http://127.0.0.1:8020/');
  await pg.waitForTimeout(800); await pg.screenshot({ path: 'page-snapshot.png' });
  await pg.waitForFunction(() => document.getElementById('sub').textContent.startsWith('running'), null, { timeout: 120000 });
  console.log('python ready in', (Date.now() - t0) / 1000, 's');
  await pg.waitForTimeout(800);
  await pg.$eval('#params input', el => { el.value = 7; el.dispatchEvent(new Event('input')); });
  await pg.waitForTimeout(1500);
  console.log('after slider:', await pg.$eval('#checks-hint', e => e.textContent));
  await pg.click('#codebox summary');
  const src = await pg.$eval('#source', e => e.value);
  await pg.$eval('#source', (e, v) => { e.value = v; }, src.replace('"#c8323a")]', '"#c8323a"), ("flag", box([2, 2, 12], center=False).translate([10, -1, 3.2 + height]), "#ffd21f")]'));
  await pg.click('#run'); await pg.waitForTimeout(2000);
  console.log('after code edit:', await pg.$eval('#checks-hint', e => e.textContent), await pg.$eval('#report', e => e.textContent));
  await pg.screenshot({ path: 'page-live.png' });
  await pg.$eval('#source', e => { e.value = e.value.replace('return [', 'return oops + ['); });
  await pg.click('#run'); await pg.waitForTimeout(1500);
  console.log('error shown:', (await pg.$eval('#error', e => e.style.display + ' ' + e.textContent.split('\n').slice(-2).join(' '))));
  console.log('errors:', JSON.stringify(errs));
  if (errs.length) process.exitCode = 1;
  await b.close();
})();
