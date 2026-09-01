---
name: daily-intel-briefing
summary: 生成「全球宏观·前沿科技·游戏全景智库」英文深度日报（IELTS Band 7.5–8.5 / CEFR C1，英文约80%+中文摘要约20%），覆盖全球大盘量化估值、AI前沿、半导体硬件、游戏产业，并附雅思学术词汇表。用户说"每日简报/智库日报/深度资讯/英文研报"时使用。
description: >
  当用户要求生成当天的全球宏观、AI、科技硬件、游戏产业的深度英文简报（20-30分钟阅读量，约2500-3500词）时使用。
  严格遵循模板：5大板块（量化估值矩阵表 / 宏观综述+行业轮动 / AI深度报道 / 半导体硬件 / 游戏产业 / 雅思词汇表），
  英文约80%篇幅、中文结构化摘要约20%，英文须达 IELTS Band 7.5-8.5（C1）学术语体（倒装、分词、名词化、AWL词汇）。
  数据只取 Tier-1 来源（见正文），先用并行 WebSearch 检索过去24-72小时事件，再逐项核实数值（指数收盘、涨跌幅、P/E、分位数、利率、公司业绩），
  禁止编造数据；拿不到精确值的用 (est.) 标注并加脚注。
agent_created: true
---

# 全球宏观·前沿科技·游戏全景智库日报（英文）

## 触发词
每日简报 / 智库日报 / 深度资讯日报 / 英文研报 / 市场全景分析 / daily briefing / intelligence report

## 交付物
单个 `.md` 文件（日期命名，如 `Global_Macro_Tech_Gaming_Intel_2026-09-01.md`），写入当前工作目录，最后用 present_files 呈现。

## 输出结构（严格按此模板，不可省略板块）
1. 标题行 `# 🌐 Global Macro, Tech & Gaming In-Depth Intelligence | 全球宏观·前沿科技·游戏全景智库`
   + `*Date: YYYY-MM-DD | Reading Time: ~25 mins | Lexical Level: IELTS Band 7.5–8.5*` + 数据口径注（覆盖时窗、估值分位来源、(est.) 标注规则、免责声明）。
2. **Section 1 全球大盘与量化估值**：
   - 1.1 核心量化矩阵表：S&P 500 / Nasdaq 100 / CSI 300 / Hang Seng 四行 × 列（Daily Return、P/E TTM/Fwd、10Y Percentile、Risk Premium、EN/CN 驱动）。表下加脚注说明各数值来源（Wind/雪球/FactSet 等）。
   - 1.2 宏观综述：2-3 段 IELTS 级英文分析（货币政策、收益率、板块轮动、机构资金逻辑）+ `- **CN 核心提炼**:` 2-3 句。
   - 1.3 强势主题指数：3-6 条，每条 `- **[Sector (Ticker)]**: Daily ±X.XX%, P/E XX.X.` + Catalyst (EN) + 中文归因。
3. **Section 2 AI 与前沿算法**：2.1/2.2/... 每条含 In-Depth Report (EN, 150-200词)、Executive Summary (CN, 2-3句)、Source。覆盖过去24h全部重要动态（模型发布、论文、商业化、监管），末尾可加"其他重要AI动态"快讯清单。
4. **Section 3 企业科技与半导体**：同上格式，覆盖制程/晶圆厂/云基建/反垄断/存储/地缘政策，可加 Hardware Briefs。
5. **Section 4 游戏产业**：同上格式，覆盖财报、并购、引擎、平台分发、预售数据。
6. **Section 5 雅思词汇表**：8-10 个 C1/C2 或 AWL 词汇/搭配表（Word | 语境释义 EN+CN | 原文例句），例句必须从本日报正文摘取。
7. 结尾：`*Compiled YYYY-MM-DD | Tier-1 sources: ...*`。

## 语言标准（硬约束）
- 英文：IELTS Academic Band 7.5–8.5，正式学术语体；用倒装、分词短语、名词化、AWL 词；禁口语化/网络俚语/寒暄语。
- 中文摘要：2-3 句精炼，含关键数字与因果。
- 全篇无问候、无签名，直接以 Markdown 文档开始。

## 数据检索（Tier-1 来源清单）
- 宏观量化：Bloomberg、FT、The Economist、Reuters Finance、WSJ、TradingView、Multpl、Yardeni、新浪财经、华尔街见闻、雪球估值周报、Wind 行情指标（含 P/E TTM + 10Y 分位）。
- AI：arXiv、OpenAI/Anthropic/DeepMind/Meta AI 官方、MIT Tech Review、Ars Technica、The Information、TechCrunch、机器之心/量子位类中文聚合。
- 硬件：AnandTech、Tom's Hardware、IEEE Spectrum、Reuters Tech、TrendForce、集微网、半导体行业观察、DailyStock。
- 游戏：GamesIndustry.biz、GDC Vault、Game Developer、IGN、PC Gamer、Newzoo、Kotaku、The Verge、官方 IR。

## 工作流（15+ 步，务必执行）
1. **并行 WebSearch 4-6 组**（同一条消息内多路并行）：
   a) 美股/欧股/亚太收盘（"S&P 500 Nasdaq close YYYY-MM-DD"）
   b) A股/港股行情（"沪深300 上证指数 今日收盘 行情"）
   c) 美债收益率/美联储/ERP（"10-year treasury yield equity risk premium"）
   d) AI 大厂（"OpenAI Anthropic DeepMind news"）
   e) 半导体（"TSMC Intel Samsung news"）
   f) 游戏（"gaming industry news studio acquisition"）
2. 视缺口补搜 2-3 组：估值分位（"Nasdaq 100 forward P/E percentile"、"沪深300 市盈率 分位数"）、重大事件核实（如换帅/收购/财报数字）。
3. **交叉核对每个数字**：同一指标至少 1 个独立来源；冲突时取权威源（官方财报 > 交易所 > 主流媒体）并在脚注说明。拿不到精确值 → (est.) + 脚注，**绝不编造**。
4. 判断"过去24h vs 一周背景"：24h 内事件写实写透，更早但仍在发酵的事件（如当周财报、央行会议）作为背景带入分析，标注日期。
5. 撰写 → 自查字数（EN 总量 2500-3500，每条 In-Depth Report 150-200 词）。
6. present_files 呈现 .md。

## 踩过的坑
- 中文聚合源（新浪/华尔街见闻）数据质量高但口径可能不同（如 WTI 不同交割月价格不同），写报告前先统一口径（注明交割月/日期）。
- 同日不同来源的涨跌幅可能因收盘/结算时点差异而不一致（如 COMEX 黄金 -0.72% vs +0.34%），选主流媒体（新华社/路透）口径并在文中注明日期。
- 估值分位来源口径差异大（5Y/10Y/全历史、TTM/Fwd），**必须在脚注写清口径**，矩阵内统一用 10Y TTM 分位。
- 美联储/利率等宏观背景变化快（如主席更替、加息预期），务必搜索最新人物与政策，不要用过时认知。
- 游戏产业新闻来源鱼龙混杂（自媒体猜测 vs 官方公告），并购/财报数字必须找公告或 Tier-1 媒体（CNBC、Reuters、公司 IR）确认。
