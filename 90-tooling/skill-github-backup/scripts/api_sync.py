# -*- coding: utf-8 -*-
"""
api_sync.py —— 纯 API 同步 skill 到 GitHub（★ 首选通道，不需要代理）

为什么不用 git push：
  实测本机 git push 永远失败 —— 直连时 TLS 握手被墙打断
  （`Failed to connect to github.com:443` / `Connection was reset`），
  挂 127.0.0.1:14146 时 `CONNECT tunnel failed, response 502`。
  而 **api.github.com 直连与挂代理都返回 200**，所以浏览器/API 这条路才是稳的。

原理（Git Data API，等价于一次 git push）：
  1. 本地 git add + commit（纯本地，不联网）
  2. GET 远端 refs/heads/main -> 远端 head
  3. 若远端 == 本地 -> 无事可做
  4. git diff <远端head> <本地head> 得到改动文件清单
  5. 逐个 POST /git/blobs 建 blob（删除的走 sha=null）
  6. POST /git/trees，base_tree = 远端 head 的 tree
  7. POST /git/commits（message + tree + parent=远端head）
  8. PATCH /git/refs/heads/main 指向新 commit
  9. 复核远端 head == 本地 head

用法：
  python api_sync.py                          # 只把已有本地提交推上去
  python api_sync.py <skill目录> [-m "说明"]   # 先 add+commit 再推（自动带 INDEX.md 与 weights.json）
"""
import argparse
import base64
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

OWNER = "KSOWOVO"
REPO = "workbuddy-skills"
BRANCH = "main"
API = "https://api.github.com"
SKILLS_ROOT = os.path.expanduser(r"~\.workbuddy\skills")
# 每次同步都必须一起提交的全局文件
GLOBAL_FILES = ["INDEX.md", "90-tooling/skill-router/weights.json"]

SENSITIVE = re.compile(
    r"token|secret|credential|\.env$|\.neodata_token|_migration\.json$",
    re.I)


def log(*a):
    print(*a, flush=True)


# ---------------- 基础工具 ----------------

def git(*args, check=True):
    r = subprocess.run(["git"] + list(args), cwd=SKILLS_ROOT,
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=180)
    if check and r.returncode != 0:
        raise RuntimeError("git %s 失败: %s" % (" ".join(args),
                                               (r.stderr or "").strip()))
    return (r.stdout or "").strip()


def get_token():
    r = subprocess.run(["git", "credential", "fill"],
                       input="protocol=https\nhost=github.com\n\n",
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace",
                       cwd=SKILLS_ROOT, timeout=30)
    for ln in (r.stdout or "").splitlines():
        if ln.startswith("password="):
            return ln.split("=", 1)[1].strip()
    raise RuntimeError("无法从凭据管理器取到 GitHub token")


def api(method, path, token, body=None, retries=4):
    """调 api.github.com。**刻意不设代理** —— 实测直连就能通。"""
    url = path if path.startswith("http") else API + path
    data = json.dumps(body).encode() if body is not None else None
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, data=data, method=method)
            req.add_header("Authorization", "Bearer " + token)
            req.add_header("Accept", "application/vnd.github+json")
            req.add_header("User-Agent", "wb-api-sync")
            if data:
                req.add_header("Content-Type", "application/json")
            # 显式绕开环境代理：直连 api.github.com 实测可用
            opener = urllib.request.build_opener(
                urllib.request.ProxyHandler({}))
            with opener.open(req, timeout=60) as r:
                raw = r.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = e.read().decode("utf-8", "replace")[:300]
            except Exception:
                pass
            # 4xx 是逻辑错误，重试无意义
            if 400 <= e.code < 500 and e.code not in (408, 429):
                raise RuntimeError("API %s %s -> HTTP %d %s"
                                   % (method, path, e.code, detail))
            last = "HTTP %d %s" % (e.code, detail)
        except Exception as e:
            last = "%s: %s" % (type(e).__name__, e)
        if i < retries - 1:
            time.sleep(2 + i * 2)
    raise RuntimeError("API %s %s 连续失败: %s" % (method, path, last))


def scan_sensitive(paths):
    """只扫准备提交的那些 skill 目录，命中就中止。"""
    bad = []
    for p in paths:
        full = os.path.join(SKILLS_ROOT, p)
        for dp, dirs, fs in os.walk(full):
            if ".git" in dp:
                continue
            for f in fs:
                if SENSITIVE.search(f):
                    bad.append(os.path.relpath(os.path.join(dp, f),
                                               SKILLS_ROOT))
    return bad


# ---------------- 主流程 ----------------

def do_commit(paths, message):
    """本地 add + commit（不联网）"""
    add = list(paths)
    for g in GLOBAL_FILES:
        if os.path.isfile(os.path.join(SKILLS_ROOT, g)):
            add.append(g)
    log("== 本地提交 ==")
    for p in add:
        git("add", p)
    st = git("status", "--porcelain")
    if not st:
        log("   无改动需要提交")
        return False
    git("commit", "-m", message)
    log("   已提交:", git("rev-parse", "--short", "HEAD"), message)
    return True


def push_via_api(token):
    local = git("rev-parse", "HEAD")
    log("\n== 推送（纯 API）==")
    log("   本地 HEAD:", local[:12])

    ref = api("GET", "/repos/%s/%s/git/ref/heads/%s" % (OWNER, REPO, BRANCH),
              token)
    remote = ref["object"]["sha"]
    log("   远端 HEAD:", remote[:12])

    if local == remote:
        log("   ✅ 已一致，无需推送")
        return True

    # 远端 head 必须能在本地解析（否则历史分叉，需要人工处理）
    if subprocess.run(["git", "cat-file", "-t", remote], cwd=SKILLS_ROOT,
                      capture_output=True).returncode != 0:
        raise RuntimeError(
            "远端 %s 在本地不存在 —— 历史分叉，需先 git fetch 对齐" % remote[:12])

    diff = git("diff", "--name-status", remote, local)
    entries = []
    for ln in diff.splitlines():
        parts = ln.split("\t")
        if len(parts) < 2:
            continue
        st, fp = parts[0], parts[-1]
        entries.append((st, fp.replace("\\", "/")))
    log("   改动文件 %d 个" % len(entries))

    tree = []
    for st, fp in entries:
        if st.startswith("D"):
            tree.append({"path": fp, "mode": "100644", "type": "blob",
                         "sha": None})
            continue
        full = os.path.join(SKILLS_ROOT, fp.replace("/", os.sep))
        if not os.path.isfile(full):
            tree.append({"path": fp, "mode": "100644", "type": "blob",
                         "sha": None})
            continue
        content = open(full, "rb").read()
        blob = api("POST", "/repos/%s/%s/git/blobs" % (OWNER, REPO), token,
                   {"content": base64.b64encode(content).decode(),
                    "encoding": "base64"})
        mode = "100755" if fp.endswith(".sh") else "100644"
        tree.append({"path": fp, "mode": mode, "type": "blob",
                     "sha": blob["sha"]})
    log("   已建 blob %d 个" % len(tree))

    new_tree = api("POST", "/repos/%s/%s/git/trees" % (OWNER, REPO), token,
                   {"base_tree": ref["object"]["sha"], "tree": tree})
    commit = api("POST", "/repos/%s/%s/git/commits" % (OWNER, REPO), token,
                 {"message": git("log", "-1", "--format=%s"),
                  "tree": new_tree["sha"], "parents": [remote]})
    api("PATCH", "/repos/%s/%s/git/refs/heads/%s" % (OWNER, REPO, BRANCH),
        token, {"sha": commit["sha"], "force": False})
    log("   新 commit:", commit["sha"][:12])

    # 复核
    time.sleep(1.5)
    ref2 = api("GET", "/repos/%s/%s/git/ref/heads/%s" % (OWNER, REPO, BRANCH),
               token)
    ok = ref2["object"]["sha"] == local
    log("   复核远端:", ref2["object"]["sha"][:12],
        "✅ 一致" if ok else "❌ 不一致")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*", help="要同步的 skill 目录（可多个）")
    ap.add_argument("-m", "--message", default=None, help="提交说明")
    a = ap.parse_args()

    paths = [p.replace("\\", "/").strip("/") for p in a.paths]
    msg = a.message or ("sync: %s" % ", ".join(paths) if paths
                        else "chore: sync")

    if paths:
        bad = scan_sensitive(paths)
        if bad:
            log("❌ 检出敏感文件，已中止：")
            for b in bad:
                log("   ", b)
            return 2
        log("== 敏感扫描 == ✅ 通过")
        do_commit(paths, msg)

    token = get_token()
    ok = push_via_api(token)
    log("\n" + ("✅ 同步完成" if ok else "❌ 同步未完成"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
