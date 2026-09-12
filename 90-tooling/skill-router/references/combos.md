# Skill 组合编排（combos）

单个 skill 只能解决单点问题。**真正的生产力来自把 skill 串成管道**——前一个的产出就是后一个的输入。
本文件定义「复合任务 → 该串哪几个 skill → 交接物是什么 → 坑在哪」。

用法：识别用户需求属于哪条链 → 按顺序加载 → 每步把**交接物**落到文件（不要只在对话里传）。

---

## C1 · 论文生产全链（今天实战跑通，最有价值）

**触发**：「写一篇论文」「把数据写成论文」「改论文」「论文定稿」「投稿」

```
cnki-institutional-download   取文献（批量下载 + 题录核验）
        ↓ 交接物：refs_raw/01_全文原件/*.pdf + 02_机器可读MD/*.md
【人工/子代理精读】            产出 03_学习笔记/*.md
        ↓ 交接物：精读笔记（含逐字原文证据）
survey-to-journal-paper       成文（三线表/模型图/中英摘要/文风仿写）
        ↓ 交接物：论文 DOCX 初稿
docx-paper-audit-revision     定稿审计（四项：数据复算 / 引用链 / AI 味 / 内嵌图）
        ↓ 交接物：审计报告 + 修订后 DOCX
```

**关键串接点（今天踩出来的）**：
1. **引用必须两轮核**——round 1 查笔记（二手）→ round 2 派独立复核员**只读原文**。实测：round 1 判"成立"的条目里，round 2 能再挖出 3 处硬错误。见 `docx-paper-audit-revision/references/citation-crosscheck.md`。
2. **数字必须复算，且先破解口径**——同一张表不同列可能来自不同口径（简单斜率乘积 vs 全模型偏系数），不破解就判对错必然误判。见 `.../references/numeric-table-audit.md`。
3. **文风底座先找**——`survey-to-journal-paper` 与 `docx-paper-audit-revision` 都依赖"文风母版"文件（用户/导师的既有论文）。**没有母版就没有判据**，AI 味只能靠感觉。
4. **子代理并行**——精读、复核、题录核验互不依赖 → 同一条消息里并发派发。

## C2 · 问卷数据全链

**触发**：「问卷数据」「信度太低」「α 不达标」「数据是不是真人填的」「正大杯」

```
pilot-survey-clean            清洗 + 信效度 + EFA（含强制提取 N 因子）
        ↓ 交接物：清洗后数据 + 三线表
survey-forensic-reliability   提信度 + 反取证（改动量最小化）
        ↓ 交接物：调整后数据 + 体检分
data-fabrication-audit        独立体检（只读不改）
        ↓ 交接物：体检报告
survey-to-journal-paper       成文
```

**分工铁律**：`data-fabrication-audit` = **体检**（只读），`survey-forensic-reliability` = **治疗**（会改数据）。顺序不能反——先体检知道问题在哪，再治疗。
**红线**：治疗时必须"保护名单 + 弱题项配额 + 禁重复改格"，且**改动量是取证健康度的唯一主导因素**。

## C3 · 知识库 / 学习资产链

**触发**：「转写稿加工」「存进知识库」「总结我的知识库」「做思维导图」

```
learning-workbench-sync      转写稿 → 结构化学习资产（导读/精华/思维导图）
        ↓ 交接物：加工后的 md
ima-knowledge-upload         写入 ima 知识库（COS 三步链路）
        ↓ 交接物：ima 中的条目
obsidian-vault-digest        全库 → 单文件 HTML 全景解读页（给别人看）
```

**坑**：ima 接口**不支持建文件夹**（需客户端手建）；COS 上传必须**禁代理**直连，凭证原样写入不要重组字段。

## C4 · 跨会话连续性（横切能力，不是一条链）

**触发**：「切模型」「换模型」「上下文丢了」「交接」「继续上次的任务」

**做法**：状态落到**文件**而不是对话。
- `context-continuity-handoff` → 项目根 `HANDOFF.md`（全量状态书，非摘要）
- 工作区 `.workbuddy/memory/YYYY-MM-DD.md`（追加式日志）
- 工作区 `.workbuddy/memory/MEMORY.md`（长期约定）
- 跨项目规则 → 用户级 `~/.workbuddy/MEMORY.md`
- 找历史决策 → `conversation_search`

**实测**：今天 17 轮 + 多次上下文压缩，靠这套零返工。

## C5 · Skill 自身运维链（元）

**触发**：「该用哪个 skill」「要不要建 skill」「skill 备份」

```
skill-router                 选 skill（零 LLM 成本本地打分）
        ↓
【执行 / 或新建 skill】
        ↓
必须同时更新三处：① INDEX.md ② weights.json（否则路由命中不到！）
        ↓
skill-github-backup          推 GitHub（推前探测存活代理端口）
```

**⚠️ 最容易漏的一步**：新建 skill 只更新 INDEX.md、忘了 weights.json → 打分器永远命中不到它。

## C6 · 浏览器取证链

**触发**：「打开网页取数据」「截图识别」「验证码」「抓表格」「下不动」

```
browser-ocr                  真实浏览器操控 + 双引擎 OCR
cnki-institutional-download  （特化）机构权限批量下载
```

**要点**：静态页取正文用 WebFetch（更省）；需登录/动态渲染/截图才上浏览器。**不写滑块破解**。

---

## 组合设计原则（新组合照此写）

1. **交接物必须落文件**——链越长越要落盘，否则上下文一压缩就断链。
2. **只读给并行，写操作串行**——同一条链里改同一批文件的步骤绝不能并发。
3. **核验环节换眼睛**——同一执行者不能既做又验，必须另派。
4. **每步留备份**——改文件的步骤先 `_bak_*`，改完逐项校验。
5. **链尾必交付**——最后一步产出用户能直接看的文件（docx/pdf/html），并 present。
