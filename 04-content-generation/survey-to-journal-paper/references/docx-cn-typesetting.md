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

```python
def clear_table_borders(table):
    tblPr = table._tbl.tblPr
    old = tblPr.find(qn('w:tblBorders'))
    if old is not None: tblPr.remove(old)
    b = OxmlElement('w:tblBorders')
    for e in ('top','left','bottom','right','insideH','insideV'):
        el = OxmlElement('w:%s' % e)
        el.set(qn('w:val'), 'none'); el.set(qn('w:sz'), '0')
        el.set(qn('w:space'), '0'); el.set(qn('w:color'), 'auto')
        b.append(el)
    tblPr.append(b)

def set_cell_borders(cell, top=None, bottom=None):
    tcPr = cell._tc.get_or_add_tcPr()
    b = tcPr.find(qn('w:tcBorders'))
    if b is None:
        b = OxmlElement('w:tcBorders'); tcPr.append(b)
    for edge, spec in (('top', top), ('bottom', bottom)):
        if spec is None: continue
        tag = qn('w:%s' % edge)
        el = b.find(tag)
        if el is None:
            el = OxmlElement('w:%s' % edge); b.append(el)
        el.set(qn('w:val'), 'single'); el.set(qn('w:sz'), str(spec))  # sz 单位 1/8 pt
        el.set(qn('w:space'), '0'); el.set(qn('w:color'), '000000')
```
标准三线表：表首行 `top=12`（=1.5pt）+ `bottom=6`（=0.75pt，表头下细线）；末行 `bottom=12`。
**其它线全部 no-border**（靠 `clear_table_borders` 兜底）。

表头跨页重复：给首行 trPr 加 `w:tblHeader`。

列宽要**逐行设置**（`row.cells[i].width = Cm(x)`），只设 `table.columns[i].width` 常被 Word 忽略。
A4 页宽 21cm，左右各留 2.7cm → 可用约 15.4cm。

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
