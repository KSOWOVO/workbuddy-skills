# -*- coding: utf-8 -*-
"""
作业图表集 v2 —— 基于 bili_raw.json 真实采集数据
产出 10 张图表，覆盖：柱状图 / 环形饼图 / 双层饼图 / 矩形树状图(Treemap) /
雷达图 / 热力图 / 横向条形图 / 趋势图 / 5A路径图
"""
import json, os, sys, math
sys.stdout.reconfigure(encoding="utf-8")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle
import squarify

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIGS = os.path.join(BASE, "figs")
os.makedirs(FIGS, exist_ok=True)

# ---------------- 中文字体 ----------------
for fp in [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\msyhbd.ttc", r"C:\Windows\Fonts\simhei.ttf"]:
    if os.path.exists(fp):
        font_manager.fontManager.addfont(fp)
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.facecolor"] = "white"
plt.rcParams["axes.facecolor"] = "white"
plt.rcParams["savefig.facecolor"] = "white"
plt.rcParams["axes.edgecolor"] = "#c8ccd4"
plt.rcParams["xtick.color"] = "#404652"
plt.rcParams["ytick.color"] = "#404652"
plt.rcParams["axes.labelcolor"] = "#2c3240"
plt.rcParams["text.color"] = "#1a1d24"

raw = json.load(open(os.path.join(BASE, "data", "bili_raw.json"), encoding="utf-8"))
S = {s["bvid"]: s for s in raw["stats"]}
DATE = raw["collected_at"][:10]

# ================= 内容分类映射（人工核定，基于标题+作者） =================
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
DROP = {"BV16z4y137cn", "BV13a4y117up"}          # 与原题无关，剔除

rows = []
for bvid, cat in CATMAP.items():
    if bvid in S and bvid not in DROP:
        d = dict(S[bvid]); d["cat"] = cat; rows.append(d)
rows.sort(key=lambda x: -(x.get("view") or 0))
print("有效样本:", len(rows), "（已剔除无关 %d 条）" % len(DROP))

CATS = ["官方物料", "攻略解说", "二创动画", "剧情解析", "媒体评测", "文化解读"]
CCOLOR = {
    "官方物料": "#B03A2E", "攻略解说": "#2E86C1", "二创动画": "#8E44AD",
    "剧情解析": "#16A085", "媒体评测": "#E67E22", "文化解读": "#34495E",
}

# 短标签（用于树状图等空间受限处，按 bvid 人工核定）
SHORT = {
    "BV1x54y1e7zf": "13分钟实机演示", "BV1y64y1q757": "12分钟UE5测试",
    "BV1VT421z711": "开学夜·鬼畜二创", "BV15YdBB6Efz": "楚人美游记",
    "BV1oH4y1c7Kk": "最终预告", "BV1AE4m1d7XT": "4K全收集攻略",
    "BV1Hi421a7yH": "往生咒出海", "BV1yS411w7Mo": "天命人混剪",
    "BV1tN4y1F79k": "6分钟实机剧情", "BV1sHePzWEbG": "钟馗先导预告",
    "BV1on4y1f7XJ": "老6面见大圣", "BV11f421q79P": "鲤鱼Ace抢先解说",
    "BV1SQ4y1V7do": "发售日预告", "BV114421U75X": "纯黑无伤攻略",
    "BV1eZqiY8EiP": "《骂》二创", "BV1t14y1t7rz": "英伟达独家试玩",
    "BV1KE4m197MV": "鲤鱼Ace解说", "BV1QLWoeaEBg": "国产彩蛋解读",
    "BV1ef421i7mm": "陕北说书二创", "BV1ex4y1J7JE": "预购开启预告",
    "BV1c6WmesEf5": "小猴子顶替", "BV1kS8H6VERt": "钟馗实机演示",
    "BV1Ye4y1f7kA": "戒网（插曲）", "BV11PcgzWEJp": "钟馗6分短片",
    "BV1Ti421a7dv": "IGN 10分评测", "BV1nh411C7yG": "3分钟混剪",
    "BV1RuWpezE7h": "观影向混剪", "BV1dS421Q7mS": "剧情解析",
}

M = ["view", "like", "coin", "favorite", "share", "danmaku", "reply"]
for r in rows:
    for k in M:
        r.setdefault(k, 0)
    r["shareRate"] = (r["share"] or 0) / r["view"] * 100 if r["view"] else 0


def W(fig, name):
    p = os.path.join(FIGS, name)
    fig.savefig(p, bbox_inches="tight", dpi=300)
    plt.close(fig)
    print("  ✔", name)


# =====================================================================
# 图1  官方PV传播量级（柱状图）
# =====================================================================
PV = [("2020.08\n13分钟实机演示", "BV1x54y1e7zf"), ("2022.08\n6分钟实机剧情", "BV1tN4y1F79k"),
      ("2024.08\n最终预告", "BV1oH4y1c7Kk"), ("2025.08\n《钟馗》先导预告", "BV1sHePzWEbG"),
      ("2026.08\n《钟馗》15分钟实机", "BV1kS8H6VERt")]
PV = [(a, S[b]) for a, b in PV if b in S]
fig, ax = plt.subplots(figsize=(9.4, 4.7))
vs = [(x[1]["view"] or 0) / 1e4 for x in PV]
bars = ax.bar(range(len(PV)), vs, width=0.55,
              color=["#922B21", "#C0392B", "#E67E22", "#8E44AD", "#16A085"], alpha=0.92,
              edgecolor="white", linewidth=1.2)
for i, (v, (_, d)) in enumerate(zip(vs, PV)):
    ax.text(i, v + max(vs) * 0.028, "%.1f万" % v, ha="center", fontsize=10.5,
            fontweight="bold", color="#7B241C")
    ax.text(i, v * 0.52, "点赞 %.0f万\n投币 %.0f万\n弹幕 %.1f万" % (
        d["like"] / 1e4, d["coin"] / 1e4, d["danmaku"] / 1e4),
        ha="center", va="center", fontsize=8.2, color="white", linespacing=1.7)
ax.set_xticks(range(len(PV))); ax.set_xticklabels([p[0] for p in PV], fontsize=9.2)
ax.set_ylabel("B站播放量（万次）", fontsize=10.5)
ax.set_ylim(0, max(vs) * 1.2)
ax.set_title("图1  《黑神话》系列官方PV在B站的传播量级\n（本组 %s 自主采集）" % DATE,
             fontsize=12.5, fontweight="bold", pad=13)
ax.grid(axis="y", ls=":", alpha=0.35); ax.set_axisbelow(True)
for s in ["top", "right"]:
    ax.spines[s].set_visible(False)
W(fig, "fig1_pv_views.png")

# =====================================================================
# 图2  单条PV互动结构（环形饼图）—— 替换原柱状漏斗，更直观
# =====================================================================
d0 = S["BV1x54y1e7zf"]
labels = ["点赞", "投币", "收藏", "分享", "弹幕", "评论"]
vals = [d0["like"], d0["coin"], d0["favorite"], d0["share"], d0["danmaku"], d0["reply"]]
cols = ["#C0392B", "#1E8449", "#F1C40F", "#2E86C1", "#E67E22", "#7D3C98"]
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.8, 4.9), gridspec_kw={"width_ratios": [1, 1]})

wedges, texts, ats = ax1.pie(
    vals, labels=None, colors=cols, autopct=lambda p: "%.1f%%" % p,
    startangle=100, counterclock=False,
    wedgeprops=dict(width=0.42, edgecolor="white", linewidth=2),
    pctdistance=0.79, textprops=dict(fontsize=9.5, color="white", fontweight="bold"))
ax1.text(0, 0.08, "总互动", ha="center", fontsize=10, color="#5d6a7a")
ax1.text(0, -0.16, "%.0f万" % (sum(vals) / 1e4), ha="center", fontsize=15,
         fontweight="bold", color="#1a1d24")
ax1.set_title("(a) 互动量结构占比", fontsize=11, fontweight="bold", pad=10)
ax1.legend(wedges, ["%s %.1f万" % (l, v / 1e4) for l, v in zip(labels, vals)],
           loc="center left", bbox_to_anchor=(0.92, 0.5), fontsize=8.8, frameon=False)

pct_like = d0["like"] / d0["view"] * 100
pct_coin = d0["coin"] / d0["view"] * 100
ax2.bar([0, 1], [pct_like, pct_coin], width=0.5, color=["#C0392B", "#1E8449"],
        alpha=0.92, edgecolor="white", linewidth=1.5)
for x, v, c in [(0, pct_like, "#7B241C"), (1, pct_coin, "#145A32")]:
    ax2.text(x, v + 0.13, "%.2f%%" % v, ha="center", fontsize=13, fontweight="bold", color=c)
ax2.annotate("投币率 > 点赞率\n（B站极罕见）", xy=(1, pct_coin), xytext=(0.42, pct_coin * 1.06),
             fontsize=10, color="#1E8449", fontweight="bold", ha="center",
             arrowprops=dict(arrowstyle="->", color="#1E8449", lw=1.6))
ax2.set_xticks([0, 1]); ax2.set_xticklabels(["点赞率", "投币率"], fontsize=11.5)
ax2.set_ylabel("占播放量比例（%）", fontsize=10.5)
ax2.set_ylim(0, max(pct_like, pct_coin) * 1.42)
ax2.set_title("(b) 投币率反超点赞率", fontsize=11, fontweight="bold", pad=10)
ax2.grid(axis="y", ls=":", alpha=0.35); ax2.set_axisbelow(True)
for s in ["top", "right"]:
    ax2.spines[s].set_visible(False)
fig.suptitle("图2  《黑神话：悟空》13分钟实机演示的B站互动结构（播放量 6,570.7万）",
             fontsize=12.5, fontweight="bold", y=1.0)
plt.tight_layout(rect=[0, 0, 1, 0.94])
W(fig, "fig2_funnel.png")

# =====================================================================
# 图3  PGC vs UGC 传播效率（分组柱状图）
# =====================================================================
offi = [r for r in rows if r["cat"] == "官方物料"]
ugc = [r for r in rows if r["cat"] != "官方物料"]
metrics = ["播放量", "点赞数", "投币数", "分享数"]
keys = ["view", "like", "coin", "share"]
o_v = [sum(r[k] for r in offi) / len(offi) for k in keys]
u_v = [sum(r[k] for r in ugc) / len(ugc) for k in keys]
fig, ax = plt.subplots(figsize=(9.4, 4.6))
x = np.arange(len(metrics)); w = 0.36
ax.bar(x - w / 2, [v / 1e4 for v in o_v], width=w, color="#B03A2E", alpha=0.92,
       edgecolor="white", linewidth=1.2, label="官方PGC（n=%d）" % len(offi))
ax.bar(x + w / 2, [v / 1e4 for v in u_v], width=w, color="#2E86C1", alpha=0.92,
       edgecolor="white", linewidth=1.2, label="创作者UGC（n=%d）" % len(ugc))
for i, (a, b) in enumerate(zip(o_v, u_v)):
    ax.text(i - w / 2, a / 1e4 + max(o_v) / 1e4 * 0.035, "%.0f万" % (a / 1e4),
            ha="center", fontsize=9.5, fontweight="bold", color="#7B241C")
    ax.text(i + w / 2, b / 1e4 + max(o_v) / 1e4 * 0.035, "%.0f万" % (b / 1e4),
            ha="center", fontsize=9.5, fontweight="bold", color="#1A5276")
    ax.text(i, -max(o_v) / 1e4 * 0.115, "官方为UGC的\n%.1f倍" % (a / b if b else 0),
            ha="center", fontsize=8.2, color="#5d6a7a", linespacing=1.5)
ax.set_xticks(x); ax.set_xticklabels(metrics, fontsize=11)
ax.set_ylabel("平均值（万）", fontsize=10.5)
ax.set_ylim(-max(o_v) / 1e4 * 0.20, max(o_v) / 1e4 * 1.20)
ax.set_title("图3  官方PGC与创作者UGC的传播效率对比（样本：有效30条中的28条）",
             fontsize=12.5, fontweight="bold", pad=13)
ax.legend(fontsize=9.5, frameon=False)
ax.grid(axis="y", ls=":", alpha=0.35); ax.set_axisbelow(True)
for s in ["top", "right"]:
    ax.spines[s].set_visible(False)
W(fig, "fig3_pgc_vs_ugc.png")

# =====================================================================
# 图4  《钟馗》传播走势（柱状+折线组合）
# =====================================================================
z = [("2025.08\n先导预告", "BV1sHePzWEbG"), ("2026.02\n6分钟小短片", "BV11PcgzWEJp"),
     ("2026.08\n15分钟实机演示", "BV1kS8H6VERt")]
z = [(a, S[b]) for a, b in z if b in S]
fig, ax = plt.subplots(figsize=(9.4, 4.6))
xx = np.arange(len(z)); w = 0.34
vv = [d["view"] / 1e4 for _, d in z]
mm = [d["share"] / 1e4 for _, d in z]
ax.bar(xx - w / 2, vv, width=w, color="#8E44AD", alpha=0.92, edgecolor="white",
       linewidth=1.2, label="播放量（万）")
ax.bar(xx + w / 2, mm, width=w, color="#16A085", alpha=0.92, edgecolor="white",
       linewidth=1.2, label="分享量（万）")
for i, (a, b) in enumerate(zip(vv, mm)):
    ax.text(i - w / 2, a + max(vv) * 0.03, "%.0f万" % a, ha="center", fontsize=10, fontweight="bold", color="#6C3483")
    ax.text(i + w / 2, b + max(vv) * 0.03, "%.0f万" % b, ha="center", fontsize=10, fontweight="bold", color="#117A65")
ax2 = ax.twinx()
sr = [d["share"] / d["view"] * 100 for _, d in z]
ax2.plot(xx, sr, marker="D", ms=8, lw=2.2, color="#C0392B", ls="--", label="分享率（%）")
for i, v in enumerate(sr):
    ax2.text(i, v + 0.28, "%.2f%%" % v, ha="center", fontsize=9.5, fontweight="bold", color="#922B21")
ax2.set_ylabel("分享率（%）", fontsize=10.5, color="#922B21")
ax2.tick_params(axis="y", colors="#922B21")
ax2.set_ylim(0, max(sr) * 1.55)
ax.set_xticks(xx); ax.set_xticklabels([a for a, _ in z], fontsize=10)
ax.set_ylabel("数量（万）", fontsize=10.5)
ax.set_ylim(0, max(vv) * 1.28)
h1, l1 = ax.get_legend_handles_labels(); h2, l2 = ax2.get_legend_handles_labels()
ax.legend(h1 + h2, l1 + l2, fontsize=9.5, frameon=False, loc="upper left")
ax.set_title("图4  《黑神话：钟馗》系列内容的传播走势（零发售窗口期热度回升）",
             fontsize=12.5, fontweight="bold", pad=13)
ax.grid(axis="y", ls=":", alpha=0.32); ax.set_axisbelow(True)
for s in ["top"]:
    ax.spines[s].set_visible(False); ax2.spines[s].set_visible(False)
W(fig, "fig4_zhongkui.png")

# =====================================================================
# 图5  内容生态矩形树状图 Treemap（用户要的"树状图"）
# =====================================================================
fig, ax = plt.subplots(figsize=(10.2, 5.8))
WW, HH = 100.0, 54.0
sizes = [r["view"] for r in rows]
_norm = squarify.normalize_sizes(sizes, WW, HH)
_rects = squarify.squarify(_norm, 0, 0, WW, HH)
for rect, r in zip(_rects, rows):
    x, y, dx, dy = rect["x"], rect["y"], rect["dx"], rect["dy"]
    c = CCOLOR[r["cat"]]
    ax.add_patch(Rectangle((x, y), dx, dy, facecolor=c, edgecolor="white", linewidth=2.0))
    area = dx * dy
    if area > 900:
        fs, show_num = 10.5, True
    elif area > 380:
        fs, show_num = 9.2, True
    elif area > 170:
        fs, show_num = 8.0, True
    else:
        fs, show_num = 7.0, False
    label = SHORT.get(r["bvid"], r["title"][:8])
    txt = "%s\n%.0f万" % (label, r["view"] / 1e4) if show_num else label
    ax.text(x + dx / 2, y + dy / 2, txt, ha="center", va="center",
            fontsize=fs, color="white", fontweight="bold", linespacing=1.5)
ax.set_xlim(0, WW); ax.set_ylim(0, HH); ax.axis("off")
ax.set_title("图5  《黑神话》内容生态矩形树状图 —— 面积 = B站播放量，颜色 = 内容类型\n"
             "（本组 %s 自主采集，含官方物料/攻略/二创/解析 等 6 类共 28 条，累计播放 5.16 亿次）" % DATE,
             fontsize=12.2, fontweight="bold", pad=14)
handles = [Rectangle((0, 0), 1, 1, facecolor=CCOLOR[c]) for c in CATS]
ax.legend(handles, CATS, loc="upper center", bbox_to_anchor=(0.5, -0.02),
          ncol=6, fontsize=9.2, frameon=False)
W(fig, "fig5_treemap.png")

# =====================================================================
# 图6  内容类型分布双层饼图（用户要的"饼图"）
# =====================================================================
fig, (a1, a2) = plt.subplots(1, 2, figsize=(10.4, 5.0))
cnt = {c: len([r for r in rows if r["cat"] == c]) for c in CATS}
vv1 = {c: sum(r["view"] for r in rows if r["cat"] == c) for c in CATS}
cs = [CCOLOR[c] for c in CATS]
w1, t1, a1p = a1.pie([cnt[c] for c in CATS], labels=[c for c in CATS], colors=cs,
                     autopct="%1.0f%%", startangle=90, counterclock=False,
                     wedgeprops=dict(width=0.45, edgecolor="white", linewidth=2),
                     pctdistance=0.78, textprops=dict(fontsize=10))
for t in a1p:
    t.set_color("white"); t.set_fontweight("bold"); t.set_fontsize(9.5)
a1.text(0, 0, "28条\n内容", ha="center", va="center", fontsize=12, fontweight="bold", color="#1a1d24", linespacing=1.4)
a1.set_title("(a) 各类内容「数量」占比", fontsize=11.5, fontweight="bold", pad=12)

w2, t2, a2p = a2.pie([vv1[c] for c in CATS], labels=[c for c in CATS], colors=cs,
                     autopct="%1.0f%%", startangle=90, counterclock=False,
                     wedgeprops=dict(width=0.45, edgecolor="white", linewidth=2),
                     pctdistance=0.78, textprops=dict(fontsize=10))
for t in a2p:
    t.set_color("white"); t.set_fontweight("bold"); t.set_fontsize(9.5)
tot = sum(vv1.values())
a2.text(0, 0, "%.1f亿\n次播放" % (tot / 1e8), ha="center", va="center", fontsize=12,
        fontweight="bold", color="#1a1d24", linespacing=1.4)
a2.set_title("(b) 各类内容「播放量」占比", fontsize=11.5, fontweight="bold", pad=12)

fig.suptitle("图6  内容类型分布：官方物料以 39% 的数量贡献了 46% 的播放量",
             fontsize=12.8, fontweight="bold", y=1.0)
plt.tight_layout(rect=[0, 0, 1, 0.93])
W(fig, "fig6_pie.png")

# =====================================================================
# 图7  官方PV多维互动率雷达图（用户要的"雷达图"）
# =====================================================================
RADAR = [("2020.08 13分钟实机", "BV1x54y1e7zf", "#922B21"),
         ("2022.08 6分钟剧情", "BV1tN4y1F79k", "#E67E22"),
         ("2024.08 最终预告", "BV1oH4y1c7Kk", "#2E86C1"),
         ("2025.08 钟馗先导", "BV1sHePzWEbG", "#8E44AD"),
         ("2026.08 钟馗实机", "BV1kS8H6VERt", "#16A085")]
RADAR = [(a, S[b], c) for a, b, c in RADAR if b in S]
axk = ["点赞率", "投币率", "收藏率", "分享率", "弹幕率"]
kkey = ["like", "coin", "favorite", "share", "danmaku"]
ang = np.linspace(0, 2 * np.pi, len(axk), endpoint=False).tolist()
ang += ang[:1]

fig, ax = plt.subplots(figsize=(7.6, 6.4), subplot_kw=dict(polar=True))
for name, d, c in RADAR:
    v = [d[k] / d["view"] * 100 for k in kkey]
    v += v[:1]
    ax.plot(ang, v, lw=2.6, color=c, label=name, marker="o", ms=5)
    ax.fill(ang, v, color=c, alpha=0.055)
ax.set_xticks(ang[:-1]); ax.set_xticklabels(axk, fontsize=12)
ax.set_ylim(0, 7)
ax.set_yticks([1, 2, 3, 4, 5, 6])
ax.set_yticklabels(["1%", "2%", "3%", "4%", "5%", "6%"], fontsize=8.2, color="#9aa2b1")
ax.set_rlabel_position(200)
ax.grid(color="#d5dae4", ls=":", alpha=0.9)
ax.spines["polar"].set_color("#d5dae4")
ax.spines["polar"].set_linewidth(1.1)
ax.tick_params(pad=9)
ax.set_title("图7  五支官方PV的多维互动率雷达图\n（各项均为「该项互动量 ÷ 播放量」）",
             fontsize=12.8, fontweight="bold", pad=28)
ax.legend(loc="upper left", bbox_to_anchor=(1.06, 1.10), fontsize=10, frameon=False)
W(fig, "fig7_radar.png")

# =====================================================================
# 图8  内容类型 × 互动指标 热力图（用户要的"热力图"）
# =====================================================================
mat, ylab = [], []
for c in CATS:
    sub = [r for r in rows if r["cat"] == c]
    if not sub:
        continue
    ylab.append("%s\n(n=%d)" % (c, len(sub)))
    mat.append([sum(r[k] for r in sub) / len(sub) for k in ["view", "like", "coin", "favorite", "share", "danmaku"]])
mat = np.array(mat, dtype=float)
# 按列做 0-1 归一化，突出相对强弱
norm = (mat - mat.min(axis=0)) / (mat.max(axis=0) - mat.min(axis=0) + 1e-9)

fig, ax = plt.subplots(figsize=(9.6, 4.5))
im = ax.imshow(norm, cmap="YlOrRd", aspect="auto", vmin=0, vmax=1)
ax.set_xticks(range(6))
ax.set_xticklabels(["播放量", "点赞", "投币", "收藏", "分享", "弹幕"], fontsize=11)
ax.set_yticks(range(len(ylab))); ax.set_yticklabels(ylab, fontsize=10)
for i in range(mat.shape[0]):
    for j in range(mat.shape[1]):
        v = mat[i, j]
        txt = ("%.0f万" % (v / 1e4)) if v >= 1e4 else ("%.0f" % v)
        ax.text(j, i, txt, ha="center", va="center", fontsize=8.6,
                color="white" if norm[i, j] > 0.55 else "#2c3240", fontweight="bold")
cb = fig.colorbar(im, ax=ax, fraction=0.028, pad=0.02)
cb.set_label("类内相对强度（列归一化）", fontsize=9)
cb.ax.tick_params(labelsize=8.5)
ax.set_title("图8  各内容类型的平均互动表现热力图（颜色越深 = 该指标相对越强）",
             fontsize=12.5, fontweight="bold", pad=13)
ax.spines[:].set_visible(False)
W(fig, "fig8_heatmap.png")

# =====================================================================
# 图9  TOP12 播放量横向条形图（用户要的"条形图"）
# =====================================================================
top = rows[:12][::-1]
fig, ax = plt.subplots(figsize=(10.0, 5.6))
vals = [r["view"] / 1e4 for r in top]
cols = [CCOLOR[r["cat"]] for r in top]
ax.barh(range(len(top)), vals, color=cols, alpha=0.93, height=0.66,
        edgecolor="white", linewidth=1.2)
for i, (v, r) in enumerate(zip(vals, top)):
    ax.text(v + max(vals) * 0.012, i, "%.0f万" % v, va="center", fontsize=9.2,
            fontweight="bold", color="#2c3240")
nm = ["[%s] %s" % (r["cat"], SHORT.get(r["bvid"], r["title"][:14])) for r in top]
ax.set_yticks(range(len(top))); ax.set_yticklabels(nm, fontsize=8.8)
ax.set_xlabel("B站播放量（万次）", fontsize=10.5)
ax.set_xlim(0, max(vals) * 1.15)
ax.set_title("图9  播放量 TOP12 内容排行（颜色 = 内容类型）", fontsize=12.5,
             fontweight="bold", pad=13)
ax.grid(axis="x", ls=":", alpha=0.32); ax.set_axisbelow(True)
for s in ["top", "right", "left"]:
    ax.spines[s].set_visible(False)
handles = [Rectangle((0, 0), 1, 1, facecolor=CCOLOR[c]) for c in CATS if any(r["cat"] == c for r in top)]
labs = [c for c in CATS if any(r["cat"] == c for r in top)]
ax.legend(handles, labs, loc="lower right", fontsize=9, frameon=False)
W(fig, "fig9_top12.png")

# =====================================================================
# 图10  5A消费者路径模型
# =====================================================================
fig, ax = plt.subplots(figsize=(10.0, 4.9))
ax.set_xlim(0, 10); ax.set_ylim(0, 5.2); ax.axis("off")
STEPS = [
    ("Aware\n了解", "13分钟实机演示\n24h播放破千万\nB站2h登顶热门第一", "#C0392B"),
    ("Appeal\n吸引", "连续六年\n「820」节点\n固化内容期待", "#E67E22"),
    ("Ask\n问询", "创作者UGC承接\n评测·攻略·考据\n（图3：n=17）", "#8E44AD"),
    ("Act\n行动", "预购+发售日预告\n3天销量破1000万套\n（官方公告）", "#2E86C1"),
    ("Advocate\n拥护", "二创·口碑扩散\n内容生态28条\n累计播放5.16亿", "#16A085"),
]
w, h, gap = 1.62, 2.5, 0.28
x0 = 0.42
for i, (title, desc, c) in enumerate(STEPS):
    x = x0 + i * (w + gap)
    ax.add_patch(FancyBboxPatch((x, 1.5), w, h, boxstyle="round,pad=0.06,rounding_size=0.12",
                                facecolor=c, edgecolor="none", alpha=0.93))
    ax.text(x + w / 2, 3.62, title, ha="center", va="center", fontsize=12.5,
            fontweight="bold", color="white", linespacing=1.45)
    ax.text(x + w / 2, 2.45, desc, ha="center", va="center", fontsize=8.5,
            color="white", linespacing=1.66)
    if i < len(STEPS) - 1:
        ax.add_patch(FancyArrowPatch((x + w + 0.02, 2.75), (x + w + gap - 0.02, 2.75),
                                     arrowstyle="-|>", mutation_scale=15, color="#5d6a7a", lw=1.9))
ax.text(5.0, 4.72, "图10  游戏科学《黑神话》营销的5A消费者路径转化",
        ha="center", fontsize=12.5, fontweight="bold", color="#1a1d24")
ax.text(5.0, 4.34, "理论来源：菲利普·科特勒《营销革命4.0》　|　数据来源：本组 %s 平台采集" % DATE,
        ha="center", fontsize=8.8, color="#5d6a7a")
ax.text(5.0, 1.02, "核心机制：以「可验证的真实内容」替代「营销承诺」，降低用户决策风险感知",
        ha="center", fontsize=9.8, color="#C0392B", fontweight="bold")
ax.text(5.0, 0.62, "关键差异：Ask（问询）环节由创作者UGC内容承接，构成信任中介——这是本案例区别于传统广告投放的核心",
        ha="center", fontsize=8.6, color="#5d6a7a")
W(fig, "fig10_5a_model.png")

print("\n图表总数: 10 张，输出目录 figs/")
print("累计播放量(28条有效): %.2f 亿" % (sum(r["view"] for r in rows) / 1e8))
for c in CATS:
    sub = [r for r in rows if r["cat"] == c]
    if sub:
        print("  %-6s 数量%2d (%.0f%%)  播放%.2f亿 (%.0f%%)" % (
            c, len(sub), len(sub) / len(rows) * 100,
            sum(r["view"] for r in sub) / 1e8,
            sum(r["view"] for r in sub) / sum(r["view"] for r in rows) * 100))
