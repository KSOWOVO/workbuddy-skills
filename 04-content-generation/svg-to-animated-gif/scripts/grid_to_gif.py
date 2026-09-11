"""grid_to_gif.py — 把「N 帧网格 HTML」一次截图 → 切帧 → 合成无缝循环 GIF。

用法：
  1. 改下面 CONFIG。
  2. 实现 frame(t) -> str，返回该帧的 SVG **内容**（不含 <svg> 外壳），t = i/N。
  3. python grid_to_gif.py

为什么这么写：无头浏览器启动一次约 1.5s。24 帧分别截图要 36s 且易失败；
把 24 帧拼成一张网格只截一次，约 3s。
"""
import math
import os
import subprocess
import sys

from PIL import Image

# ------------------------------- CONFIG -------------------------------
BASE = os.path.dirname(os.path.abspath(__file__))
EDGE_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
]
W, H = 680, 460           # 单帧逻辑尺寸（viewBox）
N = 24                    # 帧数
COLS, ROWS = 6, 4         # 网格布局，须满足 COLS*ROWS >= N
SCALE = 2                 # 超采样倍率，最后 LANCZOS 降采样
BG = "#FDFDFB"            # GIF 必须有背景色（SVG 透明背景要补 rect）
DURATION_MS = 50          # 每帧毫秒
COLORS = 192              # 调色板颜色数
OUT_GIF = os.path.join(BASE, "out.gif")
# ---------------------------------------------------------------------

CELL_W, CELL_H = W * SCALE, H * SCALE


def frame(t: float) -> str:
    """返回第 t 帧（t = i/N）的 SVG 内容。子类化/改写这个函数即可。"""
    raise NotImplementedError


def build_page(page_path: str) -> str:
    """把所有帧拼成一个绝对定位的网格页面。"""
    cells = []
    for i in range(N):
        col, row = i % COLS, i // COLS
        cells.append(
            f'<svg style="left:{col * CELL_W}px;top:{row * CELL_H}px" '
            f'width="{CELL_W}" height="{CELL_H}" viewBox="0 0 {W} {H}" '
            f'xmlns="http://www.w3.org/2000/svg">{frame(i / N)}</svg>'
        )
    html = (
        '<!DOCTYPE html><html><head><meta charset="utf-8"><style>'
        'html,body{margin:0;padding:0;overflow:hidden;background:' + BG + '}'
        'svg{position:absolute;display:block}</style></head><body>'
        + ''.join(cells) + '</body></html>'
    )
    with open(page_path, "w", encoding="utf-8") as f:
        f.write(html)
    return page_path


def find_browser() -> str:
    for p in EDGE_CANDIDATES:
        if os.path.exists(p):
            return p
    sys.exit("no chromium-based browser found")


def render(page_path: str, shot_path: str) -> None:
    if os.path.exists(shot_path):
        os.remove(shot_path)
    subprocess.run(
        [find_browser(), "--headless", "--disable-gpu", "--no-sandbox",
         "--hide-scrollbars", "--force-device-scale-factor=1",
         f"--screenshot={shot_path}",
         f"--window-size={COLS * CELL_W},{ROWS * CELL_H}",
         "file:///" + page_path.replace("\\", "/")],
        capture_output=True,
    )
    if not os.path.exists(shot_path):
        sys.exit("screenshot failed")


def slice_frames(shot_path: str, frames_dir: str) -> list:
    sheet = Image.open(shot_path).convert("RGB")
    if sheet.size != (COLS * CELL_W, ROWS * CELL_H):
        sys.exit(f"sheet size {sheet.size} != expected — check "
                 f"--force-device-scale-factor")
    os.makedirs(frames_dir, exist_ok=True)
    frames = []
    for i in range(N):
        col, row = i % COLS, i // COLS
        c = sheet.crop((col * CELL_W, row * CELL_H,
                        (col + 1) * CELL_W, (row + 1) * CELL_H))
        c = c.resize((W, H), Image.LANCZOS)
        c.save(os.path.join(frames_dir, f"f{i:02d}.png"))
        frames.append(c)
    return frames


def save_gif(frames: list, out_path: str) -> None:
    # 共享调色板：逐帧各自量化会导致帧间闪烁
    montage = Image.new("RGB", (W, H * len(frames)))
    for i, f in enumerate(frames):
        montage.paste(f, (0, i * H))
    pal = montage.quantize(colors=COLORS, method=Image.MEDIANCUT)
    pf = [f.quantize(palette=pal, dither=0) for f in frames]
    pf[0].save(out_path, save_all=True, append_images=pf[1:],
               duration=DURATION_MS, loop=0, optimize=True, disposal=2)


def main():
    page = build_page(os.path.join(BASE, "grid.html"))
    shot = os.path.join(BASE, "grid.png")
    render(page, shot)
    frames = slice_frames(shot, os.path.join(BASE, "frames"))
    save_gif(frames, OUT_GIF)
    print(f"{OUT_GIF}  {os.path.getsize(OUT_GIF) // 1024} KB  "
          f"{N} frames  {W}x{H}")


if __name__ == "__main__":
    main()
