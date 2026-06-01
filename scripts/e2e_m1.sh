#!/usr/bin/env bash
# M1 集成测试 —— 手动跑,验证全栈(docker pg/redis + uvicorn)真的能提交/查询 Run。
#
# 前置:
#   docker compose up -d
#   uv run alembic upgrade head
#   uv run uvicorn app.main:app   # 另开一个终端
# 然后:
#   ./scripts/e2e_m1.sh
set -euo pipefail

BASE="${BASE:-http://localhost:8000}"
BODY=/tmp/e2e_m1_body.json
pass=0

assert_code() {  # assert_code <expected> <actual> <label>
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

echo "[2] 提交一个 run"
code=$(curl -s -o "$BODY" -w '%{http_code}' \
  -X POST "$BASE/runs" -H 'Content-Type: application/json' \
  -d '{"input":"summarize the repo"}')
assert_code 201 "$code" "POST /runs"
status=$(json "['status']"); [ "$status" = "queued" ] && echo "  ✅ status=queued" && pass=$((pass+1)) || { echo "  ❌ status=$status"; exit 1; }
RID=$(json "['id']"); echo "  run id = $RID"

echo "[3] 按 id 查"
code=$(curl -s -o "$BODY" -w '%{http_code}' "$BASE/runs/$RID")
assert_code 200 "$code" "GET /runs/{id}"
[ "$(json "['id']")" = "$RID" ] && echo "  ✅ id 一致" && pass=$((pass+1)) || { echo "  ❌ id 不一致"; exit 1; }

echo "[4] 列表"
code=$(curl -s -o "$BODY" -w '%{http_code}' "$BASE/runs")
assert_code 200 "$code" "GET /runs"

echo "[5] 查不存在的 run"
code=$(curl -s -o "$BODY" -w '%{http_code}' "$BASE/runs/00000000-0000-7000-8000-000000000000")
assert_code 404 "$code" "GET /runs/{unknown} -> 404"

echo
echo "🎉 M1 集成测试通过($pass 项断言)"
