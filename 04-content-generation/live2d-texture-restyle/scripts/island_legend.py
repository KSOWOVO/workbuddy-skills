# -*- coding: utf-8 -*-
"""从着色诊断的渲染截图里反查：每个 UV 岛出现在身体哪个位置。

用法:
    python island_diagnostic.py <texture.png> <uvdir>        # 先生成 debug_texture
    # 用 debug_texture.png 替换模型贴图，渲染/截图
    python island_legend.py <渲染截图.png> <uvdir>            # 反查对照表

产出: <uvdir>/island_part_map.txt
"""
import os, sys, json
from collections import defaultdict
from PIL import Image


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    shot_path, uvdir = sys.argv[1], sys.argv[2]

    islands = json.load(open(os.path.join(uvdir, 'islands_colored.json'), encoding='utf-8'))
    im = Image.open(shot_path).convert('RGB')
    W, H = im.size
    px = im.load()

    pal = [tuple(d['color']) for d in islands]

    def nearest(c):
        best, bd = None, 10**9
        for cc in pal:
            d = sum((a-b)**2 for a, b in zip(c, cc))
            if d < bd:
                bd, best = d, cc
        return best if bd <= 42*42*3 else None

    # 渲染图里出现的纯色 -> 位置
    pos = defaultdict(list)
    for y in range(0, H, 2):
        for x in range(0, W, 2):
            c = px[x, y]
            mx, mn = max(c), min(c)
            if mx > 90 and (mx - mn) > 55:
                n = nearest(c)
                if n:
                    pos[n].append((x, y))

    rows = []
    for d in islands:
        c = tuple(d['color'])
        pts = pos.get(c)
        if not pts:
            rows.append((d['id'], d['box'], None, 0)); continue
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        rows.append((d['id'], d['box'], (sum(xs)/len(xs), sum(ys)/len(ys)), len(pts)))

    vis = [r for r in rows if r[2]]
    if not vis:
        sys.exit('截图里没找到任何调色板颜色 —— 检查是否真的用了 debug_texture.png，'
                 '或截图被缩放/压缩改变了颜色。')
    allx = [r[2][0] for r in vis]; ally = [r[2][1] for r in vis]
    vx0, vx1 = min(allx), max(allx); vy0, vy1 = min(ally), max(ally)

    def part_of(cx, cy, box):
        nx = (cx-vx0)/max(1e-6, vx1-vx0); ny = (cy-vy0)/max(1e-6, vy1-vy0)
        horiz = '左' if nx < 0.42 else ('右' if nx > 0.58 else '中')
        vert = ('头部上' if ny < 0.18 else '头部' if ny < 0.30 else '颈肩' if ny < 0.42
                else '躯干' if ny < 0.62 else '胯/裙' if ny < 0.74 else '腿' if ny < 0.90 else '脚')
        return f'{vert}{horiz}  ({nx*100:.0f}%,{ny*100:.0f}%)  岛{box[2]-box[0]}x{box[3]-box[1]}'

    lines = [f'渲染图 {W}x{H}，可见范围 x{vx0:.0f}-{vx1:.0f} y{vy0:.0f}-{vy1:.0f}',
             '（部位名是启发式推断，仅供参考；请对着截图目视确认，'
             '尤其注意尾巴/飘发等伸出去的元素会把可见范围拉大、导致比例失真）', '']
    for iid, box, cent, npix in sorted(rows, key=lambda r: -r[3]):
        if cent is None:
            lines.append(f'#{iid:2d}  -> 未出现在渲染中（被遮挡 / 透明 / 面积太小）')
        else:
            lines.append(f'#{iid:2d}  -> {part_of(cent[0], cent[1], box)}')

    txt = '\n'.join(lines)
    print(txt)
    with open(os.path.join(uvdir, 'island_part_map.txt'), 'w', encoding='utf-8') as f:
        f.write(txt)
    print(f'\n-> {uvdir}/island_part_map.txt')


if __name__ == '__main__':
    main()
