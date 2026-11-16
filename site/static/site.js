// Three small additions; every page works without them.
// 1. A copy button on each command block.
// 2. The current heading in the "on this page" list.
// 3. The model filter on the model list (devices/).
(function () {
  var en = document.documentElement.getAttribute('data-site-lang') === 'en';
  var say = { copy: en ? 'Copy' : '复制', copied: en ? 'Copied' : '已复制',
              selected: en ? 'Selected, press Ctrl+C' : '已选中，按 Ctrl+C' };
  document.querySelectorAll('.term:not(.out)').forEach(function (term) {
    var pre = term.querySelector('pre');
    var head = term.querySelector('.term-h');
    if (!pre || !head) return;
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'copy';
    btn.textContent = say.copy;
    btn.addEventListener('click', function () {
      var text = pre.innerText.replace(/\n+$/, '');
      var done = function (msg) {
        btn.textContent = msg;
        setTimeout(function () { btn.textContent = say.copy; }, 2000);
      };
      var select = function () {
        var r = document.createRange();
        r.selectNodeContents(pre);
        var s = window.getSelection();
        s.removeAllRanges();
        s.addRange(r);
        done(say.selected);
      };
      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text).then(function () { done(say.copied); }, select);
      } else {
        select();
      }
    });
    head.appendChild(btn);
  });

  var links = Array.prototype.slice.call(document.querySelectorAll('.toc a'));
  if (links.length && 'IntersectionObserver' in window) {
    var heads = links.map(function (a) {
      return document.getElementById(decodeURIComponent(a.getAttribute('href').slice(1)));
    });
    var mark = function () {
      var current = 0;
      heads.forEach(function (h, i) {
        if (h && h.getBoundingClientRect().top < 120) current = i;
      });
      links.forEach(function (a, i) { a.classList.toggle('on', i === current); });
    };
    var pending = false;
    window.addEventListener('scroll', function () {
      if (pending) return;
      pending = true;
      requestAnimationFrame(function () { pending = false; mark(); });
    }, { passive: true });
    mark();
  }

  var q = document.getElementById('q');
  if (!q) return;
  var norm = function (s) {
    return s.toLowerCase().replace(/[\s\-_./·（）()【】\[\]，,、!！]+/g, '');
  };
  var groups = Array.prototype.slice.call(document.querySelectorAll('[data-group]'));
  var none = document.getElementById('none');
  var run = function () {
    var n = norm(q.value);
    var any = false;
    groups.forEach(function (g) {
      var shown = 0;
      g.querySelectorAll('tr[data-k]').forEach(function (tr) {
        var ok = !n || tr.getAttribute('data-k').indexOf(n) !== -1;
        tr.hidden = !ok;
        if (ok) shown++;
      });
      g.hidden = !shown;
      var count = g.querySelector('h2 .n');
      if (count) count.textContent = shown;
      if (shown) any = true;
    });
    if (none) none.hidden = any;
  };
  q.closest('.filter').hidden = false;
  q.addEventListener('input', run);
  var initial = new URLSearchParams(location.search).get('q');
  if (initial) q.value = initial;
  run();
})();
