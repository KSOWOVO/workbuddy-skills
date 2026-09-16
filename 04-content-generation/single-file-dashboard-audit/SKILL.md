---
name: single-file-dashboard-audit
description: 生成或修改「多板块单文件 HTML 数据看板」后，做数据完整性自检，防止数据被写了却进不了卡片/筛选/搜索。触发词：没看到你放进去、数据没显示、筛选里没有、搜不到、卡片缺了、看板自检、数据遗漏巡检、LUND_EXTRA、__EXF、字段规范化、去重合并。适用于：node 脚本生成的大体积单文件 HTML（数据层 JS + 渲染层），含学校卡/专业卡/案例卡等多板块结构。
agent_created: true
---

# 单文件数据看板 · 数据完整性自检

## 这个 skill 解决什么问题

**症状**：用户说「**没看到你放进去啊**」——数据明明写在数据层里，某个板块也确实渲染了，但用户在**另一个板块**（卡片 / 筛选器 / 搜索框 / 统计数字）里找不到。

**根因**（本 skill 的核心洞察）：
> **同一份数据被多个板块消费时，很容易只接进其中一条渲染链路。**

典型场景：新增了一批项目，写进了专属板块（如「XX 专项收录」），以 `dpCard` 形式渲染，看起来「放进去了」。但它们**从未被转换成主数据结构的格式**并合入 `PROG[sid]`，于是：
- ❌ 逐校专业卡片里看不到
- ❌ 方向筛选器筛不到（`data-tags` 里没有对应 tag）
- ❌ 搜索框搜不到
- ❌ 全量排序表的「专业数」不计入
- ❌ 学校的「N 个可申专业」数字不涨

**用户的观察几乎总是准确的。别急着解释「我放在另一个板块了」——那是实现遗漏，不是用户看漏。**

---

## 强制自检流程（每次 build 后必跑）

### ① 数据层：条目是否真的进了主结构

```js
// 断言：新数据已合入 PROG，且无重复
const before = PROG[sid].length;          // 记录合并前
mergeXXX(PROG, EXTRA);
const after = PROG[sid].length;
console.log('合并前', before, '→ 合并后', after, '（新增', added, '补字段', merged, '）');

// 去重断言：用 nameKey 归一化后统计
const dup = {}; PROG[sid].forEach(x => { const k = nameKey(x.en); dup[k] = (dup[k]||0)+1; });
const bad = Object.keys(dup).filter(k => dup[k] > 1);
console.log(bad.length ? '❌ 重复: ' + bad.join(',') : '✅ 无重复');
```

### ② 渲染层：HTML 字符串里真的出现了吗

**不要只靠截图**（大体积单文件 HTML 渲染慢，截图极易白屏，看了等于没看）。
**改用静态分析 HTML 字符串**，按容器的 `id` 精确定位：

```js
const h = fs.readFileSync(OUT, 'utf8');
// 1) 目标卡片是否在正确的板块容器内
const li = h.indexOf('id="sc-lund"');                 // 学校卡 id 格式
const nx = h.indexOf('<article class="school"', li+10); // 下一张卡 = 本块结束
const blk = h.slice(li, nx > 0 ? nx : li + 300000);
const names = []; let m; const re = /<h4>(MSc[^<]+)<\/h4>/g;
while ((m = re.exec(blk))) names.push(m[1]);
console.log('块内卡片数:', names.length);
names.forEach((n,i) => console.log(' ', String(i+1).padStart(2), n));  // 肉眼核对目标条目在列
```

> ⚠️ **不要用 `</article>` 找块结束**——卡片内部有嵌套 `</article>`，会截断。用「下一个同级卡片的起始标记」更可靠。

### ③ 属性层：筛选器 / 搜索是否覆盖到

```js
// 学校卡上的 data-tags 是否含新 tag
console.log((blk.match(/data-tags="[^"]*"/g) || [])[0]);

// 全文所有 data-tag 的并集
const tags = new Set(); (h.match(/data-tag="[a-z]+"/g)||[]).forEach(x => tags.add(x.slice(10,-1)));
console.log('出现的 tag:', [...tags].sort().join(', '));
```

### ④ 标签层：新 tag 有没有中文名（**高频踩坑**）

**只要引入新 tag，必须同步补标签表**，否则筛选按钮渲染成 `undefined（3）`：

```js
const TAG_LABEL = { mkt:'市场营销', mgmt:'管理', /* ... */ data:'数据/商业分析', law:'贸易/税法' };
// 渲染时：${TAG_LABEL[p.tag] || '其他'}
```

自检：build 输出的 `QUALITY` 若报 `undefined`，**九成是这个原因**，直接搜 `undefined（` 定位。

### ⑤ 格式层：markdown 粗体有没有被 esc 吃掉

```js
// ❌ 错：esc() 把 ** 转义，粗体失效
'<div class="pNote">' + esc(p.note) + '</div>'

// ✅ 对：先转义，再转 markdown
function mdNote(s) {
  var t = esc(s).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>');
  t = t.replace(/\n{2,}/g, '</p><p>').replace(/\n/g, '<br>');
  return /<\/p>/.test(t) ? '<p>' + t + '</p>' : t;
}
```

### ⑥ 覆盖层：有没有学校/分类是空的

```js
const noCover = ALL.filter(s => !(PROG[s.id] && PROG[s.id].length));
console.log('无内容覆盖的条目数:', noCover.length);   // 期望 0
noCover.forEach(s => console.log('  -', s.id, '|', s.cn || s.n));
```

> ⚠️ **必须用「合并了扩展数据之后」的 ALL 来算**。只测基础数据会得到虚假的 0 遗漏（本 skill 来源案例中，基础 119 校全部有覆盖，加上扩展才到 176 校）。

---

## 去重合并的正确写法（配套 mergeXXX）

```js
// 归一化 key：这一步决定去重成败
function nameKey(en) {
  return String(en || '')
    .replace(/\s*[（(].*?[)）]\s*/g, ' ')          // 去中文括号
    .replace(/^MSc\s+/i, '')                        // 去学位前缀
    .replace(/\s*[—–-]\s*(方向1|方向2)[A-Za-z\s]*$/i, ' ')  // 去方向后缀
    .toLowerCase()
    .replace(/\s*(?:&|and|plus)\s*/gi, ' and ')     // ⚠️ & = and，务必归一
    .replace(/[^a-z0-9]+/g, ' ')
    .trim();
}
```

**三个必修的坑**：

1. **`&` 必须归一为 `and`** —— 否则 `Knowledge and Change` 与 `Knowledge & Change` 判为两条，产生重复卡片。
2. **带方向后缀的既有条目不参与裸名匹配** —— 否则裸名 `Service Management` 会误撞 `Service Management — Retail Management` 等 5 个方向条目。做法：把带方向的既有条目记进 `bareIdx`，传入条目**自身也带方向时**才允许匹配。
3. **裸名撞方向族时改名区分** —— 给总条目加「（方向族总览）」后缀，避免视觉上像重复。

**合并时还要顺手补全既有条目的缺失字段**（如 `cn` 中文名从 `en` 里的括号拆出来），不要只做「新增」。

---

## 「多个来源写同一件事」的归一（内容层同源问题）

同一批事实常被写进多个数据文件。**修改时必须全库搜索同类表述，一起改**：

```js
// 改完一个文件后，扫全库有没有遗留的旧口径
files.forEach(f => {
  const s = fs.readFileSync(dir + f, 'utf8');
  const hits = [];
  if (/旧数字/.test(s)) hits.push('旧数字');
  if (/旧口径关键词/.test(s)) hits.push('旧口径关键词');
  if (hits.length) console.log(f + ' :: ' + hits.join(', '));
});
```

来源案例中：修正「案例口径」时，除了案例数据文件，还在**学校备注文件**里发现一处引用了旧口径，一并改掉才叫改完。

---

## 分组降权的表达方式

当某类数据**真实但不适合作参照系**时，不要删除，而是**拆组分渲 + 降权标注**：

```js
// 按标签分组
const GROUP_A = ALL_ITEMS.filter(c => !/不适用标注/.test(c.tag || ''));
const GROUP_B = ALL_ITEMS.filter(c => /不适用标注/.test(c.tag || ''));
```

- 组 A 正常渲染，**置顶**
- 组 B 加 `style="opacity:.82"` 视觉降权，并在 tag 前缀写明口径（如 `通道类 · 非普适口径 ·`）
- 板块开头**显式说明为什么拆分**，并承认上一版的判断偏差

这比直接删掉数据更有价值：用户既能看到全貌，又不会被误导。

---

## 交付前的收尾清单

- [ ] merge 后条目数上升，去重断言通过
- [ ] 目标条目在**正确的板块容器内**（按 id 定位后肉眼核对名称列表）
- [ ] `data-tags` / `data-tag` 覆盖新 tag；标签表已补中文名
- [ ] `QUALITY` 无 `undefined` / `NaN` / 替换字符
- [ ] 无内容覆盖的条目数 = 0（用合并扩展后的全集算）
- [ ] markdown 粗体生效（抽查一条含 `**` 的 note）
- [ ] 全库搜索同类表述，旧口径已清干净
- [ ] 同步发布目录副本（`publish/index.html`）

---

## 环境备注（Windows 本机）

- **Git Bash 可能全废**（`dirname`/`cd`/`ls`/`grep`/`sed`/`tail`/`which` 报 `command not found`）→ 一律用绝对路径的 node 执行：`<node.exe> -e "..."`。列目录用 `fs.readdirSync`，读文件用 `fs.readFileSync`。
- **shell 里写 node -e 时反引号会被吃** → 把长脚本落成 `.js` 文件再执行，别硬塞进 `-e`。
- **截图验证大体积单文件 HTML 不可靠**（白屏）→ 用静态字符串分析（本 skill ②③④）。
- **agent-browser 的 shim 脚本在 PATH 下可能失效**（依赖 `sed`/`dirname`）→ 直接调 js 入口：`<node.exe> "<npm-root>/agent-browser/bin/agent-browser.js" open <url>`。
