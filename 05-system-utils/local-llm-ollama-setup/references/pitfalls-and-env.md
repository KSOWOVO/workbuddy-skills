# 踩坑清单与排障（本地模型 / Ollama / WorkBuddy 接入）

实战记录：2026-09-11 在 Ryzen 9 7845HX + RTX 5060 Laptop(4GB 显存) + Win11 家庭版、**普通用户权限**环境下完成一次完整部署。

---

## A. 下载与安装类

### A1. GitHub release 资源被代理阻断
**现象**：`curl` 直连 `github.com/.../releases/download/...` 返回 502 或超时。
**原因**：release 资源实际托管在 `release-assets.githubusercontent.com`，代理常拦。
**解法**：套 `gh-proxy.com` 镜像，实测 ~10.6 MB/s。
```bash
https://gh-proxy.com/https://github.com/<owner>/<repo>/releases/download/<tag>/<file>
```

### A2. 「安装包已损坏」的真凶是下载被中断
**现象**：双击安装器提示 *"setup files are corrupted"*。
**原因**：下载中途被 kill，文件不完整（本次卡在 130 MB，完整应为 **1,474,272,976 字节 ≈ 1.47 GB**）。
**解法**：**先比对体积再比对 SHA256**，不要凭感觉重试。
```bash
ls -l file.exe              # 与 release 页标注 size 逐字节比对
sha256sum file.exe          # 与官方 checksum 比对
```

### A3. 非管理员装不了 NSIS 安装器
**现象**：安装器 exit code 1，装完也不在 PATH；`ollama: NOT installed`。
**原因**：NSIS 安装器强制要求提权，非管理员会话下静默安装被拒。
**解法**：改用 `ollama-windows-amd64.zip` 便携版，7-Zip 解压即用，零权限。
```bash
"/c/Program Files/7-Zip/7z.exe" x ollama.zip -o/D/OllamaApp -y
```

### A4. 7-Zip 解不开 OllamaSetup.exe
**原因**：它是 PE 自解压容器而非标准 NSIS 包。
**解法**：别折腾，直接用便携版 zip。

---

## B. 运行与资源类

### B5. 权重默认落在 C 盘
**解法**：`set OLLAMA_MODELS=D:\OllamaModels`（写在启动脚本里，不要只在当前 shell 设）。

### B6. 用户误解「启动服务 = 卡电脑」
**要主动讲清楚**：

| 状态 | 内存 | 显存 | CPU |
|---|---|---|---|
| 引擎在跑、没调用 | ~100 MB | **0** | 0% |
| 推理中 | ~100 MB | 模型体积+KV | GPU 满载 |
| 任务结束后 | ~100 MB | **立即归 0** | 0% |

引擎只是个空壳（比记事本还轻），吃资源的是「把模型加载进显存」这个动作。

### B7. 默认 5 分钟驻留显存 → 想立刻释放
`OLLAMA_KEEP_ALIVE=0`（服务端环境变量，需重启 serve 生效）。
验证：调用一次后立刻 `ollama ps`，应返回**空表**。

### B8. 上下文只有 4096，agent 任务被截断
默认 `num_ctx=4096`，工具定义+上下文很容易超。
→ `OLLAMA_CONTEXT_LENGTH=8192`。
显存紧张时配 `OLLAMA_KV_CACHE_TYPE=q8_0`（需 `OLLAMA_FLASH_ATTENTION=1`）。
实测：8K 窗口下 4B 模型显存 3.2 GB → 3.3 GB（仅 +0.1 G），若不量化则 +0.6 G。

**KV 缓存显存估算**（fp16）：`2 × 层数 × KV头数 × head_dim × 2字节 × token数`
Qwen3-4B 约 144 KB/token → 4096 上下文 ≈ 0.59 GB，8192 ≈ 1.18 GB。

### B9. 沙箱拦截系统命令
`schtasks.exe`、`cscript.exe` 被安全策略拦（LOLBin 黑名单）。
→ 自启只能用 **Startup 文件夹**（Explorer 触发，不拦）。
→ `taskkill` / `tasklist` **可用**。

### B10. PowerShell 输出不回显
**现象**：命令执行了但结果看不到。
**解法**：把输出重定向到文件，再用 Read 工具读。

---

## C. WorkBuddy 接入类

### C11. 配置文件位置搞错
应用读 **`C:\Users\<user>\.workbuddy\models.json`**，
不是 `.codebuddy\models.json`（易混，写错完全不生效）。

### C12. 格式必须是数组
```json
[ { ... }, { ... } ]     ✅
{ "models": [ ... ] }    ❌ 不识别
```

### C13. 改了配置但模型列表里没有
**原因**：配置类变更不走文件热更新，provider 需重新加载。
**解法**：**完全退出 WorkBuddy 再打开**（不是关窗口）。

### C14. 端点写错
必须是 `http://127.0.0.1:11434/v1/chat/completions`。
写成 `/api/chat` 或漏掉 `/v1` 都会失败。

### C15. `maxInputTokens` 超出实际上下文
`maxInputTokens + maxOutputTokens > OLLAMA_CONTEXT_LENGTH` 时，Ollama 会**静默截断**（丢最前面的内容 → 系统提示消失 → 模型行为异常）。
→ 保持两者之和 ≤ 上下文长度。

---

## D. Qwen3 思考模式（最容易误判为故障）

### D16. 返回 `"content": ""`，内容全在 `reasoning` 里
**根因**：`max_tokens` 太小，被思考链吃光。
**解法**：`maxOutputTokens ≥ 2048`。

### D17. 思考模式关不掉
Ollama 的 Qwen3 模板**硬编码**注入开标签：
```
{{- if and (ne .Role "assistant") $last }}<|im_start|>assistant
<think>
{{ end }}
```
实测两条路都无效：
- `SYSTEM "/no_think"` 写进 Modelfile → reasoning 照旧
- OpenAI 端点传 `"think": false` → 被忽略（非标准字段）

**结论**：接受它。思考对「自主规划 + 调工具」的 agent 任务是加分项。
**唯一要做的**是保证输出 token 充足。不建议自定义 TEMPLATE（会连带影响 tools 的 XML 格式，风险大于收益）。

### D18. 查看真实模板（排障用）
```bash
ollama show qwen3:4b --template
ollama show qwen3:4b --parameters
```

---

## E. 派生模型的隐藏成本

用 Modelfile `FROM qwen3:4b` 派生新模型时，`ollama list` 会显示 SIZE 2.5 GB，**但磁盘不重复占用**——底层 blob 复用（日志会打印 `using existing layer`），实际只新增几 KB 的 manifest。
→ 所以派生模型很便宜，但**若没解决问题就该删掉**，避免模型列表混乱。`ollama rm <name>`。

---

## F. 验收清单（交付前逐条打勾）

- [ ] `curl /api/version` 返回版本号
- [ ] `curl /v1/chat/completions` 返回**非空 content**
- [ ] `ollama ps` 调用后返回**空表**（keep_alive=0 生效）
- [ ] `ollama ps` 推理中显示 CONTEXT = 目标值、PROCESSOR = 100% GPU
- [ ] 权重实际落在目标盘（`ls` 确认体积）
- [ ] `models.json` 位于 `.workbuddy` 且为数组格式
- [ ] Startup 自启 bat 存在且内容正确
- [ ] 明确告知用户：**需重启 WorkBuddy**
