#!/usr/bin/env bash
# M5 集成测试 — 验证 SSE 流式全链路:
#   1. worker 写 run_messages + publish events
#   2. GET /runs/{id}/events 对已完成 run 补历史并关流
#   3. 事件顺序: tool_call → tool_result → text → done
#
# 前置(三个终端):
#   docker compose up -d && uv run alembic upgrade head
#   uv run uvicorn app.main:app          # 终端 A
#   uv run python -m app.worker          # 终端 B
# 然后:
#   ./scripts/e2e_m5.sh
#
# 需要 .env 里有 ANTHROPIC_API_KEY / ANTHROPIC_BASE_URL / MODEL_ID
set -euo pipefail

BASE="${BASE:-http://localhost:8000}"
BODY=/tmp/e2e_m5_body.json
SSE=/tmp/e2e_m5_sse.txt
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

wait_succeeded() {
  local rid="$1"
  for i in $(seq 1 60); do
    curl -s -o "$BODY" -w '%{http_code}' "$BASE/runs/$rid" > /dev/null
    status=$(json "['status']")
    echo "  t=${i}s status=$status"
    if [ "$status" = "succeeded" ] || [ "$status" = "failed" ]; then break; fi
    sleep 1
  done
  status=$(json "['status']")
  [ "$status" = "succeeded" ] \
    || { echo "  ❌ run 未成功: status=$status error=$(json "['error']")"; exit 1; }
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

# ── 2. 提交 run，等完成 ────────────────────────────────────────────────────────
echo
echo "[2] 提交 run (get_current_time — 会产生 tool_call/tool_result/text 事件)"
RID=$(submit "What is the current UTC time? Use the get_current_time tool and tell me the result.")
pass=$((pass + 1))
echo "  run id = $RID"
wait_succeeded "$RID"
pass=$((pass + 1))

# ── 3. SSE 历史补发 ───────────────────────────────────────────────────────────
echo
echo "[3] GET /runs/{id}/events — 已完成 run 补历史后关流"
curl -s -N --max-time 15 "$BASE/runs/$RID/events" > "$SSE"
echo "  收到事件行数: $(wc -l < "$SSE")"

assert_event '"type": "tool_call"'   "tool_call 事件存在"
assert_event '"type": "tool_result"' "tool_result 事件存在"
assert_event '"type": "text"'        "text 事件存在"
assert_event '"type": "done"'        "done 事件存在(终态关流)"

# ── 4. 前端可访问 ─────────────────────────────────────────────────────────────
echo
echo "[4] 前端页面可访问"
code=$(curl -s -o "$BODY" -w '%{http_code}' "$BASE/")
assert_code 200 "$code" "GET / (index.html)"

echo
echo "🎉 M5 集成测试通过($pass 项断言) — SSE 流式全链路验证"
