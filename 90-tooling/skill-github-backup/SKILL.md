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

## 目标仓库
- GitHub 账号：`KSOWOVO`
- 仓库：`KSOWOVO/workbuddy-skills`（**public**）→ https://github.com/KSOWOVO/workbuddy-skills
- 本地位置：`~/.workbuddy/skills`（已 git init，分支 `main`，remote = 带 token 的 https URL，无 credential.helper → 零弹窗）
- 仓库结构（按功能域分类，数字前缀保序）：
  ```
  01-browser-automation/   → browser-ocr
  02-knowledge-management/ → ima-knowledge-upload
  03-data-analysis/        → pilot-survey-clean
  90-tooling/              → skill-github-backup（本 skill 自身）
  ```
  `.gitignore` 在根目录。

## 核心原则（不可违反）
1. **只同步 `agent_created: true` 的自创 skill**，不碰系统/市场预装 skill（版权与体积问题）。
2. **绝不用 `git add -A`**，逐目录精准 `git add <skill名>`，防止 token/内部文件混入。
3. 同步前必须**扫敏感文件**：`find <skill目录> -type f | grep -iE "token|secret|credential|\.env|\.json$"`，有则先脱敏或跳过。
4. 仓库 .gitignore 已屏蔽：`.neodata_token`、`*.token`、`*.migration.json`、`*_migration.json`、`.bm_skillid_migration.json` 等。**新增 skill 内部文件若含新的敏感模式，先补 .gitignore 再同步。**
5. **仓库必须保持分类整齐**：每个 skill 放在对应功能域目录（见上方结构）。类别映射：浏览器/网页自动化→`01-browser-automation`；知识库/内容/笔记管理→`02-knowledge-management`；数据/问卷/分析→`03-data-analysis`；工具/基础设施/自身→`90-tooling`；其他领域用 `10-`、`20-`… 两位数前缀新建。**同步前先检查 skill 是否在正确分类目录，不在则 `git mv` 过去；新增 skill 按功能选/建分类。** 别让目录扁平堆在一起。
6. **修改即覆盖**：对已有 skill 的修改，直接 `git add <分类/技能目录>` + commit + push，git 自动覆盖云端旧版（不用删旧目录、不用建副本）。新建 skill 同理精准 add 该目录即可。

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
脚本自动完成：扫敏感 → 精准 add+commit → git push（502 自动重试 5 次）→ 全部失败走 api.github.com 兜底 → 最终验证云端 HEAD=本地 HEAD。**用户看不到任何 502/待办/遗留项。**

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
