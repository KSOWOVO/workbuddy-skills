# -*- coding: utf-8 -*-
"""
CStream 截图引擎 —— 场景变化检测（不是固定间隔）

为什么不用固定间隔：
  课程视频里一页 PPT 常常停留 2-5 分钟。若每 5 秒截一张，
  1 小时视频 ≈ 720 张，其中 95% 是同一页 PPT 的重复帧，毫无价值。

做法：
  1. 低频采样（默认每 2 秒一帧）—— 不漏场景切换，又不会太慢。
  2. 相邻帧做「降采样 + 灰度 + 差分」算变化率，超过阈值判定为场景切换。
  3. 对候选帧算感知哈希(pHash)，与最近保留的图比对，过滤翻页动画/鼠标抖动。
  4. 相邻保留帧时间过近（< min_gap 秒）只留信息量更大的一张。
  5. 丢弃纯色/空白帧（PPT 切换的中间过渡态）。

输出：{frame_ts, path, phash, change_score}
"""
import os
import sys
import json
import subprocess
from dataclasses import dataclass, asdict

import cv2
import numpy as np

# 采样与判定参数（按课程视频调优）
SAMPLE_INTERVAL = 2.0      # 采样间隔（秒）
DIFF_THRESHOLD = 0.012     # 场景变化阈值（归一化像素差），越小越敏感
PHASH_MIN_DIST = 6         # pHash 汉明距离小于此值视为同一画面
MIN_GAP = 3.0              # 相邻保留截图的最小时间间隔（秒）
BLANK_STD_THRESHOLD = 12.0 # 画面标准差低于此值视为纯色/空白

# 单视频截图上限。防跑飞，同时保证长视频能被完整覆盖。
# 80 分钟视频若按 400 张算 = 每 12 秒一张，偏密；
# 实际做法是「自适应配额」：按视频时长反推每张最少间隔，
# 让截图均匀铺满全片，而不是撞上限后突然断在中间。
MAX_SHOTS = 400
MIN_COVERAGE_GAP = 25.0    # 长视频里两张截图的理想最小间隔（秒）


def _adaptive_min_gap(duration: float, base_gap: float = MIN_GAP) -> float:
    """
    按视频时长反推「最小截图间隔」，避免长视频撞上限后覆盖中断。

    例：80 分钟 / 400 张 = 12 秒/张 —— 太密且不够覆盖。
    目标：让 MAX_SHOTS 张图均匀铺满全片，但不少于 base_gap。
    """
    if duration and duration > 0:
        ideal = duration / float(MAX_SHOTS)
        return max(base_gap, ideal)
    return base_gap


@dataclass
class Shot:
    ts: float
    file: str
    phash: str
    change: float


def imwrite_unicode(path: str, img: np.ndarray, quality: int = 92) -> bool:
    """
    写 JPEG —— 兼容中文路径。

    ⚠️ 为什么不能直接用 cv2.imwrite：
    OpenCV 在 Windows 上把路径按 ANSI(GBK) 处理，**含中文的路径会静默失败**：
    返回 False、不抛异常、文件不生成。实测：
        ASCII 路径 -> imwrite=True
        中文路径 -> imwrite=False  （路径长度仅 77~102，远未触及 260 上限）

    本 skill 的 vault 目录必然含中文（如 `30-升学规划\\英语语法\\`），
    所以**必须**走这个函数，否则截图会全部丢失而计数依然正常 —— 
    这是最阴的一类 bug：报告说成功了 400 张，磁盘上 0 张。

    做法：cv2.imencode 编码到内存 -> Python 原生 open() 写字节。
    """
    ext = os.path.splitext(path)[1] or ".jpg"
    ok, buf = cv2.imencode(ext, img, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        return False
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(buf.tobytes())
        return True
    except Exception as e:
        print(f"[warn] 写图失败 {path}: {e}", file=sys.stderr)
        return False


def _phash(gray: np.ndarray, hash_size: int = 8) -> str:
    """感知哈希：缩到 32x32 -> DCT -> 取左上 8x8 -> 与中位数比较。"""
    small = cv2.resize(gray, (32, 32), interpolation=cv2.INTER_AREA).astype(np.float32)
    dct = cv2.dct(small)
    low = dct[:hash_size, :hash_size]
    med = np.median(low[1:])  # 跳过 DC 分量
    bits = "".join("1" if v > med else "0" for v in low.flatten())
    return f"{int(bits, 2):0{hash_size * hash_size // 4}x}"


def _hamming(a: str, b: str) -> int:
    x = int(a, 16) ^ int(b, 16)
    return bin(x).count("1")


def _change_score(prev_gray: np.ndarray, cur_gray: np.ndarray) -> float:
    """归一化像素变化率，抗轻微压缩噪声。"""
    if prev_gray is None:
        return 1.0
    h, w = 180, 320
    a = cv2.resize(prev_gray, (w, h), interpolation=cv2.INTER_AREA)
    b = cv2.resize(cur_gray, (w, h), interpolation=cv2.INTER_AREA)
    # 用高斯模糊抑制编码噪声
    a = cv2.GaussianBlur(a, (5, 5), 0)
    b = cv2.GaussianBlur(b, (5, 5), 0)
    diff = cv2.absdiff(a, b)
    return float((diff > 16).sum()) / diff.size


def _crop_content(frame: np.ndarray) -> np.ndarray:
    """
    裁掉视频四周边框（播放器 UI / 黑边 / 进度条）。
    课程录屏常有上下黑边，裁掉能显著提升 pHash 稳定性。
    """
    h, w = frame.shape[:2]
    return frame[int(h * 0.03):int(h * 0.94), int(w * 0.02):int(w * 0.98)]


def detect_shots(video_path: str, out_dir: str, start: float = 0.0,
                 end: float | None = None, sample_interval: float = SAMPLE_INTERVAL,
                 diff_threshold: float = DIFF_THRESHOLD,
                 progress_cb=None) -> list[dict]:
    """对视频做场景变化检测并导出截图（JPEG）。"""
    os.makedirs(out_dir, exist_ok=True)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"无法打开视频：{video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    vid_dur = total / fps if fps else 0.0
    if end is None:
        end = vid_dur

    step = max(1, int(round(fps * sample_interval)))

    # 自适应最小间隔：长视频自动放宽，保证截图铺满全片而非撞上限中断
    span = max(0.0, (end or vid_dur) - start)
    eff_min_gap = _adaptive_min_gap(span)
    if eff_min_gap > MIN_GAP + 0.01:
        print(f"[info] 视频 {span / 60:.1f} 分钟，截图最小间隔自适应为 "
              f"{eff_min_gap:.1f}s（默认 {MIN_GAP}s）")

    shots: list[Shot] = []
    prev_gray = None
    prev_kept_ts = -1e9
    last_phash = None
    last_std = None
    failed = 0

    idx = int(start * fps)
    cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
    frame_i = idx
    scanned = 0

    while True:
        ok = cap.grab()
        if not ok:
            break
        ts = frame_i / fps
        if ts > end:
            break

        if (frame_i - idx) % step == 0:
            ok2, frame = cap.retrieve()
            if ok2 and frame is not None:
                scanned += 1
                cropped = _crop_content(frame)
                gray = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)
                std = float(gray.std())

                score = _change_score(prev_gray, gray)
                prev_gray = gray

                is_blank = std < BLANK_STD_THRESHOLD
                changed = score >= diff_threshold
                # 从纯色恢复也算一次切换（常见：PPT 切换的过渡白屏->内容）
                recovered = (last_std is not None and last_std < BLANK_STD_THRESHOLD
                             and std >= BLANK_STD_THRESHOLD)

                if (changed or recovered) and not is_blank:
                    ph = _phash(gray)
                    dup = last_phash is not None and _hamming(ph, last_phash) < PHASH_MIN_DIST
                    too_close = (ts - prev_kept_ts) < eff_min_gap

                    if not dup and not too_close:
                        fname = f"shot_{len(shots) + 1:04d}.jpg"
                        fpath = os.path.join(out_dir, fname)
                        # 用原始尺寸截图，质量 92
                        # 必须走 imwrite_unicode：cv2.imwrite 在中文路径下静默失败
                        if not imwrite_unicode(fpath, frame, quality=92):
                            failed += 1
                            if failed <= 3:
                                print(f"[warn] 截图写入失败：{fpath}", file=sys.stderr)
                            frame_i += 1
                            continue
                        shots.append(Shot(round(ts, 2), fpath, ph, round(score, 4)))
                        prev_kept_ts = ts
                        last_phash = ph
                        if len(shots) >= MAX_SHOTS:
                            print(f"[warn] 达到截图上限 {MAX_SHOTS}，提前结束")
                            break

                last_std = std

                if progress_cb and vid_dur:
                    progress_cb(min(ts / vid_dur, 1.0), len(shots))

        frame_i += 1

    cap.release()
    if progress_cb:
        progress_cb(1.0, len(shots))
    return [asdict(s) for s in shots]


def extract_frame_at(video_path: str, ts: float, out_path: str,
                     quality: int = 92) -> bool:
    """在指定时间点取一帧（用于补关键帧）。"""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return False
    cap.set(cv2.CAP_PROP_POS_MSEC, ts * 1000.0)
    ok, frame = cap.read()
    cap.release()
    if not ok or frame is None:
        return False
    return imwrite_unicode(out_path, frame, quality=quality)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法: python shot_detector.py <视频> <输出目录> [起始秒] [结束秒]")
        sys.exit(1)
    v = sys.argv[1]
    o = sys.argv[2]
    s = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
    e = float(sys.argv[4]) if len(sys.argv) > 4 else None

    def _cb(p, n):
        print(f"\r  进度 {p * 100:5.1f}% | 已截图 {n}", end="", flush=True)

    r = detect_shots(v, o, s, e, progress_cb=_cb)
    print()
    print(f"共 {len(r)} 张截图 -> {o}")
