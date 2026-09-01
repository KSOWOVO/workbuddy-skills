# -*- coding: utf-8 -*-
"""
把本地文件上传到腾讯云 COS（用于 ima 知识库 create_media -> 上传 -> add_knowledge 流程）。

用法:
  python cos_upload.py <credential.json> <local_file_path>

credential.json 内容（直接由 mcp__ima-mcp__create_media 返回的 cos_credential 字段 + 文件信息拼成）:
{
  "secret_id": "...",
  "secret_key": "...",
  "token": "...",
  "start_time": 1788179988,
  "expired_time": 1788223188,
  "bucket_name": "ima-media-prod-1258344701",
  "region": "ap-shanghai",
  "cos_key": "2/KykN.../file_manager/xxx.md",
  "content_type": "text/markdown"
}

坑位记录（改脚本前务必读）:
1. UriPathname 的 `/` 不能被 URL 编码。只能对 key 的每一段单独 quote，再用 `/` 连接。
   若整体 quote(..., safe="") 会把 `/` 编成 %2F，COS 返回 SignatureDoesNotMatch (403)。
2. file_size 必须与实际上传字节数完全一致，且等于 create_media 时声明的值。
3. 签名 header 只用 host + x-cos-security-token 即可，不要额外加 content-type。
"""
import sys
import json
import hmac
import hashlib
import urllib.parse
from urllib.request import Request, urlopen


def build_auth(cred, secret_key, host, cos_key, method="put"):
    start_ts = int(cred["start_time"])
    end_ts = int(cred["expired_time"])
    q_sign_time = "%d;%d" % (start_ts, end_ts)
    q_key_time = q_sign_time
    sign_key = hmac.new(
        secret_key.encode("utf-8"), q_key_time.encode("utf-8"), hashlib.sha1
    ).hexdigest()

    headers_to_sign = {"host": host, "x-cos-security-token": cred["token"]}
    h_list = sorted(headers_to_sign.keys())
    h_str = "&".join(
        "%s=%s"
        % (
            urllib.parse.quote(k, safe=""),
            urllib.parse.quote(headers_to_sign[k], safe=""),
        )
        for k in h_list
    )

    # 关键：只对每一段编码，保留路径分隔符 /
    enc_path = "/" + "/".join(
        urllib.parse.quote(p, safe="") for p in cos_key.split("/")
    )
    http_string = "%s\n%s\n%s\n%s\n" % (method.lower(), enc_path, "", h_str)
    string_to_sign = "sha1\n%s\n%s\n" % (
        q_sign_time,
        hashlib.sha1(http_string.encode("utf-8")).hexdigest(),
    )
    signature = hmac.new(
        sign_key.encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha1
    ).hexdigest()

    return "&".join(
        [
            "q-sign-algorithm=sha1",
            "q-ak=" + cred["secret_id"],
            "q-sign-time=" + q_sign_time,
            "q-key-time=" + q_key_time,
            "q-header-list=" + ";".join(h_list),
            "q-url-param-list=",
            "q-signature=" + signature,
        ]
    )


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)

    with open(sys.argv[1], "r", encoding="utf-8") as f:
        cred = json.load(f)
    file_path = sys.argv[2]

    with open(file_path, "rb") as f:
        body = f.read()

    bucket = cred["bucket_name"]
    region = cred["region"]
    cos_key = cred["cos_key"]
    host = "%s.cos.%s.myqcloud.com" % (bucket, region)
    url = "https://%s/%s" % (host, cos_key)

    auth = build_auth(cred, cred["secret_key"], host, cos_key)

    req = Request(url, data=body, method="PUT")
    req.add_header("Authorization", auth)
    req.add_header("Host", host)
    req.add_header("x-cos-security-token", cred["token"])
    req.add_header("Content-Type", cred.get("content_type", "application/octet-stream"))
    req.add_header("Content-Length", str(len(body)))

    try:
        resp = urlopen(req, timeout=120)
        print("HTTP", resp.status, "| bytes:", len(body))
    except Exception as e:
        print("ERROR:", type(e).__name__, e)
        try:
            print(e.read().decode("utf-8", "ignore")[:800])
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
