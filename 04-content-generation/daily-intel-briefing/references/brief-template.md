# 日报：信息源、踩坑清单与自动化提示词模板（v6）

> 从 SKILL.md 拆出的细节章节，仅在需要时读取。**v6 = 2026-09-02 用户定型版**。

## ⚠️ v6 大改版说明（先读这段）

用户 2026-09-02 对 v5 提出以下全部意见，**v6 必须全部落实**：

1. **词汇难度降到「高中 3500 词 / IELTS 6.5」基准**，不要 7.5-8.5 难词堆砌。
   - 用短句 + 高频词；专有名词（Fed/Jackson Hole/equity risk premium 等）第一次出现时用**简单英文解释 + 括号中文**，如 `rate hike (加息)`、`bond yield (债券收益率)`。
   - 正文示范（照这个感觉写）：*"Now the market thinks there is a 55–60% chance of a rate hike in September. The 2-year bond yield rose to 4.35%, and gold fell about $100."*
2. **大盘估值不要只看一天涨跌**——按知识库价值观（Obsidian 为准、ima 其次）：
   - **PE 十年分位 30/70 定投法**是唯一估值决策框架：分位 <30 低估可分批定投（Buy/start DCA）；30-70 正常持有等待（Hold）；>70 高估不追高、等回落（Trim/wait）。
   - 每张指数卡/弹窗都要给出这个**行动信号（中英双语徽章）**，点位与当日涨跌只是背景信息。
   - 中文解读要讲清「现在能不能定投、该买什么等什么」，参考知识库：国内宽基用估值定投做波段；标普500/纳指100 用普通定投长持不择时。
   - **知识库读取优先级：Obsidian（C:\Users\13662\Documents\Obsidian\40-个人生活\投资理财\）> ima**。Obsidian 的《想提前退休…投资方法》讲 PE 30/70 定投法 + 卖法（>70 后每涨 10 分位卖 30%）；《存钱=亏钱》讲 M2 稀释、买宽基=买国运。
3. **选中翻译交互改版（关键）**：
   - **选中的是一整个句子（≥3 个英文词或长短语）→ 整句走在线翻译**（MyMemory，上下文意译），**不再逐词查内置词典**——之前"选中整句却只显示某个已收录单词的翻译"是 bug，已修。
   - 选中**单个单词/短词组** → 先查内置 DICT（423+ 条），未命中再走在线。
   - MyMemory 整句翻译质量已实测可用（如"数据中心 AI 芯片需求强劲带动公司净利润大幅增长"）。
4. **hover 联动高亮（新功能）**：鼠标移到英文句子 → 下方对应中文句**浅亮 + 轻微平滑放大**（`.en-s:hover` ↔ `.cn-s.lit`，句子级 span 配对，加载时按句号/问号/感叹号切分）；不得与选中翻译冲突（hover 用 mouseenter/mouseleave，翻译用 mouseup，事件不互斥）。
5. **界面英文为主**：导航、区块标题、按钮、提示语用英文（如 `📊 Market Overview`、`🤖 AI Frontier`、`中文全文翻译` 按钮可保留中文因为它是中文翻译入口）；中文只出现在：中文全文翻译区、词汇表双语释义。
6. AI 翻译：Google gtx 端点本机不通、Lingva 实例全部不可用 → **只用 MyMemory**，不要硬接别的。

## 国外信息源（2026-09-01 实测可用性，自动化时优先直连）
- **WebFetch 可直连（实测通过）**：
  - `gamesindustry.biz`（游戏行业，含 Newzoo/Sensor Tower 数据，最优先）✅
  - `theverge.com/tech`（科技/消费电子）✅
  - `techradar.com`（硬件/消费电子）✅
  - `anandtech.com`（已转型论坛，CPU/SoC 讨论活跃）✅
- **WebFetch 直连失败（被墙/超时，勿浪费时间重试）**：reuters.com、ft.com ✗
- **绕过方案**：Reuters/FT/WSJ/Economist 的资讯用 **WebSearch 英文关键词**抓（走服务端，不受本机网络限制）；WebFetch 失败不代表搜索不到。
- 数据源优先级：WebFetch 可直连源 > WebSearch（英文关键词 > 中文聚合）> MCP 行情。
- 常用英文检索词：`"stock market today"`、`"Fed rate hike odds"`、`"semiconductor news"`、`"AI model release"`、`"gaming industry news"`。

## 踩过的坑
- **MCP 行情比估算准**：v1 曾估纳指100 日涨跌 -0.5%，westock 实际 +0.08% —— 指数日涨跌必须用 MCP/交易所数据，别用板块代理值。
- **校验 HTML 内 IDX 数组的切片边界（2026-09-02 踩坑，3 次失败后定位）**：从 HTML 提取 `const IDX = [...]` 用 `new Function('return (' + slice + ')')()` 求值时——① 起点 `[` 在 `indexOf('const IDX = [')` 的 **i0+12**；② 终点 `indexOf('];')` 返回 `]` 位置，slice 终点取 **i1+1**；③ 必须整体括号包住表达式（`return` 后换行触发 ASI）。**不要在 Bash 内联 `node -e` 里写提取逻辑**（Windows 引号污染），写独立 `_validate.js` 再执行。
- **红利低波指数代码是 `csH30269`**（中证红利低波），PE 8.59、股息率 4.24%；无实时K线 → 卡片降级处理。
- **港股恒生指数 MCP 返回 `pe_ratio:0`**（无 PE），需用 WebSearch 补（雪球周报 ~12x/77% 分位）。
- **`data_kline` 的 `last` 字段 = 最新价/收盘价**，首条即当日；区间涨跌幅 = `last / pts[n-1-k] - 1`。
- **v6 选中翻译策略（2026-09-02 定型）**：
  - mouseup 里先数选中英文词数：`wordCount >= 3`（或 2 词且长度>20）→ **整句在线翻译**，显示 `Sentence / 整句` 标签 + MyMemory 意译结果；单词级才查 DICT。
  - DICT 423+ 条（公司/产品/人名/术语/高频词）；未命中单词再走 MyMemory。
  - MyMemory：`fetch('https://api.mymemory.translated.net/get?q='+encodeURIComponent(q)+'&langpair=en|zh-CN')`，CORS `*` 开放，8s 超时。
  - Google gtx / Lingva 在本机不可用 → 只用 MyMemory。
  - 离线兜底：提示看「中文全文翻译」。
- **句子 hover 联动实现要点（2026-09-02 定型）**：
  - 加载时把 `.p-en` 与配对 `.p-cn` 按句子切分（英文正则 `/(?<=[.!?])\s+(?=[A-Z])/`，中文按 `。！？；`），用 `<span class="en-s" data-i="n">` / `<span class="cn-s" data-i="n">` 包裹；
  - 段落内含 `<span class="term">` 时跳过（保翻译功能优先，不重建 innerHTML）；
  - CSS：`.en-s:hover{background:rgba(37,99,235,.10)}`，`.cn-s.lit{background:rgba(14,159,79,.16); font-size:1.04em}`（浅亮+平滑放大）。
- **index 代码 vs K线**：westock `data_kline` 支持 `codes` 批量（最多实测 4 个一次成功）；美股用 `us.INX/us.NDX` 而非 `us.IXIC`。
- 用户知识库：**Obsidian 优先**（`C:\Users\13662\Documents\Obsidian\40-个人生活\投资理财\`），关键词「PE 分位 定投 宽基」；ima 是备份（同批转写稿 8/31 上传）。《想提前退休》= PE 30/70 定投法+卖法；《存钱=亏钱》= M2 稀释+宽基=国运。
- 其余坑（口径、时点、宏观人物及时更新、游戏并购找公告）同前。

## 自动化每日出稿（提示词模板，直接复用）

```
你是 Elite Global Intelligence Analyst + 学术英文编辑（写作难度：IELTS 6.5 / 高中 3500 词基准）。生成 {{YYYY-MM-DD}} 的「全球宏观·前沿科技·游戏全景智库」深度日报，交付单一自包含 HTML 文件 `Global_Macro_Tech_Gaming_Intel_{YYYY-MM-DD}.html`。

# 语言（v6 硬约束）
- **英文为主、难度 IELTS 6.5 / 高中 3500 词**：短句 + 高频词；专有名词首次出现用简单英文+括号中文注解（如 rate hike(加息)、bond yield(收益率)、equity risk premium(股权风险溢价)）。禁止 7.5+ 级生僻词堆砌。
- 中文只出现在：折叠中文全文翻译区（每段逐句对照 250-400 字）、词汇表。界面（导航/标题/提示）英文为主。
- 不编造数字；估值拿不到 → (est.) + 脚注。

# 数据源（强制）
1. westock-mcp `data_kline` 批量拉指数日 K 线：sh000001 / sh000300 / sh000905 / sh000852 / sh000688 / sz399001 / sz399006 / hkHSI / us.INX / us.NDX，limit:60-130。红利低波 H30269 无实时 K线，直接给收盘数据。
2. 知识库：优先读 Obsidian `C:\Users\13662\Documents\Obsidian\40-个人生活\投资理财\想提前退休…投资方法…md` 与《存钱=亏钱…md》取 PE 30/70 定投框架；ima-mcp 兜底检索"指数基金 宽基 理财"。
3. WebSearch 6 组（美股收盘 / A股港股 / 美债美联储ERP / AI大厂 / 半导体 / 游戏）。
4. 估值分位（十年 PE-TTM）：沪深300 13.83x 72.5%；中证500 33.83x 80%；中证1000 44.25x ~78%(est.)；创业板 56.59x 46%；科创50 143.84x 92%；恒指 ~12.0x 77%；标普500 25.6x 61%；纳指100 30.4x 48%（数据时点与来源在脚注标明）。

# 5 大板块
## Section 1 Market Overview（英文标题）
- 国内宽基 8 卡（SH Comp/深成指/CSI300/CSI500/CSI1000/ChiNext/STAR50/红利低波）+ 港股境外 4 卡（HSI/HSTECH/S&P500/NDX100）。每卡：英文名+中文名 / 点位 / 当日涨跌 / PE / **10y 分位** / **行动徽章（pctSignal 自动给）**：
  - 分位<30 → `BUY zone · start DCA`（绿，可分批定投）
  - 30-70 → `HOLD · wait`（橙，持有等待）
  - >70 → `TRIM / wait`（红，不追高等回落）
- 中文解读段：按 PE 分位法讲「现在能不能定投、买什么等什么」（国内宽基看波段、美股宽基普通定投长持）；宏观综述 2 段（全球：美联储/地缘/油价；中国：A股/港股/政策），每段英文主体 + 折叠中文全文翻译；强势板块快讯。
- 卡片内嵌 mini sparkline；点击弹 SVG 走势图（近 60 日）+ 5/20/40 日涨跌 + 估值徽章。

## Section 2-4 AI / Hardware / Gaming（英文标题）
每条 = `编号 + English Title` + 英文段落（主，120-180 词，IELTS 6.5 简单学术语体）+ **折叠中文全文翻译**（逐句对应，按钮"中文全文翻译"）+ Source。

## Section 5 Vocabulary
6-8 条高中-大学常用词/搭配（Word | 简单英文释义 + 中文 | 原文例句）。

# 交互（JS 内嵌，照 v6 实现）
- 选中翻译：单词语典秒查（DICT 400+）→ 未命中 MyMemory；**选中整句（≥3词）直接整句 MyMemory 意译**，不逐词。
- hover 联动：英文句 hover → 对应中文句浅亮平滑放大（句子 span 配对）。
- 指数卡点击弹走势图；涨红跌绿（A股），估值色：红 over/橙 mid/绿 cheap。

# 工作流
1. 并行：读 Obsidian 知识库 + westock data_kline + 6 组 WebSearch。
2. K 线算近 5/20/40 日涨跌（last/pts[n-1-k]-1）。
3. 生成 HTML（v6 语言+交互）；同名 md（英文+中文摘要）。
4. present_files 一次（html 首位）。

# 交付
- `Global_Macro_Tech_Gaming_Intel_{YYYY-MM-DD}.html`（自包含、离线可用）。
- 同名 `.md`。present_files 一次。
```
