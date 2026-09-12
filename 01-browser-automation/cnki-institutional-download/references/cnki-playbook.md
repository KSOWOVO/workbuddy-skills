# 知网批量下载 & 题录复核 · 脚本骨架

复制改路径即可用。路径含中文没问题，但**不要用 `cv2.imwrite`**（写不了中文路径）。

## 1. 批量下载（batch_download.py）

```python
import os, time, re, shutil, urllib.parse
from playwright.sync_api import sync_playwright

PROFILE = r'...\_browser_profile_cnki'      # 持久化 profile，养过一次就不弹验证码
OUTDIR  = r'...\refs_raw\04_原论文24篇_全文'
SHOTDIR = r'...\paper\_cnki_shots'
DL_TMP  = r'...\_dl_tmp'                    # downloads_path 落盘目录

def san(s):                                  # Windows 非法字符
    return re.sub(r'[\\/:*?"<>|]', '', s).strip()

def wait_captcha(pg, max_wait=420):
    """出现滑块就暂停等用户手动完成。max_wait 秒后放弃。"""
    waited, said = 0, False
    while waited < max_wait:
        try:
            t, u = pg.title() or '', pg.url or ''
        except Exception:
            time.sleep(3); waited += 3; continue
        if '安全验证' in t or '/verify' in u:
            if not said:
                print('>>> 请在 Edge 窗口里滑动完成验证 <<<', flush=True); said = True
            time.sleep(4); waited += 4; continue
        return True
    return False

def listing():
    out = {}
    for f in os.listdir(DL_TMP):
        try: out[f] = os.path.getsize(os.path.join(DL_TMP, f))
        except Exception: pass
    return out

def grab(pg, before, outname, timeout_polls=70):
    """点下载 → 等真正落盘 → 搬到 OUTDIR。"""
    for sel in ('li.btn-dlpdf', 'li.btn-dlcaj'):
        try:
            el = pg.query_selector(sel)
        except Exception:
            el = None                 # 页面可能已被关掉
        if not el:
            continue
        try:
            el.click(no_wait_after=True)
        except Exception:
            pass
        for _ in range(timeout_polls):        # 关键：等 .crdownload 消失
            time.sleep(2)
            cur = listing()
            done = [f for f in cur
                    if f not in before and not f.endswith('.crdownload') and cur[f] > 3000]
            if done:
                f = done[0]
                ext = os.path.splitext(f)[1].lower() or '.bin'
                dst = os.path.join(OUTDIR, san(outname) + ext)
                shutil.move(os.path.join(DL_TMP, f), dst)
                return dst
    return None

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        PROFILE, channel='msedge', headless=False,
        viewport={'width': 1440, 'height': 900},
        accept_downloads=True, downloads_path=DL_TMP,
        args=['--disable-blink-features=AutomationControlled'])

    boot = ctx.pages[0] if ctx.pages else ctx.new_page()
    boot.goto('https://www.cnki.net/', wait_until='domcontentloaded', timeout=60000)
    time.sleep(4)                    # ★ 预热，避免触发滑块
    wait_captcha(boot)
    keeper = ctx.new_page(); keeper.goto('about:blank')   # ★ 保活页

    for title, author, outname in TARGETS:
        pg = None
        try:
            pg = ctx.new_page()      # ★ 每篇独立开页
            pg.goto('https://kns.cnki.net/kns8s/defaultresult/index?kw='
                    + urllib.parse.quote(title),
                    wait_until='domcontentloaded', timeout=60000)
            time.sleep(4)
            wait_captcha(pg)

            href = None              # 找详情页链接
            for a in pg.query_selector_all('a'):
                h = a.get_attribute('href') or ''
                if 'kcms2/article/abstract' in h:
                    href = h; break
            if not href:
                continue
            pg.goto(href, wait_until='domcontentloaded', timeout=60000)
            pg.wait_for_selector('li.btn-dlpdf', timeout=25000)

            before = listing()
            got = grab(pg, before, outname)
            print(('OK ' if got else 'X  ') + (got or ''), flush=True)
        except Exception as e:
            print('X', type(e).__name__, str(e)[:80], flush=True)   # 单篇失败不中断
        finally:
            try:
                if pg: pg.close()
            except Exception:
                pass
        time.sleep(3)

    ctx.close()
print('落地文件：')
for f in sorted(os.listdir(OUTDIR)):
    print(' ', f, os.path.getsize(os.path.join(OUTDIR, f)))
```

## 2. 题录复核（verify_titles.py）

```python
# 关键：必须加 &korder=TI（篇名精确检索）；默认"主题"检索会返回一堆不相关硕论
url = ('https://kns.cnki.net/kns8s/defaultresult/index?kw='
       + urllib.parse.quote(题名) + '&korder=TI')

rows = []
for tr in pg.query_selector_all('table tr'):
    tx = re.sub(r'\s+', ' ', tr.inner_text()).strip()
    if len(tx) > 12 and '题名' not in tx[:4]:
        rows.append(tx)          # 形如 "1 题名 作者;作者 来源 2024-04-15 期刊 47 3919 下载 …"

hit = next((r for r in rows if 预期作者 in r), rows[0] if rows else None)
```

**判定要点**：
- 作者名出现在行里 → 强证据
- 只靠题名关键词会撞车（同主题论文很多），必须叠加作者
- 常见作者（温忠麟 / 方杰 / 张民 等）会误命中别的论文 → 改用 `korder=TI` 精确检索

## 3. 落地后自检

```python
head = open(path, 'rb').read(4)
kind = 'PDF' if head[:4] == b'%PDF' else ('CAJ' if head[:3] == b'KDH' else '未知')
```

知网常把 PDF 存成 `.caj` 扩展名（实测《编辑之友》那篇），**以文件头为准**，
并把扩展名改正，否则用户打不开。
