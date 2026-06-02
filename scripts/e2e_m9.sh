#!/usr/bin/env bash
# M9 集成测试 — 验证多 agent 编排全链路:
#   1. 主 agent 把网络任务委托给 researcher sub-agent
#   2. SSE 流中出现 delegate_to_researcher tool_call 事件
#   3. run 最终 succeeded，result 非空
#
# 前置(三个终端):
#   docker compose up -d && uv run alembic upgrade head
#   uv run uvicorn app.main:app          # 终端 A
#   uv run python -m app.worker          # 终端 B
# 然后:
#   ./scripts/e2e_m9.sh
#
# 需要 .env 里有:
#   ANTHROPIC_API_KEY / ANTHROPIC_BASE_URL / MODEL_ID
#   EMBEDDING_API_KEY
set -euo pipefail

BASE="${BASE:-http://localhost:8000}"
BODY=/tmp/e2e_m9_body.json
SSE=/tmp/e2e_m9_sse.txt
pass=0

assert_code() {
  if [ "$2" = "$1" ]; then
    echo "  ✅ $3 ($2)"
    pass=$((pass + 1))
  else
    echo "  ❌ $3 — 期望 $1 实际 $2"
    cat "$BODY"; exit 1
  fi
}

json() { python3 -c "import json,sys;print(json.load(open('$BODY'))$1)"; }

submit() {
  local prompt="$1"
  local code
  code=$(curl -s -o "$BODY" -w '%{http_code}' \
    -X POST "$BASE/runs" -H 'Content-Type: application/json' \
    -d "{\"input\":$(python3 -c "import json,sys;print(json.dumps(sys.argv[1]))" "$prompt")}")
  assert_code 201 "$code" "POST /runs" >&2
  json "['id']"
}

wait_terminal() {
  local rid="$1"
  for i in $(seq 1 120); do
    curl -s -o "$BODY" "$BASE/runs/$rid" > /dev/null
    local status
    status=$(json "['status']")
    echo "  t=${i}s status=$status" >&2
    if [ "$status" = "succeeded" ] || [ "$status" = "failed" ] || [ "$status" = "cancelled" ]; then
      break
    fi
    sleep 1
  done
  json "['status']"
}

assert_event() {
  local pattern="$1" label="$2"
  if grep -q "$pattern" "$SSE"; then
    echo "  ✅ $label"
    pass=$((pass + 1))
  else
    echo "  ❌ $label — 未找到 pattern: $pattern"
    cat "$SSE"; exit 1
  fi
}

# ── 1. readiness ──────────────────────────────────────────────────────────────
echo "[1] readiness"
code=$(curl -s -o "$BODY" -w '%{http_code}' "$BASE/health/ready")
assert_code 200 "$code" "GET /health/ready"

# ── 2. 提交多 agent 任务 ──────────────────────────────────────────────────────
echo
echo "[2] 提交多 agent 任务 — 主 agent 委托 researcher"
RID=$(submit "Use the delegate_to_researcher agent to fetch the URL https://httpbin.org/json and report back what JSON fields it contains.")
pass=$((pass + 1))
echo "  run id = $RID"

# ── 3. 等待完成(sub-agent 需要更长时间) ───────────────────────────────────────
echo
echo "[3] 等待 run 完成(最长 120s)"
status=$(wait_terminal "$RID")
if [ "$status" = "succeeded" ]; then
  echo "  ✅ run succeeded"
  pass=$((pass + 1))
else
  curl -s -o "$BODY" "$BASE/runs/$RID" > /dev/null
  echo "  ❌ run 未成功: status=$status error=$(json "['error']")"
  exit 1
fi

# ── 4. 验证 SSE 历史中有 delegate_to_researcher tool_call ────────────────────
echo
echo "[4] 验证 SSE 历史中出现 delegate_to_researcher"
curl -s -N --max-time 15 "$BASE/runs/$RID/events" > "$SSE"
echo "  收到事件行数: $(wc -l < "$SSE")"

assert_event "delegate_to_researcher" "delegate_to_researcher tool_call 出现在 SSE 流"
assert_event '"type": "done"'          "done 事件存在(终态关流)"

# ── 5. 验证 result 非空 ───────────────────────────────────────────────────────
echo
echo "[5] 验证 result 非空"
curl -s -o "$BODY" "$BASE/runs/$RID" > /dev/null
result=$(json "['result']")
if [ -n "$result" ] && [ "$result" != "None" ]; then
  echo "  ✅ result 非空"
  echo "  result: ${result:0:120}..."
  pass=$((pass + 1))
else
  echo "  ❌ result 为空"
  exit 1
fi

echo
echo "🎉 M9 集成测试通过($pass 项断言) — 多 agent 编排全链路验证"
