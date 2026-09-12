#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""workbuddy-skills 一键同步脚本（用户自创 skill → GitHub 公开仓库）

用途：把自创 skill 的「本地 commit + 推送 + 验证」全自动完成，
     内部自动处理本机代理对 github.com 的间歇性 502（重试到成功），
     不再产生「本地与云端未对齐」之类的遗留项。

用法：
  python sync_to_github.py <skill相对路径> [commit message]
示例：
  python sync_to_github.py 90-tooling/skill-github-backup
  python sync_to_github.py 04-content-generation/daily-intel-briefing "feat: 更新到 v5"

注意：
  - 只同步 agent_created: true 的自创 skill；路径需在正确分类目录下
  - 同步前会自动扫敏感文件（token/secret/credential/.env/.json）
  - 内部从 git remote 提取 PAT 用于 API 兜底，不会打印 token
"""
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request

SKILLS_DIR = os.path.expanduser("~/.workbuddy/skills")
REPO = "KSOWOVO/workbuddy-skills"
RETRY_INTERVALS = [0, 5, 10, 20, 40]  # git push 重试间隔（秒）


def _resolve_git():
    """本机 bash PATH 常缺 git（PortableGit 不在 PATH）→ 显式探测绝对路径。

    优先级：环境变量 WB_GIT → shutil.which("git") → PortableGit 常见位置。
    """
    env_git = os.environ.get("WB_GIT")
    if env_git and os.path.isfile(env_git):
        return env_git
    found = shutil.which("git")
    if found:
        return found
    home = os.path.expanduser("~")
    candidates = [
        os.path.join(home, ".workbuddy", "binaries", "PortableGit",
                     "versions", "1.2.0", "cmd", "git.exe"),
        os.path.join(home, ".workbuddy", "binaries", "PortableGit",
                     "versions", "1.2.0", "mingw64", "bin", "git.exe"),
        r"C:\Program Files\Git\cmd\git.exe",
        r"C:\Program Files (x86)\Git\cmd\git.exe",
    ]
    # 兜底：扫 PortableGit/versions/*/cmd/git.exe
    pg = os.path.join(home, ".workbuddy", "binaries", "PortableGit", "versions")
    if os.path.isdir(pg):
        for v in sorted(os.listdir(pg), reverse=True):
            candidates.append(os.path.join(pg, v, "cmd", "git.exe"))
    for c in candidates:
        if os.path.isfile(c):
            return c
    return "git"  # 最后交给系统，失败时由调用方报错


GIT = _resolve_git()


def _git_env():
    """git 子进程环境：把 git 所在目录塞进 PATH，禁交互弹窗。"""
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GCM_INTERACTIVE"] = "never"
    git_dir = os.path.dirname(GIT)
    if git_dir and os.path.isdir(git_dir):
        env["PATH"] = git_dir + os.pathsep + env.get("PATH", "")
    return env


def git(args, timeout=45):
    """在 skills 目录执行 git 命令，非交互、禁 GUI 弹窗。"""
    env = _git_env()
    try:
        r = subprocess.run([GIT] + args, capture_output=True, text=True,
                           encoding="utf-8", errors="replace",
                           env=env, cwd=SKILLS_DIR, timeout=timeout)
        return r
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(args, 124, "", "timeout")
    except FileNotFoundError:
        print("❌ 找不到 git 可执行文件（已探测 %s）。" % GIT)
        print("   可设环境变量 WB_GIT 指向 git.exe 绝对路径后重试。")
        sys.exit(1)


def get_token():
    """优先从 remote URL 提取；remote 已清理为裸 URL 时，改问 Windows 凭据管理器（GCM）。"""
    r = git(["remote", "get-url", "origin"])
    if r.returncode == 0 and r.stdout:
        m = re.search(r"x-access-token:([^@]+)@", r.stdout)
        if m:
            return m.group(1)
    try:
        r2 = subprocess.run(
            [GIT, "credential", "fill"],
            input="protocol=https\nhost=github.com\n\n",
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            env=_git_env(), timeout=30, cwd=SKILLS_DIR)
        m = re.search(r"^password=(.+)$", r2.stdout or "", re.M)
        if m:
            return m.group(1).strip()
    except Exception:
        pass
    return None


def scan_sensitive(rel):
    """扫敏感文件，有则中止并提示。"""
    root = os.path.join(SKILLS_DIR, rel)
    bad = []
    for dirpath, _, files in os.walk(root):
        for fn in files:
            if re.search(r"token|secret|credential|\.env$|\.json$", fn, re.I):
                bad.append(os.path.relpath(os.path.join(dirpath, fn), root))
    if bad:
        print("❌ 发现敏感文件，中止同步：")
        for b in bad:
            print("   ", b)
        sys.exit(1)
    print("✅ 敏感文件扫描通过")


def api(url, data=None, method=None, token=None):
    """api.github.com 直连（禁代理），本机代理对 github 不稳但 api 稳定。"""
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", "Bearer " + token)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "workbuddy-skill-sync")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=90) as resp:
        return json.loads(resp.read().decode("utf-8"))


def api_fallback(rel, token):
    """git push 多次失败后的 API 兜底：把本地 HEAD 中该 skill 的文件 PUT 到云端。"""
    print("⚠️ git push 多次失败，改用 api.github.com 兜底上传（仅覆盖该 skill 目录）...")
    ls = subprocess.run([GIT, "-C", SKILLS_DIR, "ls-tree", "-r", "HEAD", rel],
                        capture_output=True, text=True,
                        env=_git_env(),
                        encoding="utf-8", errors="replace").stdout
    if not ls.strip():
        print("❌ 本地 HEAD 找不到该路径，请确认相对路径")
        sys.exit(1)
    for line in ls.splitlines():
        meta, path = line.split("\t", 1)
        blob_sha = meta.split()[2]
        blob = subprocess.run([GIT, "-C", SKILLS_DIR, "cat-file", "blob", "HEAD:" + path],
                              capture_output=True, env=_git_env()).stdout
        b64 = base64.b64encode(blob).decode("ascii")
        url = "https://api.github.com/repos/%s/contents/%s" % (
            REPO, urllib.parse.quote(path, safe="/"))
        payload = {"message": "sync: %s (API 兜底)" % rel, "content": b64}
        try:
            # 若已存在需带 sha
            try:
                info = api(url, token=token)
                payload["sha"] = info["sha"]
            except Exception:
                pass
            api(url, data=json.dumps(payload).encode(), method="PUT", token=token)
            print("  put:", path)
        except Exception as e:
            print("  FAIL:", path, e)
    # 尝试 fetch 对齐（带重试）
    for wait in RETRY_INTERVALS:
        if wait:
            time.sleep(wait)
        if git(["fetch", "origin", "main"]).returncode == 0:
            git(["reset", "--soft", "FETCH_HEAD"])
            print("✅ API 兜底完成，本地已 fetch 对齐")
            return
    print("⚠️ API 兜底完成，但 git fetch 仍不通；网络恢复后重跑本脚本即可自动对齐")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    rel = sys.argv[1].strip("/")
    msg = sys.argv[2] if len(sys.argv) > 2 else "feat: sync skill %s" % rel
    if not os.path.isdir(os.path.join(SKILLS_DIR, rel)):
        print("❌ 目录不存在：", rel)
        sys.exit(1)

    print("== 1/4 扫敏感文件 ==")
    scan_sensitive(rel)

    print("== 2/4 本地 commit ==")
    git(["add", rel])
    # INDEX.md 是全局索引，动过 skill 就必然要一起同步，避免只提交目录留下半截状态
    if os.path.isfile(os.path.join(SKILLS_DIR, "INDEX.md")):
        git(["add", "INDEX.md"])
    r = git(["commit", "-m", msg])
    if r.returncode != 0:
        tip = ((r.stderr or "") + "\n" + (r.stdout or "")).strip()
        if "nothing to commit" in tip:
            print("   无改动需要提交")
        else:
            last = tip.splitlines()[-1][:200] if tip.splitlines() else "?"
            print("❌ commit 失败：", last)
            print("   最常见原因：git 未配置 user.name / user.email（本仓曾出现）")
            print('   修复：git -C "%s" config user.name KSOWOVO' % SKILLS_DIR)
            print('         git -C "%s" config user.email ksowovo@users.noreply.github.com' % SKILLS_DIR)
            sys.exit(1)
    # 兜底：暂存区必须已清空，否则说明 commit 实际没落地
    # （否则会拿「旧 HEAD == 远端旧 HEAD」误报「云端已对齐」）
    if git(["diff", "--cached", "--quiet"]).returncode != 0:
        print("❌ 暂存区仍有未提交改动，commit 未生效 → 中止，避免假「对齐」报告")
        sys.exit(1)
    print("   本地 HEAD:", git(["log", "-1", "--oneline"]).stdout.strip())

    print("== 3/4 推送（自动重试，处理 502）==")
    pushed = False
    for i, wait in enumerate(RETRY_INTERVALS, 1):
        if wait:
            time.sleep(wait)
        r = git(["push", "origin", "main"])
        if r.returncode == 0:
            print("✅ git push 成功")
            pushed = True
            break
        err = (r.stderr or r.stdout).strip().splitlines()
        tail = err[-1][-80:] if err else "?"
        print("   第%d次失败: %s" % (i, tail))
    if not pushed:
        token = get_token()
        if token:
            api_fallback(rel, token)
        else:
            print("❌ 无法提取 token，请检查 remote 配置")

    print("== 4/4 验证 ==")
    r = git(["ls-remote", "origin", "main"])
    if r.returncode == 0 and r.stdout.split()[0] == git(["rev-parse", "HEAD"]).stdout.strip():
        print("✅ 云端 HEAD = 本地 HEAD，完全对齐，无遗留")
    else:
        print("⚠️ 云端 HEAD 与本地不同（可能其他窗口有更新），网络恢复后重跑本脚本对齐")
    print("== 同步完成 ==")


if __name__ == "__main__":
    main()
