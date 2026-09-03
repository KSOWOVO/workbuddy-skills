---
name: learning-workbench-sync
agent_created: true
summary: 学习工作台「同步数据」操作手册 + 长文档加工成结构化学习资产。三种同步模式决策、自更新契约。
description: >
  学习工作台「同步数据」与内容加工。触发词：同步 / 同步数据 / 更新工作台 / 拉取新资料 /
  加工整理视频 / 转写稿做进工作台 / 生成思维导图 / 做导读 / 提炼精华。
  三种模式：① WorkBuddy 手工（我亲自总结，质量最高）② 本地后端自动（node server/server.js + DeepSeek，浏览器点按钮全自动）
  ③ 静态刷新（无后端，只重载 data.js）。
  流程：探测 ima/Obsidian 新资料 → 拉全文 → 通顺不删减加工 → 写 xx-content.js + data.js fullRef → 校验。
  产物在 learning-workbench/。数据契约与质检细节见 references/。
---

# 学习工作台 · 同步数据

工作台目录：`C:\Users\13662\WorkBuddy\2026-08-31-20-05-05\learning-workbench\`

## 先判断：用哪种同步模式

| 模式 | 触发场景 | 谁总结 | 操作 |
|---|---|---|---|
| **A 手工加工** | 对话里说「同步/加工/整理」 | **我亲自做**，质量最高 | 见下方「操作步骤」 |
| **B 后端自动** | 浏览器点「同步」，后端在跑 | DeepSeek（提示词复刻格式） | `node server/server.js`（:8787） |
| **C 静态刷新** | file:// 或纯静态托管 | 无（只重载） | 前端自动降级，不是 bug |

## 操作步骤（模式 A，每条一句话）

1. 探测：ima `get_knowledge_list`（按更新时间倒序）找新增；Obsidian 扫 `C:/Users/13662/Documents/Obsidian`。
2. 去重：与 data.js 已有条目按标题/source 比对。
3. 拉全文：`fetch_media_content`（media_id 从步骤 1 拿）。
4. 加工（铁律）：清洗口语/图片 URL → 按 ts 分段 → 生成五面板资产。**通顺不删减、纠错不改意**。
5. 写文件：`xx-content.js` → data.js 加 fullRef（新增加 contentFile）→ index.html `<script>` 补引用。
6. 校验（见 references/sync-playbook.md「质检命令」），更新 data.js lastSynced。

## 自更新契约 ★ 本 skill 是「活文档」

以下变更发生时，**在同一轮任务内**回写更新本 skill，再同步 GitHub：

| 触发事件 | 更新位置 |
|---|---|
| ima/Obsidian 增删资料 | `references/sync-playbook.md`「数据源快照」 |
| data.js 契约字段变化 | sync-playbook「数据契约」 |
| 工作台新增功能/面板/快捷键/主题 | `references/workbench-details.md`「功能清单」 |
| server/ 模块或配置变化 | workbench-details「自动同步后端」 |
| 踩到新坑 / 更好做法 | 本文件「踩坑记录」+ 对应 references |
| 每次成功同步后 | sync-playbook「最近同步记录」 |

**更新后必做**：① 自检 SKILL.md ≤5KB、description ≤400 字，超了把细节下放 references；
② 同步 GitHub：`cd ~/.workbuddy/skills && git add 02-knowledge-management/learning-workbench-sync && git commit -m "..." && git push origin main`。

## 踩坑记录（最易踩的 3 条）

1. **merge 必须覆盖**：`mergeFullContent` 用 `full[k] !== undefined` 覆盖，否则 data.js 预置的 `essence: []` 吞掉完整版。
2. **chapter ts 必须与 segments 对齐**：合并相邻段时同步改 chapters 的 ts，否则导读点击无反应。
3. **file:// 不能 fetch JSON**：数据用 `<script>` 注入；后端生成的 obs-*.js 靠 `contentFile` 动态注入。

## 详细参考

- `references/sync-playbook.md` — 数据契约（完整版）、三种模式细节、质检命令、踩坑速查、数据源快照、最近同步记录
- `references/workbench-details.md` — 设计系统（浅色主题）、功能清单、后端架构
