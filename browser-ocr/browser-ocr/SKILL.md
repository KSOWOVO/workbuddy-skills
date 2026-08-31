---
name: browser-ocr
agent_created: true
description: 通过 agent-browser 控制真实 Chromium 浏览器（无头/有头），完成打开网页、点击、截图、提取 DOM 文本；必要时用 RapidOCR 对截图做本地中文/英文文字识别。适用于网页数据取证、表格截图识别、验证码、扫描件、canvas 渲染内容等场景。
---

# browser-ocr 工作流

## 触发条件

当用户请求包含以下任一意图时，加载本 skill：
- 打开/控制浏览器、截图网页
- 用 OCR 识别截图/图片里的文字
- 从网页或图片中提取表格、文字、数据
- 网页自动化：点击、填表、登录、滚动、导出 PDF
- 验证网页内容或做网页数据取证

## 前置条件

执行前先检查是否已安装：
- `agent-browser --version` 应能返回版本（当前验证可用的是 v0.27.0）
- Chromium 已通过 `agent-browser install` 下载到 `~/.agent-browser/browsers/`
- Python venv 中已装 `rapidocr-onnxruntime`

若未安装，按以下顺序安装：
1. `npm install -g agent-browser`
2. `agent-browser install`
3. 在隔离 Python venv 中 `pip install rapidocr-onnxruntime`

## 核心脚本

本 skill 自带两个脚本：
- `scripts/agent-browser.sh`：包装 agent-browser，自动处理 Windows 代理环境、stdout 挂起问题，并隔离 proxy/direct 两种模式。
- `scripts/ocr.py`：对图片跑 RapidOCR，输出文本和坐标；支持 `--json` 与 `--min-score`。

## 窗口形态

| 形态 | 用户看到什么 | 用法 |
|------|-------------|------|
| 默认无头 | 没有可见窗口，只有后台 chrome.exe 进程 | `./agent-browser.sh open <url> > out.log 2>&1` |
| `--headed` | 弹出一个真实的 Chrome for Testing 窗口 | `./agent-browser.sh --direct open <url> --headed` |
| dashboard | 打开 `http://localhost:4848` 网页看实时画面 | `agent-browser dashboard start` |
| 截图 | 保存成 png，可用 `--full` 截全页 | `agent-browser screenshot out.png` |

## 推荐工作流

1. **先判断文字是否已经在 DOM 里**：
   - 用 `snapshot` 或 `get text <selector>` 直接取文本，准确率最高，无需 OCR。
   - 只有当文字是图片、canvas、验证码、扫描件或设计稿时，才走 OCR。

2. **打开目标页面并截图**：
   ```bash
   ./agent-browser.sh --direct open "https://example.com" > out.log 2>&1
   ./agent-browser.sh screenshot page.png > shot.log 2>&1
   ```

3. **OCR 识别**：
   ```bash
   python scripts/ocr.py page.png --json --min-score 0.3
   ```

4. **关闭浏览器**（任务结束必须执行）：
   ```bash
   agent-browser close --all
   ```

## 持久性与跨工作区

- **位置即保险**：本 skill 位于用户目录 `~/.workbuddy/skills/browser-ocr/`，属于 user-level，**对所有工作区、所有对话框、所有模型自动可用**，不随某个项目移动。WorkBuddy 客户端更新不会覆盖此目录（marketplace 安装的 skill 在 `plugins/cache`，用户自建 skill 在 `~/.workbuddy/skills/`），并已标记 `agent_created: true`。
- **任意文件夹可调用**：包装脚本已复制为 `abrowser` 并加入 PATH（Node 的 bin 目录）。在任意文件夹的终端可直接运行 `abrowser`，不依赖当前工作目录；本 skill 内部调用时也一律使用绝对路径 `scripts/agent-browser.sh`。
- **真实依赖在用户目录**：`agent-browser` 本身装在 `~/.workbuddy/binaries/node/versions/*`（Windows 下 npm 全局 bin 在版本目录根，不是 `bin/` 子目录），Chromium 在 `~/.agent-browser/browsers/`，RapidOCR 在隔离 venv——都不在 `.workbuddy` 项目目录里，项目被删除也不影响。

## 恢复（万一目录被清空）

备份 zip 已生成在：`browser-ocr.zip`。一键恢复：

```bash
# git bash
mkdir -p "$HOME/.workbuddy/skills"
unzip -o <path>/browser-ocr.zip -d "$HOME/.workbuddy/skills/"

# 恢复 PATH 里的命令（注意版本号后缀 -2；Windows 下 npm 全局 bin 在版本目录根，不是 bin 子目录）
cp "$HOME/.workbuddy/skills/browser-ocr/browser-ocr/scripts/agent-browser.sh" \
   "$HOME/.workbuddy/binaries/node/versions/22.22.2-2/abrowser"
chmod +x "$HOME/.workbuddy/binaries/node/versions/22.22.2-2/abrowser"
```

## 关键注意

- **所有 agent-browser 命令必须重定向输出到文件**，否则 bash 会话会被后台 daemon 挂住：`> log 2>&1`。
- **Windows 代理环境**：如果系统有 `HTTP_PROXY`，Chromium 会报 `ERR_NO_SUPPORTED_PROXIES`。`agent-browser.sh` 只在启动 daemon 的 `open` 命令上用 `env -u` 清掉这些变量；后续 `screenshot` / `get title` / `click` 等命令会保持原环境变量连接 daemon，否则客户端会失联、命令空转。
- **代理/直连切换**：用 `--session proxy` 与 `--session direct` 隔离两种模式。`agent-browser.sh` 默认代理模式（127.0.0.1:7897），`--direct` 则直连。
- **HEADED 模式切换**：如果当前 session 已在无头模式运行，需先 `close` 该 session 才能再用 `--headed` 弹出窗口。`agent-browser.sh` 会在检测到 `--headed` 时自动先关对应 session。
- **残留 daemon 清理**：重装 agent-browser、切换 node 版本，或发现 `get title` / `screenshot` 返回空时，先用 `agent-browser close --all` 关会话，必要时用 `taskkill /F /IM agent-browser-win32-x64.exe` 和 `taskkill /F /IM chrome.exe` 清理旧 daemon，然后重新 `open`。
- **OCR 置信度**：短文本（如 "EC" / "SC"）可能被默认 0.5 阈值过滤，降低阈值即可召回。

## 常用命令速查

```bash
# 任意目录可用 `abrowser` 替代 `./agent-browser.sh`（已在 PATH）
abrowser open "https://www.baidu.com" > out.log 2>&1
./agent-browser.sh --direct open "https://www.baidu.com" --headed > out.log 2>&1
./agent-browser.sh snapshot -i > snap.log 2>&1
./agent-browser.sh screenshot page.png --full > shot.log 2>&1
./agent-browser.sh get title > title.log 2>&1
./agent-browser.sh click "#submit" > click.log 2>&1
./agent-browser.sh type "#username" "myuser" > type.log 2>&1
python scripts/ocr.py page.png
python scripts/ocr.py page.png --json --min-score 0.3
agent-browser close --all
```
