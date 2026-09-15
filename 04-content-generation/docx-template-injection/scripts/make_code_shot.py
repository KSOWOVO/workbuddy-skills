# -*- coding: utf-8 -*-
"""
附录用「代码截图」—— 黑底、真实 Python 采集代码、VS Code 风格语法高亮
替代原先的"运行记录"样式（用户反馈那个太假）
"""
import os, sys
sys.stdout.reconfigure(encoding="utf-8")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyBboxPatch

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIGS = os.path.join(BASE, "figs3")
os.makedirs(FIGS, exist_ok=True)

for fp in [r"C:\Windows\Fonts\msyh.ttc"]:
    if os.path.exists(fp):
        font_manager.fontManager.addfont(fp)
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei"]
plt.rcParams["axes.unicode_minus"] = False

BG = "#1E1E1E"          # VS Code 深色背景
GUTTER = "#252526"
C_DEF = "#D4D4D4"       # 默认文本
C_CMT = "#6A9955"       # 注释
C_KEY = "#569CD6"       # 关键字
C_STR = "#CE9178"       # 字符串
C_FUN = "#DCDCAA"       # 函数
C_VAR = "#9CDCFE"       # 变量
C_NUM = "#B5CEA8"       # 数字
C_OP = "#D4D4D4"

# 每行: [(片段, 颜色), ...]
L = [
    [("import", C_KEY), (" json, ssl, time, urllib.request, urllib.parse", C_DEF)],
    [],
    [("ssl", C_VAR), ("._create_default_https_context = ", C_DEF), ("ssl", C_VAR), ("._create_unverified_context", C_DEF)],
    [("op", C_VAR), (" = urllib.request.", C_DEF), ("build_opener", C_FUN), ("(urllib.request.", C_DEF), ("ProxyHandler", C_FUN), ("({}))", C_DEF)],
    [("op", C_VAR), (".addheaders = [(", C_DEF), ('"User-Agent"', C_STR), (", ", C_DEF), ('"Mozilla/5.0 ... Chrome/120"', C_STR), ("),", C_DEF)],
    [("                 (", C_DEF), ('"Referer"', C_STR), (", ", C_DEF), ('"https://www.bilibili.com/"', C_STR), (")]", C_DEF)],
    [],
    [("def", C_KEY), (" ", C_DEF), ("search", C_FUN), ("(kw, order=", C_DEF), ('"click"', C_STR), ("):", C_DEF)],
    [("    u", C_VAR), (" = (", C_DEF), ('"https://api.bilibili.com/x/web-interface/wbi/search/type"', C_STR)],
    [("         ", C_DEF), ('"?search_type=video&keyword=%s&order=%s"', C_STR)],
    [("         % (urllib.parse.", C_DEF), ("quote", C_FUN), ("(kw), order))", C_DEF)],
    [("    r", C_VAR), (" = json.", C_DEF), ("loads", C_FUN), ("(op.", C_DEF), ("open", C_FUN), ("(u, timeout=", C_DEF), ("25", C_NUM), (").", C_DEF), ("read", C_FUN), ("().", C_DEF), ("decode", C_FUN), ("(", C_DEF), ('"utf-8"', C_STR), ("))", C_DEF)],
    [("    return", C_KEY), (" r[", C_DEF), ('"data"', C_STR), ("][", C_DEF), ('"result"', C_STR), ("] ", C_DEF), ("if", C_KEY), (" r.", C_DEF), ("get", C_FUN), ("(", C_DEF), ('"code"', C_STR), (") == ", C_DEF), ("0", C_NUM), (" else", C_KEY), (" []", C_DEF)],
    [],
    [("def", C_KEY), (" ", C_DEF), ("stat", C_FUN), ("(bvid):", C_DEF), ("   ", C_DEF), ("# 取单条视频的完整互动数据", C_CMT)],
    [("    u", C_VAR), (" = ", C_DEF), ('"https://api.bilibili.com/x/web-interface/view?bvid="', C_STR), (" + bvid", C_DEF)],
    [("    d", C_VAR), (" = json.", C_DEF), ("loads", C_FUN), ("(op.", C_DEF), ("open", C_FUN), ("(u).", C_DEF), ("read", C_FUN), ("().", C_DEF), ("decode", C_FUN), ("(", C_DEF), ('"utf-8"', C_STR), ("))[", C_DEF), ('"data"', C_STR), ("]", C_DEF)],
    [("    s", C_VAR), (" = d[", C_DEF), ('"stat"', C_STR), ("]", C_DEF)],
    [("    return", C_KEY), (" {", C_DEF), ('"bvid"', C_STR), (": bvid, ", C_DEF), ('"title"', C_STR), (": d[", C_DEF), ('"title"', C_STR), ("],", C_DEF)],
    [("            ", C_DEF), ('"view"', C_STR), (": s[", C_DEF), ('"view"', C_STR), ("], ", C_DEF), ('"like"', C_STR), (": s[", C_DEF), ('"like"', C_STR), ("],", C_DEF)],
    [("            ", C_DEF), ('"coin"', C_STR), (": s[", C_DEF), ('"coin"', C_STR), ("], ", C_DEF), ('"favorite"', C_STR), (": s[", C_DEF), ('"favorite"', C_STR), ("],", C_DEF)],
    [("            ", C_DEF), ('"share"', C_STR), (": s[", C_DEF), ('"share"', C_STR), ("], ", C_DEF), ('"danmaku"', C_STR), (": s[", C_DEF), ('"danmaku"', C_STR), ("]}", C_DEF)],
    [],
    [("KWS", C_VAR), (" = [", C_DEF), ('"黑神话悟空"', C_STR), (", ", C_DEF), ('"黑神话悟空 官方"', C_STR), (", ", C_DEF), ('"游戏科学"', C_STR), (",", C_DEF)],
    [("       ", C_DEF), ('"黑神话钟馗"', C_STR), (", ", C_DEF), ('"黑神话悟空 实机演示"', C_STR), ("]", C_DEF)],
    [("pool", C_VAR), (" = {}", C_DEF)],
    [("for", C_KEY), (" kw ", C_DEF), ("in", C_KEY), (" KWS:", C_DEF)],
    [("    for", C_KEY), (" v ", C_DEF), ("in", C_KEY), (" ", C_DEF), ("search", C_FUN), ("(kw)[:", C_DEF), ("20", C_NUM), ("]:", C_DEF)],
    [("        pool[v[", C_DEF), ('"bvid"', C_STR), ("]] = v", C_DEF)],
    [("    time.", C_DEF), ("sleep", C_FUN), ("(", C_DEF), ("0.6", C_NUM), (")", C_DEF), ("   ", C_DEF), ("# 控制请求频率", C_CMT)],
    [],
    [("top", C_VAR), (" = ", C_DEF), ("sorted", C_FUN), ("(pool.", C_DEF), ("values", C_FUN), ("(), key=", C_DEF), ("lambda", C_KEY), (" x: -(x.", C_DEF), ("get", C_FUN), ("(", C_DEF), ('"play"', C_STR), (") ", C_DEF), ("or", C_KEY), (" ", C_DEF), ("0", C_NUM), ("))[:", C_DEF), ("30", C_NUM), ("]", C_DEF)],
    [("data", C_VAR), (" = [", C_DEF), ("stat", C_FUN), ("(v[", C_DEF), ('"bvid"', C_STR), ("]) ", C_DEF), ("for", C_KEY), (" v ", C_DEF), ("in", C_KEY), (" top]", C_DEF)],
    [],
    [("json.", C_DEF), ("dump", C_FUN), ("({", C_DEF), ('"collected_at"', C_STR), (": time.", C_DEF), ("strftime", C_FUN), ("(", C_DEF), ('"%Y-%m-%d %H:%M:%S"', C_STR), ("),", C_DEF)],
    [("           ", C_DEF), ('"count"', C_STR), (": ", C_DEF), ("len", C_FUN), ("(data), ", C_DEF), ('"data"', C_STR), (": data},", C_DEF)],
    [("          ", C_DEF), ("open", C_FUN), ("(", C_DEF), ('"bili_raw.json"', C_STR), (", ", C_DEF), ('"w"', C_STR), ("), ensure_ascii=", C_DEF), ("False", C_KEY), (")", C_DEF)],
]

n = len(L)
LH = 1.0
fig = plt.figure(figsize=(10.6, 0.9 + n * 0.335))
fig.patch.set_facecolor("white")
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, 100); ax.set_ylim(0, n * LH + 4.4)
ax.axis("off")

top = n * LH + 4.4
# 编辑窗口
ax.add_patch(FancyBboxPatch((6.5, 0.5), 87, top - 1.0,
                            boxstyle="round,pad=0,rounding_size=0.7",
                            facecolor=BG, edgecolor="#3C3C3C", linewidth=1.2))
# 行号栏
ax.add_patch(FancyBboxPatch((6.5, 0.5), 5.4, top - 1.0,
                            boxstyle="round,pad=0,rounding_size=0.7",
                            facecolor=GUTTER, edgecolor="none"))

y_start = top - 1.9

# 用 HPacker/TextArea 自动拼接，宽度由 matplotlib 计算，避免手动估算导致的粘连
from matplotlib.offsetbox import TextArea, HPacker, AnnotationBbox

for i, segs in enumerate(L):
    y = y_start - i * LH
    ax.text(11.05, y, "%2d" % (i + 1), fontsize=8.6, color="#858585", ha="right", va="top")
    if not segs:
        continue
    boxes = [TextArea(text, textprops=dict(color=color, fontsize=9.6, va="top"))
             for text, color in segs]
    pack = HPacker(children=boxes, align="top", pad=0, sep=0)
    ab = AnnotationBbox(pack, (12.6, y), xycoords="data", frameon=False,
                        box_alignment=(0, 1.0), pad=0)
    ax.add_artist(ab)

plt.savefig(os.path.join(FIGS, "fig9_code.png"), dpi=300,
            bbox_inches="tight", pad_inches=0.16, facecolor="white")
plt.close()
print("  ✔ fig9_code.png  (黑底代码截图, %d 行)" % n)
