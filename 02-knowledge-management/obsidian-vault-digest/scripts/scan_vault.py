# -*- coding: utf-8 -*-
"""扫描 Obsidian vault，导出结构元数据 JSON"""
import os, re, json, io

import sys
if len(sys.argv) < 3:
    print('usage: python scan_vault.py <vault_dir> <out.json>')
    sys.exit(1)
VAULT, OUT = sys.argv[1], sys.argv[2]

files = []
for root, dirs, names in os.walk(VAULT):
    dirs[:] = [d for d in dirs if d not in ('.obsidian', '.git', '.trash')]
    for n in names:
        if n.lower().endswith('.md'):
            files.append(os.path.join(root, n))

def read(p):
    for enc in ('utf-8', 'utf-8-sig', 'gbk'):
        try:
            with io.open(p, encoding=enc) as f:
                return f.read()
        except Exception:
            continue
    return ''

items = []
for p in sorted(files):
    rel = os.path.relpath(p, VAULT).replace('\\', '/')
    txt = read(p)
    lines = txt.split('\n')
    # frontmatter
    fm = {}
    body = txt
    if txt.startswith('---'):
        m = re.match(r'^---\n(.*?)\n---\n', txt, re.S)
        if m:
            fmb = m.group(1)
            body = txt[m.end():]
            for ln in fmb.split('\n'):
                mm = re.match(r'^\s*([A-Za-z_\-\u4e00-\u9fa5]+)\s*:\s*(.*)$', ln)
                if mm:
                    fm[mm.group(1).strip()] = mm.group(2).strip()

    def in_code(l):
        return l.strip().startswith('```')

    code = False
    heads = []
    for ln in body.split('\n'):
        if in_code(ln):
            code = not code
            continue
        if code:
            continue
        m = re.match(r'^(#{1,4})\s+(.*)$', ln)
        if m:
            heads.append({'level': len(m.group(1)), 'text': m.group(2).strip()})

    tags = set(re.findall(r'#([^\s#\[\]()（）,，。、]+)', body))
    # 中文标签（无空格）可能过度匹配，只保留短且非纯数字的
    tags = {t for t in tags if len(t) <= 20 and not t.isdigit()}

    links = set(re.findall(r'\[\[([^\]\|]+)(?:\|[^\]]*)?\]\]', body))
    links = {l.strip() for l in links}

    cn = len(re.findall(r'[\u4e00-\u9fa5]', body))
    en = len(re.findall(r'[A-Za-z]+', body))

    # 纯文本预览（去 markdown 符号）
    plain = re.sub(r'```.*?```', '', body, flags=re.S)
    plain = re.sub(r'^#+\s*', '', plain, flags=re.M)
    plain = re.sub(r'[`*>_\[\]()]', '', plain)
    plain = re.sub(r'\s+', ' ', plain).strip()

    items.append({
        'path': rel,
        'folder': os.path.dirname(rel) or '(根目录)',
        'name': os.path.basename(rel),
        'bytes': os.path.getsize(p),
        'lines': len(lines),
        'mtime': os.path.getmtime(p),
        'cn_chars': cn,
        'en_words': en,
        'headings': heads,
        'tags': sorted(tags),
        'links': sorted(links),
        'frontmatter': fm,
        'preview': plain[:400],
    })

with io.open(OUT, 'w', encoding='utf-8') as f:
    json.dump(items, f, ensure_ascii=False, indent=1)

print('files:', len(items))
for it in items:
    print('%-70s cn=%-6d heads=%-3d tags=%s' % (it['path'][:70], it['cn_chars'], len(it['headings']), it['tags'][:5]))
