# browser-ocr：恢复流程、关键注意与常用命令速查

> 从 SKILL.md 拆出的细节章节，仅在需要时读取。

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
