/* DigiConnect chat — shared helpers for the visitor page (talk.php) and the control panel. By SA7SVR.
   Safe formatting (everything is HTML-escaped first), emoji picker, time labels. */
window.DCChat = (function () {
  function esc(s) { return String(s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  // **bold**  *italic*  _italic_  ~~strike~~  `code`  ```block```  and links (http/https only)
  function fmt(text) {
    var t = esc(text), blocks = [], codes = [];
    t = t.replace(/```([\s\S]*?)```/g, function (_, c) { blocks.push(c.replace(/^\n/, '').replace(/\n$/, '')); return '\u0001B' + (blocks.length - 1) + '\u0001'; });
    t = t.replace(/`([^`\n]+)`/g, function (_, c) { codes.push(c); return '\u0001C' + (codes.length - 1) + '\u0001'; });
    t = t.replace(/(https?:\/\/[^\s<]+[^\s<.,;:!?)\]])/g, '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>');
    t = t.replace(/\*\*([^*\n]+)\*\*/g, '<b>$1</b>')
         .replace(/(^|[\s(])\*([^*\n]+)\*(?=[\s).,!?:;]|$)/g, '$1<i>$2</i>')
         .replace(/(^|[\s(])_([^_\n]+)_(?=[\s).,!?:;]|$)/g, '$1<i>$2</i>')
         .replace(/~~([^~\n]+)~~/g, '<s>$1</s>');
    t = t.replace(/\n/g, '<br>');
    t = t.replace(/\u0001C(\d+)\u0001/g, function (_, i) { return '<code>' + codes[+i] + '</code>'; });
    t = t.replace(/\u0001B(\d+)\u0001/g, function (_, i) { return '<pre>' + blocks[+i] + '</pre>'; });
    return t;
  }
  var EMOJI = ('😀 😃 😄 😁 😆 😅 😂 🤣 😊 🙂 😉 😍 😘 😎 🤩 🤔 😐 😮 😴 😢 😭 😡 🙄 😬 ' +
    '👍 👎 👏 🙌 🙏 💪 👋 ✌️ 🤝 👌 🤞 👀 ❤️ 💙 💚 🔥 ⭐ ✨ 🎉 🎁 ☕ 🍺 ' +
    '✅ ❌ ⚠️ ❓ ❗ ℹ️ 🆗 🆕 🚀 💬 ' +
    '📻 📡 🎧 🎙️ 🔊 📶 🌍 📍 🗺️ 📷 💻 🖥️ 🔧 🛠️ 📅 ⏰ 🔌 🔋').split(' ');
  // small pop-up with emoji; onPick(emoji) is called, the pop-up closes
  function picker(anchor, onPick) {
    var old = document.getElementById('hzemo'); if (old) { old.remove(); return; }
    var d = document.createElement('div'); d.id = 'hzemo'; d.className = 'hzemo';
    d.innerHTML = EMOJI.map(function (e) { return '<button type="button">' + e + '</button>'; }).join('');
    anchor.parentNode.style.position = anchor.parentNode.style.position || 'relative'; anchor.parentNode.appendChild(d);
    d.addEventListener('click', function (ev) { var b = ev.target.closest('button'); if (b) { onPick(b.textContent); d.remove(); } });
    setTimeout(function () { document.addEventListener('click', function off(ev) { if (!d.contains(ev.target) && ev.target !== anchor) { d.remove(); document.removeEventListener('click', off); } }); }, 0);
  }
  // wrap the selected text of a textarea: wrap(ta,'**','**')
  function wrap(ta, a, b) {
    var s = ta.selectionStart, e = ta.selectionEnd, v = ta.value, sel = v.slice(s, e);
    ta.value = v.slice(0, s) + a + sel + b + v.slice(e);
    ta.focus(); ta.selectionStart = s + a.length; ta.selectionEnd = s + a.length + sel.length; ta.dispatchEvent(new Event('input'));
  }
  function insert(ta, txt) { var s = ta.selectionStart; ta.value = ta.value.slice(0, s) + txt + ta.value.slice(ta.selectionEnd); ta.focus(); ta.selectionStart = ta.selectionEnd = s + txt.length; ta.dispatchEvent(new Event('input')); }
  function hm(t) { return new Date(t * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }); }
  function dayKey(t) { var d = new Date(t * 1000); return d.getFullYear() + '-' + (d.getMonth() + 1) + '-' + d.getDate(); }
  function dayLabel(t, today, yest) {
    var d = new Date(t * 1000), n = new Date();
    if (dayKey(t) === dayKey(n.getTime() / 1000)) return today;
    if (dayKey(t) === dayKey(n.getTime() / 1000 - 86400)) return yest;
    return d.toLocaleDateString([], { weekday: 'short', day: 'numeric', month: 'long', year: d.getFullYear() === n.getFullYear() ? undefined : 'numeric' });
  }
  function ago(t, now, lb) { var s = now - t; if (s < 60) return lb.now; if (s < 3600) return Math.floor(s / 60) + ' ' + lb.min; if (dayKey(t) === dayKey(now)) return hm(t); if (s < 7 * 86400) return new Date(t * 1000).toLocaleDateString([], { weekday: 'short' }); return new Date(t * 1000).toLocaleDateString([], { day: 'numeric', month: 'short' }); }
  function beep() { try { var c = new (window.AudioContext || window.webkitAudioContext)(), o = c.createOscillator(), g = c.createGain(); o.type = 'sine'; o.frequency.value = 880; g.gain.value = .05; o.connect(g); g.connect(c.destination); o.start(); o.stop(c.currentTime + .12); setTimeout(function () { c.close(); }, 300); } catch (e) {} }
  var CSS = '.hzemo{position:absolute;bottom:100%;left:0;z-index:30;width:292px;max-height:210px;overflow:auto;display:grid;grid-template-columns:repeat(8,1fr);gap:2px;padding:6px;background:var(--card,#fff);border:1px solid var(--line2,#999);border-radius:12px;box-shadow:0 12px 34px rgba(0,0,0,.35)}' +
    '.hzemo button{all:unset;cursor:pointer;text-align:center;font-size:20px;line-height:1;padding:5px 0;border-radius:6px}.hzemo button:hover{background:rgba(127,127,127,.25)}';
  var st = document.createElement('style'); st.textContent = CSS; document.head.appendChild(st);
  return { esc: esc, fmt: fmt, picker: picker, wrap: wrap, insert: insert, hm: hm, dayKey: dayKey, dayLabel: dayLabel, ago: ago, beep: beep };
})();
