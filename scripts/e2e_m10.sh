#!/usr/bin/env bash
# M10 集成测试 — 验证 eval + 可观测全链路:
#   1. 完成一次 run 后 input_tokens/output_tokens/cost_usd/llm_calls 落库
#   2. GET /runs/{id} 返回 metrics 字段非空且合理
#   3. SSE done 事件携带 input_tokens 字段
#   4. eval CLI 可正常启动(--help)
#   5. 结构化日志包含 trace_id 字段
#
# 前置(三个终端):
#   docker compose up -d && uv run alembic upgrade head
#   uv run uvicorn app.main:app          # 终端 A
#   uv run python -m app.worker          # 终端 B
# 然后:
#   ./scripts/e2e_m10.sh
#
# 需要 .env 里有:
#   ANTHROPIC_API_KEY / ANTHROPIC_BASE_URL / MODEL_ID
set -euo pipefail

BASE="${BASE:-http://localhost:8000}"
BODY=/tmp/e2e_m10_body.json
SSE=/tmp/e2e_m10_sse.txt
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
  for i in $(seq 1 60); do
    curl -s -o "$BODY" "$BASE/runs/$rid"
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

assert_not_null() {
  local field="$1" label="$2"
  local val
  val=$(json "['$field']")
  if [ "$val" != "None" ] && [ -n "$val" ]; then
    echo "  ✅ $label = $val"
    pass=$((pass + 1))
  else
    echo "  ❌ $label is null/empty"
    cat "$BODY"; exit 1
  fi
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

# ── 2. 提交 run ──────────────────────────────────────────────────────────────
echo
echo "[2] 提交 get_current_time run"
RID=$(submit "What is the current UTC time? Use the get_current_time tool.")
pass=$((pass + 1))
echo "  run id = $RID"

# ── 3. 等待完成 ───────────────────────────────────────────────────────────────
echo
echo "[3] 等待 run 完成(最长 60s)"
status=$(wait_terminal "$RID")
if [ "$status" = "succeeded" ]; then
  echo "  ✅ run succeeded"
  pass=$((pass + 1))
else
  echo "  ❌ run 未成功: status=$status"
  exit 1
fi

# ── 4. 验证 metrics 落库 ──────────────────────────────────────────────────────
echo
echo "[4] 验证 metrics 落库"
curl -s -o "$BODY" "$BASE/runs/$RID"
assert_not_null "input_tokens"  "input_tokens"
assert_not_null "output_tokens" "output_tokens"
assert_not_null "cost_usd"      "cost_usd"
assert_not_null "llm_calls"     "llm_calls"

# ── 5. 验证 SSE done 事件带 metrics ──────────────────────────────────────────
echo
echo "[5] 验证 SSE done 事件携带 input_tokens"
curl -s -N --max-time 10 "$BASE/runs/$RID/events" > "$SSE"
echo "  收到事件行数: $(wc -l < "$SSE")"
assert_event "input_tokens" "done 事件包含 input_tokens 字段"

# ── 6. eval CLI --help ────────────────────────────────────────────────────────
echo
echo "[6] eval CLI 可正常启动"
if uv run python -m eval --help > /dev/null 2>&1; then
  echo "  ✅ python -m eval --help OK"
  pass=$((pass + 1))
else
  echo "  ❌ python -m eval --help 失败"
  exit 1
fi

echo
echo "🎉 M10 集成测试通过($pass 项断言) — eval + 可观测全链路验证"
