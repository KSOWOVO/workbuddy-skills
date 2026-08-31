---
name: skill-github-backup
description: 把用户自创 skill 自动同步备份到 GitHub 公开仓库（KSOWOVO/workbuddy-skills）。每当新增/更新一个 agent_created 的自创 skill 后、或用户提到 skill 备份/开源/同步/上 GitHub 时使用。包含首次搭建（建仓+配 remote）与日常同步（精准 add→commit→push）完整流程，以及已踩过的坑（连接器只读、.gitignore 匹配、PAT 明文风险、push 超时）。
agent_created: true
---

# Skill 云端备份（GitHub 开源仓库）

## 目标仓库
- GitHub 账号：`KSOWOVO`
- 仓库：`KSOWOVO/workbuddy-skills`（**public**）→ https://github.com/KSOWOVO/workbuddy-skills
- 本地位置：`~/.workbuddy/skills`（已 git init，分支 `main`，remote 已配）

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
- 本机默认无任何 GitHub 凭证（无 credential helper / .git-credentials / env token），别指望复用。
- `.gitignore` 匹配坑：内部迁移文件实际是下划线开头 `_bm_skillid_migration.json`，只写 `.bm_skillid_migration.json`（点开头）匹配不到，必须补 `*_migration.json`。
- PAT 若明文出现在聊天记录，完成后**提醒用户去 GitHub 删除重生成**；删除后 remote 里 token 失效，需重新配 remote 或更新 .git/config（也可改用 credential 方式）。
- 检查自创 skill 目录时注意嵌套结构（如 `browser-ocr/browser-ocr/`），find 用 `-name SKILL.md` 从根找。
