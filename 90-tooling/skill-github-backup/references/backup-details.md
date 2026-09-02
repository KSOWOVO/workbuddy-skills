# GitHub 备份：验证仓库、API 备用通道、首次搭建、已踩过的坑

> 从 SKILL.md 拆出的细节章节，仅在需要时读取。

## 如何验证仓库是否真的存在（重要，别被误导）
⚠️ **不要用本机 curl 访问 github.com 网页来验证**——本机网络访问 github.com 网页不通：走代理 `127.0.0.1:4718` 返回 **502 Bad Gateway**，直连返回 **000 连不上**。会误判成 404。但 `api.github.com` 通（200）、git push 也通（网络路径不同）。
正确的两种验证方式：
1. **API**（本机可直连）：
   - 仓库信息 `curl -s -H "Authorization: Bearer $GH_TOKEN" https://api.github.com/repos/KSOWOVO/workbuddy-skills`（看 visibility / default_branch）
   - 文件列表 `.../contents/` 及子目录 `.../contents/<skill名>`
2. **远程抓取**：用 WebFetch 打开 `https://github.com/KSOWOVO/workbuddy-skills`（走另一条网络路径，能拿到真实页面，含 commit 历史与文件树）。

用户若在浏览器里看到 404，那是**本机网络环境问题，不是仓库问题**——建议换网络（手机热点）/用手机看，或让他打开 API 链接验证：`https://api.github.com/repos/KSOWOVO/workbuddy-skills`。

## 备用通道：git push 报 502 时改用 API 直连（已验证可用）
现象：本机代理 `127.0.0.1:4718` 对 `github.com:443` **时好时坏**，git push 会偶发失败：
`fatal: unable to access 'https://github.com/...': CONNECT tunnel failed, response 502`
（此时 `api.github.com` 往往仍是 200，可走 API 绕过。）

操作步骤：
1. `GET /repos/KSOWOVO/workbuddy-skills/contents/<文件路径>` 取 `sha`
2. 本地文件 base64 编码
3. `PUT /repos/KSOWOVO/workbuddy-skills/contents/<文件路径>`，body = `{message, content, sha}`

关键坑（与 ima COS 上传同源）：**python urllib 在本机会读环境变量代理导致失败**，必须
- 脚本内 `urllib.request.build_opener(urllib.request.ProxyHandler({}))` 显式禁代理直连
- 运行时加 `env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY ...`
- 临时脚本含 token，用完立即 `rm -f` 删掉

推完后**必须对齐本地 git 历史**（否则分叉）：
```bash
cd ~/.workbuddy/skills
git fetch origin main
git reset --soft FETCH_HEAD   # 用 FETCH_HEAD，origin/main 可能报 unknown revision
```
⚠️ 若 API 推送后 **git fetch 也因网络 502 失败**（本地 HEAD 与云端 hash 不一致），**下次同步前必须先补一次 fetch+reset 对齐**，否则 `git push` 会报 non-fast-forward 被拒。可先记录待办，网络恢复后第一时间执行。
**目录重组（分类整理）若 git push 持续失败**：可用 GitHub Contents API 全量同步——`GET /git/trees/main?recursive=1` 拿云端文件+sha → 对旧路径逐个 `DELETE`（body 带 sha）→ 对本地 HEAD 新路径逐个 `PUT`（`git ls-tree -r HEAD` + `cat-file` 取内容 base64，blob sha 相同则跳过）→ 全部成功后 fetch+reset 对齐本地。

## 首次搭建 / 换新机器（备用）
1. 需要用户提供 GitHub PAT（**repo** 权限，勾 classic token）。
2. 验证 + 建仓（API 直连，不用 MCP 连接器）：
```bash
export GH_TOKEN="<PAT>"
curl -s -H "Authorization: Bearer $GH_TOKEN" https://api.github.com/user   # 验证
curl -s -X POST -H "Authorization: Bearer $GH_TOKEN" -H "Accept: application/vnd.github+json" \
  https://api.github.com/user/repos \
  -d '{"name":"workbuddy-skills","description":"WorkBuddy 用户自定义 skill 备份与开源仓库（自动同步）","private":false}'
```
3. 配 remote（token 存于 .git/config，本地安全）：
```bash
cd ~/.workbuddy/skills && git init && git branch -m main
git remote add origin "https://x-access-token:<PAT>@github.com/KSOWOVO/workbuddy-skills.git"
git push -u origin main
```

## 已踩过的坑（务必记住）
- **WorkBuddy 的 GitHub MCP 连接器是只读受限 integration**：create_repository / push_files / 搜索仓库全被 GitHub 403/Validation Failed 拒绝，**不能用于建仓或推送**。别浪费时间，直接走「本地 git + API + PAT」。
- 本机初始无任何 GitHub 凭证，但用户选 manager 后 GCM 会把 token 存进 **Windows 凭据管理器**（控制面板→凭据管理器可见 `git:https://github.com`）。remote URL 带 token 与凭据管理器**双重保险**，任一可用即零弹窗。
- `.gitignore` 匹配坑：内部迁移文件实际是下划线开头 `_bm_skillid_migration.json`，只写 `.bm_skillid_migration.json`（点开头）匹配不到，必须补 `*_migration.json`。
- PAT 若明文出现在聊天记录，完成后**提醒用户去 GitHub 删除重生成**；删除后 remote 里 token 失效，需重新配 remote 或更新 .git/config（**删了 token 记得回来改 remote**）。
- 检查自创 skill 目录时注意嵌套结构（如 `browser-ocr/browser-ocr/`），find 用 `-name SKILL.md` 从根找。
- **⚠️ 不要用 `printf ... | git credential approve`**：本机非交互环境下 GCM 会弹 UI 死等，命令挂起直到被 SIGTERM kill。想把 token 交给 credential manager 也别走这条路。
- **⚠️ Windows 弹 "select a credential helper" 弹窗的根因（2026-09-01 实测）**：WorkBuddy 自带的 PortableGit 在**系统级** `etc/gitconfig` 写死 `credential.helper=helper-selector`，它每次都会弹窗让你选 manager/wincred/none。用户选了 manager 只写进**用户级** `~/.gitconfig`，系统级的 selector 还在 → 两者叠加，照弹。
  **正确修复（不要走弯路）**：
  1. 删系统级 selector：`git config --system --unset-all credential.helper`。若报 `could not lock config file`，是之前操作残留了空的 `gitconfig.lock`，`rm -f <PortableGit>/etc/gitconfig.lock` 后重试。
  2. 用户级保留 `credential.helper=git-credential-manager.exe`（用户选 manager 时已写入）即可。
  3. remote URL 带 token 作**双保险**（URL 自带凭证时 git 不触发 helper，绝对不弹窗）。
  4. 验证：`GIT_TERMINAL_PROMPT=0 GCM_INTERACTIVE=never git fetch origin` 应直接到网络层；报网络 TLS 错（本机代理间歇断连）不是弹窗，是网络问题。
  ❌ **不要** `git config --global --unset credential.helper`——这会删掉用户级 manager 选择，反而让弹窗逻辑混乱。
- **用户对「自动外发」敏感**：曾中途叫停同步。涉及 push/上传类操作，先确认再执行，别默默后台推；被 kill 的 push 可能只推了一半，恢复后务必用 API 验证云端文件列表。
- **⚠️ 本机 Git Bash 怪癖：`env -u ...` 前缀会吞掉 python 的 stdout（2026-09-02 实测）**——`env -u http_proxy ... python script.py` 时，python 的 print 全部不可见（exit 仍 0），连重定向到文件都是空的。所以**「脚本 exit 0 + 无输出」不代表同步成功**；判断成败必须以云端 sha/commits 为准（见下一条），或不用 `env -u`（脚本内部 ProxyHandler({}) 已足够禁代理）。
- **⚠️ api.github.com Contents API 的 GET 有边缘缓存（2026-09-02 实测）**：PUT 推完立即 `GET /contents/<path>` 可能仍返回**旧 sha**（几分钟内），会误判成推送失败。验证时加 cache-bust 参数：`GET /contents/<path>?nocache=$(date +%s)`，或直接 `GET /commits?per_page=3` 看最新 commit message。
- **行尾差异导致 blob sha 与本地不同（正常现象）**：Windows 工作区文件是 CRLF，git 对象是 LF，API 上传的是工作区内容 → 云端 blob sha ≠ 本地 `git ls-files -s` 的 sha（如本地 c1262350…、云端 295625d…），但内容逐字一致。对齐验证以「内容 + commit」为准，不要死等 sha 字面相等；API 推送产生的云端 commit sha 也会与本地不同（fd75683 vs 287db24），属正常。


## ⚠️ 行尾污染：Contents API 上传会绕过 autocrlf（2026-09-02 踩坑）

**现象**：经 Contents API 兜底推送后，云端 blob SHA 与本地 `git hash-object` 对不上。
逐字看内容一模一样，但 `git status` 在网络恢复后会出现**删不掉的幽灵改动**。

**根因**：本机仓库是 100% CRLF（`core.autocrlf=true`）。API 上传时直接发文件原始字节，
**不会**经过 git 的 clean filter 做 CRLF→LF 规范化；而 git 语义下仓库里存的是 LF 版本。
于是云端存了 CRLF blob，本地 git 期望 LF blob，两者 SHA 必然不同。

**判断方法**：
```bash
git hash-object --no-filters <file>   # 原始字节 SHA（=云端 API 上传的）
git hash-object <file>                # 应用 autocrlf 后 SHA（=git 期望的）
# 两者不同 且 前者 == 云端 API 返回的 sha → 确诊行尾污染
```

**正确做法**：上传前取 git 规范化内容，不要直接读文件字节
```bash
git show HEAD:<path>        # 已是 LF 规范化版本，用它 base64 后 PUT
```

**一键校验/修复**（已封装）：
```bash
env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY   "C:/Users/13662/.workbuddy/binaries/python/versions/3.13.12/python.exe"   "C:/Users/13662/.workbuddy/skills/90-tooling/skill-github-backup/scripts/sync_verify.py" [--fix] [--realign -y] [--json]
```
- 默认：逐个比对 git blob SHA，输出「一致 / 行尾差异 / 内容漂移 / 缺失」四类报告
- `--fix`：用 git 规范化内容重推行尾差异的文件
- `--realign -y`：网络恢复后对齐 git 历史（**仅当 tree 一致才 reset --soft**，否则拒绝）
- 安全策略：覆盖前比对忽略 CR 后的实质内容，**实质不同一律不覆盖**（防误伤其它会话改动）

**历史分叉的处理**：API 直推产生的 commit 不在本地 git 历史里。
对齐时只比较 tree（`git rev-parse HEAD^{tree}` vs `FETCH_HEAD^{tree}`），
tree 一致才 `git reset --soft FETCH_HEAD`（只移动 HEAD，工作区不动，不丢改动）。
注意 `git fetch origin main` 只更新 FETCH_HEAD，不会更新 `refs/remotes/origin/main`，
需要再跑一次 `git fetch origin` 才会刷新 remote-tracking 分支。
