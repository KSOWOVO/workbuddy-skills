# -*- coding: utf-8 -*-
"""着色诊断：给贴图里每个 UV 岛填不同纯色，渲染一次即可反查「岛 ↔ 身体部位」。

用法:
    python island_diagnostic.py <texture_00.png> <outdir>

产出:
    <outdir>/debug_texture.png      每个岛一个纯色的贴图（拿去替换模型贴图渲染）
    <outdir>/legend.png             色块 ↔ 岛号/坐标 图例
    <outdir>/islands_colored.json   机器可读的岛清单

配套：island_legend.py —— 从渲染截图里反查每个岛出现在身体哪个位置。
"""
import os, sys, json
from PIL import Image, ImageDraw, ImageFont

PALETTE = [
    (230, 40, 40), (40, 120, 230), (30, 190, 90), (240, 150, 20), (170, 40, 220),
    (255, 80, 170), (20, 200, 200), (150, 190, 30), (240, 90, 30), (90, 60, 220),
    (255, 210, 30), (30, 90, 150), (200, 30, 90), (60, 200, 130), (120, 120, 240),
    (200, 120, 60), (90, 200, 60), (250, 80, 80), (40, 160, 220), (200, 180, 40),
    (140, 80, 200), (70, 190, 190), (230, 120, 200), (110, 150, 60),
]

FONTS = [r'C:\Windows\Fonts\msyh.ttc', r'C:\Windows\Fonts\msyhbd.ttc',
         '/System/Library/Fonts/PingFang.ttc']


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    tex_path, outdir = sys.argv[1], sys.argv[2]
    min_area = int(sys.argv[3]) if len(sys.argv) > 3 else 300
    os.makedirs(outdir, exist_ok=True)

    im = Image.open(tex_path).convert('RGBA')
    W, H = im.size
    px = im.load()

    # alpha 连通域
    label = [[0] * W for _ in range(H)]
    cur = 0
    islands = []
    for sy in range(H):
        for sx in range(W):
            if px[sx, sy][3] > 24 and label[sy][sx] == 0:
                cur += 1
                st = [(sx, sy)]; label[sy][sx] = cur
                x0 = x1 = sx; y0 = y1 = sy; n = 0
                while st:
                    x, y = st.pop(); n += 1
                    x0, x1 = min(x0, x), max(x1, x)
                    y0, y1 = min(y0, y), max(y1, y)
                    for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
                        nx, ny = x+dx, y+dy
                        if 0 <= nx < W and 0 <= ny < H and px[nx, ny][3] > 24 and label[ny][nx] == 0:
                            label[ny][nx] = cur; st.append((nx, ny))
                if n >= min_area:
                    islands.append({'lab': cur, 'n': n, 'box': [x0, y0, x1+1, y1+1]})

    islands.sort(key=lambda d: -d['n'])
    print(f'有效岛 {len(islands)} 个（面积 >= {min_area}）')

    dbg = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    dp = dbg.load()
    lab2color = {}
    for i, d in enumerate(islands):
        col = PALETTE[i % len(PALETTE)]
        d['color'] = list(col); d['id'] = i + 1
        lab2color[d['lab']] = col
    for y in range(H):
        row = label[y]
        for x in range(W):
            L = row[x]
            if L in lab2color:
                dp[x, y] = (*lab2color[L], 255)
    dbg.save(os.path.join(outdir, 'debug_texture.png'))

    # 图例
    cols = 4
    rows = (len(islands) + cols - 1) // cols
    CW, CH = 430, 44
    lg = Image.new('RGB', (CW*cols, CH*rows + 10), (255, 255, 255))
    d2 = ImageDraw.Draw(lg)
    f = ImageFont.truetype(next((p for p in FONTS if os.path.exists(p)), ''), 20) \
        if any(os.path.exists(p) for p in FONTS) else ImageFont.load_default()
    for i, d in enumerate(islands):
        r, c = divmod(i, cols)
        x, y = c*CW + 8, r*CH + 8
        d2.rectangle([x, y, x+30, y+28], fill=tuple(d['color']))
        b = d['box']
        d2.text((x+40, y+2), f"#{d['id']}  ({b[0]},{b[1]})-({b[2]},{b[3]})  {b[2]-b[0]}x{b[3]-b[1]}", fill=(20,20,30), font=f)
    lg.save(os.path.join(outdir, 'legend.png'))

    with open(os.path.join(outdir, 'islands_colored.json'), 'w', encoding='utf-8') as fp:
        json.dump([{'id': d['id'], 'box': d['box'], 'area': d['n'], 'color': d['color']} for d in islands],
                  fp, ensure_ascii=False, indent=2)

    for d in islands[:24]:
        b = d['box']
        print(f"  #{d['id']:2d}  RGB{tuple(d['color'])}  box={b}  {b[2]-b[0]}x{b[3]-b[1]}  面积{d['n']}")
    print(f'-> {outdir}/debug_texture.png , legend.png')
    print('下一步：用 debug_texture.png 替换模型贴图渲染一次，再跑 island_legend.py')


if __name__ == '__main__':
    main()
