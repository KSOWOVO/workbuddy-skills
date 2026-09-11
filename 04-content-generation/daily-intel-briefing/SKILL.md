---
name: daily-intel-briefing
agent_created: true
summary: 生成「全球宏观·AI·科技硬件·游戏」英文日报（v7：IELTS 6.5 / 高中 3500 词难度）。HTML 主交付：英文界面+折叠中文全文翻译；选中翻译三级兜底（词典→在线→页内对应句，离线可用）；句级 hover 联动用 DOM 文本节点包装（无占位符，杜绝乱码）；指数卡 PE 30/70 行动徽章。，HTML 主交付：英文界面+每段折叠中文全文翻译；桌面 mouseup + 移动端 selectionchange 双通道选词翻译（任意设备可用），单词=结合语境词义+整句意译；英文句 hover 联动中文句（v3 比例映射+数字锚点对齐，句数不等也准）；指数卡 PE 十年分位 30/70 行动徽章。
description: >
  生成当日全球宏观、AI、科技硬件、游戏产业的英文简报时使用（20-30 分钟阅读量）。
  触发词：日报、简报、英文 briefing、今日资讯汇总、daily briefing、情报简报。
  v6 硬约束（2026-09-02 用户定型）：
  ①语言难度 = IELTS 6.5 / 高中 3500 词：短句高频词，专有名词首次出现加简单英文解释+括号中文，如 rate hike(加息)；
  ②界面英文为主（导航/标题/提示），中文只出现在折叠中文全文翻译区与词汇表；
  ③大盘按用户知识库「PE 十年分位 30/70 定投法」：分位<30→BUY start DCA(绿)、30-70→HOLD(橙)、>70→TRIM/wait(红)，中英双语徽章；不只看一天涨跌；
  ④知识库优先级：Obsidian（C:\Users\13662\Documents\Obsidian\40-个人生活\投资理财\）> ima；
  ⑤HTML 交互：**桌面 mouseup + 移动端 selectionchange（pointer:coarse/UA 检测，range 定位）双通道选词翻译**——移动端长按选词也能弹气泡；整句(≥3词)整句意译、单词=语境化词义+所在整句意译；英文句 hover→中文句点亮全段落生效（term 占位符保护）；指数卡点击弹走势图；
  ⑥**交互 JS/CSS 必须整体复用 `references/v6-sample-html.html` 的引擎（禁止凭描述重写）**——09-03 曾因重写丢失全部引擎，产出后必须自检（见工作流步骤 7）；
  ⑥数据优先 MCP 实时行情（westock data_kline / tdx 备用）；涨红跌绿；禁止编造数据（无精确值用 est. 并脚注）。
  详细模板、信息源清单与踩坑记录见 references/brief-template.md（仅在需要出稿时读取）。
---

# 全球宏观·前沿科技·游戏全景智库日报（v6 英文为主版）

## 触发词
每日简报 / 智库日报 / 深度资讯日报 / 英文研报 / 市场全景分析 / daily briefing / intelligence report

## 交付物
- 主交付：同名 `.html`（`Global_Macro_Tech_Gaming_Intel_YYYY-MM-DD.html`），纯内联 CSS/JS 零外部依赖。
- **⚠️ 引擎复用铁律（v6.2 起强制）**：HTML 的 `<style>` 引擎段 + `<script>` 交互引擎段（`const IDX` 后的 cardHTML/sparkSVG/openModal/drawChart/pctSignal + DICT/normWord/onlineTranslate/showSelTranslate/getContextSentence/mouseup/selectionchange/sentencePairing/toggleCn）**必须从 `references/v6-sample-html.html` 整体复制（Ctrl+C/V 级），只允许改动：① IDX 数组数据 ② body 正文/新闻/按钮文案 ③ 日期标题**。禁止凭文字描述重写引擎（09-03 教训：重写导致 hover/语境翻译/移动端全部丢失）。
- 交互能力清单（缺一不可，产出后逐项 grep 自检）：
  1. **选中翻译三级兜底**：DICT 命中→离线直出；未命中/整句→MyMemory 在线（输入先做 HTML 实体解码 decodeEnt + 450 字符按句界截断 clip450）；**在线失败或 navigator.onLine===false → offlineSentence()** 显示页内中文全文翻译对应句（零网络）。双通道触发：桌面 mouseup、移动端 selectionchange（pointer:coarse/UA，range 定位，touchstart 收起）。
  2. **hover 句级联动（v7 架构）**：用 `document.createTreeWalker` 遍历 `.p-en`/`.p-cn` 的**文本节点**，按句边界就地包 `<span class="en-s">`/`<span class="cn-s">`（英文切句含缩写合并；中文用 cnSentBounds 按 。！？； 切）——**不再使用任何占位符**（v6 的 \u0001T{n}\u0001 控制字符经 innerHTML 序列化会变成 &#1; 文本，是乱码根源）；对齐沿用 v3 比例映射+数字锚点+单调约束，区间写 data-clo/data-chi；box 级 mouseover/mouseout 委托；中文折叠时 hover 自动展开。

