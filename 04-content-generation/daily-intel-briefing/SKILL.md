---
name: daily-intel-briefing
agent_created: true
summary: 生成「全球宏观·AI·科技硬件·游戏」英文日报（v6.1：IELTS 6.5 / 高中 3500 词难度），HTML 主交付：英文界面+每段折叠中文全文翻译；选中单词=结合语境的翻译（词义+所在整句意译）、选中整句走在线意译；英文句 hover 联动中文句高亮（全段落生效含 term 段）；指数卡按 PE 十年分位 30/70 给买入/持有/卖出信号。
description: >
  生成当日全球宏观、AI、科技硬件、游戏产业的英文简报时使用（20-30 分钟阅读量）。
  触发词：日报、简报、英文 briefing、今日资讯汇总、daily briefing、情报简报。
  v6 硬约束（2026-09-02 用户定型）：
  ①语言难度 = IELTS 6.5 / 高中 3500 词：短句高频词，专有名词首次出现加简单英文解释+括号中文，如 rate hike(加息)；
  ②界面英文为主（导航/标题/提示），中文只出现在折叠中文全文翻译区与词汇表；
  ③大盘按用户知识库「PE 十年分位 30/70 定投法」：分位<30→BUY start DCA(绿)、30-70→HOLD(橙)、>70→TRIM/wait(红)，中英双语徽章；不只看一天涨跌；
  ④知识库优先级：Obsidian（C:\Users\13662\Documents\Obsidian\40-个人生活\投资理财\）> ima；
  ⑤HTML 交互：**选中整句(≥3词)→MyMemory 整句意译**；**选中单词→结合语境的翻译**：取所在英文整句→DICT 词义(未命中在线词译)+整句在线意译一起呈现（词义前有"在句中"的整句译文可对照）；**英文句 hover→对应中文句浅亮平滑放大，全段落生效（term 段用占位符保护后照常配对）**；指数卡点击弹走势图；
  ⑥数据优先 MCP 实时行情（westock data_kline / tdx 备用）；涨红跌绿；禁止编造数据（无精确值用 est. 并脚注）。
  详细模板、信息源清单与踩坑记录见 references/brief-template.md（仅在需要出稿时读取）。
---

# 全球宏观·前沿科技·游戏全景智库日报（v6 英文为主版）

## 触发词
每日简报 / 智库日报 / 深度资讯日报 / 英文研报 / 市场全景分析 / daily briefing / intelligence report

## 交付物
- 主交付：同名 `.html`（`Global_Macro_Tech_Gaming_Intel_YYYY-MM-DD.html`），纯内联 CSS/JS 零外部依赖，必须包含：
  1. **选中翻译**：`#dict-pop` 气泡 + `DICT` 423+ 词对象（normWord 归一化）+ mouseup 监听——**整句(≥3英文词或2词且>20字符)直接 MyMemory 整句意译**；**单词→结合语境**：`getContextSentence(anchorNode, sel)` 取所在英文整句 → DICT 词义或在线词译 + 整句在线意译同时展示（"【词】词义 + —整句意译— 完整中文"）；中文选区不弹。
  2. **hover 联动（v6.1 全段落生效）**：加载时按句子把 `.p-en`/`.p-cn` 切分成 `.en-s`/`.cn-s` span——**段落内的 `<span class="term">` 先替换为占位符 `\u0001T{n}\u0001`，切句包 span 后再还原，杜绝 term 段被跳过**（v6 bug：旧实现遇 .term 直接 return，导致新闻板块 hover 全失效）；hover 绑定用 box 级 `mouseover`/`mouseout` 事件委托（`ev.target.closest('.en-s')`）；**中文翻译默认折叠时 hover 自动展开（mouseleave 收回）**，保证点亮可见；`.news` 与 `.macro-block` 都处理。
  3. **指数卡片点击弹走势图**：`openModal(key)` → SVG 折线（近 60 点，红涨绿跌）+ 5/20/40 日涨跌 + **PE 分位行动徽章（pctSignal: <30 BUY / 30-70 HOLD / >70 TRIM）**。
  4. 每条新闻 = `.p-en` 英文段（主，120-180 词，6.5 难度）+ `.cn-box` 折叠中文**全文翻译**（`toggleCn`）。
- 辅助：同名 `.md`（英文+中文摘要），present_files 一次呈现（html 首位）。

## 语言标准（v6 硬约束）
- **难度 IELTS 6.5 / 高中 3500 词**：短句、高频词、避免 7.5+ 级难词；专有名词首次出现用简单英文解释+括号中文（rate hike=加息、bond yield=收益率、equity risk premium=股权风险溢价）。
- **界面英文为主**：导航/区块标题/按钮/提示用英文；中文只出现在折叠中文全文翻译区与词汇表。
- 每段配**完整中文全文翻译**（逐句对应，250-400 字，不是摘要）。
- 全篇无问候、无签名。

## 数据源优先级
1. **westock-mcp `data_kline`** 拉指数日K线：sh000001/sh000300/sh000905/sh000852/sh000688/sz399001/sz399006/hkHSI/us.INX/us.NDX，limit:60-130；红利低波 `csH30269` 无K线→降级纯数据。
2. **知识库（Obsidian 优先）**：`C:\Users\13662\Documents\Obsidian\40-个人生活\投资理财\想提前退休…md`（PE 30/70 定投+卖法）、《存钱=亏钱…md》（M2 稀释/宽基=国运）；ima-mcp 兜底 `search_knowledge`。
3. **WebSearch（Tier-1）**：宏观/美联储/地缘/公司新闻/估值分位。
4. 估值分位冲突时优先交易所口径，脚注注明来源日期。

## 工作流（务必执行）
1. 并行：读 Obsidian 知识库 + westock `data_kline`（批量）+ WebSearch 6 组（美股/A股港股/美债美联储/AI/半导体/游戏）。
2. 用 K 线算近 5/20/40 日涨跌（last/pts[n-1-k]-1），当日涨跌用最新两根 close 差。
3. 估值分位 → 用 pctSignal 逻辑给每指数 买/持有/卖 信号（30/70 法），中文解读讲"现在能不能定投"。
4. 交叉核对数字：MCP > 交易所 > 媒体；无精确值 → (est.)+脚注，绝不编造。
5. 撰写 HTML（v6：英文界面+6.5 难度正文+整句在线翻译+hover 联动+走势弹窗）→ 同名 md → present_files（html 首位）。

## 详细模板
见 `references/brief-template.md`（信息源清单、交互实现细节、踩坑记录、自动化提示词完整模板）。
