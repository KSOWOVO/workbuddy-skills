#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sync_verify.py — skill 云端同步的校验 / 修复 / 对齐工具。

解决三类问题：
  1. 行尾污染：经 GitHub Contents API 上传时直接发原始字节（Windows 下是 CRLF），
     绕过了 git 的 autocrlf 规范化，导致云端 blob 与本地 git blob 不一致。
     网络恢复后会出现「删不掉的幽灵改动」。本脚本能检测并用 git 规范化内容重推。
  2. 内容漂移：校验云端与本地是否逐字节一致。
  3. 历史分叉：API 直推产生的 commit 不在本地 git 历史里，需要 fetch 后对齐。

用法：
    python sync_verify.py                 # 只校验，输出报告
    python sync_verify.py --fix           # 校验 + 自动修复行尾污染
    python sync_verify.py --realign -y    # 网络恢复后对齐 git 历史（需 github.com:443 通）
                                          # 非交互环境必须带 -y，否则 input() 会 EOF 崩溃
    python sync_verify.py --json          # 机器可读输出

安全策略：
  - 覆盖前必比对「忽略 CR 后的实质内容」；只有确认仅行尾不同才覆盖，
    实质内容不同一律跳过并报告，绝不覆盖他人/其它会话的改动。
  - --realign 只在 HEAD 与远端的 tree 完全一致时才 reset，否则拒绝执行。

依赖：仅标准库 + 本机 git。PAT 从 remote.origin.url 自动提取。
"""

import argparse
import base64
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import urllib.request
import urllib.error

REPO = "KSOWOVO/workbuddy-skills"
API = f"https://api.github.com/repos/{REPO}/contents/"

# 预装 skill：按规则不同步，校验时跳过
SKIP_DIRS = ("ifind-finance-data", "market-query", "neodata-financial-search",
             "news-search", "westock-data", "_backup")

NO_PROXY = {"http": "", "https": ""}


def git(*args, binary=False):
    r = subprocess.run(["git", *args], capture_output=True)
    return r.stdout if binary else r.stdout.decode("utf-8", "replace")


def get_token():
    remote = git("config", "--get", "remote.origin.url").strip()
    m = re.match(r"https://x-access-token:([^@]+)@github\.com", remote)
    if not m:
        raise SystemExit(f"无法从 remote 提取 PAT: {remote[:70]}")
    return m.group(1)


def opener():
    # 必须显式禁代理，否则 Windows 下会走环境变量/注册表代理导致连接被重置
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def blob_sha(data: bytes) -> str:
    """按 git blob 语义计算 SHA1（与 git hash-object 一致）。"""
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def norm(b: bytes) -> bytes:
    return b.replace(b"\r\n", b"\n")


def tracked_files():
    out = []
    for f in git("ls-files").split():
        if not f.startswith(SKIP_DIRS):
            out.append(f)
    return out


def main():
    ap = argparse.ArgumentParser(description="skill 云端同步校验 / 修复 / 对齐")
    ap.add_argument("--fix", action="store_true", help="自动修复行尾污染（用 git 规范化内容重推）")
    ap.add_argument("--realign", action="store_true", help="网络恢复后对齐 git 历史")
    ap.add_argument("--yes", "-y", action="store_true",
                    help="自动确认（非交互/CI 环境必须，否则 input() 会 EOF 崩溃）")
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    args = ap.parse_args()

    if args.realign:
        return realign(yes=args.yes)

    token = get_token()
    op = opener()
    H = {"Authorization": f"Bearer {token}",
         "Accept": "application/vnd.github+json",
         "User-Agent": "workbuddy-sync-verify"}

    files = tracked_files()
    same, lineending, drift, missing = [], [], [], []
    for f in files:
        want = git("hash-object", f).strip()
        try:
            r = json.load(op.open(urllib.request.Request(API + f, headers=H), timeout=25))
        except urllib.error.HTTPError as e:
            missing.append({"file": f, "error": f"HTTP {e.code}"})
            continue
        except Exception as e:
            missing.append({"file": f, "error": str(e)[:60]})
            continue
        if r.get("sha") == want:
            same.append(f)
            continue
        cloud = base64.b64decode(r["content"])
        local_lf = git("show", f"HEAD:{f}", binary=True)
        if norm(cloud) == norm(local_lf):
            lineending.append({"file": f, "cloud_sha": r["sha"], "want_sha": want})
        else:
            drift.append({"file": f, "cloud_sha": r["sha"][:8], "want_sha": want[:8]})

    fixed = []
    if args.fix and lineending:
        MSG = ("fix: 用 git 规范化(LF)内容重推，修复 API 上传绕过 autocrlf 的行尾污染\n\n"
               "Contents API 上传直接发原始字节(CRLF)，git 语义下应存 LF，\n"
               "导致云端 blob 与本地不一致。已逐个校验实质内容一致后才覆盖。")
        for item in lineending:
            f = item["file"]
            local_lf = git("show", f"HEAD:{f}", binary=True)
            payload = {"message": MSG,
                       "content": base64.b64encode(local_lf).decode("ascii"),
                       "sha": item["cloud_sha"]}
            try:
                out = json.load(op.open(urllib.request.Request(
                    API + f, data=json.dumps(payload).encode("utf-8"),
                    headers={**H, "Content-Type": "application/json"},
                    method="PUT"), timeout=60))
                fixed.append({"file": f, "commit": out["commit"]["sha"][:7]})
            except Exception as e:
                drift.append({"file": f, "error": f"推送失败 {e}"})

    if args.json:
        print(json.dumps({"same": len(same), "fixed": fixed,
                          "lineending_left": [x["file"] for x in lineending if x["file"] not in
                                              [y["file"] for y in fixed]],
                          "drift": drift, "missing": missing},
                         ensure_ascii=False, indent=2))
        return 0

    print(f"校验 {len(files)} 个自创 skill 文件\n")
    for f in same:
        print(f"  [一致] {f}")
    for x in fixed:
        print(f"  [已修复] {x['file']}  -> {x['commit']}  (CRLF→LF 规范化)")
    for x in lineending:
        if x["file"] not in [y["file"] for y in fixed]:
            print(f"  [行尾差异] {x['file']}  (加 --fix 可自动修复)")
    for x in drift:
        if "error" in x:
            print(f"  [失败] {x['file']}  {x['error']}")
        else:
            print(f"  [内容漂移] {x['file']}  本地 {x['want_sha']} / 云端 {x['cloud_sha']}  ⚠ 不覆盖")
    for x in missing:
        print(f"  [缺失] {x['file']}  {x['error']}")

    ok = not drift and not missing and not [x for x in lineending
                                            if x["file"] not in [y["file"] for y in fixed]]
    print(f"\n{'=' * 56}")
    print(f"一致 {len(same)}  已修复 {len(fixed)}  待修复 {len(lineending) - len(fixed)}  "
          f"漂移 {len(drift)}  缺失 {len(missing)}")
    print("结论：" + ("云端与本地 git blob 完全一致" if ok else "存在差异，见上方明细"))
    if drift:
        print("\n⚠ 内容漂移的文件未被覆盖（保护策略）。确认后请手动处理。")
    return 0 if ok else 1


def realign(yes=False):
    """网络恢复后，把本地 git 历史对齐到 origin/main（解决 API 直推造成的分叉）。"""
    print("=== 对齐 git 历史 ===")
    r = subprocess.run(["git", "fetch", "origin", "main"], capture_output=True, text=True)
    if r.returncode != 0:
        print("git fetch 失败（github.com:443 不通？）：")
        print("  " + (r.stderr or "").strip()[:300])
        print("\n网络未恢复。等 443 通了再跑一次本命令即可。")
        return 1

    head = git("rev-parse", "HEAD").strip()
    fetch_head = git("rev-parse", "FETCH_HEAD").strip()
    print(f"本地 HEAD   : {head[:10]}")
    print(f"origin/main : {fetch_head[:10]}")

    if head == fetch_head:
        print("已对齐，无需操作。")
        return 0

    # 只比较 tree（内容），忽略 commit 历史差异
    t1 = git("rev-parse", "HEAD^{tree}").strip()
    t2 = git("rev-parse", "FETCH_HEAD^{tree}").strip()
    if t1 != t2:
        print("\n⚠ HEAD 与 origin/main 的**内容(tree)不一致**，拒绝自动对齐。")
        print("  说明还有改动没推上去。请先跑本脚本的 --fix 校验，再重新对齐。")
        d = git("diff", "--stat", "HEAD", "FETCH_HEAD")
        print("\n差异预览：\n" + d[:800])
        return 1

    print("\n内容(tree)一致，仅 commit 历史不同 → 安全，可用 reset --soft 对齐。")
    print("（--soft 只移动 HEAD，工作区文件不动，不会丢失任何改动）\n")
    if not yes and not sys.stdin.isatty():
        print("非交互环境，未自动执行。请手动运行：")
        print("    git reset --soft FETCH_HEAD")
        print("或加 --yes 自动确认。")
        return 0
    if not yes:
        ans = input("执行 git reset --soft FETCH_HEAD ? [y/N] ").strip().lower()
        if ans != "y":
            print("已取消。手动执行：git reset --soft FETCH_HEAD")
            return 0
    subprocess.run(["git", "reset", "--soft", "FETCH_HEAD"])
    print(f"已对齐，HEAD = {git('rev-parse', '--short', 'HEAD').strip()}")
    print(f"工作区状态：\n{git('status', '--short')[:400] or '  (clean)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
