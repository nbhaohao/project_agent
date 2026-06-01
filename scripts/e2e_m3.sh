#!/usr/bin/env bash
# M3 集成测试 — 验证真 LLM loop 全链路:提交 run → worker 调 LLM → status=succeeded + result 非空
#
# 前置(三个终端):
#   docker compose up -d && uv run alembic upgrade head
#   uv run uvicorn app.main:app          # 终端 A
#   uv run python -m app.worker          # 终端 B
# 然后:
#   ./scripts/e2e_m3.sh
#
# 需要 .env 里有 ANTHROPIC_API_KEY / ANTHROPIC_BASE_URL / MODEL_ID
set -euo pipefail

BASE="${BASE:-http://localhost:8000}"
BODY=/tmp/e2e_m3_body.json
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

echo "[1] readiness"
code=$(curl -s -o "$BODY" -w '%{http_code}' "$BASE/health/ready")
assert_code 200 "$code" "GET /health/ready"

echo "[2] 提交 run(触发 get_current_time 工具)"
code=$(curl -s -o "$BODY" -w '%{http_code}' \
  -X POST "$BASE/runs" -H 'Content-Type: application/json' \
  -d '{"input":"What is the current UTC time? Use the get_current_time tool and tell me the result."}')
assert_code 201 "$code" "POST /runs"
RID=$(json "['id']")
echo "  run id = $RID"

echo "[3] 等 LLM 处理(最多 60s)…"
for i in $(seq 1 60); do
  code=$(curl -s -o "$BODY" -w '%{http_code}' "$BASE/runs/$RID")
  status=$(json "['status']")
  echo "  t=${i}s status=$status"
  if [ "$status" = "succeeded" ] || [ "$status" = "failed" ]; then break; fi
  sleep 1
done

echo "[4] 验证最终状态"
code=$(curl -s -o "$BODY" -w '%{http_code}' "$BASE/runs/$RID")
assert_code 200 "$code" "GET /runs/{id}"

status=$(json "['status']")
[ "$status" = "succeeded" ] && echo "  ✅ status=succeeded" && pass=$((pass+1)) \
  || { echo "  ❌ status=$status"; cat "$BODY"; exit 1; }

result=$(json "['result']")
[ -n "$result" ] && [ "$result" != "None" ] && echo "  ✅ result 非空: ${result:0:80}…" && pass=$((pass+1)) \
  || { echo "  ❌ result 为空"; exit 1; }

echo
echo "🎉 M3 集成测试通过($pass 项断言) — 真 LLM loop 全链路验证"
