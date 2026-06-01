#!/usr/bin/env bash
# M4 集成测试 — 验证工具系统全链路:
#   1. get_current_time (无 capability 限制，M3 回归)
#   2. http_fetch       (network capability)
#   3. file_read        (fs_read capability)
#
# 前置(三个终端):
#   docker compose up -d && uv run alembic upgrade head
#   uv run uvicorn app.main:app          # 终端 A
#   uv run python -m app.worker          # 终端 B
# 然后:
#   ./scripts/e2e_m4.sh
#
# 需要 .env 里有 ANTHROPIC_API_KEY / ANTHROPIC_BASE_URL / MODEL_ID
set -euo pipefail

BASE="${BASE:-http://localhost:8000}"
BODY=/tmp/e2e_m4_body.json
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
  # 重定向到 stderr，避免被 $() 捕获混入 RID
  assert_code 201 "$code" "POST /runs" >&2
  json "['id']"
}

wait_succeeded() {
  local rid="$1" label="$2"
  for i in $(seq 1 60); do
    curl -s -o "$BODY" -w '%{http_code}' "$BASE/runs/$rid" > /dev/null
    status=$(json "['status']")
    echo "  t=${i}s status=$status"
    if [ "$status" = "succeeded" ] || [ "$status" = "failed" ]; then break; fi
    sleep 1
  done
  status=$(json "['status']")
  [ "$status" = "succeeded" ] && echo "  ✅ $label → succeeded" && pass=$((pass+1)) \
    || { echo "  ❌ $label → $status  error=$(json "['error']")"; exit 1; }
  result=$(json "['result']")
  [ -n "$result" ] && [ "$result" != "None" ] \
    && echo "  ✅ result 非空: ${result:0:100}…" && pass=$((pass+1)) \
    || { echo "  ❌ result 为空"; exit 1; }
}

# ── 1. readiness ──────────────────────────────────────────────────────────────
echo "[1] readiness"
code=$(curl -s -o "$BODY" -w '%{http_code}' "$BASE/health/ready")
assert_code 200 "$code" "GET /health/ready"

# ── 2. get_current_time (无 capability 限制，M3 回归) ─────────────────────────
echo
echo "[2] get_current_time — 无 capability 限制，M3 回归"
RID=$(submit "What is the current UTC time? Use the get_current_time tool and tell me the result.")
pass=$((pass+1))
echo "  run id = $RID"
wait_succeeded "$RID" "get_current_time"

# ── 3. http_fetch (network capability) ───────────────────────────────────────
echo
echo "[3] http_fetch — network capability"
RID=$(submit "Fetch https://httpbin.org/json using the http_fetch tool and summarise what you got back.")
pass=$((pass+1))
echo "  run id = $RID"
wait_succeeded "$RID" "http_fetch"

# ── 4. file_read (fs_read capability) ────────────────────────────────────────
echo
echo "[4] file_read — fs_read capability"
mkdir -p /tmp/agent_files
printf 'M4 test: hello from agent platform runtime' > /tmp/agent_files/hello.txt
RID=$(submit "Read the file hello.txt using the file_read tool and tell me exactly what it says.")
pass=$((pass+1))
echo "  run id = $RID"
wait_succeeded "$RID" "file_read"

echo
echo "🎉 M4 集成测试通过($pass 项断言) — 工具系统全链路验证"
