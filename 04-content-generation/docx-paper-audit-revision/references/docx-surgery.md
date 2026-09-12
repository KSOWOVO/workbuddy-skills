# DOCX 精准手术手册

paper 类 docx 的文本是**分散在多个 run** 里的，直接 `run.text = new` 或整段重写会丢格式。
下面是实测可用的三个手法。

---

## 1. 跨 run 安全替换（保留原有格式）

把一个可能横跨多个 run 的字符串替换掉，**格式沿用第一个命中 run**。

```python
def replace_in_para(p, old, new):
    """在段落 p 里把 old 换成 new，跨 run 安全，保留首 run 格式。"""
    runs = p.runs
    full = ''.join(r.text for r in runs)
    idx = full.find(old)
    if idx < 0:
        return False
    pos = 0
    sr = er = so = eo = None
    for i, r in enumerate(runs):
        L = len(r.text)
        if sr is None and pos + L > idx:
            sr, so = i, idx - pos
        if pos + L >= idx + len(old):
            er, eo = i, idx + len(old) - pos
            break
        pos += L
    if sr is None or er is None:
        return False
    head, tail = runs[sr].text[:so], runs[er].text[eo:]
    if sr == er:
        runs[sr].text = head + new + tail
    else:
        runs[sr].text = head + new
        for k in range(sr + 1, er):
            runs[k].text = ''
        runs[er].text = tail
    return True
```

**用法要点**
- 优先用**唯一长锚点**（含足够上下文），避免命中错位置。
- 同一句在多段重复时（如 7 段收尾同句），改用**段落索引定位**：
  `d.paragraphs[31]` 直接取第 31 段再替换 —— 比字符串定位可靠。
  （注意：先前的改动若没增删段落，索引是稳定的；增删过就必须重新取索引。）
- 收尾自检：改完打印被改段落全文 + 打印 `len(d.paragraphs) / len(d.tables) / len(d.inline_shapes)`，
  确认没丢段丢表。

### ⚠️ 别用"整段 collapse"！会吃掉局部格式（实测踩坑）

偷懒做法 `p.runs[0].text = ''.join(r.text for r in p.runs); 其余 run 清空`
会**把整段并成一个 run**，段落里任何**局部加粗/字号**都丢失。
真实事故：摘要段原本是 `run0="摘  要："(加粗) + run1=正文(不加粗)`，
collapse 后**整篇摘要变粗体**。

**改文本前先查 run 结构**：

```python
def sig(p):
    return [(r.font.size.pt if r.font.size else None, bool(r.font.bold), r.font.name)
            for r in p.runs]
# 单 run 段 → collapse 安全；多格式段 → 必须用上面的 replace_in_para
```

**已 collapse 后的还原**（两 run 情形）：

```python
import copy
from docx.text.run import Run
r0 = p.runs[0]; full = r0.text
k = full.index('：') + 1                  # 按实际分隔点切
r0.text = full[:k]                        # 保留加粗 rPr
el = copy.deepcopy(r0._r); r0._r.addnext(el)
nr = Run(el, p); nr.text = full[k:]; nr.font.bold = False
```

### 收尾必做的"格式签名"全量比对

改完不要只看文字 diff —— **逐段比 run 格式签名**，才能抓出被吃掉的局部格式：

```python
def sig(p): return set((r.font.size.pt if r.font.size else None, bool(r.font.bold), r.font.name) for r in p.runs)
bad = [i for i in range(min(len(orig.paragraphs), len(new.paragraphs)))
       if sig(orig.paragraphs[i]) != sig(new.paragraphs[i])]
print('格式变化段:', bad)   # 只有"原空段填入新内容"一类才是正常的
```

---

## 2. 替换 docx 内嵌图片（换外部 PNG 没用！）

`docx` 是 zip。图存在 **`word/media/imageX.png`**，正文通过
`<a:blip r:embed="rId9"/>` + `<wp:extent cx cy>` 引用。

**只覆盖磁盘上的 PNG 文件，Word 里看到的还是旧图** —— 必须替换包内字节。

```python
import zipfile, os, hashlib

def swap_docx_image(DOCX, NEWPNG, target='word/media/image1.png',
                    cx=None, cy=None):
    new = open(NEWPNG, 'rb').read()
    z = zipfile.ZipFile(DOCX)
    doc = z.read('word/document.xml').decode('utf-8')

    # ① 若新图宽高比与原图不同，必须同步改 extent，否则图被压扁
    if cx and cy:
        import re
        doc = re.sub(r'<wp:extent cx="\d+" cy="\d+"/>',
                     f'<wp:extent cx="{cx}" cy="{cy}"/>', doc)
        doc = re.sub(r'<a:ext cx="\d+" cy="\d+"/>',
                     f'<a:ext cx="{cx}" cy="{cy}"/>', doc)

    tmp = DOCX + '.tmp'
    zo = zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED)
    for it in z.infolist():
        data = z.read(it.filename)
        if it.filename == target:
            data = new
        if it.filename == 'word/document.xml':
            data = doc.encode('utf-8')
        zo.writestr(it, data)
    zo.close(); z.close()

    # ② Windows 上 os.replace 常被占用而报 WinError 5 → 就地写字节
    with open(DOCX, 'r+b') as f:
        f.write(open(tmp, 'rb').read())
        f.truncate()
    os.remove(tmp)

    # ③ 校验：包内图 md5 必须等于新图 md5
    zz = zipfile.ZipFile(DOCX)
    assert hashlib.md5(zz.read(target)).hexdigest() == hashlib.md5(new).hexdigest()
    assert zz.testzip() is None
```

**cy 怎么算**：`cy = round(cx * 图高 / 图宽)`。EMU 单位。
例：cx=5256000（=13.89cm 版心宽），原图 1635×1110 → cy = 5256000×1110/1635 ≈ 3568294。

**画布尺寸**：如果用户要求的图是"照原图重绘"，先 `Image.open()` 读出原图
`(W,H)`，新图画布**必须同尺寸**，并用像素级坐标对齐（可用 `cv2` 找连通域反推每个
矩形框的 x/y/w/h，再回填重绘脚本）。这样换进去才不会错位。

---

## 3. 中文路径读图（cv2 会失败）

`cv2.imread('C:/中文路径/x.png')` 在 Windows 返回 None。用 PIL 中转：

```python
import numpy as np, cv2
from PIL import Image

def imread_unicode(path):
    return cv2.cvtColor(np.array(Image.open(path).convert('RGB')), cv2.COLOR_RGB2BGR)
```

---

## 4. 环境坑（本机实测）

| 坑 | 现象 | 对策 |
|---|---|---|
| bash PATH 损坏 | `ls` / `grep` / `head` / `tail` 全 `command not found` | 一切改用绝对路径调 managed Python；列目录用 `os.listdir` |
| 覆盖 docx | `PermissionError WinError 5`（杀软/索引占用） | `open(path,'r+b')` 就地写 + `truncate()`，别用 `os.replace` |
| 代理阻断下载 | sci-hub 502 / AIS / ResearchGate / JSTOR 拦截 | 如实标注"未获全文"，不编造引语；让用户决定保留或降级 |
| 统计文件写作 | 写 `.md` 时中文引号可能被转为直引号 | 落 docx 前检查引号；必要时后置转换脚本 |

---

## 5. 审计用的批量提取模板

```python
import docx
d = docx.Document(DOCX)
ps = [p.text for p in d.paragraphs]

# 找参考文献起点
start = next(i for i, t in enumerate(ps) if t.strip().startswith('参考文献'))
body, refs = '\n'.join(ps[:start]), '\n'.join(ps[start:])

# 孤儿文献检测：文献表里每条的姓氏，是否在正文出现
# 幻影引用检测：正文 (作者，年份) 是否在文献表出现
```

AI 味词频对比：

```python
markers = ['其一','其二','其三','值得注意的是','据此','换言之','综上所述',
           '首先','其次','最后','赋能','彰显','颇具','靶点','标尺','黑箱']
for m in markers:
    print(m, '本文', body.count(m), '母版', base_paper_text.count(m))
# 判定：本文 > 0 且 母版 == 0  →  AI 指纹
#       本文 ≈ 母版            →  正常，别动
```

### ⚠️ "母版 0 次"必须实测，不能假设（实测踩坑）

不要凭印象判断某个词是"AI 指纹"。**逐词数母版**再下结论。反例：
- 一度以为 `上述` 是 AI 腔 → 实测**母版「上述」= 1 次**（论文 7 次），并非指纹；
  而 `以上` **母版 = 0 次** → 把"上述"改成"以上"是**改错了方向**。
- `分析`、`维度`、`系统`、`机制`、`赋能` 母版都高频 → 属正常学术词，别动。
- 数据类论文里 `表明/显示/说明` 母版大概率 0 次（母版无数据），**不能照搬清零** ——
  它们是指标陈述的必需动词，只需**避免单调**（拆到"可见/反映出/印证/说明"混用，母版用 `可见`）。
- `情境/相对/充分` 这类常用学术词，母版 0 次也多因**题材差异**，硬改会变翻译腔 → **过犹不及，宁可不改**。

**判据**：只有"AI 套话型"词（`本文`、`这一X`、`值得注意的是`、`双重/并行/着力`、
`尤为关键`、`也就是说`、`总体来看`、`再次`）才是真指纹；体裁必需的实词不算。
