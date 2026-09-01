---
name: learning-workbench-sync
summary: 把 ima 知识库里的视频转写稿（或任何长文档）加工成「学习工作台」的结构化学习资产：通顺全文（按时间戳分段）+ 导读（关键词/概要/章节速览）+ 思维导图 + 精华，写入 xx-content.js 并通过 data.js 的 fullRef 挂载。含数据契约、质检清单与全部踩坑点。
description: >
  当 Kelsen 说「加工/整理视频」「把转写稿做进工作台」「按标准整理文档」「同步资料」时使用。
  目标产物：学习工作台（learning-workbench/）里每个条目一份 xx-content.js（window.XXX_FULL），data.js 里条目加 fullRef 引用。
  流程：fetch_media_content 拉全文 → 清洗口语/时间戳/图片URL → 生成 segments/summary/keywords/chapters/mindmap/essence/highlights/formulas → 写文件 → 校验。
agent_created: true
---

# 学习工作台：视频转写稿 → 结构化学习资产

## 适用场景
- Kelsen 在 ima 上传了视频转写稿（Word/PDF，标题常带「_原文」），要我加工进学习工作台。
- 或任何「把长文档整理成 全文+导读+脑图+精华」的需求。
- 工作台目录：`C:\Users\13662\WorkBuddy\2026-08-31-20-05-05\learning-workbench\`

## 数据契约（每个条目）
```js
window.XXX_FULL = {
  segments:  [ { ts: "00:00", text: "通顺全文段落" } ],  // 按时间戳分段，必须覆盖全片
  summary:   "全文概要，多段用 \n 分隔",
  keywords:  ["关键词"],
  chapters:  [ { ts: "00:08", title: "章节名", gist: "一句话要点" } ],
  mindmap:   { label: "根", children: [ { label: "分支", children: [] } ] },
  essence:   ["核心要点"],      // 8-16 条
  highlights:["金句"],          // 3-6 条
  formulas:  ["公式/句型/清单"]  // 知识型内容放这里；雅思写作放可套用句型
};
```
data.js 中条目加 `"fullRef": "XXX_FULL"`，app.js 加载时自动合并。

## 实施步骤
1. 从 ima 拿 media_id（get_knowledge_list）→ `fetch_media_content` 拉全文。
2. **清洗**：去掉「发言人 00:00」行、`![...](url)` 图片链接；修正语音识别错字（如「护身材/后身300」→沪深300、「机型」→基金、A 写成 I 的纠正回 A/C 类）；口语捋通顺。**原则：不删减信息点、不改原意**——只做通顺与纠错，作者的数据错误保留不强行统一。
3. 按时间戳组织 segments（相邻短段可合并，ts 取段首；全片必须从头到尾覆盖）。
4. 生成 summary（5 段左右）、keywords、chapters（按主题聚类，每章 ts + title + gist）、mindmap（3-6 大分支）、essence/highlights/formulas。
5. 写入 `learning-workbench/xx-content.js`（注意：**写前先 Read 一次旧文件或确认不存在**，Write 工具要求先读）。
6. data.js 对应条目加 fullRef（用 Edit；data.js 结构变了就整文件重写）。
7. index.html 的 `<script>` 列表要包含新 content 文件。
8. 校验（见下）。

## 质检清单（必须全过）
```bash
# 1) 语法
node --check app.js data.js *-content.js
# 2) 数据完整性（用 node vm 模拟浏览器合并后断言）
#    - 每个有 fullRef 的条目：segments/summary/keywords/chapters/mindmap/essence 全部非空
#    - chapters 的每个 ts 必须存在于 segments 的 ts 集合（否则点击跳转静默失败）
#    - segments 无空文本、首尾 ts 覆盖 00:00 到结尾
# 3) 本地 http.server 起服务，curl 全部资源 200
```

## 踩坑记录（改代码前必读）
1. **merge 必须覆盖**：app.js 的 mergeFullContent 用 `full[k] !== undefined` 覆盖 item[k]，
   不能 `item[k] === undefined` 才赋值——否则 data.js 里预置的 `essence: []` 会吞掉完整版精华。
2. **chapter ts 必须与 segments 对齐**：chapters 的起始 ts 要能在 segments 里找到，
   否则导读点击无反应（jumpToSegment 找不到目标）。
3. **file:// 兼容**：数据用 `<script>` 注入（data.js / xx-content.js），不能 fetch JSON（file:// 下 CORS 拦截）。
4. **长内容独立文件**：每个条目一个 content 文件，避免 data.js 爆炸；index.html 记得加 script 标签。
5. **语音识别错字**：雅思系列高频错「护身材/后身300/沪深蛋白」→沪深300，「虎铺外/彪虎外/标铺500」→标普500，「机型/机芯」→基金。
6. 转写稿里「发言人 00:00」时间戳是无序的片段号，不能当 ts 用；ts 用正文行首的 mm:ss。

## 设计系统（styles.css 已按 Apple HIG 重做，别回退）
- 纯黑 #000 基底 + 分层表面；四级语义文字色（label-1~4）；强调色 Bright Blue #2997ff（深色背景规范）。
- 动效：cubic-bezier(.25,.1,.25,1)（标准）、(.34,1.56,.64,1)（弹簧）；微交互 140ms、状态切换 220ms、转场 320ms。
- 暗色下不用阴影，用 1px rgba(255,255,255,.08) 发丝边框分层。
- 完整设计 token 见 styles.css 顶部注释。

## 完成标准
- 全部条目五个面板可看：全文（带 ts 跳转）/ 导读 / 思维导图 / 精华 / 笔记（localStorage）。
- 15 条内容约 15 万字通顺全文（理财 6.4 万 + 大作文 4.8 万 + 小作文 3.7 万），全部质检通过。
