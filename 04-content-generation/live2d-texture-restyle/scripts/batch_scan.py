# -*- coding: utf-8 -*-
"""批量筛查：把一堆候选图按「与原稿画风的贴合度」打分排序，并出一张带分数的总览图。

用法:
    python batch_scan.py <原稿或画风样板图> <候选图目录> [--top 12] [--out 目录] [--picked "挑选目录"]

例:
    python batch_scan.py ref_画风样板.jpg ./gemini_output --top 12

输出:
    <out>/batch_ranking.png   按分数从高到低排列的总览图（带分数，便于一眼挑）
    <out>/batch_scores.json   完整分数明细
    分数 >= 80 的图会复制到 <picked> 目录（若指定）

评分逻辑：以原稿的实测指标为目标，逐项算偏差，加权成 0~100 的「画风贴合分」。
"""
import sys, os, json, shutil, argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from style_probe import probe
except ImportError:
    sys.exit('找不到 style_probe.py，请与本脚本放在同一目录')

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    sys.exit('需要 Pillow')

FONTS = [r'C:\Windows\Fonts\msyhbd.ttc', r'C:\Windows\Fonts\msyh.ttc',
         '/System/Library/Fonts/PingFang.ttc']

def font(sz):
    for f in FONTS:
        if os.path.exists(f):
            try: return ImageFont.truetype(f, sz)
            except Exception: pass
    return ImageFont.load_default()

EXT = ('.png', '.jpg', '.jpeg', '.webp', '.bmp')

# 指标权重：明度/饱和是主因，线条次之
W = {'V_median': 1.0, 'V_high_ratio': 0.8, 'S_median': 0.9, 'S_low_ratio': 0.5, 'line_ratio': 2.5}


def score(ref, cand):
    """越低越像；转成 0~100 分（越高越贴合）。"""
    d = 0.0
    for k, w in W.items():
        d += abs(ref[k] - cand[k]) * w
    # 线条颜色差异：近黑 vs 彩色描边，是"像不像"的强信号
    try:
        rh = ref.get('line_color') or '#000000'
        ch = cand.get('line_color') or '#000000'
        rr, rg, rb = int(rh[1:3],16), int(rh[3:5],16), int(rh[5:7],16)
        cr, cg, cb = int(ch[1:3],16), int(ch[3:5],16), int(ch[5:7],16)
        line_delta = (abs(rr-cr)+abs(rg-cg)+abs(rb-cb)) / 3 / 255 * 100
    except Exception:
        line_delta = 0
    d += line_delta * 0.4
    return max(0.0, min(100.0, 100.0 - d))


def contact_sheet(items, out_path, cols=4, cell=380):
    rows = (len(items) + cols - 1) // cols
    pad, capH = 16, 44
    sheet = Image.new('RGB', (cols*(cell+pad)+pad, rows*(cell+capH+pad)+pad), (250, 250, 252))
    d = ImageDraw.Draw(sheet)
    f = font(19)
    for i, (sc, path) in enumerate(items):
        r, c = divmod(i, cols)
        x = pad + c*(cell+pad); y = pad + r*(cell+capH+pad)
        try:
            im = Image.open(path).convert('RGB')
            im.thumbnail((cell, cell), Image.LANCZOS)
        except Exception:
            continue
        sheet.paste(im, (x + (cell-im.width)//2, y + capH + (cell-im.height)//2))
        good = sc >= 80
        d.rectangle([x, y, x+cell, y+capH-6], fill=(46,150,90) if good else (150,150,160))
        nm = os.path.basename(path)
        nm = nm if len(nm) <= 30 else nm[:27] + '...'
        d.text((x+8, y+8), f'{sc:5.1f}  {nm}', fill=(255,255,255), font=f)
    sheet.save(out_path, quality=92)
    return sheet.size


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('reference')
    ap.add_argument('folder')
    ap.add_argument('--top', type=int, default=12)
    ap.add_argument('--cols', type=int, default=4)
    ap.add_argument('--out', default=None)
    ap.add_argument('--picked', default=None, help='分数达标的图复制到这个目录')
    ap.add_argument('--ref-bg', default='auto', choices=['auto','alpha','white'])
    ap.add_argument('--bg', default='white', choices=['auto','alpha','white'])
    a = ap.parse_args()

    out = a.out or a.folder
    os.makedirs(out, exist_ok=True)

    ref = probe(a.reference, a.ref_bg)
    if 'error' in ref:
        sys.exit('参考图解析失败: ' + ref['error'])
    print(f"参考: {ref['file']}  V中位 {ref['V_median']}%  S中位 {ref['S_median']}%  "
          f"线条 {ref['line_color']}({ref['line_ratio']}%)  主色 {ref['top_colors'][0]['hex'] if ref['top_colors'] else '-'}")

    files = [os.path.join(a.folder, f) for f in sorted(os.listdir(a.folder))
             if f.lower().endswith(EXT) and not f.startswith('batch_')]
    if not files:
        sys.exit('目录里没有图片: ' + a.folder)
    print(f'找到 {len(files)} 张候选，开始评分…')

    results = []
    for p in files:
        r = probe(p, a.bg)
        if 'error' in r:
            print('  跳过', os.path.basename(p), r['error']); continue
        sc = score(ref, r)
        results.append({'file': os.path.basename(p), 'path': p, 'score': round(sc, 1),
                        'V_median': r['V_median'], 'V_high_ratio': r['V_high_ratio'],
                        'S_median': r['S_median'], 'S_low_ratio': r['S_low_ratio'],
                        'line_color': r['line_color'], 'line_ratio': r['line_ratio'],
                        'top_color': r['top_colors'][0]['hex'] if r['top_colors'] else None})

    results.sort(key=lambda x: -x['score'])
    for r in results[:a.top]:
        flag = 'OK ' if r['score'] >= 72 else ('~  ' if r['score'] >= 55 else '!! ')
        print(f"  {flag}{r['score']:5.1f}  V{r['V_median']:5.1f} S{r['S_median']:5.1f} "
              f"线{r['line_color']} {r['line_ratio']:4.1f}%  {r['file']}")

    # 诊断最佳候选的主要差距（比分数更有指导性）
    if results:
        b = results[0]
        print(f"\n最佳候选「{b['file']}」与原稿的差距：")
        gaps = []
        for k, label in (('V_median', '明度中位'), ('S_median', '饱和中位'),
                         ('V_high_ratio', '高明度占比'), ('S_low_ratio', '低饱和占比'),
                         ('line_ratio', '线条粗细占比')):
            dv = b.get(k, 0) - ref[k]
            if abs(dv) >= 3:
                direction = '偏' + ('高' if dv > 0 else '低')
                hint = ''
                if k == 'line_ratio':
                    hint = '  ← 描边太粗，画风会显得"厚"' if dv > 0 else '  ← 描边太细'
                if k == 'V_median' and dv < 0:
                    hint = '  ← 整体偏暗，容易有"厚涂/油画感"'
                if k == 'S_median' and dv > 0:
                    hint = '  ← 颜色偏艳'
                gaps.append(f"  {label}: {ref[k]:.1f}% → {b.get(k,0):.1f}%  ({direction} {abs(dv):.1f}){hint}")
        print('\n'.join(gaps) if gaps else '  各项均在阈值内，贴合良好')

    with open(os.path.join(out, 'batch_scores.json'), 'w', encoding='utf-8') as f:
        json.dump({'reference': ref['file'], 'results': results}, f, ensure_ascii=False, indent=2)

    top = results[:a.top]
    if top:
        size = contact_sheet([(r['score'], r['path']) for r in top],
                             os.path.join(out, 'batch_ranking.png'), cols=a.cols)
        print(f"\n总览图 -> {os.path.join(out, 'batch_ranking.png')}  {size}")

    if a.picked:
        os.makedirs(a.picked, exist_ok=True)
        n = 0
        for r in results:
            if r['score'] >= 72:
                shutil.copy(r['path'], os.path.join(a.picked, r['file'])); n += 1
        print(f'达标(≥72)的 {n} 张已复制到 {a.picked}')

    best = results[0] if results else None
    if best:
        print(f"\n最贴合：{best['file']}  {best['score']} 分")


if __name__ == '__main__':
    main()
