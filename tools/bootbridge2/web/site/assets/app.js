/* BootBridge web edition: six-step guide (shared guide-site frame and typography).
 * Everything runs locally; the only network requests are the official firmware
 * download (h3c-magic OSS), the NX30 SN pre-check (magic.h3c.com) and this
 * site's own rule data.  SPDX-License-Identifier: GPL-2.0-or-later */
(function () {
  'use strict';
  var CAT = window.BB_CATALOG, STR = window.BB_STRINGS, CMDS = window.BB_COMMANDS, E = window.BBEngine, NX = window.BBNx30, INJ = window.BBInject;
  var root = document.getElementById('root');

  function bootFail(detail) {
    var b = document.getElementById('boot-fail'), d = document.getElementById('boot-detail');
    if (root) root.innerHTML = '';
    if (b) b.hidden = false;
    if (d) d.textContent = detail || '';
  }
  (function features() {
    var miss = [];
    if (!CAT || !STR || !CMDS || !E || !NX) miss.push('assets');
    if (typeof Promise !== 'function') miss.push('Promise');
    if (typeof Uint8Array !== 'function') miss.push('Uint8Array');
    if (typeof Blob !== 'function' || !window.URL || !URL.createObjectURL) miss.push('Blob');
    if (typeof FileReader !== 'function') miss.push('FileReader');
    if (typeof atob !== 'function') miss.push('atob');
    if (miss.length) { bootFail('missing: ' + miss.join(', ')); throw new Error('BootBridge: unsupported browser'); }
  })();

  /* ---------------- helpers ---------------- */
  function esc(s) { return String(s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function fmt(s, v) { return String(s).replace(/\{(\w+)\}/g, function (m, k) { return v && v[k] != null ? v[k] : m; }); }
  function store(k, v) { try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch (e) { return null; } return null; }
  function L() { return STR[S.lang]; }
  function guideById(id) { for (var i = 0; i < CAT.guide.length; i++) if (CAT.guide[i].id === id) return CAT.guide[i]; return null; }
  function G() { return guideById(S.model); }
  function mname(g) { return g.alias ? (S.lang === 'zh' ? g.primary + '（' + g.alias + '）' : g.primary + ' (' + g.alias + ')') : g.primary; }
  function bundleFor(g) { for (var i = 0; i < CAT.bundles.length; i++) { var b = CAT.bundles[i]; if (b.model === g.id && b.inSha === g.sha && b.inSize === g.bytes) return b; } return null; }
  function outName(g) { return g.primary + '-' + g.version + '-BootBridge.bin'; }
  function mb(n) { return (n / 1048576).toFixed(1); }
  function fmtSize(n) { return S.lang === 'zh' ? mb(n) + ' MB（' + n.toLocaleString('en-US') + ' 字节）' : mb(n) + ' MB (' + n.toLocaleString('en-US') + ' bytes)'; }
  function err(code, extra) { var e = new Error(code); e.code = code; if (extra != null) e.detail = extra; return e; }
  function busy() { return S.file.st === 'hashing' || S.file.st === 'downloading' || S.gen.st === 'loading' || S.gen.st === 'running'; }

  /* ---------------- state ---------------- */
  var langPref = store('bb.lang');
  var S = {
    step: 1,
    lang: langPref === 'zh' || langPref === 'en' ? langPref : 'zh',
    theme: 'auto',
    model: CAT.guide[0].id, modal: false, toast: '',
    rules: 'ok', rulesWhy: '',
    file: { st: 'empty' }, upgraded: false,
    gen: { st: 'idle' },
    sn: { v: '', st: 'idle', r: null },
    tab: NX.platform(navigator)
  };
  var dl = null; /* AbortController of the running official download */

  (function verifyCatalog() {
    try {
      if (!CAT.meta || CAT.meta.schema !== 'bootbridge-web-catalog-v2') throw err('schema');
      if (!CAT.pack || !CAT.pack.data || !INJ) throw err('pack');
      CAT.bundles.forEach(function (b) {
        if (!E.validPlan(b) || E.dataSize(b) !== b.data.size) throw err('plan ' + b.id);
        if (!b.layout || b.layout.base.bytes !== b.outSize || b.layout.base.sha256 !== b.outSha ||
            CAT.pack.data.size > b.layout.pack.capacity) throw err('layout ' + b.id);
        var g = guideById(b.model);
        if (!g || g.bytes !== b.inSize || g.sha !== b.inSha || g.version !== b.version) throw err('guide ' + b.id);
      });
      CAT.guide.forEach(function (g) { if (!bundleFor(g)) throw err('no bundle for ' + g.id); });
    } catch (e) { S.rules = 'bad'; S.rulesWhy = e.message; }
  })();

  /* ---------------- clipboard, toast, save ---------------- */
  var toastTimer = null;
  function toast(msg) {
    S.toast = msg; render();
    clearTimeout(toastTimer); toastTimer = setTimeout(function () { S.toast = ''; render(); }, 1800);
  }
  function copyText(text) {
    function legacy() {
      var ta = document.createElement('textarea'); ta.value = text; ta.setAttribute('readonly', '');
      ta.className = 'sr'; document.body.appendChild(ta); ta.select();
      var ok = false; try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
      ta.remove(); toast(ok ? L().copied : L().copyFail);
    }
    if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(text).then(function () { toast(L().copied); }, legacy);
    else legacy();
  }
  function saveBytes(bytes, name) {
    var url = URL.createObjectURL(new Blob([bytes], { type: 'application/octet-stream' }));
    var a = document.createElement('a'); a.href = url; a.download = name; a.rel = 'noopener'; a.className = 'sr';
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 120000);
  }
  function readFile(file) {
    if (file.arrayBuffer) return file.arrayBuffer().then(function (b) { return new Uint8Array(b); });
    return new Promise(function (res, rej) {
      var r = new FileReader(); r.onload = function () { res(new Uint8Array(r.result)); }; r.onerror = function () { rej(r.error); };
      r.readAsArrayBuffer(file);
    });
  }

  /* ---------------- progress (updated in place, no re-render) ---------------- */
  function setProgress(frac, text) {
    S.prog = frac; S.progText = text;
    paintProgress();
  }
  function paintProgress() {
    var bar = document.getElementById('pbar'), tx = document.getElementById('ptx');
    if (bar) {
      var indet = S.prog == null;
      bar.parentNode.classList.toggle('indet', indet);
      bar.style.width = indet ? '' : Math.max(0, Math.min(100, Math.round(S.prog * 100))) + '%';
    }
    if (tx) tx.textContent = S.progText || '';
  }

  /* ---------------- official firmware: local file ---------------- */
  var SIZES = {}; CAT.guide.forEach(function (g) { SIZES[g.bytes] = 1; });
  var MAX_FILE = 64 << 20;
  function resetFile() {
    if (dl) { try { dl.abort(); } catch (e) { /* ignore */ } dl = null; }
    S.file = { st: 'empty' }; S.gen = { st: 'idle' };
  }
  function handleFile(file) {
    if (busy()) return;
    S.step = 2; S.gen = { st: 'idle' };
    S.file = { st: 'hashing', name: file.name, size: file.size };
    setProgress(null, ''); render();
    if (file.size > MAX_FILE || !file.size) { S.file = { st: 'bad', name: file.name, size: file.size, why: L().tooBig }; render(); return; }
    readFile(file).then(function (u8) {
      S.progText = ''; return E.sha256(u8, { onProgress: function (f) { setProgress(f, Math.round(f * 100) + '%'); } }).then(function (sha) {
        return accept(u8, sha, file.name, 'local');
      });
    }).catch(function (e) {
      S.file = (e && e.name === 'RangeError') ? { st: 'error', title: L().memT, msg: L().memS } : { st: 'error', title: L().readErrT, msg: L().readErrS };
      render();
    });
  }
  function accept(u8, sha, name, source) {
    var id = E.identify(CAT, u8.length, sha);
    if (id.ambiguous) { S.file = { st: 'error', title: L().badTitle, msg: L().ambiguous, name: name, size: u8.length, sha: sha }; render(); return; }
    if (!id.guide || !id.bundle) { S.file = { st: 'bad', name: name, size: u8.length, sha: sha }; render(); return; }
    var switched = S.model !== id.guide.id;
    S.model = id.guide.id;
    S.file = { st: 'matched', name: name, size: u8.length, sha: sha, bytes: u8, model: id.guide.id, source: source, saved: false };
    if (switched) toast(fmt(L().autoSwitched, { m: esc(mname(id.guide)) })); else render();
  }

  /* ---------------- official firmware: direct download (public URL models) ---------------- */
  function download() {
    var g = G(); if (!g.url || busy()) return;
    var ctl = typeof AbortController === 'function' ? new AbortController() : null; dl = ctl;
    S.gen = { st: 'idle' };
    S.file = { st: 'downloading', name: g.version + '.bin', size: g.bytes };
    setProgress(0, '0.0 / ' + mb(g.bytes) + ' MB'); render();
    var buf, pos = 0, last = 0;
    function prog() { var now = Date.now(); if (now - last > 120 || pos === g.bytes) { last = now; setProgress(pos / g.bytes, mb(pos) + ' / ' + mb(g.bytes) + ' MB'); } }
    fetch(g.url, { mode: 'cors', credentials: 'omit', referrerPolicy: 'no-referrer', redirect: 'error', signal: ctl ? ctl.signal : undefined })
      .then(function (res) {
        if (!res.ok) throw err('http', res.status);
        try { buf = new Uint8Array(g.bytes); } catch (e) { throw err('memory'); }
        if (!res.body || !res.body.getReader) {
          return res.arrayBuffer().then(function (ab) { if (ab.byteLength !== g.bytes) throw err('size'); buf.set(new Uint8Array(ab)); pos = g.bytes; });
        }
        var rd = res.body.getReader();
        return (function pump() {
          return rd.read().then(function (r) {
            if (r.done) return;
            if (pos + r.value.length > g.bytes) { try { rd.cancel(); } catch (e) { /* ignore */ } throw err('size'); }
            buf.set(r.value, pos); pos += r.value.length; prog();
            return pump();
          });
        })();
      })
      .then(function () {
        if (pos !== g.bytes) throw err('size');
        setProgress(null, L().hashing);
        return E.sha256(buf);
      })
      .then(function (sha) {
        dl = null;
        if (sha !== g.sha) throw err('hash');
        accept(buf, sha, g.version + '.bin', 'download');
      })
      .catch(function (e) {
        dl = null;
        if (S.file.st !== 'downloading') return;           /* reset elsewhere */
        if (e && e.name === 'AbortError') { S.file = { st: 'empty' }; toast(L().fetchCancelled); return; }
        var code = e && e.code, msg;
        if (code === 'http') msg = fmt(L().eHttp, { f: 'HTTP ' + esc(e.detail) });
        else if (code === 'size') msg = L().eSize;
        else if (code === 'hash') msg = L().eHash;
        else if (code === 'memory') msg = L().memS;
        else msg = L().eNet;
        S.file = { st: 'error', title: L().fetchFailT, msg: msg, hint: L().fetchFailHint };
        render();
      });
  }

  /* ---------------- NX30 SN pre-check ---------------- */
  function snValue() { return NX.normalize(S.sn.v); }
  function precheck() {
    var sn = snValue(); if (!NX.check(sn).ok || S.sn.st === 'checking') return;
    S.sn.st = 'checking'; S.sn.r = null; render();
    NX.precheck(sn).then(function (r) {
      if (snValue() !== sn) return;
      S.sn.st = r.state; S.sn.r = r; render();
    });
  }
  function commandsAllowed() { return S.sn.st === 'ok' || S.sn.st === 'network' || S.sn.st === 'http'; }

  /* ---------------- rule data + generation ---------------- */
  var dataCache = {}, dataWait = {};
  window.BBData = { add: function (id, b64) { var w = dataWait[id]; if (w) { delete dataWait[id]; w(b64); } } };
  function viaScript(b) {
    return new Promise(function (res, rej) {
      var s = document.createElement('script'), t = setTimeout(function () { delete dataWait[b.id]; rej(err('data-load', 'timeout')); }, 180000);
      dataWait[b.id] = function (b64) { clearTimeout(t); res(b64); };
      s.src = b.data.file; s.async = true;
      s.onerror = function () { clearTimeout(t); delete dataWait[b.id]; rej(err('data-load', 'script')); };
      s.onload = function () { s.remove(); };
      document.head.appendChild(s);
    });
  }
  function viaFetch(b, onProg) {
    var prefix = 'BBData.add("' + b.id + '","', total = prefix.length + b.data.b64 + 4;
    return fetch(b.data.file, { credentials: 'same-origin' }).then(function (res) {
      if (!res.ok) throw err('data-load', 'HTTP ' + res.status);
      if (!res.body || !res.body.getReader || typeof TextDecoder !== 'function') return res.text();
      var rd = res.body.getReader(), parts = [], got = 0, dec = new TextDecoder('ascii');
      return (function pump() {
        return rd.read().then(function (r) {
          if (r.done) { parts.push(dec.decode()); return parts.join(''); }
          got += r.value.length; parts.push(dec.decode(r.value, { stream: true })); onProg(Math.min(1, got / total), got);
          return pump();
        });
      })();
    }).then(function (text) {
      if (text.indexOf(prefix) !== 0) throw err('data-mismatch', 'prefix');
      var end = text.lastIndexOf('");');
      if (end < prefix.length) throw err('data-mismatch', 'suffix');
      return text.slice(prefix.length, end);
    });
  }
  function loadData(b, onProg) {
    if (dataCache[b.id]) return Promise.resolve(dataCache[b.id]);
    var http = /^https?:$/.test(location.protocol) && typeof fetch === 'function';
    var p = http ? viaFetch(b, onProg).catch(function (e) { if (e && e.code === 'data-mismatch') throw e; return viaScript(b); }) : viaScript(b);
    return p.then(function (b64) {
      if (b64.length !== b.data.b64) throw err('data-mismatch', 'length');
      var u8; try { u8 = E.fromBase64(b64); } catch (e) { throw err('data-mismatch', 'base64'); }
      if (u8.length !== b.data.size) throw err('data-mismatch', 'size');
      dataCache[b.id] = u8; return u8;
    });
  }
  function generate() {
    if (busy() || S.file.st !== 'matched' || S.rules !== 'ok') return;
    var g = guideById(S.file.model), b = bundleFor(g), input = S.file.bytes, total = b.data.b64;
    S.gen = { st: 'loading' }; setProgress(dataCache[b.id] ? 1 : 0, ''); render();
    loadData(b, function (f, got) { setProgress(f, mb(got * 3 / 4) + ' / ' + mb(total * 3 / 4) + ' MB'); })
      .then(function (data) {
        S.gen = { st: 'running', stage: 'check' }; setProgress(0.08, ''); render();
        return E.build(b, input, data, {
          onStage: function (st) {
            S.gen.stage = st;
            var lbl = document.getElementById('gstage');
            if (lbl) lbl.textContent = st === 'verify' ? L().verifying : L().generating;
            setProgress(st === 'check' ? 0.08 : st === 'apply' ? 0.45 : 0.8, '');
          }
        });
      })
      .then(function (r) {
        /* The plan rebuilds the base image; the rule pack goes in afterwards. */
        var pack;
        return loadData(CAT.pack, function () {}).then(function (p) {
          pack = p;
          return E.sha256(pack);
        }).then(function (h) {
          if (h !== CAT.pack.data.sha) throw err('data-mismatch', 'pack');
          var bytes = INJ.apply(r.bytes, b.layout, pack);
          return E.sha256(bytes).then(function (sha) { return { bytes: bytes, sha: sha }; });
        });
      })
      .then(function (r) {
        if (S.file.bytes !== input) return;
        S.gen = { st: 'done', bytes: r.bytes, sha: r.sha, name: outName(g) };
        render();
        saveBytes(r.bytes, outName(g));
      })
      .catch(function (e) {
        if (S.file.bytes !== input) return;
        var c = (e && e.code) || (e && e.name === 'RangeError' ? 'memory' : 'other');
        S.gen = { st: 'error', code: c, detail: (e && (e.detail || e.message)) || '' };
        render();
      });
  }
  function genError() {
    var c = S.gen.code, l = L();
    if (c === 'data-load') return [l.rulesLoadT, l.rulesLoadS];
    if (c === 'data-mismatch' || c === 'invalid-plan') return [l.rulesBadT, l.rulesBadS];
    if (c === 'input-mismatch') return [l.inputBadT, l.inputBadS];
    if (c === 'output-mismatch') return [l.outBadT, l.outBadS];
    if (c === 'memory') return [l.memT, l.memS];
    return [l.genFailT, esc(S.gen.detail || c)];
  }

  /* ---------------- diagnostics (never contains the SN) ---------------- */
  function diag() {
    var m = CAT.meta, f = S.file, lines = [
      'BootBridge Web ' + m.web + (m.label ? ' (' + m.label + ')' : ''),
      'release: ' + m.release + ' · engine ' + m.engine + ' · pack ' + CAT.pack.data.sha.slice(0, 16),
      'rules: ' + S.rules + (S.rulesWhy ? ' (' + S.rulesWhy + ')' : ''),
      'page: ' + location.protocol + ' secure=' + !!window.isSecureContext + ' subtle=' + E.hasSubtle(),
      'browser: ' + navigator.userAgent,
      'lang: ' + S.lang + ' theme: ' + S.theme + ' step: ' + S.step + ' model: ' + S.model,
      'file: ' + f.st + (f.size != null ? ' size=' + f.size : '') + (f.sha ? ' sha=' + f.sha : '') + (f.source ? ' source=' + f.source : ''),
      'gen: ' + S.gen.st + (S.gen.code ? ' code=' + S.gen.code + ' ' + (S.gen.detail || '') : '') + (S.gen.sha ? ' out=' + S.gen.sha : ''),
      'nx30 precheck: ' + S.sn.st + (S.sn.r && S.sn.r.code != null ? ' retCode=' + S.sn.r.code : '') + (S.sn.r && S.sn.r.detail ? ' ' + S.sn.r.detail : ''),
      'SN: not included'
    ];
    return lines.join('\n');
  }

  /* ---------------- views ---------------- */
  function statusTable() {
    var l = L(), g = G(), f = S.file, gs = S.gen;
    function row(k, v) { return '<tr><th scope="row">' + k + '</th><td>' + v + '</td></tr>'; }
    var fw = f.st === 'matched' ? esc(f.name) + ' · ' + l.verified : f.st === 'downloading' ? l.stDl : f.st === 'hashing' ? l.stHash : l.stFwTodo;
    var br = gs.st === 'done' ? esc(gs.name) : gs.st === 'loading' || gs.st === 'running' ? l.stBrBusy : l.stBrTodo;
    return '<section class="bb-status" aria-labelledby="bb-status-title"><h2 id="bb-status-title">' + l.sumT + '</h2><table class="kv">' +
      row(l.release, '<code>' + esc(CAT.meta.release) + '</code> · ' + (S.rules === 'ok' ? l.rulesOk : l.rulesBadT)) +
      row(l.sumModel, esc(mname(g))) + row(l.sumVer, '<code>' + esc(g.version) + '</code>') +
      row(l.sumFw, fw) + (f.sha ? row(l.kSha, '<span class="mono">' + f.sha + '</span>') : '') +
      row(l.sumUp, S.upgraded ? fmt(l.stUpOk, { v: esc(g.version) }) : l.stUpTodo) + row(l.sumBridge, '<span class="mono">' + br + '</span>') +
      '</table><p class="bb-detail">' + l.privacyLine + ' · ' + l.diagNoSn + '</p><p><button class="btn" data-copy="diag">' + l.copyDiag + '</button> <button class="btn" data-act="open-modal" aria-expanded="' + S.modal + '">' + l.settings + '</button></p></section>';
  }
  function pageFoot() {
    var l = L(), m = CAT.meta;
    return '<p class="bb-detail">' + l.title + ' ' + fmt(l.version, { v: esc(m.web) }) + ' · <a href="SHA256SUMS" target="_blank" rel="noopener">SHA256SUMS</a>' +
      (m.repo ? ' · <a href="' + esc(m.repo) + '" target="_blank" rel="noopener noreferrer">' + l.source + '</a>' : '') + '</p>';
  }
  function shaDd(sha, key) { return '<dd><span class="mono">' + sha + '</span> <button class="btn" data-copy="' + key + '">' + L().copy + '</button></dd>'; }
  function olist(items, vars) {
    return '<ol class="steps">' + items.map(function (it, i) {
      var tx = it[1].replace('{v}', '<code>' + esc(vars.v || '') + '</code>').replace('{f}', '<code>' + esc(vars.f || '') + '</code>').replace('192.168.10.1', '<code>192.168.10.1</code>');
      return '<li><h3>' + it[0] + '</h3><p>' + tx + '</p>' + (vars.extra && vars.extra[i] || '') + '</li>';
    }).join('') + '</ol>';
  }

  function head(n, t, lead) { return '<h3 id="bb-current" tabindex="-1">' + t + '</h3><p>' + lead + '</p>' + (G().testing ? '<p class="testing-note">' + L().testingNote + '</p>' : ''); }

  function step1() {
    var l = L();
    return head(1, l.s1t, l.s1l) + '<div class="model-list" role="radiogroup" aria-label="' + esc(l.s1t) + '">' + CAT.guide.map(function (g) {
      var sel = S.model === g.id;
      return '<button class="model-option" data-model="' + esc(g.id) + '" role="radio" aria-checked="' + sel + '"><span class="model-name">' + esc(g.primary) + (g.alias ? ' (' + esc(g.alias) + ')' : '') + (g.testing ? ' <span class="testing-text">' + l.testing + '</span>' : '') + '</span><span>' + fmt(l.needVer, { v: esc(g.version) }) + '</span></button>';
    }).join('') + '</div><p class="fine">' + l.s1fine + '</p>';
  }

  function fileZone() {
    var l = L(), f = S.file;
    if (f.st === 'empty') return '<button class="drop" data-act="pick" id="drop"><b>' + l.dropB + '</b><span>' + l.dropS + '</span><small>' + l.dropN + '</small></button>';
    if (f.st === 'hashing' || f.st === 'downloading') {
      var d = f.st === 'downloading';
      return '<div class="bb-section mt"><div class="filerow"><span class="tx"><b>' + esc(f.name) + '</b><span>' + (d ? l.downloading : l.hashing) + '</span></span>' + (d ? '<button class="btn" data-act="cancel">' + l.cancel + '</button>' : '') + '</div><div class="prog"><i id="pbar"></i></div><div class="progtx"><span>' + (d ? l.dlSrc : l.dropN) + '</span><span id="ptx"></span></div></div>';
    }
    if (f.st === 'matched') {
      var fg = guideById(f.model), dlSrc = f.source === 'download';
      return '<div class="result ok mt"><div class="head"><div class="grow"><b>' + fmt(l.okTitle, { m: esc(mname(fg)), v: esc(fg.version) }) + '</b><p>' + (dlSrc ? l.okSubDl : l.okSub) + '</p></div>' + (dlSrc ? '' : '<button class="btn" data-act="reset-file">' + l.another + '</button>') + '</div>' +
        '<div class="rmeta">' + '<span>' + esc(f.name) + '</span><span class="sep">·</span><span>' + l.sameAs + '</span></div>' +
        (dlSrc ? '<div class="acts"><button class="btn' + (f.saved ? '' : ' primary') + '" data-act="save-fw">' + l.saveFw + '</button><button class="btn" data-act="reset-file">' + l.another + '</button></div>' : '') + '</div>';
    }
    if (f.st === 'bad') {
      return '<div class="result warn mt"><div class="head"><div class="grow"><b>' + l.badTitle + '</b><p>' + (f.why || l.badSub) + '</p></div></div>' +
        '<div class="rmeta">' + '<span>' + esc(f.name) + '</span><span class="sep">·</span><span>' + mb(f.size) + ' MB</span>' + (f.sha ? '<span class="sep">·</span><span class="mono" title="' + f.sha + '">' + f.sha + '</span>' : '') + '</div>' +
        '<div class="acts"><button class="btn primary" data-act="reset-file">' + l.another + '</button><button class="btn" data-copy="diag">' + l.copyDiag + '</button></div></div>';
    }
    if (f.st === 'error') {
      return '<div class="result err mt"><div class="head"><div class="grow"><b>' + f.title + '</b><p>' + f.msg + (f.hint ? '<br>' + f.hint : '') + '</p></div></div>' +
        '<div class="acts">' + (G().url && f.hint ? '<button class="btn primary" data-act="dl">' + l.retry + '</button>' : '') + '<button class="btn' + (G().url && f.hint ? '' : ' primary') + '" data-act="reset-file">' + l.another + '</button><button class="btn" data-copy="diag">' + l.copyDiag + '</button></div></div>';
    }
    return '';
  }

  function snPanel() {
    var l = L(), sn = snValue(), c = NX.check(sn), st = S.sn.st, r = S.sn.r || {}, g = G(), h = '';
    var locked = st === 'checking' || commandsAllowed();
    h += '<p class="how">' + l.fetchNote + '</p><div class="snbox">';
    if (!locked) {
      var bad = sn.length > 0 && (!c.ok && (c.reason === 'chars' || sn.length > 20));
      h += '<label for="sn">' + l.snLabel + '</label><div class="snrow"><input id="sn" class="snin' + (bad ? ' bad' : '') + '" type="text" inputmode="text" autocomplete="off" autocapitalize="characters" spellcheck="false" maxlength="40" placeholder="' + esc(l.snPh) + '" value="' + esc(S.sn.v) + '">' +
        '<button class="btn primary lg" data-act="sn-check" id="sncheck"' + (c.ok ? '' : ' disabled') + '>' + l.snCheck + '</button></div>' +
        '<div class="snmeta"><span id="snhint" class="' + (bad ? 'bad' : c.ok ? 'good' : '') + '">' + snHint(sn, c) + '</span></div>';
    } else {
      h += '<label>' + l.snLabel + '</label><div class="snfixed"><span class="mono">' + esc(NX.group(sn)) + '</span>' + (st === 'checking' ? '' : '<button class="btn link" data-act="sn-edit">' + l.snEdit + '</button>') + '</div>';
    }
    h += '</div><div class="privacy">' + '<span>' + l.snPrivacy + '</span></div>';
    if (st === 'checking') h += '<div class="status busy"><span>' + l.snChecking + '</span></div>';
    else if (st === 'ok') h += '<div class="status ok">' + '<span>' + fmt(l.snOk, { v: esc(g.version) }) + '</span></div>';
    else if (st === 'network') h += '<div class="status warn">' + '<span>' + fmt(l.snNet, { f: esc(r.detail || '') }) + '</span></div>';
    else if (st === 'http') h += '<div class="status warn">' + '<span>' + fmt(l.snHttp, { f: esc(r.status) }) + '</span></div>';
    else if (st === 'unknown-sn') h += '<div class="status err">' + '<span>' + l.snUnknown + '</span></div>';
    else if (st === 'bad-format') h += '<div class="status err">' + '<span>' + l.snFormat + '</span></div>';
    else if (st === 'other-version') h += '<div class="status warn">' + '<span>' + fmt(l.snOther, { f: esc(r.version || '?'), v: esc(g.version) }) + '</span></div>';
    else if (st === 'rejected') h += '<div class="status err">' + '<span>' + fmt(l.snRejected, { f: esc(r.code == null ? '?' : r.code) }) + '</span></div>';
    else if (st === 'bad-response') h += '<div class="status err">' + '<span>' + l.snBad + '</span></div>';
    if (commandsAllowed()) {
      var key = S.tab === 'ps51' ? 'ps51' : 'sh', cmd = NX.command(CMDS[key], sn);
      h += '<div class="divider"></div><h3>' + ' ' + l.cmdT + '</h3>' +
        '<div class="tabs" role="tablist"><button role="tab" data-tab="ps51" aria-selected="' + (key === 'ps51') + '">' + l.cmdWin + '</button><button role="tab" data-tab="sh" aria-selected="' + (key === 'sh') + '">' + l.cmdSh + '</button></div>' +
        '<p class="how">' + (key === 'ps51' ? l.cmdWinHow : l.cmdShHow) + '</p>' +
        '<div class="cmd"><pre id="cmdtext" tabindex="0">' + esc(cmd) + '</pre></div>' +
        '<div class="cmdbar"><button class="btn primary" data-copy="cmd">' + l.cmdCopy + '</button></div>' +
        '<div class="fine">' + '<span>' + l.cmdSafe + '</span></div>' +
        '<p class="after">' + fmt(l.cmdAfter, { f: esc(g.version + '.bin') }) + '</p>';
    }
    return h;
  }
  function snHint(sn, c) {
    var l = L();
    if (!sn.length) return '';
    if (c.ok) return esc(NX.group(sn));
    if (c.reason === 'chars') return l.snChars;
    return fmt(l.snLen, { n: sn.length });
  }

  function step2() {
    var l = L(), g = G(), dlBusy = S.file.st === 'downloading';
    var h = head(2, l.s2t, fmt(l.s2l, { m: esc(mname(g)) }));
    h += '<div class="bb-section"><h3>' + l.target + ' · ' + esc(mname(g)) + '</h3><table class="kv"><tr><th scope="row">' + l.kVer + '</th><td><code>' + esc(g.version) + '</code></td></tr><tr><th scope="row">' + l.kSize + '</th><td>' + mb(g.bytes) + ' MB</td></tr><tr><th scope="row">' + l.kSha + '</th><td><span class="mono">' + g.sha + '</span> <button class="btn" data-copy="sha">' + l.copy + '</button></td></tr></table>';
    if (g.url) {
      h += '<div class="linkrow"><div class="url">' + '<span class="mono" title="' + esc(g.url) + '">' + esc(g.url) + '</span></div>' +
        '<button class="btn' + (S.file.st === 'matched' ? '' : ' primary') + '" data-act="dl"' + (busy() ? ' disabled' : '') + '>' + l.directDl + '</button>' +
        '<a class="btn" href="' + esc(g.url) + '" target="_blank" rel="noopener noreferrer">' + l.openBrowser + '</a>' +
        '<button class="btn" data-copy="link" aria-label="' + esc(l.copyLink) + '">' + l.copyLink + '</button></div>' +
        (dlBusy || S.file.st === 'error' ? '<div class="fine">' + '<span>' + l.dlOpenHint + '</span></div>' : '');
    } else if (g.download === "manual") {
      h += '<p class="how">' + l.manualFw + '</p>';
    } else {
      h += snPanel();
    }
    h += '</div>' + fileZone();
    return h;
  }

  function step3() {
    var l = L(), g = G();
    return head(3, l.s3t, l.s3l) + '<div class="note">' + '<span>' + fmt(l.s3warn, { v: esc(g.version) }) + '</span></div><div class="bb-section">' + olist(l.s3steps, { v: g.version }) + (g.login === "button" ? '<p class="fine">' + l.buttonLogin + '</p>' : '') + '</div>';
  }

  function step4() {
    var l = L(), f = S.file, gs = S.gen, body;
    if (S.rules !== 'ok') {
      body = '<div class="result err"><div class="head"><div class="grow"><b>' + l.rulesBadT + '</b><p>' + l.rulesBadS + '</p></div></div><div class="acts"><button class="btn" data-copy="diag">' + l.copyDiag + '</button></div></div>';
    } else if (f.st !== 'matched') {
      body = '<div class="bb-section empty"><b>' + l.noFileT + '</b><p>' + l.noFileP + '</p><button class="btn primary" data-go="2">' + l.goStep2 + '</button></div>';
    } else {
      var g = guideById(f.model), name = outName(g);
      if (gs.st === 'loading' || gs.st === 'running') {
        var stage = gs.st === 'loading' ? fmt(l.loadingRules, { m: esc(mname(g)) }) : (gs.stage === 'verify' ? l.verifying : l.generating);
        body = '<div class="bb-section"><div class="filerow"><span class="tx"><b>' + esc(name) + '</b><span id="gstage">' + stage + '</span></span></div><div class="prog"><i id="pbar"></i></div><div class="progtx"><span>' + l.noClose + '</span><span id="ptx"></span></div></div>';
      } else if (gs.st === 'done') {
        body = '<div class="result ok"><div class="head"><div class="grow"><b>' + l.doneT + '</b><p>' + l.doneS + '</p></div></div>' +
          '<dl class="kv"><dt>' + l.kOut + '</dt><dd><span class="mono" title="' + esc(gs.name) + '">' + esc(gs.name) + '</span><button class="btn link" data-copy="outname" aria-label="' + esc(l.copy) + '">' + l.copy + '</button></dd><dt>' + l.kSha + '</dt>' + shaDd(gs.sha, 'outsha') + '</dl>' +
          '<div class="acts"><button class="btn primary" data-act="save-out">' + l.saveBridge + '</button></div></div>' +
          '<div class="fine">' + '<span>' + l.noUpgrade + '</span></div>';
      } else if (gs.st === 'error') {
        var e = genError();
        body = '<div class="result err"><div class="head"><div class="grow"><b>' + e[0] + '</b><p>' + e[1] + '</p></div></div><div class="acts"><button class="btn primary" data-act="gen">' + l.retry + '</button><button class="btn" data-copy="diag">' + l.copyDiag + '</button></div></div>';
      } else {
        body = '<div class="bb-section"><div class="filerow"><span class="tx"><b>' + esc(f.name) + '</b><span>' + esc(mname(g)) + ' · ' + esc(g.version) + ' · <span class="ok-ink">' + l.verified + '</span></span></span><button class="btn link" data-go="2">' + l.change + '</button></div>' +
          '<div class="lbl">' + l.outFile + '</div><div class="out"><div class="path"><span class="mono">' + esc(name) + '</span></div></div><div class="fine">' + '<span>' + l.outNote + '</span></div></div>' +
          '<div class="row-end"><button class="btn primary lg" data-act="gen">' + l.gen + '</button><div class="fine">' + '<span>' + l.genFine + '</span></div></div>';
      }
    }
    return head(4, l.s4t, l.s4l) + body;
  }

  function step5() {
    var l = L(), g = S.file.st === 'matched' ? guideById(S.file.model) : G();
    return head(5, l.s5t, l.s5l) + '<div class="bb-section">' + olist(l.s5steps, { f: outName(g) }) + '</div><div class="note">' + '<span>' + l.s5info + '</span></div>';
  }

  function step6() {
    var l = L(), g = G(), maint = 'http://192.168.10.1/';
    var link = '<span class="linkrow"><span class="url">' + '<span class="mono">' + maint + '</span></span><a class="btn primary" href="' + maint + '" target="_blank" rel="noopener noreferrer">' + l.openBrowser + '</a><button class="btn" data-copy="maint" aria-label="' + esc(l.copy) + '">' + l.copy + '</button></span>';
    return head(6, l.s6t, l.s6l) + '<div class="note danger">' + '<span>' + l.s6backup + '</span></div>' +
      '<div class="bb-section">' + olist(l.s6steps, { extra: [link] }) + '</div>' +
      '<details class="faq"><summary>' + '<span>' + l.faqQ + '</span>' + '</summary><div class="body">' + fmt(l.faqA, { v: esc(g.version) }) + '<ol>' + l.faqSteps.map(function (s) { return '<li>' + s + '</li>'; }).join('') + '</ol></div></details>' +
      '<div class="note" data-k="s6rec">' + '<span><b>' + l.s6recT + '</b> ' + l.s6rec.replace('192.168.10.1', '<code>192.168.10.1</code>') + '</span></div>' +
      '<div class="fine">' + '<span>' + l.noUpgrade + '</span></div>';
  }

  function panelFoot() {
    var l = L(), hint = '', nextDis = false;
    if (S.step === 3) {
      nextDis = !S.upgraded;
      hint = '<label class="upgrade-check"><input type="checkbox" data-act="toggle-up"' + (S.upgraded ? ' checked' : '') + '> <span>' + fmt(l.s3check, { v: esc(G().version) }) + '</span></label>';
    }
    if (S.step === 4 && busy()) nextDis = true;
    return '<div class="panel-foot">' + hint + '<div class="bb-actions">' +
      (S.step > 1 ? '<button class="btn" data-act="prev">' + l.prev + '</button>' : '') +
      (S.step < 6 ? '<button class="btn primary" data-act="next"' + (nextDis ? ' disabled' : '') + '>' + l.next + '</button>' : '') + '</div></div>';
  }

  function modal() {
    if (!S.modal) return '';
    var l = L(), m = CAT.meta;
    return '<section class="bb-settings"><h2>' + l.settings + '</h2><p>' + l.offlineUpd + '</p><p class="about">' + fmt(l.about, { v: esc(m.web), e: esc(m.engine), rs: esc(m.release) }) + '</p><p>' + l.sumNote + '</p><button class="btn" data-act="close-modal">' + l.close + '</button></section>';
  }

  var rendered = 0;
  function render() {
    var l = L(), d = document.documentElement;
    d.setAttribute('data-theme', S.theme); d.lang = S.lang === 'zh' ? 'zh-CN' : 'en';
    document.title = 'BootBridge - IPQ50XX-Uboot 安装指南';
    var content = [null, step1, step2, step3, step4, step5, step6][S.step]();
    var keep = rendered === S.step ? window.pageYOffset : -1;
    var ae = document.activeElement, focusId = ae && ae.id, selS = null, selE = null;
    if (focusId === 'sn') { selS = ae.selectionStart; selE = ae.selectionEnd; }
    root.innerHTML = '<p class="crumb">' + l.tools + '</p><h1>BootBridge</h1>' +
      '<div class="bb-language" role="group" aria-label="Language / 语言"><button class="btn" data-set="lang" data-val="zh" aria-pressed="' + (S.lang === 'zh') + '">中文</button> <button class="btn" data-set="lang" data-val="en" aria-pressed="' + (S.lang === 'en') + '">English</button></div>' +
      '<ol class="steps bb-flow">' + l.steps.map(function (s, i) {
        var n = i + 1;
        return '<li' + (n === S.step ? ' aria-current="step"' : '') + '>' + (n === S.step ? '<section class="bb-current" data-step="' + n + '">' + content + panelFoot() + '</section>' : '<button class="step-link" data-go="' + n + '">' + s[0] + '</button>') + '</li>';
      }).join('') + '</ol>' + statusTable() + modal() + pageFoot() +
      (S.toast ? '<p class="toast" role="status">' + S.toast + '</p>' : '') +
      '<input type="file" id="picker" class="hidden-input" accept=".bin,application/octet-stream">';
    rendered = S.step;
    if (focusId) { var el = document.getElementById(focusId); if (el) { try { el.focus({ preventScroll: true }); } catch (e) { el.focus(); } if (selS != null && el.setSelectionRange) try { el.setSelectionRange(selS, selE); } catch (e) { /* ignore */ } } }
    if (keep >= 0 && Math.abs(window.pageYOffset - keep) > 1) window.scrollTo(0, keep);
    paintProgress();
  }

  /* ---------------- events ---------------- */
  function go(n) { if (n >= 1 && n <= 6) { S.step = n; render(); window.scrollTo(0, 0); } }
  function copyKey(k) {
    var g = G(), t = '';
    if (k === 'sha') t = g.sha; else if (k === 'link') t = g.url; else if (k === 'maint') t = 'http://192.168.10.1/';
    else if (k === 'outsha') t = S.gen.sha || ''; else if (k === 'outname') t = S.gen.name || '';
    else if (k === 'diag') t = diag();
    else if (k === 'cmd') t = NX.command(CMDS[S.tab === 'ps51' ? 'ps51' : 'sh'], snValue());
    if (t) copyText(t);
  }
  root.addEventListener('click', function (ev) {
    var t = ev.target.closest('[data-act],[data-go],[data-model],[data-set],[data-copy],[data-tab]');
    if (!t) return;
    var act = t.getAttribute('data-act');
    if (t.hasAttribute('data-go')) return go(+t.getAttribute('data-go'));
    if (t.hasAttribute('data-model')) {
      var id = t.getAttribute('data-model');
      if (id !== S.model) { S.model = id; if (S.file.st === 'matched' && S.file.model !== id || S.file.st === 'downloading') resetFile(); }
      return render();
    }
    if (t.hasAttribute('data-set')) {
      var k = t.getAttribute('data-set'), v = t.getAttribute('data-val');
      S[k] = v; store(k === 'lang' ? 'bb.lang' : 'bb.theme', v); return render();
    }
    if (t.hasAttribute('data-copy')) return copyKey(t.getAttribute('data-copy'));
    if (t.hasAttribute('data-tab')) { S.tab = t.getAttribute('data-tab'); return render(); }
    switch (act) {
      case 'prev': return go(S.step - 1);
      case 'next': return go(S.step + 1);
      case 'pick': { var p = document.getElementById('picker'); if (p) p.click(); return; }
      case 'reset-file': resetFile(); return render();
      case 'cancel': if (dl) dl.abort(); return;
      case 'dl': return download();
      case 'save-fw': if (S.file.bytes) { saveBytes(S.file.bytes, S.file.name); S.file.saved = true; toast(fmt(L().savedAs, { f: esc(S.file.name) })); } return;
      case 'save-out': if (S.gen.bytes) saveBytes(S.gen.bytes, S.gen.name); return;
      case 'gen': return generate();
      case 'toggle-up': S.upgraded = !S.upgraded; return render();
      case 'sn-check': return precheck();
      case 'sn-edit': S.sn.st = 'idle'; S.sn.r = null; render(); var i = document.getElementById('sn'); if (i) i.focus(); return;
      case 'open-modal': S.modal = !S.modal; return render();
      case 'close-modal': if (ev.target === t || t.tagName === 'BUTTON') { S.modal = false; render(); } return;
    }
  });
  root.addEventListener('keydown', function (ev) {
    var t = ev.target;
    if (t.getAttribute && t.getAttribute('data-act') === 'toggle-up' && (ev.key === ' ' || ev.key === 'Enter')) { ev.preventDefault(); S.upgraded = !S.upgraded; render(); var c = root.querySelector('[data-act="toggle-up"]'); if (c) c.focus(); }
    if (t.hasAttribute && t.hasAttribute('data-model') && /^(ArrowDown|ArrowUp|ArrowLeft|ArrowRight|Home|End)$/.test(ev.key)) {
      ev.preventDefault();
      var options = Array.prototype.slice.call(root.querySelectorAll('[data-model]')), index = options.indexOf(t);
      index = ev.key === 'Home' ? 0 : ev.key === 'End' ? options.length - 1 : (index + (/^(ArrowDown|ArrowRight)$/.test(ev.key) ? 1 : -1) + options.length) % options.length;
      var model = options[index].getAttribute('data-model');
      root.querySelector('[data-model="' + model + '"]').click();
      root.querySelector('[data-model="' + model + '"]').focus();
    }
    if (t.id === 'sn' && ev.key === 'Enter') { ev.preventDefault(); precheck(); }
  });
  document.addEventListener('keydown', function (ev) { if (ev.key === 'Escape' && S.modal) { S.modal = false; render(); } });
  root.addEventListener('input', function (ev) {
    if (ev.target.id !== 'sn') return;
    S.sn.v = ev.target.value; if (S.sn.st !== 'idle' && S.sn.st !== 'checking') { S.sn.st = 'idle'; S.sn.r = null; render(); return; }
    var sn = snValue(), c = NX.check(sn), bad = sn.length > 0 && (!c.ok && (c.reason === 'chars' || sn.length > 20));
    ev.target.classList.toggle('bad', bad);
    var h = document.getElementById('snhint'), n = document.getElementById('sncount'), b = document.getElementById('sncheck');
    if (h) { h.innerHTML = snHint(sn, c); h.className = bad ? 'bad' : c.ok ? 'good' : ''; }
    if (n) n.textContent = fmt(L().snCount, { n: sn.length });
    if (b) b.disabled = !c.ok;
  });
  root.addEventListener('change', function (ev) {
    if (ev.target.id !== 'picker') return;
    var fs = ev.target.files; if (!fs || !fs.length) return;
    if (fs.length > 1) return toast(L().oneFile);
    handleFile(fs[0]);
  });
  var dragDepth = 0;
  function hasFiles(ev) { var t = ev.dataTransfer && ev.dataTransfer.types; return t && Array.prototype.indexOf.call(t, 'Files') >= 0; }
  window.addEventListener('dragenter', function (ev) { if (!hasFiles(ev)) return; dragDepth++; var d = document.getElementById('drop'); if (d) d.classList.add('over'); });
  window.addEventListener('dragleave', function () { dragDepth = Math.max(0, dragDepth - 1); if (!dragDepth) { var d = document.getElementById('drop'); if (d) d.classList.remove('over'); } });
  window.addEventListener('dragover', function (ev) { if (hasFiles(ev)) { ev.preventDefault(); ev.dataTransfer.dropEffect = busy() ? 'none' : 'copy'; } });
  window.addEventListener('drop', function (ev) {
    if (!hasFiles(ev)) return;
    ev.preventDefault(); dragDepth = 0;
    var fs = ev.dataTransfer.files; if (!fs || !fs.length || busy()) return;
    if (fs.length > 1) return toast(L().oneFile);
    handleFile(fs[0]);
  });
  window.addEventListener('beforeunload', function (ev) { if (busy()) { ev.preventDefault(); ev.returnValue = ''; } });

  try { render(); } catch (e) { bootFail(String(e && e.message || e)); throw e; }
  var bf = document.getElementById('boot-fail'); if (bf) bf.hidden = true;
  window.__bb = { state: S, diag: diag }; /* for automated tests and support */
})();
