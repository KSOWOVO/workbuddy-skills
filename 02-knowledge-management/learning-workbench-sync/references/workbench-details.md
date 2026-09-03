# 学习工作台：设计系统、功能清单与自动同步后端

> 从 SKILL.md 拆出的细节章节，仅在需要时读取。
> 最后更新：2026-09-03（v3.8）

## 设计系统（当前为浅色主题，深色可切换）

**主基调：浅蓝 `#4f8ef7` + 浅粉 `#f7a8c9` + 白/浅灰蓝 `#f5f7fb`**（Kelsen 指定，2026-09-01 从深色改为浅色）。

- **双主题**：CSS 变量实现。浅色为默认（`:root`），深色用 `[data-theme="dark"]` 覆盖。
- **Surface ladder**：canvas `#f5f7fb` → surface-1 `#fff` → surface-2 `#f4f7fc` → surface-3 `#e9eff9` → surface-4 `#dfe8f6`。
- **边框三档**：`--border` `#e7ecf4` / `--border-2` `#d9e1ee` / `--border-3` `#c8d3e4`。
- **文字四级**：`--text-1` `#1c2333` → `--text-4` `#b8c1d2`。
- **粉的点缀用法**：收藏星标、金句卡片左边框+渐变底、精华圆点渐变（蓝→粉）、tab 指示器渐变、品牌点渐变、关键词 hover 渐变。
- **动效**：`--ease` cubic-bezier(.25,.1,.25,1)、`--spring` (.34,1.56,.64,1)；全部走 transform/opacity（GPU），尊重 `prefers-reduced-motion`。
- **装饰原则**：局部装饰不得孤立漂浮。分隔线用**全宽两端淡出渐变**（如 `linear-gradient(90deg, transparent, var(--border-2) 12%, var(--border-2) 88%, transparent)`），避免宽屏拉成硬线。

## 功能清单（v3.8）

| 功能 | 快捷键 | 说明 |
|---|---|---|
| 五面板 | `1`–`5` | 全文 / 导读 / 思维导图 / 精华 / 笔记 |
| 资料切换 | `J` / `K` | 上/下一份 |
| 返回列表 | `U` | 回欢迎页 |
| 收藏 | `S` | localStorage，侧栏 ★ + 欢迎页收藏区 |
| 深浅色 | `T` | localStorage 记忆 |
| 导出 Markdown | `E` | 全文+精华+脑图大纲 |
| 快捷键面板 | `?` | modal |
| 搜索 | `/` | 实时计数、Esc 清空 |
| 阅读进度 | — | 每份资料记面板+滚动位置，自动恢复 |
| 回到顶部 | — | 滚动 >600px 浮现 |
| 骨架加载 | — | 首屏 shimmer |
| 自动同步 | 按钮 | 有后端走 /api/sync，无则降级 |

## 自动同步后端（server/，2026-09-01 起）

零依赖 Node.js，让「同步」在不开 WorkBuddy 时也全自动。

- `server.js`：静态托管 + `GET /api/status` + `POST /api/sync`（0.0.0.0:8787，防并发锁、路径穿越防护）。
- 管线 `lib/sync.js`：① `lib/obsidian.js` 扫 vault（sha1 增量、`sync_ima: never` 跳过、`ignorePatterns` 忽略日记/欢迎页）→ ② `lib/summarize.js` 调 DeepSeek 分块通顺改写 + 生成五面板 JSON → ③ `lib/ima.js` 回存 ima（可选，失败仅警告）→ ④ `lib/build.js` 写 data.js + obs-*.js（带 `contentFile`）→ ⑤ 存状态（成功才记，失败下轮重试）。
- 前端：同步按钮优先 `fetch POST /api/sync`（12s 超时），失败降级为重载 data.js；`loadData` 后按 `contentFile` **动态注入**缺失 content 文件（后端生成的 obs-*.js 不在 index.html 静态列表里）。
- 配置 `server/config.json`：DeepSeek key（必填，约 ¥0.1-0.2/份）、ima 凭证（可选）。
- 部署细节见 `learning-workbench/server/README.md`。

## 完成标准

- 五面板全部可看，通顺全文不删减。
- 15 份已加工资料：理财 4 + 大作文 5 + 小作文 6，约 14.9 万字。
- 质检全过（语法 + 数据完整性 + 资源 200）。
