#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
shot_filter.py — 截图语义筛（两阶段策略的第二阶段）

Kelsen 的原始要求（2026-09-22）：
    「你可以先全部截图下来，后面再进行筛选。比如就拿这个课来举例，后面可能会有
      一些总结，那总结里的思维导图和重要内容就可以记下来。但像那些只有例举一张
      图的 PPT，截下来干嘛？……只有重要的才要留下来，不是全要留的。」

设计：不靠"猜标题"，靠**像素信息量 + 文字密度 + 与邻帧的唯一性**三层打分。
课程类视频里，"纯 logo / 过场 / 讲师头像 / 单张举例插图" 的像素特征是稳定的：
    信息量低（大片纯色背景）+ OCR 文字少 → 低分
而"知识讲解页 / 思维导图 / 总结框架页"则相反：
    文字密度高 + 线条结构多 + 与前后帧差异大 → 高分

打分维度（0~100）：
    1. ink       墨迹占比 —— 非背景像素比例。纯 logo 页 <8%，讲解页 >18%
    2. edge      边缘密度 —— 线条/文字轮廓。PPT 文字页显著高于插画页
    3. uniq      唯一性 —— 与前后 N 帧的 pHash 距离。过场动画帧高度雷同
    4. text      文字块 —— 近似文字行的横向一致性（免 OCR 的快速代理）

分级：
    S (keep_hot)   ≥ 62   重点页：总结/思维导图/框架 → 必留
    A (keep)       45~62  正常讲解页 → 留
    B (maybe)      32~45  信息偏少 → 默认留，可手动删
    C (drop)       < 32   过场/logo/纯插画 → 移除
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

import cv2
import numpy as np

# ---------------- 阈值（可调） ----------------
INK_BG_TOL = 26        # 与背景色的容差，超过算"墨迹"
EDGE_LO = 60
EDGE_HI = 160
UNIQ_WINDOW = 6        # 唯一性比较的前后帧数
DROP_TH = 32
MAYBE_TH = 45
HOT_TH = 62


def _read_unicode(path: str) -> np.ndarray | None:
    """中文路径安全读图（cv2.imread 在中文路径下会静默返回 None）"""
    try:
        buf = np.fromfile(path, dtype=np.uint8)
        if buf.size == 0:
            return None
        return cv2.imdecode(buf, cv2.IMREAD_COLOR)
    except Exception:
        return None


def _phash(img: np.ndarray, hs: int = 16) -> np.ndarray:
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    g = cv2.resize(g, (hs + 1, hs), interpolation=cv2.INTER_AREA)
    diff = g[:, 1:] > g[:, :-1]
    return diff.flatten()


def _ink_ratio(img: np.ndarray) -> float:
    """墨迹占比：与画面主导色差出容差的像素比例。"""
    small = cv2.resize(img, (320, 180), interpolation=cv2.INTER_AREA)
    pix = small.reshape(-1, 3).astype(np.float32)
    # 主导色 = 出现最多的量化色
    q = (pix // 16).astype(np.uint8)
    key = q[:, 0].astype(np.int32) * 289 + q[:, 1].astype(np.int32) * 17 + q[:, 2]
    vals, counts = np.unique(key, return_counts=True)
    bg_key = vals[counts.argmax()]
    bg = np.array([(bg_key // 289) * 16 + 8,
                   ((bg_key // 17) % 17) * 16 + 8,
                   (bg_key % 17) * 16 + 8], dtype=np.float32)
    d = np.abs(pix - bg).max(axis=1)
    return float((d > INK_BG_TOL).mean())


def _edge_density(img: np.ndarray) -> float:
    small = cv2.resize(img, (480, 270), interpolation=cv2.INTER_AREA)
    g = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    e = cv2.Canny(g, EDGE_LO, EDGE_HI)
    return float((e > 0).mean())


def _text_score(img: np.ndarray) -> float:
    """
    免 OCR 的文字密度代理：把图横切成条，统计"条内有横向连续墨迹"的比例。
    文字行的特征是：局部方差高、方向以水平为主。
    """
    h, w = img.shape[:2]
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    g = cv2.resize(g, (640, 360), interpolation=cv2.INTER_AREA)
    inv = 255 - g
    _, bw = cv2.threshold(inv, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    # 水平投影：每一行的墨迹量
    rowsum = (bw > 0).sum(axis=1).astype(np.float32) / bw.shape[1]
    # 文字行 → 投影呈现"高-低-高"的条带
    if rowsum.max() <= 0:
        return 0.0
    r = rowsum / rowsum.max()
    banded = ((r > 0.10) & (r < 0.92)).mean()
    # 同时要求墨迹不太多也不太少
    ink = float((bw > 0).mean())
    density_ok = 1.0 - abs(ink - 0.16) / 0.16
    density_ok = max(0.0, min(1.0, density_ok))
    return float(0.5 * banded + 0.5 * density_ok)


def score_shots(shots: list[dict[str, Any]],
                window: int = UNIQ_WINDOW) -> list[dict[str, Any]]:
    """
    shots: [{"file": path, "ts": 秒}, ...] 按 ts 升序
    返回原地补上 score / grade / feats 的列表
    """
    n = len(shots)
    hashes: list[np.ndarray | None] = []
    feats: list[dict[str, float]] = []

    for s in shots:
        img = _read_unicode(s["file"])
        if img is None:
            hashes.append(None)
            feats.append({"ink": 0, "edge": 0, "text": 0})
            continue
        hashes.append(_phash(img))
        feats.append({
            "ink": _ink_ratio(img),
            "edge": _edge_density(img),
            "text": _text_score(img),
        })

    for i, s in enumerate(shots):
        f = feats[i]
        h = hashes[i]

        # --- 唯一性：与前后 window 帧的最小 pHash 距离 ---
        uniq = 1.0
        if h is not None:
            dmin = 999
            for j in range(max(0, i - window), min(n, i + window + 1)):
                if j == i or hashes[j] is None:
                    continue
                d = int((h != hashes[j]).sum())
                dmin = min(dmin, d)
            uniq = min(1.0, dmin / 40.0)   # 40 位差异算"完全不同"

        # --- 归一化 ---
        ink_n = min(1.0, max(0.0, (f["ink"] - 0.03) / 0.30))
        edge_n = min(1.0, f["edge"] / 0.12)
        text_n = f["text"]

        # 加权：文字密度最重要（课程视频的核心价值是"页面上的知识点"）
        raw = (text_n * 0.42 + ink_n * 0.23 + edge_n * 0.20 + uniq * 0.15)
        score = round(raw * 100, 1)

        if score >= HOT_TH:
            grade = "S"
        elif score >= MAYBE_TH:
            grade = "A"
        elif score >= DROP_TH:
            grade = "B"
        else:
            grade = "C"

        s["score"] = score
        s["grade"] = grade
        s["feats"] = {k: round(v, 4) for k, v in f.items()}
        s["uniq"] = round(uniq, 3)

    return shots


def apply_filter(shots: list[dict], md_path: str, assets_dir: str,
                 keep_grade=("S", "A", "B"), dry_run: bool = False) -> dict:
    """
    按 grade 裁剪 md 里的图片链接（不动被删的图片文件，交由调用方决定）。
    返回统计信息。
    """
    import re

    drop = [s for s in shots if s["grade"] not in keep_grade]
    keep = [s for s in shots if s["grade"] in keep_grade]

    stat = {
        "total": len(shots),
        "kept": len(keep),
        "dropped": len(drop),
        "by_grade": {g: sum(1 for s in shots if s["grade"] == g)
                     for g in ("S", "A", "B", "C")},
        "kept_files": [os.path.basename(s["file"]) for s in keep],
        "dropped_files": [os.path.basename(s["file"]) for s in drop],
    }
    if dry_run:
        return stat

    md = open(md_path, encoding="utf-8").read()
    for s in drop:
        name = os.path.basename(s["file"])
        # 删掉 `![[...<name>]]` 整行（连同紧随其后的空行）
        md = re.sub(r"!\[\[[^\]]*" + re.escape(name) + r"\]\]\n\n?", "", md)
    open(md_path, "w", encoding="utf-8").write(md)
    return stat


def main():
    if len(sys.argv) < 2:
        print("用法: python shot_filter.py <截图目录> [--json out.json] [--apply <md路径>]")
        sys.exit(1)

    assets = sys.argv[1]
    files = sorted(f for f in os.listdir(assets)
                   if f.lower().endswith((".jpg", ".jpeg", ".png")))
    shots = [{"file": os.path.join(assets, f), "ts": i * 1.0}
             for i, f in enumerate(files)]
    shots = score_shots(shots)

    by = {g: [s for s in shots if s["grade"] == g] for g in ("S", "A", "B", "C")}
    print(f"总计 {len(shots)} 张")
    for g in ("S", "A", "B", "C"):
        print(f"  {g}: {len(by[g])} 张")
    print("\nS 级（重点页）示例：")
    for s in by["S"][:10]:
        print(f"  {os.path.basename(s['file'])}  score={s['score']}  {s['feats']}")

    if "--json" in sys.argv:
        out = sys.argv[sys.argv.index("--json") + 1]
        json.dump(shots, open(out, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print(f"\n已写出 {out}")


if __name__ == "__main__":
    main()
