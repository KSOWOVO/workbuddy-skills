#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
skill_match.py — 零 LLM 成本的 Skill 本地路由打分器。

用途：在「不确定该用哪个 skill / 该不该用 skill / 该不该新建 skill」时，
      用本地 CPU 做关键词打分，代替"凭感觉读一个 16KB 的 SKILL.md"。
      一次调用输出 ~15 行，成本远低于盲读正文。

用法：
    python skill_match.py "帮我算一下问卷的 Cronbach alpha 和 KMO"
    python skill_match.py "查一下贵州茅台今天股价" --top 3
    python skill_match.py "把这份转写稿存进 ima" --json

依赖：仅标准库。无需任何第三方包、不联网、不调用模型。
"""

import argparse
import json
import os
import re
import sys

SKILLS_ROOT = os.environ.get(
    "WB_SKILLS_ROOT",
    os.path.join(os.path.expanduser("~"), ".workbuddy", "skills"),
)

# 命中分低于该值 → 建议别建 skill，直接写脚本
AD_HOC_THRESHOLD = 3.0

# 元问题标记：用户问的是"用哪个 / 要不要建"，此时 skill-router 应该胜出。
# 反之（具体任务需求）router 必须让路——否则它会靠名字里的 "skill" 字样抢跑。
META_MARKERS = (
    "该用哪个", "哪个skill", "哪个技能", "哪个 skill", "用哪个", "用哪个技能",
    "要不要建", "要不要新建", "要不要存", "存成 skill", "存成skill", "做成 skill",
    "搜索 skill", "搜索skill", "找 skill", "找skill", "找个 skill",
    "有没有现成", "有没有相关", "有没有技能", "用 skill 还是", "用skill还是",
    "该不该", "要不要用 skill", "要不要用skill", "路由", "该走哪个",
)
META_BOOST = 2.0     # 元问题：router 加权
META_DAMP = 0.45     # 具体任务：router 让路


def parse_frontmatter(path):
    """极简 YAML frontmatter 解析：只要 name / description / summary 三个字段。"""
    meta = {"name": "", "description": "", "summary": "", "agent_created": False}
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.read().split("\n")
    except OSError:
        return None

    if not lines or lines[0].strip() != "---":
        return meta
    key = None
    buf = []
    for line in lines[1:]:
        if line.strip() == "---":
            break
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$", line)
        if m:
            if key:
                meta[key] = " ".join(buf).strip()
            key, buf = m.group(1), [m.group(2).strip()]
        elif key:
            buf.append(line.strip())
    if key:
        meta[key] = " ".join(buf).strip()
    meta["agent_created"] = str(meta.get("agent_created", "")).lower() == "true"
    return meta


def tokenize(text):
    """中英文混合切分：中文取 2-gram，英文/数字取单词。全部小写。"""
    text = (text or "").lower()
    toks = set()
    for w in re.findall(r"[a-z0-9][a-z0-9_.\-]+", text):
        toks.add(w)
    for han in re.findall(r"[\u4e00-\u9fff]+", text):
        if len(han) == 1:
            toks.add(han)
        else:
            for i in range(len(han) - 1):
                toks.add(han[i:i + 2])
            toks.add(han)
    return toks


def score(query, hay, weight):
    """加权命中：长片段（如完整术语）比 2-gram 更有信息量，给更高分。"""
    if not hay:
        return 0.0
    hay_l = hay.lower()
    s = 0.0
    for t in query:
        if len(t) < 2:
            continue
        if t in hay_l:
            # 英文长词 / 中文长词组 权重更高
            s += weight * (1.6 if len(t) >= 4 else 1.0)
    return s


def collect():
    """扫描 ~/.workbuddy/skills 下全部 SKILL.md（跳过 .git 与备份目录）。"""
    out = []
    for root, dirs, files in os.walk(SKILLS_ROOT):
        dirs[:] = [d for d in dirs if d not in (".git", "_backup_20260902", "node_modules")]
        if "SKILL.md" not in files:
            continue
        p = os.path.join(root, "SKILL.md")
        meta = parse_frontmatter(p)
        if meta is None:
            continue
        rel = os.path.relpath(p, SKILLS_ROOT).replace("\\", "/")
        out.append({
            "path": rel,
            "name": meta.get("name") or os.path.basename(root),
            "dir": os.path.basename(root),
            "description": meta.get("description", ""),
            "summary": meta.get("summary", ""),
            "agent_created": meta.get("agent_created", False),
            "size": os.path.getsize(p),
        })
    return out


def main():
    ap = argparse.ArgumentParser(description="本地 skill 路由打分（零 LLM 成本）")
    ap.add_argument("query", help="用户原始需求描述")
    ap.add_argument("--top", type=int, default=3, help="返回前 N 个，默认 3")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    q = tokenize(args.query)
    if not q:
        print("无法从输入中提取有效关键词。")
        return 1

    raw = args.query.lower()
    is_meta = any(m in raw for m in META_MARKERS)

    results = []
    for s in collect():
        # description 是触发命根，权重最高；summary 次之；名字兜底
        sc = (
            score(q, s["description"], 1.0)
            + score(q, s["summary"], 0.8)
            + score(q, s["name"], 1.2)
            + score(q, s["dir"], 0.6)
        )
        # router 是元技能：只在元问题上加权，具体任务上降权让路
        if s["name"] == "skill-router":
            sc *= META_BOOST if is_meta else META_DAMP
        if sc > 0:
            results.append((sc, s))
    results.sort(key=lambda x: (-x[0], x[1]["size"]))

    if args.json:
        print(json.dumps(
            [{"score": round(sc, 2), **s} for sc, s in results[: args.top]],
            ensure_ascii=False, indent=2))
        return 0

    if not results:
        print("本地无任何 skill 命中。\n→ 建议：直接写一次性脚本，不要新建 skill。")
        return 0

    print(f"查询：{args.query}")
    if is_meta:
        print("（识别为元决策问题：用哪个 / 要不要建 skill）")
    print()
    for sc, s in results[: args.top]:
        tag = "自创" if s["agent_created"] else "预装"
        print(f"[{sc:6.2f}] {s['name']}  ({tag}, {s['size']}B)")
        print(f"         路径: {s['path']}")
        if s["summary"]:
            print(f"         摘要: {s['summary'][:110]}")
        print()

    best = results[0][0]
    print("─" * 60)
    if best < AD_HOC_THRESHOLD:
        print(f"最高分 {best:.2f} < 阈值 {AD_HOC_THRESHOLD} → 没有真正匹配的 skill。")
        print("行动：直接写一次性脚本解决，不要新建 skill，也不要硬套现有 skill。")
    else:
        print(f"命中：加载 {results[0][1]['path']}")
        print("行动：读取该 SKILL.md；正文里的 references/ 只在真正需要细节时再读。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
