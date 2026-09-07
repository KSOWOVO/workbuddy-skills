// 通用自检器：daily-intel-briefing 产出 HTML 的强制自检（v6.4 起取代每日临时 _validate_*.js）
// 用法: node validate_output.js <今日.html 绝对路径> [母版.html 绝对路径]
//   母版默认 = 本文件同目录 v6-sample-html.html
// 检查: ①<script> 可编译 ②引擎符号齐全 ③IDX≥9卡/字段/pts尾值==last/pts极差<2.2x/chg与K线自洽
//      ④DICT 顶层词条数与母版一致(防引擎区词表漂移) ⑤移动端双通道分支 ⑥日期存在、body无母版残留、锚点完整
// 退出码 0=通过 1=失败。通过方可交付。
const fs = require('fs');
const path = require('path');

const file = process.argv[2];
if (!file) { console.error('用法: node validate_output.js <html路径> [master路径]'); process.exit(2); }
const master = process.argv[3] || path.join(__dirname, 'v6-sample-html.html');
if (!fs.existsSync(file)) { console.error('文件不存在: ' + file); process.exit(2); }
if (!fs.existsSync(master)) { console.error('母版不存在: ' + master); process.exit(2); }

const html = fs.readFileSync(file, 'utf8');
const tpl  = fs.readFileSync(master, 'utf8');
let pass = true;
const fail = (m) => { pass = false; console.log('FAIL:', m); };

// 0) 日期从文件名提取 YYYY-MM-DD
const dm = path.basename(file).match(/(\d{4}-\d{2}-\d{2})/);
const date = dm ? dm[1] : null;

// 1) JS syntax
const s0 = html.indexOf('<script>');
const s1 = html.lastIndexOf('</script>');
if (s0 < 0 || s1 <= s0) fail('script block not found');
else {
  const js = html.slice(s0 + 8, s1);
  try { new Function(js); console.log('CHECK1 script compile: OK (' + js.length + ' chars)'); }
  catch (e) { fail('script compile: ' + e.message); }
}

// 2) engine symbols
const syms = ['showSelTranslate','selectionchange','getContextSentence','sentencePairing',
  'pctSignal','toggleCn','en-s','touchstart','pointer:coarse','openModal','drawChart','mouseup','cn-box','tmap'];
for (const s of syms) {
  if (html.includes(s)) console.log('CHECK2 symbol "' + s + '": OK');
  else fail('missing symbol ' + s);
}

// 3) IDX cards: >=9, fields, pts tail==last, range<2.2x, chg consistent with K-line
const i0 = html.indexOf('const IDX = [');
const i1 = html.indexOf('];', i0);
if (i0 < 0 || i1 < 0) fail('const IDX not found');
else {
  let arr = null;
  try { arr = new Function('return (' + html.slice(i0 + 12, i1 + 1) + ')')(); } catch (e) { fail('IDX parse: ' + e.message); }
  if (!Array.isArray(arr) || arr.length < 9) fail('IDX cards: ' + (Array.isArray(arr) ? arr.length : 'not array'));
  else {
    console.log('CHECK3 IDX cards: ' + arr.length);
    for (const c of arr) {
      if (!('pct' in c) || !('last' in c) || !('chg' in c) || !Array.isArray(c.pts))
        fail('card missing field: ' + (c.key || JSON.stringify(c).slice(0, 60)));
      if (c.pts.length > 0) {
        if (Math.abs(c.pts[c.pts.length - 1] - c.last) > Math.max(0.001, 0.0005 * Math.abs(c.last)))
          fail('pts tail != last: ' + c.key);
        if (c.pts.length >= 2) {
          const k = ((c.last / c.pts[c.pts.length - 2] - 1) * 100);
          if (Math.abs(k - c.chg) > 0.35) fail('chg(' + c.chg + ') vs K线(' + k.toFixed(2) + ') 不一致: ' + c.key);
        }
      }
      if (c.pts.length > 0) {
        const mn = Math.min(...c.pts), mx = Math.max(...c.pts);
        if (mx / mn > 2.2) fail('pts range too wide: ' + c.key);
      }
    }
    console.log('CHECK3 pts tail==last & chg vs K线: OK');
  }
}

// 4) DICT top-level entries count == master (engine data must not drift)
function dictTopKeys(t) {
  const m = t.match(/const DICT = \{([\s\S]*?)\n\};/);
  if (!m) return -1;
  const ks = m[1].match(/^\s*"[^"]{1,60}"\s*:/gm);
  return ks ? ks.length : 0;
}
const n1 = dictTopKeys(html), n2 = dictTopKeys(tpl);
if (n1 < 0 || n2 < 0) fail('DICT block not found in html/master');
else if (n1 !== n2) fail('DICT 词条数漂移: 产出=' + n1 + ' 母版=' + n2 + '（引擎区禁止增删词，缺词走 vocab 表/在线兜底）');
else console.log('CHECK4 DICT top-level keys: ' + n1 + ' == master: OK');

// 5) mobile branches
if (html.includes('selectionchange') && html.includes('touchstart') && html.includes('pointer:coarse'))
  console.log('CHECK5 mobile selectionchange + touchstart: OK');
else fail('mobile branches missing');

// 6) date present (whole file not replaced is caught here: master date differs),
//    body region sanity; h1 identical to master is only a WARN (daily h1 is a fixed brand title)
if (date && !html.includes(date)) fail('日期 ' + date + ' 缺失（整文件可能未替换）');
// hero 用前缀匹配（body 导出可能带 data-page-node-id 属性），totop 子串匹配
const bh0 = html.indexOf('<header class="hero');
const bt0 = html.indexOf('<a class="totop"');
if (bh0 < 0 || bt0 < 0) fail('body 锚点 <header class="hero" 或 <a class="totop" 缺失');
else {
  const mine = html.slice(bh0, bt0);
  const mb = tpl.indexOf('<header class="hero');
  const mt = tpl.indexOf('<a class="totop"');
  const tm = mb >= 0 && mt >= 0 ? tpl.slice(mb, mt) : '';
  const h1 = (x) => { const m = x.match(/<h1[^>]*>([\s\S]*?)<\/h1>/); return m ? m[1].replace(/<[^>]+>/g, '').trim() : ''; };
  const mineH1 = h1(mine), tplH1 = h1(tm);
  if (mine.length < 3000) fail('body 区过短(' + mine.length + 'B)，疑似替换异常');
  else console.log('CHECK6 body region: ' + (mine.length / 1024).toFixed(1) + 'KB OK');
  if (mineH1 && mineH1 === tplH1 && !date)
    console.log('WARN: h1 与母版相同（本文件无日期可判，若为正式产出请人工确认 body 已替换）');
  else if (mineH1) console.log('CHECK6 body h1: "' + mineH1.slice(0, 40) + '..." OK');
}
const toggles = (html.match(/toggleCn\(/g) || []).length;
console.log('CHECK6 toggles: ' + toggles + ' | size: ' + html.length);
if (toggles < 7) fail('too few cn toggles');

console.log(pass ? '=== ALL PASS ===' : '=== FAILED ===');
process.exit(pass ? 0 : 1);
