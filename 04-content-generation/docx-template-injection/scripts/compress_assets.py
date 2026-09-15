# -*- coding: utf-8 -*-
"""
压缩案例图片素材，供插入 Word（控制文档体积）
输出：assets/final/*.jpg  宽度 1400px，JPEG q90
"""
import os, sys, json
sys.stdout.reconfigure(encoding="utf-8")
from PIL import Image

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AD = os.path.join(BASE, "assets")
FD = os.path.join(AD, "final")
os.makedirs(FD, exist_ok=True)

PICK = {
    "wukong_13min":     ("case_wukong_main",  1400),
    "steam_shot1":      ("case_gameplay_1",   1400),
    "steam_shot3":      ("case_gameplay_2",   1400),
    "wukong_final":     ("case_wukong_final", 1400),
    "zhongkui_teaser":  ("case_zhongkui",     1400),
    "zhongkui_15min":   ("case_zhongkui_2",   1400),
    "wukong_story":     ("case_wukong_story", 1400),
    "steam_shot4":      ("case_gameplay_3",   1400),
}

total = 0
for src, (dst, w) in PICK.items():
    sp = os.path.join(AD, src + ".png")
    if not os.path.exists(sp):
        print("   [缺失]", src); continue
    im = Image.open(sp).convert("RGB")
    if im.width > w:
        im = im.resize((w, int(im.height * w / im.width)), Image.LANCZOS)
    op = os.path.join(FD, dst + ".jpg")
    im.save(op, "JPEG", quality=90, optimize=True, progressive=True)
    kb = os.path.getsize(op) / 1024
    total += kb
    print("   ✔ %-24s %dx%d  %.0f KB" % (dst + ".jpg", im.width, im.height, kb))

print("\n共 %d 张，合计 %.1f MB" % (len(PICK), total / 1024))
