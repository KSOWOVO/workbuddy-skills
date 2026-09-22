# -*- coding: utf-8 -*-
"""
CStream 转录引擎 —— faster-whisper + CUDA (CTranslate2)

设计要点：
  1. 用 CTranslate2 后端驱动 CUDA，不依赖 torch / 系统 CUDA Toolkit。
  2. 8G 显存下 large-v3 用 float16，显存约 4.5G，留足余量。
  3. VAD 过滤静音，避免 Whisper 在无语音段落产生幻觉。
  4. 输出带时间戳的分段，供截图引擎做时间对齐。
"""
import os
import sys
import json
import time
from dataclasses import dataclass, asdict

MODEL_DIR = r"C:\Users\13662\.workbuddy\models\whisper"


def _register_cuda_dlls() -> None:
    """
    把 pip 装的 NVIDIA 运行时库（cuBLAS / cuDNN）加进 DLL 搜索路径。

    背景：CTranslate2 自带 CUDA kernel，但动态链接 cublas64_12.dll /
    cudnn64_9.dll。若系统没装 CUDA Toolkit，这两个 DLL 就找不到，
    推理时报 `Library cublas64_12.dll is not found or cannot be loaded`。

    解法：nvidia-cublas-cu12 / nvidia-cudnn-cu12 两个 PyPI 包自带 DLL，
    在 import ctranslate2 之前把它们的 bin 目录注册进搜索路径即可。
    这是唯一让「不装 CUDA Toolkit」成立的补丁。
    """
    if os.name != "nt":
        return
    try:
        import site
        roots = []
        for sp in site.getsitepackages():
            roots.append(os.path.join(sp, "nvidia"))
        usp = site.getusersitepackages()
        if usp:
            roots.append(os.path.join(usp, "nvidia"))

        added = []
        for root in roots:
            if not os.path.isdir(root):
                continue
            for pkg in ("cublas", "cudnn", "cuda_nvrtc"):
                for sub in ("bin", "lib"):
                    d = os.path.join(root, pkg, sub)
                    if os.path.isdir(d):
                        try:
                            os.add_dll_directory(d)
                        except Exception:
                            pass
                        os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
                        added.append(d)
        if added:
            print(f"[info] 已注册 {len(added)} 个 NVIDIA 运行时目录", file=sys.stderr)
        else:
            print("[info] 未找到 nvidia-*-cu12 运行时目录（若用 CPU 可忽略）",
                  file=sys.stderr)
    except Exception as e:
        print(f"[warn] 注册 CUDA DLL 目录失败：{e}", file=sys.stderr)


_register_cuda_dlls()


@dataclass
class Segment:
    start: float
    end: float
    text: str


def _fmt_ts(sec: float) -> str:
    """秒 -> HH:MM:SS"""
    sec = max(0, int(sec))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def pick_device() -> tuple[str, str]:
    """探测可用设备，返回 (device, compute_type)。"""
    try:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() > 0:
            types = ctranslate2.get_supported_compute_types("cuda")
            ct = "float16" if "float16" in types else "int8_float16"
            return "cuda", ct
    except Exception as e:
        print(f"[warn] CUDA 探测失败，回退 CPU：{e}", file=sys.stderr)
    return "cpu", "int8"


def load_model(model_size: str = "large-v3", device: str | None = None,
               compute_type: str | None = None):
    """加载模型。优先用本地已下载目录，否则交给 faster-whisper 自动拉取。"""
    from faster_whisper import WhisperModel

    if device is None or compute_type is None:
        device, compute_type = pick_device()

    local = os.path.join(MODEL_DIR, model_size)
    src = local if os.path.isdir(local) else model_size

    print(f"[info] 加载模型 {src} | device={device} | compute={compute_type}")
    model = WhisperModel(src, device=device, compute_type=compute_type,
                         num_workers=1, cpu_threads=4)
    return model


def transcribe(audio_path: str, model, language: str = "zh",
               vad: bool = True, beam_size: int = 5,
               progress_cb=None) -> dict:
    """
    转录音频/视频。返回 {segments, language, duration, device, elapsed}
    audio_path 可以是视频文件，faster-whisper 内部用 PyAV 解码。
    """
    t0 = time.time()
    segments_iter, info = model.transcribe(
        audio_path,
        language=language,
        beam_size=beam_size,
        vad_filter=vad,
        vad_parameters=dict(min_silence_duration_ms=500),
        condition_on_previous_text=False,   # 关闭可显著减少长音频的复读/幻觉
        word_timestamps=False,
    )

    segs: list[Segment] = []
    duration = getattr(info, "duration", 0.0) or 0.0
    for s in segments_iter:
        txt = (s.text or "").strip()
        if not txt:
            continue
        segs.append(Segment(round(s.start, 2), round(s.end, 2), txt))
        if progress_cb and duration:
            progress_cb(min(s.end / duration, 1.0), len(segs))

    elapsed = time.time() - t0
    return {
        "segments": [asdict(s) for s in segs],
        "language": getattr(info, "language", language),
        "duration": round(duration, 2),
        "elapsed": round(elapsed, 2),
    }


def to_markdown(result: dict, title: str, source: str = "",
                shots: list[dict] | None = None,
                ts_style: str = "bold",
                topics: list[dict] | None = None) -> str:
    """
    生成 Obsidian markdown。

    对齐 Kelsen 现有笔记风格：H1 标题 + 正文段落。
    区别仅在于：段落前加时间戳，段落间按时间插入截图双链。

    ts_style:
      "bold"  -> **03:12**（默认，比旧稿的「发言人 00:00」更省版面）
      "legacy"-> 发言人   03:12（完全复刻旧稿写法）
      "none"  -> 不带时间戳

    shots:  [{ts, file, rel}] 按 ts 插入到对应段落之后。
    topics: [{ts, title, start_idx}] 话题块小标题，插在对应段落之前。
    """
    shots = shots or []
    topics = topics or []
    segs = result["segments"]

    # ---- 先把截图分配到段落 ----
    # 三级判据（按优先级）：
    #   ① 区间覆盖：某段的 [start, end] 覆盖了截图时刻 —— 最准，直接用。
    #   ② 最近邻  ：没有覆盖段时，取 start 与截图时刻最近的段。
    #   ③ 单调约束：后一张图的归属段不得早于前一张，保证图文顺序不乱。
    # 旧版只做「start >= ts 的第一段」，末尾几张图找不到归属就全堆在文末，
    # 实测 6 张 PPT 有 3 张被挤到最后 —— 这是本函数存在的意义。
    assign: dict[int, list[dict]] = {}
    n = len(segs)
    prev = 0
    for sh in sorted(shots, key=lambda x: x["ts"]):
        ts = float(sh["ts"])

        # ① 区间覆盖
        target = None
        for i in range(prev, n):
            s = segs[i]
            if s["start"] <= ts <= s["end"] + 0.5:
                target = i
                break

        # ② 最近邻（只在 prev..n-1 范围内找，天然满足单调约束）
        if target is None and n:
            best_i, best_d = prev, None
            for i in range(prev, n):
                d = abs(segs[i]["start"] - ts)
                if best_d is None or d < best_d:
                    best_i, best_d = i, d
            target = best_i

        if target is None:
            target = max(0, n - 1)

        # ③ 单调约束
        target = max(target, prev)
        prev = target
        assign.setdefault(target, []).append(sh)

    lines: list[str] = [f"# {title}", ""]
    if source:
        lines += [f"{source}", ""]

    # 话题块小标题按 start_idx 索引，方便插入
    topic_at: dict[int, str] = {}
    for t in topics:
        if t.get("title"):
            topic_at.setdefault(int(t["start_idx"]), t["title"])

    n_embed = 0
    for i, seg in enumerate(segs):
        # 话题小标题：插在该块第一段之前，占一行 H2
        if i in topic_at:
            lines.append(f"## ▎{topic_at[i]}")
            lines.append("")

        if ts_style == "legacy":
            lines.append(f"发言人   {_fmt_ts(seg['start'])}")
        elif ts_style == "bold":
            lines.append(f"**{_fmt_ts(seg['start'])}**")
        lines.append("")
        lines.append(seg["text"])
        lines.append("")

        for sh in assign.get(i, []):
            embed = sh.get("rel") or sh["file"]
            lines.append(f"![[{embed}]]")
            lines.append("")
            n_embed += 1

    return "\n".join(lines).rstrip() + "\n"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python transcriber.py <音视频路径> [输出json]")
        sys.exit(1)

    src = sys.argv[1]
    m = load_model()
    res = transcribe(src, m)
    print(f"时长 {res['duration']}s | 分段 {len(res['segments'])} | 耗时 {res['elapsed']}s")

    out = sys.argv[2] if len(sys.argv) > 2 else None
    if out:
        with open(out, "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=2)
        print("已写入:", out)
