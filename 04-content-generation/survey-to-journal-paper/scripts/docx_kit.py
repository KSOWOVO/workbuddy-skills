# -*- coding: utf-8 -*-
"""中文期刊 DOCX 排版工具箱（可复用）
用法：from docx_kit import set_font, add_three_line_table, fix_quotes_cn, setup_doc
依赖：python-docx
"""
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

SONG, HEI, KAI, TNR = '宋体', '黑体', '楷体', 'Times New Roman'


# ---------- 字体 ----------
def set_font(run, cn=SONG, en=TNR, size=12, bold=False):
    run.font.name = en
    run.font.size = Pt(size)
    run.font.bold = bold
    rPr = run._element.get_or_add_rPr()
    rf = rPr.find(qn('w:rFonts'))
    if rf is None:
        rf = OxmlElement('w:rFonts'); rPr.append(rf)
    rf.set(qn('w:ascii'), en); rf.set(qn('w:hAnsi'), en); rf.set(qn('w:eastAsia'), cn)


def setup_doc(doc, top=2.4, bottom=2.4, left=2.7, right=2.7):
    s = doc.sections[0]
    s.top_margin, s.bottom_margin = Cm(top), Cm(bottom)
    s.left_margin, s.right_margin = Cm(left), Cm(right)
    st = doc.styles['Normal']
    st.font.name = TNR
    st.font.size = Pt(12)
    st.element.rPr.rFonts.set(qn('w:eastAsia'), SONG)


# ---------- 三线表 ----------
def clear_table_borders(table):
    tblPr = table._tbl.tblPr
    old = tblPr.find(qn('w:tblBorders'))
    if old is not None:
        tblPr.remove(old)
    b = OxmlElement('w:tblBorders')
    for e in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
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
        if spec is None:
            continue
        tag = qn('w:%s' % edge)
        el = b.find(tag)
        if el is None:
            el = OxmlElement('w:%s' % edge); b.append(el)
        el.set(qn('w:val'), 'single'); el.set(qn('w:sz'), str(spec))
        el.set(qn('w:space'), '0'); el.set(qn('w:color'), '000000')


def repeat_as_header(row):
    trPr = row._tr.get_or_add_trPr()
    e = OxmlElement('w:tblHeader'); e.set(qn('w:val'), 'true')
    trPr.append(e)


def add_three_line_table(doc, header, rows, widths=None, size=9,
                         merges=None, first_col_left=True):
    """三线表。merges: [(r1, r2, col)] 以数据行索引（0 起）做纵向合并。"""
    t = doc.add_table(rows=1, cols=len(header))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    clear_table_borders(t)

    for i, h in enumerate(header):
        c = t.rows[0].cells[i]
        p = c.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        pf = p.paragraph_format
        pf.space_before = Pt(2); pf.space_after = Pt(2); pf.line_spacing = 1.0
        set_font(p.add_run(str(h)), HEI, TNR, size, True)
        set_cell_borders(c, top=12, bottom=6)
    repeat_as_header(t.rows[0])

    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            c = cells[i]
            p = c.paragraphs[0]
            p.alignment = (WD_ALIGN_PARAGRAPH.LEFT
                           if (i == 0 and first_col_left) else WD_ALIGN_PARAGRAPH.CENTER)
            pf = p.paragraph_format
            pf.space_before = Pt(1.2); pf.space_after = Pt(1.2); pf.line_spacing = 1.0
            set_font(p.add_run('' if v is None else str(v)), SONG, TNR, size, False)

    if merges:
        for r1, r2, col in merges:
            a = t.cell(r1 + 1, col); b = t.cell(r2 + 1, col)
            if a is not b:
                a.merge(b)

    for c in t.rows[-1].cells:
        set_cell_borders(c, bottom=12)

    if widths:
        for r_ in t.rows:
            for i, w in enumerate(widths):
                if i < len(r_.cells):
                    r_.cells[i].width = Cm(w)
    return t


# ---------- 引号修复（只对纯文本 md 用！） ----------
def fix_quotes_cn(text):
    """把直引号 " 按行内出现顺序成对转成中文弯引号。
    ⚠️ 禁止用于 Python 源码文件（会破坏字符串定界符）。"""
    out = []
    for line in text.split('\n'):
        buf, open_q = [], True
        for ch in line:
            if ch == '"':
                buf.append('\u201c' if open_q else '\u201d')
                open_q = not open_q
            else:
                buf.append(ch)
        out.append(''.join(buf))
    return '\n'.join(out)


# ---------- 段落 ----------
def para(doc, text='', cn=SONG, size=12, bold=False, align=None,
         indent=0, sb=0, sa=3, line=1.5):
    p = doc.add_paragraph()
    if align is not None:
        p.alignment = align
    pf = p.paragraph_format
    pf.space_before = Pt(sb); pf.space_after = Pt(sa); pf.line_spacing = line
    if indent:
        pf.first_line_indent = Pt(size * indent)
    if text:
        set_font(p.add_run(text), cn, TNR, size, bold)
    return p
