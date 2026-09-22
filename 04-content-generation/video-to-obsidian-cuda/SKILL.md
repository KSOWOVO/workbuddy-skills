---
name: video-to-obsidian-cuda
description: 把视频/音频转录成 Obsidian 笔记，并备份纯文本稿到 ima 知识库。触发词：转录这个视频 / 视频转文字 / 用 CUDA 转录 / 把这个视频存进 Obsidian / 课程视频整理 / 转写稿 / 丢视频进来。能力：faster-whisper large-v3 跑 CUDA（RTX 5060 8G 实测可用）→ 整理成 md 落 Obsidian → 纯文本稿传 ima。（截图是可选旁路，默认关闭）
agent_created: true
---

# 视频 → CUDA 转录 → Obsidian + ima

**主线只有两件事**：转录落 Obsidian、纯文本稿传 ima。Kelsen 2026-09-22 明确砍掉了截图（详见 §6）。

---

## 一、固定路径

| 用途 | 路径 |
|---|---|
| 转录入口 | `<skill>/scripts/pipeline.py` |
| **Python 解释器** | `C:\Users\13662\.workbuddy\binaries\python\envs\whisper\Scripts\python.exe` |
| 模型 | `C:\Users\13662\.workbuddy\models\whisper\large-v3` |
| Obsidian vault | `C:\Users\13662\Documents\Obsidian` |
| 原件仓库 | `C:\Users\13662\Documents\学习资料` |
| ima 知识库 ID | `001aa55b37801a4a` |
| ima 上传脚本 | `~/.workbuddy/skills/02-knowledge-management/ima-knowledge-upload/scripts/cos_upload.py` |

> ⚠️ **解释器必须用 `envs\whisper\`** —— 只有它装了 `faster-whisper 1.2.1` + `ctranslate2 4.8.2` + NVIDIA 运行时库。
> `envs\default\` 和 `versions\3.13.12\` 用了会直接 `ModuleNotFoundError`。

---

## 二、标准动作（照抄，不要重新推理）

### 第 1 步：转录 + 落 Obsidian

```bash
export PATH="/c/Windows/System32:/c/Windows:/usr/bin:/bin:$PATH"
PY="C:/Users/13662/.workbuddy/binaries/python/envs/whisper/Scripts/python.exe"
SK="C:/Users/13662/.workbuddy/skills/04-content-generation/video-to-obsidian-cuda"
"$PY" "$SK/scripts/pipeline.py" "<视频路径>"
```

**这一条命令就够了**：分类会自动判（见 §三），笔记 / `_plain/` 稿 / 原件备份一起出来。

一小时视频 ≈ 15–25 分钟跑完（模型加载约 14s 一次性开销），**用 `run_in_background` 跑**，别让它阻塞对话。

### 第 2 步：校对 + 整理（🔴 不能跳过，Kelsen 2026-09-22 明确要求）

> 原话：「每次转录完之后，你要稍微看一下……每一篇你都要全篇检查一下，把转录错的
> 词语搞清楚究竟是什么，然后把它改好。不能完全不改，转录完是啥就是啥。」
> 「你每次把视频放进去，都要整理一遍排序，不能不整理。」

**2a. 全篇通读，改错**——Whisper 的中文同音误识别是**成规律**的，通读一遍就能全部抓出。
必须真的读完（分块 Read），不能只看开头。**实测 80 分钟视频里揪出 20+ 类错词**：

| 错形 | 正确 | 说明 |
|---|---|---|
| 重聚 / 从具 / 从剧 / 从举 / 冲剧 / 冲句 / 重句 | **从句** | 最高频，六种错形 |
| 复词 / 复次 / 复制 | **副词** | 「条件复词从句」→「条件副词从句」 |
| 编语 / 兵语 | **宾语** | |
| 英语图 / 英语托 / 英语突围 | **英语兔** | 频道名被听错 |
| 位于动词 / 位语动词 / 尾语动词 | **谓语动词** | |
| 同位于从句 / 同文语 / 同谓语 | **同位语从句** | |
| 不吉误 / 单吉误 / 双吉误 | **不及物 / 单及物 / 双及物** | |
| 毕动词 | **be 动词** | |
| 实态 / 将来事态 | **时态** | |
| 竹子翻译 | **逐字翻译** | |
| 修是 | **修饰** | |
| 后制的 | **后置的** | |
| 原音副词从句 | **原因副词从句** | |

**英文粘连**：相邻两句英文常被听成一句（`carrotwhich`、`hungryso`、`videoyou`），
补空格或拆成两行。**大写被吞**：`toOK` → `took`、`loOK` → `look`。

⚠️ **只改「听错的词」，不改「意思」**（铁律见 §七）。遇到语义不确定的（比如某处
明显被吞掉一个词），**不要猜** —— 在汇报里列出来让 Kelsen 定。

**2b. 整理小标题**——`outliner.py` 生成的是**草稿**，词频法有天花板：
它会产出「胡萝卜 · 兔子」「carrot · ate」这种「共现词」，**不是主题名**。
虽然它已能切出完整的「形容词从句 / 宾语补语从句」（见脚本内的长词压制规则），
但仍**必须由你按通读理解手写一遍**，改成真正的主题名
（如「形容词从句的思维方式」「限定性与非限定性」「形式主语 it」）。

**2c. 交回文件**——校对完把主笔记原样覆盖到 `_plain/`（截图关时两者本就相同），
因为 ima 传的是 `_plain`。然后用 `DUPLICATE_NAME_STRATEGY_REPLACE` 重传一次，
让 ima 里的版本同步更新。

### 第 3 步：纯文本稿传 ima

ima 三步链路，缺一不可：

1. **`mcp__ima-mcp__create_media`**
   - `file_name` **不含扩展名**
   - `file_ext` = `md`
   - `file_size` **必须精确字节数**（`os.path.getsize()` 取）
   - `content_type` = `text/markdown`
2. **COS 上传**（必须先 `unset` 代理，否则必失败）
   ```bash
   unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy ALL_PROXY all_proxy
   "$PY" "<ima-skill>/scripts/cos_upload.py" cred.json "<_plain 的 md 路径>"
   ```
   把 `create_media` 返回的 `cos_credential` **原样**落 JSON，只加一个 `content_type` 字段。预期 `HTTP 200`。
3. **`mcp__ima-mcp__add_knowledge`** —— `folder_id` 留空（根目录），策略 `DUPLICATE_NAME_STRATEGY_REPLACE`

**验证（不能省）**：再调 `get_knowledge_list`，确认新条目 `media_state: 2`、`parse_progress: 100`。
只看 `add_knowledge` 的返回值不算数 —— 它不报解析状态。

收尾删掉 `cred*.json`（含临时凭证，12 小时有效）。

---

## 三、分类自动判定（不用传 `-s`）

`resolve_subject()` 按标题/文件名关键词自动落到 vault 子目录，实测：

```
'雅思大作文写作【1. 大作文题型介绍】' → 30-升学规划/雅思写作/大作文
'英语语法精讲合集'                  → 30-升学规划/英语语法
'想提前退休_投资方法'                → 40-个人生活/投资理财
'某某无关视频'                     → 00-收件箱
```

要手动指定就传短名（会自动展开）：

| 短名 | 实际落点 |
|---|---|
| `雅思写作/大作文` / `雅思写作/小作文` | `30-升学规划/雅思写作/...` |
| `英语语法` | `30-升学规划/英语语法` |
| `雅思` | `30-升学规划/雅思` |
| `投资理财` | `40-个人生活/投资理财` |
| `竞赛科研` | `20-竞赛科研` |
| `课程学习` | `10-课程学习` |

### 常用参数

| 参数 | 说明 |
|---|---|
| `--subject/-s` | 分类（短名即可） |
| `--title/-t` | 笔记标题（默认取文件名） |
| `--lang/-l` | 语言，默认 `zh`；纯英文视频传 `en` |
| `--no-raw` | 不备份原件 |
| `--start/--end` | 只处理片段（秒） |
| `--shots` | **开启截图**（默认关，见 §六） |

---

## 四、流程与产物

```
[1/4] 转录   faster-whisper large-v3 → CUDA float16 → VAD 过滤 → polish() 整理
[2/4] 截图   默认跳过
[3/4] 落地   写 Obsidian md + _plain/ 纯文本稿
[4/4] 备份   原件 cp 到 Documents\学习资料\<分类>\
```

产出三处：

1. `Obsidian\<分类>\<标题>.md` —— 笔记（`# H1` + `## ▎小标题` + 时间戳段落）
2. `Obsidian\<分类>\_plain\<标题>.md` —— ima 专用纯文本稿
3. `Documents\学习资料\<分类>\<原视频>` —— 原件备份

**带时间戳**（`**00:08**`）是为了回看时能定位视频位置。

---

## 五、关键坑（都踩过，别改回去）

### 5.1 🔴 `Library cublas64_12.dll is not found` —— 最容易卡死的一关

**症状**：CUDA 探测通过、模型加载成功，一跑真实音频就崩。

**为什么静音测试会「假通过」**：纯静音经 VAD 过滤后没有语音段，**根本没进 encoder**，用不到 cuBLAS。**必须用有声音的音频测。**

**根因**：CTranslate2 自带 CUDA kernel，但动态链接 cuBLAS / cuDNN。系统没装 CUDA Toolkit 就找不到。

**解法**（已实施，不用重做）：装 NVIDIA 官方 PyPI 轮子
```bash
"$PY" -m pip install nvidia-cublas-cu12 nvidia-cudnn-cu12 nvidia-cuda-nvrtc-cu12 \
  --index-url https://pypi.org/simple --no-cache-dir
```
`transcriber.py` 顶部 `_register_cuda_dlls()` 会把 DLL 目录加进搜索路径，
**必须在 `import ctranslate2` 之前执行** —— 已在模块顶部自动跑，无需干预。

已装版本：`nvidia-cublas-cu12 12.9.2.10` / `nvidia-cudnn-cu12 9.26.0.51` / `nvidia-cuda-nvrtc-cu12 12.9.86`。

### 5.2 不要加 YAML frontmatter

Kelsen 现有 vault 笔记（20+ 篇）**全部无 frontmatter**，只有 `# H1` + 正文。新笔记默认不加，保持风格一致。

### 5.3 `_plain/` 是 ima 的接口，别删

截图关闭时它和主笔记内容相同；一旦开了 `--shots`，主笔记会带 `![[...]]` 双链而 ima 解析不了，
所以**永远统一用 `_plain/` 传 ima**，不要图省事传主笔记。

### 5.4 其他

- **代理**：Clash Verge 在 `7897`。下载模型/装包要带 `--proxy http://127.0.0.1:7897`；
  但 **COS 上传必须 `unset` 代理**，否则失败。
- **Bash PATH**：本机 Git Bash 缺 coreutil，命令前加
  `export PATH="/c/Windows/System32:/c/Windows:/usr/bin:/bin:$PATH"`。
- **Bash 下 `find` 匹配不了中文路径** —— 会静默返回空，让人误判「文件不存在」。
  **核对文件一律用 Python**（`os.listdir` / `os.path.isfile`），不要信 `find`。
- **删除操作用 Python**（`os.remove` / `shutil.rmtree`）：`rm -rf` 和批量 `rm -f` 会被
  WorkBuddy 的删除保护反复 SIGTERM 掐断。这与沙箱无关，完全访问下同样如此。
- **原始视频落点**：Kelsen 从对话丢进来的视频，先定位再处理，不要假设路径。

### 5.5 沙箱模式下可用（2026-09-21 实测，无需完全访问）

本 skill 依赖的资源几乎全在工作区之外，但实测**零拦截**：解释器可执行、模型可读、
vault 可写可删、ima/COS 网络连通、完整 pipeline 跑通。
**不需要「完全访问」权限**，完全访问只是省掉授权弹窗。

---

## 六、可选：截图（默认关闭，保留备用）

> **2026-09-22 Kelsen 决策：主线不要截图。** 理由：①截图让流程复杂、跑得慢；
> ②ima 本来就不吃图片；③他以后在自己的 HTML 知识库面板里单独处理配图。
>
> 代码**保留**（能跑、有验证），需要时加 `--shots` 启用。以后若要在 HTML 面板里配图，
> 这套场景检测 + 语义筛仍然可用。

启用：`pipeline.py <视频> --shots`

实现要点（改之前读）：

- **场景变化检测**，不是固定间隔。四层过滤：2 秒采样灰度差分 → pHash 去重（汉明距离 < 6）
  → 自适应最小间隔 + 空白帧过滤（std < 12）→ 上限 400 张。
- **自适应最小间隔** `max(MIN_GAP, duration / MAX_SHOTS)`：80 分钟视频会算成 12.0s。
  固定 3.0s 的实测事故是**在 58% 处撞满 400 张上限**，后 42% 一张图都没有。
- **`cv2.imwrite` 在中文路径下静默失败**（最阴的坑）：报告「已捕捉 400 张」，但 `_assets/` 空空如也，
  **不报错、不抛异常、退出码 0**。因为 OpenCV 在 Windows 上按 ANSI(GBK) 处理路径。
  本 vault 路径必然含中文，**必中**。解法：用 `shot_detector.imwrite_unicode()`
  （`cv2.imencode` 编码到内存 + Python 原生 `open()` 写字节），**不要直接用 `cv2.imwrite`**。
- **落盘护栏**：`pipeline.py` 会强制核对磁盘真实文件数，对不上就 raise 或剔除失效引用。
  **教训：不要只信 `report["shots"]` 计数，那数的是内存列表，必须验磁盘实物。**
- **图文对齐三级判据**：①区间覆盖 → ②最近邻 → ③单调约束。只用①会让末尾的图全堆在文末。
- **`![[ ]]` 内链必须用反斜杠**：写成 `dir/file.jpg`（正斜杠）Obsidian 按整名解析，
  **实测 304/304 全部变坏链**。必须 `rel.replace("/", "\\")`。
- **两阶段策略**：先宽收再语义筛。`shot_filter.py` 按文字密度 / 墨迹量 / 线条结构 / 邻帧唯一性
  打分分级（S/A/B/C），C 级是过场动画和纯 logo 帧，应删。
  实测 80 分钟课 **S 53 / A 127 / B 95 / C 29**，304 → 275 张。

---

## 七、整理层设计红线（Kelsen 的既有铁律）

**「通顺不删减、纠错不改意」** —— 只做机械、可审计、无歧义的整理：

| 允许 | 禁止 |
|---|---|
| 合并碎句、去语气词（嗯呃啊哦） | 猜词义、替换专业术语 |
| 压重复字词 | 删改原话 |
| 接缝去重（`讲雅思`+`雅思作文`→`讲雅思作文`） | 缩写、总结性改写 |
| 中英之间补空格 | 调整语序 |
| 中文语境标点规范化（`,` → `，`） | 加原文没有的内容 |

整理程度：**中度，加段落小标题**。小标题（`## ▎`）**必须从原文提取词频**，不能凭空生成。

> 曾写过一个 `FIX_MAP`（如「提示」→「题型」），自查时发现违反「纠错不改意」，
> **已全部删除**。别再走回头路。

---

## 八、收尾检查

1. `Obsidian\<分类>\<标题>.md` 存在
2. `Obsidian\<分类>\_plain\<标题>.md` 存在（ima 用）
3. `Documents\学习资料\<分类>\<原视频>` 存在
4. ima 上传成功 → `get_knowledge_list` 里 `media_state: 2`、`parse_progress: 100`
5. 汇报给 Kelsen：路径 + 「Obsidian 记得 Refresh」

### ⚠️ ima 连接器会掉线（2026-09-21 实测遇到）

`connector-status` 里没有 ima 时，`ToolSearch` 搜 `mcp__ima-mcp__*` 会一无所获 ——
**必须在 WorkBuddy「连接器」面板重新连接**，这一步 agent 做不了。

掉线时不要卡住：先把笔记 + `_plain/` 稿落盘，把 ima 上传记为待办，
并在汇报里**显式说明「ima 没传成功，原因是连接器掉线」**，不要假装成功。

### ⚠️ ima MCP 没有删除接口

实测只有 6 个工具：`get_knowledge_base_list` / `get_knowledge_list` / `search_knowledge` /
`fetch_media_content` / `create_media` / `add_knowledge`。

**传错了删不掉**，只能在 ima 客户端手动删。所以**测试稿标题必须带「测试」字样**，方便事后识别。

---

## 九、自更新契约

`scripts/` 是**工作副本**，源头在 `C:\Users\13662\WorkBuddy\2026-08-31-20-05-05\cstream\`。
改动后**必须同步两边**（脚本有 6 个）：

```bash
cp .../cstream/{pipeline,transcriber,shot_detector,shot_filter,polisher,outliner}.py \
   ~/.workbuddy/skills/04-content-generation/video-to-obsidian-cuda/scripts/
```

跑真实视频后若发现新的坑或参数更优，**立即回写本文档** —— 文档落后等于下次重新踩坑。
