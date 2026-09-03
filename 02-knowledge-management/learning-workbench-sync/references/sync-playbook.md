# 学习工作台 · 同步手册（细节）

> 从 SKILL.md 拆出的细节。**数据源快照与最近同步记录必须随实际状态更新**（自更新契约）。
> 最后更新：2026-09-03

## 数据契约（每个条目，完整版）

```js
window.XXX_FULL = {
  segments:  [ { ts: "00:00", text: "通顺全文段落" } ],  // 按时间戳分段，必须覆盖全片
  summary:   "全文概要（多段用 \n）",
  keywords:  ["关键词", ...],           // 8-30 个，文中真实术语
  chapters:  [ { ts: "00:08", title: "章节名", gist: "一句话要点" } ],  // ts 必须存在于 segments
  mindmap:   { label: "根", children: [{ label: "分支", children: [] }] },  // 每级都要 children 数组
  essence:   ["核心要点"],              // 8-16 条，只留可复用结论
  highlights:["金句"],                  // 3-6 条，尽量原文原句
  formulas:  ["公式/句型/清单"]         // 雅思写作放可套用句型
};
```

data.js 条目加 `"fullRef": "XXX_FULL"`；后端/本地新增的再加 `"contentFile": "<id>-content.js"`（前端动态注入用）。
加工铁律：**通顺但不删减**——只纠错与捋顺，数字/名称/案例/逻辑全保留；作者数据错误保留不强行统一。

## 数据源快照

| 源 | 位置 | 状态 |
|---|---|---|
| ima 知识库 | id `001aa55b37801a4a`（KS今天偷吃麥當當的知识库） | 19 个条目（含「学习工作台说明」与 ima 指南 pdf）；新上传转写稿为 WORD |
| Obsidian vault | `C:/Users/13662/Documents/Obsidian` | 分类：00-收件箱/10-课程学习/20-竞赛科研/30-升学规划/40-个人生活/90-模板库 |
| 工作台 data.js | `learning-workbench/data.js` | 16 份已加工（finance 4 / ielts-w 5 / ielts-s 6 / methods 1）约 17.3 万字 |

**拉新资料**：ima 用 `get_knowledge_list`（sort 用 `UPDATE_TS_DESC_SORT_TYPE` 找最新）→ 拿 `media_id` → `fetch_media_content` 拉全文。
Obsidian 侧新增则走后端（见下）或手工读文件。

## 三种同步模式详解

### A · WorkBuddy 手工加工（质量最高）
- **触发**：对话里说「同步/加工」。我亲自做，保证通顺不删减 + 五面板资产。
- **步骤**：探测（ima list 按更新时间倒序找新增）→ 对比 data.js 去重 → 拉全文 → 清洗+生成 → 写 `xx-content.js` → data.js 加 fullRef（+contentFile）→ index.html 补 script → node vm 校验（chapters ts 必须对齐 segments）→ 更新 data.js lastSynced。

### B · 本地后端自动（DeepSeek）
- `node server/server.js`（:8787，零依赖）。浏览器/平板点「同步」→ `POST /api/sync`。
- 管线：obsidian.js 扫 vault（sha1 增量、`.sync-state.json` 记录已同步）→ summarize.js 调 DeepSeek 分块改写 + 五面板 JSON → ima.js 回存（可选）→ build.js 写 data.js + obs-*.js → 更新状态。
- 质量 ≈ 提示词复刻手工标准（85-90%）。人工补校可提升。
- **注意**：改 server 代码/配置必须重启进程才生效。

### C · 静态刷新（无后端）
- file:// 双击或纯静态托管：同步按钮 fetch `/api/sync` 失败 → 自动降级只重载 data.js。不是 bug。

## 质检命令（每次同步后跑）

```bash
# 语法（在 learning-workbench/ 下）
"C:/Users/13662/.workbuddy/binaries/node/versions/22.22.2-2/node.exe" --check *.js

# 合并校验：全部条目 segments/summary/keywords/chapters/mindmap/essence 非空；
# chapters 每个 ts 必须存在于 segments ts 集合（node vm 模拟 app.js mergeFullContent 后断言）
```

## 踩坑速查

1. `mergeFullContent` 用 `full[k] !== undefined` 覆盖，否则 data.js 预置的 `essence: []` 吞掉完整版。
2. chapter ts 必须能在 segments 找到（合并相邻段时记得同步改 chapters 的 ts）。
3. file:// 不能 fetch JSON，用 `<script>` 注入；后端生成的 obs-*.js 靠条目 `contentFile` 字段动态注入。
4. `[hidden]{display:none!important}` 必须有，否则 `.welcome{display:flex}` 会让 hidden 失效。
5. 分隔线用全宽两端淡出渐变，别用会孤立漂浮的局部短装饰线。
6. 雅思转写稿常见错字：护身材/后身300→沪深300；虎铺外/彪虎外→标普500；机型/机芯→基金；「帕/怕/泡泡」→part；「钉钉/静听」→精听；「chat GBD/TPT/CHB」→ChatGPT；「剑鞘/见朝/镜像」→剑雅（剑桥雅思）；「真金」→真题。
7. 报班（作者说「不报班」）类字词：粤语口音会把「班」说成「办」，留意上下文。
8. 后端 `.sync-state.json` 在 `server/` 根（不是 lib/）。

## 最近同步记录

| 时间 | 来源 | 新增 | 结果 |
|---|---|---|---|
| 2026-09-03 | ima | 雅思自学流程介绍（method-1，→方法库） | 16 份 / 17.3 万字，校验通过，lastSynced 更新 |
