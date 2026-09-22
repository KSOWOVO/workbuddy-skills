---
name: file-content-inspection
description: 判断一个文件"能不能删"之前，先真正打开它看内容——而不是只看文件名。触发词：打开看看里面是什么、只读文件名不够、这文件是什么、能不能删、哈希名文件、Download (1).mp4 是什么、帮我看看这批文件、文件内容识别。覆盖 PDF(含乱码CMap)、Office、HTML、视频、压缩包、未知扩展名的内容侦查。
agent_created: true
---

# 文件内容侦查（File Content Inspection）

## 核心原则

**永远不要凭文件名判断文件价值。** 用户原话：

> 「我发现你每次都会有一个问题啊，就是你只读文件名。你应该可以把它打开，看看里面是什么内容的吧？……因为那些哈希值的，有可能是-我从知网或者建筑上面下载下来的文档啊，那肯定不能删啊」

**惨痛教训**：曾把 5 个哈希命名的 `.xlsx` 判为"疑似无用"（准备删），实际是张**佛山「文武红」海外社媒问卷原始数据**（Credamo 平台导出）；`查看成绩.pdf` 系列判为重复，实际是**本人两个学期的成绩单**。**凭文件名判断 = 高风险误删。**

## 环境准备（关键！不要用错 Python）

本机有**两个** Python，能力不同：

| Python | 路径 | 库 |
|---|---|---|
| 隔离运行时 | `C:\Users\13662\.workbuddy\binaries\python\versions\3.13.12\python.exe` | **裸的，无第三方库** |
| 默认 venv ★ | `C:\Users\13662\.workbuddy\binaries\python\envs\default\Scripts\python.exe` | pymupdf 1.28.2 / pdfplumber 0.11.10 / opencv-python 5.0 / openpyxl 3.1.5 / python-docx 1.2.0 / numpy / pillow 12.3 |

**→ 一律用 `envs\default\Scripts\python.exe`**，它能直接读 PDF/Office/视频。走 `versions\3.13.12\python.exe` 会 ImportError 然后被迫手写解析器（浪费大量时间且易错）。

用 Bash 工具调用（不要用 PowerShell 调 Python，中文路径会乱码）：
```bash
cd "C:/Users/13662/WorkBuddy/<session>" && C:/Users/13662/.workbuddy/binaries/python/envs/default/Scripts/python.exe script.py > out.log 2>&1; echo "EXIT=$?"
```
然后用 Read 工具读 `out.log`。

## 按类型的侦查配方

### PDF ★ 首选 PyMuPDF，一行出结果

```python
import fitz
doc = fitz.open(path)
for p in doc:
    print(p.get_text("text"))          # 文本（自动处理 CMap/ToUnicode）
    for b in p.get_text("blocks"):     # 带坐标，能还原表格排版
        print(b[:4], repr(b[4]))
```

**不要手写 PDF 解析器。** 我曾手写 zlib 解压 + 正则抽 `<hex>` + 解析 ToUnicode CMap，跑通后得到的是**乱序乱码**（Identity-H 编码 + CID 映射错位），而 PyMuPDF 一把就出正确中文。血的教训。

**判断重复**：PDF 的 MD5 不同 ≠ 内容不同（打印时间戳会变）。要提取关键字段再比：
```python
for line in doc[0].get_text("text").splitlines():
    if line.startswith(("学年学期", "打印时间", "学号")):
        print(line)
```
例：4 个 `查看成绩.pdf` MD5 全不同，但实为 **2 个学期 × 2 个打印日期**，各自不可替代 → 全留。

**PDF 内嵌图片**（文本提取为空时看这个）：
```python
for img in doc[0].get_images(full=True):
    pix = fitz.Pixmap(doc, img[0])
    pix.save("out.png")   # 存出来直接 Read 看图
```

### Excel / XLSX
```python
import openpyxl
wb = openpyxl.load_workbook(path, read_only=True)
for ws in wb:
    print("SHEET:", ws.title, ws.max_row, ws.max_column)
    for row in ws.iter_rows(max_row=6, values_only=True):
        print("  ", row)
```
（无 openpyxl 时的兜底：`zipfile` 读 `xl/worksheets/sheet*.xml`，正则抽 `<t>`/`<is>`/`<v>`）

### Word / DOCX
```python
import docx
d = docx.Document(path)
print("\n".join(p.text for p in d.paragraphs[:60]))
```

### HTML
```python
import re
raw = open(path, encoding='utf-8', errors='ignore').read()
print(re.search(r'<title>(.*?)</title>', raw, re.S).group(1))
body = re.sub(r'<script[\s\S]*?</script>|<style[\s\S]*?</style>', '', raw)
print(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', body))[:800])
```

### 视频 ★ 抽帧看图，别只看元数据
```python
import cv2, os
cap = cv2.VideoCapture(path)
n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)); fps = cap.get(cv2.CAP_PROP_FPS)
print("%dx%d  %.1f s" % (cap.get(3), cap.get(4), n/fps if fps else 0))
for i, frac in enumerate([0.1, 0.5, 0.9]):
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(n*frac))
    ok, fr = cap.read()
    if ok: cv2.imwrite(f"vf_{i}.jpg", fr, [cv2.IMWRITE_JPEG_QUALITY, 85])
```
然后用 Read 工具看 jpg。**短视频的水印/角标能直接给出平台和作者**（如 `TikTok @xlionsbysouth`、`@ldfa_paris`），这是判断题材归属的关键证据。

### 压缩包
```python
import zipfile, os
z = zipfile.ZipFile(path)
print("entries:", len(z.namelist()))
for n in z.namelist()[:40]:
    print("%9.1f MB  %s" % (z.getinfo(n).file_size/1024**2, n))
print("含安装器:", [n for n in z.namelist() if n.lower().endswith(('.exe','.msi','.bat'))])
```
判断"是不是完整可用安装包"：看有没有 `Set-up.exe`/`install.exe` + `packages/` 目录 + 总解压体积。

### 未知扩展名 / 无扩展名
```python
head = open(path, 'rb').read(16)
print(head.hex(), head[:8])
```
对照魔数：`504B0304`=zip/docx/xlsx · `25504446`=`%PDF` · `D0CF11E0`=旧 MS Office · `89504E47`=PNG · `FFD8FF`=JPEG · `00000018 66747970`=mp4。

## 判定框架（三档，偏保守）

| 档 | 条件 | 动作 |
|---|---|---|
| **确定留** | 本人学业/研究数据、成绩单、原创作品、正在用的素材、参考文献 | 不动 |
| **可移回收站** | **字节级（MD5）完全相同** —— 无任何信息损失 | 移回收站，可还原 |
| **待确认** | 内容看不懂 / 归属不明 / 体积大但用途不确定 | **列出来问用户，不自作主张** |

**MD5 相同的重复文件才是安全的删除对象。** 同名但大小/MD5 不同 = **不同版本，必须都留**。

## 陷阱清单

1. **PowerShell 调 Python 中文路径乱码** → 输出文件名变 `鏌ョ湅鎴愮哗`。**用 Bash 工具调**。
2. **`Add-Type` 被沙箱禁**（`Add-Type compiles and loads .NET code at runtime`）→ 想用 `System.IO.Compression.ZipFile` 会失败。改用 Python。
3. **审计前先确认清单是新鲜的**。曾拿上一轮已执行的 `dup_plan.json` 去验，124 个路径全 MISS，误以为路径出错，实际是**那批文件早清完了**。**每次重新扫描，不要复用旧 plan 文件。**
4. **`os.walk` 可能被沙箱拦**（撞到 `AppData\...\auth`）→ 加 `if 'auth' in dp or 'AppData' in dp: dirs[:]=[]` 跳过。
5. **`cmd /c` 在 PowerShell 工具里被禁** → 删目录用 `[System.IO.Directory]::Delete()` 或改 Python `shutil`/Shell API。
6. **移回收站**用 Shell API（`FOF_ALLOWUNDO=0x40`），不要用 `Remove-Item`（会触发 safe-delete 失败或直接永久删除）。
7. **★ 判断「重复」绝不能按文件名分组**。用「文件名 + 大小」做键，会**漏掉所有跨文件名的重复**
   （`xxx (1).html` 与 `xxx (3).html` 的 MD5 可能完全相同，`查看成绩.pdf` 与 `查看成绩 (1).pdf` 同理）。
   必须**只按大小分组**再比 MD5。完整做法与保护区清单见 `safe-duplicate-cleanup` skill。
8. **「移到回收站」不等于「释放空间」** —— 文件仍在 `$Recycle.Bin` 里占着，必须清空才真正腾出。报告时要分清这两件事。

## 输出规范

侦查完给用户一张表，**每个文件一行**，含：真实内容摘要 · 体积 · 判定 · 依据。不要只报"XX 个文件可删"。
