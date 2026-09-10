# 资料库在线化：page 上传 + database 双向同步

适用：把本地单文件工作台变成"在资料库打开即多设备同步"的在线页。

## 0. 前置

1. 读运行模式：
   ```bash
   python "<plugin>/skills/library/runtime_context.py"   # {"mode":"client"} 或 sandbox
   ```
2. `mode=client` 时，**每条网络命令前**都要换票：`ToolSearch["connect_open_platform"]` → `DeferExecuteTool{skill_id:"library"}` → 取 `token`，用
   `printf '%s' "<token>" | python <script> --token-stdin ...` 传入（不落文件、不回显）。
   - 注意：连 `--help` 都会先鉴权，`{"error":"code=AUTH_REQUIRED..."}` 就是没传 token。
3. 脚本根目录：`<plugin>/skills/library/`（page/、database/、manage/ 子目录）。

## 1. 上传页面

```bash
printf '%s' "$TOK" | python "<plugin>/skills/library/page/import_html.py" "<file.html>" --token-stdin
# 成功 → KS_IMPORT_OK {"node_block_id":"...","url":"https://www.workbuddy.cn/space/d/<id>",...}
# 覆盖更新同一节点（需 admin 权限，权限不足返回 56161，此时改走 edit-flow 增量事务）：
printf '%s' "$TOK" | python ".../import_html.py" "<file.html>" --token-stdin \
  --node-block-id "<node_block_id>" --databases '[{"id":"<database_id>"}]'
```
- 单文件上限 50 MiB；`.html`/`.htm`/`.zip`。
- 页面里**不允许**有指向第三方域的 `<img src>`（平台内链除外）；纯 SVG/canvas 页面天然过关。

## 2. 建数据表（存状态快照）

```bash
printf '%s' "$TOK" | python ".../database/create_database.py" --token-stdin --schema '<JSON>'
# → {"database_id":"...","space_id":"","property_count":4,"properties":[...]}
```
分片快照表的 schema（规避长文本限制）：
```json
{"title":"XX台·进度备份","properties":[
  {"name":"分片键","config":{"text":""}},
  {"name":"序号","config":{"number":{"decimalPlaces":0,"useSeparate":false}}},
  {"name":"内容","config":{"text":""}},
  {"name":"更新时间","config":{"text":""}}]}
```
Windows 下用 `subprocess.run([py, script, "--token-stdin", "--schema", json.dumps(schema, ensure_ascii=False)], input=token, ...)` 传参，避免 shell 中文编码问题。

## 3. 页面侧 SDK 接入（关键契约）

- 平台注入 `window.__SMART_PAGE__.database`（页面里用 `try/catch` 探测，无则降级 localStorage）。
- `databaseId` **必须硬编码字符串字面量**。
- 方法：`db.query({databaseId, filter?, sorts?, fields?, startCursor?, pageSize?})`、`db.addRecord({databaseId, properties})`、`db.updateRecord({databaseId, recordId, properties})`（增量）、`db.deleteRecord({databaseId, recordId})`、`db.getSchema`、`db.onUpdated(handler)`（同步订阅，非 Promise）。
- `query` 返回 `{results, nextCursor, hasMore}`，**续页参数名固定 `startCursor`**（写 `cursor` 会被静默忽略 → 死循环）；`pageSize` 默认 50、最大 200；单次只回一页，拉全量必须自己循环 + 游标前进 + 硬上限熔断。
- 记录是扁平对象 `{"字段名": 值}`，主键为 `_id`。
- 字段值 oneof：`{text:".."}` / `{number:1}` / `{select:"选项名或 opt_id"}` / `{date:"2026-06-24"}` / `{checkbox:true}` 等。

## 4. 同步策略（本项目已验证可用）

- 状态 `JSON.stringify` 后按 **6000 字符分片**，每片一条记录（`分片键` 固定值区分业务，`序号` 排序，`内容` 文本，`更新时间` ISO）。
- 写入：对比现有分片记录 → 变化的 `updateRecord`、新增的 `addRecord`、多余的 `deleteRecord`；完成后重新 `loadAll` 刷新本地缓存。
- 拉取：按 `更新时间` 与本地 `S._ts` 比较，云端更新才覆盖（最后写入者胜）。
- 触发：`save()` 后防抖 2.5s 推送；启动时拉一次；`onUpdated` 触发时再拉。
- 降级：任何异常 → 状态徽标显示"同步失败"，但 localStorage 读写照常，不影响使用。
- 页面上给一个状态徽标（离线本地/同步中/已同步/同步失败）和「立即同步云端」按钮。

## 5. 收尾

- 发布是独立动作：只有用户明说"发布/部署"才跑 `page/publish_page.py --token-stdin --node-id <id>`；否则交付协作态链接 `/space/d/<id>` 并提示"可在页面右上角点发布"。
- 回执给出 `url`，不回显 token / 签名 URL / 原始响应。
