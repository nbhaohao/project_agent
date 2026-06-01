#!/usr/bin/env bash
# M2 集成测试 — 验证全链路：提交 run → worker 消费 → 状态变 succeeded
#
# 前置(三个终端):
#   docker compose up -d
#   uv run alembic upgrade head
#   uv run uvicorn app.main:app        # 终端 A
#   python -m app.worker               # 终端 B (或 uv run python -m app.worker)
# 然后:
#   ./scripts/e2e_m2.sh
set -euo pipefail

BASE="${BASE:-http://localhost:8000}"
BODY=/tmp/e2e_m2_body.json
pass=0

assert_code() {
  if [ "$2" = "$1" ]; then
    echo "  ✅ $3 ($2)"
    pass=$((pass + 1))
  else
    echo "  ❌ $3 — 期望 $1 实际 $2"
    cat "$BODY"
    exit 1
  fi
}

json() { python3 -c "import json,sys;print(json.load(open('$BODY'))$1)"; }

echo "[1] readiness"
code=$(curl -s -o "$BODY" -w '%{http_code}' "$BASE/health/ready")
assert_code 200 "$code" "GET /health/ready"

echo "[2] 提交 run"
code=$(curl -s -o "$BODY" -w '%{http_code}' \
  -X POST "$BASE/runs" -H 'Content-Type: application/json' \
  -d '{"input":"e2e m2 test"}')
assert_code 201 "$code" "POST /runs"
RID=$(json "['id']")
echo "  run id = $RID"

echo "[3] 等 worker 处理(最多 15s)…"
for i in $(seq 1 15); do
  code=$(curl -s -o "$BODY" -w '%{http_code}' "$BASE/runs/$RID")
  status=$(json "['status']")
  echo "  t=${i}s status=$status"
  if [ "$status" = "succeeded" ] || [ "$status" = "failed" ]; then
    break
  fi
  sleep 1
done

echo "[4] 验证最终状态"
code=$(curl -s -o "$BODY" -w '%{http_code}' "$BASE/runs/$RID")
assert_code 200 "$code" "GET /runs/{id}"
status=$(json "['status']")
[ "$status" = "succeeded" ] && echo "  ✅ status=succeeded" && pass=$((pass+1)) \
  || { echo "  ❌ status=$status (期望 succeeded)"; exit 1; }

echo
echo "🎉 M2 集成测试通过($pass 项断言)"
