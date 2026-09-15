# -*- coding: utf-8 -*-
"""
把正文内容注入作业模板 docx（v3：修复图片未嵌入的根因）
根因：v2 用「搬运 XML 元素」的方式注入，图片的 r:embed 关系留在临时文档中，
      目标文档 rels 里没有对应关系 → Word 打开图片全部显示不出来。
修复：直接在目标文档的正文单元格上创建段落与图片，确保图片关系正确写入 document.xml.rels。
"""
import os, re, shutil, zipfile
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TPL = r"C:\Users\13662\Desktop\新媒体营销-第一次作业(1).docx"
OUTDIR = os.path.join(BASE, "out")
FIGS = os.path.join(BASE, "figs")
ASSETS = os.path.join(BASE, "assets", "final")
OUT = os.path.join(OUTDIR, "新媒体营销-第一次作业-伍凯森组.docx")
MD = open(os.path.join(OUTDIR, "正文.md"), encoding="utf-8").read()

IMG_W = 5.4      # 英寸（表格单元格可用宽度约 5.74 英寸）

FIGMAP = {
    "图1":  ("fig1_pv_views.png",   "图1  《黑神话》系列官方PV在B站的传播量级（本组2026-09-15采集）"),
    "图2":  ("fig2_funnel.png",     "图2  《黑神话：悟空》13分钟实机演示的B站互动结构：投币率反超点赞率"),
    "图3":  ("fig3_pgc_vs_ugc.png", "图3  官方PGC与创作者UGC的传播效率对比（本组2026-09-15采集）"),
    "图4":  ("fig4_zhongkui.png",   "图4  《黑神话：钟馗》系列内容的传播走势（零发售窗口期热度回升）"),
    "图5":  ("fig5_treemap.png",    "图5  《黑神话》内容生态矩形树状图：面积＝播放量，颜色＝内容类型"),
    "图6":  ("fig6_pie.png",        "图6  内容类型分布：数量占比与播放量占比对比"),
    "图7":  ("fig7_radar.png",      "图7  五支官方PV的多维互动率雷达图"),
    "图8":  ("fig8_heatmap.png",    "图8  各内容类型的平均互动表现热力图"),
    "图9":  ("fig9_top12.png",      "图9  播放量 TOP12 内容排行（颜色＝内容类型）"),
    "图10": ("fig10_5a_model.png",  "图10  游戏科学《黑神话》营销的5A消费者路径转化（自绘）"),
}


def set_font(run, name="宋体", size=10.5, bold=False):
    run.font.name = name
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = RGBColor(0, 0, 0)
    rPr = run._element.get_or_add_rPr()
    rf = rPr.find(qn("w:rFonts"))
    if rf is None:
        rf = OxmlElement("w:rFonts"); rPr.append(rf)
    for a in ("w:ascii", "w:hAnsi", "w:eastAsia"):
        rf.set(qn(a), name)


def set_spacing(p, multiple=1.5, first_indent_chars=2, space_before=0, space_after=0):
    pf = p.paragraph_format
    pf.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
    pf.line_spacing = multiple
    pf.space_before = Pt(space_before)
    pf.space_after = Pt(space_after)
    if first_indent_chars:
        pPr = p._element.get_or_add_pPr()
        ind = pPr.find(qn("w:ind"))
        if ind is None:
            ind = OxmlElement("w:ind"); pPr.append(ind)
        ind.set(qn("w:firstLineChars"), str(int(first_indent_chars * 100)))
        ind.set(qn("w:firstLine"), "0")


# ---------- 注意：以下函数全部作用在【目标文档的单元格】上 ----------
def mk_body(cell, text):
    p = cell.add_paragraph()
    set_spacing(p, 1.5, 2, 0, 3)
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    for seg in re.split(r"(\*\*[^*]+\*\*)", text):
        if not seg:
            continue
        if seg.startswith("**") and seg.endswith("**"):
            set_font(p.add_run(seg[2:-2]), "宋体", 10.5, True)
        else:
            set_font(p.add_run(seg), "宋体", 10.5, False)
    return p


def mk_h2(cell, text):
    p = cell.add_paragraph()
    set_spacing(p, 1.5, 0, 10, 5)
    set_font(p.add_run(text), "宋体", 12, True)
    return p


def mk_h3(cell, text):
    p = cell.add_paragraph()
    set_spacing(p, 1.5, 0, 7, 3)
    set_font(p.add_run(text), "宋体", 10.5, True)
    return p


def mk_fig(cell, img, caption):
    p = cell.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_spacing(p, 1.0, 0, 8, 2)
    p.add_run().add_picture(img, width=Inches(IMG_W))
    c = cell.add_paragraph(); c.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_spacing(c, 1.0, 0, 0, 10)
    set_font(c.add_run(caption), "宋体", 9, False)


# ============================ 打开模板并定位正文单元格 ============================
shutil.copy(TPL, OUT)
doc = Document(OUT)

target = None
for tbl in doc.tables:
    for row in tbl.rows:
        for i, cell in enumerate(row.cells):
            if cell.text.strip() == "正文" and i + 1 < len(row.cells):
                target = row.cells[i + 1]
                break
        if target is not None:
            break
    if target is not None:
        break
assert target is not None, "未找到正文单元格"

# 清空该单元格原有段落（含红色说明文字）
for p in list(target.paragraphs):
    p._element.getparent().remove(p._element)

# ============================ 直接在单元格内构建内容 ============================
inserted, n_case = set(), 0
for ln in MD.split("\n"):
    s = ln.rstrip()
    if not s.strip() or s.startswith("> ") or s.startswith("# "):
        continue
    m = re.match(r"^@@IMG:([^|]+)\|([^@]+)@@$", s.strip())
    if m:
        fn, cap = m.group(1).strip(), m.group(2).strip()
        p = os.path.join(ASSETS, fn + ".jpg")
        if os.path.exists(p):
            mk_fig(target, p, cap); n_case += 1
        else:
            print("   [案例图缺失]", p)
        continue
    if s.startswith("## "):
        mk_h2(target, s[3:].strip()); continue
    if s.startswith("### "):
        mk_h3(target, s[4:].strip()); continue
    if s.startswith("- "):
        mk_body(target, "　　" + s[2:].strip()); continue

    mk_body(target, s)
    for k in re.findall(r"图\d+", s):
        if k in FIGMAP and k not in inserted:
            f, cap = FIGMAP[k]
            mk_fig(target, os.path.join(FIGS, f), cap)
            inserted.add(k)

missing = [k for k in FIGMAP if k not in inserted]
if missing:
    print("⚠ 未按引用位置插入，追加到末尾:", missing)
    for k in sorted(missing, key=lambda x: int(x[1:])):
        f, cap = FIGMAP[k]
        mk_fig(target, os.path.join(FIGS, f), cap)

doc.save(OUT)
print("数据图:", len(inserted), "| 案例图:", n_case)
print("已生成:", OUT)

# ============================ 复核（关键：检查图片是否真嵌入） ============================
d2 = Document(OUT)
for tbl in d2.tables:
    for row in tbl.rows:
        for i, cell in enumerate(row.cells):
            if cell.text.strip() == "正文" and i + 1 < len(row.cells):
                tc = row.cells[i + 1]._tc
                txt = "".join(t.text or "" for t in tc.findall(".//" + qn("w:t")))
                print("正文中文字数:", len(re.findall(r"[\u4e00-\u9fff]", txt)))
                print("内嵌图片(drawing)数:", len(tc.findall(".//" + qn("w:drawing"))))

z = zipfile.ZipFile(OUT)
media = sorted([n for n in z.namelist() if n.startswith("word/media/")])
rels = z.read("word/_rels/document.xml.rels").decode("utf-8")
print("\nword/media 文件数:", len(media))
for m in media:
    print("   ", m, "%.0f KB" % (z.getinfo(m).file_size / 1024))
print("图片关系(IMAGE)数:", rels.count("relationships/image"))
print("文件总大小: %.1f MB" % (os.path.getsize(OUT) / 1024 / 1024))
