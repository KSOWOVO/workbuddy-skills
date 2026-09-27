#!/usr/bin/env bash
# agy-dispatch.sh — 带重试与完整校验的 Antigravity CLI headless 派活器
#
# 用法:
#   ./agy-dispatch.sh <目标目录> "<任务描述>" [模型ID] [--effort high]
#
# 示例:
#   ./agy-dispatch.sh /tmp/proj "把 utils.py 里的函数改成异步"
#   ./agy-dispatch.sh /tmp/proj "审查 src/ 的错误处理" claude-sonnet-4-6
#
# 退出码: 0=成功且校验通过  1=agy 失败  2=前置检查失败  3=文件未落地

set -uo pipefail

TARGET_DIR="${1:?用法: $0 <目标目录> \"<任务描述>\" [模型ID]}"
PROMPT="${2:?缺任务描述}"
MODEL="${3:-}"
MAX_RETRY=3
TIMEOUT=300

# ---------- 前置检查 ----------
if ! command -v agy >/dev/null 2>&1; then
  echo "[FAIL] agy 不在 PATH。安装: irm https://antigravity.google/cli/install.ps1 | iex" >&2
  exit 2
fi

if ! agy models >/dev/null 2>&1; then
  echo "[FAIL] 凭证或网络不通。检查: (1) Clash TUN 开启 + 规则模式 (2) 需要时交互式跑一次 agy 登录" >&2
  exit 2
fi

if [ ! -d "$TARGET_DIR" ]; then
  echo "[FAIL] 目标目录不存在: $TARGET_DIR" >&2
  exit 2
fi

# 记录派活前的文件快照，用于事后判断是否真有产出
BEFORE=$(find "$TARGET_DIR" -type f -newermt '-1 second' 2>/dev/null | wc -l)
BEFORE_LIST=$(mktemp)
find "$TARGET_DIR" -type f 2>/dev/null | sort > "$BEFORE_LIST"

# ---------- 组装参数 ----------
ARGS=(-p "$PROMPT" --add-dir "$TARGET_DIR" --output-format json)
[ -n "$MODEL" ] && ARGS+=(--model "$MODEL")

# ---------- 带重试派活 ----------
OUT=""
for i in $(seq 1 $MAX_RETRY); do
  OUT=$(timeout "$TIMEOUT" agy "${ARGS[@]}" 2>&1 | tail -1)
  if echo "$OUT" | grep -q '"status":"SUCCESS"'; then
    break
  fi
  echo "[WARN] 第 $i 次失败，重试中..." >&2
done

if ! echo "$OUT" | grep -q '"status":"SUCCESS"'; then
  echo "[FAIL] $MAX_RETRY 次均失败。原始输出:" >&2
  echo "$OUT" >&2
  echo "" >&2
  echo "排查: 若报 Bad Gateway/EOF → 网络抖动，稍后重试。" >&2
  echo "     若报认证错误 → 交互式跑 agy 重新登录。" >&2
  rm -f "$BEFORE_LIST"
  exit 1
fi

# ---------- 校验 ----------
echo "$OUT"

CONV_ID=$(echo "$OUT" | grep -o '"conversation_id":"[^"]*"' | cut -d'"' -f4)

# 校验 1: 是否有被拒操作（= 权限没配好）
if echo "$OUT" | grep -q '"denied_actions"'; then
  echo "" >&2
  echo "[WARN] 存在 denied_actions —— 权限未配置好，部分操作被静默拒绝。" >&2
  echo "       修复: 创建 ~/.gemini/antigravity-cli/settings.json" >&2
  echo '       {"permissions":{"allow":["write_file(*)","read_file(*)","command(regex:.*)"]}}' >&2
fi

# 校验 2: 目标目录是否真有新文件
AFTER_LIST=$(mktemp)
find "$TARGET_DIR" -type f 2>/dev/null | sort > "$AFTER_LIST"
NEW_FILES=$(comm -13 "$BEFORE_LIST" "$AFTER_LIST")

if [ -n "$NEW_FILES" ]; then
  echo "" >&2
  echo "[OK] 新增文件:" >&2
  echo "$NEW_FILES" | sed 's/^/     /' >&2
else
  # 没新文件，检查是否落到 scratch
  SCRATCH_HIT=$(find "$HOME/.gemini/antigravity-cli/scratch" -type f -newermt '-5 minutes' 2>/dev/null | head -5)
  if [ -n "$SCRATCH_HIT" ]; then
    echo "" >&2
    echo "[WARN] 目标目录无新文件，但 scratch 目录有新文件（= 未正确声明工作区）:" >&2
    echo "$SCRATCH_HIT" | sed 's/^/     /' >&2
    rm -f "$BEFORE_LIST" "$AFTER_LIST"
    exit 3
  fi
fi

rm -f "$BEFORE_LIST" "$AFTER_LIST"

[ -n "$CONV_ID" ] && echo "" >&2 && echo "[INFO] conversation_id = $CONV_ID（可 --conversation 续接）" >&2
exit 0
