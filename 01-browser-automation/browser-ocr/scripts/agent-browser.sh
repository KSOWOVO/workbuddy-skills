#!/usr/bin/env bash
# ab.sh — agent-browser 包装器（已处理 Windows 代理环境 & 输出挂起 & 模式切换问题）
#
# 用法:
#   ./ab.sh open <url>                      走本地代理（默认，可访问 Google 等）
#   ./ab.sh --direct open <url>             直连（国内站点更快）
#   ./ab.sh --direct open <url> --headed    弹出可见窗口
#   ./ab.sh snapshot -i
#   ./ab.sh screenshot out.png
#   ./ab.sh close
#
# 两条硬性注意:
#   1. 调用时必须把输出重定向到文件，否则 bash 会话会被后台进程挂住:
#        ./ab.sh open https://example.com > out.log 2>&1
#   2. 两种模式用不同 --session 隔离，各自常驻独立浏览器实例，切换即时生效
#
# 环境: agent-browser 0.27.0，Chrome 152

set -u

PROXY="${AB_PROXY:-http://127.0.0.1:7897}"
MODE="proxy"

if [ "${1:-}" = "--direct" ]; then
  MODE="direct"
  shift
fi

# 清空代理环境变量：Chromium 继承这些变量后会报 ERR_NO_SUPPORTED_PROXIES
# 注意：只能在启动 daemon 的 `open` 命令上用；后续 screenshot/get title 等命令
# 若也清掉代理变量，agent-browser 客户端会连不上已运行的 daemon，导致空转。
CLEAN=(env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy -u ALL_PROXY -u all_proxy)

# --headed / --proxy 这类启动期选项对已运行的 daemon 无效，需要先关掉该 session
for arg in "$@"; do
  if [ "$arg" = "--headed" ]; then
    if [ "$MODE" = "proxy" ]; then
      agent-browser --session proxy close >/dev/null 2>&1
    else
      agent-browser --session direct close >/dev/null 2>&1
    fi
    break
  fi
done

if [ "${1:-}" = "open" ]; then
  # 启动 daemon 时清代理，让 Chromium 不要继承 HTTP_PROXY
  if [ "$MODE" = "proxy" ]; then
    "${CLEAN[@]}" agent-browser --proxy "$PROXY" --session proxy "$@"
  else
    "${CLEAN[@]}" agent-browser --session direct "$@"
  fi
else
  # 连接已运行 daemon，保持原环境变量，否则客户端会失联
  if [ "$MODE" = "proxy" ]; then
    agent-browser --session proxy "$@"
  else
    agent-browser --session direct "$@"
  fi
fi
