// Two small additions; every page works without them.
// 1. A copy button on each command block.
// 2. The model filter on the model list (devices/).
(function () {
  document.querySelectorAll('pre.cmd').forEach(function (pre) {
    var box = document.createElement('div');
    box.className = 'cmdbox';
    pre.parentNode.insertBefore(box, pre);
    box.appendChild(pre);
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'copy';
    btn.textContent = '复制';
    btn.addEventListener('click', function () {
      var text = pre.innerText.replace(/\n+$/, '');
      var done = function (msg) {
        btn.textContent = msg;
        setTimeout(function () { btn.textContent = '复制'; }, 2000);
      };
      var select = function () {
        var r = document.createRange();
        r.selectNodeContents(pre);
        var s = window.getSelection();
        s.removeAllRanges();
        s.addRange(r);
        done('已选中，按 Ctrl+C');
      };
      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text).then(function () { done('已复制'); }, select);
      } else {
        select();
      }
    });
    box.appendChild(btn);
  });

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
