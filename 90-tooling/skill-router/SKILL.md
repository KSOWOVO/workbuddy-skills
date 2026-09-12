---
name: skill-router
agent_created: true
description: >
  Skill 路由与元决策助手。当用户需求**不确定该不该用 skill、不确定用哪个 skill、或纠结要不要新建一个 skill** 时使用。
  触发词：该用哪个 skill / 有没有现成的技能 / 要不要建个 skill / 用 skill 还是自己写脚本 / 搜索一下 skill / 找 skill / 有没有相关能力 / 这个要不要存成 skill。
  也适用于需求横跨多个领域（如既要抓数据又要出报告）、或多个金融数据 skill 之间撞车需要定优先级时。
  不适用于：目标 skill 已经明确的情况（此时直接加载那个 skill，不要先读本文件，避免多花一次调用）。
summary: 在「用哪个 skill / 用不用 skill / 要不要建 skill」三种元决策场景下给出路由判断，并提供零 LLM 成本的本地打分脚本，避免盲读大体积 SKILL.md 浪费 token。
---

# Skill 路由

## 铁律：目标明确就直接加载，不要先读我

如果你已经知道该用哪个 skill，**直接加载它**。本文件的唯一价值是消除"不确定"，
在确定的场景里读它纯属浪费 token。

## 三步决策

**第 1 步：先问「这是不是一次性的？」**
一次性、<40 行、没有可复用的坑（环境配置/鉴权/编码/代理）→ **直接写脚本，不建 skill**。
这是默认路径，不是偷懒。建 skill 的成本是长期维护，收益只在重复第 3 次之后才显现。

**第 2 步：不确定就跑本地打分（零 LLM 成本，约 15 行输出）**

```bash
env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY \
  "C:/Users/13662/.workbuddy/binaries/python/versions/3.13.12/python.exe" \
  "C:/Users/13662/.workbuddy/skills/90-tooling/skill-router/scripts/skill_match.py" \
  "<用户的原始需求原文>" --top 3
```

- 最高分 ≥ 3.0 → 加载它。
- 最高分 < 3.0 → 没有真匹配，**直接写脚本，不要硬套、不要新建**。

**第 3 步：命中后按渐进式披露读取**
先读 SKILL.md 正文 → 只有正文里明确指向 `references/` 的细节才去读。
**禁止**一口气把 references 全读进来。脚本（scripts/）直接执行，不要读源码。

## 复合任务：skill 要**串成管道**，不是单点调用

单个 skill 只解决单点问题。真实需求往往是复合的，**前一个 skill 的产出就是后一个的输入**。
6 条已固化管道（完整定义 / 交接物 / 坑详见 **`references/combos.md`**）：

| 链 | 触发场景 | 串联顺序 |
|---|---|---|
| **C1 论文生产** | 写论文/改论文/定稿/投稿 | `cnki-institutional-download` 取文献 → 精读 → `survey-to-journal-paper` 成文 → `docx-paper-audit-revision` 定稿审计 |
| **C2 问卷数据** | 信度/α/数据真伪/正大杯 | `pilot-survey-clean` 清洗 → `survey-forensic-reliability` 提信度 → `data-fabrication-audit` 体检 → 成文 |
| **C3 知识库** | 转写稿加工/入库/可视化 | `learning-workbench-sync` 加工 → `ima-knowledge-upload` 入库 → `obsidian-vault-digest` 出全景页 |
| **C4 跨会话** | 切模型/交接（横切） | `context-continuity-handoff` + 工作区 memory + `conversation_search` |
| **C5 skill 运维** | 选/建/备份 skill | `skill-router` 选 → 执行 → ①INDEX ②weights.json → `skill-github-backup` |
| **C6 浏览器取证** | 抓取/下载/OCR | `browser-ocr` / `cnki-institutional-download`（特化） |

**串接三条铁律**：①交接物**落文件**（链越长越要落盘，否则上下文一压缩就断链）②核验必须**换眼睛**（同一执行者不能既做又验）③只读可并行、**改同一批文件必须串行**。

## 场景路由表

| 需求场景 | 优先 skill | 备注 |
|---|---|---|
| 问卷/量表：α 信度、KMO、EFA、CITC、SEM、清洗 | `pilot-survey-clean` | 正大杯 / 佛山IP论文同流程 |
| 文件写进 ima 知识库、读 ima 条目 | `ima-knowledge-upload` | COS 上传需禁代理 |
| 视频转写稿 → 学习工作台结构化资产 | `learning-workbench-sync` | |
| 网页抓取/截图/验证码/表格图识别 | `browser-ocr` | 纯静态页用 WebFetch 即可，别上浏览器 |
| 英文深度日报（宏观·AI·硬件·游戏） | `daily-intel-briefing` | 正文精简版，模板在 references/ |
| 自创 skill 备份 GitHub | `skill-github-backup` | 详细流程在 references/ |

### 同类 skill 撞车：交给权重仲裁，不要靠硬编码优先级

多个 skill 都能沾边时（如 5 个金融 skill），打分器用权重模型选对的那个：

    final = (关键词分 × 域专长乘子 + 域命中加分) × 自创加成 − 体积惩罚

- **域专长乘子**：`weights.json` 定义每个 skill 在各能力域的擅长程度（如行情域 `market-query=1.8`）。
- **域命中加分**：命中域触发词就给专长 skill 加分，解决"营收/净利润"这类冷僻词误判为无匹配。
- **自创加成** ×1.15；**体积惩罚**每 KB −0.06，抑制动辄 17KB 的重型 skill（省 token 关键一环）。

**调路由只改 `weights.json`，不动脚本。** 实测各类需求各自选对：行情→`market-query`、财报→`westock-data`、新闻→`news-search`、自然语言→`neodata-financial-search`、改论文→`docx-paper-audit-revision`、知网下载→`cnki-institutional-download`。
行情类**不要**用 WebSearch 替代（数据不准）。

## 什么时候才建新 skill

同时满足 ≥2 条才建：
- 同一类任务已经做过或明确会再做（≥3 次）
- 有**非显然的坑**值得固化（代理、鉴权、编码、特定 API 链路、目录约定）
- 流程 ≥5 步且顺序敏感
- 需要捆绑脚本/模板/资产

只满足"做过一次"→ **不建**。写进当日 memory 就够了。

## 全局索引

完整清单见 `C:/Users/13662/.workbuddy/skills/INDEX.md`（skill 名 / 一句话 / 触发词 / 体积 / 是否自创）。

**新增或改动 skill 后必须同步更新两处，缺一个路由就失准**：
1. `INDEX.md` —— 清单表（一句话 + 触发词 + 体积）
2. **`weights.json` —— 加一个能力域**（triggers + 该 skill 权重 1.8）

⚠️ 只改 INDEX.md 是不够的：打分器只认 `weights.json` 里的域，漏加 = 这个 skill **永远命中不到**，等于白做。
（2026-09-12 实测：19 个自创 skill 曾有 12 个完全没进权重表。）改完**必须实测几条真实查询**验证命中，分数应远超阈值 3.0。
