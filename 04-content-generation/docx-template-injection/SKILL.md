---
name: docx-template-injection
description: >
  把正文与图表填进学校作业/课程报告模板 docx（保留封面、信息表、分工表、页眉）。
  触发词：填进模板、按模板做、作业模板、课程报告模板、把这个填进去、照这个格式做、
  保留封面表格、图文并茂的作业、Word 里图片显示不出来。
  核心解决两个坑：① 用 python-docx 搬运 XML 元素会导致图片全部丢失（Word 里显示不出来），
  必须直接在目标文档上创建段落与图片；② 模板说明性文字需连"红色字体+黄色高亮"一起清。
  配套脚本可直接复用（填表、清理、自检）。
summary: 作业/报告类 docx 模板注入的可靠流程与两个致命坑（图片丢失、说明文字残留），含可复用脚本与自检清单。
agent_created: true
---

# docx 模板注入（作业 / 课程报告）

## 何时用

- 有一份学校发的**模板 docx**（封面 + 作业信息表 + 正文单元格 + 分工表 + 评阅表），要填真实内容
- 用户说"照这个模板做""填进去""保留封面""图文并茂"
- 报告里要插入**自制数据图表 + 案例实拍/官方素材图**

不适用：从零新建文档（直接用 tencent-docx 系列）、纯格式转换。

---

## ⚠️ 两个致命坑（先记住再动手）

### 坑1：图片会"静默丢失"——Word 里全部显示不出来

**错误做法**：新建一个临时 `Document()`，在里面 `add_picture`，然后把 `p._element` 搬到目标文档的单元格里。

```python
# ❌ 千万不要这样：图片关系留在临时文档，目标文档 rels 里没有
tmp = Document()
tmp.add_paragraph().add_run().add_picture(img)
target_cell._tc.append(tmp.paragraphs[0]._element)
```

原因：图片的 `r:embed="rId5"` 是**相对关系 ID**，关系存在各文档自己的 `word/_rels/document.xml.rels` 里。搬 XML 只搬了引用，没搬关系 → Word 找不到图片，静默不显示（不报错）。

**正确做法**：直接在目标文档的单元格上创建段落和图片。

```python
# ✔ 正确：图片关系会正确写入目标文档
for p in list(target_cell.paragraphs):      # 先清空原有段落
    p._element.getparent().remove(p._element)
p = target_cell.add_paragraph()
p.add_run().add_picture(img_path, width=Inches(5.4))
```

**交付前必查**（这是唯一能发现坑1的方法）：

```python
import zipfile
z = zipfile.ZipFile(out)
media = [n for n in z.namelist() if n.startswith("word/media/")]
rels = z.read("word/_rels/document.xml.rels").decode()
n_draw = len(tc.findall(".//" + qn("w:drawing")))   # 正文里的图片对象数
assert len(media) - 1 >= n_draw, "图片没真正嵌入！"
assert rels.count("relationships/image") >= n_draw, "图片关系缺失！"
```
（`-1` 是因为模板自带的 `image1.png` 会占一个）

### 坑2：模板说明文字要连"高亮"一起清

模板常写「以上红色字体，提交作业时删除」。只删文字不够——那些字往往还带 `w:highlight val="yellow"`。要连格式一起处理：

```python
xml = re.sub(r'<w:highlight w:val="yellow"\s*/>', '', xml)   # 清高亮
# 同时检查 w:color w:val="FF0000" 数量应为 0
```

---

## 标准流程（顺序敏感，不要跳步）

```
1. 解析模板 → 找出正文在哪个表格单元格
2. 定位正文单元格（左列文字恰为"正文"，取右侧合并单元格）
3. 清空该单元格全部段落（含红色说明文字）
4. 直接在单元格上逐段创建：标题(宋体小四加粗) / 正文(宋体五号) / 图片
5. 填封面、同组人员、小组分工表
6. 清红色字体 + 黄色高亮
7. 跑自检脚本（字数/图片/格式/嵌入校验）
```

**为什么 4 必须直接在单元格上做**——见坑1。

### 1. 定位正文单元格

```python
target = None
for tbl in doc.tables:
    for row in tbl.rows:
        for i, cell in enumerate(row.cells):
            if cell.text.strip() == "正文" and i + 1 < len(row.cells):
                target = row.cells[i + 1]      # 右侧合并单元格
                break
```
表格结构典型为：`[0]封面  [1]作业信息表(含正文)  [2]分工表  [3]评阅表`。

### 2. 格式参数（对齐常见作业规范）

| 元素 | 字体 | 字号 | 半磅值 | 其他 |
|---|---|---|---|---|
| 一级标题 | 宋体 | 小四 | `w:sz=24` | 加粗 |
| 二级标题 | 宋体 | 五号 | `w:sz=21` | 加粗 |
| 正文 | 宋体 | 五号 | `w:sz=21` | 行距 `w:line=360`（1.5倍）、首行缩进 2 字符 |

首行缩进 2 字符：`w:ind` 设 `w:firstLineChars="200"`、`w:firstLine="0"`。

### 3. 图片宽度

表格单元格宽 `8478 twips`（≈5.89 英寸），两侧 cellMargin 各 108 twips。
**图片宽度用 5.4 英寸**，留安全边距；超过会出现溢出或显示异常。

### 4. 图注用单倍行距

正文查行距时会误报图注（`w:line=240`）。图注本来就是单倍行距，自检脚本要把含 `w:drawing` 的段落排除掉。

---

## 配套脚本

| 脚本 | 用途 |
|---|---|
| `scripts/inject_docx.py` | 按 md 源文件注入正文+图片（**核心，含坑1的正确写法**） |
| `scripts/fill_members.py` | 填封面姓名、同组人员、小组分工表 |
| `scripts/clean_highlight.py` | 清红色字体与黄色高亮 |
| `scripts/verify.py` | 交付前自检（字数/图片嵌入/格式/分工表） |

**正文源文件用 md 维护**，再注入 docx。好处：改内容不用碰 docx，重跑注入即可。
图片位置用标记表达：数据图在正文写「图3」自动插图；案例图用 `@@IMG:文件名\|图注@@` 单独占一行。

**图号匹配要用正则**，否则「图1」会误匹配「图10」：
```python
for k in re.findall(r"图\d+", s):     # ✔
    ...
# if "图1" in s:                      # ✘ 会误匹配「图10」
```

---

## 案例素材图从哪来（作业"图文并茂"用）

自制数据图是分析，**案例本身的视觉素材**（海报、实机画面）另外下载：

| 来源 | 拿什么 | 方法 |
|---|---|---|
| **哔哩哔哩** | 官方 PV 封面（=官方宣传海报） | `api.bilibili.com/x/web-interface/view?bvid=xxx` → `data.pic` |
| **Steam** | 官方游戏截图、主视觉 | `store.steampowered.com/api/appdetails?appids=<appid>&l=schinese` → `screenshots[].path_full` |

两个接口都**无需登录**。注意：
- B站 `pic` 字段是 `http://`，要换成 `https://`
- 代理环境下必须禁代理：`env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY`，且脚本内 `urllib.request.build_opener(ProxyHandler({}))`
- 下载后用 PIL **压到宽 1400px、JPEG q90**，否则 1920×1080 PNG 每张 2-3MB，文档会爆

---

## 附录：代码不要贴整段，要「截图」

用户明确不要整段代码贴进 Word（"不好看"），要**一张黑底代码截图**，看起来像随手截的编辑器画面。

做法：matplotlib 画 VS Code 深色主题的代码图（`scripts/make_code_shot.py`）。

**配色**（VS Code Dark+）：
```python
BG="#1E1E1E"  GUTTER="#252526"  C_DEF="#D4D4D4"
C_KEY="#569CD6"   C_STR="#CE9178"   C_FUN="#DCDCAA"
C_VAR="#9CDCFE"   C_NUM="#B5CEA8"   C_CMT="#6A9955"
```

**关键坑：分段着色的宽度计算**。语法高亮要把一行拆成多个 `(文本, 颜色)` 片段分别渲染，若手算宽度推进 x 坐标，几乎必然重叠。

```python
# ✔ 用 HPacker/TextArea，宽度由 matplotlib 自己算
from matplotlib.offsetbox import TextArea, HPacker, AnnotationBbox
boxes = [TextArea(t, textprops=dict(color=c, fontsize=9.6, va="top")) for t, c in segs]
pack = HPacker(children=boxes, align="top", pad=0, sep=0)
ax.add_artist(AnnotationBbox(pack, (x, y), xycoords="data", frameon=False,
                             box_alignment=(0, 1.0), pad=0))
# ✘ 不要用 get_window_extent 逐片段测量再累加，实测仍会粘连
#    （下划线、点号等字符的 advance width 有偏差）
```

**另一个坑**：Consolas 无中文字形，且 `font.sans-serif` 列表回退在 `savefig` 时**不可靠**——中文会全变成方框。代码里有中文（关键词列表、注释）时，直接统一用 `Microsoft YaHei`，别指望回退。

---

## 图表编号：全文统一，按出现顺序

用户要求「从第一页到最后一页，第一张图叫图1，第一张表叫表1」——**阿拉伯数字，不是中文数字**。

- 图注格式：`图1  XXX说明`
- 表题格式：`表1  XXX说明`（居中、加粗、小五）
- 附录里的截图**也纳入同一编号体系**（代码截图可能是图9）

⚠️ **注入时的经典 bug**：正文若提前提到「见文末图9」，注入脚本会**在那里就把图9插进去**。要么别提前引用，要么把「附图/代码见图9」这类表述放到真正的位置。

**附录分页**：`## 附录二` 前插入分页符，保证附录各自另起一页。
```python
p = cell.add_paragraph(); r = p.add_run()
br = OxmlElement("w:br"); br.set(qn("w:type"), "page"); r._element.append(br)
```

---

## 正文文风：Kelsen 的硬要求（踩过才记住）

这位用户对"AI 味"极敏感，作业/报告正文必须满足：

| 禁止 | 替换为 |
|---|---|
| 分号 `；` | 目标 **0 个**，改句号断句 |
| 其一 / 其二 / 其三 | 第一是 / 第二是 / 第三是 |
| 值得注意的是、综上所述、换言之、颇具启示、有鉴于此 | 直接删掉，或改「但…更值得关注」 |
| 破折号 `——` 堆叠 | 各留 1 处，其余拆句 |
| 解释性括号 `（说明：…）`、`（注：…）` | **全删**，内容融进正文或直接不要 |
| 加粗 `**…**` | 作业正文不加粗（标题层级靠字号区分） |
| 同句连重（N 段收尾同一句） | 轮换 3 种说法 |

**正面要求**：
- 用「我们」写，有第一人称的现场感（"我们在调研中捕捉到""这组数字说明"）
- 句子长短交错，短句断得干脆
- 讲具体的数字和动作，不讲空泛的总结
- 结尾落到一个具体判断，不要"综上所述"式收束
- 字数**按内容需要写**：作业要求 1500 字时写 2500-3500 字是合适的，但不要写到 7000 字（会显得堆砌）

**结构上**：如果报告用了爬虫/数据采集，逻辑必须是
`企业产品介绍 → 我们爬了什么数据、怎么爬的 → 基于数据的分析 → 结论`
**不要**把数据来源打散在各章，要**集中一段说清楚**（用户原话："你这样有点散"）。
爬虫代码片段与原始数据表放附录，这是区别于普通作业的核心卖点。

**图注编号**：用中文数字「图一、图二…」，与正文引用严格一致；案例实拍图也纳入同一编号体系。

---

## 自制图表清单（"图文并茂"的高分组合）

matplotlib 需 `pip install matplotlib squarify`（装到 venv），中文要 `font_manager.addfont(r"C:\Windows\Fonts\msyh.ttc")`。

推荐 5-6 类，覆盖不同视觉形态：

| 图型 | 用途 | 实现 |
|---|---|---|
| 矩形树状图 Treemap | 内容/流量结构占比 | `squarify.squarify()` 拿坐标后**自己画**，可控制小块字号 |
| 环形饼图 / 双层饼图 | 构成占比 | `pie(wedgeprops=dict(width=0.45))` |
| 雷达图 | 多维对比 | `subplot_kw=dict(polar=True)` |
| 热力图 | 类型×指标矩阵 | `imshow` + 列归一化 |
| 横向条形图 | 排行 | `barh` |
| 分组柱状图 | 两组对比 | 双 `bar` 错位 |

**Treemap 注意**：`squarify.plot()` 的 label 不会自动裁剪，长标签会溢出。改用 `squarify.squarify()` 拿矩形坐标 + 手动 `Rectangle` + 按面积分档字号：
```python
rects = squarify.squarify(squarify.normalize_sizes(sizes, W, H), 0, 0, W, H)
# 面积 >900 用 10.5pt，>380 用 9.2pt，>170 用 8pt，更小只显标签不显数字
```
颜色分类里**避免两个相近色**（如 #8E44AD 与 #7D3C98 都是紫，图例会分不清）。

### ⚠️ 圆角柱：在数据坐标下必被拉伸（踩过两次）

`FancyBboxPatch` 的 `rounding_size` 在数据坐标下，x 与 y 的量纲不同（柱宽 0.5、柱高 7000），圆角会被压成看不见。

**正确做法**：按两个方向分别把「屏幕像素半径」换算成数据单位。

```python
def pixratio(ax):
    p = ax.transData.transform((0, 0))
    sx = abs(ax.transData.transform((1, 0))[0] - p[0])   # 每数据单位的x像素
    sy = abs(ax.transData.transform((0, 1))[1] - p[1])   # 每数据单位的y像素
    return sx, sy

def round_rect(ax, x, y, w, h, r_px, color):
    sx, sy = pixratio(ax)
    rx = min(r_px / sx, w / 2)      # ← 各自维度限制！
    ry = min(r_px / sy, h / 2)      # ← 不要把 x 的宽度套到 y 上
    v = [(x, y), (x, y + h - ry),
         (x, y + h), (x + rx, y + h),          # 左上圆角
         (x + w - rx, y + h),
         (x + w, y + h), (x + w, y + h - ry),  # 右上圆角
         (x + w, y), (x, y)]
    c = [Path.MOVETO, Path.LINETO, Path.CURVE3, Path.CURVE3, Path.LINETO,
         Path.CURVE3, Path.CURVE3, Path.LINETO, Path.CLOSEPOLY]
    ax.add_patch(PathPatch(Path(v, c), facecolor=color, edgecolor="none"))
```
**易错点**：写成 `ry = min(r_px/sy, w/2)` 就白做了（用柱宽限制柱高方向的半径 = 圆角趋近 0）。
**验证方法**：生成图后扫柱顶那一行像素，若从柱左边界开始就是柱色，说明圆角没生效。

### 用户偏好的视觉语言（Kelsen）

**深蓝圆角卡片 + 编号徽章 + 大留白 + 无边框**，配色参考：
```python
C_DEEP="#12456B"  C_MAIN="#1B6CA8"  C_LIGHT="#3E9DD9"
C_RED="#D64545"   C_ORANGE="#E8843C" C_GREEN="#2E9E7E"  C_GREY="#8496A5"
```
- `axes.spines` 全部隐藏、`set_yticks([])`、无网格线
- 标题左对齐 + 副标题（数据来源/说明）分两行，**用 `pad=40+` 留出空间，否则标题与来源文字重叠**
- 柱体内不要塞文字（矮柱会溢出）
- 流程图/示意图用 `FancyBboxPatch(boxstyle="round,pad=0,rounding_size=1.6")`——**在等比例坐标系（如 0-100 × 0-34）里画，圆角才正常**
- 别画雷达图、路径模型这类学术味重的图，课程作业容易被质疑"老师让你解释答不上来"


---

## 自检清单（交付前逐项过）

- [ ] 正文字数 ≥ 要求（记录实际值）
- [ ] 正文内嵌图片数 = 预期张数
- [ ] **`word/media` 文件数 ≥ 图片数**（坑1 的唯一防线）
- [ ] **`document.xml.rels` 图片关系数 ≥ 图片数**
- [ ] 红色字体 = 0，黄色高亮 = 0
- [ ] 标题/正文的字体字号行距抽查通过
- [ ] 分工表人数 = 实际组员数
- [ ] 文档体积合理（一般 < 10MB）
- [ ] 列出待用户手填项（如学号）
