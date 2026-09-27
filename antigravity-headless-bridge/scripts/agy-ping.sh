#!/usr/bin/env bash
# agy-ping.sh — 小A 链路体检 + 用量汇报
#
# 用法:
#   ./agy-ping.sh              仅体检（不消耗额度）
#   ./agy-ping.sh report       跑一次探针并输出格式化用量汇报
#
# 输出：出口地区 / agy 版本 / 链路状态 / 用量明细

set -uo pipefail

MODE="${1:-check}"

echo "═══════════════════════════════════════"
echo " 小A 链路体检  $(date '+%Y-%m-%d %H:%M:%S')"
echo "═══════════════════════════════════════"

# --- 1. 版本 ---
if command -v agy >/dev/null 2>&1; then
  printf "agy 版本      : %s\n" "$(agy --version 2>/dev/null | head -1)"
else
  echo "agy 版本      : ✗ 未找到 agy，检查 PATH"
  exit 2
fi

# --- 2. 出口地区 ---
GEO_JSON=$(timeout 20 curl -s --max-time 15 https://ipinfo.io/json 2>/dev/null)
if [ -n "$GEO_JSON" ]; then
  CC=$(echo "$GEO_JSON" | grep -o '"country": *"[^"]*"' | cut -d'"' -f4)
  CY=$(echo "$GEO_JSON" | grep -o '"city": *"[^"]*"' | cut -d'"' -f4)
  IP=$(echo "$GEO_JSON" | grep -o '"ip": *"[^"]*"' | cut -d'"' -f4)
  printf "出口地区      : %s / %s  (%s)\n" "$CC" "$CY" "$IP"
  case "$CC" in
    JP|SG|KR|HK|TW) printf "节点评价      : ✓ %s 属亚洲邻近节点，推荐\n" "$CC" ;;
    CN)             echo  "节点评价      : ✗ 出口在国内，agy 必失败！请检查 TUN 是否开启" ;;
    *)              printf "节点评价      : ⚠ %s 非亚洲节点，可能不稳；失败时优先换 JP\n" "$CC" ;;
  esac
else
  echo "出口地区      : ✗ ipinfo 不可达（网络可能未通）"
fi

# --- 3. 代理变量 ---
PROXY=$(env | grep -i '^https_proxy=' | head -1 | cut -d= -f2-)
printf "代理变量      : %s\n" "${PROXY:-（未注入）}"

# --- 4. 凭证 ---
if timeout 40 agy models >/dev/null 2>&1; then
  echo "凭证状态      : ✓ 有效（agy models 可拉取）"
else
  echo "凭证状态      : ✗ 无效或网络不通 → 需交互式跑一次 agy 重新登录"
fi

# --- 5. 可选：探针 + 用量 ---
if [ "$MODE" = "report" ]; then
  echo "───────────────────────────────────────"
  echo "运行探针..."
  OUT=$(timeout 90 agy -p "Reply with exactly: PING" --output-format json 2>&1 | tail -1)
  if echo "$OUT" | grep -q '"status":"SUCCESS"'; then
    echo "链路状态      : ✓ SUCCESS"
    echo
    echo "── 本次用量 ──"
    echo "$OUT" | grep -o '"usage":{[^}]*}' | sed 's/"usage"://' | \
      tr ',' '\n' | tr -d '{}"' | sed 's/^/  /'
    echo "$OUT" | grep -o '"duration_seconds":[0-9.]*' | sed 's/^/  /'
    echo "$OUT" | grep -o '"conversation_id":"[^"]*"' | sed 's/^/  /'
    echo
    echo "  ⚠ 剩余额度：headless 模式无法获取（官方仅在交互式 TUI 状态栏"
    echo "     与 /credits、/usage 面板显示）。请勿依赖此处数字。"
  else
    echo "链路状态      : ✗ 失败"
    echo "$OUT" | head -c 400
    echo
    echo "  → 优先动作：换节点（JP 优先）"
  fi
fi

echo "═══════════════════════════════════════"
