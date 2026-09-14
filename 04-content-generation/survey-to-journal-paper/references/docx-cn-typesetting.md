# python-docx 中文期刊排版备忘

## 1. 中文字体设置（最容易踩）
python-docx 的 `run.font.name` 只设 `w:ascii` 与 `w:hAnsi`，**中文会走 `w:eastAsia`，不设就回退成默认字体**。
必须手动补：

```python
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

def set_font(run, cn="宋体", en="Times New Roman", size=12, bold=False):
    run.font.name = en
    run.font.size = Pt(size)
    run.font.bold = bold
    rPr = run._element.get_or_add_rPr()
    rf = rPr.find(qn('w:rFonts'))
    if rf is None:
        rf = OxmlElement('w:rFonts'); rPr.append(rf)
    rf.set(qn('w:ascii'), en); rf.set(qn('w:hAnsi'), en); rf.set(qn('w:eastAsia'), cn)
```

`Normal` 样式同理：`doc.styles['Normal'].element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')`

期刊常用字体：正文宋体小四(12pt)、一级标题黑体四号、二级标题黑体小四、题名黑体小二/三号、
作者楷体、表题黑体五号、表内五号或小五。

## 2. 三线表（必须手写 XML）

**规范**：顶线 1.5pt、表头下线 0.75pt、底线 1.5pt，其余全无边框。
`w:sz` 单位是 **1/8 pt** → 1.5pt = `12`，0.75pt = `6`。

### 2.1 稳健实现：顶线/底线画在「表级」，表头下线画在「单元格级」

⚠️ **最常见的坑**：把三条线全用单元格级 `w:tcBorders` 实现。一旦做纵向合并（`vMerge`），
合并单元格的 bottom 边框会吞掉/错位，**底线断线**。正确做法：

```python
def set_table_edge(table, edge, sz):          # 表级：top / bottom
    tblPr = table._tbl.tblPr
    b = tblPr.find(qn('w:tblBorders'))
    if b is None:
        b = OxmlElement('w:tblBorders'); tblPr.append(b)
    el = b.find(qn('w:%s' % edge))
    if el is None:
        el = OxmlElement('w:%s' % edge); b.append(el)
    el.set(qn('w:val'), 'single'); el.set(qn('w:sz'), str(sz))
    el.set(qn('w:space'), '0'); el.set(qn('w:color'), '000000')

# 顶线/底线：set_table_edge(t, 'top', 12) / set_table_edge(t, 'bottom', 12)
# 表头下线：set_cell_borders(header_cell, bottom=6) —— 只画在表头行每一格
```

`w:tcBorders` **必须排在 `w:tcW` 之后**（OOXML schema 顺序），否则 Word 可能忽略整块边框：
```python
tcW = tcPr.find(qn('w:tcW'))
if tcW is not None: tcW.addnext(b)
else: tcPr.append(b)
```

**合并后必须复核表头下线**：`merge()` 会重建行结构，最后再对 `t.rows[0]` 逐格补一次
`set_cell_borders(c, bottom=6)`。

表头跨页重复：给首行 trPr 加 `w:tblHeader`。防单行被拦腰截断：加 `w:cantSplit`。

### 2.2 列宽：先算再给，别拍脑袋

**必须先把版心算准**。本机 Word 默认文档是 **US Letter 21.59 × 27.94cm**（**不是 A4 21×29.7**），
页边距 2.54cm → **版心宽 = 21.59 − 2.54×2 = 16.51cm**。
实测：直接读 `doc.sections[0].page_width/left_margin`，别假设。

**逐格反算最小列宽**（避免表头折行、`＜0.001` 被拆两行）：
```python
PT_PER_CM = 28.3465
CJK, HALF = 9.0, 4.5          # 9pt 字号下：全角字宽 9pt，半角 4.5pt
PAD = 0.20 * PT_PER_CM * 2    # 单元格左右内边距合计约 0.4cm

def need_cm(s):
    w = sum(9.0 if unicodedata.east_asian_width(c) in ('W','F') else 4.5 for c in str(s))
    return (w + PAD) / PT_PER_CM
```
对**表头与每一格数据**取 `max`，得到该列最小宽度；各列之和 ≤ 16.51cm 才能保证零折行。
剩余空间按比例摊给长文本列，让表格**撑满版心**（中文期刊表格不留右侧空白）。

**列宽要三处一致**，否则 Word 自动重排导致列宽乱跳：
`w:tblW`（=各列之和）、`w:tblGrid/w:gridCol`、每格 `w:tcW`（gridSpan 列要合并计宽）。
另外 `w:tblGrid` **必须紧跟 `w:tblPr`**。

### 2.3 排版细节
- **垂直居中**：每格 `tcPr` 加 `w:vAlign w:val="center"`，合并单元格尤其需要。
- **表题不与表体分离**：表题段设 `keep_with_next = True`（否则"孤标题"留页底，表翻页）。
- **高表**：行数多（如 18 行）的表格收紧段落 `space_before/after`（0.4pt）才放得下一页；
  实在放不下再允许分页，别为"不拆页"把整表推到下一页留大片空白。

### 2.4 ⚠️ 验证必须靠渲染，不能只看 XML

XML 写对了 ≠ 渲染出来是对的。**唯一可信的验收方式**：

```
docx → Word COM 导出 PDF → PyMuPDF 渲染 PNG → 目视 + 解析矢量线段
```

```python
import win32com.client as win32
word = win32.gencache.EnsureDispatch('Word.Application')
word.Visible = False; word.DisplayAlerts = 0
doc = word.Documents.Open(src, ReadOnly=True)
doc.SaveAs(pdf, FileFormat=17)      # 17 = wdFormatPDF
doc.Close(False); word.Quit()
```

```python
import pymupdf
d = pymupdf.open(pdf)
p = d[page_no]
for dr in p.get_drawings():          # 客观读出每条线的位置与粗细
    for it in dr['items']:
        if it[0] == 'l' and abs(it[1].y - it[2].y) < 1.5:     # 横线
            print(f'y={it[1].y:.1f} x={min(it[1].x,it[2].x):.1f}->{max(it[1].x,it[2].x):.1f} w={dr["width"]}')
pix = p.get_pixmap(matrix=pymupdf.Matrix(5, 5), clip=pymupdf.Rect(x0,y0,x1,y1))
pix.save('zoom.png')                 # 裁剪放大关键区域后肉眼看
```

**验收清单**（逐项看图确认，不要跳过）：
1. 顶线/底线 x 范围 = 版心左右边界（如 72.1 → 540.0pt @ Letter+2.54cm 边距）
2. 表头下线比顶线细一半（`width` 12 vs 6）、长度与顶线一致
3. 表头**无折行**；`＜0.001` 之类不可拆串**未被拆行**
4. 表格无跨页拦腰截断（或跨页处表头正确重复）
5. 表题与表体同页
6. 合并单元格内容垂直居中

依赖：`pip install pywin32 pymupdf`。`fitz` 已弃用，`import pymupdf` 即可（API 同名）。

## 3. 纵向合并
```python
a = t.cell(r1, col); b = t.cell(r2, col)
if a is not b: a.merge(b)
```
注意 `.cell()` 用的是**表内绝对行号**（含表头行），不是数据行索引。合并后只有左上角单元格保留文本。

## 4. 插图
```python
p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.add_run().add_picture(png_path, width=Cm(14.6))
```
只支持位图。SVG 需先转 PNG（matplotlib / cairosvg）。
matplotlib 中文字体：`plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]`，
同时 `plt.rcParams["axes.unicode_minus"] = False`（否则负号变方块）。

**图中路径标签易重叠**：SEM 图建议先给每个节点算好中心坐标，标签用 `bbox=dict(boxstyle="round", fc="white")`
压住箭头；画完必须**回读图片肉眼检查**，别只信代码没报错。

## 5. 中文引号被转直引号（高频事故）
某些写入通道会把 `“ ”` 规范化为 `"`（U+0022）。补救：

```python
# 逐行交替替换；只对纯文本 md 用！
def fix_quotes(text):
    out = []
    for line in text.split("\n"):
        buf, open_q = [], True
        for ch in line:
            if ch == '"':
                buf.append("\u201c" if open_q else "\u201d"); open_q = not open_q
            else:
                buf.append(ch)
        out.append("".join(buf))
    return "\n".join(out)
```

⚠️ **绝对不要对 Python 源码文件跑这个**——会把字符串定界符也换成弯引号，导致语法错误、
列表列数错位（`IndexError: tuple index out of range` 的典型来源）。
源码里中文内容一律用**单引号 `'...'`** 做定界符，内容中的引号写成 `\u201c`/`\u201d` 或直接弯引号。

## 6. 环境
- 依赖：`python-docx`、`openpyxl`、`pdfplumber`、`matplotlib`
- 本机（Kelsen 机）装法：venv 在 `C:/Users/13662/.workbuddy/binaries/python/envs/default`
- 该机 bash PATH 常损坏：`ls/grep/head/tail` 均 not found → 用绝对路径调 Python；
  列目录用 Python `os.walk`；读文件用 Read 工具。行内 `2>/dev/null` 可屏蔽 shim 噪声。
