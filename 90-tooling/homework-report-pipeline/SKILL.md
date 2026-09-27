---
name: homework-report-pipeline
description: 把「学生作业/实训报告」做成成品交付的流水线——派小A 写码与文书、填进老师给的 Word 模板、预执行 Jupyter notebook 供用户截图。触发词：实训报告、作业报告、填进模板交作业、帮我做作业、Python 实训、Jupyter 截图、notebook 预执行、答案+截图+解释、doc_replace_text 跨段落报错、insert_markdown 字号不对。适用于：老师给了 Word/Excel 模板 + 一堆题目，需要产出「答案+运行截图+解释+知识点」形式的报告，且代码需在 Jupyter 里跑出截图。
agent_created: true
---

# 作业报告流水线（Word 模板填充 + Notebook 预执行）

## 适用场景

老师给了一份 Word 模板 + N 道题，要求以「**答案 + 运行截图 + 解释 + 知识点梳理**」形式作答，
且截图必须是 Jupyter 界面里带 `In [n]` 标记的运行截图。

**核心洞察**：整份作业只有「截图」必须用户亲手做；代码编写、文书写作、Word 填充、notebook 预执行**全都可以自动化**。

## 分工原则（与「小A 协议」配合）

| 环节 | 谁做 | 说明 |
|---|---|---|
| 代码编写 + 验算 | 小A·**claude**（`claude-sonnet-4-6`），CC 没额度用 GPT | 编程任务才动用 claude/GPT 池 |
| 解释 / 知识点梳理 / 代码注释 | 小A·**gemini**（`gemini-3.8-flash-high`） | 非代码任务**默认 gemini**，额度最多；分批串行 |
| **独立复算 / 审文书 / 核对全部答案** | **小A·gemini** ⭐ | 用户 2026-09-27 明确：「**让小A检查，不要花我们token**」→ 复核也要派出去，别自己啃 |
| 预执行 notebook / 填 Word / 格式还原 / 组装 | **Nova** | 必须在本会话内操作文件（小A 看不到本会话产物） |
| 截图 | **用户**（不可替代） | 截图是「本人操作」的证据 |

> 分工总纲见技能 `nova-xiaoA-collab`；派活技术细节见 `antigravity-headless-bridge`。

### 🔴 核对答案时：让小A **实跑**、不许只靠推理
派活 prompt 里要给本机 Python 路径，并明确要求「凡能用代码验证的都要实际跑一遍」。
本机实测（2026-09-27 全量核对 10 题）：Gemini **66 秒**跑完，**抓到了我自己漏掉的一个真问题**
（第 3 题两问只答了一问）→ 出题人自检容易漏，**外派第二双眼睛很值**。

派活规范见技能 `antigravity-headless-bridge`（单次 ≤10min、串行、后台跑、只看文件落地）。

## 标准流程

### 1. 读模板，把题目落成文件
```bash
# 用 tencent-docs-routing → tencent-local-office-edit 通道
python3 edsdk.py call open_file file_path="<绝对路径>.doc"
python3 edsdk.py call doc_resolve_document_structure --json '{"file_id":"...","mode":"full","limit":0}'
# 内容在表格大单元格里被截断时，用 doc_get_table_info 拿全量文本
```
把题目原文写成 `questions.md`（供数模式：小A 自己读文件，不在 prompt 里复述）。

### 2. 派活给两个模型（串行）
- claude：读 `questions.md` → 写 `code_answers.md`（代码+运行输出+答案，≤130 行）
- gemini：读 `questions.md` + `code_answers.md` → 分批写 `explanations_A/B.md`（解释 2-4 句 + 知识点 3-5 条）
- prompt 里要求「像大二学生自己整理的笔记、不用套话」，防 AI 腔

### 3. 独立复算（必做）
用本地 Python 把每题跑一遍，与 claude 答案逐条比对。**不让小A 自证。**

### 4. 填 Word 模板（**坑最多，见下**）
复制模板副本（原件不动）→ 定位 → 逐题插入 → 统一格式 → 保存。

### 5. 预执行 notebook
```bash
jupyter nbconvert --to notebook --execute --inplace --allow-errors "xxx.ipynb"
```
执行后输出和 `execution_count` 固化进文件，用户打开即见结果，无需逐个 Shift+Enter。

## 🔴 踩过的坑（全部实测）

### doc_replace_text 不能跨段落
```
error: range [a, b) covers a line/paragraph break placeholder at index N;
replacing across newlines is not allowed
```
**解法**：不要整块替换。改为**逐题从后往前 `doc_insert_markdown`**：
- 定位每题的下一题开头坐标（`doc_find`），把上一题的答案块插在那里
- **从最后一题往前插**（Q10→Q1），前面的坐标就不漂移
- `markdown` 参数传 `"file://<绝对路径>.md"` 避免长字符串转义

### insert_markdown 的默认格式 ≠ 模板要求
实测：插入文本默认 **font_size=10.5（五号）+ 西文 Times New Roman**。
若模板要求「宋体 小四（12pt）」→ 必须补两步：
```json
{"ranges": [{"begin": a, "end": b}], "font_size": 12}
{"ranges": [{"begin": a, "end": b}], "font_family": "宋体"}
```
（`font_family` 会同时作用于中西文。用 `doc_get_text_property` 抽查中文位和英文位，两者都要对。）

### nbconvert 遇报错 cell 即中止
题目本身是「报错题」（如 `3*{1,2,3}` → TypeError）时，默认执行会停在那里、**文件不被更新**。
必须加 **`--allow-errors`**，报错信息会照常存进 notebook（正是要的效果）。

### table_id 会变（重要）
保存后重新 `open_file`、或复制文件后，**table_id 全部重新生成**。
❌ 不要复用上一轮的 `table_id`（报 `table_id 'xxx' not found`）
✅ 每次操作前 `doc_list_tables` 重取

### doc_to_image 两个坑
1. 路径含**中文全角括号**（如 `实训报告（一）.doc`）→ `file not found`（英文名副本可绕过）
2. 远端 `docs.qq.com` 转换服务**经常 50000 服务繁忙**，重试无效就跳过——用文本级验证替代

### 题号 ≠ In[n]（用户必问）
第 1 题若只截官网图无代码，则 `In[1]` 是**第 2 题**，整体错位 1。
用户会以为「第 5 题报错了」（其实 In[5] 是第 6 题的报错题）。
**预防**：用 markdown cell 写「## 第N题」做分隔，让用户按标题对号入座。

### 🔴🔴 `#` 注释到底要不要？—— **要！**（2026-09-27 晚用户最终定调，推翻同日早前的相反结论）

**结论演进（别再走回头路）**：
- 早前用户曾说「我们课上没有这么要求，把 `#` 的标注去掉」→ 我当时据此清了注释
- **当天稍后用户改口**：「**`#` 符号解释代码功能**。我看了一下，**你开始是对的呀，他是要解释的**。
  你**回滚回之前的那个版本，就是有井号的版本**。」
- ✅ **最终以"要注释"为准。**

**注释格式（用户给了老师示例截图，必须严格照抄）**：
- 注释**单独占一行、写在代码的下一行**（**不是行内**！）
- `#` 后面**不加空格**，直接跟中文
- 内容是「解释这一行代码的功能」，10~20 字，简明
```python
from math import sin
#从math库中导入sin函数
from math import *
#从math库中导入所有函数，*表示所有
```
**关键技术验证**：代码行后面跟注释行，**Jupyter 照样会显示输出**。
（用 `ast.parse` 验证：最后一个 AST 节点仍是 `Expr`，注释不产生节点，IPython 的 display hook 照常触发。
唯一例外是赋值语句如 `x = zip(...)`，本就无输出。）

**仍然要避免的**：
- markdown 标题只写「## 第N题」，**不要**写「→ 答案：xxx」（像预填答案）
- 不在 notebook 里写「本题答案为报错」「⚠️ 注意」这类讲解（属于报告正文，不属于代码文件）
- 不加 `# 第①步` 这种流水账式教学标注 —— 注释只**解释代码功能**

### 🔴🔴 「上朱庇特」= 交付**预执行好**的 notebook（2026-09-27 用户明确，我走了大弯路）

~~我先后犯的两个错：① 花十几分钟去找 Jupyter 装在哪、反复启服务；② 只交付"代码写好的 notebook"，
让用户自己运行。~~

**用户原话**：「你不用找了呀！……**我直接用 Jupyter 打开它就可以截图了呀**。有这么麻烦吗？
按照之前那个做法来就好了呀」「你还要像这个截图一样，**把运行结果给我**啊，**难道要我自己运行吗**。
反正**我自己运行不了**……**你就直接给我一个完整的文件，我打开它，然后直接截图就好了**」

**✅ 正确交付标准（就两步，没有第三步）**：
1. Nova 在 WorkBuddy 里**把 `.ipynb` 写好，并且预执行完、结果烧进文件**
2. **用户自己**去 Jupyter 打开、截图 ← 打开动作是**用户的**，不是 Nova 的

**🔴 铁律**：
- **不要找 Jupyter、不要启服务、不要探端口** —— 用户有现成的，自己会开
- 用户的 kernel 常常起不来（`Error Starting Kernel: Failed to fetch`），
  **所以"让用户自己跑"这条路根本走不通 → 必须预执行**
- 交付时提醒用户 **F5 刷新**（文件刚被重写，旧标签页是旧内容）

### 🔧 预执行 notebook 的正确做法（已验证）

```python
# 用 Anaconda 的 python 跑（它有 nbclient/nbformat）
import nbformat
from nbclient import NotebookClient
nb = nbformat.read(NB, as_version=4)
NotebookClient(nb, timeout=180, allow_errors=True,
               kernel_name="python3", resources={"metadata": {"path": dir}}).execute()
nbformat.write(nb, NB)
```
- ⚠️ **`allow_errors=True` 必须有**：报错题（如 `3*{1,2,3}`）不加会中断，输出写不进去
- ⚠️ nbformat 读回后 **`cell["source"]` 是 list**，做 `.split("\n")` 前要 `"".join()`
- ⚠️ 复核时确认每格都有 `execution_count`（1,2,3…）+ `outputs`
- 脚本样例：项目内 `_workspace/exec_nb.py`
- 也可用 `jupyter nbconvert --to notebook --execute --inplace --allow-errors`
- **不需要**让 notebook"已信任"：Notebook 7 对未信任 notebook 仍会渲染文本类输出（只 sanitize HTML/JS）

### 🔴 插图与保存（2026-09-27 实操踩坑，全部真实发生）

**1. `doc_find` 返回的 locations 不按文档顺序！**
直接取 `locations[0]` 会拿到**错误的题**（实测把第 1 题的 4 张图插到了第 9 题）。
✅ 必须 `sorted(locs, key=lambda x: x['begin'])` 后再取，或用 `related_text` 里的独特文字（如答案"ABCD"）二次确认。

**2. 清空占位句时范围不能含段落分隔符**
`doc_replace_text` 的 `[begin, end)` 若 end 正好压在段落符上 → 报 `covers a line/paragraph break placeholder`。
✅ 用**不含段落符的完整句串**做范围（如"在此处插入 Jupyter 运行截图（代码 X，输出 Y）。"整句），find 出来的 end 就正好在段落符前。

**3. 文档被 Word/WPS 占用时保存会"假成功"**
`save_file` 返回 `File saved to: ...Temp\...document-save-staging\xxx.doc`，
**原文件根本没变**（大小/时间不变）；显式传 `file_path` 则报 `Export file is occupied`。
✅ 判断方法：比对**文件大小**（带图的报告会显著变大）；处理：请用户关闭 Word/WPS 后重存。
（`~$xxx.doc` 锁定文件是 Word 打开的可靠信号）

**4. `doc_to_image` 远端服务经常整日不可用**
`docs.qq.com/api/v6/slidetools/doc/upload_credential` 可能连续 50000「服务繁忙」，与代理/网络无关。
✅ 不要死磕：放弃视觉终检，改用**结构化验证**——图片数量、每张图所属段落、文字四要素计数、字体字号抽查。

**5. 插图与撤销的正确姿势**
- `doc_insert_image` 每张图占 **1 个字符位**，同段落连续插入可用 `idx+1` 递推
- 插错位置：`doc_list_recent_ai_edits` 拿 version → `doc_undo_ai_edit(target_version=v)` 逐个撤销（实测 4 张图 4 次撤销全部成功，文档恢复原状）
- **不要**用 doc_replace_text 清空整段（会踩坑 2），也用不了"删除图片"工具——错了就撤销重来

### 🔴🔴 模板里「看起来像我生成的」内容，也**绝对不能擅自删**（2026-09-27 血的教训）

**经过**：模板 R6C2 里有一张 7×7 的「角色分工说明」表（A~F 六个角色 + 体力耗时/脑力难度评分）。
内容**看起来像我编的**，我判断"模板里本来没有、是我加的"，就**把它删了**。
结果是**模板原本就有这张表**，用户不得不回来纠正：
「**我超不对 我看到那个原文件的角色分工模板了 那个本来就有的** 你其他做的都很好
把那个**原封不动**的改回去」。

**规则**：
1. **没确证来源之前，不动手删任何模板内容。** 「像我生成的」不等于「是我生成的」——
   老师给的模板里什么奇怪内容都可能有。
2. 删除前先确证：原始模板文件还在不在？表/段落在原模板里的位置是什么？（本次靠把
   `_build_v2.doc` 转成 docx 再解析，才确认该表在「注意…」段之后、「实训过程与实现方法：」段之前）
3. 真删了也能救：从原模板 XML 里把**整个 `<w:tbl>`（含 `tblPr`/`tblGrid`/每行 `tcPr`）**搬回来，
   连前置标题段和前后空段一起搬，才叫"原封不动"；插入后逐格文本比对（本次 7×7 全格 **0 差异**）。

**连带坑：插入 XML 片段后必须补齐命名空间声明**
ElementTree 序列化会写 `ns0:` 前缀 → 要 `replace('ns0:','w:')` 并清掉元素自带的 `xmlns:*`，
**同时检查根标签是否缺声明**（本次缺 `xmlns:wp14`/`wp`/`w10`/`wps`/`a`）→ 缺声明 Word 报 `unbound prefix`。

**连带坑：自动编号（numPr）是隐形的坑**
段落带 `<w:numPr><w:numId w:val="N"/>` 会**自动生成可见编号**（本次一度渲染出"7."）。
- 模板的编号映射：`numId 1→abstractNum 1(japaneseCounting)`、`2→0`、`3→3(decimal, start=2)`、`4→2`
- `numId=1` 错指到 `abstractNumId=2`(decimal start=7) 就会显示成"7."！
- **改 numId 只能改目标段**（用 `x.rfind('<w:p ', 0, pos)` 界定段落范围），否则误伤别的段
- 修完**必须导出 PDF 用文本层核对编号**（Word 里数字是域，XML 里看不见）

### 其他
- `doc_find` 的参数名是 `text`（不是 `query`）
- `get_pool_status` 里若出现 UUID 型 file_id（用户在预览面板打开了文档），**优先用它**——改动用户能实时看到；用路径当 file_id 会报 `document is not open`
- cell 缺 `id` 会报 `MissingIDFieldWarning` → 生成 ipynb 时给每个 cell 写 `id`
- Anaconda 装在非默认路径时，注册表 / PATH / `ls C:\` 都可能查不到 → 直接问用户，或从运行中的进程拿路径
- 本机 `cmd` 不在 Git Bash 的 PATH 里 → 用 `/c/Windows/System32/cmd.exe //c start msedge "url1" ...` 批量开浏览器标签

## 🔴 填「成绩评定」这类小表（2026-09-27 实测）

**用 `doc_set_table_cells`**（batch，一次填多个格）：
```bash
# 参数写 JSON 文件再 --json-file，避免中文引号地狱
python3 edsdk.py call doc_set_table_cells --json-file grade_cells.json
# {"file_id":"...","table_id":"...","cells":[{"row":2,"col":1,"text":"伍凯森"}, ...]}
```
- `row`/`col` 是 **1-based**，与 `doc_get_table_info` 返回的一致
- 只传 `text` 不传 `text_format` → **继承单元格原有格式**（最小改动，推荐）
- 目标表常常是**嵌套表**（如「成绩评定」嵌在「指导教师评阅意见」表里）→ `doc_list_tables` 里能看到，别只数顶层表

### 🔴🔴 最大的坑：`save_file` 会把「真 .doc」偷偷转成「docx 内容 + .doc 扩展名」

- 填表前文件头 `D0 CF 11 E0`（OLE2 真 Word 97-2003）→ `save_file` 后变成 `50 4B 03 04`（ZIP/OOXML）
- Word 仍能打开（按内容嗅探），但**扩展名与真实格式不符**，交作业/超星等平台可能挑刺
- ✅ **修复**：用 Word COM 重新另存为真 .doc
```python
import pythoncom, win32com.client as win32
pythoncom.CoInitialize()
word = win32.DispatchEx("Word.Application"); word.Visible=False; word.DisplayAlerts=0
d = word.Documents.Open(P); d.SaveAs2(P, 0)   # 0 = wdFormatDocument（Word 97-2003 真 .doc）
d.Close(0); word.Quit()
```
- ✅ **验证**：读文件头前 4 字节必须是 `D0 CF 11 E0`；再比对**页数 / 内联图数量 / 图片宽度**与原文件一致
- pywin32 装在隔离 venv：`C:\Users\13662\.workbuddy\binaries\python\envs\default\Scripts\python.exe`

### 用户用 Word 外部编辑后，edsdk 实例会失效
- `get_pool_status` 会显示 `file_path: ""`、`last_saved_ms: -1`；旧 `table_id` 报 `not found`
- ✅ 重新 `open_file`（fresh, `wait=true`）→ `doc_list_tables` **重取 table_id**（内容一变 id 就变）

## 🔧 读低分辨率聊天截图：放大再读（2026-09-27 实测有效）

群聊截图常常只有 400px 宽、字极小，直接读会认错字。用 PIL **放大 4 倍 + 竖向切块**：
```python
from PIL import Image
im = Image.open(src); w, h = im.size
im.resize((w*4, h*4), Image.LANCZOS).save("_big.png")
for i in range(4):
    im.crop((0, h*i//4, w, h*(i+1)//4)).resize((w*4, h//4*4), Image.LANCZOS).save(f"_part{i+1}.png")
```
逐块 Read 就能准确读出「谁选了 A/B/C」。**本机 PIL 可用**（`from PIL import Image` 直接 import）。

## 交付清单（给用户）
1. 填好的 Word 报告（截图位留醒目占位提示）
2. 预执行好的 `.ipynb`（打开即见结果）
3. 逐题代码清单 md（习惯复制粘贴的用户）
4. 小A 用量汇报（模型 / 耗时 / token）
5. 截图清单（每题对应哪张图 + 命名建议）

## 用户待办
装 Jupyter → 打开 ipynb → **F5 刷新**（预执行后必须刷新）→ 逐格截图 → 把图交回贴进 Word。
⚠️ 提醒用户不要点 `Restart & Clear Output`，会清掉已跑好的结果。
