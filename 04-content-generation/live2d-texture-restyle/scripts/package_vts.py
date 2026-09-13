# -*- coding: utf-8 -*-
"""打包成 VTube Studio 可直接导入的模型文件夹。

用法:
    python package_vts.py --src <原模型目录> --tex <新贴图.png> --name OC_myoc [--out <交付目录>]

    # 一次打两套（多套服装 = 多个文件夹）
    python package_vts.py --src ../yoyo --tex tex_a.png --name OC_open  --out 交付/
    python package_vts.py --src ../yoyo --tex tex_b.png --name OC_zipped --out 交付/

--src 里需要有 *.moc3 / *.model3.json / *.physics3.json / *.cdi3.json（脚本自动识别）。
产出结构：
    交付/OC_myoc/
        OC_myoc.model3.json      ← 这个文件名就是 VTS 里显示的模型名
        OC_myoc.moc3
        OC_myoc.physics3.json
        OC_myoc.cdi3.json
        icon.png
        OC_myoc.2048/texture_00.png
"""
import os, sys, json, glob, shutil, argparse


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', required=True, help='原模型目录（含 moc3 等）')
    ap.add_argument('--tex', required=True, help='新贴图 png')
    ap.add_argument('--name', required=True, help='模型名（会成为文件名与 VTS 显示名）')
    ap.add_argument('--out', default='交付_OC模型', help='交付目录')
    ap.add_argument('--tex-size', default='2048', help='贴图目录后缀，默认 2048')
    a = ap.parse_args()

    src = os.path.abspath(a.src)
    stem = a.name

    def find(pat):
        g = glob.glob(os.path.join(src, pat))
        return g[0] if g else None

    moc = find('*.moc3')
    if not moc:
        sys.exit(f'在 {src} 里找不到 .moc3')
    phys = find('*.physics3.json')
    cdi = find('*.cdi3.json')
    icon = find('icon*.png') or find('ico*.png')
    orig_json = find('*.model3.json')

    d = os.path.join(os.path.abspath(a.out), stem)
    texdir = os.path.join(d, f'{stem}.{a.tex_size}')
    os.makedirs(texdir, exist_ok=True)

    shutil.copy(moc, os.path.join(d, f'{stem}.moc3'))
    if phys: shutil.copy(phys, os.path.join(d, f'{stem}.physics3.json'))
    if cdi:  shutil.copy(cdi,  os.path.join(d, f'{stem}.cdi3.json'))
    if icon: shutil.copy(icon, os.path.join(d, 'icon.png'))
    shutil.copy(a.tex, os.path.join(texdir, 'texture_00.png'))

    # 以原 model3.json 为模板；没有就新建
    cfg = {'Version': 3, 'FileReferences': {}, 'Groups': []}
    if orig_json:
        try:
            with open(orig_json, encoding='utf-8') as f:
                cfg = json.load(f)
        except Exception:
            pass
    cfg.setdefault('FileReferences', {})
    cfg['FileReferences'].update({
        'Moc': f'{stem}.moc3',
        'Textures': [f'{stem}.{a.tex_size}/texture_00.png'],
    })
    if phys: cfg['FileReferences']['Physics'] = f'{stem}.physics3.json'
    if cdi:  cfg['FileReferences']['DisplayInfo'] = f'{stem}.cdi3.json'
    if icon: cfg['FileReferences']['Icon'] = 'icon.png'

    # 补标准眨眼分组（否则 VTS 里不眨眼）
    groups = cfg.setdefault('Groups', [])
    if not any(g.get('Name') == 'EyeBlink' for g in groups):
        groups.append({'Target': 'Parameter', 'Name': 'EyeBlink',
                       'Ids': ['ParamEyeLOpen', 'ParamEyeROpen']})

    with open(os.path.join(d, f'{stem}.model3.json'), 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

    print(f'✔ {d}')
    for root, _, files in os.walk(d):
        for fn in sorted(files):
            p = os.path.join(root, fn)
            print(f'    {os.path.relpath(p, d):40s} {os.path.getsize(p)/1024:8.1f} KB')
    print('\n把整个文件夹复制到 <VTube Studio>/Live2DModels/ 即可导入。')


if __name__ == '__main__':
    main()
