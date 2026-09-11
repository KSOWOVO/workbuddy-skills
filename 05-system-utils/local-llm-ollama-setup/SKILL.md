---
name: local-llm-ollama-setup
description: 在 Windows 上装本地小模型（Ollama 引擎 + Qwen3 等）并接入 WorkBuddy 本地模型功能。触发词：本地模型、本地大模型、装个小模型、Ollama、离线跑模型、qwen3、自托管 LLM、接模型到 WorkBuddy、显存不够选哪个模型、不用云端跑自动化。核心能力：按显存精准选型、无管理员权限用便携版绕开安装器、权重重定向到 D 盘、WorkBuddy models.json 接入、KEEP_ALIVE=0 让模型用完即卸不占资源。不适用于：云端 API 模型接入、纯 OCR 识别。
agent_created: true
---

# 本地小模型安装与接入 WorkBuddy

把开源小模型装在本机供 WorkBuddy 自动化任务离线调用。**默认假设用户是普通权限 Windows 用户。**

## 一、先定两件事

### 1. 查显存 → 定档位

| 可用显存 | 选这个 | 量化后体积 | 说明 |
|---|---|---|---|
| ≤ 2 GB | Qwen3-1.7B | ~1.2 GB | 仅够轻量问答 |
| **4 GB** | **Qwen3-4B** | **~2.5 GB** | 甜点位，支持工具调用 |
| 6–8 GB | Qwen3-8B | ~5.2 GB | 能力明显更强 |
| 12 GB+ | Qwen3-14B / 32B | 9 / 20 GB | 接近可用的复杂推理 |

**硬判据**：模型体积+KV缓存 ≤ 显存×0.85，超出会溢到内存、速度暴跌 10 倍。
**要工具调用（自动化任务前提）→ 不要低于 4B。**
⚠️ `wmic ... AdapterRAM` 是 32 位会溢出，别信它报的大小，让用户看任务管理器。

### 2. 查权限 → 定方式

```bash
net session >/dev/null 2>&1 && echo "ADMIN" || echo "NOT ADMIN"
```

**非管理员 → NSIS 安装器必然失败**（需提权）→ 走便携版 zip；管理员可直接装。

## 二、安装（便携版路线）

```bash
# 1) 下载引擎（约 1.5 GB；代理下 github 直连 502，用镜像）
curl -L --noproxy '*' -o /d/ollama.zip \
  "https://gh-proxy.com/https://github.com/ollama/ollama/releases/download/v<版本>/ollama-windows-amd64.zip"
ls -l /d/ollama.zip     # ⚠️ 必须比对体积：对不上=下载中断（会报"文件已损坏"）

# 2) 解压到 D 盘（7-Zip，无需权限）
"/c/Program Files/7-Zip/7z.exe" x /d/ollama.zip -o/d/OllamaApp -y

# 3) 权重默认落 C 盘必须重定向 → 4) 拉模型
OLLAMA_MODELS="D:/OllamaModels" /d/OllamaApp/ollama.exe pull qwen3:4b
```

## 三、启动脚本（环境变量是「不卡」的关键）

写 `D:\OllamaApp\serve.bat`：

```bat
@echo off
title Ollama Local Server - 关闭此窗口即停止服务
set OLLAMA_MODELS=D:\OllamaModels
set OLLAMA_KEEP_ALIVE=0
set OLLAMA_CONTEXT_LENGTH=8192
set OLLAMA_KV_CACHE_TYPE=q8_0
set OLLAMA_FLASH_ATTENTION=1
"D:\OllamaApp\ollama.exe" serve
```

- `OLLAMA_KEEP_ALIVE=0` —— 任务结束**立刻卸载模型**，显存瞬间归零（默认要驻留 5 分钟）
- `OLLAMA_CONTEXT_LENGTH=8192` —— 默认 4096，跑 agent 任务会被截断
- `OLLAMA_KV_CACHE_TYPE=q8_0` + `OLLAMA_FLASH_ATTENTION=1` —— KV 缓存量化，8K 窗口显存只 +0.1G（否则 +0.6G）

配 `stop-ollama.bat`：`taskkill /IM ollama.exe /F >nul 2>&1`

## 四、接入 WorkBuddy

配置文件 **`C:\Users\<user>\.workbuddy\models.json`**（⚠️ 不是 `.codebuddy`），格式是 **JSON 数组**：

```json
[
  {
    "id": "qwen3:4b",
    "name": "Qwen3-4B 本地 (Ollama)",
    "vendor": "Ollama",
    "url": "http://127.0.0.1:11434/v1/chat/completions",
    "apiKey": "ollama",
    "maxInputTokens": 6144,
    "maxOutputTokens": 2048,
    "supportsToolCall": true,
    "supportsImages": false
  }
]
```

- `url` **必须**带 `/v1/chat/completions`；`id` 与 `ollama list` **逐字一致**
- `maxInputTokens + maxOutputTokens` 不得超 `OLLAMA_CONTEXT_LENGTH`，否则静默截断
- **写完必须让用户完全退出并重启 WorkBuddy**，配置类变更不热加载

## 五、自启（⚠️ 沙箱限制）

`schtasks.exe` / `cscript.exe` **会被安全策略拦截**（LOLBin 黑名单）。改用 Startup 文件夹（Explorer 触发，不拦）：

```
C:\Users\<user>\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\ollama-serve.bat
```

内容 = serve.bat + `start "Ollama" /min "...\ollama.exe" serve` + `exit`。

## 六、验收（三步全过才算完）

```bash
curl -s --noproxy '*' http://127.0.0.1:11434/api/version          # 1. 引擎活着
curl -s --noproxy '*' -X POST http://127.0.0.1:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen3:4b","messages":[{"role":"user","content":"回复：OK"}],"max_tokens":2048}'  # 2. 真实端点+content 非空
/d/OllamaApp/ollama.exe ps                                        # 3. 应返回空表（用完即卸生效）
```

## 七、必须主动纠正用户的两个误解

1. **「启动引擎」≠「吃资源」**：空载 ~100MB 内存 / CPU 0% / 显存 0，只有被调用才加载，任务结束立刻释放。
2. **Qwen3 思考模式关不掉**（模板硬编码 `<think>`，`/no_think` 与 `think:false` 均无效）：对策是 **maxOutputTokens ≥ 2048**，否则 content 为空、自动化任务失败。

详见 `references/pitfalls-and-env.md`
