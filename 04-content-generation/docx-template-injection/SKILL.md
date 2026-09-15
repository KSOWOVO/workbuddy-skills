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
