# -*- coding: utf-8 -*-
"""
api_sync.py —— 纯内容比对的 GitHub 同步（★ 首选通道，全程不用代理）

为什么不用 git push（2026-09-22 逐项实测）：
  - 直连：TCP 能连上 github.com:443，但 TLS 握手被墙打断
          （`Failed to connect ... Could not connect to server` / `Connection was reset`）
  - 挂 127.0.0.1:14146：`CONNECT tunnel failed, response 502`
  - 而 **api.github.com 直连与挂代理都返回 200** → 浏览器/API 这条路才是稳的。

★ 为什么按「内容」比对而不是比对 commit sha：
  GitHub 用 API 创建的 commit 是**服务端生成**的，committer/时间戳与本地不同，
  所以 `远端 commit sha != 本地 commit sha` **永远成立**。若拿 sha 当判据，
  每次跑都会以为「有改动」，反复重推。
  因此本脚本用 **git blob sha（纯内容哈希）** 逐文件比对，天然幂等：
  内容一致就什么都不做，改了就只推那几个文件。

流程：
  1.（可选）git add + commit —— 只为本地留存历史，不联网
  2. GET 远端 commit -> 其 tree sha；GET tree?recursive=1 -> {路径: blob sha}
  3. 本地 git ls-files 取跟踪文件，逐个算 blob sha
  4. 求出 新增/修改/删除 的差集
  5. 差集为空 -> 直接结束（幂等）
  6. 逐个 POST /git/blobs 建 blob（删除项 sha=null）
  7. POST /git/trees，base_tree = 远端 **tree sha**（不是 commit sha！）
  8. POST /git/commits（parent = 远端 commit sha）
  9. PATCH /git/refs/heads/main
 10. 复核：重新拉远端 tree，逐文件比 blob sha

用法：
  python api_sync.py                          # 把本地跟踪文件同步到远端
  python api_sync.py <skill目录> [-m "说明"]   # 先 add+commit 再同步（自动带全局索引文件）
  python api_sync.py --check                  # 只比对不推送（干跑）
"""
import argparse
import base64
import hashlib
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
ROOT = r"C:\Users\13662\.workbuddy\skills"
GLOBAL_FILES = ["INDEX.md", "90-tooling/skill-router/weights.json"]
SENSITIVE = re.compile(
    r"token|secret|credential|\.env$|\.neodata_token|_migration\.json$", re.I)

# 预装/市场 skill —— 按本 skill 的核心原则 1「只同步 agent_created 的自创 skill」
# 不应该进公开仓库。这几个此前被误传上去了，这里**只跳过、不删除**
# （删远端要 Kelsen 单独确认，见汇报）。
EXCLUDE_PREFIXES = (
    "ifind-finance-data/", "market-query/", "news-search/",
    "neodata-financial-search/", "westock-data/",
)


def log(*a):
    print(*a, flush=True)


# ---------------- git 辅助 ----------------

def git(*args, check=True, binary=False):
    r = subprocess.run(["git"] + list(args), cwd=ROOT,
                       capture_output=True, text=not binary,
                       encoding=None if binary else "utf-8",
                       errors=None if binary else "replace", timeout=300)
    if check and r.returncode != 0:
        msg = (r.stderr or b"").decode("utf-8", "replace") if binary else (r.stderr or "")
        raise RuntimeError("git %s 失败: %s" % (" ".join(args), msg.strip()))
    return r.stdout


def blob_sha(content: bytes) -> str:
    """git blob 的 sha1：sha1("blob <len>\\0" + content)"""
    h = hashlib.sha1()
    h.update(b"blob %d\x00" % len(content))
    h.update(content)
    return h.hexdigest()


def tracked_files():
    out = git("ls-files", "-z", binary=True)
    return [p.decode("utf-8", "replace") for p in out.split(b"\x00") if p]


def local_state(files):
    """
    返回 ({路径: blob sha}, {路径: 原始字节})

    ★ 必须手算 sha1(原始字节)，**不能用 `git hash-object`**：
      本机 `core.autocrlf = input`，`git hash-object` 会把 CRLF 转成 LF 再算哈希；
      而远端仓库里存的是**原始字节**（早年走 Contents API 上传，绕过了 git 过滤器）。
      实测对照（INDEX.md）：
        远端 tree 的 blob sha  d45d84a2...  == 手算(原始字节) ✅
        `git hash-object`      42b4597a...  ✗ 差
      用 hash-object 会把 4 个内容完全相同的文件误报成「已修改」。
    """
    out_sha, out_raw = {}, {}
    for fp in files:
        full = os.path.join(ROOT, fp.replace("/", os.sep))
        if not os.path.isfile(full):
            continue
        content = open(full, "rb").read()
        out_sha[fp] = blob_sha(content)
        out_raw[fp] = content
    return out_sha, out_raw


def get_token():
    r = subprocess.run(["git", "credential", "fill"],
                       input="protocol=https\nhost=github.com\n\n",
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=ROOT, timeout=30)
    for ln in (r.stdout or "").splitlines():
        if ln.startswith("password="):
            return ln.split("=", 1)[1].strip()
    raise RuntimeError("无法从凭据管理器取到 GitHub token")


def api(method, path, token, body=None, retries=4):
    """调 api.github.com —— 显式 ProxyHandler({}) 绕开环境代理（直连实测可用）"""
    url = path if path.startswith("http") else API + path
    data = json.dumps(body).encode() if body is not None else None
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, data=data, method=method)
            req.add_header("Authorization", "Bearer " + token)
            req.add_header("Accept", "application/vnd.github+json")
            req.add_header("User-Agent", "wb-api-sync")
            if data:
                req.add_header("Content-Type", "application/json")
            with opener.open(req, timeout=60) as r:
                raw = r.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = e.read().decode("utf-8", "replace")[:300]
            except Exception:
                pass
            if 400 <= e.code < 500 and e.code not in (408, 429):
                raise RuntimeError("API %s %s -> HTTP %d %s"
                                   % (method, path, e.code, detail))
            last = "HTTP %d %s" % (e.code, detail)
        except Exception as e:
            last = "%s: %s" % (type(e).__name__, e)
        if i < retries - 1:
            time.sleep(2 + i * 2)
    raise RuntimeError("API %s %s 连续失败: %s" % (method, path, last))


def remote_state(token):
    """返回 (commit_sha, tree_sha, {path: blob_sha})"""
    ref = api("GET", "/repos/%s/%s/git/ref/heads/%s" % (OWNER, REPO, BRANCH),
              token)
    csha = ref["object"]["sha"]
    commit = api("GET", "/repos/%s/%s/git/commits/%s" % (OWNER, REPO, csha),
                 token)
    tsha = commit["tree"]["sha"]
    tree = api("GET", "/repos/%s/%s/git/trees/%s?recursive=1"
               % (OWNER, REPO, tsha), token)
    files = {x["path"]: x["sha"] for x in tree["tree"] if x["type"] == "blob"}
    return csha, tsha, files


def scan_sensitive(paths):
    bad = []
    for p in paths:
        full = os.path.join(ROOT, p)
        for dp, dirs, fs in os.walk(full):
            if ".git" in dp:
                continue
            for f in fs:
                if SENSITIVE.search(f):
                    bad.append(os.path.relpath(os.path.join(dp, f), ROOT))
    return bad


# ---------------- 主流程 ----------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*", help="要同步的 skill 目录（可多个）")
    ap.add_argument("-m", "--message", default=None)
    ap.add_argument("--check", action="store_true", help="只比对，不推送")
    a = ap.parse_args()

    paths = [p.replace("\\", "/").strip("/") for p in a.paths]

    # 1) 本地提交（只为历史留存）
    if paths and not a.check:
        bad = scan_sensitive(paths)
        if bad:
            log("❌ 检出敏感文件，已中止：")
            for b in bad:
                log("   ", b)
            return 2
        log("== 敏感扫描 == ✅ 通过")
        add = list(paths) + [g for g in GLOBAL_FILES
                             if os.path.isfile(os.path.join(ROOT, g))]
        for p in add:
            git("add", p)
        if git("status", "--porcelain").strip():
            git("commit", "-m", a.message or ("sync: %s" % ", ".join(paths)))
            log("   本地提交:", git("rev-parse", "--short", "HEAD").strip())
        else:
            log("   本地无改动需要提交")

    token = get_token()
    log("\n== 比对（按内容）==")
    csha, tsha, rfiles = remote_state(token)
    log("   远端 commit %s / 文件 %d 个" % (csha[:12], len(rfiles)))

    # ★ 用你本机原始字节算 sha1（不能用 git hash-object，见 local_state 注释）
    lfiles_all, lstat_all = local_state(tracked_files())

    def excluded(p):
        return p.startswith(EXCLUDE_PREFIXES)

    lfiles = {p: s for p, s in lfiles_all.items() if not excluded(p)}
    lstat = {p: b for p, b in lstat_all.items() if not excluded(p)}
    rfiles_cmp = {p: s for p, s in rfiles.items() if not excluded(p)}
    n_ex = len(rfiles) - len(rfiles_cmp)
    if n_ex:
        log("   跳过预装 skill 文件 %d 个（不同步也不删除）" % n_ex)

    added = sorted(set(lfiles) - set(rfiles_cmp))
    modified = sorted(p for p in set(lfiles) & set(rfiles_cmp)
                      if lfiles[p] != rfiles_cmp[p])
    deleted = sorted(set(rfiles_cmp) - set(lfiles))
    log("   本地跟踪文件 %d 个" % len(lfiles))
    log("   新增 %d / 修改 %d / 删除 %d"
        % (len(added), len(modified), len(deleted)))

    if not (added or modified or deleted):
        log("   ✅ 远端与本地内容完全一致，无需推送")
        return 0
    for p in (added + modified)[:15]:
        log("     M %s" % p)
    for p in deleted[:10]:
        log("     D %s" % p)
    if len(added) + len(modified) + len(deleted) > 25:
        log("     ...（共 %d 项）" % (len(added) + len(modified) + len(deleted)))

    if a.check:
        log("\n（--check 模式，未推送）")
        return 0

    log("\n== 推送（纯 API）==")
    tree = []
    for p in added + modified:
        blob = api("POST", "/repos/%s/%s/git/blobs" % (OWNER, REPO), token,
                   {"content": base64.b64encode(lstat[p]).decode(),
                    "encoding": "base64"})
        mode = "100755" if p.endswith(".sh") else "100644"
        tree.append({"path": p, "mode": mode, "type": "blob",
                     "sha": blob["sha"]})
    for p in deleted:
        tree.append({"path": p, "mode": "100644", "type": "blob", "sha": None})
    log("   已建 blob %d 个" % len(added + modified))

    new_tree = api("POST", "/repos/%s/%s/git/trees" % (OWNER, REPO), token,
                   {"base_tree": tsha, "tree": tree})   # ← tree sha，不是 commit sha
    msg = git("log", "-1", "--format=%s").strip() or "chore: api sync"
    commit = api("POST", "/repos/%s/%s/git/commits" % (OWNER, REPO), token,
                 {"message": msg, "tree": new_tree["sha"], "parents": [csha]})
    api("PATCH", "/repos/%s/%s/git/refs/heads/%s" % (OWNER, REPO, BRANCH),
        token, {"sha": commit["sha"], "force": False})
    log("   新 commit %s" % commit["sha"][:12])

    # 复核：重拉远端 tree，逐文件比 blob sha
    time.sleep(2)
    _, _, rfiles2 = remote_state(token)
    bad = [p for p in added + modified if rfiles2.get(p) != lfiles[p]]
    extra = [p for p in deleted if p in rfiles2]
    log("\n== 复核 ==")
    log("   远端文件 %d 个（推送前 %d）" % (len(rfiles2), len(rfiles)))
    if bad or extra:
        log("   ❌ 不一致：内容错 %d 个 / 残留 %d 个" % (len(bad), len(extra)))
        for p in (bad + extra)[:10]:
            log("      %s" % p)
        return 1
    log("   ✅ 全部 %d 个改动文件的内容已逐字节核对一致"
        % (len(added) + len(modified) + len(deleted)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
