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
| `03-data-analysis/qdii-quota-check` | 查 QDII/跨境基金当日申购状态与单日上限，按"每天 N 元"筛选能买哪只 | QDII 限购、暂停申购、买不进去、还有哪里能买、单日限额、标普500/纳指/恒生科技 定投额度、跨境额度 | 2.6K | 含 `scripts/quota.py`（跑时加 `PYTHONIOENCODING=utf-8`）；已固化三大坑：节假日误判/额度动态收紧/份额分开算 |
| `02-knowledge-management/ima-knowledge-upload` | 本地文件写进 ima 知识库 / 读 ima | 存进 ima、入库、同步到 ima、知识库搜索 | 4.5K | 含 `scripts/cos_upload.py`（禁代理） |
| `02-knowledge-management/obsidian-vault-digest` | 扫描 Obsidian vault → 生成单文件 HTML 全景解读页（知识地图 SVG + 板块配比 + 体系拆解 + 库体检报告） | 总结知识库、Obsidian 可视化、vault 有什么、知识库体检、做个知识库主页给别人看 | 4.4K | 含 `scripts/scan_vault.py`（全库元数据）、`scripts/extract_points.py`（**转写稿无小标题时必须抽关键句**）；references/design-spec.md（配色/动效/SVG 画法） |
| `02-knowledge-management/learning-workbench-sync` | 工作台「同步数据」操作手册 + 转写稿→结构化学习资产；**自更新契约**（随知识库/数据/功能演化） | 同步数据、更新工作台、拉新资料、加工视频、整理转写稿、做进工作台 | 4.7K | 三种模式决策 + references/sync-playbook.md（数据源快照）+ references/workbench-details.md（设计系统/后端） |
| `01-browser-automation/browser-ocr` | 浏览器自动化 + **双引擎 OCR（PaddleOCR 优先 + RapidOCR 兜底）**；模型不识图时的本地 OCR 兜底 | 打开网页、点击、截图、验证码、表格图识别、识别截图、OCR 兜底 | 4.9K | 含 `scripts/agent-browser.sh`、`ocr.py`；**paddle 必须 3.1.0**（3.3.x 有 oneDNN bug） |
| `04-content-generation/daily-intel-briefing` | 英文日报 **v6**（宏观·AI·硬件·游戏）IELTS 6.5/高中3500词，PE分位 BUY/HOLD/TRIM | 日报、简报、英文 briefing、智库日报 | 5.0K | 模板已拆 `references/` |
| `04-content-generation/exam-wordbank-workspace` | 备考工作台**内置大词库**合成（KyleBing 词表 + ECDict + ipa-dict → 数千词带音标/词性/释义/搭配）+ 单文件 HTML + 资料库分片双向同步 | 背词台、备考台、单词工作台、内置词库、艾宾浩斯、四级/六级/考研/雅思词汇表、词表要带音标、塞 3500 个词 | 3.6K | 含 `scripts/build_words.py`（--kb-file/--target 可调）+ `references/library-sync.md`（page 上传 + database 分片同步 SDK 契约）|
| `04-content-generation/svg-to-animated-gif` | 矢量插画 → **无缝循环 GIF**（无头 Edge 一次截「N 帧网格」+ 整数周期法） | 做成 GIF、生成动图、让插画动起来、animate this SVG、循环动画、动图帧 | 2.4K | 含 `scripts/grid_to_gif.py`（改 CONFIG + `frame(t)` 即可复用）+ `references/loop_math.md`（无缝循环周期对齐）；**别装 cairosvg/playwright，用现成 Edge** |
| `90-tooling/skill-github-backup` | 自创 skill 同步 GitHub | skill 备份、同步、开源、上 GitHub | 5.1K | 含 `scripts/sync_to_github.py` |
| `90-tooling/skill-router` | 路由元决策 + **同类 skill 权重仲裁** | 该用哪个 skill、要不要建 skill、该自己写脚本吗、同类撞车选谁 | 5.4K | 含 `scripts/skill_match.py` + `weights.json`（**调路由改这个，不动脚本**） |
| `05-system-utils/windows-app-official-download` | 取 Windows 软件官方正版包（含地区限制绕过）+ 签名/Defender 双校验 | 下载 Windows/电脑/PC 版、地区问题下不了、商店区域限制、官方无毒包、第三方站不放心、有没有原生 Win 版 | 4.6K | **只下载不代装、不改系统设置**；references/store-forensics.md（判读 `installer.type`）+ verify-playbook.md（Defender ExitCode 2 是权限失败非检出） |
| `90-tooling/skland-endfield-toolkit` | 终末地 MaaEnd 每日自动化 + 森空岛官方 API（签到/账号面板/协议空间精调） | MaaEnd、终末地自动化、每日任务、森空岛签到、协议空间、账号面板、skland token、preaction | 2.7K | 生产已部署于 `~\.workbuddy\skland_tools\`（含 README 与修复入口）；references/skland-api.md（端点链+签名算法+数据结构） |
| `05-system-utils/local-llm-ollama-setup` | Windows 装本地小模型（Ollama 引擎 + Qwen3）并接入 WorkBuddy 本地模型功能 | 本地模型、本地大模型、装个小模型、Ollama、离线跑模型、qwen3、接模型到 WorkBuddy、显存不够选哪个模型、自托管 LLM | 5.0K | **按显存选型**（4G→4B/8G→8B）；非管理员走便携版绕开 NSIS；三大环境变量 `KEEP_ALIVE=0`+`CONTEXT_LENGTH=8192`+`KV_CACHE_TYPE=q8_0`；references/pitfalls-and-env.md（18 条实战坑 + 验收清单） |

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
04-content-generation/   简报、写作、日报、插画动图（GIF）
05-system-utils/         系统工具：软件下载取证、官方包校验、安装器安全核验、本地模型部署（Ollama/LLM）
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
