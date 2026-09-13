# -*- coding: utf-8 -*-
"""把重绘后的部件按原坐标贴回，生成新的 texture 贴图。

用法:
    python reassemble.py <原贴图> <manifest.json> <重绘件目录> <输出.png>

说明:
    manifest.json 由 part_segment.py 产出（04_manifest.json）。
    重绘件目录里放同名文件即可（如 01_后发.png）；缺失的部件自动沿用原图，不会留空洞。
    重绘件尺寸若与 box 不符，会先缩放到 box 尺寸——但**强烈建议保持原尺寸**，
    缩放会引入模糊并可能让 UV 对齐偏移。
"""
import sys, os, json, argparse

try:
    from PIL import Image
except ImportError:
    sys.exit('需要 Pillow: pip install pillow')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('texture')
    ap.add_argument('manifest')
    ap.add_argument('parts_dir')
    ap.add_argument('out')
    ap.add_argument('--strict-size', action='store_true',
                    help='尺寸不符时报错退出，而不是自动缩放')
    a = ap.parse_args()

    base = Image.open(a.texture).convert('RGBA')
    with open(a.manifest, encoding='utf-8') as f:
        manifest = json.load(f)

    pasted, missing, resized = 0, [], []
    for m in manifest:
        fn = m.get('file') or f"{m['id']:02d}_{m.get('name','part')}.png"
        src = os.path.join(a.parts_dir, fn)
        if not os.path.exists(src):
            alt = [f for f in os.listdir(a.parts_dir) if f.startswith(f"{m['id']:02d}_")]
            if alt:
                src = os.path.join(a.parts_dir, alt[0])
            else:
                missing.append(fn); continue

        part = Image.open(src).convert('RGBA')
        x0, y0, x1, y1 = m['box']
        bw, bh = x1 - x0, y1 - y0
        if part.size != (bw, bh):
            if a.strict_size:
                sys.exit(f'尺寸不符: {fn} 是 {part.size}，期望 {(bw, bh)}')
            part = part.resize((bw, bh), Image.LANCZOS)
            resized.append(fn)

        # 只覆盖部件框内、且重绘件不透明的像素，保留框内原有的其他内容
        base.paste(part, (x0, y0), part)
        pasted += 1

    base.save(a.out)
    print(f'已贴回 {pasted}/{len(manifest)} 个部件 -> {a.out}  {base.size}')
    if resized:
        print(f'⚠ 被缩放 {len(resized)} 个（建议重绘时保持原尺寸）: {", ".join(resized[:5])}')
    if missing:
        print(f'ℹ 缺失 {len(missing)} 个（沿用原图）: {", ".join(missing[:5])}')
    print('下一步：把输出文件替换掉原 texture，重新加载模型查看效果。')


if __name__ == '__main__':
    main()
