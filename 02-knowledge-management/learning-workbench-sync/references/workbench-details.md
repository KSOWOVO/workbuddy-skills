# 学习工作台：设计系统、完成标准与自动同步后端

> 从 SKILL.md 拆出的细节章节，仅在需要时读取。

## 设计系统（styles.css 已按 Apple HIG 重做，别回退）
- 纯黑 #000 基底 + 分层表面；四级语义文字色（label-1~4）；强调色 Bright Blue #2997ff（深色背景规范）。
- 动效：cubic-bezier(.25,.1,.25,1)（标准）、(.34,1.56,.64,1)（弹簧）；微交互 140ms、状态切换 220ms、转场 320ms。
- 暗色下不用阴影，用 1px rgba(255,255,255,.08) 发丝边框分层。
- 完整设计 token 见 styles.css 顶部注释。

## 完成标准
- 全部条目五个面板可看：全文（带 ts 跳转）/ 导读 / 思维导图 / 精华 / 笔记（localStorage）。
- 15 条内容约 15 万字通顺全文（理财 6.4 万 + 大作文 4.8 万 + 小作文 3.7 万），全部质检通过。

## 自动同步后端（2026-09-01 新增，server/ 目录）
Kelsen 在浏览器/平板打开工作台、不一定会开 WorkBuddy。`learning-workbench/server/` 是零依赖 Node.js 后端：

- `server.js`：静态托管 + `GET /api/status` + `POST /api/sync`（0.0.0.0:8787，防并发锁，路径穿越防护）。
- 同步管线（`lib/sync.js`）：① `lib/obsidian.js` 扫描 vault（sha1 增量、frontmatter `sync_ima: never` 跳过、`ignorePatterns` 忽略日记/欢迎页）→ ② `lib/summarize.js` 调 DeepSeek 分块通顺改写 + 一次调用生成五面板 JSON（提示词复刻手工加工标准）→ ③ `lib/ima.js` 回存 ima（可选，失败仅警告）→ ④ `lib/build.js` 写 data.js + obs-<id>-content.js（条目带 `contentFile` 字段）→ ⑤ 存状态（成功才记，失败下次重试）。
- 前端 app.js 同步按钮：优先 `fetch POST /api/sync`（12s 超时），解析失败/无后端退回旧「只刷新 data.js」；`loadData` 后**动态注入缺失 content 文件**（用条目 `contentFile` 字段，因为后端生成的 obs-*.js 不在 index.html 里）。
- 配置：`server/config.json`（DeepSeek key 必填；ima 可选）。首次同步把已有笔记预置为已同步（`server/.sync-state.json`），避免重复处理。
- 踩坑补充：状态文件路径在 `server/` 而非 `server/lib/`；后端改代码/配置必须重启；file:// 下 fetch 失败是预期（前端自动降级）。
- 详细部署说明见 `learning-workbench/server/README.md`。
