// SPDX-License-Identifier: GPL-2.0-or-later
// Host-only check that the device page always offers "return to OEM", whatever the
// rest of the state says, and that the button really posts /api/return.
//   node device_return_mock.js WEB_DEVICE_DIR
'use strict';
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const DIR = process.argv[2];
let pass = 0, fail = 0;
const ok = (name, cond, extra) => {
  cond ? pass++ : fail++;
  console.log((cond ? 'PASS ' : 'FAIL ') + name + (extra ? ' — ' + extra : ''));
};
const base = {
  schema: 'bb-state-v1', facts: { route: 'mp02.1', env: { productname: 'NX30_2i5x' }, appsbl_sha256: ['a', 'a'] },
  pack: 'ok', rule_set: 'BB2-R1', decision: { code: 'ok', message: 'ok', board: 'D', candidate: 'D-x' },
  oem_return: { code: 'ready', message: 'ok' }, backup: { ready: false, bytes: 0, sha256: '' },
  last: { action: '', code: '', message: '' },
};
const cases = {
  'NX54 unrecognized, no backup': { ...base, facts: { route: 'mp03.1', layout: 'nx54', env: { productname: 'BX54E' } },
    pack: 'missing', decision: { code: 'no_board', message: 'no' } },
  'NX54 experimental ECC': { ...base,
    facts: { route: 'mp03.1', env: { productname: 'NX54' }, ecc_evidence: { sampled: true, parts: [
      { failed: 0, corrected: 1, non_ff: 80 }, { failed: 0, corrected: 0, non_ff: 90 },
      { failed: 0, corrected: 0, non_ff: 91 }, { failed: 0, corrected: 0, non_ff: 1 },
      { failed: 0, corrected: 0, non_ff: 1 }] } },
    decision: { code: 'ok', board: 'NX54', candidate: 'NX54-auto', nand_evidence: 'experimental' } },
  'NX54 backup not downloaded': { ...base, decision: { code: 'ok', board: 'NX54', candidate: 'NX54-auto' },
    backup: { ready: true, full: true, downloaded: false, bytes: 124256256, sha256: 'test' } },
  'install done': { ...base, oem_return: { code: 'already_oem', message: 'm' },
    last: { action: 'install', code: 'done', message: 'done' } },
  'no matching U-Boot, pack missing': { ...base, pack: 'missing', decision: { code: 'no_board', message: 'no' } },
  'OEM return reported not ready': { ...base, oem_return: { code: 'bad_slots', message: 'bad' } },
  'state without facts': { schema: 'bb-state-v1', last: {} },
  'state request fails': null,
};
const types = { '.html': 'text/html', '.js': 'application/javascript', '.css': 'text/css' };

(async () => {
  const launch = process.env.CHROMIUM ? { executablePath: process.env.CHROMIUM } : {};
  const browser = await chromium.launch(launch);
  for (const [name, state] of Object.entries(cases)) {
    const page = await browser.newPage();
    let posted = false;
    await page.route('http://bridge.test/**', (r) => {
      const p = new URL(r.request().url()).pathname;
      if (p === '/api/return' && r.request().method() === 'POST') {
        posted = true;
        return r.fulfill({ contentType: 'application/json', body: JSON.stringify(state || base) });
      }
      if (p.startsWith('/api/'))
        return state ? r.fulfill({ contentType: 'application/json', body: JSON.stringify(state) })
          : r.fulfill({ status: 500, body: 'down' });
      const f = path.join(DIR, p === '/' ? 'index.html' : p);
      return fs.existsSync(f) ? r.fulfill({ contentType: types[path.extname(f)] || 'text/plain', body: fs.readFileSync(f) })
        : r.fulfill({ status: 404, body: '' });
    });
    await page.goto('http://bridge.test/');
    await page.waitForTimeout(300);
    if (name === 'NX54 experimental ECC') {
      ok('experimental: backup warning displayed', (await page.textContent('#device-sub')) ===
        '闪存型号未登记，按实测 ECC 放行（实验性）。安装前请务必生成并下载完整备份。');
      ok('experimental: per-partition evidence shown', (await page.textContent('#tech')).includes('corrected 1（上限 8），非擦除页 80'));
    }
    const enabled = await page.isEnabled('#return-button');
    ok(name + ': return enabled', enabled);
    if (enabled) {
      await page.click('#return-button');
      await page.click('#confirm-yes');
      await page.waitForTimeout(300);
    }
    ok(name + ': return posted', posted);
    if (name === 'NX54 backup not downloaded') {
      ok('NX54: install disabled until backup download', await page.isDisabled('#main-button'));
      ok('NX54: backup download available', await page.isVisible('#backup-link'));
    }
    await page.close();
  }
  await browser.close();
  console.log(`${pass} passed, ${fail} failed`);
  process.exit(fail ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(1); });
