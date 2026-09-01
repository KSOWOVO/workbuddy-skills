---
name: skill-github-backup
description: 把用户自创 skill 自动同步备份到 GitHub 公开仓库（KSOWOVO/workbuddy-skills）。每当新增/更新一个 agent_created 的自创 skill 后、或用户提到 skill 备份/开源/同步/上 GitHub 时使用。包含首次搭建（建仓+配 remote）与日常同步（精准 add→commit→push）完整流程，以及已踩过的坑（连接器只读、.gitignore 匹配、PAT 明文风险、push 超时）。
agent_created: true
---

# Skill 云端备份（GitHub 开源仓库）

## 目标仓库
- GitHub 账号：`KSOWOVO`
- 仓库：`KSOWOVO/workbuddy-skills`（**public**）→ https://github.com/KSOWOVO/workbuddy-skills
- 本地位置：`~/.workbuddy/skills`（已 git init，分支 `main`，remote = 带 token 的 https URL，无 credential.helper → 零弹窗）
- 云端现有：`.gitignore` + `browser-ocr` / `ima-knowledge-upload` / `pilot-survey-clean` / `skill-github-backup`（本 skill 自身）

## 核心原则（不可违反）
1. **只同步 `agent_created: true` 的自创 skill**，不碰系统/市场预装 skill（版权与体积问题）。
2. **绝不用 `git add -A`**，逐目录精准 `git add <skill名>`，防止 token/内部文件混入。
3. 同步前必须**扫敏感文件**：`find <skill目录> -type f | grep -iE "token|secret|credential|\.env|\.json$"`，有则先脱敏或跳过。
4. 仓库 .gitignore 已屏蔽：`.neodata_token`、`*.token`、`*.migration.json`、`*_migration.json`、`.bm_skillid_migration.json` 等。**新增 skill 内部文件若含新的敏感模式，先补 .gitignore 再同步。**

## 日常同步流程（每新增/更新自创 skill 后执行）
```bash
cd ~/.workbuddy/skills
# 1. 确认该 skill 是自创的（SKILL.md frontmatter 有 agent_created: true）
# 2. 扫敏感文件（有则处理，无则继续）
find <skill名> -type f | grep -iE "token|secret|credential|\.env|\.json$"
# 3. 精准暂存 + 提交 + 推送
git add <skill名>
git commit -m "feat: sync skill <skill名>"
git push
```
- push 慢/超时：用后台跑（run_in_background），完成后用 API 验证云端文件：
  `curl -s -H "Authorization: Bearer $GH_TOKEN" https://api.github.com/repos/KSOWOVO/workbuddy-skills/contents/`
- 网络慢时 push 可能 SIGTERM：重试即可，commit 已成功不受影响。

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
