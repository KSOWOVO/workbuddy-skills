---
name: learning-workbench-sync
agent_created: true
summary: 知识库面板「同步数据」操作手册：从 Obsidian vault 重建站点数据、给新篇目配交互动效。含四层导航架构、27 个动效清单与自更新契约。
description: >
  知识库面板（learning-workbench）「同步数据」与内容重构。触发词：同步 / 同步数据 / 更新工作台 /
  更新知识库面板 / 拉取新资料 / Obsidian 可视化 / 给新篇目做动效。
  流程：扫 Obsidian vault（只读）→ node _parse.js 生成 kb-data.json → node _mkdata.js 生成 kb-data.js
  → node _smoke.js 冒烟校验 → 若新增语法篇目则在 widgets.js 补一个专属交互动效。
  站点为四层导航（总览→领域→篇目→正文），27 篇英语语法各有专属动效。
  产物在 learning-workbench/。细节见 references/。
---

# 知识库面板 · 同步数据

工作台目录：`C:\Users\13662\WorkBuddy\2026-08-31-20-05-05\learning-workbench\`
数据源：`C:\Users\13662\Documents\Obsidian`（**只读，绝不修改原文件**）

## 同步（三步脚本）

```bash
cd learning-workbench
node _parse.js      # 扫 vault → kb-data.json（兼容两种转录格式，自动分节，ts 自动对齐）
node _mkdata.js     # kb-data.json → kb-data.js（前端 <script> 直载）
node _smoke.js      # 冒烟：27 个 widget 渲染 + 领域覆盖 + 数据完整性
```

改完刷新浏览器即可（静态站点，无需重启）。本地服务：`node server/server.js`（:8787）。

## 站点结构（四层导航）

```
L1 总览 → L2 领域(6) → L3 篇目 → L4 正文（专属动效 + 沉浸式阅读器）
```
- 路由：hash 化 `#/home` `#/d/grammar` `#/p/g13` `#/search/词` `#/fav` `#/help`
- 文件：`index.html`(外壳) + `styles.css`(设计系统) + `app.js`(路由/视图/阅读器) +
  `widgets.js`(27 个动效) + `kb-data.js`(内容) + `server/`(后端)
- 主题：浅色默认（浅蓝 #4f8ef7 + 浅粉 #f7a8c9 + 白），深色对等

## 给新篇目加交互动效（本 skill 的核心价值）

语法篇目 id 为 `g01`~`g27`，其他领域为 `x01`~`xNN`。在 `widgets.js` 的 `W` 注册：

```js
W.g28 = {
  t:'动效标题', d:'一句话说明',
  r:function(){ return '<HTML 结构>'; },        // 返回 HTML 字符串
  b:function(root,ctx){ /* 绑定交互；ctx.tenses 是 16 时态数据 */ }
};
```

**其他领域**用领域级键（自动回退，无需逐篇写）：
`W['d:雅思写作:大作文']`、`W['d:雅思写作:小作文']`、`W['d:雅思备考']`、
`W['d:投资理财']`、`W['d:竞赛科研']`、`W['d:课程学习']`

解析顺序（app.js `resolveWidget`）：篇级 → 领域+子类 → 领域级。

可用样式类（已内置于 widgets.js 的 `CSS` 常量）：
`.w-segs/.w-seg`（分段控件）、`.w-card`、`.w-code`（公式）、`.w-lab`（小标题）、
`.w-note`、`.w-svgbox`（SVG 容器）、`.tok`（句子成分染色：`.s`主语 `.v`谓语 `.o`宾语 `.be`助动词）、
`.tl-*`（时态时间线专用）、`.w-tbl`、`.w-blocks/.w-block`、`.w-tree`、`.w-swap`。

## 自更新契约 ★ 本 skill 是「活文档」

| 触发事件 | 更新位置 |
|---|---|
| Obsidian 增删篇目 | `references/sync-playbook.md`「数据源快照」 |
| kb-data 结构或解析规则变化 | sync-playbook「数据契约」+ 本文件同步步骤 |
| 站点新增功能/快捷键/主题 | `references/workbench-details.md`「功能清单」 |
| 新增/修改交互动效 | workbench-details「27 个动效清单」 |
| 踩到新坑 / 更好做法 | 本文件「踩坑记录」+ 对应 references |
| 每次成功同步后 | sync-playbook「最近同步记录」 |

**更新后必做**：① 自检 SKILL.md ≤5KB、description ≤400 字，超了下放 references；
② 同步 GitHub（走 API，见 `90-tooling/skill-github-backup` 的 `scripts/api_sync.py`，
**不要用 git push**——本机 TLS 被墙）。

## 踩坑记录（最易踩的 3 条）

1. **vault 有两种转录格式**：`## ▎小节` + `**00:00**`（词法/句法）与
   `发言人1   00:00`（动词组）。后者**「发言人」后可能带数字**，正则漏了会导致整篇被解析成 1 段。
2. **章节 ts 必须落在 segments 上**，否则大纲点击无效；`_parse.js` 已内置自动就近对齐。
3. **本机 Git Bash 常年损坏**（`dirname/ls/head/curl/sleep` 全 command not found，
   node 路径会变版本号）。**一律用 PowerShell 调 `node`**，不要依赖 bash 工具链。

## 详细参考

- `references/sync-playbook.md` — 数据契约、解析规则、质检命令、数据源快照、最近同步记录
- `references/workbench-details.md` — 设计系统、功能清单、27 个动效清单、前端架构
