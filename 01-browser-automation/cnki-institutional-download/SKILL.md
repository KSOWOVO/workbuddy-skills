---
name: cnki-institutional-download
agent_created: true
summary: 借校园网机构权限，用 Playwright 驱动系统 Edge 批量下载知网文献全文，并逐条复核题录。
description: >
  需要从中国知网（CNKI）批量下载文献全文，或核验中文题录是否准确时使用。
  触发词：知网下载、CNKI、批量下文献、下载全文、查知网、题录核验、这条文献对不对、
  校园网、机构权限、图书馆权限、下不动文献。
  前提：已连校园网（IP 机构认证，**无需账号密码、无验证码**）。
  产出：全文 PDF/CAJ 归档 + 题录复核对照表。技术细节见 references/cnki-playbook.md。
---

# 知网机构权限批量下载与题录复核

## 先判断：到底要不要登录？

**先做这一步，别急着找账号密码。**

打开 `https://www.cnki.net/`，看右上角。**如果显示你学校的名字**（如"广州工商学院"），
说明校园网 IP 已被机构认证 —— **不需要登录、不需要学号密码、通常也不会有验证码**。

只有显示"机构登录"时才需要账号。**优先走 IP 认证路线**：既省事，也避免在对话里传密码。

> 安全提醒：如果用户把账号密码发在聊天里，用完提醒他改密码；**不要把凭据写进任何文件**。

## 技术栈选择（关键）

| 方案 | 评价 |
|---|---|
| `agent-browser` skill | 要下 ~500MB Chromium，慢 |
| **Playwright (Python) + `channel='msedge'`** | ✅ **首选**：pip 装包几秒，直接驱动系统已装的 Edge，不下载浏览器 |

```python
ctx = p.chromium.launch_persistent_context(
    PROFILE_DIR, channel='msedge', headless=False,   # headless=False 让用户能看见
    accept_downloads=True, downloads_path=DL_TMP,
    args=['--disable-blink-features=AutomationControlled'])
```

用 `launch_persistent_context` + 固定 profile 目录：Cookie 与信任标记会累积，
**第二次之后基本不会再触发风控**。

## 六大坑（全部踩过，照抄即可避开）

1. **滑块验证**：全新 profile + 直接拼检索 URL 深跳 → 必触发 `blockPuzzle` 滑块。
   **解法**：先老实打开首页待 4 秒"预热"，再去检索；用养过的 profile。**不要写破解滑块的代码**——
   真出现了就请用户手动滑一次（脚本里做 `wait_captcha()` 等待即可，一次性）。
2. **`expect_download` 会崩**：知网点击下载后常把承载页关掉，`Download.save_as` 报
   `TargetClosedError`。**解法**：用 `downloads_path=<目录>` 让浏览器直接落盘，然后轮询文件系统。
3. **抢太早**：Chrome/Edge 下载中文件名是 `.crdownload`，直接搬走会拿到半截文件。
   **解法**：轮询直到出现**不以 `.crdownload` 结尾**且 >3000 B 的文件。
4. **点下载会让整个 context 死掉**：`li.btn-dlpdf` 在某些刊上会关掉页面。
   **解法**：每篇**独立 `ctx.new_page()`**，外加一个 `about:blank` **保活页**，
   并容忍 `TargetClosedError`（单篇失败不影响后续）。
5. **Windows 非法文件名字符**：标题里的 `" / : * ? < > |` 会让 `save_as` 报
   `OSError: Invalid argument`。**必须 sanitize**：
   `re.sub(r'[\\/:*?"<>|]', '', name)`。
6. **扩展名会骗人**：知网给的 `.caj` 里可能是真 PDF。落地后**查文件头**：
   `%PDF` = PDF，`KDH` = 真 CAJ（需 CAJViewer）。

## 下载按钮选择器（知网 kns8s / kcms2）

| 选择器 | 含义 |
|---|---|
| `li.btn-dlpdf` | PDF 下载 |
| `li.btn-dlcaj` | CAJ 下载 |
| 列表页行内 `下载` | 直接拿 CAJ |

流程：`kns8s/defaultresult/index?kw=<题名>` → 找 `a[href*="kcms2/article/abstract"]` →
进详情页 → `wait_for_selector('li.btn-dlpdf')` → 点 → 等落盘。
**PDF 拿不到就退 CAJ**（有些刊只给 CAJ）。索引类文献（《商展经济》等）可能**不提供任何可下载文件**。

## 题录复核：这才是最权威的验证

**WebSearch 查题录会出错**（实测：AI 生成的 29 条里有 2 条作者姓名是凭空编的、
1 条作者顺序颠倒、1 条年份错 2 年、1 条刊名张冠李戴）。**知网是中文文献的原始数据库，用它复核。**

```python
url = 'https://kns.cnki.net/kns8s/defaultresult/index?kw=' + quote(题名) + '&korder=TI'
```

- **必须加 `&korder=TI`（篇名精确检索）**。默认"主题"检索会发散，返回一堆不相关的硕论。
- 抓结果行文本：`<序号> <题名> <作者;作者> <来源> <发表时间> <类型> …`
- **匹配规则**：优先取"结果行中出现预期作者名"的那条。**光靠题名关键词会撞车**
  （实测 A02 撞到了 A03 那篇）。

## 输出约定

- 全文归档目录 + 一份 `_知网复核.md`：逐条列出「索引登记题录 | 知网返回记录 | 判定」
- 复核结论要**如实标注**哪些是知网直接命中、哪些靠其他一手来源、哪些字段（如起止页码）仍缺

## 参考
- `references/cnki-playbook.md` —— 可直接复用的完整脚本骨架
