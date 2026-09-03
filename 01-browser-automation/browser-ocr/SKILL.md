---
name: browser-ocr
agent_created: true
summary: 用 agent-browser 控制真实 Chromium（无头/有头）完成网页抓取、点击、截图、DOM 提取；必要时用 RapidOCR 做本地中英文识别。
description: >
  需要真实浏览器或图像文字识别时使用。
  触发词：打开网页、登录网站、点按钮、填表单、下拉加载、截图、网页取证、抓表格、导出数据、
  验证码、扫描件、图片转文字、OCR、识别截图里的字、canvas 渲染内容、动态渲染页面。
  不适用于：静态页面取正文（用 WebFetch 更省），以及纯本地图片之外的常规文件读取。
---

# browser-ocr 工作流

## 触发条件

当用户请求包含以下任一意图时，加载本 skill：
- 打开/控制浏览器、截图网页
- 用 OCR 识别截图/图片里的文字
- 从网页或图片中提取表格、文字、数据
- 网页自动化：点击、填表、登录、滚动、导出 PDF
- 验证网页内容或做网页数据取证
- **当前模型不支持直接识图，但用户粘贴/引用了图片**（系统提示 "model does not support images / Content filtered"，或 Read 图片只返回"被过滤/不支持"）→ **必须 OCR 兜底，禁止回复"我看不了图片"，更禁止编造图片内容**

## 模型不识图时的图片 OCR 兜底（2026-09-03 强制）

任何会话收到用户图片（截图/扫描件/聊天图片），若当前模型读不了图（Read 图片失败/被过滤/返回不支持），**无条件走本地 OCR**，不要直接说"请换多模态模型"：

1. **定位图片真实路径**（用户 @ 的图片会落盘）：
   - WorkBuddy 剪贴板截图：`C:\Users\13662\.workbuddy\clipboard-images\`（按修改时间取最新，或按对话里 `<image_local_path>` 精确匹配）
   - 微信收到的图片：`C:\Users\13662\Documents\xwechat_files\wxid_jkqytfnhr4g622_78c5\temp\` 下按时间找
   - 用户直接给路径 → 直接用

2. **OCR 识别**（Python 直跑，不需要真浏览器）：
   ```bash
   "C:/Users/13662/.workbuddy/binaries/python/versions/3.13.12/python.exe" \
     "C:/Users/13662/.workbuddy/skills/01-browser-automation/browser-ocr/scripts/ocr.py" \
     "<图片路径>" --min-score 0.3
   ```
   - 文字版输出即图片内容；需坐标用 `--json`
   - OCR 把数字/汉字读错很常见（如 吴→伍、246→240），**关键数字（成绩/学号/分数）要结合上下文交叉验证，拿不准就明确告诉用户"这里是 OCR 结果，请对照原件"**，绝不把 OCR 误读当事实

3. 识别完把文字内容当正常输入处理（分析/计算/填表照常），**并在回复里注明"已通过 OCR 识别你发的图片"** 让用户知道链路。

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

## 详细参考
恢复流程 / 关键注意 / 常用命令速查 → `references/browser-details.md`（仅在需要时读取）
