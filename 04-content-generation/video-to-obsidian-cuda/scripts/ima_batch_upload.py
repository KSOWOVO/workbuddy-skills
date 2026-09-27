# -*- coding: utf-8 -*-
"""
ima_batch_upload.py —— 一次把整个目录的 md 批量传进 ima 知识库

原理：WorkBuddy 的 MCP 服务器是本地 HTTP 服务（JSON-RPC over SSE），
可以直接用脚本调用，无需逐个人工触发 MCP 工具。

链路（每个文件）：create_media → COS PUT → add_knowledge
端点/凭据从环境变量 CODEBUDDY_MCP_CONFIG 里动态读取（端口每会话会变）。

用法：
  python ima_batch_upload.py <目录> [--kb 001aa55b37801a4a] [--apply]
"""
import argparse
import base64
import glob
import hashlib
import hmac
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

KB = "001aa55b37801a4a"
MIME = {".md": "text/markdown", ".txt": "text/plain", ".pdf": "application/pdf"}


# ---------- MCP 调用 ----------
def mcp_cfg():
    """
    ima 的 MCP 调用配置，两级解析：
    ① 环境变量 CODEBUDDY_MCP_CONFIG 里有 ima-mcp 条目（会话启动时 ima 已连接）
    ② 否则兜底：connector-proxy 端点 + 从 ~/.workbuddy/mcp-tool-list.json
       的 entries 里定位 ima 路由 hash（create_media 所在的路由）。
    端口每会话会漂移（实测 1285/2488/4160），一律动态读取，绝不硬编码。
    """
    cfg = os.environ.get("CODEBUDDY_MCP_CONFIG", "")
    if not cfg:
        raise RuntimeError("环境缺 CODEBUDDY_MCP_CONFIG")
    servers = json.loads(cfg).get("mcpServers", {})
    for k in ("ima-mcp", "ima", "connector:ima-mcp"):
        if k in servers:
            return servers[k]

    # —— 兜底：connector-proxy 端点 + 动态路由 hash ——
    proxy = None
    for k, v in servers.items():
        u = (v.get("url") or "")
        if "/mcp" in u and ("127.0.0.1" in u or "localhost" in u):
            proxy = v
            break
    if not proxy:
        raise RuntimeError("找不到 connector-proxy 端点")

    tl = os.path.expanduser(r"~\.workbuddy\mcp-tool-list.json")
    entries = json.load(open(tl, encoding="utf-8")).get("entries", {})
    h = None
    for rh, tools in entries.items():
        if isinstance(tools, list) and any(
                isinstance(t, dict) and t.get("name") == "create_media"
                for t in tools):
            h = rh
            break
    if not h:
        raise RuntimeError("mcp-tool-list.json 里没找到 ima 路由")
    base = proxy["url"].rsplit("/", 1)[0]
    return {"url": "%s/%s/mcp" % (base, h),
            "headers": proxy.get("headers", {})}


_CFG = None


def rpc(method, params=None, timeout=90):
    global _CFG
    if _CFG is None:
        _CFG = mcp_cfg()
    body = {"jsonrpc": "2.0", "id": 1, "method": method}
    if params is not None:
        body["params"] = params
    req = urllib.request.Request(_CFG["url"],
                                 data=json.dumps(body).encode(), method="POST")
    for k, v in _CFG.get("headers", {}).items():
        req.add_header(k, v)
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json, text/event-stream")
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with op.open(req, timeout=timeout) as r:
        raw = r.read().decode("utf-8", "replace")
    # SSE 格式：可能有多行 data:
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            return json.loads(line[5:].strip())
    return json.loads(raw)


def call_tool(name, args, timeout=180):
    r = rpc("tools/call", {"name": name, "arguments": args}, timeout)
    if "error" in r:
        raise RuntimeError("MCP %s 错误: %s" % (name, r["error"]))
    res = r.get("result", {})
    if res.get("isError"):
        raise RuntimeError("MCP %s isError: %s" % (name, res.get("content")))
    # 结构化内容优先
    if "structuredContent" in res:
        return res["structuredContent"]
    for it in res.get("content", []):
        if it.get("type") == "text":
            try:
                return json.loads(it["text"])
            except Exception:
                return {"_text": it["text"]}
    return res


# ---------- COS ----------
def cos_put(cred, local_path):
    with open(local_path, "rb") as f:
        body = f.read()
    sk = cred["secret_key"]
    st, et = int(cred["start_time"]), int(cred["expired_time"])
    qt = "%d;%d" % (st, et)
    sign_key = hmac.new(sk.encode(), qt.encode(), hashlib.sha1).hexdigest()
    host = "%s.cos.%s.myqcloud.com" % (cred["bucket_name"], cred["region"])
    key = cred["cos_key"]
    hs = {"host": host, "x-cos-security-token": cred["token"]}
    hlist = sorted(hs)
    hs_str = "&".join("%s=%s" % (urllib.parse.quote(k, safe=""),
                                 urllib.parse.quote(hs[k], safe=""))
                      for k in hlist)
    enc = "/" + "/".join(urllib.parse.quote(p, safe="") for p in key.split("/"))
    http_str = "put\n%s\n\n%s\n" % (enc, hs_str)
    sts = "sha1\n%s\n%s\n" % (qt, hashlib.sha1(http_str.encode()).hexdigest())
    sig = hmac.new(sign_key.encode(), sts.encode(), hashlib.sha1).hexdigest()
    auth = "&".join(["q-sign-algorithm=sha1", "q-ak=" + cred["secret_id"],
                     "q-sign-time=" + qt, "q-key-time=" + qt,
                     "q-header-list=" + ";".join(hlist), "q-url-param-list=",
                     "q-signature=" + sig])
    req = urllib.request.Request("https://%s/%s" % (host, key), data=body,
                                 method="PUT")
    req.add_header("Authorization", auth)
    req.add_header("Host", host)
    req.add_header("x-cos-security-token", cred["token"])
    req.add_header("Content-Type", cred.get("content_type", "text/markdown"))
    req.add_header("Content-Length", str(len(body)))
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with op.open(req, timeout=180) as r:
        return r.status, len(body)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", help="要上传的目录（递归找 *.md）")
    ap.add_argument("--kb", default=KB)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--only", default=None, help="只传文件名含此串的")
    a = ap.parse_args()

    files = []
    for dp, ds, fs in os.walk(a.root):
        if "_plain" in dp or "_staging" in dp:
            continue
        for f in sorted(fs):
            if f.endswith(".md"):
                files.append(os.path.join(dp, f))
    if a.only:
        files = [f for f in files if a.only in f]
    files.sort()
    print("待上传 %d 个文件" % len(files))
    if not a.apply:
        for f in files:
            print("   %8d B  %s" % (os.path.getsize(f),
                                    os.path.relpath(f, a.root)))
        print("\n（预演模式，未上传；加 --apply 执行）")
        return 0

    ok = fail = 0
    for i, p in enumerate(files, 1):
        name = os.path.splitext(os.path.basename(p))[0]
        size = os.path.getsize(p)
        ext = os.path.splitext(p)[1].lower().lstrip(".")
        print("[%2d/%d] %s (%d B)" % (i, len(files), name, size), flush=True)
        try:
            cm = call_tool("create_media", {
                "knowledge_base_id": a.kb, "file_name": name,
                "file_ext": ext, "file_size": size,
                "content_type": MIME.get("." + ext, "text/markdown")})
            mid = cm.get("media_id")
            cred = cm.get("cos_credential")
            if not mid or not cred:
                raise RuntimeError("create_media 返回缺字段: %s" % str(cm)[:200])
            cred["content_type"] = MIME.get("." + ext, "text/markdown")
            st, n = cos_put(cred, p)
            call_tool("add_knowledge", {
                "knowledge_base_id": a.kb, "media_id": mid, "folder_id": "",
                "duplicate_name_strategy":
                    "DUPLICATE_NAME_STRATEGY_REPLACE"})
            print("        ✅ COS %s / %d B -> 已入库" % (st, n), flush=True)
            ok += 1
        except Exception as e:
            print("        ❌ %s: %s" % (type(e).__name__, e), flush=True)
            fail += 1
        time.sleep(0.6)

    print("\n" + "=" * 50)
    print("成功 %d / 失败 %d" % (ok, fail))
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
