# -*- coding: utf-8 -*-
"""合成四级词库：KyleBing 词表 + ECDict(音标/释义/词形) + ipa-dict 兜底音标"""
import csv, json, re, sys, collections

csv.field_size_limit(10 ** 9)
import argparse
_ap = argparse.ArgumentParser()
_ap.add_argument('--kb-file', default='cet4_kb.txt', help='考纲词表（TAB 分隔：word\t释义）')
_ap.add_argument('--target', type=int, default=3500, help='收录词数')
_ap.add_argument('--out', default='words.json')
A = _ap.parse_args()
KB_FILE, TARGET, OUT = A.kb_file, A.target, A.out

# ---------- 1. KyleBing 四级词表 ----------
kb = {}          # word -> meaning
kb_order = []
for line in open(KB_FILE, encoding='utf-8'):
    line = line.rstrip('\n')
    if not line.strip():
        continue
    p = line.split('\t')
    if len(p) < 2:
        continue
    w = p[0].strip().lower()
    if not re.match(r"^[a-z][a-z\-']*$", w):
        continue
    m = '\t'.join(p[1:]).strip()
    if w not in kb:
        kb[w] = m
        kb_order.append(w)

# ---------- 2. ECDict ----------
ec = {}
phrases = []     # (phrase, collins, oxford, frq)
with open('ecdict.csv', encoding='utf-8', errors='ignore') as f:
    r = csv.reader(f)
    hdr = next(r, None)
    idx = {h: i for i, h in enumerate(hdr or [])}
    for row in r:
        if len(row) < len(hdr):
            continue
        w = (row[idx['word']] or '').strip().lower()
        if not w:
            continue
        try:
            frq = int(row[idx['frq']] or 0)
        except ValueError:
            frq = 0
        try:
            col = int(row[idx['collins']] or 0)
        except ValueError:
            col = 0
        try:
            oxf = int(row[idx['oxford']] or 0)
        except ValueError:
            oxf = 0
        if ' ' in w:
            if len(w) < 42 and (col >= 2 or oxf == 1 or frq > 0):
                phrases.append((w, col, oxf, frq))
            continue
        ec[w] = {
            'ph': (row[idx['phonetic']] or '').strip(),
            'tr': (row[idx['translation']] or '').strip(),
            'ex': (row[idx['exchange']] or '').strip(),
            'frq': frq,
            'tag': (row[idx['tag']] or '').strip(),
        }

# ---------- 3. ipa-dict 标准音标（英式优先，美式兜底） ----------
ipa_uk, ipa_us = {}, {}
for fn, d in (('ipa_en_UK.txt', ipa_uk), ('ipa_en_US.txt', ipa_us)):
    try:
        for line in open(fn, encoding='utf-8'):
            p = line.rstrip('\n').split('\t')
            if len(p) >= 2 and p[1].strip():
                d[p[0].strip().lower()] = p[1].strip()
    except FileNotFoundError:
        pass

# ---------- 4. 选词：四级 tag 优先 + 词频高的优先（frq 越小越常用） ----------
def score(w):
    e = ec.get(w)
    if e:
        f = e['frq'] if e['frq'] > 0 else 10 ** 6
        return (0 if 'cet4' in e['tag'] else 1, f)
    return (2, 10 ** 6)

ranked = sorted(kb_order, key=lambda w: (score(w)[0], score(w)[1], w))
chosen = ranked[:TARGET]
chosen_set = set(chosen)

# ---------- 5. 短语索引（常考搭配来源） ----------
phr_by_word = collections.defaultdict(list)
for ph, col, oxf, frq in phrases:
    toks = ph.split()
    for t in set(toks):
        t = t.strip(".,'-")
        if t in chosen_set:
            phr_by_word[t].append((frq, col, oxf, ph))
for w in phr_by_word:
    phr_by_word[w].sort(key=lambda x: (-x[1], -x[2], -x[0], len(x[3])))

# ---------- 6. 词形变化 ----------
EX_NAME = {'p': '过去式', 'd': '过去分词', 'i': '现在分词', '3': '三单',
           'r': '比较级', 't': '最高级', 's': '复数', '0': '原型', '1': '变形'}
def forms(ex):
    if not ex:
        return ''
    out = []
    for seg in ex.split('/'):
        if ':' not in seg:
            continue
        k, v = seg.split(':', 1)
        k = k.strip()
        if k in ('p', 'd', 'i', '3', 'r', 't', 's') and v.strip():
            out.append(EX_NAME.get(k, k) + ' ' + v.strip())
    seen = set()
    res = []
    for o in out:
        if o not in seen:
            seen.add(o)
            res.append(o)
    return ' · '.join(res[:3])

POS_RE = re.compile(r'^\s*((?:n|v|vt|vi|adj|adv|prep|conj|pron|num|art|int|aux)\.(?:\s*[，,]\s*)?)+')
def split_pos(m):
    mm = POS_RE.match(m)
    if mm:
        pos = mm.group(1).strip().rstrip('，,')
        rest = m[mm.end():].strip()
        return pos, (rest or m)
    return '', m

def clean_tr(s, w):
    s = s.replace('\\n', '；').replace('\n', '；').strip()
    s = re.sub(r'(；\s*)+', '；', s).strip('；')
    s = re.sub(r'\s{2,}', ' ', s)
    if len(s) > 58:
        # 截断到第一个句号/分号后
        cut = re.split(r'(?<=[；;])', s)
        acc = ''
        for c in cut:
            if len(acc) + len(c) > 58:
                break
            acc += c
        s = acc.strip(' ；;，,') or s[:58]
    return s

out = []
noph = 0
nocol = 0
for w in chosen:
    e = ec.get(w)
    kb_m = kb.get(w, '')
    # 音标：英式 > 美式 > ECDict
    ph = ipa_uk.get(w) or ipa_us.get(w) or ''
    if not ph and e and e['ph']:
        p = e['ph'].strip()
        p = (p.replace('ә', 'ə').replace('є', 'ɛ').replace('ɡ', 'ɡ')
              .replace("'", 'ˈ').replace('ɒ', 'ɒ'))
        if not p.startswith('/'):
            p = '/' + p.strip('/') + '/'
        ph = p
    if not ph:
        noph += 1
    # 释义 + 词性
    src = ''
    if e and e['tr']:
        src = clean_tr(e['tr'], w)
    if not src:
        src = kb_m
    pos, cn = split_pos(src)
    if not pos:
        kpos, _ = split_pos(kb_m)
        pos = kpos
    if not cn:
        cn = kb_m
    # 搭配
    col = ''
    cand = phr_by_word.get(w)
    if cand:
        col = cand[0][3]
    if not col:
        col = forms(e['ex'] if e else '')
    if not col:
        nocol += 1
    out.append([w, ph, pos, cn, col])

json.dump(out, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print('chosen', len(out))
print('no phonetic', noph, 'no collocation', nocol)
print('with phrase collocation', sum(1 for x in out if x[4] and ' ' in x[4]))
print('sample:')
for x in out[:5]:
    print(x)
import os
print('json size KB', round(os.path.getsize(OUT) / 1024))
