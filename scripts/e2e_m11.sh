#!/usr/bin/env bash
# M11 集成测试 — 验证容器化全栈部署:
#   1. docker compose 全栈健康(postgres + redis + migrate + api + worker)
#   2. GET /health/ready → 200, postgres + redis ok
#   3. 提交 run → 容器化 worker 执行 → succeeded
#   4. run 结果带 metrics(input_tokens 非空) — M10 特性在容器里仍可用
#   5. SSE done 事件携带 input_tokens
#   6. 前端静态文件可访问(index.html 含 trace_id)
#
# 前置:
#   cp .env.example .env  # 填入 LLM/Embedding 密钥
#   docker compose up -d  # 一键起全栈
# 然后:
#   ./scripts/e2e_m11.sh
set -euo pipefail

BASE="${BASE:-http://localhost:8000}"
BODY=/tmp/e2e_m11_body.json
SSE=/tmp/e2e_m11_sse.txt
pass=0

assert_code() {
  if [ "$2" = "$1" ]; then
    echo "  ✅ $3 ($2)"
    pass=$((pass + 1))
  else
    echo "  ❌ $3 — 期望 $1 实际 $2"
    cat "$BODY" 2>/dev/null || true; exit 1
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

# ── 1. API 健康 ──────────────────────────────────────────────────────────────
echo "[1] 容器化 API 健康检查"
code=$(curl -s -o "$BODY" -w '%{http_code}' "$BASE/health/ready")
assert_code 200 "$code" "GET /health/ready"
# 验证 postgres + redis 都 ok
checks=$(python3 -c "import json,sys; d=json.load(open('$BODY')); print(d['checks']['postgres'], d['checks']['redis'])")
if [ "$checks" = "ok ok" ]; then
  echo "  ✅ postgres=ok redis=ok"
  pass=$((pass + 1))
else
  echo "  ❌ 基建未就绪: $checks"; exit 1
fi

# ── 2. 前端静态文件可访问 ──────────────────────────────────────────────────────
echo
echo "[2] 前端静态文件"
code=$(curl -s -o "$BODY" -w '%{http_code}' "$BASE/")
assert_code 200 "$code" "GET / (index.html)"
if grep -q "trace_id" "$BODY"; then
  echo "  ✅ index.html 包含 trace_id UI"
  pass=$((pass + 1))
else
  echo "  ❌ index.html 未找到 trace_id 关键字"; exit 1
fi

# ── 3. 提交 run，容器化 worker 执行 ──────────────────────────────────────────
echo
echo "[3] 提交 run — 容器化 worker 执行"
RID=$(submit "What is the current UTC time? Use the get_current_time tool.")
pass=$((pass + 1))
echo "  run id (= trace_id) = $RID"

# ── 4. 等待完成 ───────────────────────────────────────────────────────────────
echo
echo "[4] 等待 run 完成(最长 60s)"
status=$(wait_terminal "$RID")
if [ "$status" = "succeeded" ]; then
  echo "  ✅ run succeeded"
  pass=$((pass + 1))
else
  echo "  ❌ run 未成功: status=$status"; exit 1
fi

# ── 5. metrics 落库 ───────────────────────────────────────────────────────────
echo
echo "[5] metrics 落库(M10 特性在容器里仍可用)"
curl -s -o "$BODY" "$BASE/runs/$RID"
assert_not_null "input_tokens" "input_tokens"
assert_not_null "llm_calls"    "llm_calls"

# ── 6. SSE done 事件携带 metrics ─────────────────────────────────────────────
echo
echo "[6] SSE done 事件携带 input_tokens"
curl -s -N --max-time 10 "$BASE/runs/$RID/events" > "$SSE"
assert_event "input_tokens" "done 事件包含 input_tokens"

echo
echo "🎉 M11 集成测试通过($pass 项断言) — 容器化全栈部署验证"
