#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
xlsx_probe.py — Excel 数据造假指纹核验（只读，零依赖）

用法:
    python xlsx_probe.py "C:\\path\\to\\数据.xlsx"

为什么不用 pandas/openpyxl：本机未装 openpyxl，pandas.read_excel 会 ImportError。
本脚本只用标准库 zipfile+xml，直接读 xlsx 内部 XML，任何时候都能跑。

输出四段：
  [0] 文件级指纹  —— 生成器/创建时间/修改间隔（最关键，一眼定性）
  [1] 结构总览    —— 各表行列数、字段名
  [2] 主体检      —— 时间戳、时长、IP/设备/重复、量表分布、直线作答
  [3] 分布自然度  —— 时长唯一值、日期峰谷、答案偏态
"""
import zipfile, re, sys
from xml.etree import ElementTree as ET
from collections import Counter
from datetime import datetime

NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
RNS = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'


def load(path):
    z = zipfile.ZipFile(path)
    names = z.namelist()
    shared = []
    if 'xl/sharedStrings.xml' in names:
        root = ET.fromstring(z.read('xl/sharedStrings.xml'))
        for si in root.findall(NS + 'si'):
            shared.append(''.join(t.text or '' for t in si.iter(NS + 't')))
    wb = ET.fromstring(z.read('xl/workbook.xml'))
    rels = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
    rmap = {r.get('Id'): r.get('Target') for r in rels}

    def ci(ref):
        m = re.match(r'([A-Z]+)', ref or 'A')
        n = 0
        for ch in m.group(1):
            n = n * 26 + ord(ch) - 64
        return n - 1

    def read(part):
        root = ET.fromstring(z.read(part))
        rows = []
        for row in root.iter(NS + 'row'):
            cells = {}
            for c in row.findall(NS + 'c'):
                t = c.get('t'); v = c.find(NS + 'v'); isn = c.find(NS + 'is')
                if t == 's' and v is not None:
                    val = shared[int(v.text)]
                elif t == 'inlineStr' and isn is not None:
                    val = ''.join(x.text or '' for x in isn.iter(NS + 't'))
                elif v is not None:
                    val = v.text
                    try:
                        f = float(val)
                        val = int(f) if f == int(f) else f
                    except Exception:
                        pass
                else:
                    continue
                cells[ci(c.get('r'))] = val
            if cells:
                w = max(cells) + 1
                rows.append([cells.get(i, '') for i in range(w)])
        return rows

    out = {}
    for sh in wb.find(NS + 'sheets'):
        t = rmap.get(sh.get(RNS + 'id'), '').lstrip('/')
        out[sh.get('name')] = read(t if t.startswith('xl/') else 'xl/' + t)
    return z, names, out


def file_fingerprint(z, names):
    print('=' * 62)
    print('[0] 文件级指纹')
    for part in ('docProps/core.xml', 'docProps/app.xml'):
        if part in names:
            txt = z.read(part).decode('utf-8', 'ignore')
            cre = re.search(r'<dc:creator[^>]*>(.*?)</dc:creator>', txt)
            created = re.search(r'<dcterms:created[^>]*>(.*?)</dcterms:created>', txt)
            modified = re.search(r'<dcterms:modified[^>]*>(.*?)</dcterms:modified>', txt)
            app = re.search(r'<Application>(.*?)</Application>', txt)
            if cre:
                print('  生成者(creator) :', cre.group(1))
            if app:
                print('  应用程序        :', app.group(1))
            if created:
                print('  创建时间        :', created.group(1))
            if modified:
                print('  修改时间        :', modified.group(1))
            if created and modified:
                f = '%Y-%m-%dT%H:%M:%SZ'
                try:
                    d = (datetime.strptime(modified.group(1), f)
                         - datetime.strptime(created.group(1), f)).total_seconds()
                    print('  创建→修改间隔   : %.0f 秒' % d)
                    if d < 300:
                        print('  >> 红旗：整个文件在 %d 秒内由脚本一次性写出，'
                              '基本不可能是问卷平台原始导出' % d)
                except Exception:
                    pass
    print('  zip 条目数      :', len(names))


def main(path):
    z, names, book = load(path)
    file_fingerprint(z, names)

    print('=' * 62)
    print('[1] 结构总览')
    for n, rows in book.items():
        if not rows:
            print('  %s: 空' % n); continue
        hdr = [str(x) for x in rows[0]]
        print('  %s: %d 行 x %d 列' % (n, len(rows), max(len(r) for r in rows)))
        print('     字段:', [h[:24] for h in hdr][:12])

    # 主表：取行数最多的那张
    main_name = max(book, key=lambda k: len(book[k]) * (max(len(r) for r in book[k]) if book[k] else 0))
    s = book[main_name]
    h = [str(x).strip() for x in s[0]]
    data = s[1:]
    I = {n: i for i, n in enumerate(h)}

    def col(n):
        i = I[n]
        return [r[i] if i < len(r) else '' for r in data]

    print('=' * 62)
    print('[2] 主表体检 —', main_name, '(%d 份)' % len(data))

    print('  整行完全重复:', len(data) - len({tuple(str(x) for x in r) for r in data}), '条')
    for c in ['作答ID', '用户ID', 'IP', '作答渠道', '设备类型', '提交时间']:
        if c in I:
            v = [str(x) for x in col(c)]
            print('  [%s] 唯一 %d/%d' % (c, len(set(v)), len(v)), Counter(v).most_common(3))

    tcol = next((c for c in ['作答总时长(秒)', '作答时长', '时长(秒)'] if c in I), None)
    if tcol:
        d = sorted(float(x) for x in col(tcol) if str(x).replace('.', '').isdigit())
        if d:
            n = len(d)
            print('  时长 min=%.0f p10=%.0f 中位=%.0f p90=%.0f max=%.0f'
                  % (d[0], d[int(n * .1)], d[n // 2], d[int(n * .9)], d[-1]))
            print('    <30秒废卷 %d 份；唯一值 %d/%d（重复率 %.2f）'
                  % (sum(1 for x in d if x < 30), len(set(d)), n, n / len(set(d))))
            if not any(x > 3 * d[n // 2] for x in d):
                print('    >> 存疑：无任何长尾（真人总有挂着页面不提交的），分布被压成窄带')

    sc, ec = ('开始时间' in I), ('结束时间' in I)
    if sc and ec:
        st, en = [str(x) for x in col('开始时间')], [str(x) for x in col('结束时间')]
        print('  开始时间 %s ~ %s' % (min(st), max(st)))
        print('  日期分布:', sorted(Counter(x[:10] for x in st).items()))
        if tcol:
            F = '%Y-%m-%d %H:%M:%S'; ok = bad = 0
            for a, b, dd in zip(st, en, col(tcol)):
                try:
                    A = datetime.strptime(a, F); B = datetime.strptime(b, F)
                    if abs((B - A).total_seconds() - float(dd)) < 1:
                        ok += 1
                    else:
                        bad += 1
                except Exception:
                    pass
            print('  时间戳自洽（结束-开始==时长）: 一致 %d / 不一致 %d' % (ok, bad))

    if '操作系统类型' in I and '浏览器类型' in I:
        fp = [tuple(str(col(k)[i]) for k in ['操作系统类型', '浏览器类型'] if k in I)
              for i in range(len(data))]
        print('  设备指纹组合 唯一 %d/%d' % (len(set(fp)), len(fp)), Counter(fp).most_common(3))

    keys = [k for k in h if re.search(r'-(C[123]|SC\d|MA\d|CI\d|PV\d|SA\d|SI\d|SB\d)\.', k)]
    if keys:
        allv = Counter()
        for k in keys:
            allv.update(str(x) for x in col(k))
        print('  量表题 %d 个，总答案分布:' % len(keys), sorted(allv.items()))
        lin = sum(1 for i in range(len(data))
                  if len({str(col(k)[i]) for k in keys}) == 1)
        print('  直线作答（全部同答案）:', lin, '份')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else input('xlsx 路径: ').strip('"'))
