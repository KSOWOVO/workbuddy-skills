# -*- coding: utf-8 -*-
"""清除残留的黄色高亮格式（说明性文字的高亮标记）"""
import os, zipfile, shutil, re
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "out", "新媒体营销-第一次作业-伍凯森组.docx")
TMP = OUT + ".tmp"

zin = zipfile.ZipFile(OUT, "r")
zout = zipfile.ZipFile(TMP, "w", zipfile.ZIP_DEFLATED)
n_fixed = 0
for item in zin.infolist():
    data = zin.read(item.filename)
    if item.filename == "word/document.xml":
        s = data.decode("utf-8")
        before = s.count('w:highlight w:val="yellow"')
        # 删除 highlight 元素
        s = re.sub(r'<w:highlight w:val="yellow"\s*/>', '', s)
        after = s.count('w:highlight w:val="yellow"')
        n_fixed = before - after
        data = s.encode("utf-8")
    zout.writestr(item, data)
zin.close(); zout.close()
shutil.move(TMP, OUT)
print("已清除黄色高亮 %d 处" % n_fixed)

z = zipfile.ZipFile(OUT)
x = z.read("word/document.xml").decode("utf-8")
print("复核 -> 红色字体:", x.count('w:color w:val="FF0000"'), "| 黄色高亮:", x.count('w:highlight w:val="yellow"'))
