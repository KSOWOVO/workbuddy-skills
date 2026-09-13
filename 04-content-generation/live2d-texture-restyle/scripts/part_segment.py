# -*- coding: utf-8 -*-
"""Live2D 贴图分区：网格法 + 连通域找出部件块，输出标注图 / 清单 / 单部件裁剪。

用法:
    # 1) 自动分块（先摸底，看看部件大概在哪）
    python part_segment.py texture_00.png outdir

    # 2) 人工核对后写 parts.json，按语义命名重新出图（推荐）
    #    parts.json 格式: [{"id":1,"name":"后发","box":[x0,y0,x1,y1]}, ...]
    python part_segment.py texture_00.png outdir --parts parts.json

产出:
    outdir/01_网格参考.png      32px 网格叠加，方便读坐标
    outdir/02_auto_blocks.json  自动分块结果（含坐标）
    outdir/03_标注图.png        带编号+名称的标注图（喂给出图 AI 用）
    outdir/parts/<id>_<name>.png 单部件裁剪（逐区重绘时用）
"""
import sys, os, json, argparse

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    sys.exit('需要 Pillow: pip install pillow')

FONT_CANDIDATES = [
    r'C:\Windows\Fonts\msyhbd.ttc', r'C:\Windows\Fonts\msyh.ttc',
    r'C:\Windows\Fonts\simhei.ttf',
    '/System/Library/Fonts/PingFang.ttc',
    '/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc',
]


def load_font(size):
    for fp in FONT_CANDIDATES:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                pass
    return ImageFont.load_default()


def auto_blocks(im, grid=32, min_cells=6):
    """网格法 + 8 邻域连通域合并，返回部件块列表。"""
    W, H = im.size
    px = im.load()
    cols, rows = W // grid, H // grid
    occ = [[False] * cols for _ in range(rows)]
    for r in range(rows):
        for c in range(cols):
            hit = False
            for y in range(r * grid, r * grid + grid, max(1, grid // 8)):
                for x in range(c * grid, c * grid + grid, max(1, grid // 8)):
                    if x < W and y < H and px[x, y][3] > 16:
                        hit = True; break
                if hit: break
            occ[r][c] = hit

    seen = [[False] * cols for _ in range(rows)]
    blocks = []
    for r in range(rows):
        for c in range(cols):
            if occ[r][c] and not seen[r][c]:
                st = [(r, c)]; seen[r][c] = True
                minr = maxr = r; minc = maxc = c; cnt = 0
                while st:
                    cr, cc = st.pop(); cnt += 1
                    minr, maxr = min(minr, cr), max(maxr, cr)
                    minc, maxc = min(minc, cc), max(maxc, cc)
                    for dr in (-1, 0, 1):
                        for dc in (-1, 0, 1):
                            nr, nc = cr + dr, cc + dc
                            if 0 <= nr < rows and 0 <= nc < cols and occ[nr][nc] and not seen[nr][nc]:
                                seen[nr][nc] = True; st.append((nr, nc))
                if cnt >= min_cells:
                    blocks.append({'x': minc * grid, 'y': minr * grid,
                                   'w': (maxc - minc + 1) * grid,
                                   'h': (maxr - minr + 1) * grid, 'cells': cnt})
    blocks.sort(key=lambda b: -b['cells'])
    return blocks


def make_grid_ref(im, out_path, grid=32):
    g = im.copy(); px = g.load()
    W, H = g.size
    for i in range(0, W + 1, grid):
        for y in range(H):
            if i < W:
                r, gg, b, a = px[i, y]
                px[i, y] = (255, 60, 60, 110) if (y // 8) % 2 == 0 else (r, gg, b, max(a, 1))
    for j in range(0, H + 1, grid):
        for x in range(W):
            if j < H:
                r, gg, b, a = px[x, j]
                px[x, j] = (255, 60, 60, 110) if (x // 8) % 2 == 0 else (r, gg, b, max(a, 1))
    g.save(out_path)


def render(im, parts, out_path):
    out = im.copy()
    d = ImageDraw.Draw(out)
    font = load_font(max(16, im.width // 70))
    W, H = im.size
    for p in parts:
        x0, y0, x1, y1 = p['box']
        d.rectangle([x0, y0, x1, y1], outline=(255, 40, 120, 255), width=max(2, W // 400))
        label = f"{p['id']} {p.get('name','')}"
        try:
            tw = int(d.textlength(label, font=font)) + 16
        except Exception:
            tw = len(label) * font.size + 16
        lx = min(max(0, x0), W - tw - 4)
        ly = max(0, y0 - int(font.size * 1.3))
        d.rectangle([lx, ly, lx + tw, ly + int(font.size * 1.25)], fill=(255, 0, 100, 240))
        d.text((lx + 8, ly + 2), label, fill=(255, 255, 255, 255), font=font)
    out.save(out_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('texture')
    ap.add_argument('outdir')
    ap.add_argument('--parts', help='人工核对的部件清单 json')
    ap.add_argument('--grid', type=int, default=32)
    ap.add_argument('--min-cells', type=int, default=6)
    a = ap.parse_args()

    os.makedirs(a.outdir, exist_ok=True)
    im = Image.open(a.texture).convert('RGBA')
    W, H = im.size
    print(f'贴图 {W}x{H}')

    make_grid_ref(im, os.path.join(a.outdir, '01_网格参考.png'), a.grid)

    blocks = auto_blocks(im, a.grid, a.min_cells)
    with open(os.path.join(a.outdir, '02_auto_blocks.json'), 'w', encoding='utf-8') as f:
        json.dump(blocks, f, ensure_ascii=False, indent=2)
    print(f'自动分块 {len(blocks)} 块 -> 02_auto_blocks.json')
    print('  （自动分块只是摸底，请肉眼核对语义后写 parts.json 再跑一次 --parts）')

    if a.parts:
        with open(a.parts, encoding='utf-8') as f:
            parts = json.load(f)
    else:
        parts = [{'id': i, 'name': f'part{i}', 'box': [b['x'], b['y'], b['x'] + b['w'], b['y'] + b['h']]}
                 for i, b in enumerate(blocks, 1)]

    render(im, parts, os.path.join(a.outdir, '03_标注图.png'))

    pd = os.path.join(a.outdir, 'parts')
    os.makedirs(pd, exist_ok=True)
    manifest = []
    for p in parts:
        x0, y0, x1, y1 = p['box']
        safe = str(p.get('name', 'part')).replace('/', '_').replace(' ', '')
        fn = f"{p['id']:02d}_{safe}.png"
        im.crop((max(0, x0), max(0, y0), min(W, x1), min(H, y1))).save(os.path.join(pd, fn))
        manifest.append({'id': p['id'], 'name': p.get('name'), 'box': [x0, y0, x1, y1],
                         'w': x1 - x0, 'h': y1 - y0, 'file': fn})
    with open(os.path.join(a.outdir, '04_manifest.json'), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f'标注图 -> 03_标注图.png   单部件 {len(manifest)} 个 -> parts/')
    print('逐区重绘时：部件必须留在自己的 box 内，画布尺寸不可变。')
    print('拼回时按 04_manifest.json 的 box 原位贴回。')


if __name__ == '__main__':
    main()
