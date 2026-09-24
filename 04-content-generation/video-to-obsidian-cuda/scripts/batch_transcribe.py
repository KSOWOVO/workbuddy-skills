# -*- coding: utf-8 -*-
"""
batch_transcribe.py —— 批量转录（模型只加载一次）

为什么不用 for 循环调 pipeline.py：
  pipeline.run() 每次都 load_model()，large-v3 加载约 14s。
  18 个文件就白花 4 分钟。本脚本全程只加载一次。

特性：
  - 幂等/可续跑：输出 md 已存在且非空就跳过
  - 逐个打印进度到日志，便于后台监控
  - 截图默认关（--shots 可开）

用法：
  python batch_transcribe.py <目录或文件...> --subject 英语语法 \
      --tag-file _batch_state.json
"""
import argparse
import datetime
import glob
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from transcriber import load_model, transcribe, to_markdown  # noqa: E402
from polisher import polish  # noqa: E402
from outliner import segment_topics  # noqa: E402
import pipeline as PL  # noqa: E402


def safe_name(s: str) -> str:
    s = re.sub(r'[\\/:*?"<>|]', "_", s).strip()
    s = re.sub(r"\s+", " ", s)
    return s[:120]


def fmt(sec):
    sec = max(0, int(sec))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return "%d:%02d:%02d" % (h, m, s)


def collect(args, exclude=None):
    out = []
    for a in args:
        if os.path.isdir(a):
            for ext in ("mp4", "mkv", "mov", "m4a", "mp3", "wav", "flac"):
                out += glob.glob(os.path.join(a, "*." + ext))
        elif os.path.isfile(a):
            out.append(a)
    # 去重 + 稳定排序
    out = sorted(set(os.path.abspath(p) for p in out))
    if exclude:
        pats = exclude if isinstance(exclude, (list, tuple)) else [exclude]
        out = [p for p in out
               if not any(re.search(x, os.path.basename(p)) for x in pats)]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+", help="目录或文件（可多个）")
    ap.add_argument("--subject", "-s", default="英语语法",
                    help="vault 分类短名（会过 SUBJECT_MAP 展开）")
    ap.add_argument("--subdir", default="_staging",
                    help="分类下的子目录；传空字符串则直接落在分类目录")
    ap.add_argument("--order", default=None,
                    help="指定处理顺序的 json（_vid_recon.json）")
    ap.add_argument("--state", default=None, help="状态文件，用于续跑与进度")
    ap.add_argument("--shots", action="store_true")
    ap.add_argument("--lang", "-l", default="zh")
    ap.add_argument("--exclude", action="append", default=None,
                    help="正则，命中文件名的跳过（可多次）")
    ap.add_argument("--out-dir", default=None,
                    help="直接指定输出根目录（优先于 --subject/--subdir）。"
                         "供小A等外部流程先产出到交付区，验收后再归位 vault")
    a = ap.parse_args()

    files = collect(a.inputs, a.exclude)
    if a.order and os.path.isfile(a.order):
        rank = {os.path.abspath(r["file"]): r["i"]
                for r in json.load(open(a.order, encoding="utf-8"))}
        files.sort(key=lambda p: rank.get(p, 999))
    if not files:
        print("没有找到可处理的文件")
        return 1

    if a.out_dir:
        # 外部流程（小A）交付区模式：产出先落指定目录，宿主验收后归位 vault
        out_dir = os.path.abspath(a.out_dir)
    else:
        # ⚠️ subject 必须传 vault 认识的短名（如「英语语法」），
        # 否则 resolve_subject 会原样返回，导致目录落到 vault 根下（踩过）。
        base_subject = PL.resolve_subject(a.subject, "", "")
        subject = (os.path.join(base_subject, a.subdir)
                   if a.subdir else base_subject)
        out_dir = os.path.join(PL.VAULT, subject)
    plain_dir = os.path.join(out_dir, "_plain")
    os.makedirs(plain_dir, exist_ok=True)

    state = {"start": datetime.datetime.now().isoformat(), "done": [],
             "skipped": [], "failed": []}
    if a.state and os.path.isfile(a.state):
        try:
            state = json.load(open(a.state, encoding="utf-8"))
            state.setdefault("done", [])
        except Exception:
            pass

    print("=== 批量转录 ===")
    print("  待处理 %d 个文件" % len(files))
    print("  输出目录 %s" % out_dir)
    print("  截图 %s" % ("开" if a.shots else "关"))
    sys.stdout.flush()

    t_load = time.time()
    model = load_model(os.environ.get("WB_MODEL", "large-v3"))
    dev = getattr(model, "device", "?")
    print("  模型加载 %.1fs | device=%s" % (time.time() - t_load, dev))
    sys.stdout.flush()

    total_dur = 0.0
    t0 = time.time()
    for idx, v in enumerate(files, 1):
        base = os.path.splitext(os.path.basename(v))[0]
        title = safe_name(base)
        md_path = os.path.join(out_dir, title + ".md")
        if os.path.isfile(md_path) and os.path.getsize(md_path) > 2000:
            print("\n[%d/%d] 跳过（已存在）：%s" % (idx, len(files), title))
            state["skipped"].append(title)
            continue

        print("\n[%d/%d] %s" % (idx, len(files), title))
        print("        文件 %.1f MB" % (os.path.getsize(v) / 1024 / 1024))
        sys.stdout.flush()
        ts = time.time()
        try:
            result = transcribe(v, model, language=a.lang)
            raw_n = len(result["segments"])
            result["segments"] = polish(result["segments"])
            topics = segment_topics(result["segments"])
            body = to_markdown(result, title, source=os.path.basename(v),
                               shots=[], topics=topics)
            open(md_path, "w", encoding="utf-8").write(body)
            open(os.path.join(plain_dir, title + ".md"), "w",
                 encoding="utf-8").write(body)
            el = time.time() - ts
            total_dur += result["duration"]
            print("        ✅ %s | %d 段 → %d 段 | %d 小标题 | %.0fs"
                  % (fmt(result["duration"]), raw_n,
                     len(result["segments"]), len(topics), el))
            state["done"].append({
                "title": title, "file": v, "dur": result["duration"],
                "sec": round(el, 1), "md": md_path})
        except Exception as e:
            print("        ❌ 失败: %s: %s" % (type(e).__name__, e))
            state["failed"].append({"title": title, "file": v,
                                    "err": "%s: %s" % (type(e).__name__, e)})
        if a.state:
            json.dump(state, open(a.state, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1)
        sys.stdout.flush()

    el = time.time() - t0
    print("\n" + "=" * 56)
    print("完成 %d / 跳过 %d / 失败 %d"
          % (len(state["done"]), len(state["skipped"]), len(state["failed"])))
    print("音频总时长 %s | 总耗时 %.0fs (%.1fx 实时)"
          % (fmt(total_dur), el, total_dur / el if el else 0))
    if state["failed"]:
        for f in state["failed"]:
            print("  ❌ %s: %s" % (f["title"], f["err"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
