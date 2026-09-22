---
name: safe-duplicate-cleanup
description: 安全清理硬盘上的重复文件——扫描真重复、避开程序运行必需的文件、批量移入回收站。触发词：重复文件、去重、删重复、同样的文件存了两份、微信占太多空间、C盘又满了、清理冗余、跨文件名重复、MD5 相同的文件。适用于 Windows，偏保守：绝不永久删除，一律走回收站。
agent_created: true
---

# 安全重复文件清理（Safe Duplicate Cleanup）

## 核心原则

1. **只删字节级（MD5）完全相同的文件** —— 同名但 MD5 不同 = 不同版本，必须都留。
2. **每组至少保留一份** —— 永远不做"删掉全部副本"。
3. **一律走回收站**（`FOF_ALLOWUNDO`），给用户留后悔药。绝不永久删除。
4. **程序运行必需的文件即便重复也不删** —— 见下方保护区清单。
5. **保守**：判断不了就跳过并报告，不要赌。

## ★ 最大的坑：按文件名分组会漏掉一大半重复

**错误写法**（曾长期使用，导致误报"0 组重复"）：
```python
seen[(fn, sz)].append(p)     # 键 = 文件名 + 大小
for k, v in seen.items():
    if len(v) < 2: continue
    # 只对同名文件比 MD5 → 跨文件名重复完全漏掉
```
`code_artifact (1).html` 与 `code_artifact (3).html` **MD5 一模一样**，却因文件名不同从未被分到一组。
`查看成绩.pdf` 与 `查看成绩 (1).pdf` 同理。

**正确写法**：**只按大小分组**，同大小的才比 MD5：
```python
import os, hashlib, collections

def md5(p, bs=1 << 20):
    h = hashlib.md5()
    with open(p, 'rb') as f:
        while True:
            b = f.read(bs)
            if not b: break
            h.update(b)
    return h.hexdigest().upper()

def head(p, n=65536):
    with open(p, 'rb') as f:
        return f.read(n)

by_size = collections.defaultdict(list)
for dp, dn, fns in os.walk(root):
    dn[:] = [d for d in dn if d not in ("AppData", "node_modules", ".git",
                                        "$RECYCLE.BIN", "System Volume Information")]
    for fn in fns:
        p = os.path.join(dp, fn)
        try:
            if os.path.isfile(p):
                sz = os.path.getsize(p)
                if sz: by_size[sz].append(p)
        except Exception:
            pass

groups = []
waste = 0
for sz, paths in by_size.items():
    if len(paths) < 2: continue
    # 快速预筛：前 64KB 相同的才做全量 MD5
    by_head = collections.defaultdict(list)
    for p in paths:
        try: by_head[head(p)].append(p)
        except Exception: pass
    for _, ps in by_head.items():
        if len(ps) < 2: continue
        if sz <= 65536:                      # head 已覆盖全文
            continue_ok = [ps]
        by_hash = collections.defaultdict(list)
        for p in ps:
            try: by_hash[md5(p)].append(p)
            except Exception: pass
        for h, fs in by_hash.items():
            if len(fs) > 1:
                groups.append({'md5': h, 'size': sz, 'files': fs})
                waste += sz * (len(fs) - 1)
```
性能：6.8 万文件全盘扫描约 **10 秒**。64KB 预筛是关键加速手段。

## ★ 第二坑：移到回收站 ≠ 释放空间

`SHFileOperationW` + `FOF_ALLOWUNDO` 只是把文件挪进 `C:\$Recycle.Bin`，**磁盘可用空间不变**。
必须 `Clear-RecycleBin -Force`（或用户手动清空）才真正腾出空间。

→ **先跟用户确认再清空回收站**。清空不可逆。
→ 报告时要分开写：「已移入回收站 X GB」与「清空后实际释放 X GB」。

检查回收站真实占用（注意 `$` 要转义，别在 bash 里被展开）：
```python
rb = "C:/$Recycle.Bin"
for sid in os.listdir(rb):
    sp = os.path.join(rb, sid)
    if os.path.isdir(sp):
        s = sum(os.path.getsize(os.path.join(r, f))
                for r, d, fs in os.walk(sp) for f in fs)
        print(sid, s / 1024**3, "GB")
```

## ★ 绝对保护区 —— MD5 相同也绝不能删

这些看似"重复"，实为程序运行必需，删了会坏事：

| 路径特征 | 是什么 | 删了会怎样 |
|---|---|---|
| `\Battlefield V\settings\PROFSAVE` 与 `PROFSAVE_backup` | 游戏存档及其备份 | 丢存档 |
| `\Rockstar Games\` | GTA 各版本 `metadata.dat` | 游戏数据异常 |
| `*.db-shm` / `*.db-wal` / `*.db-journal` | SQLite 运行时共享内存 | 数据库可能损坏 |
| `\Tencent Files\...\nt_db\` | QQ 数据库 | QQ 数据异常 |
| `\BaiduNetdiskTmp\` | 网盘运行时临时文件 | 下载中断 |
| `\AppData\` 下任何东西 | 程序配置/缓存 | 不确定，一律不碰 |
| `*.lnk` | 快捷方式 | 桌面/开始菜单项失效 |

**判定规则：任一组里有文件落在保护区 → 整组跳过**（不要只删组内的其他成员）。

```python
PROTECT = ["\\Battlefield V\\settings\\", "\\Rockstar Games\\", "\\nt_db\\",
           "\\BaiduNetdiskTmp\\", "\\db_storage\\", "\\Tencent Files\\", "\\AppData\\"]
PROTECT_EXT = (".db", ".db-shm", ".db-wal", ".db-journal",
               ".dat", ".sav", ".lnk", ".sys", ".drv")

def protected(p):
    lp = p.lower()
    return any(s.lower() in lp for s in PROTECT) or p.lower().endswith(PROTECT_EXT)
```

实的踩坑数据：某次全盘 4084 组重复 / 6.44 GB，其中 **3159 组 / 1.08 GB 落在保护区**，
正确跳过后只处理 925 组 / 5.38 GB。

## 保留优先级（决定每组留哪一份）

数字越小越优先保留。核心思想：**保留"用户主动整理过的正式位置"，删掉缓存/自动生成的副本**。

```python
def prio(p):
    if "\\Documents\\大学文件\\" in p:  return 0   # 用户整理的正式文件区
    if "\\Documents\\Obsidian\\" in p:  return 1   # 用户笔记库
    if "\\Desktop\\" in p:              return 2
    if "\\Downloads\\" in p:            return 3
    if "\\Documents\\" in p:            return 4
    if "\\xwechat_files\\" in p:        return 6   # 微信自动存档，优先级最低
    return 5

fs = sorted(g['files'], key=lambda p: (prio(p), len(p), p))
keep, kill = fs[0], fs[1:]
```

**微信 `xwechat_files` 是最常见的重复源**：`msg\file\`、`msg\video\`、`msg\attach\` 会为每份
收发文件自动存档，而用户往往又把它们复制到 Documents 整理 → 双份。
删微信侧副本的副作用：对应聊天记录里点开该文件会显示"已过期"，但**内容不丢**（正式位置有）。

## 批量移入回收站（比逐个快得多）

`SHFileOperationW` 的 `pFrom` 支持**多个路径以 `\0` 分隔**（末尾需双 `\0`）：

```python
import ctypes
from ctypes import wintypes

class SHFILEOPSTRUCTW(ctypes.Structure):
    _fields_ = [("hwnd", wintypes.HWND), ("wFunc", wintypes.UINT),
                ("pFrom", wintypes.LPCWSTR), ("pTo", wintypes.LPCWSTR),
                ("fFlags", ctypes.c_uint16), ("fAnyOperationsAborted", wintypes.BOOL),
                ("hNameMappings", ctypes.c_void_p), ("lpszProgressTitle", wintypes.LPCWSTR)]

FO_DELETE, FOF_ALLOWUNDO = 3, 0x0040
FOF_NOCONFIRMATION, FOF_SILENT, FOF_NOERRORUI = 0x0010, 0x0004, 0x0400
shell32 = ctypes.windll.shell32

def recycle(paths, batch=40):
    """paths: 存在的文件路径列表。返回 (成功数, 失败列表)"""
    ok, fail = 0, []
    for i in range(0, len(paths), batch):
        chunk = [p for p in paths[i:i + batch] if os.path.exists(p)]
        if not chunk: continue
        op = SHFILEOPSTRUCTW()
        op.wFunc = FO_DELETE
        op.pFrom = "\0".join(chunk) + "\0"      # ctypes 会再补一个 \0
        op.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI
        op.fAnyOperationsAborted = False
        rc = shell32.SHFileOperationW(ctypes.byref(op))
        if rc == 0 and not op.fAnyOperationsAborted:
            ok += len(chunk)
        else:                                    # 整批失败则逐个重试，定位具体项
            for p in chunk:
                if not os.path.exists(p): ok += 1; continue
                o2 = SHFILEOPSTRUCTW()
                o2.wFunc = FO_DELETE
                o2.pFrom = p + "\0"
                o2.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI
                rc2 = shell32.SHFileOperationW(ctypes.byref(o2))
                if rc2 == 0: ok += 1
                else: fail.append((rc2, p))
    return ok, fail
```

- **批大小 40** 稳妥（`pFrom` 有 ~32K 字符上限）。
- 实测 1274 个文件耗时 **89 秒**，失败 1 个（被程序占用的缓存文件，`rc=120`）。
- **不要用 `Remove-Item -Recurse`**：会触发 WorkBuddy safe-delete 失败，或直接永久删除。

## 执行流程

1. **扫描** → 按大小分组 + 64KB 预筛 + 全量 MD5
2. **分类统计** → 按目录归属统计组数/可释放量，先给用户看分布
3. **生成计划** → 保护区整组跳过；按 `prio()` 定每组 keeper 与 kill 列表
4. **打印摘要 + 最大的若干组** → 自查数量级是否合理（异常就先别执行）
5. **执行** → `recycle()` 分批
6. **复扫验证** → 重跑扫描，剩余重复应全部落在保护区
7. **报告** → 明确写清：移入回收站多少 GB、**清空回收站才实际释放**、是否有失败项

## 陷阱清单

1. **按文件名分组 = 漏掉跨文件名重复**（见上，最重要）。
2. **移到回收站不释放空间**，必须清空。报告要分清。
3. **`os.walk("C:/$Recycle.Bin")` 在 bash 里 `$` 会被展开** → 写成 `.py` 文件跑，或单引号包住。
4. **不要复用旧的扫描清单**。曾拿上一轮已执行的 `dup_plan.json` 去验证，124 条路径全 MISS，
   误判为路径 bug，实际是那批文件早清完了。**每次重新扫描。**
5. **`Add-Type` 被沙箱禁**，`System.IO.Compression.ZipFile` 用不了；**`cmd /c` 在 PowerShell 工具里被禁**。
6. **必须用 Bash 工具调 Python**（PowerShell 调会让中文路径乱码）；用
   `C:\Users\13662\.workbuddy\binaries\python\envs\default\Scripts\python.exe`（有完整第三方库）。
7. **`~$xxx.docx`** 是 Word 崩溃残留的锁文件，属纯垃圾，可全删（不只留一份）。
8. **同名不同 MD5 = 不同版本**，绝不能当重复删（如 `报告.docx` 与 `报告 (1).docx` 内容不同时）。
