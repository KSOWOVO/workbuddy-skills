# -*- coding: utf-8 -*-
"""
CStream 主编排 —— 视频 → CUDA 转录 + 场景截图 → Obsidian 笔记

一条命令跑完：
    python pipeline.py <视频路径> --subject 雅思写作/大作文 --title "标题"

设计遵循 Kelsen 既有的 Obsidian 体系（见 SYNC.md）：
  - 笔记落进 vault 对应分类目录，与现有笔记同级
  - 截图放 <笔记名>_assets/ 子目录，用 Obsidian 双链 ![[...]] 引用
  - frontmatter 标注 type: raw / sync_ima: raw（沿用已有契约）
"""
import os
import re
import sys
import json
import time
import shutil
import argparse
import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from transcriber import load_model, transcribe, to_markdown  # noqa: E402
from shot_detector import detect_shots  # noqa: E402
from shot_filter import score_shots, apply_filter  # noqa: E402
from polisher import polish  # noqa: E402
from outliner import segment_topics  # noqa: E402

VAULT = r"C:\Users\13662\Documents\Obsidian"
RAWARK = r"C:\Users\13662\Documents\学习资料"

# 短名 -> vault 真实子路径。
# vault 顶层结构：00-收件箱 / 10-课程学习 / 20-竞赛科研 / 30-升学规划 /
#                40-个人生活 / 90-模板库
# 直接传「雅思写作/大作文」比传「30-升学规划/雅思写作/大作文」省事，
# 也避免把笔记落到 vault 根目录（旧流程踩过的坑）。
SUBJECT_MAP = {
    "雅思写作/大作文": "30-升学规划/雅思写作/大作文",
    "雅思写作/小作文": "30-升学规划/雅思写作/小作文",
    "雅思写作": "30-升学规划/雅思写作",
    "雅思": "30-升学规划/雅思",
    "英语语法": "30-升学规划/英语语法",
    "升学规划": "30-升学规划",
    "投资理财": "40-个人生活/投资理财",
    "个人生活": "40-个人生活",
    "课程学习": "10-课程学习",
    "竞赛科研": "20-竞赛科研",
    "收件箱": "00-收件箱",
    "模板库": "90-模板库",
}

# 关键词 -> 短名。用于没传 --subject 时自动判类。
# 判定只看标题/文件名，命中即用；多个命中时取最长关键词命中的那个。
KEYWORD_RULES = [
    (["大作文", "agree or disagree", "discuss both", "positive or negative",
      "outweigh", "why why", "雅思作文"], "雅思写作/大作文"),
    (["小作文", "line graph", "bar chart", "pie chart", "table",
      "流程图", "地图题", "柱状图", "饼图"], "雅思写作/小作文"),
    (["语法", "grammar", "从句", "时态", "语态", "英语兔"], "英语语法"),
    (["雅思", "ielts", "四六级", "四级", "六级", "背单词", "词汇"], "雅思"),
    (["理财", "投资", "基金", "股票", "定投", "退休", "财务自由", "存钱"], "投资理财"),
    (["营销", "市场调研", "论文", "实证", "sem", "spss", "问卷", "竞赛",
      "正大杯", "调研"], "竞赛科研"),
]


def resolve_subject(subject: str, title: str = "", video: str = "") -> str:
    """把短名/空值解析成 vault 真实相对路径。"""
    s = (subject or "").strip().strip("/\\")
    if s:
        return SUBJECT_MAP.get(s, s)

    hay = f"{title} {os.path.basename(video or '')}".lower()
    best, best_len = "", 0
    for kws, short in KEYWORD_RULES:
        for kw in kws:
            if kw.lower() in hay and len(kw) > best_len:
                best, best_len = short, len(kw)
    return SUBJECT_MAP.get(best, "00-收件箱") if best else "00-收件箱"


def _safe_name(s: str) -> str:
    """Windows 文件名安全化，保留中文。"""
    s = re.sub(r'[\\/:*?"<>|]', "_", s).strip()
    s = re.sub(r"\s+", " ", s)
    return s[:120] if len(s) > 120 else s


def _fmt_ts(sec: float) -> str:
    sec = max(0, int(sec))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def build_frontmatter(title: str, subject: str, src_name: str,
                      duration: float, n_shots: int, device: str) -> str:
    """
    生成 frontmatter。

    注意：Kelsen 现有 vault 笔记（雅思写作/语法/理财等 20+ 篇）
    **均无 frontmatter**，只有 H1 + 正文。故此函数默认不启用，
    仅当显式传 --frontmatter 时才输出，保证新笔记与既有风格一致。
    """
    today = datetime.date.today().isoformat()
    return "\n".join([
        "---",
        f"title: {title}",
        "type: raw",
        f"subject: {subject.split('/')[0] if subject else '未分类'}",
        "method: 无",
        "sync_ima: raw",
        f"source_video: {src_name}",
        f"duration: {_fmt_ts(duration)}",
        f"shots: {n_shots}",
        f"transcribe: faster-whisper large-v3 / {device}",
        f"created: {today}",
        "tags: [视频转录, 自动截图]",
        "---",
        "",
    ])


def run(video: str, subject: str, title: str | None = None,
        language: str = "zh", enable_shots: bool = False,
        sample_interval: float = 2.0, copy_raw: bool = True,
        model_size: str = "large-v3", start: float = 0.0,
        end: float | None = None, frontmatter: bool = False,
        enable_topics: bool = True, export_plain: bool = True,
        filter_shots: bool = True, prune_dropped: bool = True) -> dict:
    t_all = time.time()
    video = os.path.abspath(video)
    if not os.path.isfile(video):
        raise FileNotFoundError(video)

    src_name = os.path.basename(video)
    if not title:
        title = _safe_name(os.path.splitext(src_name)[0])
    title = _safe_name(title)

    # 短名/空值 -> vault 真实相对路径（空则按标题关键词自动判类）
    subject = resolve_subject(subject, title, video)
    out_dir = os.path.join(VAULT, subject)
    os.makedirs(out_dir, exist_ok=True)

    report = {"video": video, "title": title, "subject": subject,
              "out_dir": out_dir}

    # ---------- 1. 转录 ----------
    print("\n[1/4] 转录中（CUDA）...")
    model = load_model(model_size)
    device = getattr(model, "device", "cuda")

    def _tcb(p, n):
        print(f"\r  转录 {p * 100:5.1f}% | 已出 {n} 段", end="", flush=True)

    result = transcribe(video, model, language=language, progress_cb=_tcb)
    print()
    raw_n = len(result["segments"])
    result["segments"] = polish(result["segments"])
    report["duration"] = result["duration"]
    report["segments"] = len(result["segments"])
    report["segments_raw"] = raw_n
    report["transcribe_sec"] = result["elapsed"]
    print(f"  完成：时长 {_fmt_ts(result['duration'])}，"
          f"{raw_n} 段 → 整理后 {len(result['segments'])} 段，"
          f"耗时 {result['elapsed']}s")

    # ---------- 2. 截图 ----------
    shots: list[dict] = []
    if enable_shots:
        print("\n[2/4] 场景检测 + 截图...")
        assets_dir = os.path.join(out_dir, f"{title}_assets")

        def _scb(p, n):
            print(f"\r  截图 {p * 100:5.1f}% | 已捕捉 {n} 张", end="", flush=True)

        raw_shots = detect_shots(video, assets_dir, start=start, end=end,
                                 sample_interval=sample_interval,
                                 progress_cb=_scb)
        print()

        # ---- 落盘校验：防止「计数正常但磁盘为空」 ----
        # 历史事故：cv2.imwrite 在中文路径下静默失败，报告 400 张、
        # 磁盘 0 张，笔记里全是坏链接。这里强制核对真实文件数。
        on_disk = 0
        if os.path.isdir(assets_dir):
            on_disk = sum(1 for f in os.listdir(assets_dir)
                          if f.lower().endswith((".jpg", ".jpeg", ".png")))
        if on_disk != len(raw_shots):
            print(f"  [ERROR] 截图落盘不符：记录 {len(raw_shots)} 张 / "
                  f"磁盘 {on_disk} 张", file=sys.stderr)
            if on_disk == 0 and raw_shots:
                raise RuntimeError(
                    "截图全部写入失败（磁盘 0 张）。"
                    "常见原因：路径含中文且未走 imwrite_unicode，"
                    "或目标目录无写权限。")
            # 部分失败：只保留真实存在的，避免笔记里出现坏链接
            raw_shots = [s for s in raw_shots if os.path.isfile(s["file"])]
            print(f"  已剔除失效引用，保留 {len(raw_shots)} 张", file=sys.stderr)

        # 转成 Obsidian 可用的相对引用。
        # 坑：![[ ]] 里 Obsidian 把整串当作「文件名」解析，路径分隔符必须是
        # 反斜杠（vault 内的相对路径），写成 "dir/file.jpg" 会全部变成坏链
        # —— 实测 304/304 全部失效。这里统一转反斜杠。
        for s in raw_shots:
            rel = os.path.relpath(s["file"], out_dir).replace("/", "\\")
            shots.append({"ts": s["ts"], "file": s["file"], "rel": rel})

        # ---- 内链可用性校验：逐条确认 rel 能解析回真实文件 ----
        bad = [s for s in shots
               if not os.path.isfile(
                   os.path.normpath(os.path.join(out_dir, s["rel"])))]
        if bad:
            print(f"  [ERROR] {len(bad)} 条内链无法解析回真实文件，"
                  f"示例：{bad[0]['rel']}", file=sys.stderr)
            shots = [s for s in shots if s not in bad]

        report["shots"] = len(shots)
        report["assets_dir"] = assets_dir
        print(f"  完成：{len(shots)} 张 -> {assets_dir}（已核验落盘 + 内链可解析）")

        # ---- 2b. 语义筛（两阶段策略第二阶段）----
        # Kelsen 的要求：先全收，再筛。课程视频里大量帧是"过场动画 / 只剩
        # 一个 logo / 单张举例插图"，留着没用；真正有价值的是知识点页、
        # 思维导图、总结框架页。这里按像素信息量给每张打分分级。
        if filter_shots:
            print("\n[2b/4] 截图语义筛...")
            score_shots(shots)
            grades = {g: sum(1 for s in shots if s["grade"] == g)
                      for g in ("S", "A", "B", "C")}
            print(f"  S(重点) {grades['S']} | A(讲解) {grades['A']} | "
                  f"B(次要) {grades['B']} | C(过场) {grades['C']}")
            report["shot_grades"] = grades
    else:
        print("\n[2/4] 截图已关闭，跳过")

    # ---------- 3. 生成 Obsidian 笔记 ----------
    print("\n[3/4] 写入 Obsidian...")

    # 生成小标题（中度整理：帮回看时快速定位）
    topics = []
    if enable_topics:
        topics = segment_topics(result["segments"])
        report["topics"] = len(topics)
        print(f"  话题块 {len(topics)} 个")

    body = to_markdown(result, title, source=src_name, shots=shots,
                       topics=topics)

    if frontmatter:
        fm = build_frontmatter(title, subject, src_name, result["duration"],
                               len(shots), device)
        md = fm + body
    else:
        # 默认：与 Kelsen 既有笔记风格一致（H1 + 正文，无 frontmatter）
        md = body

    md_path = os.path.join(out_dir, f"{title}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)
    report["md"] = md_path
    print(f"  笔记：{md_path}")

    # 3a. 按语义分级裁剪：把 C 级（过场/logo/纯插图）的引用和文件一起清掉。
    # 放在笔记写完之后做，这样 S/A/B 的文件名保持原编号，时间轴不乱。
    if enable_shots and filter_shots and prune_dropped and shots:
        dropped = [s for s in shots if s["grade"] == "C"]
        if dropped:
            graded = [{"file": s["file"], "grade": s["grade"]} for s in shots]
            json.dump(graded, open(os.path.join(out_dir, "_shot_grades.json"),
                                   "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1)
            # 先改 md（去引用），再删文件
            stat = apply_filter(shots, md_path, assets_dir,
                                keep_grade=("S", "A", "B"))
            removed = 0
            for s in dropped:
                try:
                    os.remove(s["file"])
                    removed += 1
                except OSError:
                    pass
            report["shots_dropped"] = removed
            report["shots_final"] = len(shots) - removed
            print(f"  语义筛：移除 {removed} 张过场帧，"
                  f"保留 {len(shots) - removed} 张")

            # 内链复核：裁剪后必须仍然 0 坏链
            md2 = open(md_path, encoding="utf-8").read()
            left = re.findall(r"!\[\[([^\]]+)\]\]", md2)
            dead = [x for x in left
                    if not os.path.isfile(
                        os.path.normpath(os.path.join(out_dir, x)))]
            if dead:
                print(f"  [ERROR] 裁剪后出现 {len(dead)} 条坏链", file=sys.stderr)
            else:
                print(f"  内链复核：{len(left)} 条全部可解析")

    # 3b. 纯文本版（供 ima 回存，ima 不支持图片）
    if export_plain:
        plain = to_markdown(result, title, source=src_name, shots=[],
                            topics=topics)
        plain_dir = os.path.join(out_dir, "_plain")
        os.makedirs(plain_dir, exist_ok=True)
        plain_path = os.path.join(plain_dir, f"{title}.md")
        with open(plain_path, "w", encoding="utf-8") as f:
            f.write(plain)
        report["plain_md"] = plain_path
        print(f"  纯文本稿（供 ima）：{plain_path}")

    # ---------- 4. 原件备份 ----------
    if copy_raw:
        raw_dir = os.path.join(RAWARK, subject) if subject else os.path.join(RAWARK, "00-收件箱")
        os.makedirs(raw_dir, exist_ok=True)
        raw_dst = os.path.join(raw_dir, src_name)
        if os.path.abspath(raw_dst) != video:
            shutil.copy2(video, raw_dst)
        report["raw_backup"] = raw_dst
        print(f"  原件：{raw_dst}")
    else:
        print("[4/4] 原件备份已关闭")

    report["total_sec"] = round(time.time() - t_all, 1)
    print(f"\n全部完成，总耗时 {report['total_sec']}s")
    return report


def main():
    ap = argparse.ArgumentParser(
        description="视频 -> CUDA转录 -> Obsidian笔记 + ima纯文本稿（截图默认关，--shots 开启）")
    ap.add_argument("video", help="视频文件路径")
    ap.add_argument("--subject", "-s", default="", help="Obsidian 分类目录，如 雅思写作/大作文")
    ap.add_argument("--title", "-t", default=None, help="笔记标题（默认取文件名）")
    ap.add_argument("--lang", "-l", default="zh", help="语言，默认 zh")
    ap.add_argument("--shots", action="store_true",
                    help="开启场景截图（默认关闭，只出纯文字笔记）")
    ap.add_argument("--interval", type=float, default=2.0, help="采样间隔秒，默认 2.0")
    ap.add_argument("--no-raw", action="store_true", help="不备份原件")
    ap.add_argument("--model", default="large-v3", help="模型，默认 large-v3")
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--end", type=float, default=None)
    ap.add_argument("--json", default=None, help="把结果报告写入 json")
    ap.add_argument("--no-filter", action="store_true",
                    help="开启截图时：关闭语义筛（保留全部帧，含过场）")
    ap.add_argument("--no-prune", action="store_true",
                    help="开启截图时：语义筛只裁笔记引用，不删过场帧文件")
    a = ap.parse_args()

    rep = run(a.video, a.subject, a.title, a.lang, a.shots,
              a.interval, not a.no_raw, a.model, a.start, a.end,
              filter_shots=not a.no_filter,
              prune_dropped=not a.no_prune)

    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(rep, f, ensure_ascii=False, indent=2)
    print(json.dumps(rep, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
