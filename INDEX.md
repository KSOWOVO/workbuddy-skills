# Skill 全局索引

> 路由不确定时先查本表，或跑打分脚本：
> `python 90-tooling/skill-router/scripts/skill_match.py "<需求>" --top 3`
> 新增/修改 skill 后**必须**更新本文件。

## 体积预算（违反即需重构）

| 层级 | 预算 | 说明 |
|---|---|---|
| `description` | ≤ 400 字 | **常驻上下文**，每次会话都要付 token，最贵 |
| `SKILL.md` 正文 | ≤ 5 KB | 命中时才加载 |
| `references/` | 不限 | 按需 Read，禁止一次性全读 |
| `scripts/` | 不限 | 直接执行，不读源码 |

## 自创 skill（`agent_created: true`，需同步 GitHub）

| Skill | 一句话 | 关键触发词 | 正文 | 备注 |
|---|---|---|---|---|
| `03-data-analysis/pilot-survey-clean` | 问卷/量表数据清洗 + 信效度 + 可视化 | α 信度、KMO、EFA、CITC、SEM、预调查、清洗、直线作答、Likert、题项分析 | 3.9K | 正大杯/佛山IP论文同流程 |
| `02-knowledge-management/ima-knowledge-upload` | 本地文件写进 ima 知识库 / 读 ima | 存进 ima、入库、同步到 ima、知识库搜索 | 4.5K | 含 `scripts/cos_upload.py`（禁代理） |
| `02-knowledge-management/learning-workbench-sync` | 转写稿 → 学习工作台结构化资产 | 加工视频、整理转写稿、做进工作台 | 6.7K | 含数据契约 + 质检清单 |
| `01-browser-automation/browser-ocr` | 浏览器自动化 + 截图 OCR | 打开网页、点击、截图、验证码、表格图识别 | 6.3K | 含 `scripts/agent-browser.sh`、`ocr.py` |
| `04-content-generation/daily-intel-briefing` | 英文日报 **v6**（宏观·AI·硬件·游戏）IELTS 6.5/高中3500词，PE分位 BUY/HOLD/TRIM | 日报、简报、英文 briefing、智库日报 | 5.0K | 模板已拆 `references/` |
| `90-tooling/skill-github-backup` | 自创 skill 同步 GitHub | skill 备份、同步、开源、上 GitHub | 5.1K | 含 `scripts/sync_to_github.py` |
| `90-tooling/skill-router` | 路由元决策 | 该用哪个 skill、要不要建 skill、该自己写脚本吗 | 4.3K | 含 `scripts/skill_match.py` |

## 预装 skill（只读，不改不同步）

| Skill | 一句话 | 正文 | 何时用 |
|---|---|---|---|
| `market-query` | A股行情/板块/资金流/K线 | 11.6K | 行情类**默认入口**，最轻 |
| `westock-data` | 全品类金融数据（财报/股东/ETF/龙虎榜/产业链/宏观） | 10.1K | 行情之外的一切，先读其 `references/routing-guide.md` |
| `news-search` | 新闻快讯检索 | 5.9K | 只要"消息/新闻"时 |
| `neodata-financial-search` | 自然语言金融搜索 | 17.1K | 自然语言提问、研报舆情 |
| `ifind-finance-data` | 同花顺 iFinD | 8.1K | 智能选股/宏观指标搜索 |

## 目录分类约定

```
01-browser-automation/   浏览器、网页自动化、截图识别
02-knowledge-management/ 知识库、笔记、内容加工
03-data-analysis/        数据清洗、统计、问卷、可视化
04-content-generation/   简报、写作、日报
10- ~ 80-/               预留新功能域（两位数前缀）
90-tooling/              工具、基础设施、元技能（router/backup）
```

新 skill 按功能归入对应分类目录；不在正确目录时先 `git mv` 再同步。

## 路由原则（跨模型、跨会话生效）

1. **目标明确 → 直接加载，不走 router。**
2. **一次性脚本 → 直接写 py，不建 skill。** 这是默认路径。
3. **不确定 → 跑本地打分脚本**（零 LLM 成本），不要凭感觉硬读大文件。
4. **命中后渐进式读取**：正文 → 按需 references → scripts 只执行不读。
5. **金融需求优先级**：market-query > westock-data > neodata > news-search，不用 WebSearch 替代。
