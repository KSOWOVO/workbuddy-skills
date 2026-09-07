# -*- coding: utf-8 -*-
"""抽取各篇中含方法论标记的关键句"""
import os, re, io, json

import sys
if len(sys.argv) < 3:
    print('usage: python extract_points.py <vault_dir> <out.json>')
    sys.exit(1)
VAULT, OUT = sys.argv[1], sys.argv[2]
# 先用 scan_vault.py 拿到文件清单，把要精读的相对路径填进 TARGETS
TARGETS = [
    "30-升学规划/雅思/雅思自学流程介绍，以及一些奇技淫巧.md",
    "30-升学规划/雅思写作/大作文/雅思大作文写作【1. 大作文题型介绍 & Agree or disagree 题型带练】.md",
    "30-升学规划/雅思写作/大作文/雅思大作文写作【2 positive or negative】.md",
    "30-升学规划/雅思写作/大作文/雅思大作文写作 【3. discuss both views and give your own opinion】.md",
    "30-升学规划/雅思写作/大作文/雅思大作文写作 【4. Do you think the advantages of this trend outweigh the disadvantage】.md",
    "30-升学规划/雅思写作/大作文/雅思大作文写作 【5. Why_Why+positive or negative】.md",
    "30-升学规划/雅思写作/小作文/雅思小作文写作【1. line graph】.md",
    "30-升学规划/雅思写作/小作文/雅思小作文写作【2. table】.md",
    "30-升学规划/雅思写作/小作文/雅思小作文写作【3. 柱状图】.md",
    "30-升学规划/雅思写作/小作文/雅思小作文写作【4. 饼图】.md",
    "30-升学规划/雅思写作/小作文/雅思小作文写作【5.流程图】.md",
    "30-升学规划/雅思写作/小作文/雅思小作文【6.地图题】.md",
    "40-个人生活/投资理财/想提前退休？保证你一学就会还可照搬的投资方法_保姆级完整教学，基本一听就懂，且长期收益秒杀95%的大V _ 想财务自由提前退休必看！.md",
    "40-个人生活/投资理财/存钱=亏钱_万字解析最适合普通人的投资指南【阿Test正经比比】.md",
    "40-个人生活/投资理财/如何理财，如何爱人，如何破产.md",
    "40-个人生活/投资理财/大男主如何管理小金库？.md",
]

MARK = re.compile(r'(首先|其次|最后|第一|第二|第三|第四|记住|核心|关键|重点|总结|所以|因此|一定|不要|建议|原则|方法|技巧|公式|比例|策略|就是|本质|其实)')

def read(p):
    for enc in ('utf-8', 'utf-8-sig', 'gbk'):
        try:
            with io.open(p, encoding=enc) as f:
                return f.read()
        except Exception:
            continue
    return ''

res = {}
for rel in TARGETS:
    p = os.path.join(VAULT, rel)
    if not os.path.exists(p):
        print('MISS', rel); continue
    txt = read(p)
    txt = re.sub(r'^.*?发言人.*?\d\d:\d\d', '', txt, count=1, flags=re.S) if '发言人' in txt else txt
    # 去掉时间戳前缀
    txt = re.sub(r'发言人\s*\d*\s*\d\d:\d\d', '', txt)
    sents = re.split(r'[。！？\n]', txt)
    picked = []
    seen = set()
    for s in sents:
        s = re.sub(r'\s+', '', s).strip()
        if not (25 <= len(s) <= 130):
            continue
        if not MARK.search(s):
            continue
        if s.startswith('|') or s.startswith('#'):
            continue
        key = s[:18]
        if key in seen:
            continue
        seen.add(key)
        picked.append(s)
    res[rel] = picked[:30]

with io.open(OUT, 'w', encoding='utf-8') as f:
    json.dump(res, f, ensure_ascii=False, indent=1)
print('done', {k: len(v) for k, v in res.items()})
