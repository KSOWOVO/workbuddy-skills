---
name: skill-github-backup
agent_created: true
summary: 把自创 skill（agent_created: true）同步备份到 GitHub 公开仓库 KSOWOVO/workbuddy-skills，含一键脚本与 API 兜底通道。
description: >
  新增或更新了自创 skill 后需要备份到 GitHub 时使用，也用于用户提到 skill 备份/开源/同步/上 GitHub。
  仓库：KSOWOVO/workbuddy-skills。只同步 frontmatter 含 agent_created: true 的 skill。
  流程：确认分类目录正确 → 扫敏感文件 → 一键脚本 sync_to_github.py（自动重试 502 + API 兜底）→ 验证云端。
  详细步骤、首次搭建、API 备用通道与踩坑记录见 references/backup-details.md（仅在脚本失败时读取）。
---

# Skill 云端备份（GitHub 开源仓库）

## 🔴 首选通道：纯 API 同步（不用代理，2026-09-22 实测定型）

```bash
"C:/Users/13662/.workbuddy/binaries/python/versions/3.13.12/python.exe" \
  "C:/Users/13662/.workbuddy/skills/90-tooling/skill-github-backup/scripts/api_sync.py" \
  <分类目录>/<skill名> [-m "提交说明"]
```

不带参数就只推送已有本地提交；带目录则先 add+commit 再推（自动带上 `INDEX.md`
与 `90-tooling/skill-router/weights.json`）。

**为什么必须走 API、不能用 git push**（2026-09-22 逐项实测）：

| 通道 | 直连（不挂代理） | 挂 `127.0.0.1:14146` |
|---|---|---|
| `github.com:443` git push | TCP 通但 **TLS 握手被打断**（`Connection was reset`） | **`CONNECT tunnel failed, response 502`** |
| `raw.githubusercontent.com` | ❌ 失败 | 通 |
| **`api.github.com`** | **✅ HTTP 200** | **✅ HTTP 200** |

结论：**`api.github.com` 两条路都通，直连即可用**。所以一切读写都走 Git Data API
（blobs → trees → commits → PATCH ref），等价于一次 git push，**不需要任何代理**。

> ⚠️ **旧文档的坑，别再走回头路**：上一版写「本 shell 通常没有代理环境变量」——
> **已经不对了**。WorkBuddy 现在会注入 `https_proxy=http://127.0.0.1:14146`，
> 而该代理对 git push 返回 502。所以**永远不要依赖 `git push`**，
> `api_sync.py` 内部对 API 请求显式使用 `ProxyHandler({})` 绕开代理。

> ⚠️ **验证不要用 `raw.githubusercontent.com`**（直连失败）。用 Contents API：
> `GET /repos/KSOWOVO/workbuddy-skills/contents/<path>?ref=main`
> 返回的 `content` 是 base64，解出来再比对。`api_sync.py` 的复核就走的这条路。

---

## 目标仓库
- GitHub 账号：`KSOWOVO`
- 仓库：`KSOWOVO/workbuddy-skills`（**public**）→ https://github.com/KSOWOVO/workbuddy-skills
- 本地位置：`~/.workbuddy/skills`（已 git init，分支 `main`）。**认证现状（2026-09-08 更新）**：remote URL 已不含 token（被清理为裸 URL），改由 **Windows 凭据管理器（GCM）自动提供凭据**——git push/fetch 直接可用；**调 GitHub REST API 时用 `printf "protocol=https\nhost=github.com\n\n" | git credential fill | grep '^password=' | cut -d= -f2` 取 token**（40 位 ghp_），不要再从 remote URL 提取（会拿到 URL 本身 → 401）。
- 仓库结构（按功能域分类，数字前缀保序）：
  ```
  01-browser-automation/   → browser-ocr、cnki-institutional-download
  02-knowledge-management/ → ima-knowledge-upload、learning-workbench-sync、obsidian-vault-digest
  03-data-analysis/        → pilot-survey-clean、data-fabrication-audit、survey-forensic-reliability、qdii-quota-check
  04-content-generation/   → daily-intel-briefing、exam-wordbank-workspace、svg-to-animated-gif、
                             survey-to-journal-paper、docx-paper-audit-revision、live2d-texture-restyle
  05-system-utils/         → windows-app-official-download、phone-audio-to-pc
  90-tooling/              → skill-github-backup（本 skill 自身）、skill-router、context-continuity-handoff、
                             skland-endfield-toolkit
  ```
  `.gitignore` 在根目录。**以 `skills/INDEX.md` 与 `git ls-files` 为准，本清单可能滞后于新增分类。**

## 核心原则（不可违反）
1. **只同步 `agent_created: true` 的自创 skill**，不碰系统/市场预装 skill（版权与体积问题）。
2. **绝不用 `git add -A`**，逐目录精准 `git add <skill名>`，防止 token/内部文件混入。
3. 同步前必须**扫敏感文件**：`find <skill目录> -type f | grep -iE "token|secret|credential|\.env|\.json$"`，有则先脱敏或跳过。
4. 仓库 .gitignore 已屏蔽：`.neodata_token`、`*.token`、`*.migration.json`、`*_migration.json`、`.bm_skillid_migration.json` 等。**新增 skill 内部文件若含新的敏感模式，先补 .gitignore 再同步。**
5. **仓库必须保持分类整齐**：每个 skill 放在对应功能域目录（见上方结构）。类别映射：浏览器/网页自动化→`01-browser-automation`；知识库/内容/笔记管理→`02-knowledge-management`；数据/问卷/分析→`03-data-analysis`；**内容生成/写作/插画/日报→`04-content-generation`；系统工具/软件下载/音频→`05-system-utils`**；工具/基础设施/自身→`90-tooling`；其他领域用 `10-`、`20-`… 两位数前缀新建。**同步前先检查 skill 是否在正确分类目录，不在则 `git mv` 过去；新增 skill 按功能选/建分类。** 别让目录扁平堆在一起。
6. **修改即覆盖**：对已有 skill 的修改，直接 `git add <分类/技能目录>` + commit + push，git 自动覆盖云端旧版（不用删旧目录、不用建副本）。新建 skill 同理精准 add 该目录即可。
7. **别漏全局索引文件**（2026-09-13 踩坑固化）：新建/更新 skill 时，除了 skill 目录本身，**`INDEX.md` 和 `90-tooling/skill-router/weights.json` 也必须一起提交**。
   `weights.json` 尤其容易漏——按用户约定，新增 skill 必须在该表里加一个能力域，否则路由**永远命中不到它，skill 等于白做**。
   历史上脚本只 add 了 skill 目录 + INDEX.md，导致 `weights.json` 的注册长期留在本地推不上去（表现为 sync 报"无改动需要提交"但远端缺少注册）。
   **脚本已修**（`sync_to_github.py` 第 2 步现在一并 add 这两个文件）。手动流程时同样别忘 `git add INDEX.md 90-tooling/skill-router/weights.json`。

## 日常同步流程（每新增/更新自创 skill 后执行）

### ⭐ 推荐：一键同步脚本（自动处理 502、自动对齐、不产生遗留项）
```bash
# 用受管 python 跑（禁代理环境变量，与脚本内部禁代理一致）
env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY \
  "C:/Users/13662/.workbuddy/binaries/python/versions/3.13.12/python.exe" \
  ~/.workbuddy/skills/90-tooling/skill-github-backup/scripts/sync_to_github.py \
  <分类目录>/<skill名> ["commit message"]
# 示例：
#   ... sync_to_github.py 90-tooling/skill-github-backup "docs: 更新说明"
```
> ⚠️ **Windows 受管 Bash 环境实证（2026-09-03）**：
> ① `env -u ...` 会**吞掉整个命令的 stdout**（连 `python -c "print('x')"` 都零输出、exit 0）——脚本看起来"什么都没做"其实是正常路径被静音；本 shell 通常没有代理环境变量（`env | grep -i proxy` 为空），**直接去掉 `env -u` 前缀即可**；
> ② 脚本参数**不要用 `~` 开头的 POSIX 路径**——Windows python 会把它解析成 `c:\c\Users\...` 报 No such file；用显式全路径 `"C:/Users/13662/.workbuddy/skills/90-tooling/skill-github-backup/scripts/sync_to_github.py"`。
脚本自动完成：扫敏感 → 精准 add+commit → git push（502 自动重试 5 次）→ 全部失败走 api.github.com 兜底 → 最终验证云端 HEAD=本地 HEAD。**用户看不到任何 502/待办/遗留项。**
> 🔧 **2026-09-11 修的两个脚本 bug**（遇到"进程崩在 `r.stderr` 为 None"/"无法提取 token"先看这里）：
> ① 本机 git 输出**不是 UTF-8**（含 GBK 字节），`text=True` 默认解码会在 reader 线程抛 `UnicodeDecodeError`，导致 `r.stdout/stderr` 变成 `None` → 下一行 `in r.stderr` 抛 `TypeError` 直接崩。**已给所有 `subprocess.run(text=True)` 加 `encoding="utf-8", errors="replace"`，并对 `r.stderr` 做 `or ""` 兜底。**
> ② remote URL 已被清理为裸 URL，旧的"从 remote 正则提取 token"必然返回 None → API 兜底恒失效。**已改为：remote 提取失败时回退 `git credential fill`（`printf "protocol=https\nhost=github.com\n\n"`）解析 `password=`。**
> 🚑 **`.git` 损坏（refs 被删/对象丢失，报 "not a git repository" 但 `.git` 存在）的急救恢复**，
> 以及"`git status` 报大量 M 但字节完全相同 = 假警报"的判定铁律，见 `references/backup-details.md` 末节。
> **铁律：`git status` 说改了 ≠ 真改了，必须用 `git cat-file blob` 二进制字节对质。**

### 手动流程（脚本不可用时）
```bash
cd ~/.workbuddy/skills
# 0. 分类整理（每次都做）：确认 <skill名> 已在正确功能域目录
#    如 browser-ocr 应在 01-browser-automation/，若还在根目录则：
#    mkdir -p <分类目录> && git mv <skill名> <分类目录>/ && rmdir <skill名> 2>/dev/null
# 1. 确认该 skill 是自创的（SKILL.md frontmatter 有 agent_created: true）
# 2. 扫敏感文件（有则处理，无则继续）
find <分类目录>/<skill名> -type f | grep -iE "token|secret|credential|\.env|\.json$"
# 3. 精准暂存（覆盖更新，不加 -A）+ 提交 + 推送
git add <分类目录>/<skill名>
git commit -m "feat: sync skill <分类目录>/<skill名>"
git push    # 502 就多试几次（网络间歇性）
```
- push 慢/超时：用后台跑（run_in_background），完成后用 API 验证云端文件：
  `curl -s -H "Authorization: Bearer $GH_TOKEN" https://api.github.com/repos/KSOWOVO/workbuddy-skills/contents/`
- 网络慢时 push 可能 SIGTERM：重试即可，commit 已成功不受影响。
- ⚠️ **其他窗口也共享此 git 仓库**：别的模型/窗口可能在更新 skill 后放回根目录路径，导致重复。同步前检查 `git ls-files | grep <skill名>` 是否有根目录与分类目录两份，有则 `git rm -f <根目录重复>` 清理后再同步（内容先合并到分类目录）。

- 🚨 **2026-09-16 实测新坑（三条，全部踩过）**：
  1. **API 兜底只覆盖 skill 目录，INDEX.md / weights.json 不会被上传** —— 必须手动 Contents API PUT 补传这两个全局文件（GET 当前 sha → PUT 带 sha + branch main），传完必须 GET 回内容做断言，不能只看 HTTP 200。
  2. **push 报 non-fast-forward ≠ 网络问题**：前一轮被 SIGTERM 的脚本可能已完成 API 兜底 PUT（远端已有 API commit）→ 本地 push 自然被拒。先 `git fetch` 看远端再决定，别盲目重试。
  3. **⚠️ 对 skills 仓库做 `git reset --hard origin/main` 有砸工作区风险**：fetch 与 rev-parse 之间 origin/main 引用可能解析到旧值，且本地工作区历史上就缺大量 tracked 文件 → reset 到旧引用后 9 处文件丢失（含 skill_match.py）。**对齐必须 reset 到 API 查到的具体云端 SHA**（如 f17dae7），不要用 origin/main 引用；reset 前先 `git cat-file -t <sha>` 确认对象在本地。恢复方法：`git reset --hard <云端最新SHA>` 一步找回全部。
