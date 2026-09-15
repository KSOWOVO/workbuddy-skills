# -*- coding: utf-8 -*-
"""最终交付检查：合规项 + 图片真嵌入 + 格式"""
import os, re, zipfile, sys
sys.stdout.reconfigure(encoding="utf-8")
from docx import Document
from docx.oxml.ns import qn

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "out", "新媒体营销-第一次作业-伍凯森组_终版.docx")
doc = Document(OUT)
OK, BAD = "✔", "✘"
errs = []

print("=" * 68)
print("                交付前最终检查报告")
print("=" * 68)

# ---------- 1 红色文字 / 高亮 ----------
z = zipfile.ZipFile(OUT)
xml = z.read("word/document.xml").decode("utf-8")
red, yel = xml.count('w:color w:val="FF0000"'), xml.count('w:highlight w:val="yellow"')
print("\n【1】模板说明文字清理")
print("     红色字体 %d 处 %s   黄色高亮 %d 处 %s" % (red, OK if red == 0 else BAD, yel, OK if yel == 0 else BAD))
if red or yel: errs.append("模板红色/高亮文字未清干净")

# ---------- 2 定位正文 ----------
tc = None
for tbl in doc.tables:
    for row in tbl.rows:
        for i, c in enumerate(row.cells):
            if c.text.strip() == "正文" and i + 1 < len(row.cells):
                tc = row.cells[i + 1]._tc
                break
        if tc is not None: break
    if tc is not None: break

txt = "".join(t.text or "" for t in tc.findall(".//" + qn("w:t")))
cn = len(re.findall(r"[\u4e00-\u9fff]", txt))
print("\n【2】正文字数")
print("     %d 字（要求 ≥1500 字）  %s" % (cn, OK if cn >= 1500 else BAD))
if cn < 1500: errs.append("字数不足")

# ---------- 3 图片（关键：验证真嵌入） ----------
drawings = len(tc.findall(".//" + qn("w:drawing")))
media = [n for n in z.namelist() if n.startswith("word/media/")]
rels = z.read("word/_rels/document.xml.rels").decode("utf-8")
imgrels = rels.count("relationships/image")
print("\n【3】图表（关键项）")
print("     正文内嵌图片对象 %d 个（要求：图文并茂）  %s" % (drawings, OK if drawings >= 8 else BAD))
print("     word/media 实际文件 %d 个  %s" % (len(media), OK if len(media) - 1 >= drawings else BAD))
print("     document.xml.rels 图片关系 %d 条  %s" % (imgrels, OK if imgrels >= drawings else BAD))
if len(media) - 1 < drawings:
    errs.append("图片未真正嵌入（media 文件数少于引用数）")
if imgrels < drawings:
    errs.append("图片关系缺失，Word 中将显示不出")

# 逐图检查嵌入字节
embed = [n for n in media if n != "word/media/image1.png"]
print("     %s 已嵌入图片：" % OK)
for m in sorted(embed):
    print("        %-24s %6.0f KB" % (m.split("/")[-1], z.getinfo(m).file_size / 1024))

# ---------- 4 格式 ----------
print("\n【4】格式规范（标题宋体小四加粗 / 正文宋体五号 / 行距1.5倍）")
n_h2 = n_h3 = n_body = 0
bad_fmt = []
for p in tc.findall(qn("w:p")):
    ts = "".join(t.text or "" for t in p.findall(".//" + qn("w:t")))
    if not ts.strip() or p.findall(".//" + qn("w:drawing")):
        continue
    pPr = p.find(qn("w:pPr"))
    sp = pPr.find(qn("w:spacing")) if pPr is not None else None
    line = sp.get(qn("w:line")) if sp is not None else None
    r = p.find(qn("w:r"))
    if r is None: continue
    rPr = r.find(qn("w:rPr"))
    szel = rPr.find(qn("w:sz")) if rPr is not None else None
    sz = szel.get(qn("w:val")) if szel is not None else None
    b = (rPr is not None and rPr.find(qn("w:b")) is not None)
    rf = rPr.find(qn("w:rFonts")) if rPr is not None else None
    font = rf.get(qn("w:eastAsia")) if rf is not None else None
    if sz == "24":
        n_h2 += 1
        if not b or font != "宋体": bad_fmt.append(("标题", ts[:24], sz, b, font))
    elif sz == "21":
        n_body += 1
        if font != "宋体": bad_fmt.append(("正文", ts[:24], sz, b, font))
        if line != "360": bad_fmt.append(("行距≠1.5", ts[:24], line))
    else:
        n_h3 += 1
print("     标题(小四) %d 个 / 小标题(五号加粗) %d 个 / 正文(五号) %d 个" % (n_h2, n_h3, n_body))
if bad_fmt:
    print("     ⚠ 异常 %d 处:" % len(bad_fmt))
    for x in bad_fmt[:8]: print("        -", x)
    errs.append("部分段落格式异常")
else:
    print("     %s 全部段落格式规范" % OK)

# ---------- 5 分工表 ----------
print("\n【5】小组分工表")
t2 = doc.tables[2]
filled = 0
for r in t2.rows[1:]:
    nm = r.cells[1].text.strip()
    if nm:
        filled += 1
        print("     %-4s | %s" % (nm, r.cells[3].text.strip()[:46]))
print("     已填 %d 人（要求 7 人）  %s" % (filled, OK if filled == 7 else BAD))
if filled != 7: errs.append("分工表人数不符")

# ---------- 6 封面 ----------
print("\n【6】封面信息")
t0 = doc.tables[0]
for r in t0.rows:
    a = r.cells[0].text.strip(); b2 = r.cells[1].text.strip().replace("\n", " ")
    if a: print("     %-10s %s" % (a, b2))

# ---------- 7 待补 ----------
print("\n【7】待补充项")
print("     学号：分工表 7 人的学号列目前为空，需手动填写")

# ---------- 总结 ----------
print("\n" + "=" * 68)
if errs:
    print("❌ 存在问题：")
    for e in errs: print("   -", e)
else:
    print("✅ 全部检查项通过，可以提交")
print("文件：%s" % OUT)
print("大小：%.1f MB" % (os.path.getsize(OUT) / 1024 / 1024))
print("=" * 68)
