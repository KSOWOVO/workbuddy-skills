---
name: ima-knowledge-upload
agent_created: true
summary: 通过 ima MCP 把本地文件（md/txt/pdf/docx/pptx/xmind）写入 ima 知识库，或读取/检索 ima 已有内容。链路 create_media → COS 签名上传 → add_knowledge。
description: >
  把本地生成的文件写进 ima 知识库，或读取 ima 已有内容时使用。
  写入触发词：存进 ima、上传到知识库、写入 ima、同步到 ima、放进知识库、ima 入库、backup to ima。
  读取触发词：列出知识库、列出知识条目、搜一下 ima、抓取某条知识正文、ima 里有没有。
  适用文件：md / txt / pdf / docx / pptx / xmind 及任意文档。
  含 COS 签名与 MIME 对照表；COS 上传必须禁用代理环境变量（脚本内已处理）。
---

# ima 知识库读写

## 前置条件
ima MCP 连接器必须处于 connected。用 `ToolSearch` 加载工具：
`mcp__ima-mcp__get_knowledge_base_list`、`get_knowledge_list`、`search_knowledge`、
`fetch_media_content`、`create_media`、`add_knowledge`、`import_urls`。

调用方式：`DeferExecuteTool`。

## 读：拿到 knowledge_base_id
`get_knowledge_base_list` 参数是 `params` **数组**：
```json
{"params": [{"limit": 20, "type": "KBT_MINE_KB"}]}
```
返回 `knowledge_base_list[].id`。个人知识库只有一个，记下来复用。
- 列条目：`get_knowledge_list` {knowledge_base_id, limit, cursor: ""}
- 搜索：`search_knowledge` {knowledge_base_id, query}
- 读正文：`fetch_media_content` {media_id}

## 写：三步链路（缺一不可）

### 1. create_media
参数：`knowledge_base_id`、`file_name`（不含扩展名）、`file_ext`、`file_size`（**字节数，必须精确**）、`content_type`。

MIME 对照（禁止用 `application/octet-stream` 兜底）：
| 扩展名 | content_type |
|---|---|
| md / markdown | text/markdown |
| txt | text/plain |
| pdf | application/pdf |
| doc | application/msword |
| docx | application/vnd.openxmlformats-officedocument.wordprocessingml.document |
| ppt | application/vnd.ms-powerpoint |
| pptx | application/vnd.openxmlformats-officedocument.presentationml.presentation |
| xls | application/vnd.ms-excel |
| xlsx | application/vnd.openxmlformats-officedocument.spreadsheetml.sheet |
| csv | text/csv |
| xmind | application/x-xmind |
| html | text/html |
| png / jpg / webp | image/png / image/jpeg / image/webp |
| mp3 / m4a / wav / aac | audio/mpeg / audio/x-m4a / audio/wav / audio/aac |
| epub | application/epub+zip |

返回 `media_id` 与 `cos_credential`（含 secret_id / secret_key / token / start_time / expired_time / bucket_name / region / cos_key）。**凭证有效期约 12 小时，务必一次性跑完。**

### 2. 上传 COS
把 `cos_credential` 加上 `content_type` 存成 `cred.json`，然后：
```bash
python scripts/cos_upload.py cred.json "<本地文件绝对路径>"
```
成功返回 `HTTP 200`。

**签名坑（已踩过，别改回去）**：
- UriPathname 的分隔符 `/` **不能**被 URL 编码。只能对 cos_key 每一段单独 `quote(safe="")` 再用 `/` 拼接。整体编码会得到 `%2F` → COS 返回 `403 SignatureDoesNotMatch`。
- 签名 header 只签 `host` + `x-cos-security-token`，不要加 content-type。
- 上传字节数必须等于 create_media 声明的 `file_size`，否则服务端校验拒绝。

排查：COS 返回的 XML 里会带它自己算的 `StringToSign` 和 `FormatString`，逐字对比即可定位。

### 3. add_knowledge 入库
```json
{"knowledge_base_id": "...", "media_id": "...", "folder_id": "", "duplicate_name_strategy": "DUPLICATE_NAME_STRATEGY_REPLACE"}
```
`folder_id` 留空 = 根目录。**REPLACE 会覆盖同名文件**，适合反复更新同一份文档。

### 4. 验证
再调一次 `get_knowledge_list`，确认 `total_size` +1、新条目 `media_state: 2`（解析成功）、`parse_progress: 100`。
只有 `media_state: 2` 的知识才能被检索/问答命中。

## 已知限制
- **没有创建文件夹的 MCP 工具**。文件夹需在 ima 客户端手动建；建好后从 `get_knowledge_list` 的 `folder_info` / `parent_folder_id` 拿到 `folder_id`，写文件时传进去。
- 不支持直接上传本地文件，必须走 create_media + COS。
- 网页/文章可用 `import_urls`（最多 10 条，需 folder_id，可传空字符串）直接导入。

## 典型场景：学习笔记闭环
视频/文档 → 转写文本 → 加工出「整理稿 + 思维导图 + 精华」→ 各自存为 md → 逐个走上面三步入库 → 再同步到前端展示层。
每份 md 建议在开头写清来源资料与所用方法，便于后续检索时定位依据。
