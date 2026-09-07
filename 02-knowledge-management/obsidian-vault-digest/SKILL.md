---
name: obsidian-vault-digest
description: 扫描 Obsidian vault 并生成「通俗易懂的单文件 HTML 全景解读页」——含知识地图 SVG、板块占比、内容体系拆解、自动化数据仪表盘、库体检报告。触发词：总结一下我的知识库 / Obsidian 库可视化 / 我的 vault 里有什么 / 做个知识库主页给别人看 / 知识库体检。也适用于任何「一堆 markdown 让人看不懂，需要讲人话」的场景（可指定任意目录）。
agent_created: true
---

# Obsidian Vault 全景解读

把一个 markdown 笔记库，变成外人 3 分钟能看懂的单页 HTML。

## 何时用

- 用户想「看懂/展示」自己的知识库，而不是找某一篇笔记
- 需要给他人（或不熟的我）解释这个库装了什么、缺什么
- 任意目录的 md 集合需要体检（双链率、标签率、空目录、内容配比）

## 流程（顺序敏感）

1. **扫结构**：`find <vault> -type d`（排除 `.obsidian/.git`）+ `find -name "*.md" -printf "%TY-%Tm-%Td %6s %p"` 看规模与空目录
2. **扫元数据**：`python scripts/scan_vault.py <vault> <out.json>` → 每篇的字数/heading/tags/双链/frontmatter/预览
3. **判类型**：看 headings 数量。若每篇只有 1 个 H1 → **转写稿型库**（无内部分级标题，必须抽关键句）；若 heading 丰富 → 直接用标题做骨架
4. **抽内容要点**：`python scripts/extract_points.py <vault> <out.json>`（改脚本内 `TARGETS` 为目标文件）→ 抓含「首先/核心/记住/本质/所以/建议」的 25–130 字句
5. **读关键篇**：对体量最大 / 结构最特殊的 1–3 篇用 Read 精读，其余靠抽取句归纳
6. **算配比**：按目录聚合中文字数 → 板块占比（这是「投入证据」，比篇数更有说服力）
7. **做 HTML**：单文件、离线可看、零 CDN 依赖。设计规格见 `references/design-spec.md`
8. **校验**：用 html.parser 查标签闭合（脚本见下），再 present_files

## 必须输出的 6 个模块

| 模块 | 作用 | 数据来源 |
|---|---|---|
| Hero + 关键数字 | 一句话定位 + 外行类比 | 篇数/总字数/板块数/打卡/双链数 |
| 知识地图 SVG | 一图看清装了什么 | 目录树 + 字数（分支粗细 ∝ 字数） |
| 板块卡 + 单篇字数排行 | 精力配比 | scan.json |
| 内容体系拆解 | **核心价值**：把转写稿提炼成可操作的框架 | extract.json + 精读 |
| 自动化数据仪表盘 | 库里唯一会自己更新的数据 | frontmatter/表格型笔记 |
| 体检报告 + 建议 | 好在哪 / 缺在哪 / 按 ROI 排序的行动 | 下面的检查清单 |

## 体检检查清单（每项都要给结论）

- **双链率**：有 `[[]]` 的笔记 ÷ 总数。低于 20% → 判定「是文件夹树，不是知识网络」
- **标签率**：有 tags 的笔记 ÷ 总数。低于 20% → 无法横向聚合
- **空目录**：0 文件的分类目录，逐个点名
- **占位文件**：`欢迎.md`、空日记、空 `.canvas`
- **输入/产出比**：他人转写稿 vs 自己加工的笔记（模板卡/复盘/错题）
- **MOC 缺失**：是否有目录/索引页
- **自动化入口**：有没有脚本自动写入的笔记（这是库的「活数据」）

## 坑（已踩过）

- **转写稿没有小标题**：视频转写稿几乎只有一个 H1，靠 heading 提取会拿到空骨架，必须走「关键句抽取」
- **中文字符统计要用 `[\u4e00-\u9fa5]` 正则**，不能用 bytes（UTF-8 一个汉字 3 字节，会虚高 3 倍）
- **统计要在去掉 frontmatter 的 body 上做**，否则自动写入的 YAML 会污染
- **代码块里的 `#` 会被误判成 heading**，提取时要跳过 ``` 包裹区
- **极小的进度环看不到**：0.9% 的弧长只有 4px，要设最小可见弧（3%）并在中心标真实数字
- **数字滚动别只查子元素的 `[data-to]`**，reveal 元素自身也可能是计数器，两者都要处理
- **Windows 路径**用 `r"..."` 原始字符串，vault 路径含中文，`find` 前先 `cd` 进去

## HTML 标签闭合校验（改完必跑）

```python
from html.parser import HTMLParser
import io
VOID={'area','base','br','col','embed','hr','img','input','link','meta','source','track','wbr',
      'path','circle','rect','stop','use','feGaussianBlur','feMerge','feMergeNode'}
# handle_starttag 入栈 / handle_endtag 出栈比对，输出未闭合与不匹配
```

## 脚本

- `scripts/scan_vault.py <vault_dir> <out.json>` — 全库元数据
- `scripts/extract_points.py <vault_dir> <out.json>` — 关键句抽取（改 `TARGETS`）
