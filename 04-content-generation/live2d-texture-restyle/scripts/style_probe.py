# -*- coding: utf-8 -*-
"""画风量化探针：测出明度/饱和度分布、线条颜色与占比、主色，用来判断两张画是否"同一画风"。

用法:
    python style_probe.py <图片>                      # 自动判定背景
    python style_probe.py <图片> --bg alpha           # 用 alpha 通道分离（贴图）
    python style_probe.py <图片> --bg white           # 背景是纯白（AI 出图常是）
    python style_probe.py <图片> --label original
    python style_probe.py <A> <B> --compare           # 直接对比两张，输出差值

输出：明度中位/高明度占比、饱和中位/低饱和占比、线条色与占比、主色 top-N。
经验值（柔光二次元风）：V中位≥75%、V>75%占比≥80%、S中位≤40%、S≤40%占比≥90%、
线条近黑且占比 2~3%、主色 top1 应与原稿一致。
"""
import sys, os, json, argparse
import colorsys
from collections import Counter, deque

try:
    from PIL import Image
except ImportError:
    sys.exit('需要 Pillow: pip install pillow')


def separable_background(px, W, H, tol=12):
    """四角取样 + BFS 洪水填充，标出连通的背景区域。返回 mask[y][x]=True 表示背景。"""
    corners = [px[0, 0], px[W - 1, 0], px[0, H - 1], px[W - 1, H - 1]]
    bg = corners[0]

    def is_bg(c):
        return all(abs(c[i] - bg[i]) < tol for i in range(3))

    mask = [[False] * W for _ in range(H)]
    dq = deque()
    for x in range(W):
        for y in (0, H - 1):
            if is_bg(px[x, y]) and not mask[y][x]:
                mask[y][x] = True; dq.append((x, y))
    for y in range(H):
        for x in (0, W - 1):
            if is_bg(px[x, y]) and not mask[y][x]:
                mask[y][x] = True; dq.append((x, y))
    while dq:
        x, y = dq.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < W and 0 <= ny < H and not mask[ny][nx] and is_bg(px[nx, ny]):
                mask[ny][nx] = True; dq.append((nx, ny))
    return mask


def median(a):
    s = sorted(a)
    return s[len(s) // 2] if s else 0.0


def probe(path, bg_mode='auto', max_colors=8, step=2):
    im = Image.open(path).convert('RGBA')
    W, H = im.size
    px = im.load()

    if bg_mode == 'alpha':
        fg = [(x, y) for y in range(0, H, step) for x in range(0, W, step) if px[x, y][3] > 200]
    elif bg_mode == 'white':
        fg = [(x, y) for y in range(0, H, step) for x in range(0, W, step)
              if not (px[x, y][0] > 245 and px[x, y][1] > 245 and px[x, y][2] > 245)]
    else:
        mask = separable_background(px, W, H)
        fg = [(x, y) for y in range(0, H, step) for x in range(0, W, step)
              if not mask[y][x] and px[x, y][3] > 60]

    if not fg:
        return {'file': path, 'error': '未找到前景像素，试试 --bg 参数'}

    vs, ss = [], []
    colors = Counter()
    dark = Counter()
    dark_n = 0
    for x, y in fg:
        r, g, b, a = px[x, y]
        h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        vs.append(v); ss.append(s)
        if s > 0.08:
            colors[(r // 16 * 16, g // 16 * 16, b // 16 * 16)] += 1
        if r + g + b < 300:                      # 暗像素 ≈ 线条
            dark[(r // 24 * 24, g // 24 * 24, b // 24 * 24)] += 1
            dark_n += 1

    n = len(fg)
    top = []
    for c, k in colors.most_common(max_colors):
        h, s, v = colorsys.rgb_to_hsv(c[0] / 255, c[1] / 255, c[2] / 255)
        top.append({'hex': '#%02X%02X%02X' % c, 'h': round(h * 360, 1),
                    's': round(s * 100, 1), 'v': round(v * 100, 1), 'px': k})

    line_top = []
    for c, k in dark.most_common(4):
        line_top.append({'hex': '#%02X%02X%02X' % c, 'px': k})

    return {
        'file': os.path.basename(path),
        'size': [W, H],
        'fg_px': n,
        'V_median': round(median(vs) * 100, 1),
        'V_high_ratio': round(sum(1 for v in vs if v > 0.75) / n * 100, 1),
        'S_median': round(median(ss) * 100, 1),
        'S_low_ratio': round(sum(1 for s in ss if s <= 0.40) / n * 100, 1),
        'line_color': line_top[0]['hex'] if line_top else None,
        'line_ratio': round(dark_n / n * 100, 2),
        'line_top': line_top,
        'top_colors': top,
    }


VERDICT = [
    ('V_median',      75, '>=', '明度中位'),
    ('V_high_ratio',  80, '>=', '高明度占比'),
    ('S_median',      40, '<=', '饱和中位'),
    ('S_low_ratio',   90, '>=', '低饱和占比'),
]

def show(res):
    if 'error' in res:
        print('!!', res['file'], res['error']); return
    print(f"\n=== {res['file']}  {res['size'][0]}x{res['size'][1]}  前景 {res['fg_px']}px ===")
    for key, thr, op, name in VERDICT:
        val = res[key]
        ok = val >= thr if op == '>=' else val <= thr
        print(f"  {name:12s} {val:6.1f}%   (目标 {op}{thr}%)  {'OK' if ok else '!! 偏离'}")
    print(f"  线条颜色     {res['line_color']}   占比 {res['line_ratio']}%   (目标 近黑、2~3%)")
    print(f"  主色 top{len(res['top_colors'])}:")
    for c in res['top_colors']:
        print(f"    {c['hex']}  H{c['h']:5.1f}° S{c['s']:5.1f}% V{c['v']:5.1f}%")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('images', nargs='+')
    ap.add_argument('--bg', default='auto', choices=['auto', 'alpha', 'white'])
    ap.add_argument('--label', default='')
    ap.add_argument('--compare', action='store_true')
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()

    results = [probe(p, a.bg) for p in a.images]
    for r in results:
        if a.label: r['label'] = a.label
        show(r)

    if a.compare and len(results) >= 2:
        A, B = results[0], results[1]
        print(f"\n--- 对比 {A['file']}  →  {B['file']} ---")
        for key, thr, op, name in VERDICT:
            d = B[key] - A[key]
            flag = 'OK' if abs(d) < 8 else ('!! 差异大' if abs(d) > 15 else '~ 略偏')
            print(f"  {name:12s} {A[key]:6.1f} → {B[key]:6.1f}   Δ{d:+6.1f}  {flag}")
        print(f"  线条色       {A['line_color']} → {B['line_color']}")
        print(f"  线条占比     {A['line_ratio']}% → {B['line_ratio']}%")
        ca = A['top_colors'][0]['hex'] if A['top_colors'] else '-'
        cb = B['top_colors'][0]['hex'] if B['top_colors'] else '-'
        print(f"  主色 top1    {ca} → {cb}   {'OK 一致' if ca == cb else '!! 不一致'}")

    if a.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
