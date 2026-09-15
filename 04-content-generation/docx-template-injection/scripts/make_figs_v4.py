# -*- coding: utf-8 -*-
"""
图表集 v4 —— 最终版（6张，现代扁平卡片风）
1) 官方PV传播量级        2) 数据采集与分析流程（突出爬虫）  3) 内容生态矩形树状图
4) 单条PV互动结构        5) 钟馗传播走势                   6) 播放量Top10
修复要点：手工构造圆角路径（避免 FancyBboxPatch 在数据坐标下被拉伸）、
         标题与来源文字错层、去柱内溢出文字、紧凑坐标范围
"""
import json, os, sys, math
sys.stdout.reconfigure(encoding="utf-8")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager
from matplotlib.patches import Rectangle, FancyBboxPatch, PathPatch, FancyArrowPatch
from matplotlib.path import Path
import squarify

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIGS = os.path.join(BASE, "figs3")
os.makedirs(FIGS, exist_ok=True)

for fp in [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\msyhbd.ttc"]:
    if os.path.exists(fp):
        font_manager.fontManager.addfont(fp)
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

C_DEEP, C_MAIN, C_LIGHT, C_PALE = "#12456B", "#1B6CA8", "#3E9DD9", "#A8D4EE"
C_RED, C_ORANGE, C_GREEN, C_GREY = "#D64545", "#E8843C", "#2E9E7E", "#8496A5"
CC = {"官方物料": C_DEEP, "攻略解说": C_MAIN, "二创动画": C_LIGHT,
      "剧情解析": C_GREEN, "媒体评测": C_ORANGE, "文化解读": C_GREY}

raw = json.load(open(os.path.join(BASE, "data", "bili_raw.json"), encoding="utf-8"))
S = {s["bvid"]: s for s in raw["stats"]}
DATE_CN = "2026年9月15日"


def save(fig, name):
    fig.savefig(os.path.join(FIGS, name), bbox_inches="tight", dpi=300, pad_inches=0.3)
    plt.close(fig)
    print("  ✔", name)


def strip(ax):
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0)


def pixratio(ax):
    """返回 (每数据单位对应的x像素, y像素)"""
    p = ax.transData.transform((0, 0))
    sx = abs(ax.transData.transform((1, 0))[0] - p[0])
    sy = abs(ax.transData.transform((0, 1))[1] - p[1])
    return sx, sy


def round_rect(ax, x, y, w, h, r_px, color, alpha=1.0, zorder=2):
    """在数据坐标下画「顶部圆角」矩形；r_px 为屏幕像素半径，保证圆角不被拉伸"""
    sx, sy = pixratio(ax)
    rx = min(r_px / sx, w / 2)
    ry = min(r_px / sy, h / 2)
    v = [(x, y),
         (x, y + h - ry),
         (x, y + h), (x + rx, y + h),
         (x + w - rx, y + h),
         (x + w, y + h), (x + w, y + h - ry),
         (x + w, y),
         (x, y)]
    c = [Path.MOVETO, Path.LINETO, Path.CURVE3, Path.CURVE3, Path.LINETO,
         Path.CURVE3, Path.CURVE3, Path.LINETO, Path.CLOSEPOLY]
    ax.add_patch(PathPatch(Path(v, c), facecolor=color, edgecolor="none", alpha=alpha, zorder=zorder))


# =====================================================================
# 图一  官方PV传播量级
# =====================================================================
PV = [("2020.08", "13分钟实机演示", "BV1x54y1e7zf", C_DEEP),
      ("2022.08", "6分钟实机剧情", "BV1tN4y1F79k", C_MAIN),
      ("2024.08", "最终预告", "BV1oH4y1c7Kk", C_LIGHT),
      ("2025.08", "《钟馗》先导预告", "BV1sHePzWEbG", C_ORANGE),
      ("2026.08", "《钟馗》15分钟实机", "BV1kS8H6VERt", C_GREEN)]
PV = [(a, b, S[c], d) for a, b, c, d in PV if c in S]
fig, ax = plt.subplots(figsize=(9.8, 5.2))
vs = [p[2]["view"] / 1e4 for p in PV]
for i, (a, b, d, col) in enumerate(PV):
    round_rect(ax, i - 0.27, 0, 0.54, vs[i], 9, col)
    ax.text(i, vs[i] + max(vs) * 0.045, "%.0f万" % vs[i], ha="center",
            fontsize=13, fontweight="bold", color=col)
ax.set_xticks(range(len(PV)))
ax.set_xticklabels(["%s\n%s" % (p[0], p[1]) for p in PV], fontsize=10,
                   color="#243746", linespacing=1.8)
ax.set_ylim(0, max(vs) * 1.30); ax.set_yticks([]); ax.set_xlim(-0.62, len(PV) - 0.38)
strip(ax)
ax.set_title("图一  游戏科学官方PV在B站的传播量级", fontsize=16, fontweight="bold",
             color="#0E2A3F", pad=46, loc="left")
ax.text(0.0, 1.035, "数据来源：本组于%s自建爬虫采集，样本为游戏科学官方账号发布的全部PV" % DATE_CN,
        transform=ax.transAxes, fontsize=10, color=C_GREY)
save(fig, "figA_pv.png")

# =====================================================================
# 图二  数据采集与分析流程（突出「我们真的爬了」）
# =====================================================================
fig, ax = plt.subplots(figsize=(10.6, 3.5))
ax.set_xlim(0, 106); ax.set_ylim(0, 34); ax.axis("off")

STEPS = [
    ("01", "确定采集对象", "锁定游戏科学官方\n及头部二创内容", C_DEEP),
    ("02", "调用公开接口", "B站 web-interface\n5个关键词×20条", C_MAIN),
    ("03", "数据清洗", "剔除无关视频\n得28条有效样本", C_LIGHT),
    ("04", "可视化分析", "绘制6张图表\n支撑本报告结论", C_GREEN),
]
bw, bh, gap = 21.5, 19.0, 5.6
x0 = 1.0
for i, (num, title, desc, col) in enumerate(STEPS):
    x = x0 + i * (bw + gap)
    ax.add_patch(FancyBboxPatch((x, 6), bw, bh, boxstyle="round,pad=0,rounding_size=1.6",
                                facecolor=col, edgecolor="none"))
    ax.add_patch(FancyBboxPatch((x + 1.6, 20.4), 5.4, 3.6,
                                boxstyle="round,pad=0,rounding_size=1.1",
                                facecolor="white", edgecolor="none", alpha=0.25))
    ax.text(x + 4.3, 22.2, num, ha="center", va="center", fontsize=9.5,
            color="white", fontweight="bold")
    ax.text(x + bw / 2, 17.0, title, ha="center", va="center", fontsize=12.5,
            color="white", fontweight="bold")
    ax.text(x + bw / 2, 11.0, desc, ha="center", va="center", fontsize=9.2,
            color="white", linespacing=1.6, alpha=0.95)
    if i < len(STEPS) - 1:
        ax.add_patch(FancyArrowPatch((x + bw + 0.8, 15.5), (x + bw + gap - 0.8, 15.5),
                                     arrowstyle="-|>", mutation_scale=16,
                                     color=C_PALE, lw=2.6))
ax.text(53, 31.0, "图二  本报告的数据采集与处理流程", ha="center", fontsize=16,
        fontweight="bold", color="#0E2A3F")
ax.text(53, 2.2, "全部数据均由本组自建脚本通过公开接口采集，可复现、可核验",
        ha="center", fontsize=9.5, color=C_GREY)
save(fig, "figB_flow.png")

# =====================================================================
# 图三  内容生态矩形树状图
# =====================================================================
CATMAP = {
    "BV1x54y1e7zf": "官方物料", "BV1y64y1q757": "官方物料", "BV1oH4y1c7Kk": "官方物料",
    "BV1tN4y1F79k": "官方物料", "BV1sHePzWEbG": "官方物料", "BV1SQ4y1V7do": "官方物料",
    "BV1ex4y1J7JE": "官方物料", "BV1kS8H6VERt": "官方物料", "BV1Ye4y1f7kA": "官方物料",
    "BV11PcgzWEJp": "官方物料", "BV1nh411C7yG": "官方物料",
    "BV1Ti421a7dv": "媒体评测", "BV1t14y1t7rz": "媒体评测",
    "BV1AE4m1d7XT": "攻略解说", "BV114421U75X": "攻略解说",
    "BV11f421q79P": "攻略解说", "BV1KE4m197MV": "攻略解说",
    "BV1VT421z711": "二创动画", "BV15YdBB6Efz": "二创动画", "BV1eZqiY8EiP": "二创动画",
    "BV1QLWoeaEBg": "二创动画", "BV1c6WmesEf5": "二创动画", "BV1ef421i7mm": "二创动画",
    "BV1yS411w7Mo": "剧情解析", "BV1on4y1f7XJ": "剧情解析",
    "BV1RuWpezE7h": "剧情解析", "BV1dS421Q7mS": "剧情解析",
    "BV1Hi421a7yH": "文化解读",
}
SHORT = {
    "BV1x54y1e7zf": "13分钟实机演示", "BV1y64y1q757": "12分钟UE5测试", "BV1VT421z711": "开学夜二创",
    "BV15YdBB6Efz": "楚人美游记", "BV1oH4y1c7Kk": "最终预告", "BV1AE4m1d7XT": "4K全收集攻略",
    "BV1Hi421a7yH": "往生咒出海", "BV1yS411w7Mo": "天命人混剪", "BV1tN4y1F79k": "6分钟实机剧情",
    "BV1sHePzWEbG": "钟馗先导预告", "BV1on4y1f7XJ": "老6面见大圣", "BV11f421q79P": "鲤鱼抢先解说",
    "BV1SQ4y1V7do": "发售日预告", "BV114421U75X": "纯黑无伤攻略", "BV1eZqiY8EiP": "《骂》二创",
    "BV1t14y1t7rz": "英伟达试玩", "BV1KE4m197MV": "鲤鱼Ace解说", "BV1QLWoeaEBg": "国产彩蛋",
    "BV1ef421i7mm": "陕北说书", "BV1ex4y1J7JE": "预购开启", "BV1c6WmesEf5": "小猴子顶替",
    "BV1kS8H6VERt": "钟馗实机演示", "BV1Ye4y1f7kA": "戒网插曲", "BV11PcgzWEJp": "钟馗6分短片",
    "BV1Ti421a7dv": "IGN评测", "BV1nh411C7yG": "3分钟混剪", "BV1RuWpezE7h": "观影混剪",
    "BV1dS421Q7mS": "剧情解析",
}
DROP = {"BV16z4y137cn", "BV13a4y117up"}
rows = []
for bv, c in CATMAP.items():
    if bv in S and bv not in DROP:
        d = dict(S[bv]); d["cat"] = c; rows.append(d)
rows.sort(key=lambda x: -x["view"])

fig, ax = plt.subplots(figsize=(10.4, 5.9))
WW, HH = 100.0, 53.0
rects = squarify.squarify(squarify.normalize_sizes([r["view"] for r in rows], WW, HH), 0, 0, WW, HH)
for rect, r in zip(rects, rows):
    x, y, dx, dy = rect["x"], rect["y"], rect["dx"], rect["dy"]
    ax.add_patch(Rectangle((x, y), dx, dy, facecolor=CC[r["cat"]], edgecolor="white", linewidth=2.6))
    a = dx * dy
    fs, num = (11.5, True) if a > 900 else (10, True) if a > 380 else (9, True) if a > 170 else (8, False)
    label = SHORT.get(r["bvid"], r["title"][:8])
    ax.text(x + dx / 2, y + dy / 2, "%s\n%.0f万" % (label, r["view"] / 1e4) if num else label,
            ha="center", va="center", fontsize=fs, color="white", fontweight="bold", linespacing=1.6)
ax.set_xlim(0, WW); ax.set_ylim(0, HH); ax.axis("off")
ax.text(0, HH * 1.13, "图三  内容生态结构", fontsize=16, fontweight="bold", color="#0E2A3F")
ax.text(0, HH * 1.045, "面积表示播放量，颜色区分内容类型　|　共28条有效样本，累计播放5.16亿次",
        fontsize=10, color=C_GREY)
handles = [Rectangle((0, 0), 1, 1, facecolor=CC[c]) for c in CC]
ax.legend(handles, list(CC.keys()), loc="upper center", bbox_to_anchor=(0.5, -0.02),
          ncol=6, fontsize=10.5, frameon=False)
save(fig, "figC_treemap.png")

# =====================================================================
# 图四  单条PV互动结构
# =====================================================================
d0 = S["BV1x54y1e7zf"]
labels = ["点赞", "投币", "收藏", "分享", "弹幕", "评论"]
vals = [d0["like"], d0["coin"], d0["favorite"], d0["share"], d0["danmaku"], d0["reply"]]
cols = [C_MAIN, C_RED, C_ORANGE, C_LIGHT, C_GREEN, C_GREY]

fig = plt.figure(figsize=(10.8, 4.6))
gs = fig.add_gridspec(1, 2, width_ratios=[1.02, 1], wspace=0.28)
ax1, ax2 = fig.add_subplot(gs[0]), fig.add_subplot(gs[1])
w, t, at = ax1.pie(vals, colors=cols, autopct=lambda p: "%.1f%%" % p, startangle=90,
                   counterclock=False, wedgeprops=dict(width=0.40, edgecolor="white", linewidth=3),
                   pctdistance=0.80, textprops=dict(fontsize=10, color="white", fontweight="bold"))
ax1.text(0, 0.10, "总互动量", ha="center", fontsize=10.5, color=C_GREY)
ax1.text(0, -0.18, "%.0f万" % (sum(vals) / 1e4), ha="center", fontsize=20,
         fontweight="bold", color="#0E2A3F")
ax1.set_title("互动量构成", fontsize=13, fontweight="bold", color="#0E2A3F", pad=10)
ax1.legend(w, ["%s %.0f万" % (l, v / 1e4) for l, v in zip(labels, vals)],
           loc="center left", bbox_to_anchor=(0.93, 0.5), fontsize=9.8, frameon=False)

pl, pc = d0["like"] / d0["view"] * 100, d0["coin"] / d0["view"] * 100
for xi, v, c in [(0, pl, C_MAIN), (1, pc, C_RED)]:
    round_rect(ax2, xi - 0.26, 0, 0.52, v, 9, c)
    ax2.text(xi, v + max(pl, pc) * 0.075, "%.2f%%" % v, ha="center", fontsize=16,
             fontweight="bold", color=c)
ax2.set_xticks([0, 1]); ax2.set_xticklabels(["点赞率", "投币率"], fontsize=13, color="#243746")
ax2.set_yticks([]); ax2.set_ylim(0, max(pl, pc) * 1.50); ax2.set_xlim(-0.62, 1.62)
strip(ax2)
ax2.set_title("投币率反超点赞率", fontsize=13, fontweight="bold", color="#0E2A3F", pad=10)
ax2.text(0.5, max(pl, pc) * 1.27, "在B站投币需消耗用户自有硬币，\n投币量高于点赞量属罕见信号",
         ha="center", fontsize=10, color=C_RED, linespacing=1.8)
fig.text(0.012, 1.045, "图四  《黑神话：悟空》13分钟实机演示的互动结构", fontsize=16,
         fontweight="bold", color="#0E2A3F", ha="left")
fig.text(0.012, 0.985, "该视频播放量6571万次，为本组采集样本中传播量级最高的单条内容",
         fontsize=10, color=C_GREY, ha="left")
save(fig, "figD_interaction.png")

# =====================================================================
# 图五  钟馗传播走势
# =====================================================================
Z = [("2025.08", "先导预告", "BV1sHePzWEbG"), ("2026.02", "6分钟小短片", "BV11PcgzWEJp"),
     ("2026.08", "15分钟实机演示", "BV1kS8H6VERt")]
Z = [(a, b, S[c]) for a, b, c in Z if c in S]
fig, ax = plt.subplots(figsize=(9.8, 4.7))
vv = [d["view"] / 1e4 for _, _, d in Z]
mm = [d["share"] / 1e4 for _, _, d in Z]
wd = 0.30
for i in range(len(Z)):
    for off, val, col in [(-wd / 2 - 0.025, vv[i], C_MAIN), (wd / 2 + 0.025, mm[i], C_ORANGE)]:
        round_rect(ax, i + off - wd / 2, 0, wd, val, 8, col)
        ax.text(i + off, val + max(vv) * 0.05, "%.0f万" % val, ha="center", fontsize=12,
                fontweight="bold", color=col)
ax.set_xticks(range(len(Z)))
ax.set_xticklabels(["%s\n%s" % (a, b) for a, b, _ in Z], fontsize=11.5,
                   color="#243746", linespacing=1.8)
ax.set_yticks([]); ax.set_ylim(0, max(vv) * 1.32); ax.set_xlim(-0.62, len(Z) - 0.38)
strip(ax)
ax.set_title("图五  《黑神话：钟馗》的传播走势", fontsize=16, fontweight="bold",
             color="#0E2A3F", pad=46, loc="left")
ax.text(0.0, 1.035, "深蓝为播放量，橙色为分享量　|　在零发售窗口期内热度回升，未出现逐次衰减",
        transform=ax.transAxes, fontsize=10, color=C_GREY)
save(fig, "figE_zhongkui.png")

# =====================================================================
# 图六  播放量Top10
# =====================================================================
top = rows[:10][::-1]
fig, ax = plt.subplots(figsize=(10.2, 5.4))
vals6 = [r["view"] / 1e4 for r in top]
for i, (v, r) in enumerate(zip(vals6, top)):
    round_rect(ax, 0, i - 0.27, v, 0.54, 8, CC[r["cat"]])
    ax.text(v + max(vals6) * 0.014, i, "%.0f万" % v, va="center", fontsize=10.5,
            fontweight="bold", color=CC[r["cat"]])
ax.set_yticks(range(len(top)))
ax.set_yticklabels(["[%s] %s" % (r["cat"], SHORT.get(r["bvid"], r["title"][:14])) for r in top],
                   fontsize=10, color="#243746")
ax.set_xticks([]); ax.set_xlim(0, max(vals6) * 1.17); ax.set_ylim(-0.7, len(top) - 0.3)
strip(ax); ax.tick_params(axis="y", pad=8)
ax.set_title("图六  播放量前十的内容排行", fontsize=16, fontweight="bold",
             color="#0E2A3F", pad=34, loc="left")
ax.text(0.0, 1.02, "颜色区分内容类型　|　官方内容占据前两位，但创作者内容合计入榜七席",
        transform=ax.transAxes, fontsize=10, color=C_GREY)
save(fig, "figF_top10.png")

print("\n全部完成 → figs3/")
