#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
skill_match.py — 零 LLM 成本的 Skill 本地路由打分器（含同类 skill 权重仲裁）。

解决的问题：
  1. 不确定该用哪个 skill 时，用本地 CPU 打分代替"凭感觉读一个 16KB 的 SKILL.md"；
  2. 多个同类 skill 都能沾边时（如 5 个金融 skill），按**能力域专长**选出对的那个；
  3. 同等条件下让轻量 skill 优先，省 token。

打分公式：
    final = 关键词分 × 域专长乘子 × 自创加成 − 体积惩罚

  - 关键词分：description/summary/name/dir 的加权命中（中文 2-gram + 英文分词）
  - 域专长乘子：来自 weights.json，描述"每个 skill 在各能力域的擅长程度"
                （如行情域 market-query=1.8、news-search=0.2，直接拉开差距）
  - 自创加成：agent_created: true 的 skill ×1.15（更贴合用户习惯）
  - 体积惩罚：每 KB 扣 0.06 分，抑制动辄 17KB 的重型 skill

用法：
    python skill_match.py "查一下贵州茅台股价和资金流向"
    python skill_match.py "帮我算问卷的 Cronbach alpha 和 KMO" --top 3
    python skill_match.py "..." --json         # 机器可读
    python skill_match.py "..." --explain      # 展开分数构成

依赖：仅标准库。不联网、不调用模型、零 LLM 成本。
"""

import argparse
import io
import json
import os
import re
import sys

SKILLS_ROOT = os.environ.get(
    "WB_SKILLS_ROOT",
    os.path.join(os.path.expanduser("~"), ".workbuddy", "skills"),
)
WEIGHTS_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "weights.json")

_DEFAULT_CFG = {
    "domain_multiplier": 1.0,
    "selfmade_boost": 1.15,
    "cost_per_kb": 0.06,
    "ad_hoc_threshold": 3.0,
    "domain_hit_factor": 1.0,
    "close_call_ratio": 0.18,
    "meta_boost": 2.0,
    "meta_damp": 0.45,
}

# 元问题标记：用户问的是"用哪个 / 要不要建"，此时 skill-router 应该胜出。
# 反之（具体任务需求）router 必须让路——否则它会靠名字里的 "skill" 字样抢跑。
META_MARKERS = (
    "该用哪个", "哪个skill", "哪个技能", "哪个 skill", "用哪个", "用哪个技能",
    "要不要建", "要不要新建", "要不要存", "存成 skill", "存成skill", "做成 skill",
    "搜索 skill", "搜索skill", "找 skill", "找skill", "找个 skill",
    "有没有现成", "有没有相关", "有没有技能", "用 skill 还是", "用skill还是",
    "该不该", "要不要用 skill", "要不要用skill", "路由", "该走哪个",
)


def load_weights():
    """加载权重配置；缺失或损坏时降级为纯关键词模式，不中断路由。"""
    try:
        with io.open(WEIGHTS_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        d = dict(_DEFAULT_CFG)
        d.update(cfg.get("defaults", {}))
        return d, cfg.get("domains", {}), True
    except Exception:
        return dict(_DEFAULT_CFG), {}, False


def parse_frontmatter(path):
    """极简 YAML frontmatter 解析：只要 name / description / summary / agent_created。"""
    meta = {"name": "", "description": "", "summary": "", "agent_created": False}
    try:
        with io.open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.read().split("\n")
    except OSError:
        return None

    if not lines or lines[0].strip() != "---":
        return meta
    key, buf = None, []

    def flush():
        v = " ".join(buf).strip()
        # 去 YAML 引号（如 name: "ifind-finance-data"）
        if len(v) >= 2 and v[0] == v[-1] and v[0] in ("\"", "'"):
            v = v[1:-1]
        if key:
            meta[key] = v

    for line in lines[1:]:
        if line.strip() == "---":
            break
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$", line)
        if m:
            flush()
            key, buf = m.group(1), [m.group(2).strip()]
        elif key:
            buf.append(line.strip())
    flush()
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
    """加权命中：长片段（完整术语）比 2-gram 更有信息量，给更高分。"""
    if not hay:
        return 0.0
    hay_l = hay.lower()
    s = 0.0
    for t in query:
        if len(t) < 2:
            continue
        if t in hay_l:
            s += weight * (1.6 if len(t) >= 4 else 1.0)
    return s


def collect():
    """扫描 ~/.workbuddy/skills 下全部 SKILL.md（跳过 .git 与备份目录）。"""
    out = []
    for root, dirs, files in os.walk(SKILLS_ROOT):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules")
                   and not d.startswith("_backup")]
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


def detect_domains(raw, domains):
    """判定 query 命中的能力域及其强度（触发词命中数）。可多域并存。"""
    hits = {}
    for dname, d in domains.items():
        c = sum(1 for t in d.get("triggers", []) if t in raw)
        if c:
            hits[dname] = c
    return hits


def domain_multiplier(name, hits, domains):
    """多域加权平均：命中词多的域话语权更大。未在任何域列出的 skill 返回 1.0（不干预）。"""
    if not hits:
        return 1.0, {}
    total = sum(hits.values())
    acc, detail = 0.0, {}
    for dname, c in hits.items():
        w = domains.get(dname, {}).get("weights", {})
        if name in w:
            contrib = w[name] * c / total
            acc += contrib
            detail[dname] = w[name]
    if not detail:
        return 1.0, {}
    # 未提及的域按 1.0 补齐，避免"只列了强项域"时把分数整体压低
    missing = total
    for dname, c in hits.items():
        if dname in detail:
            missing -= c
    if missing > 0:
        acc += 1.0 * missing / total
    return acc, detail


def domain_score(name, hits, domains, factor):
    """域命中加分：只对在该域 weights 中显式列出的 skill 生效，避免不相关 skill 虚高。"""
    if not hits:
        return 0.0
    s = 0.0
    for dname, c in hits.items():
        w = domains.get(dname, {}).get("weights", {})
        if name in w:
            s += c * w[name] * factor
    return s


def main():
    ap = argparse.ArgumentParser(description="本地 skill 路由打分（含同类权重仲裁，零 LLM 成本）")
    ap.add_argument("query", help="用户原始需求描述")
    ap.add_argument("--top", type=int, default=3, help="返回前 N 个，默认 3")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--explain", action="store_true", help="展开分数构成")
    args = ap.parse_args()

    cfg, domains, weights_ok = load_weights()
    q = tokenize(args.query)
    if not q:
        print("无法从输入中提取有效关键词。")
        return 1

    raw = args.query.lower()
    is_meta = any(m in raw for m in META_MARKERS)
    hits = detect_domains(raw, domains)

    results = []
    for s in collect():
        kw = (
            score(q, s["description"], 1.0)
            + score(q, s["summary"], 0.8)
            + score(q, s["name"], 1.2)
            + score(q, s["dir"], 0.6)
        )
        dm, ddetail = domain_multiplier(s["name"], hits, domains)
        dsc = domain_score(s["name"], hits, domains, cfg["domain_hit_factor"])
        sm = cfg["selfmade_boost"] if s["agent_created"] else 1.0
        cost = s["size"] / 1024.0 * cfg["cost_per_kb"]
        final = max(0.0, (kw * dm + dsc) * sm - cost)
        # router 是元技能：只在元问题上加权，具体任务上降权让路
        if s["name"] == "skill-router":
            final *= cfg["meta_boost"] if is_meta else cfg["meta_damp"]
        if final > 0 or kw > 0:
            results.append({
                "final": final, "kw": kw, "dm": dm, "dsc": dsc,
                "sm": sm, "cost": cost,
                "ddetail": ddetail, **s,
            })
    results.sort(key=lambda x: (-x["final"], x["size"]))

    if args.json:
        print(json.dumps(
            [{k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()
              if k != "description"} for r in results[: args.top]],
            ensure_ascii=False, indent=2))
        return 0

    if not results or results[0]["final"] <= 0:
        print("本地无任何 skill 命中。\n→ 建议：直接写一次性脚本，不要新建 skill。")
        return 0

    thr = cfg["ad_hoc_threshold"]
    print(f"查询：{args.query}")
    if is_meta:
        print("（识别为元决策问题：用哪个 / 要不要建 skill）")
    if hits:
        top_domains = sorted(hits.items(), key=lambda x: -x[1])
        print("域判定：" + "、".join(f"{d}(命中{c})" for d, c in top_domains))
    if not weights_ok:
        print("（警告：weights.json 缺失，已降级为纯关键词模式）")
    print()

    shown = results[: args.top]
    for r in shown:
        tag = "自创" if r["agent_created"] else "预装"
        print(f"[{r['final']:6.2f}] {r['name']}  ({tag}, {r['size']/1024:.1f}KB)")
        print(f"         路径: {r['path']}")
        if args.explain:
            dm_txt = "、".join(f"{k}×{v}" for k, v in r["ddetail"].items()) or "无"
            print(f"         构成: (关键词 {r["kw"]:.2f} × 域专长 {r["dm"]:.2f} + 域加分 {r["dsc"]:.2f}) "
                  f"× {'自创' if r["agent_created"] else '预装'} {r["sm"]:.2f} − 体积 {r["cost"]:.2f} = {r["final"]:.2f}")
            print(f"         域权重: {dm_txt}")
        elif r["summary"]:
            print(f"         摘要: {r['summary'][:110]}")
        print()

    best, second = shown[0], (shown[1] if len(shown) > 1 else None)
    print("─" * 64)
    if best["final"] < thr:
        print(f"最高分 {best['final']:.2f} < 阈值 {thr} → 没有真正匹配的 skill。")
        print("行动：直接写一次性脚本解决，不要新建 skill，也不要硬套现有 skill。")
        return 0

    print(f"命中：加载 {best['path']}")
    if second and best["final"] > 0:
        gap = (best["final"] - second["final"]) / best["final"]
        if gap < cfg["close_call_ratio"]:
            print(f"注意：与 {second['name']} 分差仅 {gap*100:.0f}%（<{cfg['close_call_ratio']*100:.0f}%），两者接近。")
            if best["dm"] > second["dm"] + 0.2:
                print(f"      选 {best['name']}：在当前能力域更专（{best['dm']:.2f} vs {second['dm']:.2f}）。")
            elif best["size"] < second["size"] * 0.6:
                print(f"      选 {best['name']}：能力接近但轻得多（{best['size']//1024}KB vs {second['size']//1024}KB），省 token。")
    print("行动：读取该 SKILL.md；正文里的 references/ 只在真正需要细节时再读。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
