# 模式 C：从整篇论文里「抽取指定章节 → 按母版格式重排」

**场景**：手上已有一篇完整论文（导师稿 / 自己写的定稿），用户只要其中某一两章（常见：「我明天只汇报数据分析那部分」），
要求单独打印/汇报，且格式对齐另一篇指定母版论文。

**硬约束（用户没明说也必须遵守）**
1. **正文文字一字不改**——任务性质是"搬运 + 排版"，不是"改写"。任何润色都是越界。
2. **表号沿用原文编号**，绝不重编。原文正文写着"如表2所示"，若把截出来的第一张表重编为"表1"，全文引用立刻错乱。
3. 保留 `（续）` 表、表注、脚注编号等一切原有结构。

---

## 流程

### 1. 先量母版，别猜格式
```python
from docx import Document
s = Document(master).sections[0]
print(s.page_width.cm, s.page_height.cm,             # 常见 US Letter 21.59×27.94，不是 A4
      s.top_margin.cm, s.left_margin.cm)             # 版心 = 宽 − 左右边距
```
再抓母版几个代表段落的 `style / 字体(eastAsia) / 字号 / line_spacing / first_line_indent / space_before|after`，
照抄成基准表。**源文档自身的格式通常不齐**（页边距、表宽各行其是），以母版为准。

本机常用基准（7P 母版）：Letter + 四边 2.54cm → 版心 **16.51cm**；
正文宋体 12pt / 行距 1.5 / 首行缩进 24pt / 段后 3pt；章标题黑体 12pt 加粗；
表题黑体 10.5pt 居中（表上方）；表体宋体 9pt；表注宋体 9pt。

### 2. 按 body 顺序抽取（段落与表格是混排的）
`doc.paragraphs` 和 `doc.tables` 是两个独立序列，**丢失相对顺序**。必须遍历 body：
```python
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

def iter_block(parent, doc):
    for child in parent.iterchildren():
        if child.tag == qn('w:p'):   yield Paragraph(child, doc)
        elif child.tag == qn('w:tbl'): yield Table(child, doc)
```
切段：找起点标题（如"四、实证分析结果"）与终点（如"参考文献"）的 block 下标，切 `blocks[start:end]`。

### 3. 表格数据全量提取（要带合并语义）
```python
for tr in tbl.findall(qn('w:tr')):
    for tc in tr.findall(qn('w:tc')):
        tcPr = tc.find(qn('w:tcPr'))
        span = int(tcPr.find(qn('w:gridSpan')).get(qn('w:val'))) if ... else 1
        vm   = tcPr.find(qn('w:vMerge'))       # 'restart' / None(=continue) / 无
        text = ''.join(t.text or '' for t in tc.iter(qn('w:t')))
```
`vMerge` 无 `w:val` 属性时代表 `continue`（续接上一行），**别当成"无合并"**。
落成 JSON 后，重建时再换算成 `add_three_line_table(merges=[(r1,r2,col)])`（数据行索引，不含表头）。

### 4. 列宽：反算 → 齐版心
见 `docx-cn-typesetting.md` §2.2。本章节补充两条实战判断：

- **齐版心 vs 放大上限**：内容极少的表（4 列短词）强行撑满版心会显空。
  两种都能用——**期刊风格选齐版心**（整篇整齐、有"续表同宽"的天然收益）；
  若追求自然可选 `target = min(版心, 需求×1.45)` 并居中。**同一篇文档只能选一种**。
- **`（续）`表与主表必须同宽**。按**表号**归组（不是按表题段落对象——两张表的表题是两个不同段落，按对象归组会失效），
  组内取 `max(target)` 统一。齐版心下此问题自动消失。

### 5. 列对齐：只看数据行，别被表头骗
判据：**该列数据行的最大汉字数 ≥ 6 → 左对齐（文字列）；否则居中（数值列）。表头一律居中。**
```python
def cjk_count(s):
    return sum(1 for ch in str(s) if unicodedata.east_asian_width(ch) in ('W','F'))
left_cols = {i for i in range(n)
             if max([cjk_count(r[i]) for r in rows] or [0]) >= 6}
```
⚠️ **把表头也算进去会误判**：像"删除该项后α区间""标准化系数β"这类表头有 6–8 个汉字，但整列数据是纯数值，
判成左对齐后数字左右乱飘。**表头不参与判定。**

效果：`变量/类别/选项/路径/中介路径` 等文字列左对齐，`β/z/P/CR/AVE/均值` 等数值列居中——这是中文社科三线表的标准观感。

### 6. 生成时的排版细节
- 章标题 `黑体 12pt 加粗`，二级标题同（段前 9pt / 段后 4.5pt）
- 表题段 `keep_with_next=True`（防孤标题）；表注 `宋体 9pt`
- 行数 > 18 的表：`row_gap=0.5` + `keep_together=False`（允许跨页，靠 `w:tblHeader` 重复表头）
- 页脚加 PAGE 域居中，方便打印对页
- 顺带输出 PDF（Word COM，`FileFormat=17`）交给用户直接打印

### 7. 交付前必须做两道校验
**① 文本级**：掐掉新增的标题区后，逐段比对新旧正文（`''.join(s.split())` 去空白后比较），
表题/表注逐条比对。目标：段落数相同且逐段一致。

**② 表格级必须走 XML，不能用 `row.cells`**：
python-docx 的 `row.cells` 会把**被合并区域的每一行都返回同一份文本**，
直接比对会得到"原件有空串、新件没有"的假差异（本轮实测 3 张表虚报）。
正确做法是把新文档也用 `findall(qn('w:tr'))/(qn('w:tc'))` 拆出
`(文本, span, vMerge)` 三元组，与源 JSON 逐格比对——**合并语义也在比对范围内**。

**③ 渲染级**：docx → Word COM → PDF → PyMuPDF PNG，肉眼过一遍关键页（详见 `docx-cn-typesetting.md` §2.4）。

---

## 本轮（2026-09-14 佛山文武红四五章汇报稿）实测数据
- 抽取：2 个一级标题 + 6 个二级标题 + 37 段正文 + 14 张表 + 14 表题 + 11 表注
- 版心 16.51cm；14 张表全部齐版心；输出 16 页
- 校验：正文 45/45 段一致、14/14 表逐格零差异、表题表注 14/14、11/11 一致
- 打印友好：同时交付 docx + PDF（PDF 由 Word 真实渲染，格式不会跑）
