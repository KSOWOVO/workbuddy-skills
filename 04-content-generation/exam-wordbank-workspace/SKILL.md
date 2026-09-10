---
name: exam-wordbank-workspace
description: 为背词/备考类个人工作台合成**内置大词库**（数千词，含音标·词性·释义·搭配）并产出零依赖单文件 HTML，可选接入资料库数据表实现多设备双向同步。触发词：背词台、备考台、单词工作台、内置词库、艾宾浩斯、四级/六级/考研/雅思词汇表、词表要带音标、做成一个能背单词的网页、给工作台塞 3500 个词。不适用于：只要一份单词表不做页面、纯词频统计、已有词库只需导入。
agent_created: true
---

# 内置大词库的备考工作台

用户说"给我内置 N 个词"时，**不要自己逐条写词**（N≥1000 时输出量爆炸且易出错）——走"开源词库合成"路线。

## 一、词库合成（`scripts/build_words.py`）

三源合并，各司其职：

| 用途 | 数据源 | 获取方式 |
|---|---|---|
| 词表范围（考纲词） | KyleBing/english-vocabulary | `raw.githubusercontent.com/KyleBing/english-vocabulary/master/` + URL-encode 文件名，如 `3 四级-乱序.txt`（TAB 分隔：`word\t释义`） |
| 音标/释义/词频/词形 | ECDict | `raw.githubusercontent.com/skywind3000/ECDict/master/ecdict.csv`（66MB，**易超时截断，截断版仍可用**） |
| 标准 IPA 音标 | open-dict-data/ipa-dict | `data/en_UK.txt`（英式，注意**不是 en_GB**）、`data/en_US.txt` |

字段优先级：
- **音标**：ipa_UK → ipa_US → ECDict（后者是非标准字符，需把 `ә→ə`、`є→ɛ`、`'→ˈ` 再包 `/`）
- **词性+释义**：ECDict `translation`（`\n` 清洗为 `；`，截断到 58 字符）→ KyleBing 释义
- **常考搭配**：ECDict 里含空格的**真实短语词条**（按 collins/oxford/frq 排序取一条）→ 退化用 `exchange` 解析的词形（复数/过去式/三单）→ 都没有就留空，**不要编造搭配**
- **选词**：先按 ECDict `tag` 含 `cet4` 优先，再按 `frq` **升序**（frq 是排名，越小越常用；=0 排最后），取前 N；输出顺序仍按词表原顺序以保持乱序背词体验

运行：
```bash
PYTHONIOENCODING=utf-8 python scripts/build_words.py   # 产出 words.json，格式 [[word, ph, pos, cn, col], ...]
```
脚本内 `KB_FILE` / `TARGET` 可调（六级换成 `4 六级-乱序.txt`）。

## 二、页面要点（单文件 HTML）

- 词表整块注入：模板里留 `var WORDS_RAW = /*__WORDS_JSON__*/[];`，构建时字符串替换成 JSON（3500 词约 368KB → 成品约 460KB，远低于资料库 50MiB 上限）。
- 背词核心：`box`(0–5) ↔ 间隔 `[1,2,4,7,15,30]`；答对 `box+1`、`due = today + INTV[box-1]`（**第 1 次认识 = 1 天后，这里最容易 off-by-one**）；答错 `box-1` + 回队尾 + 收进生词本；当天错 ≥3 次改到明天并**出队**——出队后 `idx` 不要 +1，否则会跳词。
- 队列构建：每日 `到期复习词 + (daily + carry) 个新词`，`carry` = 昨日未答完的新词数，实现"昨日顺延"。
- 图表一律手写内联 SVG（环形进度、14 天折线、30 天热力图）；图标用内联 SVG，不用 emoji。
- 战绩海报用 canvas 画竖版图 + `toDataURL` 下载。
- 冒烟自检：`node --check` 抽出的 `<script>`；正则比对 JS 里 `$('id')` 与 HTML `id="..."` 是否齐全；`grep` 确认无外部 http 引用。

## 三、资料库在线化（可选，用户要"在线存储/多设备同步"时）

见 `references/library-sync.md`：page 上传 + database 分片同步接入步骤与 SDK 契约要点。

## 四、边界

- 考试日期、题型结构等一律标注"以官方公告为准"。
- 搭配字段宁可留空也不编；缺数据的字段在 UI 上隐藏，不显示占位。
- 词库版权：仅使用 CC/MIT 类开源词表，不再分发原始词库文件本身。
